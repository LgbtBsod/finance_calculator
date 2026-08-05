"""views/expenses_tab.py — Вкладка «Расходы».

CRUD расходов: добавление, таблица, удаление.
"""

from __future__ import annotations

import streamlit as st

from database import DatabaseManager

from .common import delete_buttons, fmt

__all__ = ["render_expenses_tab"]


def render_expenses_tab(
    db: DatabaseManager,
    sel_month: int,
    sel_year: int,
) -> None:
    st.subheader("➕ Добавить расход")
    with st.form("exp_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            en = st.text_input("Название", key="en")
        with c2:
            ea = st.number_input(
                "Сумма (₽)", value=0.0, min_value=0.0, step=100, format="%g", key="ea"
            )
        with c3:
            eh = st.selectbox(
                "Половина",
                [1, 2],
                format_func=lambda x: "1-я" if x == 1 else "2-я",
                key="eh",
            )
        er = st.checkbox("🔄 Повторять каждый месяц", key="er")
        if st.form_submit_button("Добавить"):
            if en and ea > 0:
                try:
                    db.add_expense(en, ea, eh, sel_month, sel_year, er)
                except Exception as exc:
                    st.error(f"Ошибка добавления расхода: {exc}")
                else:
                    st.cache_data.clear()
                    st.success(f"«{en}» добавлен!")
                    st.rerun()

    st.divider()
    st.subheader("📋 Таблица расходов")

    show_all = st.checkbox("Все месяцы", key="sa")
    all_e = (
        db.get_expenses(sel_month, sel_year)
        if not show_all
        else db.get_expenses()
    )

    if all_e:
        import pandas as pd

        df = pd.DataFrame(all_e)
        df["half"] = df["half"].apply(lambda x: "1-я" if x == 1 else "2-я")
        df["is_recurring"] = df["is_recurring"].apply(lambda x: "🔄" if x else "—")
        df["amount"] = df["amount"].apply(lambda x: fmt(float(x)))
        st.dataframe(df, use_container_width=True, hide_index=True)

        delete_buttons(all_e, "de", db.delete_expense)
    else:
        st.info("Нет расходов.")
