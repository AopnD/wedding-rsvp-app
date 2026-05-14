from __future__ import annotations

from dataclasses import dataclass

from app.services.status_helpers import (
    get_latest_message,
    get_latest_rsvp,
    get_latest_sent_message,
)

from sqlalchemy.orm import Session, joinedload

from app.models import Guest


@dataclass(frozen=True)
class DashboardSummary:
    total_guests: int
    sendable: int
    sent: int
    failed: int
    responded: int
    attending: int
    not_attending: int
    total_attending_guests: int


def get_dashboard_summary(
    db: Session,
    event_id: int,
) -> DashboardSummary:
    """
    Build the main dashboard progress numbers for one event.

    Rules:
    - total_guests: all imported guests for the event
    - sendable: Telegram-matched guests without a sent invitation
    - sent: guests with at least one sent invitation message
    - failed: guests whose latest message failed and who do not have a sent message
    - responded: guests with at least one RSVP response
    - attending: latest RSVP is "yes"
    - not_attending: latest RSVP is "no"
    - total_attending_guests: sum of attending_count from latest "yes" RSVPs
    """

    guests = (
        db.query(Guest)
        .options(
            joinedload(Guest.messages),
            joinedload(Guest.rsvps),
        )
        .filter(Guest.event_id == event_id)
        .order_by(Guest.id.asc())
        .all()
    )

    sendable_count = 0
    sent_count = 0
    failed_count = 0

    responded_count = 0
    attending_count = 0
    not_attending_count = 0
    total_attending_guests = 0

    for guest in guests:
        sent_message = get_latest_sent_message(guest.messages)
        latest_message = get_latest_message(guest.messages)

        if sent_message is not None:
            sent_count += 1
        elif latest_message is not None and latest_message.status == "failed":
            failed_count += 1
        elif guest.is_matched_telegram_contact:
            sendable_count += 1

        latest_rsvp = get_latest_rsvp(guest.rsvps)

        if latest_rsvp is None:
            continue

        responded_count += 1

        if latest_rsvp.response == "yes":
            attending_count += 1
            total_attending_guests += latest_rsvp.attending_count
        elif latest_rsvp.response == "no":
            not_attending_count += 1

    return DashboardSummary(
        total_guests=len(guests),
        sendable=sendable_count,
        sent=sent_count,
        failed=failed_count,
        responded=responded_count,
        attending=attending_count,
        not_attending=not_attending_count,
        total_attending_guests=total_attending_guests,
    )


