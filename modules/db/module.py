"""DBModule — обёртка над пакетом ``db`` (фасад ``Database``).

ЕДИНСТВЕННЫЙ модуль, знающий про SQL. После каждой записи шлёт
``db:changed`` (entity=...) — ядро диспатчит это событие после раскрутки
верхнеуровневого request, вне открытой транзакции.

Однотипные действия (проброс read, add -> {"id"}, delete с undo) генерируются
из таблиц ниже — «какое действие какие сущности трогает» видно в одном месте.
"""

from __future__ import annotations

from typing import Any

from core.errors import ValidationError
from core.module import Module
from db import DatabaseManager

# read-действие -> метод DatabaseManager (чистый проброс **kw).
_READS = {
    name: name for name in (
        "get_setting", "get_settings_bundle", "get_expenses", "get_income",
        "get_expense_groups", "get_expense_group", "get_vacations", "get_birthdays",
        "get_debts", "get_corrections", "calendar_needs_fill", "get_calendar_month",
    )
}

# add-действие -> (метод DatabaseManager, сущность для db:changed).
# Возвращает {"id": <lastrowid>}.
_ADDS = {
    "add_expense": ("add_expense", "expenses"),
    "add_income": ("add_income", "income"),
    "add_vacation": ("add_vacation", "vacations"),
    "add_birthday": ("add_birthday", "birthdays"),
    "create_debt": ("create_debt", "debts"),
    "add_debt_repayment": ("add_debt_repayment", "debts"),
}

# delete-действие -> (kind для снимка undo, метод, затронутые сущности).
_UNDO_DELETES = {
    "delete_expense": ("expense", "delete_expense", ("expenses",)),
    "delete_income": ("income", "delete_income", ("income",)),
    "delete_vacation": ("vacation", "delete_vacation", ("vacations",)),
    "delete_birthday": ("birthday", "delete_birthday", ("birthdays",)),
    "delete_debt": ("debt", "delete_debt", ("debts",)),
    "delete_expense_group": ("expense_group", "delete_expense_group",
                             ("expense_groups", "expenses")),  # расходы -> «без группы»
}
_RESTORE_ENTITIES = {kind: ents for kind, _m, ents in _UNDO_DELETES.values()}


class DBModule(Module):
    name = "db"

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self._db_path = db_path
        self.db: DatabaseManager | None = None

    def initialize(self) -> None:
        self.db = DatabaseManager(self._db_path)
        self._actions = {
            **{a: self._proxy(m) for a, m in _READS.items()},
            **{a: self._adder(m, e) for a, (m, e) in _ADDS.items()},
            **{a: self._undo_deleter(k, m, e) for a, (k, m, e) in _UNDO_DELETES.items()},
            "set_setting": self._set_setting,
            "update_expense": self._update_expense,
            "update_income": self._update_income,
            "set_period_override": self._set_period_override,
            "clear_period_override": self._clear_period_override,
            "restore_deleted": self._restore_deleted,
            "create_expense_group": self._create_group,
            "update_expense_group": self._update_group,
            "update_birthday": self._update_birthday,
            "update_debt": self._update_debt,
            "delete_debt_repayment": self._delete_repayment,
            "save_calendar_data": self._save_calendar_data,
            "clear_calendar_cache": self._clear_calendar_cache,
            "save_corrections": self._save_corrections,
            "backup_to": self._backup_to,
            "db_path": lambda: self._db_path,
        }

    def shutdown(self) -> None:
        if self.db is not None:
            self.db.close()

    # ── генераторы однотипных действий ───────────────────────

    def _proxy(self, method: str):
        return lambda **kw: getattr(self.db, method)(**kw)

    def _adder(self, method: str, entity: str):
        def add(**kw: Any) -> dict:
            new_id = getattr(self.db, method)(**kw)
            self._changed(entity)
            return {"id": new_id}
        return add

    def _undo_deleter(self, kind: str, method: str, entities: tuple[str, ...]):
        def delete(**kw: Any) -> dict:
            row_id = next(iter(kw.values()))          # единственный аргумент — id строки
            snap = self.db.snapshot_for_undo(kind, row_id)
            getattr(self.db, method)(row_id)
            for e in entities:
                self._changed(e)
            return {"undo": snap}
        return delete

    def _restore_deleted(self, snapshot: dict) -> dict:
        self.db.restore_from_undo(snapshot)
        for e in _RESTORE_ENTITIES.get(snapshot.get("kind"), ()):
            self._changed(e)
        return {"restored": snapshot.get("kind")}

    # ── settings ─────────────────────────────────────────────

    def _set_setting(self, key: str, value: Any) -> None:
        self.db.set_setting(key, str(value))
        self._changed("settings")

    # ── expenses / income (частичное обновление + понятная ошибка) ──

    def _update_expense(self, eid: int, **kw: Any) -> dict | None:
        try:
            self.db.update_expense(eid=eid, **kw)
        except ValueError as e:  # db.repositories.expenses: "Expense with id N not found"
            raise ValidationError("Расход не найден — возможно, удалён в другой вкладке") from e
        self._changed("expenses")
        return next((e for e in self.db.get_expenses() if e["id"] == eid), None)

    def _update_income(self, iid: int, **kw: Any) -> dict | None:
        try:
            self.db.update_income(iid=iid, **kw)
        except ValueError as e:
            raise ValidationError("Доход не найден — возможно, удалён") from e
        self._changed("income")
        return next((i for i in self.db.get_income() if i["id"] == iid), None)

    def _set_period_override(self, kind: str, row_id: int, year: int,
                             month: int, amount: float) -> None:
        self.db.set_period_override(kind, row_id, year, month, amount)
        self._changed("expenses" if kind == "expense" else "income")

    def _clear_period_override(self, kind: str, row_id: int, year: int, month: int) -> None:
        self.db.clear_period_override(kind, row_id, year, month)
        self._changed("expenses" if kind == "expense" else "income")

    # ── expense groups (возвращают саму строку) ──────────────

    def _create_group(self, **kw: Any) -> dict | None:
        self.db.create_expense_group(**kw)
        self._changed("expense_groups")
        return self.db.get_expense_group(kw["group_id"])

    def _update_group(self, group_id: str, **kw: Any) -> dict | None:
        self.db.update_expense_group(group_id=group_id, **kw)
        self._changed("expense_groups")
        return self.db.get_expense_group(group_id)

    # ── прочие простые записи ────────────────────────────────

    def _update_birthday(self, bid: int, name: str, birth_date: str,
                         gift_amount: float) -> None:
        self.db.update_birthday(bid, name, birth_date, gift_amount)
        self._changed("birthdays")

    def _update_debt(self, debt_id: int, **kw: Any) -> None:
        self.db.update_debt(debt_id, **kw)
        self._changed("debts")

    def _delete_repayment(self, repayment_id: int) -> None:
        self.db.delete_debt_repayment(repayment_id)
        self._changed("debts")

    def _save_calendar_data(self, year: int, rows: list) -> None:
        self.db.save_calendar_data(year, [tuple(r) for r in rows])

    def _clear_calendar_cache(self, year: int) -> None:
        self.db.clear_calendar_cache(year)

    def _save_corrections(self, year: int, rows: list) -> None:
        self.db.save_corrections(year, [tuple(r) for r in rows])
        self._changed("corrections")

    def _backup_to(self, target_path: str) -> None:
        if self._db_path == ":memory:":
            raise ValidationError("Резервная копия недоступна для in-memory БД")
        self.db.backup_to(target_path)

    # ── helper ───────────────────────────────────────────────

    def _changed(self, entity: str) -> None:
        self.k.emit("db:changed", entity=entity)
