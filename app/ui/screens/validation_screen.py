from __future__ import annotations

import logging
from typing import Any

import flet as ft

from app.core.database import SessionLocal
from app.services.event_service import create_event
from app.services.guest_import_db_service import import_valid_guest_rows_to_database
from app.ui.context import AppContext
from app.ui.layout import clear_page, section_card, table_container


logger = logging.getLogger(__name__)


PREVIEW_ROW_LIMIT = 100


def render_validation_screen(context: AppContext) -> None:
    page = context.page
    state = context.state
    status = context.status

    logger.info("Rendering validation screen.")

    clear_page(page, status.text)

    result = state.validation_result

    if result is None:
        logger.warning("Validation screen requested without validation result.")
        status.show_error("No validation result found.")

        from app.ui.screens.upload_screen import render_upload_screen

        render_upload_screen(context)
        return

    valid_preview_rows = result.valid_rows[:PREVIEW_ROW_LIMIT]
    invalid_preview_rows = result.invalid_rows[:PREVIEW_ROW_LIMIT]

    valid_rows_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Row")),
            ft.DataColumn(ft.Text("Name")),
            ft.DataColumn(ft.Text("Phone")),
            ft.DataColumn(ft.Text("Guests")),
        ],
        rows=[
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row.row_number))),
                    ft.DataCell(ft.Text(row.name)),
                    ft.DataCell(ft.Text(row.normalized_phone)),
                    ft.DataCell(ft.Text(str(row.guests_count))),
                ]
            )
            for row in valid_preview_rows
        ],
    )

    invalid_rows_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Row")),
            ft.DataColumn(ft.Text("Errors")),
        ],
        rows=[
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row.row_number))),
                    ft.DataCell(ft.Text(", ".join(row.errors))),
                ]
            )
            for row in invalid_preview_rows
        ],
    )

    def ensure_event_exists(db: Any) -> int:
        """
        Create the event only at the final confirmed import step.

        This avoids empty events if the user goes back, closes the app,
        or validates files without importing.
        """

        logger.info("Ensuring event exists before importing guests.")

        if state.event_id is not None:
            logger.info("Using existing event. event_id=%s", state.event_id)
            return state.event_id

        if not state.couple_names:
            logger.error("Cannot create event because couple names are missing.")
            raise ValueError("Missing couple names. Please return to setup.")

        logger.info("Creating event from UI state.")

        event = create_event(
            db=db,
            couple_names=state.couple_names,
            wedding_date=state.wedding_date,
            venue_name=state.venue_name,
            venue_address=state.venue_address,
        )

        state.event_id = event.id

        logger.info("Event created from UI. event_id=%s", event.id)

        return event.id

    def on_import_valid_rows(_: ft.ControlEvent) -> None:
        logger.info("Import valid guests button clicked.")

        if state.selected_file_path is None:
            status.show_error("No file selected.")
            return

        if state.validation_result is None:
            status.show_error("Please validate the file before importing.")
            return

        db = SessionLocal()

        try:
            event_id = ensure_event_exists(db)

            logger.info(
                "Importing valid guests to database. event_id=%s valid=%s invalid=%s",
                event_id,
                len(state.validation_result.valid_rows),
                len(state.validation_result.invalid_rows),
            )

            import_result = import_valid_guest_rows_to_database(
                db=db,
                valid_rows=state.validation_result.valid_rows,
                event_id=event_id,
                invalid_count=len(state.validation_result.invalid_rows),
            )

            logger.info(
                "Guest import completed from UI. event_id=%s saved=%s invalid=%s duplicates=%s",
                event_id,
                import_result.saved_count,
                import_result.invalid_count,
                import_result.duplicate_count,
            )

            status.show_success(
                f"Import finished. Saved {import_result.saved_count} guests. "
                f"Skipped {import_result.invalid_count} invalid rows and "
                f"{import_result.duplicate_count} duplicate guests."
            )

            from app.ui.screens.dashboard_screen import render_dashboard_screen

            render_dashboard_screen(context)

        except Exception:
            logger.exception("Failed to import guests to database.")
            status.show_error("Something went wrong while saving guests.")

        finally:
            db.close()

    valid_preview_note = ""
    if len(result.valid_rows) > PREVIEW_ROW_LIMIT:
        valid_preview_note = f" Showing first {PREVIEW_ROW_LIMIT} valid rows only."

    invalid_preview_note = ""
    if len(result.invalid_rows) > PREVIEW_ROW_LIMIT:
        invalid_preview_note = f" Showing first {PREVIEW_ROW_LIMIT} invalid rows only."

    page.add(
        ft.Column(
            controls=[
                ft.Text("Validation result", size=32, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Step 3 of 3: review the file. "
                    "The event and guests will be saved only after you click import."
                ),
                section_card(
                    "Summary",
                    [
                        ft.Text(f"Valid rows: {len(result.valid_rows)}"),
                        ft.Text(f"Invalid rows: {len(result.invalid_rows)}"),
                        ft.Text(
                            "Duplicate protection: if this event already contains a guest "
                            "with the same phone number, that guest will be skipped."
                        ),
                    ],
                ),
                section_card(
                    "Valid guests",
                    [
                        ft.Text(
                            "No valid guests found."
                            if not result.valid_rows
                            else f"Previewing valid guests.{valid_preview_note}"
                        ),
                        table_container(valid_rows_table)
                        if result.valid_rows
                        else ft.Container(),
                    ],
                ),
                section_card(
                    "Invalid rows",
                    [
                        ft.Text(
                            "No invalid rows found."
                            if not result.invalid_rows
                            else f"Previewing invalid rows.{invalid_preview_note}"
                        ),
                        table_container(invalid_rows_table)
                        if result.invalid_rows
                        else ft.Container(),
                    ],
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Import valid guests",
                            on_click=on_import_valid_rows,
                            disabled=not result.valid_rows,
                        ),
                        ft.TextButton(
                            "Back to upload",
                            on_click=lambda _: _go_back_to_upload(context),
                        ),
                    ],
                    spacing=12,
                ),
            ],
            spacing=18,
        )
    )

    page.update()


def _go_back_to_upload(context: AppContext) -> None:
    from app.ui.screens.upload_screen import render_upload_screen

    render_upload_screen(context)