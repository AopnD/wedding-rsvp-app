from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models import Guest, Rsvp


@dataclass(frozen=True)
class GuestRsvpStatus:
    guest_id: int
    guest_name: str
    phone_number: str | None
    response: str
    attending_count: int
    notes: str | None
    submitted_at: datetime


def list_latest_rsvps_for_event(
    db: Session,
    event_id: int,
) -> list[GuestRsvpStatus]:
    """
    Return the latest RSVP response for each guest in an event.

    Alpha behavior:
    - Guests can submit RSVP more than once.
    - The dashboard shows only the latest RSVP per guest.
    """

    guests = (
        db.query(Guest)
        .options(joinedload(Guest.rsvps))
        .filter(Guest.event_id == event_id)
        .order_by(Guest.id.asc())
        .all()
    )

    results: list[GuestRsvpStatus] = []

    for guest in guests:
        latest_rsvp = _get_latest_rsvp(guest.rsvps)

        if latest_rsvp is None:
            continue

        results.append(
            GuestRsvpStatus(
                guest_id=guest.id,
                guest_name=guest.full_name,
                phone_number=guest.phone_number,
                response=latest_rsvp.response,
                attending_count=latest_rsvp.attending_count,
                notes=latest_rsvp.notes,
                submitted_at=latest_rsvp.submitted_at,
            )
        )

    return results


def _get_latest_rsvp(rsvps: list[Rsvp]) -> Rsvp | None:
    if not rsvps:
        return None

    return max(rsvps, key=lambda rsvp: rsvp.id)