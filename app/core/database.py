from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATA_DIR, DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_database() -> None:
    """
    Create the local data folder and all database tables.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Import models here so SQLAlchemy knows about them before creating tables.
    from app.models import event, guest, message, rsvp  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db_session():
    """
    Small helper for scripts and later for the app services.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()