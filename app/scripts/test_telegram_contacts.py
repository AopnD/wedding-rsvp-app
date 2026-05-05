from __future__ import annotations

import logging

from app.services.telegram_service import (
    TelegramServiceError,
    load_telegram_contacts,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    try:
        contacts = load_telegram_contacts()

    except TelegramServiceError as exc:
        print(f"Could not load Telegram contacts: {exc}")
        return

    print(f"Loaded Telegram contacts: {len(contacts)}")
    print("-" * 80)

    for contact in contacts[:50]:
        print(
            f"name={contact.display_name}, "
            f"username={contact.username or ''}, "
            f"phone={contact.phone or ''}, "
            f"normalized_phone={contact.normalized_phone or ''}"
        )

    if len(contacts) > 50:
        print()
        print(f"Showing first 50 contacts only out of {len(contacts)}.")


if __name__ == "__main__":
    main()