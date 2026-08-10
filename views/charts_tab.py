"""views/charts_tab.py — Вкладка «Визуализация».

Годовые графики: зарплата, расходы, остатки с использованием Plotly.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from calculator import SalaryCalculator
from config import MONTH_DISPLAY
from database import DatabaseManager

__all__ = ["render_charts_tab"]


def render_charts_tab(
    db: DatabaseManager,
    sal_calc: SalaryCalculator,
    sel_year: int,
) -> None:
    # Выбор типа визуализации
    chart_type = st.radio(
        "Тип графиков:",
        options=["plotly_interactive", "streamlit_native"],
        format_func=lambda x: "🔹 Интерактивные (Plotly)" if x == "plotly_interactive" else "📊 Стандартные (Streamlit)",
        horizontal=True,
        label_visibility="collapsed"
    )
    
    use_plotly = chart_type == "plotly_interactive"
    
    st.subheader("📊 Распределение зарплаты по месяцам")
    _year_salary_chart(sal_calc, sel_year, use_plotly)

    st.divider()
    st.subheader("💸 Расходы по месяцам")
    _year_expenses_chart(db, sel_year, use_plotly)

    st.divider()
    st.subheader("📈 Динамика остатков")
    _balance_trend_chart(db, sal_calc, sel_year, use_plotly)
    
    st.divider()
    st.subheader("📊 Сводная диаграмма: Зарплата vs Расходы")
    _salary_vs_expenses_chart(db, sal_calc, sel_year, use_plotly)


# ── Зарплата за год ─────────────────────────────────────────


def _year_salary_chart(sal_calc: SalaryCalculator, year: int, use_plotly: bool = True) -> None:
    months = [MONTH_DISPLAY[m] for m in range(1, 13)]
    data = {
        "Месяц": months,
        "Чистая ЗП": [sal_calc.calculate(year, m).net_salary for m in range(1, 13)],
        "Аванс": [sal_calc.calculate(year, m).advance for m in range(1, 13)],
        "Получка": [sal_calc.calculate(year, m).payout for m in range(1, 13)],
    }
    
    if use_plotly:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=data["Чистая ЗП"], name="Чистая ЗП", line=dict(color="#4CAF50", width=3)))
        fig.add_trace(go.Bar(x=months, y=data["Аванс"], name="Аванс", marker_color="#2196F3"))
        fig.add_trace(go.Bar(x=months, y=data["Получка"], name="Получка", marker_color="#FF9800"))
        fig.update_layout(
            title="Распределение зарплаты по месяцам",
            xaxis_title="Месяц",
            yaxis_title="Сумма (₽)",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(
            data={"Чистая ЗП": data["Чистая ЗП"], "Аванс": data["Аванс"], "Получка": data["Получка"]},
            x=months,
            use_container_width=True,
        )


# ── Расходы за год ──────────────────────────────────────────


def _year_expenses_chart(db: DatabaseManager, year: int, use_plotly: bool = True) -> None:
    months = [MONTH_DISPLAY[m] for m in range(1, 13)]
    h1_total = []
    h2_total = []
    for m in range(1, 13):
        exps = db.get_expenses(m, year)
        h1_total.append(sum(float(e["amount"]) for e in exps if e["half"] == 1))
        h2_total.append(sum(float(e["amount"]) for e in exps if e["half"] == 2))
    
    if use_plotly:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=months, y=h1_total, name="1-я половина", marker_color="#2196F3"))
        fig.add_trace(go.Bar(x=months, y=h2_total, name="2-я половина", marker_color="#FF9800"))
        fig.update_layout(
            title="Расходы по месяцам",
            xaxis_title="Месяц",
            yaxis_title="Сумма (₽)",
            barmode="group",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(
            data={"1-я половина": h1_total, "2-я половина": h2_total},
            x=months,
            color=["#2196F3", "#FF9800"],
            use_container_width=True,
            stack=False,
        )


# ── Динамика остатков ───────────────────────────────────────


def _balance_trend_chart(
    db: DatabaseManager, sal_calc: SalaryCalculator, year: int, use_plotly: bool = True
) -> None:
    months = [MONTH_DISPLAY[m] for m in range(1, 13)]
    b1_data = []
    b2_data = []
    for m in range(1, 13):
        exps = db.get_expenses(m, year)
        r = sal_calc.balance(year, m, exps)
        b1_data.append(r.balance_h1)
        b2_data.append(r.balance_h2)
    
    if use_plotly:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=b1_data, name="1-я половина", line=dict(color="#4CAF50", width=3, shape="spline")))
        fig.add_trace(go.Scatter(x=months, y=b2_data, name="2-я половина", line=dict(color="#F44336", width=3, shape="spline")))
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.update_layout(
            title="Динамика остатков по месяцам",
            xaxis_title="Месяц",
            yaxis_title="Остаток (₽)",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(
            data={"1-я половина": b1_data, "2-я половина": b2_data},
            x=months,
            use_container_width=True,
        )


# ── Сводная диаграмма: Зарплата vs Расходы ──────────────────


def _salary_vs_expenses_chart(
    db: DatabaseManager, sal_calc: SalaryCalculator, year: int, use_plotly: bool = True
) -> None:
    """Показывает соотношение доходов и расходов по месяцам."""
    months = [MONTH_DISPLAY[m] for m in range(1, 13)]
    income = []
    expenses = []
    balance = []
    
    for m in range(1, 13):
        exps = db.get_expenses(m, year)
        r = sal_calc.balance(year, m, exps)
        total_income = r.salary.total_accrued
        total_expenses = r.expenses_h1 + r.expenses_h2
        income.append(total_income)
        expenses.append(total_expenses)
        balance.append(total_income - total_expenses)
    
    if use_plotly:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05)
        
        # Верхний график: доходы и расходы
        fig.add_trace(go.Bar(x=months, y=income, name="Доходы", marker_color="#4CAF50"), row=1, col=1)
        fig.add_trace(go.Bar(x=months, y=expenses, name="Расходы", marker_color="#F44336"), row=1, col=1)
        
        # Нижний график: баланс
        colors = ["#4CAF50" if b >= 0 else "#F44336" for b in balance]
        fig.add_trace(go.Bar(x=months, y=balance, name="Баланс", marker_color=colors), row=2, col=1)
        
        fig.update_layout(
            height=600,
            title="Сводная диаграмма: Доходы vs Расходы vs Баланс",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig.update_xaxes(title_text="Месяц", row=2, col=1)
        fig.update_yaxes(title_text="Сумма (₽)", row=1, col=1)
        fig.update_yaxes(title_text="Баланс (₽)", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        df = pd.DataFrame({
            "Месяц": months,
            "Доходы": income,
            "Расходы": expenses,
            "Баланс": balance
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
