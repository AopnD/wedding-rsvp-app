from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from app.core.database import SessionLocal, create_database
from app.importers.guest_import_service import GuestImportError, import_guest_file
from app.importers.guest_validator import ValidationResult
from app.services.event_service import create_event
from app.services.guest_import_db_service import import_valid_guests_to_database
from app.services.guest_query_service import list_guests_for_event


logger = logging.getLogger(__name__)


class AppState:
    """
    Small in-memory UI state.

    This keeps Chunk 4 simple.
    Later we can replace this with a more formal app controller if needed.
    """

    def __init__(self) -> None:
        self.event_id: int | None = None
        self.selected_file_path: Path | None = None
        self.validation_result: ValidationResult | None = None


def main(page: ft.Page) -> None:
    create_database()

    state = AppState()

    page.title = "Local Wedding RSVP"
    page.window_width = 1000
    page.window_height = 750
    page.padding = 24
    page.theme_mode = ft.ThemeMode.LIGHT

    status_text = ft.Text("", color=ft.Colors.RED_700)

    def set_status(message: str, is_error: bool = False) -> None:
        status_text.value = message
        status_text.color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
        page.update()

    def clear_page() -> None:
        page.controls.clear()
        page.add(status_text)

    def render_setup_screen() -> None:
        clear_page()

        couple_names = ft.TextField(
            label="Couple names",
            hint_text="Example: Omer & Dana",
            width=500,
        )

        wedding_date = ft.TextField(
            label="Wedding date",
            hint_text="Example: 2026-09-01",
            width=500,
        )

        venue_name = ft.TextField(
            label="Venue name",
            hint_text="Example: The Garden Hall",
            width=500,
        )

        venue_address = ft.TextField(
            label="Venue address",
            hint_text="Optional",
            width=500,
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        def on_continue(_: ft.ControlEvent) -> None:
            if not couple_names.value or not couple_names.value.strip():
                set_status("Please enter the couple names.", is_error=True)
                return

            db = SessionLocal()

            try:
                event = create_event(
                    db=db,
                    couple_names=couple_names.value,
                    wedding_date=wedding_date.value,
                    venue_name=venue_name.value,
                    venue_address=venue_address.value,
                )

                state.event_id = event.id
                set_status("Event created successfully.")
                render_upload_screen()

            except Exception:
                logger.exception("Failed to create event")
                set_status("Something went wrong while creating the event.", is_error=True)

            finally:
                db.close()

        page.add(
            ft.Column(
                controls=[
                    ft.Text("Setup", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text("Enter the basic wedding details."),
                    couple_names,
                    wedding_date,
                    venue_name,
                    venue_address,
                    ft.ElevatedButton("Continue to upload", on_click=on_continue),
                ],
                spacing=16,
            )
        )

        page.update()

    def render_upload_screen() -> None:
        clear_page()

        selected_file_text = ft.Text("No file selected yet.")

        def on_file_selected(event: ft.FilePickerResultEvent) -> None:
            if not event.files:
                return

            selected_file = event.files[0]

            if not selected_file.path:
                set_status("Could not read selected file path.", is_error=True)
                return

            state.selected_file_path = Path(selected_file.path)
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
                        "Upload a CSV or XLSX file with these columns: "
                        "name, phone_number, guests_count."
                    ),
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
                spacing=16,
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
                for row in result.valid_rows
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
                for row in result.invalid_rows
            ],
        )

        def on_import_valid_rows(_: ft.ControlEvent) -> None:
            if state.event_id is None:
                set_status("No event was created yet.", is_error=True)
                return

            if state.selected_file_path is None:
                set_status("No file selected.", is_error=True)
                return

            db = SessionLocal()

            try:
                saved_count, invalid_count = import_valid_guests_to_database(
                    db=db,
                    file_path=state.selected_file_path,
                    event_id=state.event_id,
                )

                set_status(
                    f"Import finished. Saved {saved_count} guests. "
                    f"Skipped {invalid_count} invalid rows."
                )

                render_dashboard_screen()

            except Exception:
                logger.exception("Failed to import guests to database")
                set_status("Something went wrong while saving guests.", is_error=True)

            finally:
                db.close()

        page.add(
            ft.Column(
                controls=[
                    ft.Text("Validation result", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Valid rows: {len(result.valid_rows)}"),
                    ft.Text(f"Invalid rows: {len(result.invalid_rows)}"),
                    ft.Divider(),
                    ft.Text("Valid guests", size=20, weight=ft.FontWeight.BOLD),
                    valid_rows_table if result.valid_rows else ft.Text("No valid guests found."),
                    ft.Divider(),
                    ft.Text("Invalid rows", size=20, weight=ft.FontWeight.BOLD),
                    invalid_rows_table if result.invalid_rows else ft.Text("No invalid rows found."),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                "Import valid guests",
                                on_click=on_import_valid_rows,
                                disabled=not result.valid_rows,
                            ),
                            ft.TextButton("Back to upload", on_click=lambda _: render_upload_screen()),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
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
                for guest in guests
            ],
        )

        page.add(
            ft.Column(
                controls=[
                    ft.Text("Dashboard", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Imported guests: {len(guests)}"),
                    guests_table if guests else ft.Text("No guests imported yet."),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                "Upload another file",
                                on_click=lambda _: render_upload_screen(),
                            ),
                            ft.TextButton(
                                "Start new event",
                                on_click=lambda _: render_setup_screen(),
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
            )
        )

        page.update()

    render_setup_screen()