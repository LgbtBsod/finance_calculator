"""db.query — SQL-примитивы пакета без внешних зависимостей.

Единственное место, где определён ``_UNSET`` (сентинел трёхзначных PATCH-полей),
общий для расходов и доходов SQL-фрагмент проекции повторов, хелпер выборки
переопределений суммы за месяц и ``build_update`` — общий сборщик частичного
UPDATE (что было размазано по нескольким ручным SET-конструкторам).
"""

from __future__ import annotations

import sqlite3
from typing import Any

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


def build_update(
    table: str, fields: dict[str, Any], where: dict[str, Any],
) -> tuple[str | None, list[Any]]:
    """Сборщик частичного UPDATE.

    ``fields``: ``{колонка: значение | _UNSET}`` — колонки со значением ``_UNSET``
    пропускаются; любое другое значение (включая ``None`` -> ``NULL``) пишется.
    ``where``: ``{колонка: значение}`` — AND-равенства (обычно ``{"id": row_id}``).

    Возвращает ``(sql, params)`` либо ``(None, [])``, когда менять нечего —
    вызывающий делает ранний ``return`` (как старое ``if not updates: return``).
    Порядок колонок в SET = порядок ключей ``fields`` (совпадает со старым
    ручным ``updates.append`` -> строка SQL идентична).
    """
    cols = [(c, v) for c, v in fields.items() if v is not _UNSET]
    if not cols:
        return None, []
    set_sql = ", ".join(f"{c}=?" for c, _ in cols)
    where_sql = " AND ".join(f"{c}=?" for c in where)
    sql = f"UPDATE {table} SET {set_sql} WHERE {where_sql}"  # noqa: S608 — идентификаторы литеральны
    return sql, [v for _, v in cols] + list(where.values())
