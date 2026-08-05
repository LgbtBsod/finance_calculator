"""views/charts_tab.py — Вкладка «Визуализация».

Годовые графики: зарплата, расходы, остатки.
"""

from __future__ import annotations

import streamlit as st

from calculator import SalaryCalculator
from config import MONTH_DISPLAY
from database import DatabaseManager

__all__ = ["render_charts_tab"]


def render_charts_tab(
    db: DatabaseManager,
    sal_calc: SalaryCalculator,
    sel_year: int,
) -> None:
    st.subheader("📊 Распределение зарплаты по месяцам")
    _year_salary_chart(sal_calc, sel_year)

    st.divider()
    st.subheader("📊 Расходы по месяцам")
    _year_expenses_chart(db, sel_year)

    st.divider()
    st.subheader("📊 Динамика остатков")
    _balance_trend_chart(db, sal_calc, sel_year)


# ── Зарплата за год ─────────────────────────────────────────


def _year_salary_chart(sal_calc: SalaryCalculator, year: int) -> None:
    import pandas as pd

    months: list[str] = []
    net: list[float] = []
    adv: list[float] = []
    pay: list[float] = []
    for m in range(1, 13):
        r = sal_calc.calculate(year, m)
        months.append(MONTH_DISPLAY[m])
        net.append(r.net_salary)
        adv.append(r.advance)
        pay.append(r.payout)

    df = pd.DataFrame(
        {"Месяц": months, "Чистая ЗП": net, "Аванс": adv, "Получка": pay}
    )
    st.line_chart(df.set_index("Месяц"), use_container_width=True)


# ── Расходы за год ──────────────────────────────────────────


def _year_expenses_chart(db: DatabaseManager, year: int) -> None:
    import pandas as pd

    months: list[str] = []
    h1_total: list[float] = []
    h2_total: list[float] = []
    for m in range(1, 13):
        exps = db.get_expenses(m, year)
        months.append(MONTH_DISPLAY[m])
        h1_total.append(
            sum(float(e["amount"]) for e in exps if e["half"] == 1)
        )
        h2_total.append(
            sum(float(e["amount"]) for e in exps if e["half"] == 2)
        )

    df = pd.DataFrame(
        {"Месяц": months, "1-я половина": h1_total, "2-я половина": h2_total}
    )
    st.bar_chart(
        df.set_index("Месяц"),
        color=["#2196F3", "#FF9800"],
        use_container_width=True,
        stack=False,
    )


# ── Динамика остатков ───────────────────────────────────────


def _balance_trend_chart(
    db: DatabaseManager, sal_calc: SalaryCalculator, year: int
) -> None:
    import pandas as pd

    months: list[str] = []
    b1_data: list[float] = []
    b2_data: list[float] = []
    for m in range(1, 13):
        exps = db.get_expenses(m, year)
        r = sal_calc.balance(year, m, exps)
        months.append(MONTH_DISPLAY[m])
        b1_data.append(r.balance_h1)
        b2_data.append(r.balance_h2)

    df = pd.DataFrame(
        {"Месяц": months, "1-я половина": b1_data, "2-я половина": b2_data}
    )
    st.line_chart(df.set_index("Месяц"), use_container_width=True)
