"""db.repositories.debts — таблицы debts + debt_repayments.

``get_debts`` грузит все погашения одним запросом и считает
``repaid_amount`` / ``remaining_amount`` в Python (без коррелированного
подзапроса).
"""

from __future__ import annotations

from db.query import _UNSET, build_update
from db.repositories.base import _Repo


class DebtRepo(_Repo):
    def create_debt(
        self,
        title: str,
        total_amount: float,
        month: int,
        year: int,
        monthly_payment: float = 0.0,
        payment_half: int = 2,
    ) -> int:
        with self._tx() as c:
            cursor = c.execute(
                "INSERT INTO debts "
                "(title, total_amount, month, year, created_at, monthly_payment, payment_half) "
                "VALUES (?, ?, ?, ?, datetime('now'), ?, ?)",
                (title, total_amount, month, year, monthly_payment, payment_half),
            )
            return cursor.lastrowid

    def update_debt(
        self, debt_id: int, *, title: str | None = None, total_amount: float | None = None,
        monthly_payment: float | None = None, payment_half: int | None = None,
    ) -> None:
        sql, params = build_update("debts", {
            "title": title if title is not None else _UNSET,
            "total_amount": total_amount if total_amount is not None else _UNSET,
            "monthly_payment": monthly_payment if monthly_payment is not None else _UNSET,
            "payment_half": payment_half if payment_half is not None else _UNSET,
        }, {"id": debt_id})
        if sql is None:
            return
        with self._tx() as c:
            c.execute(sql, params)

    def get_debts(self) -> list[dict]:
        with self._tx() as c:
            rows = c.execute(
                "SELECT id, title, total_amount, month, year, created_at, "
                "monthly_payment, payment_half FROM debts ORDER BY year, month, created_at"
            ).fetchall()
            # Один запрос всех погашений, группируем в Python по debt_id —
            # и repaid_amount считаем отсюда же (без коррелированного подзапроса).
            repayments_by_debt: dict[int, list[dict]] = {}
            for r in c.execute(
                "SELECT id, debt_id, amount, date, note FROM debt_repayments ORDER BY date"
            ).fetchall():
                repayments_by_debt.setdefault(r["debt_id"], []).append(dict(r))

            debts = []
            for row in rows:
                debt = dict(row)
                reps = repayments_by_debt.get(debt["id"], [])
                debt["repaid_amount"] = sum(r["amount"] for r in reps)
                debt["remaining_amount"] = max(0.0, debt["total_amount"] - debt["repaid_amount"])
                debt["repayments"] = reps
                debts.append(debt)
            return debts

    def delete_debt(self, debt_id: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM debts WHERE id=?", (debt_id,))

    def add_debt_repayment(
        self,
        debt_id: int,
        amount: float,
        date: str,
        note: str | None = None,
    ) -> int:
        with self._tx() as c:
            cursor = c.execute(
                "INSERT INTO debt_repayments (debt_id, amount, date, note) VALUES (?, ?, ?, ?)",
                (debt_id, amount, date, note),
            )
            return cursor.lastrowid

    def delete_debt_repayment(self, repayment_id: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM debt_repayments WHERE id=?", (repayment_id,))
