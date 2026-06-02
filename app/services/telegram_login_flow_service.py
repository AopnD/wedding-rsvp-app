from __future__ import annotations

import logging
from dataclasses import dataclass

from telethon.errors import (
    ApiIdInvalidError,
    AuthRestartError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from app.services.telegram_service import (
    TelegramAccountInfo,
    TelegramLoginError,
    TelegramServiceError,
    create_telegram_client,
    _account_info_from_user,
)


logger = logging.getLogger(__name__)


@dataclass
class TelegramLoginFlow:
    """
    Holds the temporary Telegram login state while the app is open.

    The phone_code_hash is returned by Telegram after requesting a login code.
    It is required when submitting the code.
    """

    phone_number: str | None = None
    phone_code_hash: str | None = None


@dataclass(frozen=True)
class TelegramCodeRequestResult:
    phone_number: str
    message: str


@dataclass(frozen=True)
class TelegramSignInResult:
    account: TelegramAccountInfo
    message: str


async def request_login_code_async(
    flow: TelegramLoginFlow,
    phone_number: str,
) -> TelegramCodeRequestResult:
    """
    Ask Telegram to send a login code to the user's Telegram account.

    This is the real point where fake API ID/API hash values usually fail.
    If Telegram asks to restart the auth process, we retry once with a fresh client.
    """

    cleaned_phone_number = phone_number.strip()

    if not cleaned_phone_number:
        raise TelegramLoginError("Phone number is required.")

    last_error: Exception | None = None

    for attempt in range(1, 3):
        client = create_telegram_client()

        try:
            await client.connect()

            sent_code = await client.send_code_request(cleaned_phone_number)

            flow.phone_number = cleaned_phone_number
            flow.phone_code_hash = sent_code.phone_code_hash

            logger.info(
                "Telegram login code requested successfully. attempt=%s",
                attempt,
            )

            return TelegramCodeRequestResult(
                phone_number=cleaned_phone_number,
                message="Telegram sent a login code. Please enter it below.",
            )

        except ApiIdInvalidError as exc:
            raise TelegramLoginError(
                "Telegram rejected these API settings. "
                "Please check your API ID and API hash."
            ) from exc

        except PhoneNumberInvalidError as exc:
            raise TelegramLoginError(
                "Telegram says this phone number is invalid. "
                "Use international format, for example +351912345678."
            ) from exc

        except AuthRestartError as exc:
            last_error = exc
            logger.warning(
                "Telegram asked to restart authorization. attempt=%s",
                attempt,
            )

            # Retry once. If the second attempt also fails, we show a clear error.
            continue

        except ConnectionError as exc:
            last_error = exc
            logger.warning(
                "Telegram connection dropped while requesting login code. attempt=%s",
                attempt,
            )

            # Retry once. This can happen after AuthRestartError.
            continue

        except TelegramServiceError:
            raise

        except Exception as exc:
            logger.exception("Failed to request Telegram login code.")
            raise TelegramLoginError(
                "Could not request Telegram login code. "
                "Please check your Telegram API ID, API hash, phone number, and internet connection."
            ) from exc

        finally:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Failed to disconnect Telegram client after code request.")

    logger.exception(
        "Telegram login code request failed after retry.",
        exc_info=last_error,
    )

    raise TelegramLoginError(
        "Telegram asked to restart the login process and the retry also failed. "
        "Please close the app, reopen it, and try again. "
        "If this keeps happening, delete data/telegram and try the Telegram login again."
    )


async def sign_in_with_code_async(
    flow: TelegramLoginFlow,
    code: str,
) -> TelegramSignInResult:
    """
    Complete Telegram login using the code sent by Telegram.

    If the account has 2FA enabled, this raises SessionPasswordNeededError.
    The UI should then show a password field.
    """

    cleaned_code = code.strip().replace(" ", "")

    if not cleaned_code:
        raise TelegramLoginError("Login code is required.")

    if not flow.phone_number or not flow.phone_code_hash:
        raise TelegramLoginError(
            "Please request a Telegram login code before submitting the code."
        )

    client = create_telegram_client()

    try:
        await client.connect()

        await client.sign_in(
            phone=flow.phone_number,
            code=cleaned_code,
            phone_code_hash=flow.phone_code_hash,
        )

        me = await client.get_me()

        if me is None:
            raise TelegramLoginError("Could not read Telegram account after login.")

        account = _account_info_from_user(me)

        logger.info(
            "Telegram login completed with code. user_id=%s username=%s",
            account.user_id,
            account.username,
        )

        return TelegramSignInResult(
            account=account,
            message=f"Telegram login successful. Connected as {account.display_name}.",
        )

    except SessionPasswordNeededError:
        raise

    except PhoneCodeInvalidError as exc:
        raise TelegramLoginError("The Telegram login code is invalid.") from exc

    except PhoneCodeExpiredError as exc:
        raise TelegramLoginError(
            "The Telegram login code expired. Please request a new code."
        ) from exc

    except TelegramServiceError:
        raise

    except Exception as exc:
        logger.exception("Failed to sign in with Telegram code.")
        raise TelegramLoginError(f"Telegram login failed: {exc}") from exc

    finally:
        await client.disconnect()


async def sign_in_with_password_async(
    password: str,
) -> TelegramSignInResult:
    """
    Complete Telegram login when the account has two-step verification enabled.
    """

    cleaned_password = password.strip()

    if not cleaned_password:
        raise TelegramLoginError("Telegram 2FA password is required.")

    client = create_telegram_client()

    try:
        await client.connect()

        await client.sign_in(password=cleaned_password)

        me = await client.get_me()

        if me is None:
            raise TelegramLoginError("Could not read Telegram account after login.")

        account = _account_info_from_user(me)

        logger.info(
            "Telegram login completed with 2FA password. user_id=%s username=%s",
            account.user_id,
            account.username,
        )

        return TelegramSignInResult(
            account=account,
            message=f"Telegram login successful. Connected as {account.display_name}.",
        )

    except TelegramServiceError:
        raise

    except Exception as exc:
        logger.exception("Failed to sign in with Telegram 2FA password.")
        raise TelegramLoginError(
            "Telegram 2FA login failed. Please check your password."
        ) from exc

    finally:
        await client.disconnect()


def request_login_code(
    flow: TelegramLoginFlow,
    phone_number: str,
) -> TelegramCodeRequestResult:
    import asyncio

    return asyncio.run(
        request_login_code_async(
            flow=flow,
            phone_number=phone_number,
        )
    )


def sign_in_with_code(
    flow: TelegramLoginFlow,
    code: str,
) -> TelegramSignInResult:
    import asyncio

    return asyncio.run(
        sign_in_with_code_async(
            flow=flow,
            code=code,
        )
    )


def sign_in_with_password(
    password: str,
) -> TelegramSignInResult:
    import asyncio

    return asyncio.run(
        sign_in_with_password_async(password=password)
    )