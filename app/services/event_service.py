from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Event


logger = logging.getLogger(__name__)


def create_event(
    db: Session,
    couple_names: str,
    wedding_date: str | None = None,
    venue_name: str | None = None,
    venue_address: str | None = None,
) -> Event:
    """
    Create a wedding event.

    In the alpha version, the UI creates one event per app session/import flow.
    Later we can add event selection/editing.
    """

    event = Event(
        couple_names=couple_names.strip(),
        wedding_date=wedding_date.strip() if wedding_date else None,
        venue_name=venue_name.strip() if venue_name else None,
        venue_address=venue_address.strip() if venue_address else None,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info("Created event. event_id=%s couple_names=%s", event.id, event.couple_names)

    return event