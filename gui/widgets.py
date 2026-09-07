"""Мелкие переиспользуемые Flet-хелперы для вью."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date

import flet as ft

from .format import MONTH_NAMES_RU
from .theme import COLORS


def year_options(span_back: int = 2, span_fwd: int = 2) -> list[int]:
    now = date.today().year
    return list(range(now - span_back, now + span_fwd + 1))


def card(*content: ft.Control, padding: int = 16, expand: bool = False,
         accent: str | None = None, bgcolor: str | None = None) -> ft.Container:
    if accent:
        border = ft.Border(
            top=ft.BorderSide(1, COLORS["border"]),
            right=ft.BorderSide(1, COLORS["border"]),
            bottom=ft.BorderSide(1, COLORS["border"]),
            left=ft.BorderSide(4, accent),
        )
    else:
        border = ft.Border.all(1, COLORS["border"])
    return ft.Container(
        content=content[0] if len(content) == 1 else ft.Column(list(content), tight=True, spacing=8),
        padding=padding,
        bgcolor=bgcolor or COLORS["surface"],
        border=border,
        border_radius=12,
        expand=expand,
    )


def section_title(text: str) -> ft.Text:
    return ft.Text(text, size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"])


def hint(text: str) -> ft.Text:
    return ft.Text(text, size=12, color=COLORS["text_secondary"])


def money_text(value: float, size: int = 22, color: str | None = None) -> ft.Text:
    from .format import format_currency

    return ft.Text(
        format_currency(value), size=size, weight=ft.FontWeight.BOLD,
        color=color or COLORS["text"],
    )


def text_field(
    label: str, value: str = "", *, hint_text: str = "", keyboard: str | None = None,
    width: int | None = None, on_submit: Callable | None = None, password: bool = False,
) -> ft.TextField:
    kt = None
    if keyboard == "number":
        kt = ft.KeyboardType.NUMBER
    return ft.TextField(
        label=label, value=value, hint_text=hint_text, keyboard_type=kt,
        width=width, dense=True, on_submit=on_submit, password=password,
        border_color=COLORS["border"], color=COLORS["text"],
    )


def dropdown(
    label: str, options: Iterable[tuple[str, str]], value: str | None = None,
    *, on_select: Callable | None = None, width: int | None = None,
) -> ft.Dropdown:
    return ft.Dropdown(
        label=label,
        value=value,
        width=width,
        dense=True,
        options=[ft.DropdownOption(key=k, text=t) for k, t in options],
        on_select=on_select,
        border_color=COLORS["border"],
        color=COLORS["text"],
    )


def month_dropdown(value: int, on_select: Callable) -> ft.Dropdown:
    return dropdown(
        "Месяц",
        [(str(i), MONTH_NAMES_RU[i]) for i in range(1, 13)],
        str(value),
        on_select=on_select,
        width=150,
    )


def year_dropdown(value: int, on_select: Callable) -> ft.Dropdown:
    return dropdown(
        "Год",
        [(str(y), str(y)) for y in year_options()],
        str(value),
        on_select=on_select,
        width=110,
    )


def switch_row(label: str, value: bool, on_change: Callable) -> ft.Switch:
    return ft.Switch(label=label, value=value, on_change=on_change,
                     active_color=COLORS["accent"])


def primary_button(text: str, on_click: Callable, *, icon: str | None = None,
                   expand: bool = False) -> ft.FilledButton:
    return ft.FilledButton(text, icon=icon, on_click=on_click, expand=expand)


def tonal_button(text: str, on_click: Callable, *, icon: str | None = None,
                 expand: bool = False) -> ft.FilledTonalButton:
    return ft.FilledTonalButton(text, icon=icon, on_click=on_click, expand=expand)


def ghost_button(text: str, on_click: Callable, *, icon: str | None = None) -> ft.TextButton:
    return ft.TextButton(text, icon=icon, on_click=on_click)


def icon_button(icon: str, on_click: Callable, *, tooltip: str = "",
                color: str | None = None) -> ft.IconButton:
    return ft.IconButton(icon=icon, on_click=on_click, tooltip=tooltip, icon_color=color,
                         icon_size=18)


def chip(text: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=11, color=color, weight=ft.FontWeight.W_500),
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        border=ft.Border.all(1, color),
        border_radius=999,
    )


def empty_state(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=13, color=COLORS["text_secondary"]),
        padding=ft.Padding.symmetric(vertical=24, horizontal=8),
    )


def card_grid(cards: list[ft.Control], *, col_sm: int = 6, col_lg: int = 4) -> ft.Control:
    """Адаптивная сетка карточек.

    ``ft.Row(wrap=True)`` из контейнеров фиксированной ширины внутри
    вертикально-скроллящейся колонки в Flet 0.86 не измеряется и рендерится
    серым прямоугольником — поэтому используем ``ResponsiveRow`` и снимаем
    с карточек фиксированную ширину (её задаёт колонка)."""
    for c in cards:
        if isinstance(c, ft.Container):
            c.width = None
    return ft.ResponsiveRow(
        controls=[
            ft.Container(c, col={"xs": 12, "sm": col_sm, "lg": col_lg}, padding=0)
            for c in cards
        ],
        run_spacing=12,
        columns=12,
    )


# ── диалоги ────────────────────────────────────────────────────


def show_modal(page: ft.Page, title: str, body: ft.Control, actions: list[ft.Control]) -> ft.AlertDialog:
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, size=17, weight=ft.FontWeight.BOLD),
        content=ft.Container(content=body, width=460),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
        scrollable=True,
    )
    page.show_dialog(dlg)
    return dlg


def confirm(page: ft.Page, title: str, on_yes: Callable[[], None], *,
            danger: bool = True) -> None:
    def close(e=None):
        page.pop_dialog()

    def yes(e):
        close()
        on_yes()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
            actions=[
                ft.TextButton("Отмена", on_click=close),
                ft.FilledButton(
                    "Удалить" if danger else "OK",
                    on_click=yes,
                    style=ft.ButtonStyle(bgcolor=COLORS["danger"] if danger else None,
                                         color="#ffffff" if danger else None),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
