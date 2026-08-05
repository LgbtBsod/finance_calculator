"""views/memo_tab.py — Вкладка «Памятка».

Свободные расходы / долги / обязательства. Не влияют на баланс ЗП.
"""

from __future__ import annotations

import streamlit as st
from datetime import date

from database import DatabaseManager

from .common import delete_buttons, fmt, memo_card

__all__ = ["render_memo_tab"]


def render_memo_tab(db: DatabaseManager) -> None:
    st.info(
        "📌 **Памятка** — свободные расходы / долги / обязательства. "
        "**Не вычитаются** из баланса зарплаты."
    )

    st.subheader("➕ Добавить")
    with st.form("memo_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            mn = st.text_input("Кому / за что", key="mn")
        with c2:
            ma = st.number_input(
                "Сумма (₽)", min_value=0.0, step=100, format="%g", key="ma"
            )
        with c3:
            md = st.date_input("Дата", value=date.today(), key="md")
        if st.form_submit_button("Добавить"):
            if mn and ma > 0:
                try:
                    db.add_memo_expense(mn, ma, md.isoformat())
                except Exception as exc:
                    st.error(f"Ошибка добавления: {exc}")
                else:
                    st.cache_data.clear()
                    st.success("Добавлено!")
                    st.rerun()

    st.divider()
    _memo_list(db)


# ── Список обязательств ──────────────────────────────────────


def _memo_list(db: DatabaseManager) -> None:
    st.subheader("📋 Список обязательств")
    all_m = db.get_memo_expenses()
    if not all_m:
        st.info("Пусто.")
        return

    total = sum(float(m["amount"]) for m in all_m)
    st.metric("Общая сумма памятки", fmt(total))

    for m in all_m:
        try:
            td = date.fromisoformat(m["target_date"])
            ds = td.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            ds = str(m.get("target_date", ""))
        memo_card(m["name"], float(m["amount"]), ds)

    delete_buttons(all_m, "dm", db.delete_memo_expense)
