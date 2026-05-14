from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models import Guest

from app.services.status_helpers import (
    get_latest_message,
    get_latest_sent_message,
)


@dataclass(frozen=True)
class GuestMessageStatus:
    guest_id: int
    guest_name: str
    phone_number: str | None
    telegram_matched: bool
    status: str
    error_message: str | None
    sent_at: datetime | None


@dataclass(frozen=True)
class MessageStatusSummary:
    total_guests: int
    telegram_matched: int
    ready_to_send: int
    sent: int
    failed: int
    not_matched: int
    statuses: list[GuestMessageStatus]


def get_message_status_summary(
    db: Session,
    event_id: int,
) -> MessageStatusSummary:
    """
    Build dashboard-friendly invitation sending status.

    Status rules:
    - sent: guest has at least one sent message
    - failed: latest message is failed and no sent message exists
    - ready_to_send: matched Telegram contact and no sent message
    - not_matched: no Telegram match
    """

    guests = (
        db.query(Guest)
        .options(joinedload(Guest.messages))
        .filter(Guest.event_id == event_id)
        .order_by(Guest.id.asc())
        .all()
    )

    statuses: list[GuestMessageStatus] = []

    sent_count = 0
    failed_count = 0
    ready_to_send_count = 0
    matched_count = 0
    not_matched_count = 0

    for guest in guests:
        if guest.is_matched_telegram_contact:
            matched_count += 1
        else:
            not_matched_count += 1

        latest_message = get_latest_message(guest.messages)
        sent_message = get_latest_sent_message(guest.messages)

        if sent_message is not None:
            status = "sent"
            error_message = None
            sent_at = sent_message.sent_at
            sent_count += 1

        elif latest_message is not None and latest_message.status == "failed":
            status = "failed"
            error_message = latest_message.error_message
            sent_at = None
            failed_count += 1

        elif guest.is_matched_telegram_contact:
            status = "ready"
            error_message = None
            sent_at = None
            ready_to_send_count += 1

        else:
            status = "not matched"
            error_message = None
            sent_at = None

        statuses.append(
            GuestMessageStatus(
                guest_id=guest.id,
                guest_name=guest.full_name,
                phone_number=guest.phone_number,
                telegram_matched=guest.is_matched_telegram_contact,
                status=status,
                error_message=error_message,
                sent_at=sent_at,
            )
        )

    return MessageStatusSummary(
        total_guests=len(guests),
        telegram_matched=matched_count,
        ready_to_send=ready_to_send_count,
        sent=sent_count,
        failed=failed_count,
        not_matched=not_matched_count,
        statuses=statuses,
    )

