from __future__ import annotations

import logging

import flet as ft

from app.core.database import SessionLocal
from app.services.guest_query_service import list_guests_for_event
from app.services.telegram_service import (
    TelegramServiceError,
    match_event_guests_with_telegram_contacts,
)
from app.ui.context import AppContext
from app.ui.dialogs import show_reset_dialog
from app.ui.layout import clear_page, section_card, table_container


logger = logging.getLogger(__name__)


PREVIEW_ROW_LIMIT = 100


def render_dashboard_screen(context: AppContext) -> None:
    page = context.page
    state = context.state
    status = context.status

    logger.info("Rendering dashboard screen.")

    clear_page(page, status.text)

    if state.event_id is None:
        logger.warning("Dashboard requested without selected event.")
        status.show_error("No event selected.")

        from app.ui.screens.setup_screen import render_setup_screen

        render_setup_screen(context)
        return

    db = SessionLocal()

    try:
        logger.info("Loading dashboard guests. event_id=%s", state.event_id)

        guests = list_guests_for_event(db=db, event_id=state.event_id)

        logger.info(
            "Dashboard guests loaded. event_id=%s guests=%s",
            state.event_id,
            len(guests),
        )

    except Exception:
        logger.exception("Failed to load dashboard guests.")
        status.show_error("Something went wrong while loading guests.")
        guests = []

    finally:
        db.close()

    guest_preview_rows = guests[:PREVIEW_ROW_LIMIT]

    guests_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Name")),
            ft.DataColumn(ft.Text("Phone")),
            ft.DataColumn(ft.Text("Invited count")),
            ft.DataColumn(ft.Text("Telegram matched")),
        ],
        rows=[
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(guest.id))),
                    ft.DataCell(ft.Text(guest.full_name)),
                    ft.DataCell(ft.Text(guest.phone_number or "")),
                    ft.DataCell(ft.Text(str(guest.invited_count))),
                    ft.DataCell(
                        ft.Text(
                            "Yes" if guest.is_matched_telegram_contact else "No"
                        )
                    ),
                ]
            )
            for guest in guest_preview_rows
        ],
    )

    def on_match_telegram_contacts(_: ft.ControlEvent) -> None:
        logger.info("Telegram matching button clicked.")

        if state.event_id is None:
            status.show_error("No event selected.")
            return

        db = SessionLocal()

        try:
            logger.info(
                "Telegram matching started from dashboard. event_id=%s",
                state.event_id,
            )

            result = match_event_guests_with_telegram_contacts(
                db=db,
                event_id=state.event_id,
            )

            logger.info(
                "Telegram matching completed from dashboard. event_id=%s matched=%s total=%s",
                state.event_id,
                result.matched_count,
                result.total_guests,
            )

            status.show_success(
                f"Telegram matching finished. "
                f"Matched {result.matched_count} of {result.total_guests} guests."
            )

            render_dashboard_screen(context)

        except TelegramServiceError as exc:
            logger.exception("Telegram matching failed.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected Telegram matching error.")
            status.show_error("Something went wrong while matching Telegram contacts.")

        finally:
            db.close()

    preview_note = ""
    if len(guests) > PREVIEW_ROW_LIMIT:
        preview_note = f" Showing first {PREVIEW_ROW_LIMIT} guests only."

    page.add(
        ft.Column(
            controls=[
                ft.Text("Dashboard", size=32, weight=ft.FontWeight.BOLD),
                section_card(
                    "Current event",
                    [
                        ft.Text(f"Couple names: {state.couple_names or 'Unknown'}"),
                        ft.Text(f"Imported guests: {len(guests)}"),
                        ft.Text(
                            "Telegram matching and RSVP status will be added in later chunks."
                        ),
                    ],
                ),
                section_card(
                    "Guests",
                    [
                        ft.Text(
                            "No guests imported yet."
                            if not guests
                            else f"Imported guest preview.{preview_note}"
                        ),
                        table_container(guests_table, height=360)
                        if guests
                        else ft.Container(),
                    ],
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Match Telegram contacts",
                            on_click=on_match_telegram_contacts,
                            disabled=not guests,
                        ),
                        ft.ElevatedButton(
                            "Upload another file",
                            on_click=lambda _: _go_to_upload(context),
                        ),
                        ft.TextButton(
                            "Start new event",
                            on_click=lambda _: _go_to_setup(context),
                        ),
                        ft.TextButton(
                            "Delete local test data",
                            on_click=lambda _: show_reset_dialog(
                                context=context,
                                on_reset_finished=lambda: _go_to_setup(context),
                            ),
                        ),
                    ],
                    spacing=12,
                ),
            ],
            spacing=18,
        )
    )

    page.update()


def _go_to_upload(context: AppContext) -> None:
    from app.ui.screens.upload_screen import render_upload_screen

    render_upload_screen(context)


def _go_to_setup(context: AppContext) -> None:
    from app.ui.screens.setup_screen import render_setup_screen

    render_setup_screen(context)