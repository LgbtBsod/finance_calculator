"""db.rows — чистые мапперы ``sqlite3.Row`` -> ``TypedDict`` из models.py.

Нулевого ввода-вывода: получают уже загруженную строку и приводят типы /
проставляют производные поля (``projected`` / ``overridden``) / при запросе
конкретного периода подменяют month/year на просматриваемый (кроме оклада).
"""

from __future__ import annotations

import sqlite3

from models import ExpenseRow, IncomeRow


def _apply_override(d: dict, override_amount: float | None) -> None:
    """Переопределение суммы на конкретный месяц (period_overrides)."""
    d["overridden"] = override_amount is not None
    if override_amount is not None:
        d["amount"] = override_amount


def _is_projected(row: dict, view_month: int | None, view_year: int | None) -> bool:
    """Строка спроецирована повторяющимся правилом, если запрошен конкретный
    период и он не совпадает с периодом создания строки."""
    return (
        bool(row.get("is_recurring"))
        and view_month is not None
        and view_year is not None
        and (row["month"], row["year"]) != (view_month, view_year)
    )


def expense_from_row(
    r: sqlite3.Row, *, view_month: int | None = None, view_year: int | None = None,
    override_amount: float | None = None,
) -> ExpenseRow:
    """sqlite3.Row → ExpenseRow с корректным типом is_recurring (bool).

    Если задан view_month/view_year (запрос конкретного периода в
    get_expenses), месяц/год в результате подменяются на запрошенный
    период — иначе спроецированный повторяющийся расход показывал бы
    месяц своего создания, а не месяц, на который он сейчас
    распространяется. override_amount (из period_overrides) заменяет сумму
    для этого месяца.
    """
    d = dict(r)
    d["is_recurring"] = bool(d["is_recurring"])
    # Убеждаемся, что group_id/recurring_until присутствуют
    if "group_id" not in d:
        d["group_id"] = None
    if "recurring_until" not in d:
        d["recurring_until"] = None
    d["projected"] = _is_projected(d, view_month, view_year)
    if view_month is not None and view_year is not None:
        d["month"] = view_month
        d["year"] = view_year
    _apply_override(d, override_amount)
    return ExpenseRow(**d)


def income_from_row(
    r: sqlite3.Row, *, view_month: int | None = None, view_year: int | None = None,
    override_amount: float | None = None,
) -> IncomeRow:
    """sqlite3.Row → IncomeRow (см. expense_from_row — та же логика проекции)."""
    d = dict(r)
    d["is_recurring"] = bool(d["is_recurring"])
    d.setdefault("recurring_until", None)
    d["projected"] = _is_projected(d, view_month, view_year)
    # Оклад (kind='salary') всегда показывает СВОЙ месяц «действует с» —
    # подмена на просматриваемый период тут только запутала бы.
    if d.get("kind") != "salary" and view_month is not None and view_year is not None:
        d["month"] = view_month
        d["year"] = view_year
    _apply_override(d, override_amount)
    return IncomeRow(**d)
