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
    # Заголовок с улучшенным оформлением
    st.markdown(
        '<div style="background:linear-gradient(135deg,#f5f7fa 0%,#e4e8eb 100%);'
        'padding:20px;border-radius:12px;margin-bottom:20px;">'
        '<h2 style="color:#2c3e50;margin:0;">➕ Добавить расход</h2>'
        '</div>',
        unsafe_allow_html=True,
    )
    
    with st.form("exp_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            en = st.text_input("Название", placeholder="Например: Аренда", key="en")
        with c2:
            ea = st.number_input(
                "Сумма (₽)", min_value=0.0, step=100.0, format="%g", key="ea"
            )
        with c3:
            eh = st.selectbox(
                "Половина месяца",
                [1, 2],
                format_func=lambda x: "📅 1-я половина" if x == 1 else "📅 2-я половина",
                key="eh",
            )
        er = st.checkbox("🔄 Повторять каждый месяц", key="er")
        
        submit_col = st.columns([3, 1])
        with submit_col[0]:
            submitted = st.form_submit_button(
                "✅ Добавить расход",
                use_container_width=True,
            )
        
        if submitted:
            if not en:
                st.warning("⚠️ Введите название расхода")
            elif ea <= 0:
                st.warning("⚠️ Сумма должна быть больше нуля")
            else:
                try:
                    db.add_expense(en, ea, eh, sel_month, sel_year, er)
                except Exception as exc:
                    st.error(f"Ошибка добавления расхода: {exc}")
                else:
                    st.cache_data.clear()
                    st.success(f"✅ «{en}» добавлен!")
                    st.rerun()

    st.divider()
    st.subheader("📋 Таблица расходов")

    show_all = st.checkbox("Показать все месяцы", key="sa")
    all_e = (
        db.get_expenses(sel_month, sel_year)
        if not show_all
        else db.get_expenses()
    )

    if all_e:
        import pandas as pd

        df = pd.DataFrame(all_e)
        df["half"] = df["half"].apply(lambda x: "1-я" if x == 1 else "2-я")
        df["is_recurring"] = df["is_recurring"].apply(lambda x: "🔄" if x else "")
        df["amount_fmt"] = df["amount"].apply(lambda x: fmt(float(x)))
        
        # Переименовываем колонки для отображения
        display_df = df.rename(columns={
            "name": "Название",
            "amount_fmt": "Сумма",
            "half": "Половина",
            "is_recurring": "Повтор",
            "month": "Месяц",
            "year": "Год"
        })
        
        if not show_all:
            display_df = display_df[["Название", "Сумма", "Половина", "Повтор"]]
        else:
            display_df = display_df[["Название", "Сумма", "Половина", "Месяц", "Год", "Повтор"]]
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Сумма": st.column_config.TextColumn(width="medium"),
                "Половина": st.column_config.TextColumn(width="small"),
                "Повтор": st.column_config.TextColumn(width="small"),
            }
        )

        # Кнопки удаления в строку
        st.markdown("### 🗑️ Удаление расходов")
        cols = st.columns(min(len(all_e), 5))
        for idx, item in enumerate(all_e):
            col_idx = idx % len(cols)
            with cols[col_idx]:
                if st.button(
                    f"🗑️ {item['name'][:15]}...",
                    key=f"de_{item['id']}",
                    help=f"Удалить: {item['name']} ({fmt(float(item['amount']))})",
                    use_container_width=True,
                ):
                    try:
                        db.delete_expense(item["id"])
                    except Exception as exc:
                        st.error(f"Ошибка при удалении: {exc}")
                    else:
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.info("💡 Нет расходов. Добавьте первый расход выше!")
