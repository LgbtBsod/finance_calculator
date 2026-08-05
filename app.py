"""app.py — Streamlit UI. Точка входа.

Архитектура:
  app.py       — page_config + инициализация + routing по вкладкам
  views/       — пакет UI-компонентов (SRP: один модуль = одна ответственность)
    common     — хелперы (fmt, delete_buttons, memo_card)
    sidebar    — боковая панель настроек
    balance_tab — вкладка «Баланс и ЗП»
    expenses_tab — вкладка «Расходы»
    birthdays_tab — вкладка «Дни рождения»
    memo_tab    — вкладка «Памятка»
    charts_tab — вкладка «Визуализация»

Зависимости:
  config        — константы
  database      — SQLite (единственный модуль знающий SQL)
  prod_calendar — производственный календарь (Strategy + Decorator)
  calculator    — бизнес-логика (ЗП, ДР, баланс)
  views         — UI-компоненты
"""

from __future__ import annotations

import streamlit as st
from datetime import date

from config import DB_FILENAME, MONTH_DISPLAY
from database import DatabaseManager
from prod_calendar import CalendarService
from calculator import BirthdayService, SalaryCalculator

from views import (
    balance_tab,
    birthdays_tab,
    charts_tab,
    expenses_tab,
    memo_tab,
    sidebar,
)

__all__ = []


# ═══════════════════════════════════════════════════════════════
#  ФАБРИКИ СЕРВИСОВ (кэшируются в рамках Streamlit-сессии)
# ═══════════════════════════════════════════════════════════════


@st.cache_resource
def init_db() -> DatabaseManager:
    return DatabaseManager(DB_FILENAME)


@st.cache_resource
def init_calendar_service(_db: DatabaseManager) -> CalendarService:
    svc = CalendarService(
        get_setting=_db.get_setting,
        set_setting=_db.set_setting,
        get_corrections=_db.get_corrections,
        save_corrections=_db.save_corrections,
        clear_calendar_cache=_db.clear_calendar_cache,
        calendar_needs_fill=_db.calendar_needs_fill,
        save_calendar_data=_db.save_calendar_data,
        get_calendar_month=_db.get_calendar_month,
    )
    # Предзаполнить календарь на текущий и соседние годы
    current_year = int(_db.get_setting("current_year") or date.today().year)
    for y in range(current_year - 1, current_year + 3):
        svc.build_and_cache_year(y)
    return svc


@st.cache_resource
def init_salary_calc(
    _db: DatabaseManager,
    cal_svc: CalendarService,
) -> SalaryCalculator:
    return SalaryCalculator(
        get_setting=_db.get_setting,
        calendar=cal_svc,
        vacations=_db,
    )


@st.cache_resource
def init_bd_service(_db: DatabaseManager) -> BirthdayService:
    return BirthdayService(get_setting=_db.get_setting)


# ═══════════════════════════════════════════════════════════════
#  MAIN — точка входа
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    st.set_page_config(
        page_title="Личный финансовый калькулятор",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Инициализация сервисов
    db = init_db()
    cal_svc = init_calendar_service(db)
    sal_calc = init_salary_calc(db, cal_svc)
    bd_svc = init_bd_service(db)

    # Sidebar (возвращает выбранный период)
    sel_month, sel_year = sidebar.render_sidebar(db, cal_svc)

    # Заголовок
    st.title("💰 Личный финансовый калькулятор")
    st.caption(f"Период: **{MONTH_DISPLAY[sel_month]} {sel_year}**")

    # Кэшируем календарь на выбранный год
    cal_svc.build_and_cache_year(sel_year)

    # Вкладки
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Баланс и ЗП",
        "💸 Расходы",
        "🎂 Дни рождения",
        "📝 Памятка",
        "📈 Визуализация",
    ])

    with tab1:
        balance_tab.render_balance_tab(
            db, cal_svc, sal_calc, bd_svc, sel_month, sel_year
        )
    with tab2:
        expenses_tab.render_expenses_tab(db, sel_month, sel_year)
    with tab3:
        birthdays_tab.render_birthdays_tab(db, bd_svc)
    with tab4:
        memo_tab.render_memo_tab(db)
    with tab5:
        charts_tab.render_charts_tab(db, sal_calc, sel_year)


if __name__ == "__main__":
    main()
