from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import ENV_FILE_PATH


TELEGRAM_API_ID_ENV = "RSVP_TELEGRAM_API_ID"
TELEGRAM_API_HASH_ENV = "RSVP_TELEGRAM_API_HASH"


@dataclass(frozen=True)
class TelegramEnvSettings:
    api_id: str
    api_hash: str


@dataclass(frozen=True)
class TelegramEnvValidationResult:
    is_valid: bool
    errors: list[str]


def load_telegram_env_settings() -> TelegramEnvSettings:
    """
    Load Telegram API settings from the current process environment.

    app.core.config already loads .env during app startup.
    """

    return TelegramEnvSettings(
        api_id=os.getenv(TELEGRAM_API_ID_ENV, "").strip(),
        api_hash=os.getenv(TELEGRAM_API_HASH_ENV, "").strip(),
    )


def validate_telegram_env_settings(
    api_id: str,
    api_hash: str,
) -> TelegramEnvValidationResult:
    errors: list[str] = []

    cleaned_api_id = api_id.strip()
    cleaned_api_hash = api_hash.strip()

    if not cleaned_api_id:
        errors.append("Telegram API ID is required.")
    else:
        try:
            int(cleaned_api_id)
        except ValueError:
            errors.append("Telegram API ID must be a number.")

    if not cleaned_api_hash:
        errors.append("Telegram API hash is required.")

    elif len(cleaned_api_hash) < 10:
        errors.append("Telegram API hash looks too short.")

    return TelegramEnvValidationResult(
        is_valid=not errors,
        errors=errors,
    )


def save_telegram_env_settings(
    api_id: str,
    api_hash: str,
) -> None:
    """
    Save Telegram API settings to .env next to the app.

    Also updates os.environ immediately, so the running app can use the new values
    without requiring restart.
    """

    cleaned_api_id = api_id.strip()
    cleaned_api_hash = api_hash.strip()

    validation = validate_telegram_env_settings(
        api_id=cleaned_api_id,
        api_hash=cleaned_api_hash,
    )

    if not validation.is_valid:
        raise ValueError(" ".join(validation.errors))

    ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"{TELEGRAM_API_ID_ENV}={cleaned_api_id}",
        f"{TELEGRAM_API_HASH_ENV}={cleaned_api_hash}",
        "",
    ]

    ENV_FILE_PATH.write_text("\n".join(lines), encoding="utf-8")

    os.environ[TELEGRAM_API_ID_ENV] = cleaned_api_id
    os.environ[TELEGRAM_API_HASH_ENV] = cleaned_api_hash