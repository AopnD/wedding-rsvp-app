from sqlalchemy.orm import Session

from app.core.database import SessionLocal, create_database
from app.models import Event, Guest


def create_test_guest(db: Session) -> Guest:
    event = Event(
        couple_names="Omer & Partner",
        wedding_date="2026-09-01",
        venue_name="Example Venue",
        venue_address="Example Address",
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    guest = Guest(
        event_id=event.id,
        full_name="Test Guest",
        phone_number="+351900000000",
        telegram_username=None,
        invited_count=2,
        is_matched_telegram_contact=False,
    )

    db.add(guest)
    db.commit()
    db.refresh(guest)

    return guest


def main() -> None:
    create_database()

    db = SessionLocal()

    try:
        guest = create_test_guest(db)
        print("Guest created successfully.")
        print(f"Guest ID: {guest.id}")
        print(f"Guest name: {guest.full_name}")
        print(f"Event ID: {guest.event_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()