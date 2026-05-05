from __future__ import annotations

from app.core.database import SessionLocal, create_database
from app.services.reset_service import delete_all_local_data


def main() -> None:
    create_database()

    db = SessionLocal()

    try:
        result = delete_all_local_data(db)

        print("All local app data deleted successfully.")
        print(f"Deleted events: {result.deleted_events}")
        print(f"Deleted guests: {result.deleted_guests}")
        print(f"Deleted messages: {result.deleted_messages}")
        print(f"Deleted RSVPs: {result.deleted_rsvps}")

    finally:
        db.close()


if __name__ == "__main__":
    main()