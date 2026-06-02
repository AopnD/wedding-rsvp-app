from __future__ import annotations

import logging

import flet as ft

from app.ui.context import AppContext
from app.ui.layout import clear_page, section_card


logger = logging.getLogger(__name__)


def render_telegram_login_screen(
    context: AppContext,
    message: str | None = None,
) -> None:
    page = context.page
    status = context.status

    logger.info("Rendering Telegram login screen.")

    clear_page(page, status.text)

    def on_edit_settings(_: ft.ControlEvent) -> None:
        from app.ui.screens.telegram_setup_screen import render_telegram_setup_screen

        render_telegram_setup_screen(
            context=context,
            message="Edit your Telegram API settings.",
        )

    page.add(
        ft.Column(
            controls=[
                ft.Text("Login to Telegram", size=34, weight=ft.FontWeight.BOLD),
                ft.Text(
                    message
                    or (
                        "Telegram API settings are saved, but this app is not logged "
                        "in to Telegram yet."
                    ),
                    color=ft.Colors.GREY_700,
                ),
                section_card(
                    "Telegram login",
                    [
                        ft.Text(
                            "Next we will add phone number + login code login here. "
                            "For now, this screen confirms the startup routing works."
                        ),
                        ft.TextButton(
                            "Edit Telegram settings",
                            on_click=on_edit_settings,
                        ),
                    ],
                ),
            ],
            spacing=18,
        )
    )

    page.update()