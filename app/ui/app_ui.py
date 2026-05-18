from __future__ import annotations

import atexit
import logging

import flet as ft

from app.core.database import create_database
from app.services.rsvp_runtime_service import RsvpRuntimeManager
from app.ui.context import AppContext
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

    render_setup_screen(context)