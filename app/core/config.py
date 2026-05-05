from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "rsvp_app.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

TELEGRAM_DATA_DIR = DATA_DIR / "telegram"
TELEGRAM_SESSION_PATH = TELEGRAM_DATA_DIR / "rsvp_app_telegram.session"