from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Guest


def list_guests_for_event(db: Session, event_id: int) -> list[Guest]:
    """
    Return all guests imported for a specific event.
    """

    return (
        db.query(Guest)
        .filter(Guest.event_id == event_id)
        .order_by(Guest.id.asc())
        .all()
    )