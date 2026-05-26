from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

import phonenumbers
from sqlalchemy.orm import Session
from telethon import TelegramClient, functions
from telethon.errors import SessionPasswordNeededError
from telethon.tl import types

from app.core.config import TELEGRAM_DATA_DIR, TELEGRAM_SESSION_PATH
from app.models import Guest


logger = logging.getLogger(__name__)


class TelegramServiceError(Exception):
    """Base error for Telegram integration."""


class TelegramConfigError(TelegramServiceError):
    """Raised when Telegram API credentials are missing or invalid."""


class TelegramLoginError(TelegramServiceError):
    """Raised when Telegram login fails."""


class TelegramNotLoggedInError(TelegramServiceError):
    """Raised when the local Telegram session is not logged in."""


@dataclass(frozen=True)
class TelegramCredentials:
    api_id: int
    api_hash: str


@dataclass(frozen=True)
class TelegramAccountInfo:
    user_id: int
    display_name: str
    username: str | None
    phone: str | None


@dataclass(frozen=True)
class TelegramContactInfo:
    user_id: int
    display_name: str
    username: str | None
    phone: str | None
    normalized_phone: str | None


@dataclass(frozen=True)
class TelegramGuestMatch:
    guest_id: int
    guest_name: str
    phone_number: str | None
    is_matched: bool
    telegram_username: str | None


@dataclass(frozen=True)
class TelegramMatchResult:
    total_guests: int
    matched_count: int
    unmatched_count: int
    matches: list[TelegramGuestMatch]


def get_telegram_credentials_from_env() -> TelegramCredentials:
    """
    Read Telegram API credentials.

    Credentials can come from:
    - the local .env file in the project root
    - real OS environment variables

    Required values:
    - RSVP_TELEGRAM_API_ID
    - RSVP_TELEGRAM_API_HASH
    """

    api_id_raw = os.getenv("RSVP_TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("RSVP_TELEGRAM_API_HASH", "").strip()

    if not api_id_raw:
        raise TelegramConfigError(
            "Missing RSVP_TELEGRAM_API_ID environment variable."
        )

    if not api_hash:
        raise TelegramConfigError(
            "Missing RSVP_TELEGRAM_API_HASH environment variable."
        )

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise TelegramConfigError(
            "RSVP_TELEGRAM_API_ID must be a number."
        ) from exc

    return TelegramCredentials(
        api_id=api_id,
        api_hash=api_hash,
    )


def create_telegram_client() -> TelegramClient:
    """
    Create a Telethon client using the local app session path.
    """

    credentials = get_telegram_credentials_from_env()

    TELEGRAM_DATA_DIR.mkdir(parents=True, exist_ok=True)

    return TelegramClient(
        str(TELEGRAM_SESSION_PATH),
        credentials.api_id,
        credentials.api_hash,
    )


async def login_with_phone_async(phone_number: str) -> TelegramAccountInfo:
    """
    Log in to Telegram using the user's phone number.

    Telethon will ask for the login code in the terminal.
    If the account has two-step verification enabled, it may ask for the password too.
    """

    cleaned_phone_number = phone_number.strip()

    if not cleaned_phone_number:
        raise TelegramLoginError("Phone number is required.")

    client = create_telegram_client()

    try:
        await client.start(phone=cleaned_phone_number)

        me = await client.get_me()

        if me is None:
            raise TelegramLoginError("Could not read Telegram account after login.")

        logger.info(
            "Telegram login successful. user_id=%s username=%s",
            me.id,
            me.username,
        )

        return _account_info_from_user(me)

    except SessionPasswordNeededError as exc:
        raise TelegramLoginError(
            "This Telegram account requires two-step verification. "
            "Please run the login script again and enter your Telegram password when asked."
        ) from exc

    except TelegramServiceError:
        raise

    except Exception as exc:
        logger.exception("Telegram login failed.")
        raise TelegramLoginError(f"Telegram login failed: {exc}") from exc

    finally:
        await client.disconnect()


def login_with_phone(phone_number: str) -> TelegramAccountInfo:
    """
    Sync wrapper for scripts and the Flet UI.
    """

    return asyncio.run(login_with_phone_async(phone_number))


async def is_telegram_logged_in_async() -> bool:
    """
    Check whether the local Telegram session is already authorized.
    """

    client = create_telegram_client()

    try:
        await client.connect()
        return await client.is_user_authorized()

    finally:
        await client.disconnect()


def is_telegram_logged_in() -> bool:
    """
    Sync wrapper for scripts and the Flet UI.
    """

    return asyncio.run(is_telegram_logged_in_async())


async def load_telegram_contacts_async(
    default_phone_region: str = "PT",
) -> list[TelegramContactInfo]:
    """
    Load contacts from the logged-in Telegram account.
    """

    client = create_telegram_client()

    try:
        await client.connect()

        if not await client.is_user_authorized():
            raise TelegramNotLoggedInError(
                "Telegram is not logged in yet. Run the Telegram login step first."
            )

        contacts_result = await client(functions.contacts.GetContactsRequest(hash=0))
        contacts = contacts_result.users

        results: list[TelegramContactInfo] = []

        for contact in contacts:
            if not isinstance(contact, types.User):
                continue

            results.append(
                TelegramContactInfo(
                    user_id=contact.id,
                    display_name=_build_display_name(contact),
                    username=contact.username,
                    phone=contact.phone,
                    normalized_phone=_normalize_telegram_phone(
                        contact.phone,
                        default_region=default_phone_region,
                    ),
                )
            )

        logger.info("Loaded Telegram contacts. count=%s", len(results))

        return results

    except TelegramServiceError:
        raise

    except Exception as exc:
        logger.exception("Failed to load Telegram contacts.")
        raise TelegramServiceError(f"Failed to load Telegram contacts: {exc}") from exc

    finally:
        await client.disconnect()


def load_telegram_contacts(
    default_phone_region: str = "PT",
) -> list[TelegramContactInfo]:
    """
    Sync wrapper for scripts and the Flet UI.
    """

    return asyncio.run(
        load_telegram_contacts_async(default_phone_region=default_phone_region)
    )


def match_event_guests_with_telegram_contacts(
    db: Session,
    event_id: int,
    default_phone_region: str = "PT",
) -> TelegramMatchResult:
    """
    Match imported guests against the user's Telegram contacts.

    Safety behavior:
    - Only matches guests already imported into the local database.
    - Does not import new phone numbers into Telegram.
    - Does not send any messages.
    - Only sets is_matched_telegram_contact and telegram_username.
    """

    contacts = load_telegram_contacts(default_phone_region=default_phone_region)

    contacts_by_phone = {
        contact.normalized_phone: contact
        for contact in contacts
        if contact.normalized_phone
    }

    guests = (
        db.query(Guest)
        .filter(Guest.event_id == event_id)
        .order_by(Guest.id.asc())
        .all()
    )

    matches: list[TelegramGuestMatch] = []
    matched_count = 0

    for guest in guests:
        contact = contacts_by_phone.get(guest.phone_number or "")

        if contact is None:
            guest.is_matched_telegram_contact = False
            guest.telegram_username = None

            matches.append(
                TelegramGuestMatch(
                    guest_id=guest.id,
                    guest_name=guest.full_name,
                    phone_number=guest.phone_number,
                    is_matched=False,
                    telegram_username=None,
                )
            )
            continue

        guest.is_matched_telegram_contact = True
        guest.telegram_username = contact.username

        matched_count += 1

        matches.append(
            TelegramGuestMatch(
                guest_id=guest.id,
                guest_name=guest.full_name,
                phone_number=guest.phone_number,
                is_matched=True,
                telegram_username=contact.username,
            )
        )

    db.commit()

    unmatched_count = len(guests) - matched_count

    logger.info(
        "Telegram guest matching finished. event_id=%s total=%s matched=%s unmatched=%s",
        event_id,
        len(guests),
        matched_count,
        unmatched_count,
    )

    return TelegramMatchResult(
        total_guests=len(guests),
        matched_count=matched_count,
        unmatched_count=unmatched_count,
        matches=matches,
    )


def _account_info_from_user(user: types.User) -> TelegramAccountInfo:
    return TelegramAccountInfo(
        user_id=user.id,
        display_name=_build_display_name(user),
        username=user.username,
        phone=user.phone,
    )


def _build_display_name(user: types.User) -> str:
    parts = [
        user.first_name or "",
        user.last_name or "",
    ]

    display_name = " ".join(part for part in parts if part).strip()

    if display_name:
        return display_name

    if user.username:
        return f"@{user.username}"

    return str(user.id)


def _normalize_telegram_phone(
    phone_number: str | None,
    default_region: str,
) -> str | None:
    """
    Normalize Telegram contact phone numbers to E.164.

    Telegram often returns contact phones without '+', for example:
    351912345678 instead of +351912345678.
    """

    if not phone_number:
        return None

    cleaned_phone = str(phone_number).strip()

    if not cleaned_phone:
        return None

    if not cleaned_phone.startswith("+"):
        cleaned_phone = f"+{cleaned_phone}"

    try:
        parsed_number = phonenumbers.parse(cleaned_phone, default_region)
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed_number):
        return None

    return phonenumbers.format_number(
        parsed_number,
        phonenumbers.PhoneNumberFormat.E164,
    )