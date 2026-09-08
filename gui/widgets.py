"""Мелкие переиспользуемые Flet-хелперы для вью — в стиле SAP Horizon."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date

import flet as ft

from .format import MONTH_NAMES_RU
from .theme import (
    COLORS,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_FIELD,
    RADIUS_PILL,
    card_shadow,
)


def year_options(span_back: int = 2, span_fwd: int = 2) -> list[int]:
    now = date.today().year
    return list(range(now - span_back, now + span_fwd + 1))


def card(*content: ft.Control, padding: int = 16, expand: bool = False,
         accent: str | None = None, bgcolor: str | None = None) -> ft.Container:
    """Карточка Horizon: мягкая тень, скруглённые углы, без жёсткой рамки.
    ``accent`` рисует цветную полосу слева (семантический акцент)."""
    kw: dict = {}
    if accent:
        kw["border"] = ft.Border(left=ft.BorderSide(3, accent))
    return ft.Container(
        content=content[0] if len(content) == 1
        else ft.Column(list(content), tight=True, spacing=8),
        padding=padding,
        bgcolor=bgcolor or COLORS["surface"],
        border_radius=RADIUS_CARD,
        shadow=card_shadow(),
        expand=expand,
        **kw,
    )


def section_title(text: str) -> ft.Text:
    return ft.Text(text, size=19, weight=ft.FontWeight.W_700, color=COLORS["text"])


def hint(text: str) -> ft.Text:
    return ft.Text(text, size=12, color=COLORS["text_secondary"])


def money_text(value: float, size: int = 22, color: str | None = None) -> ft.Text:
    from .format import format_currency

    return ft.Text(
        format_currency(value), size=size, weight=ft.FontWeight.W_700,
        color=color or COLORS["text"],
    )


def _field_style() -> dict:
    return {
        "border_color": COLORS["border_strong"],
        "focused_border_color": COLORS["accent"],
        "border_radius": RADIUS_FIELD,
        "bgcolor": COLORS["field"],
        "color": COLORS["text"],
        "label_style": ft.TextStyle(color=COLORS["text_secondary"], size=12),
        "content_padding": ft.Padding(12, 10, 12, 10),
    }


def text_field(
    label: str, value: str = "", *, hint_text: str = "", keyboard: str | None = None,
    width: int | None = None, on_submit: Callable | None = None, password: bool = False,
) -> ft.TextField:
    kt = ft.KeyboardType.NUMBER if keyboard == "number" else None
    return ft.TextField(
        label=label, value=value, hint_text=hint_text, keyboard_type=kt,
        width=width, dense=True, on_submit=on_submit, password=password,
        **_field_style(),
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
        **_field_style(),
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


def _btn_shape() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=RADIUS_BUTTON),
        padding=ft.Padding(16, 10, 16, 10),
    )


def primary_button(text: str, on_click: Callable, *, icon: str | None = None,
                   expand: bool = False) -> ft.FilledButton:
    """Emphasized-кнопка Horizon: синий фон #0070f2, радиус .5rem."""
    return ft.FilledButton(
        text, icon=icon, on_click=on_click, expand=expand,
        style=ft.ButtonStyle(
            bgcolor=COLORS["accent"], color="#ffffff",
            shape=ft.RoundedRectangleBorder(radius=RADIUS_BUTTON),
            padding=ft.Padding(16, 10, 16, 10),
        ),
    )


def tonal_button(text: str, on_click: Callable, *, icon: str | None = None,
                 expand: bool = False) -> ft.FilledTonalButton:
    return ft.FilledTonalButton(text, icon=icon, on_click=on_click, expand=expand,
                                style=_btn_shape())


def ghost_button(text: str, on_click: Callable, *, icon: str | None = None) -> ft.TextButton:
    return ft.TextButton(text, icon=icon, on_click=on_click,
                         style=ft.ButtonStyle(color=COLORS["link"]))


def icon_button(icon: str, on_click: Callable, *, tooltip: str = "",
                color: str | None = None) -> ft.IconButton:
    return ft.IconButton(icon=icon, on_click=on_click, tooltip=tooltip,
                         icon_color=color or COLORS["text_secondary"], icon_size=18)


def chip(text: str, color: str, *, bg: str | None = None) -> ft.Container:
    """ObjectStatus-подобный чип Horizon: цветной текст на светлой подложке."""
    return ft.Container(
        content=ft.Text(text, size=11, color=color, weight=ft.FontWeight.W_600),
        padding=ft.Padding(8, 3, 8, 3),
        bgcolor=bg or ft.Colors.with_opacity(0.12, color),
        border_radius=RADIUS_PILL,
    )


def empty_state(text: str, *, icon: str = ft.Icons.INBOX_OUTLINED) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(icon, size=40, color=COLORS["neutral"]),
                ft.Text(text, size=13, color=COLORS["text_secondary"],
                        text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10, tight=True,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding(8, 40, 8, 40),
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
        run_spacing=14,
        columns=12,
    )


# ── диалоги ────────────────────────────────────────────────────


def show_modal(page: ft.Page, title: str, body: ft.Control,
               actions: list[ft.Control]) -> ft.AlertDialog:
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, size=17, weight=ft.FontWeight.W_700, color=COLORS["text"]),
        content=ft.Container(content=body, width=460),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=COLORS["surface"],
        shape=ft.RoundedRectangleBorder(radius=RADIUS_CARD),
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
            title=ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=COLORS["text"]),
            bgcolor=COLORS["surface"],
            shape=ft.RoundedRectangleBorder(radius=RADIUS_CARD),
            actions=[
                ft.TextButton("Отмена", on_click=close,
                              style=ft.ButtonStyle(color=COLORS["text_secondary"])),
                ft.FilledButton(
                    "Удалить" if danger else "OK",
                    on_click=yes,
                    style=ft.ButtonStyle(
                        bgcolor=COLORS["danger"] if danger else COLORS["accent"],
                        color="#ffffff",
                        shape=ft.RoundedRectangleBorder(radius=RADIUS_BUTTON),
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
