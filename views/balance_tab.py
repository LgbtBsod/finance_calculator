"""views/balance_tab.py — Вкладка «Баланс и ЗП».

Отображает: отпускные, начисления, расходы, остаток, мини-графики.
"""

from __future__ import annotations

import streamlit as st
from datetime import date

from calculator import BirthdayService, SalaryCalculator
from database import DatabaseManager
from prod_calendar import CalendarService

from models import BalanceResult, SalaryBreakdown

from .common import delete_buttons, fmt

__all__ = ["render_balance_tab"]


def render_balance_tab(
    db: DatabaseManager,
    cal_svc: CalendarService,
    sal_calc: SalaryCalculator,
    bd_svc: BirthdayService,
    sel_month: int,
    sel_year: int,
) -> None:
    # Авто-создание расходов по ДР-триггерам (один раз за сессию)
    _auto_birthday_expenses(db, bd_svc)

    # Отпускные
    _vacations_section(db, sel_month, sel_year)

    st.divider()

    # Карточки начислений
    cur_exps = db.get_expenses(sel_month, sel_year)
    bal = sal_calc.balance(sel_year, sel_month, cur_exps)
    s = bal.salary

    _accrual_cards(s)

    st.divider()

    # Расходы по половинам
    _expenses_summary(cur_exps, bal)

    st.divider()

    # Итоговый остаток
    _balance_metrics(bal)

    # Мини-графики
    st.divider()
    st.subheader("📊 Начисления vs Расходы")
    ch1, ch2 = st.columns(2)
    with ch1:
        _bar_comparison(s, bal)
    with ch2:
        _pie_salary(s)

    # Рабочие дни
    total, h1d, h2d = cal_svc.get_working_days(sel_year, sel_month)
    s_short = st.session_state.get("s_short", False)
    st.caption(
        f"📅 Рабочие дни: {total} | 1-я: {h1d} | 2-я: {h2d}"
        + (" (сокращённые учитываются)" if s_short else "")
    )


# ── Авто-расходы по ДР ──────────────────────────────────────


def _auto_birthday_expenses(
    db: DatabaseManager,
    bd_svc: BirthdayService,
) -> None:
    if not st.session_state.get("_bd_auto_done"):
        bds = db.get_birthdays()
        exps = db.get_expenses(date.today().month, date.today().year)
        cutoff = int(db.get_setting("advance_cutoff_day") or 15)
        created = bd_svc.auto_create_expenses(bds, exps, db.add_expense, cutoff)
        if created:
            st.cache_data.clear()
            st.rerun()
        st.session_state["_bd_auto_done"] = True


# ── Отпускные ────────────────────────────────────────────────


def _vacations_section(
    db: DatabaseManager,
    sel_month: int,
    sel_year: int,
) -> None:
    st.subheader("🏖️ Отпускные")
    with st.expander("Добавить отпускные", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            va = st.number_input(
                "Сумма (₽)", min_value=0.0, step=1000.0, format="%g", key="va"
            )
        with c2:
            vd = st.date_input(
                "Дата выплаты",
                value=date(sel_year, sel_month, 1),
                key="vd",
            )
        if st.button("Добавить", key="add_vac"):
            if va > 0:
                try:
                    db.add_vacation(va, vd.isoformat())
                except Exception as exc:
                    st.error(f"Ошибка добавления отпускных: {exc}")
                else:
                    st.cache_data.clear()
                    st.success("Добавлено!")
                    st.rerun()

    cur_vacs = db.get_vacations(sel_month, sel_year)
    if cur_vacs:
        import pandas as pd

        st.dataframe(
            pd.DataFrame(cur_vacs),
            use_container_width=True,
            hide_index=True,
        )
        delete_buttons(cur_vacs, "dv", db.delete_vacation)


# ── Карточки начислений ──────────────────────────────────────


def _accrual_cards(s: SalaryBreakdown) -> None:
    st.subheader("💳 Начисления")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Итого начислено",
            fmt(s.total_accrued),
            help="Чистая ЗП + Отпускные",
        )
    with c2:
        st.metric(
            "К выплате (1-я)",
            fmt(s.to_pay_half_1),
            help="Аванс + отпускные 1-й половины",
        )
    with c3:
        st.metric(
            "К выплате (2-я)",
            fmt(s.to_pay_half_2),
            help="Получка + отпускные 2-й половины",
        )

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**1-я половина:**")
        st.write(f"• Аванс: {fmt(s.advance)}")
        st.write(f"• Отпускные: {fmt(s.vacation_half_1)}")
    with d2:
        st.markdown("**2-я половина:**")
        st.write(f"• Получка: {fmt(s.payout)}")
        st.write(f"• Отпускные: {fmt(s.vacation_half_2)}")


# ── Расходы по половинам ─────────────────────────────────────


def _expenses_summary(cur_exps: list, bal: BalanceResult) -> None:
    st.subheader("📋 Расходы на месяц")
    ec1, ec2 = st.columns(2)

    h1_items = [e for e in cur_exps if e["half"] == 1]
    h2_items = [e for e in cur_exps if e["half"] == 2]

    with ec1:
        st.markdown("**1-я половина:**")
        for e in h1_items:
            st.write(f"• {e['name']}: {fmt(float(e['amount']))}")
        st.markdown(f"**Итого:** {fmt(bal.expenses_h1)}")
    with ec2:
        st.markdown("**2-я половина:**")
        for e in h2_items:
            st.write(f"• {e['name']}: {fmt(float(e['amount']))}")
        st.markdown(f"**Итого:** {fmt(bal.expenses_h2)}")


# ── Итоговый остаток ─────────────────────────────────────────


def _balance_metrics(bal: BalanceResult) -> None:
    st.subheader("📊 Итоговый остаток")
    b1, b2 = st.columns(2)
    with b1:
        icon = "🔴" if bal.balance_h1 < 0 else "🟢"
        st.metric(
            f"Остаток 1-я {icon}",
            fmt(bal.balance_h1),
            delta_color="inverse" if bal.balance_h1 < 0 else "normal",
        )
    with b2:
        icon = "🔴" if bal.balance_h2 < 0 else "🟢"
        st.metric(
            f"Остаток 2-я {icon}",
            fmt(bal.balance_h2),
            delta_color="inverse" if bal.balance_h2 < 0 else "normal",
        )


# ── Мини-графики ─────────────────────────────────────────────


def _bar_comparison(s: SalaryBreakdown, bal: BalanceResult) -> None:
    """Горизонтальная полоса: начисления vs расходы по половинам."""
    import pandas as pd

    data = pd.DataFrame(
        {
            "Период": ["1-я половина", "2-я половина"],
            "Начисления": [s.to_pay_half_1, s.to_pay_half_2],
            "Расходы": [bal.expenses_h1, bal.expenses_h2],
            "Остаток": [
                s.to_pay_half_1 - bal.expenses_h1,
                s.to_pay_half_2 - bal.expenses_h2,
            ],
        }
    )
    st.bar_chart(
        data=data,
        x="Период",
        color=["#4CAF50", "#FF5722", "#2196F3"],
        horizontal=False,
        use_container_width=True,
    )


def _pie_salary(s: SalaryBreakdown) -> None:
    """Столбчатая: Аванс vs Получка + Отпускные."""
    st.bar_chart(
        data={
            "Аванс": [s.advance],
            "Получка": [s.payout],
            "Отпускные": [s.vacation_half_1 + s.vacation_half_2],
        },
        color=["#2196F3", "#4CAF50", "#FFC107"],
        use_container_width=True,
    )
