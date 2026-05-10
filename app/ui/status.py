from __future__ import annotations

import logging

import flet as ft


logger = logging.getLogger(__name__)


class StatusController:
    """
    Small helper for showing status messages in the UI.

    Usage:
    - show_success(...) for green success/info messages
    - show_error(...) for red error messages
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.text = ft.Text("", color=ft.Colors.RED_700)

    def show_success(self, message: str) -> None:
        logger.info("UI status success: %s", message)
        self.text.value = message
        self.text.color = ft.Colors.GREEN_700
        self.page.update()

    def show_error(self, message: str) -> None:
        logger.warning("UI status error: %s", message)
        self.text.value = message
        self.text.color = ft.Colors.RED_700
        self.page.update()

    def clear(self) -> None:
        self.text.value = ""
        self.page.update()