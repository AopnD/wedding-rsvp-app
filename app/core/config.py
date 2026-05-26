from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

ENV_FILE_PATH = BASE_DIR / ".env"

# Load local environment variables from .env.
# This does not replace real OS environment variables.
# It only fills missing values from the .env file.
load_dotenv(dotenv_path=ENV_FILE_PATH)


DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "rsvp_app.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

TELEGRAM_DATA_DIR = DATA_DIR / "telegram"
TELEGRAM_SESSION_PATH = TELEGRAM_DATA_DIR / "rsvp_app_telegram.session"