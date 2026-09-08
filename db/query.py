"""db.query — SQL-примитивы пакета без внешних зависимостей.

Единственное место, где определён ``_UNSET`` (сентинел трёхзначных PATCH-полей),
общий для расходов и доходов SQL-фрагмент проекции повторов и хелпер выборки
переопределений суммы за конкретный месяц. ``build_update`` (общий сборщик
partial-UPDATE) добавляется отдельной стадией.
"""

from __future__ import annotations

import sqlite3

# Сентинел для трёхзначных PATCH-полей: отличает "аргумент не передан"
# (оставить как есть) от "передан явный None" (очистить значение в БД).
_UNSET = object()

# Условие выборки за период с проекцией повторяющихся строк вперёд: точное
# совпадение периода ЛИБО повторяющаяся строка, созданная раньше и ещё не
# достигшая recurring_until. Общее для expenses и income (DRY).
RECURRING_WHERE = """
    (month = :month AND year = :year)
    OR (
        is_recurring = 1
        AND (year < :year OR (year = :year AND month < :month))
        AND (
            recurring_until IS NULL
            OR CAST(strftime('%Y', recurring_until) AS INTEGER) > :year
            OR (
                CAST(strftime('%Y', recurring_until) AS INTEGER) = :year
                AND CAST(strftime('%m', recurring_until) AS INTEGER) >= :month
            )
        )
    )
"""


def period_overrides(c: sqlite3.Connection, kind: str, year: int,
                     month: int) -> dict[int, float]:
    """row_id -> сумма-переопределение за (year, month) для строк вида ``kind``
    ('expense' | 'income'). Принимает уже открытый курсор — второй транзакции
    не открывает."""
    return {
        r["row_id"]: r["amount"]
        for r in c.execute(
            "SELECT row_id, amount FROM period_overrides "
            "WHERE kind=? AND year=? AND month=?", (kind, year, month)
        ).fetchall()
    }
