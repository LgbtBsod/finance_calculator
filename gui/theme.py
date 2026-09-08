"""Тема и палитра GUI — SAP Horizon (Morning / Evening).

Цвета взяты 1-в-1 из ``@sap-theming/theming-base-content`` (тема
``sap_horizon`` — светлая «Morning», ``sap_horizon_dark`` — тёмная
«Evening»). ``COLORS`` пересобирается функцией :func:`apply` при смене
режима; каждое вью читает ``COLORS[...]`` при построении и подхватывает
изменение при следующей перестройке.
"""

from __future__ import annotations

import flet as ft

# Фирменный акцент SAP (sapBrandColor) — одинаков в обеих темах.
ACCENT = "#0070f2"

# ── SAP Horizon Morning ────────────────────────────────────
_LIGHT: dict[str, str] = {
    "bg": "#f5f6f7",            # sapBackgroundColor
    "surface": "#ffffff",       # sapTile_Background / sapList_Background
    "surface_alt": "#eff1f2",   # sapShell_Background
    "shell": "#ffffff",         # sapShellColor (Morning shell — белый)
    "field": "#ffffff",         # sapField_Background
    "hover": "#eaecee",         # sapList_Hover_Background
    "selected_bg": "#ebf8ff",   # sapList_SelectionBackgroundColor
    "selected_text": "#0064d9", # sapContent_Selected_TextColor
    "text": "#131e29",          # sapTextColor
    "text_secondary": "#556b82",# sapContent_LabelColor
    "border": "#d9d9d9",        # sapGroup_ContentBorderColor
    "border_strong": "#556b81", # sapField_BorderColor
    "accent": ACCENT,           # sapBrandColor
    "accent_hover": "#0064d9",  # sapButton_Emphasized_Hover_Background
    "accent_bg": "#e1f4ff",     # sapInformationBackground
    "link": "#0064d9",          # sapLink_TextColor
    "success": "#256f3a",       # sapPositiveColor
    "success_el": "#30914c",    # sapPositiveElementColor
    "success_bg": "#f5fae5",    # sapPositiveBackground
    "warning": "#e76500",       # sapCriticalColor
    "warning_bg": "#fff8d6",    # sapCriticalBackground
    "danger": "#aa0808",        # sapNegativeColor
    "danger_el": "#f53232",     # sapNegativeElementColor
    "danger_bg": "#ffeaf4",     # sapNegativeBackground
    "neutral": "#788fa6",       # sapNeutralColor
}

# ── SAP Horizon Evening ────────────────────────────────────
_DARK: dict[str, str] = {
    "bg": "#12171c",
    "surface": "#1d232a",
    "surface_alt": "#252c34",
    "shell": "#12171c",
    "field": "#161c22",
    "hover": "#2b333c",
    "selected_bg": "#0a2d4d",
    "selected_text": "#4db1ff",
    "text": "#f5f6f7",
    "text_secondary": "#8396a8",
    "border": "#323c48",
    "border_strong": "#5b6b7c",
    "accent": ACCENT,
    "accent_hover": "#4db1ff",
    "accent_bg": "#00144a",
    "link": "#008fff",
    "success": "#97dd40",
    "success_el": "#6dad1f",
    "success_bg": "#11331a",
    "warning": "#ffdf72",
    "warning_bg": "#382700",
    "danger": "#fa6161",
    "danger_el": "#fa6161",
    "danger_bg": "#350000",
    "neutral": "#a9b4be",
}

COLORS: dict[str, str] = dict(_LIGHT)

# Радиусы SAP Horizon (в px): tile 1rem, element .75rem, button .5rem, field .25rem.
RADIUS_TILE = 16
RADIUS_CARD = 12
RADIUS_BUTTON = 8
RADIUS_FIELD = 6
RADIUS_PILL = 999

# Шрифтовой стек: SAP «72» лицензионный и не бандлится — системный аналог.
FONT_STACK = "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

# sapChart_OrderedColor_1..11 (Horizon) — для групп расходов и графиков.
SWATCHES: list[str] = [
    "#168eff", "#c87b00", "#75980b", "#df1278", "#8b47d7",
    "#049f9a", "#0070f2", "#cc00dc", "#798c77", "#da6c6c", "#5d36ff",
]


def card_shadow() -> ft.BoxShadow:
    """Аналог sapContent_Shadow0 — мягкая тень карточки Horizon."""
    dark = COLORS["bg"] == _DARK["bg"]
    return ft.BoxShadow(
        spread_radius=0,
        blur_radius=6,
        offset=ft.Offset(0, 2),
        color=ft.Colors.with_opacity(0.45 if dark else 0.13, "#223548"),
    )


def resolve_dark(mode: str, system_is_dark: bool) -> bool:
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return system_is_dark


def apply(mode: str, *, system_is_dark: bool = False) -> bool:
    """Пересобрать ``COLORS`` под режим. Возвращает, тёмная ли тема."""
    dark = resolve_dark(mode, system_is_dark)
    COLORS.clear()
    COLORS.update(_DARK if dark else _LIGHT)
    return dark


def _scheme(dark: bool) -> ft.ColorScheme:
    pal = _DARK if dark else _LIGHT
    return ft.ColorScheme(
        primary=pal["accent"],
        on_primary="#ffffff",
        error=pal["danger"],
        surface=pal["bg"],
        on_surface=pal["text"],
        on_surface_variant=pal["text_secondary"],
        surface_container=pal["surface"],
        surface_container_high=pal["surface_alt"],
        outline=pal["border"],
        outline_variant=pal["border"],
    )


def build_theme(dark: bool) -> ft.Theme:
    return ft.Theme(color_scheme_seed=ACCENT, color_scheme=_scheme(dark), font_family=FONT_STACK)
