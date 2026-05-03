from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Guest


@dataclass(frozen=True)
class GuestRsvpLink:
    guest_id: int
    guest_name: str
    phone_number: str | None
    invite_code: str
    public_rsvp_url: str


def build_guest_rsvp_url(
    public_base_url: str,
    invite_code: str,
) -> str:
    """
    Build the public RSVP URL for one guest.
    """

    cleaned_base_url = public_base_url.rstrip("/")
    return f"{cleaned_base_url}/rsvp/{invite_code}"


def list_guest_rsvp_links(
    db: Session,
    event_id: int,
    public_base_url: str,
) -> list[GuestRsvpLink]:
    """
    Return personalized public RSVP links for all guests in one event.
    """

    guests = (
        db.query(Guest)
        .filter(Guest.event_id == event_id)
        .order_by(Guest.id.asc())
        .all()
    )

    return [
        GuestRsvpLink(
            guest_id=guest.id,
            guest_name=guest.full_name,
            phone_number=guest.phone_number,
            invite_code=guest.invite_code,
            public_rsvp_url=build_guest_rsvp_url(
                public_base_url=public_base_url,
                invite_code=guest.invite_code,
            ),
        )
        for guest in guests
    ]