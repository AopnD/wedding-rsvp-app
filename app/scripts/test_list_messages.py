from __future__ import annotations

from app.core.database import SessionLocal
from app.models import Guest, Message


def main() -> None:
    db = SessionLocal()

    try:
        messages = (
            db.query(Message)
            .join(Guest)
            .order_by(Message.created_at.desc())
            .all()
        )

        print(f"Total invitation messages: {len(messages)}")
        print("-" * 80)

        if not messages:
            print("No invitation messages found yet.")
            return

        for message in messages:
            print(
                f"id={message.id}, "
                f"guest={message.guest.full_name}, "
                f"phone={message.guest.phone_number}, "
                f"status={message.status}, "
                f"telegram_message_id={message.telegram_message_id}, "
                f"sent_at={message.sent_at}, "
                f"created_at={message.created_at}"
            )

            if message.error_message:
                print(f"error={message.error_message}")

            print("-" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()