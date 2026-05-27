from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Event, Guest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartupEventState:
    """
    Event data loaded from the local SQLite database when the app starts.

    This is used to restore the dashboard after the app was closed.
    """

    event_id: int
    couple_names: str
    wedding_date: str | None
    venue_name: str | None
    venue_address: str | None
    total_guests: int
    telegram_matched_guests: int


def load_latest_startup_event_state(db: Session) -> StartupEventState | None:
    """
    Load the latest saved event that has guests.

    Alpha behavior:
    - If no event exists, start from setup screen.
    - If the latest event has no guests, ignore it.
    - If an event with guests exists, restore it and open the dashboard.

    Later, when the app supports multiple events, this can become an
    event-selection screen instead of automatically choosing the latest event.
    """

    event = (
        db.query(Event)
        .order_by(Event.id.desc())
        .first()
    )

    if event is None:
        logger.info("No saved event found on startup.")
        return None

    total_guests = (
        db.query(Guest)
        .filter(Guest.event_id == event.id)
        .count()
    )

    if total_guests <= 0:
        logger.info(
            "Latest event has no guests; starting setup screen. event_id=%s",
            event.id,
        )
        return None

    telegram_matched_guests = (
        db.query(Guest)
        .filter(Guest.event_id == event.id)
        .filter(Guest.is_matched_telegram_contact.is_(True))
        .count()
    )

    logger.info(
        "Loaded startup event from database. event_id=%s guests=%s matched=%s",
        event.id,
        total_guests,
        telegram_matched_guests,
    )

    return StartupEventState(
        event_id=event.id,
        couple_names=event.couple_names,
        wedding_date=event.wedding_date,
        venue_name=event.venue_name,
        venue_address=event.venue_address,
        total_guests=total_guests,
        telegram_matched_guests=telegram_matched_guests,
    )