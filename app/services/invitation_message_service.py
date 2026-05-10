from __future__ import annotations

from app.models import Event, Guest
from app.services.link_service import build_guest_rsvp_url


def build_fixed_invitation_message(
    event: Event,
    guest: Guest,
    public_base_url: str,
) -> str:
    """
    Build the fixed alpha invitation message.

    Alpha rules:
    - One fixed template.
    - Personalized guest name.
    - Personalized RSVP link.
    - No custom free-text message yet.
    """

    rsvp_url = build_guest_rsvp_url(
        public_base_url=public_base_url,
        invite_code=guest.invite_code,
    )

    wedding_date_text = event.wedding_date or "our wedding"
    venue_text = ""

    if event.venue_name:
        venue_text = f"\nVenue: {event.venue_name}"

    return (
        f"Hi {guest.full_name},\n\n"
        f"You are invited to the wedding of {event.couple_names}.\n"
        f"Date: {wedding_date_text}"
        f"{venue_text}\n\n"
        f"Please RSVP here:\n"
        f"{rsvp_url}\n\n"
        f"Thank you!"
    )