from __future__ import annotations

from pathlib import Path

from app.importers.guest_validator import ValidationResult


class AppState:
    """
    In-memory UI state for the current desktop app session.

    This does not replace the SQLite database.
    It only remembers what the user is currently doing in the UI.
    """

    def __init__(self) -> None:
        self.event_id: int | None = None

        self.couple_names: str | None = None
        self.wedding_date: str | None = None
        self.venue_name: str | None = None
        self.venue_address: str | None = None

        self.selected_file_path: Path | None = None
        self.validation_result: ValidationResult | None = None

        # Remembered while the app is open.
        # Set automatically when the app starts the public Cloudflare tunnel.
        self.public_base_url: str | None = None

        # Dashboard runtime indicator.
        # Values: "not_started", "live", "warning", "failed"
        self.rsvp_runtime_indicator_status: str = "not_started"
        self.rsvp_runtime_indicator_message: str | None = None

        # Invitation sending UI flow.
        # These remember whether Telegram matching was already completed
        # for the currently loaded guest list.
        self.invitation_flow_matched_event_id: int | None = None
        self.invitation_flow_matched_total_guests: int | None = None

    def clear_import_state(self) -> None:
        self.selected_file_path = None
        self.validation_result = None

    def clear_all(self) -> None:
        self.event_id = None

        self.couple_names = None
        self.wedding_date = None
        self.venue_name = None
        self.venue_address = None

        self.public_base_url = None

        self.rsvp_runtime_indicator_status = "not_started"
        self.rsvp_runtime_indicator_message = None

        self.clear_import_state()