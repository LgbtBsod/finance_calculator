"""Прогноз погашения долга — чистые функции, без ядра и БД.

Перенесено из services.py: модулю modules/finance они нужны, а импортировать
фасад из модуля нельзя (модуль -> фасад = нарушение направления зависимостей).
Порт frontend/src/lib/debtProjection.ts.
"""

from __future__ import annotations

import calendar as _cal
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

__all__ = ["DebtProjection", "project_debt_payoff", "project_payoff_at_rate", "add_months"]


@dataclass(frozen=True, slots=True)
class DebtProjection:
    avg_monthly_rate: float
    months_to_payoff: int | None
    projected_date: date | None


def add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def project_debt_payoff(
    remaining_amount: float,
    repayments: list[dict[str, Any]],
    today: date | None = None,
) -> DebtProjection:
    """Темп = весь погашенный объём / число месяцев с первого платежа
    (включительно) — нерегулярные платежи честно дают более медленный темп."""
    today = today or date.today()
    if remaining_amount <= 0 or not repayments:
        return DebtProjection(0.0, None, None)

    dates = []
    for r in repayments:
        try:
            dates.append(date.fromisoformat(str(r["date"])[:10]))
        except (ValueError, KeyError, TypeError):
            continue
    if not dates:
        return DebtProjection(0.0, None, None)

    months_elapsed = max(1, _months_between(min(dates), today) + 1)
    total_repaid = sum(float(r["amount"]) for r in repayments)
    avg = total_repaid / months_elapsed
    if avg <= 0:
        return DebtProjection(avg, None, None)

    months = math.ceil(remaining_amount / avg)
    return DebtProjection(avg, months, add_months(today, months))


def project_payoff_at_rate(
    remaining_amount: float, monthly_rate: float, today: date | None = None
) -> date | None:
    today = today or date.today()
    if remaining_amount <= 0 or not (monthly_rate > 0):
        return None
    return add_months(today, math.ceil(remaining_amount / monthly_rate))
