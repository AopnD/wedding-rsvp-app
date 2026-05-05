from __future__ import annotations

from app.services.telegram_service import load_telegram_contacts


PHONES_TO_CHECK = {
    "+351963618457",
    "+972523558034",
}


def main() -> None:
    contacts = load_telegram_contacts()

    print(f"Loaded contacts: {len(contacts)}")
    print("-" * 80)

    found_any = False

    for contact in contacts:
        if contact.normalized_phone in PHONES_TO_CHECK:
            found_any = True
            print("MATCH FOUND")
            print(f"name={contact.display_name}")
            print(f"username={contact.username or ''}")
            print(f"phone={contact.phone or ''}")
            print(f"normalized_phone={contact.normalized_phone or ''}")
            print("-" * 80)

    if not found_any:
        print("No matching Telegram contacts found for:")
        for phone in sorted(PHONES_TO_CHECK):
            print(phone)


if __name__ == "__main__":
    main()