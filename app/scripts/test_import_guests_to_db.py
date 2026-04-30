from __future__ import annotations

from pathlib import Path

from app.core.database import SessionLocal, create_database
from app.models import Event
from app.services.guest_import_db_service import import_valid_guests_to_database


def create_test_event_if_needed() -> int:
    """
    Creates a simple test event and returns its ID.

    Later, the real Flet UI will create/select the event.
    For now, this gives us a safe event_id to attach imported guests to.
    """

    db = SessionLocal()

    try:
        event = Event(
            couple_names="Omer & Partner",
            wedding_date="2026-09-01",
            venue_name="Example Venue",
            venue_address="Example Address",
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return event.id

    finally:
        db.close()


def main() -> None:
    create_database()

    file_path = Path("sample_guests.csv")
    event_id = create_test_event_if_needed()

    db = SessionLocal()

    try:
        saved_count, invalid_count = import_valid_guests_to_database(
            db=db,
            file_path=file_path,
            event_id=event_id,
        )

        print("Guest import finished.")
        print(f"Event ID: {event_id}")
        print(f"Saved guests: {saved_count}")
        print(f"Invalid rows skipped: {invalid_count}")

    finally:
        db.close()


if __name__ == "__main__":
    main()