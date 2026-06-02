from __future__ import annotations

import logging

import flet as ft
from telethon.errors import SessionPasswordNeededError

from app.services.telegram_login_flow_service import (
    TelegramLoginFlow,
    request_login_code,
    sign_in_with_code,
    sign_in_with_password,
)
from app.services.telegram_service import TelegramLoginError
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

    login_flow = TelegramLoginFlow()

    phone_field = ft.TextField(
        label="Telegram phone number",
        hint_text="Example: +351912345678",
        width=520,
    )

    code_field = ft.TextField(
        label="Telegram login code",
        hint_text="Enter the code Telegram sends you",
        width=520,
        visible=False,
    )

    password_field = ft.TextField(
        label="Telegram 2FA password",
        hint_text="Only needed if your Telegram account has 2FA enabled",
        width=520,
        password=True,
        can_reveal_password=True,
        visible=False,
    )

    send_code_button = ft.ElevatedButton("Send Telegram code")
    login_button = ft.ElevatedButton("Login", visible=False)
    password_login_button = ft.ElevatedButton("Login with 2FA password", visible=False)

    login_help_text = ft.Text(
        message
        or (
            "Telegram API settings are saved. "
            "Now login to your personal Telegram account."
        ),
        color=ft.Colors.GREY_700,
    )

    def continue_to_app() -> None:
        """
        After Telegram login succeeds, continue to the normal app startup flow.

        This mirrors app_ui.py's existing behavior:
        - If a saved event exists, open dashboard.
        - Otherwise, open wedding setup.
        """

        from app.core.database import SessionLocal
        from app.services.startup_service import load_latest_startup_event_state
        from app.ui.screens.dashboard_screen import render_dashboard_screen
        from app.ui.screens.setup_screen import render_setup_screen

        db = SessionLocal()

        try:
            startup_event = load_latest_startup_event_state(db)

            if startup_event is not None:
                context.state.load_startup_event(startup_event)
                render_dashboard_screen(context)
                return

            render_setup_screen(context)

        except Exception:
            logger.exception("Failed to continue after Telegram login.")
            status.show_error("Telegram login worked, but the app could not continue.")

        finally:
            db.close()

    def on_send_code(_: ft.ControlEvent) -> None:
        phone_number = phone_field.value or ""

        if not phone_number.strip():
            status.show_error("Please enter your Telegram phone number.")
            return

        try:
            status.show_success("Requesting Telegram login code...")

            result = request_login_code(
                flow=login_flow,
                phone_number=phone_number,
            )

            status.show_success(result.message)

            phone_field.disabled = True
            code_field.visible = True
            login_button.visible = True
            send_code_button.disabled = True

            page.update()

        except TelegramLoginError as exc:
            logger.exception("Telegram code request failed.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected Telegram code request error.")
            status.show_error(
                "Could not request Telegram login code. "
                "Please check your Telegram setup."
            )

    def on_login_with_code(_: ft.ControlEvent) -> None:
        code = code_field.value or ""

        if not code.strip():
            status.show_error("Please enter the Telegram login code.")
            return

        try:
            status.show_success("Logging in to Telegram...")

            result = sign_in_with_code(
                flow=login_flow,
                code=code,
            )

            status.show_success(result.message)
            continue_to_app()

        except SessionPasswordNeededError:
            logger.info("Telegram account requires 2FA password.")

            status.show_error(
                "This Telegram account has two-step verification enabled. "
                "Enter your Telegram password below."
            )

            password_field.visible = True
            password_login_button.visible = True
            login_button.disabled = True
            page.update()

        except TelegramLoginError as exc:
            logger.exception("Telegram login with code failed.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected Telegram login error.")
            status.show_error("Could not login to Telegram.")

    def on_login_with_password(_: ft.ControlEvent) -> None:
        password = password_field.value or ""

        if not password.strip():
            status.show_error("Please enter your Telegram 2FA password.")
            return

        try:
            status.show_success("Logging in with Telegram 2FA password...")

            result = sign_in_with_password(password=password)

            status.show_success(result.message)
            continue_to_app()

        except TelegramLoginError as exc:
            logger.exception("Telegram 2FA login failed.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected Telegram 2FA login error.")
            status.show_error("Could not login with Telegram 2FA password.")

    def on_edit_settings(_: ft.ControlEvent) -> None:
        from app.ui.screens.telegram_setup_screen import render_telegram_setup_screen

        render_telegram_setup_screen(
            context=context,
            message="Edit your Telegram API settings.",
        )

    send_code_button.on_click = on_send_code
    login_button.on_click = on_login_with_code
    password_login_button.on_click = on_login_with_password

    page.add(
        ft.Column(
            controls=[
                ft.Text("Login to Telegram", size=34, weight=ft.FontWeight.BOLD),
                login_help_text,
                section_card(
                    "Telegram login",
                    [
                        ft.Text(
                            "Use your Telegram phone number in international format. "
                            "Telegram will send a login code to your Telegram account."
                        ),
                        phone_field,
                        send_code_button,
                        code_field,
                        login_button,
                        password_field,
                        password_login_button,
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