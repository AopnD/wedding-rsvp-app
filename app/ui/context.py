from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from app.ui.state import AppState
from app.ui.status import StatusController


@dataclass
class AppContext:
    """
    Shared UI context passed between screens.

    This keeps screen functions simple and avoids passing page/state/status
    separately everywhere.
    """

    page: ft.Page
    state: AppState
    status: StatusController