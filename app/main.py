from __future__ import annotations

import logging

import flet as ft

from app.ui.app_ui import main


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


if __name__ == "__main__":
    ft.app(target=main)