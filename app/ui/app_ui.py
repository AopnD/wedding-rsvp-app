from __future__ import annotations

import atexit
import logging

import flet as ft

from app.core.database import SessionLocal, create_database
from app.services.rsvp_runtime_service import RsvpRuntimeManager
from app.services.startup_service import load_latest_startup_event_state
from app.ui.context import AppContext
from app.ui.screens.dashboard_screen import render_dashboard_screen
from app.ui.screens.setup_screen import render_setup_screen
from app.ui.state import AppState
from app.ui.status import StatusController


logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    logger.info("Initializing desktop UI.")

    create_database()
    logger.info("Database initialized for desktop UI.")

    state = AppState()
    status = StatusController(page)
    runtime = RsvpRuntimeManager()

    atexit.register(runtime.stop_all)

    context = AppContext(
        page=page,
        state=state,
        status=status,
        runtime=runtime,
    )

    page.title = "Local Wedding RSVP"
    page.window_width = 1050
    page.window_height = 780
    page.padding = 24
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    startup_event = _load_startup_event_or_none()

    if startup_event is not None:
        state.load_startup_event(startup_event)

        logger.info(
            "Opening dashboard from saved database state. event_id=%s",
            startup_event.event_id,
        )

        status.show_success(
            "Saved event loaded from the local database. "
            "Start the public RSVP link again when you are ready."
        )

        render_dashboard_screen(context)
        return

    logger.info("No saved event found. Opening setup screen.")
    render_setup_screen(context)


def _load_startup_event_or_none():
    """
    Load the latest saved event from the database.

    Kept outside main() so startup stays easy to read.
    """

    db = SessionLocal()

    try:
        return load_latest_startup_event_state(db)

    except Exception:
        logger.exception("Failed to load startup event state.")
        return None

    finally:
        db.close()