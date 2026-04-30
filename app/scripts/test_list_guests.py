from __future__ import annotations

from app.core.database import SessionLocal
from app.models import Guest


def main() -> None:
    db = SessionLocal()

    try:
        guests = db.query(Guest).all()

        print(f"Total guests in database: {len(guests)}")
        print("-" * 50)

        for guest in guests:
            print(
                f"id={guest.id}, "
                f"event_id={guest.event_id}, "
                f"name={guest.full_name}, "
                f"phone={guest.phone_number}, "
                f"invited_count={guest.invited_count}, "
                f"matched_telegram={guest.is_matched_telegram_contact}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()