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

        # Chunk 8: remembered while the app is open.
        # User pastes the Cloudflare tunnel URL here before sending invitations.
        self.public_base_url: str | None = None

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

        self.clear_import_state()