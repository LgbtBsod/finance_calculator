"""DBModule — обёртка над database.DatabaseManager.

ЕДИНСТВЕННЫЙ модуль, знающий про SQL. После каждой записи шлёт
``db:changed`` (entity=...) — ядро диспатчит это событие после раскрутки
верхнеуровневого request, вне открытой транзакции.
"""

from __future__ import annotations

from typing import Any

from core.errors import ValidationError
from core.module import Module
from database import DatabaseManager

# Тонкие read-действия: имя action -> имя метода DatabaseManager (просто проброс).
_READS = {
    "get_setting": "get_setting",
    "get_settings_bundle": "get_settings_bundle",
    "get_expenses": "get_expenses",
    "get_expense_groups": "get_expense_groups",
    "get_expense_group": "get_expense_group",
    "get_vacations": "get_vacations",
    "get_birthdays": "get_birthdays",
    "get_debts": "get_debts",
    "get_corrections": "get_corrections",
    "calendar_needs_fill": "calendar_needs_fill",
    "get_calendar_month": "get_calendar_month",
}


class DBModule(Module):
    name = "db"

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self._db_path = db_path
        self.db: DatabaseManager | None = None

    def initialize(self) -> None:
        self.db = DatabaseManager(self._db_path)
        self._actions = {
            # reads
            **{a: (lambda m: lambda **kw: getattr(self.db, m)(**kw))(meth)
               for a, meth in _READS.items()},
            # settings write
            "set_setting": self._set_setting,
            # expenses
            "add_expense": self._add_expense,
            "update_expense": self._update_expense,
            "delete_expense": self._delete_expense,
            # expense groups
            "create_expense_group": self._create_group,
            "update_expense_group": self._update_group,
            "delete_expense_group": self._delete_group,
            # vacations
            "add_vacation": self._add_vacation,
            "delete_vacation": self._delete_vacation,
            # birthdays
            "add_birthday": self._add_birthday,
            "update_birthday": self._update_birthday,
            "delete_birthday": self._delete_birthday,
            # debts
            "create_debt": self._create_debt,
            "delete_debt": self._delete_debt,
            "add_debt_repayment": self._add_repayment,
            "delete_debt_repayment": self._delete_repayment,
            # calendar cache (пишет только calendar-модуль)
            "save_calendar_data": self._save_calendar_data,
            "clear_calendar_cache": self._clear_calendar_cache,
            "save_corrections": self._save_corrections,
            # backup
            "backup_to": self._backup_to,
            "db_path": lambda: self._db_path,
        }

    def shutdown(self) -> None:
        if self.db is not None:
            self.db.close()

    # ── settings ─────────────────────────────────────────────

    def _set_setting(self, key: str, value: Any) -> None:
        self.db.set_setting(key, str(value))
        self._changed("settings")

    # ── expenses ─────────────────────────────────────────────

    def _add_expense(self, **kw: Any) -> dict:
        new_id = self.db.add_expense(**kw)
        self._changed("expenses")
        return {"id": new_id}

    def _update_expense(self, eid: int, **kw: Any) -> dict | None:
        try:
            self.db.update_expense(eid=eid, **kw)
        except ValueError as e:  # database.py: "Expense with id N not found"
            raise ValidationError("Расход не найден — возможно, удалён в другой вкладке") from e
        self._changed("expenses")
        return next((e for e in self.db.get_expenses() if e["id"] == eid), None)

    def _delete_expense(self, eid: int) -> None:
        self.db.delete_expense(eid)
        self._changed("expenses")

    # ── expense groups ───────────────────────────────────────

    def _create_group(self, **kw: Any) -> dict | None:
        self.db.create_expense_group(**kw)
        self._changed("expense_groups")
        return self.db.get_expense_group(kw["group_id"])

    def _update_group(self, group_id: str, **kw: Any) -> dict | None:
        self.db.update_expense_group(group_id=group_id, **kw)
        self._changed("expense_groups")
        return self.db.get_expense_group(group_id)

    def _delete_group(self, group_id: str) -> None:
        self.db.delete_expense_group(group_id)
        self._changed("expense_groups")
        self._changed("expenses")  # расходы стали «без группы»

    # ── vacations ────────────────────────────────────────────

    def _add_vacation(self, **kw: Any) -> dict:
        new_id = self.db.add_vacation(**kw)
        self._changed("vacations")
        return {"id": new_id}

    def _delete_vacation(self, vid: int) -> None:
        self.db.delete_vacation(vid)
        self._changed("vacations")

    # ── birthdays ────────────────────────────────────────────

    def _add_birthday(self, **kw: Any) -> dict:
        new_id = self.db.add_birthday(**kw)
        self._changed("birthdays")
        return {"id": new_id}

    def _update_birthday(self, bid: int, name: str, birth_date: str,
                         gift_amount: float) -> None:
        self.db.update_birthday(bid, name, birth_date, gift_amount)
        self._changed("birthdays")

    def _delete_birthday(self, bid: int) -> None:
        self.db.delete_birthday(bid)
        self._changed("birthdays")

    # ── debts ────────────────────────────────────────────────

    def _create_debt(self, **kw: Any) -> dict:
        debt_id = self.db.create_debt(**kw)
        self._changed("debts")
        return {"id": debt_id}

    def _delete_debt(self, debt_id: int) -> None:
        self.db.delete_debt(debt_id)
        self._changed("debts")

    def _add_repayment(self, **kw: Any) -> dict:
        rid = self.db.add_debt_repayment(**kw)
        self._changed("debts")
        return {"id": rid}

    def _delete_repayment(self, repayment_id: int) -> None:
        self.db.delete_debt_repayment(repayment_id)
        self._changed("debts")

    # ── calendar cache ───────────────────────────────────────

    def _save_calendar_data(self, year: int, rows: list) -> None:
        self.db.save_calendar_data(year, [tuple(r) for r in rows])

    def _clear_calendar_cache(self, year: int) -> None:
        self.db.clear_calendar_cache(year)

    def _save_corrections(self, year: int, rows: list) -> None:
        self.db.save_corrections(year, [tuple(r) for r in rows])
        self._changed("corrections")

    # ── backup ───────────────────────────────────────────────

    def _backup_to(self, target_path: str) -> None:
        if self._db_path == ":memory:":
            raise ValidationError("Резервная копия недоступна для in-memory БД")
        self.db.backup_to(target_path)

    # ── helper ───────────────────────────────────────────────

    def _changed(self, entity: str) -> None:
        self.k.emit("db:changed", entity=entity)
