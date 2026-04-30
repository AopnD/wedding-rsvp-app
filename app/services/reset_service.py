from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Event, Guest, Message, Rsvp


logger = logging.getLogger(__name__)


def delete_all_local_data(db: Session) -> None:
    """
    Delete all local app data.

    Intended for alpha/testing only.
    Keeps the database file and tables, but clears app records.
    """

    db.query(Rsvp).delete()
    db.query(Message).delete()
    db.query(Guest).delete()
    db.query(Event).delete()

    db.commit()

    logger.warning("Deleted all local RSVP app data.")