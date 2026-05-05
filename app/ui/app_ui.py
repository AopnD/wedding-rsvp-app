from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from app.core.database import SessionLocal, create_database
from app.importers.guest_import_service import GuestImportError, import_guest_file
from app.importers.guest_validator import ValidationResult
from app.services.event_service import create_event
from app.services.guest_import_db_service import import_valid_guest_rows_to_database
from app.services.guest_query_service import list_guests_for_event
from app.services.reset_service import delete_all_local_data

from app.services.telegram_service import (
    TelegramServiceError,
    match_event_guests_with_telegram_contacts,
)


logger = logging.getLogger(__name__)


PREVIEW_ROW_LIMIT = 100


class AppState:
    """
    Small in-memory UI state.

    This keeps the alpha version simple.
    Later we can replace this with a more formal app controller.
    """

    def __init__(self) -> None:
        self.event_id: int | None = None

        self.couple_names: str | None = None
        self.wedding_date: str | None = None
        self.venue_name: str | None = None
        self.venue_address: str | None = None

        self.selected_file_path: Path | None = None
        self.validation_result: ValidationResult | None = None

    def clear_import_state(self) -> None:
        self.selected_file_path = None
        self.validation_result = None

    def clear_all(self) -> None:
        self.event_id = None

        self.couple_names = None
        self.wedding_date = None
        self.venue_name = None
        self.venue_address = None

        self.clear_import_state()


def main(page: ft.Page) -> None:
    create_database()

    state = AppState()

    page.title = "Local Wedding RSVP"
    page.window_width = 1050
    page.window_height = 780
    page.padding = 24
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    status_text = ft.Text("", color=ft.Colors.RED_700)

    def set_status(message: str, is_error: bool = False) -> None:
        status_text.value = message
        status_text.color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
        page.update()

    def clear_page() -> None:
        page.controls.clear()
        page.add(status_text)

    def section_card(title: str, controls: list[ft.Control]) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
                    *controls,
                ],
                spacing=12,
            ),
            padding=18,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=12,
            bgcolor=ft.Colors.WHITE,
        )

    def table_container(table: ft.DataTable, height: int = 280) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            height=height,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=10,
            padding=8,
        )

    def show_reset_dialog() -> None:
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
                render_setup_screen()

                set_status(
                    f"All local test data was deleted. "
                    f"Deleted {result.deleted_events} events, "
                    f"{result.deleted_guests} guests, "
                    f"{result.deleted_messages} messages, "
                    f"and {result.deleted_rsvps} RSVPs."
                )

            except Exception:
                logger.exception("Failed to delete local test data from UI.")
                close_dialog()
                set_status("Something went wrong while deleting local test data.", is_error=True)

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
            set_status("Could not open reset confirmation dialog.", is_error=True)

    def render_setup_screen() -> None:
        clear_page()

        couple_names = ft.TextField(
            label="Couple names",
            hint_text="Example: Omer & Dana",
            width=520,
            value=state.couple_names or "",
        )

        wedding_date = ft.TextField(
            label="Wedding date",
            hint_text="Example: 2026-09-01",
            width=520,
            value=state.wedding_date or "",
        )

        venue_name = ft.TextField(
            label="Venue name",
            hint_text="Example: The Garden Hall",
            width=520,
            value=state.venue_name or "",
        )

        venue_address = ft.TextField(
            label="Venue address",
            hint_text="Optional",
            width=520,
            multiline=True,
            min_lines=2,
            max_lines=4,
            value=state.venue_address or "",
        )

        def on_continue(_: ft.ControlEvent) -> None:
            if not couple_names.value or not couple_names.value.strip():
                set_status("Please enter the couple names.", is_error=True)
                return

            state.couple_names = couple_names.value.strip()
            state.wedding_date = wedding_date.value.strip() if wedding_date.value else None
            state.venue_name = venue_name.value.strip() if venue_name.value else None
            state.venue_address = venue_address.value.strip() if venue_address.value else None

            state.clear_import_state()

            set_status("Wedding details saved. No database event has been created yet.")
            render_upload_screen()

        page.add(
            ft.Column(
                controls=[
                    ft.Text("Local Wedding RSVP", size=34, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Step 1 of 3: enter the basic wedding details. "
                        "The event will only be created after you confirm the guest import."
                    ),
                    section_card(
                        "Wedding details",
                        [
                            couple_names,
                            wedding_date,
                            venue_name,
                            venue_address,
                            ft.Row(
                                controls=[
                                    ft.ElevatedButton(
                                        "Continue to upload",
                                        on_click=on_continue,
                                    ),
                                    ft.TextButton(
                                        "Delete local test data",
                                        on_click=lambda _: show_reset_dialog(),
                                    ),
                                ],
                                spacing=12,
                            ),
                        ],
                    ),
                ],
                spacing=18,
            )
        )

        page.update()

    def render_upload_screen() -> None:
        clear_page()

        selected_file_text = ft.Text(
            f"Selected file: {state.selected_file_path}"
            if state.selected_file_path
            else "No file selected yet."
        )

        def on_file_selected(event: ft.FilePickerResultEvent) -> None:
            if not event.files:
                return

            selected_file = event.files[0]

            if not selected_file.path:
                set_status("Could not read selected file path.", is_error=True)
                return

            state.selected_file_path = Path(selected_file.path)
            state.validation_result = None

            selected_file_text.value = f"Selected file: {state.selected_file_path}"
            set_status("File selected.")
            page.update()

        file_picker = ft.FilePicker(on_result=on_file_selected)
        page.overlay.append(file_picker)

        def on_validate(_: ft.ControlEvent) -> None:
            if state.selected_file_path is None:
                set_status("Please select a CSV or XLSX file first.", is_error=True)
                return

            try:
                state.validation_result = import_guest_file(state.selected_file_path)
                set_status("File validated successfully.")
                render_validation_screen()

            except GuestImportError as exc:
                logger.exception("Guest import validation failed")
                set_status(str(exc), is_error=True)

            except Exception:
                logger.exception("Unexpected validation error")
                set_status("Something went wrong while validating the file.", is_error=True)

        page.add(
            ft.Column(
                controls=[
                    ft.Text("Upload guests", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Step 2 of 3: upload a CSV or XLSX file with these columns: "
                        "name, phone_number, guests_count."
                    ),
                    section_card(
                        "Guest file",
                        [
                            ft.ElevatedButton(
                                "Choose CSV/XLSX file",
                                on_click=lambda _: file_picker.pick_files(
                                    allow_multiple=False,
                                    allowed_extensions=["csv", "xlsx"],
                                ),
                            ),
                            selected_file_text,
                            ft.Row(
                                controls=[
                                    ft.ElevatedButton("Validate file", on_click=on_validate),
                                    ft.TextButton("Back", on_click=lambda _: render_setup_screen()),
                                ],
                                spacing=12,
                            ),
                        ],
                    ),
                ],
                spacing=18,
            )
        )

        page.update()

    def render_validation_screen() -> None:
        clear_page()

        result = state.validation_result

        if result is None:
            set_status("No validation result found.", is_error=True)
            render_upload_screen()
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

        def ensure_event_exists(db) -> int:
            """
            Create the event only at the final confirmed import step.

            This avoids empty events if the user goes back, closes the app,
            or validates files without importing.
            """

            if state.event_id is not None:
                return state.event_id

            if not state.couple_names:
                raise ValueError("Missing couple names. Please return to setup.")

            event = create_event(
                db=db,
                couple_names=state.couple_names,
                wedding_date=state.wedding_date,
                venue_name=state.venue_name,
                venue_address=state.venue_address,
            )

            state.event_id = event.id
            return event.id

        def on_import_valid_rows(_: ft.ControlEvent) -> None:
            if state.selected_file_path is None:
                set_status("No file selected.", is_error=True)
                return

            if state.validation_result is None:
                set_status("Please validate the file before importing.", is_error=True)
                return

            db = SessionLocal()

            try:
                event_id = ensure_event_exists(db)

                import_result = import_valid_guest_rows_to_database(
                    db=db,
                    valid_rows=state.validation_result.valid_rows,
                    event_id=event_id,
                    invalid_count=len(state.validation_result.invalid_rows),
                )

                set_status(
                    f"Import finished. Saved {import_result.saved_count} guests. "
                    f"Skipped {import_result.invalid_count} invalid rows and "
                    f"{import_result.duplicate_count} duplicate guests."
                )

                render_dashboard_screen()

            except Exception:
                logger.exception("Failed to import guests to database")
                set_status("Something went wrong while saving guests.", is_error=True)

            finally:
                db.close()

        valid_preview_note = ""
        if len(result.valid_rows) > PREVIEW_ROW_LIMIT:
            valid_preview_note = (
                f" Showing first {PREVIEW_ROW_LIMIT} valid rows only."
            )

        invalid_preview_note = ""
        if len(result.invalid_rows) > PREVIEW_ROW_LIMIT:
            invalid_preview_note = (
                f" Showing first {PREVIEW_ROW_LIMIT} invalid rows only."
            )

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
                                on_click=lambda _: render_upload_screen(),
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=18,
            )
        )

        page.update()

    def render_dashboard_screen() -> None:
        clear_page()

        if state.event_id is None:
            set_status("No event selected.", is_error=True)
            render_setup_screen()
            return

        db = SessionLocal()

        try:
            guests = list_guests_for_event(db=db, event_id=state.event_id)

        except Exception:
            logger.exception("Failed to load dashboard guests")
            set_status("Something went wrong while loading guests.", is_error=True)
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
            if state.event_id is None:
                set_status("No event selected.", is_error=True)
                return

            db = SessionLocal()

            try:
                result = match_event_guests_with_telegram_contacts(
                    db=db,
                    event_id=state.event_id,
                )

                set_status(
                    f"Telegram matching finished. "
                    f"Matched {result.matched_count} of {result.total_guests} guests."
                )

                render_dashboard_screen()

            except TelegramServiceError as exc:
                logger.exception("Telegram matching failed")
                set_status(str(exc), is_error=True)

            except Exception:
                logger.exception("Unexpected Telegram matching error")
                set_status(
                    "Something went wrong while matching Telegram contacts.",
                    is_error=True,
                )

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
                                on_click=lambda _: render_upload_screen(),
                            ),
                            ft.TextButton(
                                "Start new event",
                                on_click=lambda _: render_setup_screen(),
                            ),
                            ft.TextButton(
                                "Delete local test data",
                                on_click=lambda _: show_reset_dialog(),
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=18,
            )
        )

        page.update()

    render_setup_screen()