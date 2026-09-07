"""BirthdaysModule — обёртка над calculator.BirthdayService."""

from __future__ import annotations

from datetime import date

from calculator import BirthdayService
from core.module import Module


class BirthdaysModule(Module):
    name = "birthdays"
    requires = ("db",)

    def __init__(self) -> None:
        super().__init__()
        self._svc: BirthdayService | None = None

    def initialize(self) -> None:
        self._svc = BirthdayService(
            get_setting=lambda key: self.k.request("db", "get_setting", key=key)
        )
        self._actions = {
            "upcoming": self._upcoming,
            "auto_create_expenses": self._auto_create_expenses,
            "gift_expense_period": self._gift_expense_period,
        }

    # ── actions ──────────────────────────────────────────────

    def _upcoming(self, days: int = 30) -> list[dict]:
        birthdays = self.k.request("db", "get_birthdays")
        return [
            {
                "name": a.name,
                "birth_date": a.birth_date,
                "gift_amount": a.gift_amount,
                "trigger_date": a.trigger_date.isoformat(),
                "days_until": a.days_until,
            }
            for a in self._svc.upcoming(birthdays, days_ahead=days)
        ]

    def _auto_create_expenses(self) -> int:
        today = date.today()
        birthdays = self.k.request("db", "get_birthdays")
        existing = self.k.request("db", "get_expenses", month=today.month, year=today.year)

        def add_expense_fn(**kw):  # noqa: ANN003 - контракт BirthdayService
            self.k.request("db", "add_expense", **kw)

        return self._svc.auto_create_expenses(birthdays, existing, add_expense_fn=add_expense_fn)

    def _gift_expense_period(self, birth_day: int, birth_month: int, ref_year: int) -> list[int]:
        half, month, year = self._svc.gift_expense_period(birth_day, birth_month, ref_year)
        return [half, month, year]
