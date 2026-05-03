from __future__ import annotations

from app.core.database import SessionLocal, create_database
from app.models import Event, Guest
from app.services.invite_code_service import generate_unique_invite_code


def main() -> None:
    create_database()

    db = SessionLocal()

    try:
        event = Event(
            couple_names="Omer & Dana",
            wedding_date="2026-09-01",
            venue_name="Example Venue",
            venue_address="Example Address",
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        invite_code = generate_unique_invite_code(db)

        guest = Guest(
            event_id=event.id,
            full_name="Test Guest",
            phone_number="+351900000000",
            telegram_username=None,
            invite_code=invite_code,
            invited_count=2,
            is_matched_telegram_contact=False,
        )

        db.add(guest)
        db.commit()
        db.refresh(guest)

        print("Test RSVP guest created.")
        print(f"Guest ID: {guest.id}")
        print(f"Guest name: {guest.full_name}")
        print()
        print("Open this link in your browser:")
        print(f"http://127.0.0.1:8000/rsvp/{guest.invite_code}")

    finally:
        db.close()


if __name__ == "__main__":
    main()