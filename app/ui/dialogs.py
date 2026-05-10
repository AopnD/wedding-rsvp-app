from __future__ import annotations

import logging
from typing import Callable

import flet as ft

from app.core.database import SessionLocal
from app.services.reset_service import delete_all_local_data
from app.ui.context import AppContext


logger = logging.getLogger(__name__)


def show_reset_dialog(
    context: AppContext,
    on_reset_finished: Callable[[], None],
) -> None:
    """
    Show a confirmation dialog before deleting all local app data.

    The callback lets the caller decide which screen to render after reset.
    """

    page = context.page
    state = context.state
    status = context.status

    logger.warning("Reset dialog requested from UI.")

    def close_dialog() -> None:
        try:
            if hasattr(page, "close"):
                page.close(dialog)
            else:
                dialog.open = False
                page.update()
        except Exception:
            logger.exception("Failed to close reset dialog.")

    def on_confirm_reset(_: ft.ControlEvent) -> None:
        logger.warning("Reset confirmed from UI.")

        db = SessionLocal()

        try:
            result = delete_all_local_data(db)
            state.clear_all()

            logger.warning(
                "UI reset completed. events=%s guests=%s messages=%s rsvps=%s",
                result.deleted_events,
                result.deleted_guests,
                result.deleted_messages,
                result.deleted_rsvps,
            )

            close_dialog()
            on_reset_finished()

            status.show_success(
                f"All local test data was deleted. "
                f"Deleted {result.deleted_events} events, "
                f"{result.deleted_guests} guests, "
                f"{result.deleted_messages} messages, "
                f"and {result.deleted_rsvps} RSVPs."
            )

        except Exception:
            logger.exception("Failed to delete local test data from UI.")
            close_dialog()
            status.show_error("Something went wrong while deleting local test data.")

        finally:
            db.close()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Delete local test data?"),
        content=ft.Text(
            "This will permanently delete all local events, guests, messages, "
            "and RSVP responses from the SQLite database."
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
            ft.ElevatedButton(
                "YES, DELETE ALL LOCAL DATA",
                bgcolor=ft.Colors.RED_700,
                color=ft.Colors.WHITE,
                on_click=on_confirm_reset,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        if hasattr(page, "open"):
            page.open(dialog)
        else:
            page.dialog = dialog
            dialog.open = True
            page.update()

    except Exception:
        logger.exception("Failed to open reset dialog.")
        status.show_error("Could not open reset confirmation dialog.")