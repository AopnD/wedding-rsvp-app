from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.models import Guest


def generate_invite_code() -> str:
    """
    Generate a public-safe invite code for RSVP links.

    token_urlsafe creates URL-friendly text.
    16 bytes gives enough randomness for the alpha version.
    """

    return secrets.token_urlsafe(16)


def generate_unique_invite_code(db: Session) -> str:
    """
    Generate an invite code that does not already exist in the database.
    """

    for _ in range(10):
        invite_code = generate_invite_code()

        existing_guest = (
            db.query(Guest)
            .filter(Guest.invite_code == invite_code)
            .first()
        )

        if existing_guest is None:
            return invite_code

    raise RuntimeError("Could not generate a unique invite code.")