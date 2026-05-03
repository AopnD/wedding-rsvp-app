from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.models import Guest, Rsvp


logger = logging.getLogger(__name__)


VALID_RSVP_RESPONSES = {"yes", "no"}


class RsvpError(Exception):
    """Base error for RSVP operations."""


class GuestInviteNotFoundError(RsvpError):
    """Raised when an invite code does not match any guest."""


class InvalidRsvpResponseError(RsvpError):
    """Raised when an RSVP response is invalid."""


class InvalidAttendingCountError(RsvpError):
    """Raised when attending count is invalid."""


@dataclass(frozen=True)
class RsvpSubmissionResult:
    guest_id: int
    guest_name: str
    response: str
    attending_count: int


def get_guest_by_invite_code(db: Session, invite_code: str) -> Guest:
    """
    Find a guest by their public invite code.
    """

    guest = (
        db.query(Guest)
        .options(joinedload(Guest.event))
        .filter(Guest.invite_code == invite_code)
        .first()
    )

    if guest is None:
        raise GuestInviteNotFoundError("RSVP invite link was not found.")

    return guest


def submit_rsvp_response(
    db: Session,
    invite_code: str,
    response: str,
    attending_count: int,
    notes: str | None = None,
) -> RsvpSubmissionResult:
    """
    Save a guest RSVP response.

    Alpha behavior:
    - Allows resubmission.
    - Stores each submission as a new row.
    - Later the dashboard can show the latest RSVP per guest.
    """

    cleaned_response = response.strip().lower()

    if cleaned_response not in VALID_RSVP_RESPONSES:
        raise InvalidRsvpResponseError("Response must be yes or no.")

    guest = get_guest_by_invite_code(db=db, invite_code=invite_code)

    if cleaned_response == "no":
        final_attending_count = 0
    else:
        final_attending_count = attending_count

    if final_attending_count < 0:
        raise InvalidAttendingCountError("Attending count cannot be negative.")

    if cleaned_response == "yes" and final_attending_count < 1:
        raise InvalidAttendingCountError("Attending count must be at least 1.")

    if final_attending_count > guest.invited_count:
        raise InvalidAttendingCountError(
            f"Attending count cannot be higher than invited count ({guest.invited_count})."
        )

    rsvp = Rsvp(
        guest_id=guest.id,
        response=cleaned_response,
        attending_count=final_attending_count,
        notes=notes.strip() if notes and notes.strip() else None,
    )

    db.add(rsvp)
    db.commit()

    logger.info(
        "Saved RSVP response. guest_id=%s response=%s attending_count=%s",
        guest.id,
        cleaned_response,
        final_attending_count,
    )

    return RsvpSubmissionResult(
        guest_id=guest.id,
        guest_name=guest.full_name,
        response=cleaned_response,
        attending_count=final_attending_count,
    )