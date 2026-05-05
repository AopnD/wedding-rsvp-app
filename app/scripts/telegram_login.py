from __future__ import annotations

import logging

from app.services.telegram_service import TelegramServiceError, login_with_phone


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    print("Telegram login")
    print("-" * 50)
    print("Use your Telegram phone number in international format.")
    print("Example: +351912345678")
    print()

    phone_number = input("Telegram phone number: ").strip()

    try:
        account = login_with_phone(phone_number)

    except TelegramServiceError as exc:
        print()
        print(f"Telegram login failed: {exc}")
        return

    print()
    print("Telegram login successful.")
    print(f"Account: {account.display_name}")
    print(f"Username: @{account.username}" if account.username else "Username: none")
    print(f"Phone: {account.phone or 'unknown'}")


if __name__ == "__main__":
    main()