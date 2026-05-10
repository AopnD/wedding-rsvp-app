from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload
from telethon.errors import FloodWaitError, RPCError

from app.models import Event, Guest, Message
from app.services.invitation_message_service import build_fixed_invitation_message
from app.services.telegram_service import (
    TelegramContactInfo,
    TelegramNotLoggedInError,
    TelegramServiceError,
    create_telegram_client,
    load_telegram_contacts_async,
)


logger = logging.getLogger(__name__)


class InvitationSendError(Exception):
    """Raised when invitation sending cannot start."""


@dataclass(frozen=True)
class InvitationSendPreview:
    guest_id: int
    guest_name: str
    phone_number: str | None
    message_text: str


@dataclass(frozen=True)
class InvitationSendResult:
    total_candidates: int
    sent_count: int
    failed_count: int
    skipped_count: int


def build_invitation_send_previews(
    db: Session,
    event_id: int,
    public_base_url: str,
) -> list[InvitationSendPreview]:
    """
    Build preview messages for guests who are eligible for sending.

    Eligibility:
    - guest belongs to the event
    - guest is matched to a Telegram contact
    - guest has not already received a successfully sent invitation
    """

    event = _get_event_or_raise(db=db, event_id=event_id)
    guests = _list_unsent_matched_guests(db=db, event_id=event_id)

    previews: list[InvitationSendPreview] = []

    for guest in guests:
        previews.append(
            InvitationSendPreview(
                guest_id=guest.id,
                guest_name=guest.full_name,
                phone_number=guest.phone_number,
                message_text=build_fixed_invitation_message(
                    event=event,
                    guest=guest,
                    public_base_url=public_base_url,
                ),
            )
        )

    return previews


def send_invitations_to_matched_guests(
    db: Session,
    event_id: int,
    public_base_url: str,
    delay_seconds: int = 8,
) -> InvitationSendResult:
    """
    Sync wrapper for scripts/UI.

    Sends invitations to matched Telegram contacts only.
    """

    return asyncio.run(
        send_invitations_to_matched_guests_async(
            db=db,
            event_id=event_id,
            public_base_url=public_base_url,
            delay_seconds=delay_seconds,
        )
    )


async def send_invitations_to_matched_guests_async(
    db: Session,
    event_id: int,
    public_base_url: str,
    delay_seconds: int = 8,
) -> InvitationSendResult:
    """
    Send fixed invitation messages through the user's Telegram account.

    Safety rules:
    - Only sends to guests already matched with Telegram contacts.
    - Does not send to unmatched guests.
    - Does not send twice to guests with an existing 'sent' message.
    - Waits between messages to reduce risk of Telegram rate limits.
    - Stores sent/failed status in the local messages table.
    """

    if delay_seconds < 3:
        raise InvitationSendError("Delay must be at least 3 seconds for safety.")

    event = _get_event_or_raise(db=db, event_id=event_id)
    guests = _list_unsent_matched_guests(db=db, event_id=event_id)

    if not guests:
        logger.info("No matched unsent guests found. event_id=%s", event_id)
        return InvitationSendResult(
            total_candidates=0,
            sent_count=0,
            failed_count=0,
            skipped_count=0,
        )

    contacts = await load_telegram_contacts_async()
    contacts_by_phone = _contacts_by_phone(contacts)

    client = create_telegram_client()

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    try:
        await client.connect()

        if not await client.is_user_authorized():
            raise TelegramNotLoggedInError(
                "Telegram is not logged in yet. Run the Telegram login step first."
            )

        for index, guest in enumerate(guests, start=1):
            contact = contacts_by_phone.get(guest.phone_number or "")

            if contact is None:
                skipped_count += 1

                logger.warning(
                    "Skipping guest because Telegram contact is no longer available. "
                    "guest_id=%s phone=%s",
                    guest.id,
                    guest.phone_number,
                )

                _save_message_status(
                    db=db,
                    guest=guest,
                    status="failed",
                    message_text="",
                    error_message="Telegram contact was not found during send.",
                )
                continue

            message_text = build_fixed_invitation_message(
                event=event,
                guest=guest,
                public_base_url=public_base_url,
            )

            logger.info(
                "Sending invitation. event_id=%s guest_id=%s guest_name=%s index=%s total=%s",
                event_id,
                guest.id,
                guest.full_name,
                index,
                len(guests),
            )

            try:
                sent_message = await client.send_message(
                    entity=contact.user_id,
                    message=message_text,
                )

                _save_message_status(
                    db=db,
                    guest=guest,
                    status="sent",
                    message_text=message_text,
                    telegram_message_id=str(sent_message.id),
                    sent_at=datetime.now(UTC),
                )

                sent_count += 1

                logger.info(
                    "Invitation sent successfully. guest_id=%s telegram_message_id=%s",
                    guest.id,
                    sent_message.id,
                )

            except FloodWaitError as exc:
                failed_count += 1

                error_message = (
                    f"Telegram rate limit hit. Wait required: {exc.seconds} seconds."
                )

                logger.exception(
                    "Telegram flood wait while sending invitation. guest_id=%s wait_seconds=%s",
                    guest.id,
                    exc.seconds,
                )

                _save_message_status(
                    db=db,
                    guest=guest,
                    status="failed",
                    message_text=message_text,
                    error_message=error_message,
                )

                break

            except RPCError as exc:
                failed_count += 1

                logger.exception(
                    "Telegram RPC error while sending invitation. guest_id=%s",
                    guest.id,
                )

                _save_message_status(
                    db=db,
                    guest=guest,
                    status="failed",
                    message_text=message_text,
                    error_message=str(exc),
                )

            except Exception as exc:
                failed_count += 1

                logger.exception(
                    "Unexpected error while sending invitation. guest_id=%s",
                    guest.id,
                )

                _save_message_status(
                    db=db,
                    guest=guest,
                    status="failed",
                    message_text=message_text,
                    error_message=str(exc),
                )

            if index < len(guests):
                await asyncio.sleep(delay_seconds)

    except TelegramServiceError:
        raise

    except Exception as exc:
        logger.exception("Invitation sending failed before completion.")
        raise InvitationSendError(f"Invitation sending failed: {exc}") from exc

    finally:
        await client.disconnect()

    logger.info(
        "Invitation sending finished. event_id=%s total=%s sent=%s failed=%s skipped=%s",
        event_id,
        len(guests),
        sent_count,
        failed_count,
        skipped_count,
    )

    return InvitationSendResult(
        total_candidates=len(guests),
        sent_count=sent_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
    )


def _get_event_or_raise(db: Session, event_id: int) -> Event:
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if event is None:
        raise InvitationSendError(f"Event was not found. event_id={event_id}")

    return event


def _list_unsent_matched_guests(db: Session, event_id: int) -> list[Guest]:
    guests = (
        db.query(Guest)
        .options(joinedload(Guest.messages))
        .filter(Guest.event_id == event_id)
        .filter(Guest.is_matched_telegram_contact.is_(True))
        .order_by(Guest.id.asc())
        .all()
    )

    unsent_guests: list[Guest] = []

    for guest in guests:
        already_sent = any(message.status == "sent" for message in guest.messages)

        if already_sent:
            continue

        unsent_guests.append(guest)

    return unsent_guests


def _contacts_by_phone(
    contacts: list[TelegramContactInfo],
) -> dict[str, TelegramContactInfo]:
    return {
        contact.normalized_phone: contact
        for contact in contacts
        if contact.normalized_phone
    }


def _save_message_status(
    db: Session,
    guest: Guest,
    status: str,
    message_text: str,
    telegram_message_id: str | None = None,
    error_message: str | None = None,
    sent_at: datetime | None = None,
) -> None:
    message = Message(
        guest_id=guest.id,
        status=status,
        message_text=message_text,
        telegram_message_id=telegram_message_id,
        error_message=error_message,
        sent_at=sent_at,
    )

    db.add(message)
    db.commit()