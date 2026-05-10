from __future__ import annotations

import flet as ft


def clear_page(page: ft.Page, status_text: ft.Control) -> None:
    """
    Clear all visible controls from the page and keep the shared status text
    at the top of the page.

    The caller should pass status.text, not the whole StatusController.
    Example:
        clear_page(page, status.text)
    """

    page.controls.clear()
    page.add(status_text)


def section_card(title: str, controls: list[ft.Control]) -> ft.Container:
    """
    Reusable card-like section used across the desktop UI.
    """

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
    """
    Scrollable container for DataTable controls.

    Gives tables both horizontal and vertical scrolling so large guest files
    do not break the layout.
    """

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