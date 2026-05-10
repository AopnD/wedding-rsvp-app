from __future__ import annotations

import logging

import flet as ft

from app.core.logging_config import setup_logging
from app.ui.app_ui import main


setup_logging()

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting Local Wedding RSVP desktop app.")
    ft.app(target=main)