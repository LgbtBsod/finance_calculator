"""Тема и палитра GUI.

``COLORS`` пересобирается функцией :func:`apply` при смене режима темы —
каждое вью читает ``COLORS[...]`` при построении и подхватывает изменение
при следующей перестройке.
"""

from __future__ import annotations

import flet as ft

ACCENT = "#2563eb"

_LIGHT = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "surface_alt": "#eef1f5",
    "text": "#111827",
    "text_secondary": "#6b7280",
    "border": "#e2e5ea",
    "accent": ACCENT,
    "success": "#15803d",
    "success_bg": "#dcfce7",
    "warning": "#b45309",
    "warning_bg": "#fef3c7",
    "danger": "#b91c1c",
    "danger_bg": "#fee2e2",
    "accent_bg": "#dbeafe",
}

_DARK = {
    "bg": "#0f141a",
    "surface": "#1a212b",
    "surface_alt": "#232c38",
    "text": "#e8eaed",
    "text_secondary": "#95a1b0",
    "border": "#2c3744",
    "accent": "#5b9bff",
    "success": "#86efac",
    "success_bg": "#14361f",
    "warning": "#fcd34d",
    "warning_bg": "#3a2c0a",
    "danger": "#fca5a5",
    "danger_bg": "#3a1414",
    "accent_bg": "#12294d",
}

COLORS: dict[str, str] = dict(_LIGHT)

# Палитра для новых групп расходов и категорий графика.
SWATCHES: list[str] = [
    "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
    "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5",
    "#0d9488", "#c026d3", "#e11d48", "#059669", "#f59e0b",
]


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
    return ft.Theme(color_scheme_seed=ACCENT, color_scheme=_scheme(dark))
