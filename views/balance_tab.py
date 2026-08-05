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
    
    # Карточки с улучшенным оформлением
    with c1:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#e3f2fd 0%,#bbdefb 100%);'
            f'padding:20px;border-radius:12px;text-align:center;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            f'<div style="color:#1976d2;font-size:0.9em;margin-bottom:8px;">'
            f'Итого начислено</div>'
            f'<div style="color:#0d47a1;font-size:1.8em;font-weight:bold;">'
            f'{fmt(s.total_accrued)}</div>'
            f'<div style="color:#666;font-size:0.8em;margin-top:8px;">'
            f'Чистая ЗП + Отпускные</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#e8f5e9 0%,#c8e6c9 100%);'
            f'padding:20px;border-radius:12px;text-align:center;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            f'<div style="color:#388e3c;font-size:0.9em;margin-bottom:8px;">'
            f'К выплате (1-я)</div>'
            f'<div style="color:#1b5e20;font-size:1.8em;font-weight:bold;">'
            f'{fmt(s.to_pay_half_1)}</div>'
            f'<div style="color:#666;font-size:0.8em;margin-top:8px;">'
            f'Аванс + отпускные 1-й</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#fff3e0 0%,#ffe0b2 100%);'
            f'padding:20px;border-radius:12px;text-align:center;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            f'<div style="color:#f57c00;font-size:0.9em;margin-bottom:8px;">'
            f'К выплате (2-я)</div>'
            f'<div style="color:#e65100;font-size:1.8em;font-weight:bold;">'
            f'{fmt(s.to_pay_half_2)}</div>'
            f'<div style="color:#666;font-size:0.8em;margin-top:8px;">'
            f'Получка + отпускные 2-й</div></div>',
            unsafe_allow_html=True,
        )

    # Детализация по половинам
    st.markdown("---")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown(
            f'<div style="background:#f8f9fa;padding:16px;border-radius:8px;'
            f'border-left:4px solid #2196F3;">'
            f'<strong style="color:#1976D2;font-size:1.1em;">1-я половина</strong><br>'
            f'<span style="color:#424242;">• Аванс:</span> <strong>{fmt(s.advance)}</strong><br>'
            f'<span style="color:#424242;">• Отпускные:</span> <strong>{fmt(s.vacation_half_1)}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with d2:
        st.markdown(
            f'<div style="background:#f8f9fa;padding:16px;border-radius:8px;'
            f'border-left:4px solid #FF9800;">'
            f'<strong style="color:#F57C00;font-size:1.1em;">2-я половина</strong><br>'
            f'<span style="color:#424242;">• Получка:</span> <strong>{fmt(s.payout)}</strong><br>'
            f'<span style="color:#424242;">• Отпускные:</span> <strong>{fmt(s.vacation_half_2)}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )


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
    
    # Определяем цвета и иконки в зависимости от баланса
    is_positive_h1 = bal.balance_h1 >= 0
    is_positive_h2 = bal.balance_h2 >= 0
    
    with b1:
        bg_color = "#e8f5e9" if is_positive_h1 else "#ffebee"
        text_color = "#2e7d32" if is_positive_h1 else "#c62828"
        icon = "✅" if is_positive_h1 else "⚠️"
        label = "Положительный остаток (1-я)" if is_positive_h1 else "Дефицит (1-я)"
        
        st.markdown(
            f'<div style="background:{bg_color};padding:24px;border-radius:12px;'
            f'text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            f'<div style="font-size:2em;margin-bottom:8px;">{icon}</div>'
            f'<div style="color:#666;font-size:0.9em;margin-bottom:8px;">{label}</div>'
            f'<div style="color:{text_color};font-size:2em;font-weight:bold;">'
            f'{fmt(bal.balance_h1)}</div></div>',
            unsafe_allow_html=True,
        )
    
    with b2:
        bg_color = "#e8f5e9" if is_positive_h2 else "#ffebee"
        text_color = "#2e7d32" if is_positive_h2 else "#c62828"
        icon = "✅" if is_positive_h2 else "⚠️"
        label = "Положительный остаток (2-я)" if is_positive_h2 else "Дефицит (2-я)"
        
        st.markdown(
            f'<div style="background:{bg_color};padding:24px;border-radius:12px;'
            f'text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            f'<div style="font-size:2em;margin-bottom:8px;">{icon}</div>'
            f'<div style="color:#666;font-size:0.9em;margin-bottom:8px;">{label}</div>'
            f'<div style="color:{text_color};font-size:2em;font-weight:bold;">'
            f'{fmt(bal.balance_h2)}</div></div>',
            unsafe_allow_html=True,
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
