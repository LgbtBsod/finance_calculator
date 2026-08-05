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
    # Заголовок с улучшенным оформлением
    st.markdown(
        '<div style="background:linear-gradient(135deg,#fce4ec 0%,#f8bbd9 100%);'
        'padding:20px;border-radius:12px;margin-bottom:20px;">'
        '<h2 style="color:#880e4f;margin:0;">🎂 Дни рождения</h2>'
        '</div>',
        unsafe_allow_html=True,
    )
    
    st.subheader("➕ Добавить день рождения")
    with st.form("bd_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            bn = st.text_input("Имя", placeholder="Например: Иван", key="bn")
        with c2:
            bdt = st.text_input("Дата (ДД.ММ)", placeholder="15.06", key="bdt")
        with c3:
            ba = st.number_input(
                "Сумма подарка (₽)",
                min_value=0.0,
                step=500.0,
                value=0.0,
                format="%g",
                key="ba",
            )
        
        submit_col = st.columns([3, 1])
        with submit_col[0]:
            submitted = st.form_submit_button(
                "✅ Добавить ДР",
                use_container_width=True,
            )
        
        if submitted:
            if not bn:
                st.warning("⚠️ Введите имя")
            elif not bdt:
                st.warning("⚠️ Введите дату в формате ДД.ММ")
            elif ba <= 0:
                st.warning("⚠️ Сумма подарка должна быть больше нуля")
            else:
                try:
                    db.add_birthday(bn, bdt, ba)
                except Exception as exc:
                    st.error(f"Ошибка добавления ДР: {exc}")
                else:
                    st.cache_data.clear()
                    st.success(f"✅ «{bn}» добавлен!")
                    st.rerun()

    st.divider()
    st.subheader("📋 Все дни рождения")
    all_bd = db.get_birthdays()
    if all_bd:
        import pandas as pd

        df = pd.DataFrame(all_bd)
        df_display = df.rename(columns={
            "name": "Имя",
            "birth_date": "Дата",
            "gift_amount": "Сумма"
        })
        df_display["Сумма"] = df_display["Сумма"].apply(lambda x: fmt(float(x)))
        
        st.dataframe(
            df_display[["Имя", "Дата", "Сумма"]],
            use_container_width=True,
            hide_index=True,
        )
        
        # Кнопки удаления
        st.markdown("### 🗑️ Удаление")
        cols = st.columns(min(len(all_bd), 4))
        for idx, item in enumerate(all_bd):
            col_idx = idx % len(cols)
            with cols[col_idx]:
                if st.button(
                    f"🗑️ {item['name'][:12]}",
                    key=f"db_{item['id']}",
                    help=f"Удалить: {item['name']} ({item['birth_date']})",
                    use_container_width=True,
                ):
                    try:
                        db.delete_birthday(item["id"])
                    except Exception as exc:
                        st.error(f"Ошибка при удалении: {exc}")
                    else:
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.info("💡 Нет записей о днях рождения. Добавьте первую запись выше!")

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
