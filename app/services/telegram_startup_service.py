from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.services.env_settings_service import (
    load_telegram_env_settings,
    validate_telegram_env_settings,
)
from app.services.telegram_service import (
    TelegramConfigError,
    TelegramServiceError,
    is_telegram_logged_in,
)


logger = logging.getLogger(__name__)


TelegramStartupMode = Literal[
    "credentials_required",
    "login_required",
    "ready",
]


@dataclass(frozen=True)
class TelegramStartupState:
    mode: TelegramStartupMode
    message: str


def check_telegram_startup_state() -> TelegramStartupState:
    """
    Decide where the app should route the user on startup.

    Alpha behavior:
    - Missing/invalid API credentials -> Telegram setup screen
    - Valid credentials but no saved Telegram session -> Telegram login screen
    - Valid credentials and saved session -> normal app flow
    """

    settings = load_telegram_env_settings()

    validation = validate_telegram_env_settings(
        api_id=settings.api_id,
        api_hash=settings.api_hash,
    )

    if not validation.is_valid:
        return TelegramStartupState(
            mode="credentials_required",
            message="Telegram API settings are missing or invalid.",
        )

    try:
        if is_telegram_logged_in():
            return TelegramStartupState(
                mode="ready",
                message="Telegram is already connected.",
            )

        return TelegramStartupState(
            mode="login_required",
            message="Telegram API settings are saved, but Telegram is not logged in yet.",
        )

    except TelegramConfigError as exc:
        logger.warning("Telegram configuration error on startup: %s", exc)
        return TelegramStartupState(
            mode="credentials_required",
            message=str(exc),
        )

    except TelegramServiceError as exc:
        logger.warning("Telegram service error on startup: %s", exc)
        return TelegramStartupState(
            mode="login_required",
            message=str(exc),
        )

    except Exception:
        logger.exception("Unexpected Telegram startup check error.")
        return TelegramStartupState(
            mode="login_required",
            message=(
                "Could not check Telegram login status. "
                "Please review your Telegram setup."
            ),
        )