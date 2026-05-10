from __future__ import annotations

import logging

import flet as ft

from app.ui.context import AppContext
from app.ui.dialogs import show_reset_dialog
from app.ui.layout import clear_page, section_card


logger = logging.getLogger(__name__)


def render_setup_screen(context: AppContext) -> None:
    page = context.page
    state = context.state
    status = context.status

    logger.info("Rendering setup screen.")

    clear_page(page, status.text)

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
        logger.info("Setup continue button clicked.")

        if not couple_names.value or not couple_names.value.strip():
            status.show_error("Please enter the couple names.")
            return

        state.couple_names = couple_names.value.strip()
        state.wedding_date = wedding_date.value.strip() if wedding_date.value else None
        state.venue_name = venue_name.value.strip() if venue_name.value else None
        state.venue_address = venue_address.value.strip() if venue_address.value else None

        state.clear_import_state()

        logger.info(
            "Wedding details saved in UI state. couple_names=%s",
            state.couple_names,
        )

        status.show_success("Wedding details saved. No database event has been created yet.")

        from app.ui.screens.upload_screen import render_upload_screen

        render_upload_screen(context)

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
                                    on_click=lambda _: show_reset_dialog(
                                        context=context,
                                        on_reset_finished=lambda: render_setup_screen(context),
                                    ),
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