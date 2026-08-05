"""views — Пакет UI-компонентов Streamlit.

Каждый модуль отвечает за одну вкладку или секцию (SRP).
app.py — только точка входа: page_config + tab routing.
"""

from . import (
    common,
    sidebar,
    balance_tab,
    expenses_tab,
    birthdays_tab,
    memo_tab,
    charts_tab,
)

__all__ = [
    "common",
    "sidebar",
    "balance_tab",
    "expenses_tab",
    "birthdays_tab",
    "memo_tab",
    "charts_tab",
]
