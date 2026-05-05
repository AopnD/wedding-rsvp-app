from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Event, Guest, Message, Rsvp


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResetLocalDataResult:
    deleted_events: int
    deleted_guests: int
    deleted_messages: int
    deleted_rsvps: int


def delete_all_local_data(db: Session) -> ResetLocalDataResult:
    """
    Delete all local app data.

    Intended for alpha/testing only.
    Keeps the database file and tables, but clears app records.
    """

    deleted_rsvps = db.query(Rsvp).delete()
    deleted_messages = db.query(Message).delete()
    deleted_guests = db.query(Guest).delete()
    deleted_events = db.query(Event).delete()

    db.commit()

    logger.warning(
        "Deleted all local RSVP app data. events=%s guests=%s messages=%s rsvps=%s",
        deleted_events,
        deleted_guests,
        deleted_messages,
        deleted_rsvps,
    )

    return ResetLocalDataResult(
        deleted_events=deleted_events,
        deleted_guests=deleted_guests,
        deleted_messages=deleted_messages,
        deleted_rsvps=deleted_rsvps,
    )