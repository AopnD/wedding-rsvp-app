from __future__ import annotations

import logging

import flet as ft

from app.services.env_settings_service import (
    load_telegram_env_settings,
    save_telegram_env_settings,
    validate_telegram_env_settings,
)

from app.ui.context import AppContext
from app.ui.layout import clear_page, section_card


logger = logging.getLogger(__name__)


def render_telegram_setup_screen(
    context: AppContext,
    message: str | None = None,
) -> None:
    page = context.page
    status = context.status

    logger.info("Rendering Telegram setup screen.")

    clear_page(page, status.text)

    current_settings = load_telegram_env_settings()

    api_id_field = ft.TextField(
        label="Telegram API ID",
        hint_text="Example: 12345678",
        width=520,
        value=current_settings.api_id,
    )

    api_hash_field = ft.TextField(
        label="Telegram API Hash",
        hint_text="Paste your Telegram API hash here",
        width=520,
        password=True,
        can_reveal_password=True,
        value=current_settings.api_hash,
    )

    helper_text = ft.Text(
        message
        or (
            "Telegram setup is required once. "
            "Your API ID and API hash are saved only on this computer."
        ),
        color=ft.Colors.GREY_700,
    )

    def on_save(_: ft.ControlEvent) -> None:
        api_id = api_id_field.value or ""
        api_hash = api_hash_field.value or ""

        validation = validate_telegram_env_settings(
            api_id=api_id,
            api_hash=api_hash,
        )

        if not validation.is_valid:
            status.show_error(" ".join(validation.errors))
            return

        try:
            save_telegram_env_settings(
                api_id=api_id,
                api_hash=api_hash,
            )

            logger.info("Telegram API settings saved from UI.")
            status.show_success(
                "Telegram API settings saved. Next step: login to Telegram."
            )

            from app.ui.screens.telegram_login_screen import render_telegram_login_screen

            render_telegram_login_screen(
                context=context,
                message="Telegram API settings saved. Login is the next step.",
            )

        except Exception:
            logger.exception("Failed to save Telegram API settings.")
            status.show_error("Could not save Telegram API settings.")

    page.add(
        ft.Column(
            controls=[
                ft.Text("Telegram setup required", size=34, weight=ft.FontWeight.BOLD),
                helper_text,
                section_card(
                    "Telegram API settings",
                    [
                        ft.Text(
                            "To use your personal Telegram account, the app needs "
                            "your Telegram API ID and API hash."
                        ),
                        api_id_field,
                        api_hash_field,
                        ft.ElevatedButton(
                            "Save Telegram settings",
                            on_click=on_save,
                        ),
                    ],
                ),
            ],
            spacing=18,
        )
    )

    page.update()