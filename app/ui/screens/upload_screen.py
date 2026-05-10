from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from app.importers.guest_import_service import GuestImportError, import_guest_file
from app.ui.context import AppContext
from app.ui.layout import clear_page, section_card


logger = logging.getLogger(__name__)


def render_upload_screen(context: AppContext) -> None:
    page = context.page
    state = context.state
    status = context.status

    logger.info("Rendering upload screen.")

    clear_page(page, status.text)

    selected_file_text = ft.Text(
        f"Selected file: {state.selected_file_path}"
        if state.selected_file_path
        else "No file selected yet."
    )

    def on_file_selected(event: ft.FilePickerResultEvent) -> None:
        logger.info("File picker result received.")

        if not event.files:
            logger.info("File picker closed without selecting a file.")
            return

        selected_file = event.files[0]

        if not selected_file.path:
            status.show_error("Could not read selected file path.")
            return

        state.selected_file_path = Path(selected_file.path)
        state.validation_result = None

        logger.info("Guest file selected. path=%s", state.selected_file_path)

        selected_file_text.value = f"Selected file: {state.selected_file_path}"
        status.show_success("File selected.")
        page.update()

    file_picker = ft.FilePicker(on_result=on_file_selected)
    page.overlay.append(file_picker)

    def on_validate(_: ft.ControlEvent) -> None:
        logger.info("Validate file button clicked.")

        if state.selected_file_path is None:
            status.show_error("Please select a CSV or XLSX file first.")
            return

        try:
            logger.info("Guest file validation started. path=%s", state.selected_file_path)

            state.validation_result = import_guest_file(state.selected_file_path)

            logger.info(
                "Guest file validation completed. valid=%s invalid=%s missing_columns=%s",
                len(state.validation_result.valid_rows),
                len(state.validation_result.invalid_rows),
                state.validation_result.missing_columns,
            )

            status.show_success("File validated successfully.")

            from app.ui.screens.validation_screen import render_validation_screen

            render_validation_screen(context)

        except GuestImportError as exc:
            logger.exception("Guest import validation failed.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected validation error.")
            status.show_error("Something went wrong while validating the file.")

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
                                ft.TextButton(
                                    "Back",
                                    on_click=lambda _: _go_back_to_setup(context),
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


def _go_back_to_setup(context: AppContext) -> None:
    from app.ui.screens.setup_screen import render_setup_screen

    render_setup_screen(context)