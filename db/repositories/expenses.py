"""db.repositories.expenses — таблица expenses + запись в period_overrides.

Проекция повторяющихся строк вперёд — общий с доходами SQL-фрагмент
``query.RECURRING_WHERE`` + наложение переопределений суммы за месяц
(``query.period_overrides``) + маппер ``rows.expense_from_row``.
"""

from __future__ import annotations

from db.query import _UNSET, RECURRING_WHERE, period_overrides
from db.repositories.base import _Repo
from db.rows import expense_from_row
from models import ExpenseRow


class ExpenseRepo(_Repo):
    def add_expense(
        self,
        name: str,
        amount: float,
        half: int,
        month: int,
        year: int,
        is_recurring: bool = False,
        group_id: str | None = None,
        recurring_until: str | None = None,
    ) -> int:
        with self._tx() as c:
            cursor = c.execute(
                "INSERT INTO expenses "
                "(name,amount,half,month,year,is_recurring,group_id,recurring_until) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (name, amount, half, month, year, int(is_recurring), group_id, recurring_until),
            )
            return cursor.lastrowid

    def get_expenses(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> list[ExpenseRow]:
        """Расходы за период.

        Без month/year — сырые строки как они есть в БД (используется
        режимом "за все периоды" в UI).

        С month/year — точное совпадение периода ПЛЮС спроецированные
        повторяющиеся расходы, чей период создания раньше запрошенного:
        повторяющийся расход не переносится в БД копией на каждый месяц,
        а автоматически "продолжается" вперёд, пока не наступит месяц
        recurring_until (включительно) — после него проекция прекращается.
        У спроецированных строк month/year в ответе подменяются на
        запрошенный период (см. expense_from_row) — иначе карточка расхода
        показывала бы месяц своего создания, а не месяц, на который она
        сейчас распространяется.
        """
        cols = ("id, name, amount, half, month, year, "
                "is_recurring, group_id, recurring_until")
        with self._tx() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    f"SELECT {cols} FROM expenses WHERE {RECURRING_WHERE} ORDER BY half, id",
                    {"month": month, "year": year},
                ).fetchall()
                ov = period_overrides(c, "expense", year, month)
                return [
                    expense_from_row(r, view_month=month, view_year=year,
                                     override_amount=ov.get(r["id"]))
                    for r in rows
                ]

            rows = c.execute(
                f"SELECT {cols} FROM expenses ORDER BY year, month, half, id"
            ).fetchall()
            return [expense_from_row(r) for r in rows]

    def set_period_override(self, kind: str, row_id: int, year: int,
                            month: int, amount: float) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO period_overrides (kind, row_id, year, month, amount) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(kind, row_id, year, month) DO UPDATE SET amount=excluded.amount",
                (kind, row_id, year, month, amount),
            )

    def clear_period_override(self, kind: str, row_id: int, year: int, month: int) -> None:
        with self._tx() as c:
            c.execute(
                "DELETE FROM period_overrides WHERE kind=? AND row_id=? AND year=? AND month=?",
                (kind, row_id, year, month),
            )

    def delete_expense(self, eid: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM expenses WHERE id=?", (eid,))
            c.execute("DELETE FROM period_overrides WHERE kind='expense' AND row_id=?", (eid,))

    def update_expense(
        self,
        eid: int,
        name: str | None = None,
        amount: float | None = None,
        half: int | None = None,
        is_recurring: bool | None = None,
        group_id: str | None | object = _UNSET,
        recurring_until: str | None | object = _UNSET,
    ) -> None:
        """Обновить расход с частичным обновлением полей (PATCH semantics).

        group_id/recurring_until — трёхзначные поля: значение по умолчанию
        `_UNSET` означает "не менять", а явно переданный `None` — "снять
        группу"/"снять дату завершения повторения" (отличить "не передали"
        от "передали пустое" обычным None-дефолтом нельзя, т.к. очистка —
        тоже None).
        """
        with self._tx() as c:
            # Получаем текущие значения
            current = c.execute(
                "SELECT name, amount, half, is_recurring, group_id, recurring_until "
                "FROM expenses WHERE id=?",
                (eid,),
            ).fetchone()

            if not current:
                raise ValueError(f"Expense with id {eid} not found")

            # Используем новые значения или оставляем старые
            new_name = name if name is not None else current["name"]
            new_amount = amount if amount is not None else current["amount"]
            new_half = half if half is not None else current["half"]
            new_is_recurring = (
                is_recurring if is_recurring is not None else bool(current["is_recurring"])
            )
            new_group_id = current["group_id"] if group_id is _UNSET else group_id
            new_recurring_until = (
                current["recurring_until"] if recurring_until is _UNSET else recurring_until
            )

            c.execute(
                "UPDATE expenses SET name=?, amount=?, half=?, is_recurring=?, "
                "group_id=?, recurring_until=? WHERE id=?",
                (
                    new_name,
                    new_amount,
                    new_half,
                    int(new_is_recurring),
                    new_group_id,
                    new_recurring_until,
                    eid,
                ),
            )
