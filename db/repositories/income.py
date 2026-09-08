"""db.repositories.income — таблица income (доходы: зеркало expenses без групп).

kind='fixed' — разовая/повторяющаяся сумма (в баланс как «прочий доход»);
kind='salary' — оклад, считается SalaryCalculator (amount = оклад/мес + kef/
метод/пропорции на самой строке).
"""

from __future__ import annotations

from db.query import _UNSET, RECURRING_WHERE, period_overrides
from db.repositories.base import _Repo
from db.rows import income_from_row
from models import IncomeRow


class IncomeRepo(_Repo):
    _INCOME_COLS = ("id, name, amount, half, month, year, is_recurring, recurring_until, "
                    "kind, kef, split_method, first_half_ratio, second_half_ratio")

    def add_income(
        self, name: str, amount: float, half: int, month: int, year: int,
        is_recurring: bool = False, recurring_until: str | None = None,
        kind: str = "fixed", kef: float | None = None, split_method: str | None = None,
        first_half_ratio: float | None = None, second_half_ratio: float | None = None,
    ) -> int:
        with self._tx() as c:
            cursor = c.execute(
                "INSERT INTO income (name, amount, half, month, year, is_recurring, "
                "recurring_until, kind, kef, split_method, first_half_ratio, second_half_ratio) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (name, amount, half, month, year, int(is_recurring), recurring_until,
                 kind, kef, split_method, first_half_ratio, second_half_ratio),
            )
            return cursor.lastrowid

    def get_income(
        self, month: int | None = None, year: int | None = None
    ) -> list[IncomeRow]:
        """Доходы за период — та же проекция повторяющихся строк вперёд, что и
        у расходов (см. get_expenses)."""
        cols = self._INCOME_COLS
        with self._tx() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    f"SELECT {cols} FROM income WHERE {RECURRING_WHERE} ORDER BY half, id",
                    {"month": month, "year": year},
                ).fetchall()
                ov = period_overrides(c, "income", year, month)
                return [
                    income_from_row(r, view_month=month, view_year=year,
                                    override_amount=ov.get(r["id"]))
                    for r in rows
                ]
            rows = c.execute(
                f"SELECT {cols} FROM income ORDER BY year, month, half, id"
            ).fetchall()
            return [income_from_row(r) for r in rows]

    def delete_income(self, iid: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM period_overrides WHERE kind='income' AND row_id=?", (iid,))
            c.execute("DELETE FROM income WHERE id=?", (iid,))

    def update_income(
        self, iid: int, name: str | None = None, amount: float | None = None,
        half: int | None = None, is_recurring: bool | None = None,
        recurring_until: str | None | object = _UNSET,
        kef: float | None = None, split_method: str | None = None,
        first_half_ratio: float | None = None, second_half_ratio: float | None = None,
    ) -> None:
        with self._tx() as c:
            cur = c.execute(
                "SELECT name, amount, half, is_recurring, recurring_until, "
                "kef, split_method, first_half_ratio, second_half_ratio "
                "FROM income WHERE id=?", (iid,),
            ).fetchone()
            if not cur:
                raise ValueError(f"Income with id {iid} not found")

            def _keep(new, key):
                return new if new is not None else cur[key]

            c.execute(
                "UPDATE income SET name=?, amount=?, half=?, is_recurring=?, recurring_until=?, "
                "kef=?, split_method=?, first_half_ratio=?, second_half_ratio=? WHERE id=?",
                (
                    _keep(name, "name"), _keep(amount, "amount"), _keep(half, "half"),
                    int(is_recurring if is_recurring is not None else bool(cur["is_recurring"])),
                    cur["recurring_until"] if recurring_until is _UNSET else recurring_until,
                    _keep(kef, "kef"), _keep(split_method, "split_method"),
                    _keep(first_half_ratio, "first_half_ratio"),
                    _keep(second_half_ratio, "second_half_ratio"),
                    iid,
                ),
            )
