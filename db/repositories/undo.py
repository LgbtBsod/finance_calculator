"""db.repositories.undo — обратимое удаление: снимок строки -> восстановление 1-в-1.

``_UNDO_TABLES`` перечисляет столбцы полностью, чтобы вставить строку обратно с
тем же id. Для долга дополнительно снимаются его погашения (каскад ON DELETE),
для расхода/дохода — переопределения суммы за месяц.
"""

from __future__ import annotations

from db.repositories.base import _Repo

# Таблицы, для которых удаление можно отменить: kind -> (таблица, столбцы).
# Столбцы перечислены полностью, чтобы восстановить строку 1-в-1 с тем же id.
_UNDO_TABLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "expense": ("expenses",
                ("id", "name", "amount", "half", "month", "year",
                 "is_recurring", "group_id", "recurring_until")),
    "income": ("income",
               ("id", "name", "amount", "half", "month", "year",
                "is_recurring", "recurring_until", "kind", "kef", "split_method",
                "first_half_ratio", "second_half_ratio")),
    "expense_group": ("expense_groups",
                      ("id", "name", "color", "parent_id", "sort_order", "monthly_limit")),
    "vacation": ("vacations",
                 ("id", "total_amount", "payout_date", "start_date", "end_date")),
    "birthday": ("birthdays", ("id", "name", "birth_date", "gift_amount")),
    "debt": ("debts",
             ("id", "title", "total_amount", "month", "year", "created_at",
              "monthly_payment", "payment_half")),
}


class UndoRepo(_Repo):
    def snapshot_for_undo(self, kind: str, row_id: int | str) -> dict | None:
        """Снимок строки перед удалением — плоский dict для отмены операции.
        Для долга дополнительно снимаются его погашения (каскад ON DELETE)."""
        table, cols = _UNDO_TABLES[kind]
        with self._tx() as c:
            row = c.execute(
                f"SELECT {', '.join(cols)} FROM {table} WHERE id=?", (row_id,)  # noqa: S608
            ).fetchone()
            if row is None:
                return None
            snap: dict = {"kind": kind, "row": dict(row)}
            if kind == "debt":
                snap["repayments"] = [
                    dict(r) for r in c.execute(
                        "SELECT id, debt_id, amount, date, note "
                        "FROM debt_repayments WHERE debt_id=?", (row_id,)
                    ).fetchall()
                ]
            if kind in ("expense", "income"):
                snap["overrides"] = [
                    dict(r) for r in c.execute(
                        "SELECT kind, row_id, year, month, amount FROM period_overrides "
                        "WHERE kind=? AND row_id=?", (kind, row_id)
                    ).fetchall()
                ]
        return snap

    def restore_from_undo(self, snapshot: dict) -> None:
        """Вставить обратно строку (и погашения долга) из снимка
        snapshot_for_undo. INSERT OR IGNORE — повторная отмена безопасна."""
        kind = snapshot["kind"]
        table, cols = _UNDO_TABLES[kind]
        row = snapshot["row"]
        placeholders = ", ".join(f":{col}" for col in cols)
        with self._tx() as c:
            c.execute(
                f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "  # noqa: S608
                f"VALUES ({placeholders})",
                {col: row.get(col) for col in cols},
            )
            for rp in snapshot.get("repayments", []):
                c.execute(
                    "INSERT OR IGNORE INTO debt_repayments (id, debt_id, amount, date, note) "
                    "VALUES (:id, :debt_id, :amount, :date, :note)", rp
                )
            for ov in snapshot.get("overrides", []):
                c.execute(
                    "INSERT OR IGNORE INTO period_overrides (kind, row_id, year, month, amount) "
                    "VALUES (:kind, :row_id, :year, :month, :amount)", ov
                )
