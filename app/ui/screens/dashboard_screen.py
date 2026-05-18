from __future__ import annotations

import logging

import flet as ft

from app.core.database import SessionLocal
from app.services.dashboard_summary_service import (
    DashboardSummary,
    get_dashboard_summary,
)
from app.services.guest_query_service import list_guests_for_event
from app.services.invitation_send_service import (
    InvitationSendError,
    build_invitation_send_previews,
    send_invitations_to_matched_guests,
)
from app.services.message_status_service import (
    MessageStatusSummary,
    get_message_status_summary,
)
from app.services.rsvp_query_service import list_latest_rsvps_for_event
from app.services.rsvp_runtime_service import RsvpRuntimeError
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

        dashboard_summary = get_dashboard_summary(
            db=db,
            event_id=state.event_id,
        )

        message_summary = get_message_status_summary(
            db=db,
            event_id=state.event_id,
        )

        rsvp_statuses = list_latest_rsvps_for_event(
            db=db,
            event_id=state.event_id,
        )

        logger.info(
            "Dashboard guests loaded. event_id=%s guests=%s",
            state.event_id,
            len(guests),
        )

    except Exception:
        logger.exception("Failed to load dashboard guests.")
        status.show_error("Something went wrong while loading guests.")
        guests = []
        rsvp_statuses = []

        dashboard_summary = DashboardSummary(
            total_guests=0,
            sendable=0,
            sent=0,
            failed=0,
            responded=0,
            attending=0,
            not_attending=0,
            total_attending_guests=0,
        )

        message_summary = MessageStatusSummary(
            total_guests=0,
            telegram_matched=0,
            ready_to_send=0,
            sent=0,
            failed=0,
            not_matched=0,
            statuses=[],
        )

    finally:
        db.close()

    runtime_status = context.runtime.get_status()

    if runtime_status.public_base_url:
        state.public_base_url = runtime_status.public_base_url

    if state.rsvp_runtime_indicator_status != "failed":
        if state.public_base_url and runtime_status.server_running and runtime_status.tunnel_running:
            state.rsvp_runtime_indicator_status = "live"
            state.rsvp_runtime_indicator_message = "Public RSVP link is live."
        elif state.public_base_url and (
            not runtime_status.server_running or not runtime_status.tunnel_running
        ):
            state.rsvp_runtime_indicator_status = "warning"
            state.rsvp_runtime_indicator_message = (
                "The public RSVP link was started, but the server or tunnel "
                "does not look healthy. Check data/logs/app.log."
            )
            logger.warning(
                "RSVP runtime warning. server_running=%s tunnel_running=%s public_url=%s",
                runtime_status.server_running,
                runtime_status.tunnel_running,
                state.public_base_url,
            )

    guest_preview_rows = guests[:PREVIEW_ROW_LIMIT]
    message_status_preview_rows = message_summary.statuses[:PREVIEW_ROW_LIMIT]
    rsvp_preview_rows = rsvp_statuses[:PREVIEW_ROW_LIMIT]

    rsvp_status_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Guest")),
            ft.DataColumn(ft.Text("Phone")),
            ft.DataColumn(ft.Text("Response")),
            ft.DataColumn(ft.Text("Attending count")),
            ft.DataColumn(ft.Text("Notes")),
            ft.DataColumn(ft.Text("Submitted at")),
        ],
        rows=[
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(row.guest_name)),
                    ft.DataCell(ft.Text(row.phone_number or "")),
                    ft.DataCell(ft.Text(_format_rsvp_response(row.response))),
                    ft.DataCell(ft.Text(str(row.attending_count))),
                    ft.DataCell(ft.Text(row.notes or "")),
                    ft.DataCell(ft.Text(str(row.submitted_at))),
                ]
            )
            for row in rsvp_preview_rows
        ],
    )

    invitation_preview_text = ft.Text(
        "No preview yet. Start the public RSVP link, then click Preview invitation.",
        selectable=True,
        color=ft.Colors.GREY_700,
    )

    send_help_text = ft.Text(
        _build_send_help_text(
            ready_to_send_count=message_summary.ready_to_send,
            has_public_url=bool(state.public_base_url),
        ),
        color=ft.Colors.GREY_700,
    )

    def get_public_url_or_show_error() -> str | None:
        public_base_url = state.public_base_url

        if not public_base_url:
            status.show_error(
                "Start the public RSVP link before previewing or sending invitations."
            )
            return None

        return public_base_url

    def on_start_public_rsvp_link(_: ft.ControlEvent) -> None:
        logger.info("Start public RSVP link button clicked.")

        if state.event_id is None:
            status.show_error("No event selected.")
            return

        try:
            status.show_success(
                "Starting public RSVP link. This may take a few seconds."
            )

            public_base_url = context.runtime.start_public_tunnel_if_needed()
            state.public_base_url = public_base_url
            state.rsvp_runtime_indicator_status = "live"
            state.rsvp_runtime_indicator_message = "Public RSVP link is live."

            logger.info("Public RSVP link ready: %s", public_base_url)

            status.show_success("Public RSVP link is ready.")
            render_dashboard_screen(context)

        except RsvpRuntimeError as exc:
            logger.exception("Failed to start public RSVP link.")
            state.rsvp_runtime_indicator_status = "failed"
            state.rsvp_runtime_indicator_message = str(exc)
            status.show_error(str(exc))
            render_dashboard_screen(context)


        except Exception:
            logger.exception("Unexpected error while starting public RSVP link.")
            state.rsvp_runtime_indicator_status = "failed"
            state.rsvp_runtime_indicator_message = (
                "Something went wrong while starting the public RSVP link."
            )
            status.show_error("Something went wrong while starting the public RSVP link.")
            render_dashboard_screen(context)

    def on_preview_invitation(_: ft.ControlEvent) -> None:
        logger.info("Invitation preview button clicked.")

        if state.event_id is None:
            status.show_error("No event selected.")
            return

        public_base_url = get_public_url_or_show_error()

        if public_base_url is None:
            return

        db = SessionLocal()

        try:
            previews = build_invitation_send_previews(
                db=db,
                event_id=state.event_id,
                public_base_url=public_base_url,
            )

            if not previews:
                invitation_preview_text.value = (
                    "No invitations are ready to send.\n\n"
                    "Possible reasons:\n"
                    "- No guests are matched with Telegram contacts yet.\n"
                    "- All matched guests already have a sent message.\n"
                    "- The imported phone numbers do not match your Telegram contacts."
                )
                invitation_preview_text.color = ft.Colors.RED_700

                status.show_error(
                    "No invitations are ready to send. Match Telegram contacts first."
                )

                page.update()
                return

            first_preview = previews[0]

            invitation_preview_text.value = (
                f"Preview for {first_preview.guest_name}:\n\n"
                f"{first_preview.message_text}"
            )
            invitation_preview_text.color = ft.Colors.BLACK

            status.show_success(
                f"Preview generated. {len(previews)} invitation(s) are ready to send."
            )

            page.update()

        except InvitationSendError as exc:
            logger.exception("Failed to build invitation preview.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected error while building invitation preview.")
            status.show_error("Something went wrong while building the invitation preview.")

        finally:
            db.close()

    def on_send_invitations_requested(_: ft.ControlEvent) -> None:
        logger.info("Send invitations button clicked.")

        if state.event_id is None:
            status.show_error("No event selected.")
            return

        public_base_url = get_public_url_or_show_error()

        if public_base_url is None:
            return

        if message_summary.ready_to_send <= 0:
            status.show_error("No invitations are ready to send.")
            return

        show_send_confirmation_dialog(
            context=context,
            public_base_url=public_base_url,
            message_summary=message_summary,
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

    def on_open_guests_dialog(_: ft.ControlEvent) -> None:
        logger.info("Guest list dialog opened.")

        dialog_guests_table = ft.DataTable(
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

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Guests"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "No guests imported yet."
                            if not guests
                            else f"Imported guest preview.{guest_preview_note}"
                        ),
                        table_container(dialog_guests_table, height=420)
                        if guests
                        else ft.Container(),
                    ],
                    spacing=12,
                    tight=True,
                ),
                width=900,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: _close_dialog(page, dialog)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        _open_dialog(page, dialog)

    def on_open_invitation_status_dialog(_: ft.ControlEvent) -> None:
        logger.info("Invitation status dialog opened.")

        dialog_message_status_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Guest")),
                ft.DataColumn(ft.Text("Phone")),
                ft.DataColumn(ft.Text("Telegram")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Sent at")),
                ft.DataColumn(ft.Text("Error")),
            ],
            rows=[
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(row.guest_name)),
                        ft.DataCell(ft.Text(row.phone_number or "")),
                        ft.DataCell(ft.Text("Yes" if row.telegram_matched else "No")),
                        ft.DataCell(ft.Text(row.status)),
                        ft.DataCell(ft.Text(str(row.sent_at) if row.sent_at else "")),
                        ft.DataCell(ft.Text(row.error_message or "")),
                    ]
                )
                for row in message_status_preview_rows
            ],
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Invitation status"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(f"Total guests: {message_summary.total_guests}"),
                        ft.Text(f"Telegram matched: {message_summary.telegram_matched}"),
                        ft.Text(f"Ready to send: {message_summary.ready_to_send}"),
                        ft.Text(f"Sent: {message_summary.sent}"),
                        ft.Text(f"Failed: {message_summary.failed}"),
                        ft.Text(f"Not matched: {message_summary.not_matched}"),
                        ft.Text(
                            "No message statuses yet."
                            if not message_summary.statuses
                            else f"Message status preview.{message_status_preview_note}"
                        ),
                        table_container(dialog_message_status_table, height=420)
                        if message_summary.statuses
                        else ft.Container(),
                    ],
                    spacing=8,
                    tight=True,
                ),
                width=950,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: _close_dialog(page, dialog)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        _open_dialog(page, dialog)

    guest_preview_note = ""
    if len(guests) > PREVIEW_ROW_LIMIT:
        guest_preview_note = f" Showing first {PREVIEW_ROW_LIMIT} guests only."

    message_status_preview_note = ""
    if len(message_summary.statuses) > PREVIEW_ROW_LIMIT:
        message_status_preview_note = (
            f" Showing first {PREVIEW_ROW_LIMIT} message statuses only."
        )

    rsvp_preview_note = ""
    if len(rsvp_statuses) > PREVIEW_ROW_LIMIT:
        rsvp_preview_note = f" Showing first {PREVIEW_ROW_LIMIT} RSVP responses only."

    page.add(
        ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "Dashboard",
                            size=32,
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                        ),
                        _runtime_status_light(
                            indicator_status=state.rsvp_runtime_indicator_status,
                            message=state.rsvp_runtime_indicator_message,
                            public_base_url=state.public_base_url,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Container(
                            content=section_card(
                                "Current event",
                                [
                                    ft.Text(f"Couple names: {state.couple_names or 'Unknown'}"),
                                    ft.Text(f"Imported guests: {len(guests)}"),
                                ],
                            ),
                            width=260,
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        "Quick views",
                                        size=20,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(
                                        "Open detailed tables without cluttering the dashboard.",
                                        color=ft.Colors.GREY_700,
                                    ),
                                    ft.Row(
                                        controls=[
                                            ft.ElevatedButton(
                                                "Guest list",
                                                on_click=on_open_guests_dialog,
                                                disabled=not guests,
                                            ),
                                            ft.ElevatedButton(
                                                "Invitation status",
                                                on_click=on_open_invitation_status_dialog,
                                                disabled=not guests,
                                            ),
                                        ],
                                        spacing=12,
                                    ),
                                ],
                                spacing=12,
                            ),
                            padding=18,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=12,
                            bgcolor=ft.Colors.WHITE,
                            width=360,
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                section_card(
                    "Progress summary",
                    [
                        ft.Row(
                            controls=[
                                _dashboard_metric_card(
                                    "Total guests",
                                    dashboard_summary.total_guests,
                                    "Imported guest rows",
                                ),
                                _dashboard_metric_card(
                                    "Sendable",
                                    dashboard_summary.sendable,
                                    "Matched and not sent",
                                ),
                                _dashboard_metric_card(
                                    "Sent",
                                    dashboard_summary.sent,
                                    "Invitations sent",
                                ),
                                _dashboard_metric_card(
                                    "Failed",
                                    dashboard_summary.failed,
                                    "Latest send failed",
                                ),
                            ],
                            spacing=12,
                        ),
                        ft.Row(
                            controls=[
                                _dashboard_metric_card(
                                    "Responded",
                                    dashboard_summary.responded,
                                    "Guests with RSVP",
                                ),
                                _dashboard_metric_card(
                                    "Attending",
                                    dashboard_summary.attending,
                                    "Latest RSVP is yes",
                                ),
                                _dashboard_metric_card(
                                    "Not attending",
                                    dashboard_summary.not_attending,
                                    "Latest RSVP is no",
                                ),
                                _dashboard_metric_card(
                                    "Total attending guests",
                                    dashboard_summary.total_attending_guests,
                                    "Including +1s/family count",
                                ),
                            ],
                            spacing=12,
                        ),
                    ],
                ),
                (
                    section_card(
                        "RSVP server and public link",
                        [
                            ft.Text(
                                "The local RSVP server runs on your computer. "
                                "The public link lets guests open their personal RSVP pages."
                            ),
                            ft.Text(
                                f"Local RSVP server: "
                                f"{'Running' if runtime_status.server_running else 'Not running'}"
                            ),
                            ft.Text(f"Local address: {runtime_status.local_base_url}"),
                            ft.Text(
                                "Public RSVP link: "
                                + (
                                    state.public_base_url
                                    if state.public_base_url
                                    else "Not started yet"
                                ),
                                selectable=True,
                            ),
                            ft.Row(
                                controls=[
                                    ft.ElevatedButton(
                                        "Start public RSVP link",
                                        on_click=on_start_public_rsvp_link,
                                        disabled=not guests,
                                    ),
                                ],
                                spacing=12,
                            ),
                        ],
                    )
                    if state.rsvp_runtime_indicator_status == "not_started"
                    else ft.Container()
                ),
                section_card(
                    "RSVP responses",
                    [
                        ft.Text(
                            "No RSVP responses yet."
                            if not rsvp_statuses
                            else f"Latest RSVP response per guest.{rsvp_preview_note}"
                        ),
                        table_container(rsvp_status_table, height=320)
                        if rsvp_statuses
                        else ft.Container(),
                    ],
                ),
                section_card(
                    "Invitation sending",
                    [
                        ft.Text(
                            "Match Telegram contacts, preview the invitation, then confirm sending. "
                            "The public RSVP link is managed in the section above."
                        ),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton(
                                    "1. Match Telegram contacts",
                                    on_click=on_match_telegram_contacts,
                                    disabled=not guests,
                                ),
                                ft.ElevatedButton(
                                    "2. Preview invitation",
                                    on_click=on_preview_invitation,
                                    disabled=not guests or not state.public_base_url,
                                ),
                                ft.ElevatedButton(
                                    "3. Send invitations",
                                    on_click=on_send_invitations_requested,
                                    disabled=(
                                        not guests
                                        or not state.public_base_url
                                        or message_summary.ready_to_send <= 0
                                    ),
                                ),
                            ],
                            spacing=12,
                        ),
                        send_help_text,
                        ft.Container(
                            content=invitation_preview_text,
                            padding=14,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=10,
                            bgcolor=ft.Colors.GREY_100,
                            width=760,
                        ),
                    ],
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Refresh dashboard",
                            on_click=lambda _: render_dashboard_screen(context),
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


def show_send_confirmation_dialog(
    context: AppContext,
    public_base_url: str,
    message_summary: MessageStatusSummary,
) -> None:
    page = context.page
    state = context.state
    status = context.status

    ready_to_send_count = message_summary.ready_to_send

    def close_dialog() -> None:
        try:
            if hasattr(page, "close"):
                page.close(dialog)
            else:
                dialog.open = False
                page.update()
        except Exception:
            logger.exception("Failed to close send confirmation dialog.")

    def on_confirm_send(_: ft.ControlEvent) -> None:
        logger.warning(
            "Invitation sending confirmed from UI. event_id=%s ready_count=%s",
            state.event_id,
            ready_to_send_count,
        )

        if state.event_id is None:
            close_dialog()
            status.show_error("No event selected.")
            return

        close_dialog()

        db = SessionLocal()

        try:
            status.show_success(
                "Sending invitations. Please keep the app open until it finishes."
            )

            result = send_invitations_to_matched_guests(
                db=db,
                event_id=state.event_id,
                public_base_url=public_base_url,
                delay_seconds=8,
            )

            status.show_success(
                f"Invitation sending finished. "
                f"Sent {result.sent_count}, "
                f"failed {result.failed_count}, "
                f"skipped {result.skipped_count}."
            )

            render_dashboard_screen(context)

        except TelegramServiceError as exc:
            logger.exception("Telegram error while sending invitations from UI.")
            status.show_error(str(exc))

        except InvitationSendError as exc:
            logger.exception("Invitation sending failed from UI.")
            status.show_error(str(exc))

        except Exception:
            logger.exception("Unexpected error while sending invitations from UI.")
            status.show_error("Something went wrong while sending invitations.")

        finally:
            db.close()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Send Telegram invitations?"),
        content=ft.Column(
            controls=[
                ft.Text(
                    "This will send real Telegram messages from your personal Telegram account.",
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.RED_700,
                ),
                ft.Text(f"Ready to send: {message_summary.ready_to_send}"),
                ft.Text(f"Already sent: {message_summary.sent}"),
                ft.Text(f"Previous failed attempts: {message_summary.failed}"),
                ft.Text(f"Not matched with Telegram: {message_summary.not_matched}"),
                ft.Text(""),
                ft.Text("Public RSVP URL:", weight=ft.FontWeight.BOLD),
                ft.Text(public_base_url, selectable=True),
                ft.Text(""),
                ft.Text("Safety rules:", weight=ft.FontWeight.BOLD),
                ft.Text("- Only Telegram-matched guests will receive messages."),
                ft.Text("- Guests with an existing sent message will be skipped."),
                ft.Text("- The app waits between messages to reduce rate-limit risk."),
                ft.Text("- If Telegram returns a rate-limit warning, sending stops."),
            ],
            tight=True,
            spacing=6,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: close_dialog()),
            ft.ElevatedButton(
                f"YES, SEND {ready_to_send_count} INVITATION(S)",
                bgcolor=ft.Colors.GREEN_700,
                color=ft.Colors.WHITE,
                on_click=on_confirm_send,
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
        logger.exception("Failed to open send confirmation dialog.")
        status.show_error("Could not open send confirmation dialog.")




def _open_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    try:
        if hasattr(page, "open"):
            page.open(dialog)
        else:
            page.dialog = dialog
            dialog.open = True
            page.update()

    except Exception:
        logger.exception("Failed to open dashboard dialog.")


def _close_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    try:
        if hasattr(page, "close"):
            page.close(dialog)
        else:
            dialog.open = False
            page.update()

    except Exception:
        logger.exception("Failed to close dashboard dialog.")



def _runtime_status_light(
    indicator_status: str,
    message: str | None,
    public_base_url: str | None,
) -> ft.Container:
    if indicator_status == "live":
        color = ft.Colors.GREEN_600
        label = "RSVP live"
        helper = public_base_url or message or "Server and tunnel are running."

    elif indicator_status == "warning":
        color = ft.Colors.AMBER_600
        label = "RSVP warning"
        helper = message or "There may be an issue with the server or tunnel."

    elif indicator_status == "failed":
        color = ft.Colors.RED_600
        label = "RSVP failed"
        helper = message or "Could not start the public RSVP link."

    else:
        color = ft.Colors.GREY_400
        label = "RSVP not live"
        helper = "Public RSVP link has not been started yet."

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    width=14,
                    height=14,
                    border_radius=7,
                    bgcolor=color,
                    animate_opacity=ft.Animation(1200, ft.AnimationCurve.EASE_IN_OUT),
                    opacity=0.85,
                ),
                ft.Column(
                    controls=[
                        ft.Text(label, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            helper,
                            size=12,
                            color=ft.Colors.GREY_700,
                            selectable=bool(public_base_url),
                        ),
                    ],
                    spacing=2,
                    tight=True,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=10,
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=20,
        bgcolor=ft.Colors.WHITE,
    )



def _dashboard_metric_card(
    label: str,
    value: int,
    helper_text: str | None = None,
) -> ft.Container:
    controls: list[ft.Control] = [
        ft.Text(label, size=13, color=ft.Colors.GREY_700),
        ft.Text(str(value), size=28, weight=ft.FontWeight.BOLD),
    ]

    if helper_text:
        controls.append(
            ft.Text(
                helper_text,
                size=12,
                color=ft.Colors.GREY_600,
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=controls,
            spacing=4,
        ),
        width=220,
        padding=14,
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=12,
        bgcolor=ft.Colors.WHITE,
    )


def _format_rsvp_response(response: str) -> str:
    if response == "yes":
        return "Yes"

    if response == "no":
        return "No"

    return response


def _build_send_help_text(
    ready_to_send_count: int,
    has_public_url: bool,
) -> str:
    if not has_public_url:
        return (
            "Start the public RSVP link before previewing or sending invitations."
        )

    if ready_to_send_count > 0:
        return (
            f"{ready_to_send_count} invitation(s) are ready to send. "
            "Preview the message first, then send."
        )

    return (
        "Send is disabled because there are no guests ready to send. "
        "First match Telegram contacts. If this stays at 0, the uploaded phone numbers "
        "do not match your Telegram contacts, or all matched guests were already sent."
    )


def _go_to_upload(context: AppContext) -> None:
    from app.ui.screens.upload_screen import render_upload_screen

    render_upload_screen(context)


def _go_to_setup(context: AppContext) -> None:
    from app.ui.screens.setup_screen import render_setup_screen

    render_setup_screen(context)