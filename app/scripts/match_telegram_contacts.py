from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.models import Event
from app.services.telegram_service import (
    TelegramServiceError,
    match_event_guests_with_telegram_contacts,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    db = SessionLocal()

    try:
        event = (
            db.query(Event)
            .order_by(Event.id.desc())
            .first()
        )

        if event is None:
            print("No event found.")
            print("Import guests from the UI first, then run this script again.")
            return

        result = match_event_guests_with_telegram_contacts(
            db=db,
            event_id=event.id,
        )

        print("Telegram matching finished.")
        print(f"Event ID: {event.id}")
        print(f"Total guests: {result.total_guests}")
        print(f"Matched: {result.matched_count}")
        print(f"Unmatched: {result.unmatched_count}")
        print("-" * 80)

        for match in result.matches:
            status = "MATCHED" if match.is_matched else "NOT MATCHED"
            username = f"@{match.telegram_username}" if match.telegram_username else ""
            print(
                f"{status} | "
                f"{match.guest_name} | "
                f"{match.phone_number or ''} | "
                f"{username}"
            )

    except TelegramServiceError as exc:
        print(f"Telegram matching failed: {exc}")

    finally:
        db.close()


if __name__ == "__main__":
    main()