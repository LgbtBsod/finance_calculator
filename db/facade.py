"""db.facade — класс ``Database``: тонкий фасад над Engine + репозиториями.

Публичная поверхность 1-в-1 со старым ``DatabaseManager`` (имена, позиционные и
keyword-параметры, дефолты, ``_UNSET``-семантика PATCH-полей). Делегаторы явные
(не ``__getattr__``) — mypy strict видит поверхность, ядро с ``strict=True``
валидирует возвраты, поверхность грепается.

``DatabaseManager = Database`` в конце файла — alias (не подкласс), чтобы
``type()`` / ``isinstance`` / repr совпадали со старым кодом.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from db.engine import Engine
from db.migrations import bootstrap, migrate_schema
from db.query import _UNSET
from db.repositories import (
    BirthdayRepo,
    CalendarRepo,
    DebtRepo,
    ExpenseGroupRepo,
    ExpenseRepo,
    IncomeRepo,
    SettingsRepo,
    UndoRepo,
    VacationRepo,
)

if TYPE_CHECKING:
    import sqlite3

    from models import (
        BirthdayRow,
        CalendarRow,
        CorrectionRow,
        ExpenseRow,
        IncomeRow,
        VacationRow,
    )


class Database:
    """Управляет всеми операциями с SQLite через слоёный пакет ``db``.

    Каждый метод возвращает TypedDict или list[TypedDict], а не сырой dict —
    потребители получают автодополнение полей.

    Конкурентный доступ: оптимистическая блокировка сознательно НЕ реализована.
    Если два клиента правят одну запись одновременно, побеждает тот, кто
    записал последним (last-write-wins). Это принятое ограничение —
    приложение однопользовательское.
    """

    def __init__(self, db_path: str = "budget.db") -> None:
        self.db_path = db_path
        self._engine = Engine(db_path)
        bootstrap(self._engine)
        self._settings = SettingsRepo(self._engine)
        self._calendar = CalendarRepo(self._engine)
        self._birthdays = BirthdayRepo(self._engine)
        self._expenses = ExpenseRepo(self._engine)
        self._income = IncomeRepo(self._engine)
        self._vacations = VacationRepo(self._engine)
        self._groups = ExpenseGroupRepo(self._engine)
        self._debts = DebtRepo(self._engine)
        self._undo = UndoRepo(self._engine)

    # ── settings ─────────────────────────────────────────────

    def get_setting(self, key: str) -> str:
        return self._settings.get_setting(key)

    def get_settings_bundle(self) -> dict[str, str]:
        return self._settings.get_settings_bundle()

    def set_setting(self, key: str, value: str) -> None:
        self._settings.set_setting(key, value)

    # ── calendar ─────────────────────────────────────────────

    def calendar_needs_fill(self, year: int) -> bool:
        return self._calendar.calendar_needs_fill(year)

    def save_calendar_data(self, year: int, rows: list[tuple]) -> None:
        self._calendar.save_calendar_data(year, rows)

    def clear_calendar_cache(self, year: int) -> None:
        self._calendar.clear_calendar_cache(year)

    def get_calendar_month(self, year: int, month: int) -> list[CalendarRow]:
        return self._calendar.get_calendar_month(year, month)

    def get_corrections(self) -> list[CorrectionRow]:
        return self._calendar.get_corrections()

    def save_corrections(self, year: int, rows: list[tuple]) -> None:
        self._calendar.save_corrections(year, rows)

    # ── birthdays ────────────────────────────────────────────

    def add_birthday(self, name: str, birth_date: str, gift_amount: float) -> int:
        return self._birthdays.add_birthday(name, birth_date, gift_amount)

    def get_birthdays(self) -> list[BirthdayRow]:
        return self._birthdays.get_birthdays()

    def delete_birthday(self, bid: int) -> None:
        self._birthdays.delete_birthday(bid)

    def update_birthday(self, bid: int, name: str, birth_date: str,
                        gift_amount: float) -> None:
        self._birthdays.update_birthday(bid, name, birth_date, gift_amount)

    # ── expenses ─────────────────────────────────────────────

    def add_expense(
        self, name: str, amount: float, half: int, month: int, year: int,
        is_recurring: bool = False, group_id: str | None = None,
        recurring_until: str | None = None,
    ) -> int:
        return self._expenses.add_expense(
            name, amount, half, month, year, is_recurring, group_id, recurring_until
        )

    def get_expenses(self, month: int | None = None,
                     year: int | None = None) -> list[ExpenseRow]:
        return self._expenses.get_expenses(month, year)

    def set_period_override(self, kind: str, row_id: int, year: int,
                            month: int, amount: float) -> None:
        self._expenses.set_period_override(kind, row_id, year, month, amount)

    def clear_period_override(self, kind: str, row_id: int, year: int, month: int) -> None:
        self._expenses.clear_period_override(kind, row_id, year, month)

    def delete_expense(self, eid: int) -> None:
        self._expenses.delete_expense(eid)

    def update_expense(
        self, eid: int, name: str | None = None, amount: float | None = None,
        half: int | None = None, is_recurring: bool | None = None,
        group_id: str | None | object = _UNSET,
        recurring_until: str | None | object = _UNSET,
    ) -> None:
        self._expenses.update_expense(
            eid, name, amount, half, is_recurring, group_id, recurring_until
        )

    # ── income ───────────────────────────────────────────────

    def add_income(
        self, name: str, amount: float, half: int, month: int, year: int,
        is_recurring: bool = False, recurring_until: str | None = None,
        kind: str = "fixed", kef: float | None = None, split_method: str | None = None,
        first_half_ratio: float | None = None, second_half_ratio: float | None = None,
    ) -> int:
        return self._income.add_income(
            name, amount, half, month, year, is_recurring, recurring_until, kind, kef,
            split_method, first_half_ratio, second_half_ratio,
        )

    def get_income(self, month: int | None = None,
                   year: int | None = None) -> list[IncomeRow]:
        return self._income.get_income(month, year)

    def delete_income(self, iid: int) -> None:
        self._income.delete_income(iid)

    def update_income(
        self, iid: int, name: str | None = None, amount: float | None = None,
        half: int | None = None, is_recurring: bool | None = None,
        recurring_until: str | None | object = _UNSET,
        kef: float | None = None, split_method: str | None = None,
        first_half_ratio: float | None = None, second_half_ratio: float | None = None,
    ) -> None:
        self._income.update_income(
            iid, name, amount, half, is_recurring, recurring_until, kef, split_method,
            first_half_ratio, second_half_ratio,
        )

    # ── vacations ────────────────────────────────────────────

    def add_vacation(self, total_amount: float, payout_date: str,
                     start_date: str | None = None, end_date: str | None = None) -> int:
        return self._vacations.add_vacation(total_amount, payout_date, start_date, end_date)

    def get_vacations(self, month: int | None = None,
                      year: int | None = None) -> list[VacationRow]:
        return self._vacations.get_vacations(month, year)

    def delete_vacation(self, vid: int) -> None:
        self._vacations.delete_vacation(vid)

    # ── expense groups ───────────────────────────────────────

    def create_expense_group(
        self, group_id: str, name: str, color: str, parent_id: str | None = None,
        sort_order: int = 0, monthly_limit: float | None = None,
    ) -> None:
        self._groups.create_expense_group(
            group_id, name, color, parent_id, sort_order, monthly_limit
        )

    def get_expense_groups(self) -> list[dict]:
        return self._groups.get_expense_groups()

    def get_expense_group(self, group_id: str) -> dict | None:
        return self._groups.get_expense_group(group_id)

    def update_expense_group(
        self, group_id: str, name: str | None = None, color: str | None = None,
        parent_id: str | None | object = _UNSET, sort_order: int | None = None,
        monthly_limit: float | None | object = _UNSET,
    ) -> None:
        self._groups.update_expense_group(
            group_id, name, color, parent_id, sort_order, monthly_limit
        )

    def delete_expense_group(self, group_id: str) -> None:
        self._groups.delete_expense_group(group_id)

    # ── debts ────────────────────────────────────────────────

    def create_debt(
        self, title: str, total_amount: float, month: int, year: int,
        monthly_payment: float = 0.0, payment_half: int = 2,
    ) -> int:
        return self._debts.create_debt(
            title, total_amount, month, year, monthly_payment, payment_half
        )

    def update_debt(
        self, debt_id: int, *, title: str | None = None, total_amount: float | None = None,
        monthly_payment: float | None = None, payment_half: int | None = None,
    ) -> None:
        self._debts.update_debt(
            debt_id, title=title, total_amount=total_amount,
            monthly_payment=monthly_payment, payment_half=payment_half,
        )

    def get_debts(self) -> list[dict]:
        return self._debts.get_debts()

    def delete_debt(self, debt_id: int) -> None:
        self._debts.delete_debt(debt_id)

    def add_debt_repayment(self, debt_id: int, amount: float, date: str,
                           note: str | None = None) -> int:
        return self._debts.add_debt_repayment(debt_id, amount, date, note)

    def delete_debt_repayment(self, repayment_id: int) -> None:
        self._debts.delete_debt_repayment(repayment_id)

    # ── undo удаления ────────────────────────────────────────

    def snapshot_for_undo(self, kind: str, row_id: int | str) -> dict | None:
        return self._undo.snapshot_for_undo(kind, row_id)

    def restore_from_undo(self, snapshot: dict) -> None:
        self._undo.restore_from_undo(snapshot)

    # ── инфраструктура + тест-совместимость ──────────────────

    def close(self) -> None:
        self._engine.close()

    def backup_to(self, target_path: str) -> None:
        self._engine.backup_to(target_path)

    def _transaction(self) -> Any:
        """Только для тестов (test_database.py: `with db._transaction() as c`)."""
        return self._engine._transaction()

    def _migrate_schema(self, c: sqlite3.Connection) -> None:
        """Только для тестов (проверка идемпотентности миграций)."""
        migrate_schema(c)


DatabaseManager = Database
