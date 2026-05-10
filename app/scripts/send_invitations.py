from __future__ import annotations

import argparse
import logging

from app.core.database import SessionLocal, create_database
from app.core.logging_config import setup_logging
from app.models import Event
from app.services.invitation_send_service import (
    InvitationSendError,
    build_invitation_send_previews,
    send_invitations_to_matched_guests,
)
from app.services.telegram_service import TelegramServiceError


logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    create_database()

    parser = argparse.ArgumentParser(
        description="Preview and send fixed wedding invitations through Telegram."
    )

    parser.add_argument(
        "--public-base-url",
        required=True,
        help="The public tunnel URL. Example: https://example.trycloudflare.com",
    )

    parser.add_argument(
        "--event-id",
        type=int,
        default=None,
        help="Optional event ID. If omitted, the latest event is used.",
    )

    parser.add_argument(
        "--delay-seconds",
        type=int,
        default=8,
        help="Delay between Telegram messages. Default: 8 seconds.",
    )

    args = parser.parse_args()

    db = SessionLocal()

    try:
        event_id = args.event_id or _get_latest_event_id(db)

        if event_id is None:
            print("No event found.")
            print("Import guests from the UI first, then try again.")
            return

        previews = build_invitation_send_previews(
            db=db,
            event_id=event_id,
            public_base_url=args.public_base_url,
        )

        print()
        print("=" * 80)
        print("INVITATION SEND PREVIEW")
        print("=" * 80)
        print(f"Event ID: {event_id}")
        print(f"Public base URL: {args.public_base_url}")
        print(f"Guests ready to send: {len(previews)}")
        print("-" * 80)

        if not previews:
            print("No invitations to send.")
            print()
            print("Possible reasons:")
            print("- No guests are matched with Telegram contacts yet.")
            print("- All matched guests already have a sent message.")
            print("- You have not imported guests yet.")
            return

        first_preview = previews[0]

        print("First message preview:")
        print("-" * 80)
        print(f"Guest: {first_preview.guest_name}")
        print(f"Phone: {first_preview.phone_number or ''}")
        print()
        print(first_preview.message_text)
        print("-" * 80)

        print()
        print("Guests that will receive an invitation:")
        print("-" * 80)

        for preview in previews:
            print(
                f"guest_id={preview.guest_id} | "
                f"{preview.guest_name} | "
                f"{preview.phone_number or ''}"
            )

        print()
        print("Safety check:")
        print("- Only Telegram-matched guests will be sent.")
        print("- Guests with an existing sent message will be skipped.")
        print("- The app will wait between messages.")
        print()

        confirmation = input("Type SEND to send these invitations: ").strip()

        if confirmation != "SEND":
            print("Sending cancelled. No messages were sent.")
            return

        result = send_invitations_to_matched_guests(
            db=db,
            event_id=event_id,
            public_base_url=args.public_base_url,
            delay_seconds=args.delay_seconds,
        )

        print()
        print("=" * 80)
        print("INVITATION SENDING FINISHED")
        print("=" * 80)
        print(f"Total candidates: {result.total_candidates}")
        print(f"Sent: {result.sent_count}")
        print(f"Failed: {result.failed_count}")
        print(f"Skipped: {result.skipped_count}")
        print()
        print("Check data/logs/app.log for detailed logs.")

    except TelegramServiceError as exc:
        logger.exception("Telegram service error while sending invitations.")
        print(f"Telegram error: {exc}")

    except InvitationSendError as exc:
        logger.exception("Invitation send error.")
        print(f"Invitation sending failed: {exc}")

    except Exception:
        logger.exception("Unexpected error while sending invitations.")
        print("Something went wrong while sending invitations.")

    finally:
        db.close()


def _get_latest_event_id(db) -> int | None:
    event = (
        db.query(Event)
        .order_by(Event.id.desc())
        .first()
    )

    if event is None:
        return None

    return event.id


if __name__ == "__main__":
    main()