"""views/birthdays_tab.py — Вкладка «Дни рождения».

CRUD дней рождений + отображение ближайших триггеров.
"""

from __future__ import annotations

import streamlit as st

from calculator import BirthdayService
from database import DatabaseManager

from .common import delete_buttons, fmt

__all__ = ["render_birthdays_tab"]


def render_birthdays_tab(
    db: DatabaseManager,
    bd_svc: BirthdayService,
) -> None:
    st.subheader("🎂 Добавить день рождения")
    with st.form("bd_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            bn = st.text_input("Имя", key="bn")
        with c2:
            bdt = st.text_input("Дата (ДД.ММ)", placeholder="01.01", key="bdt")
        with c3:
            ba = st.number_input(
                "Сумма подарка (₽)",
                min_value=0.0,
                step=100,
                format="%g",
                key="ba",
            )
        if st.form_submit_button("Добавить ДР"):
            if bn and bdt and ba > 0:
                try:
                    db.add_birthday(bn, bdt, ba)
                except Exception as exc:
                    st.error(f"Ошибка добавления ДР: {exc}")
                else:
                    st.cache_data.clear()
                    st.success(f"«{bn}» добавлен!")
                    st.rerun()

    st.divider()
    st.subheader("📋 Все дни рождения")
    all_bd = db.get_birthdays()
    if all_bd:
        import pandas as pd

        st.dataframe(
            pd.DataFrame(all_bd), use_container_width=True, hide_index=True
        )
        delete_buttons(all_bd, "db", db.delete_birthday)
    else:
        st.info("Нет записей.")

    st.divider()
    _upcoming_alerts(bd_svc, all_bd)


# ── Ближайшие триггеры ──────────────────────────────────────


def _upcoming_alerts(
    bd_svc: BirthdayService,
    all_bd: list[dict],
) -> None:
    st.subheader("⚠️ Ближайшие ДР (30 дней)")
    alerts = bd_svc.upcoming(all_bd, days_ahead=30)
    if alerts:
        for a in alerts:
            st.warning(
                f"🎂 **{a.name}** — ДР {a.birth_date} | "
                f"📅 Триггер {a.trigger_date:%d.%m.%Y} "
                f"(через {a.days_until} дн.) | "
                f"💰 {fmt(a.gift_amount)}",
                icon="⚠️",
            )
    else:
        st.success("В ближайшие 30 дней нет ДР!")
