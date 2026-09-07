"""services.py — тонкий типизированный фасад GUI над ядром.

GUI (gui/views/*.py) знает только про FinanceService. Фасад НЕ содержит логики:
  - CRUD -> прямой request в модуль db, маппинг snake_case строк БД -> camelCase;
  - агрегации (balance / analytics / settings) -> request в модуль finance;
  - валидация ввода -> core.validation (бросает ValidationError, ядро её не оборачивает);
  - чистый прогноз долга -> core.projection.

Держит core.Kernel (композиционный корень), но для операций пользуется узким
KernelView('gui') — той же дисциплиной, что и модули.
"""

from __future__ import annotations

import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.errors import ValidationError
from core.kernel import Kernel
from core.projection import DebtProjection, project_debt_payoff, project_payoff_at_rate
from core.validation import validate_birth_date, validate_iso_date

__all__ = [
    "FinanceService",
    "ValidationError",
    "DebtProjection",
    "project_debt_payoff",
    "project_payoff_at_rate",
]

_UNSET: Any = object()


class FinanceService:
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.k = kernel.view("gui")

    def close(self) -> None:
        self._kernel.shutdown()

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self.k.subscribe(event, handler)

    # ═══════════════════════ expense groups ═══════════════════════

    @staticmethod
    def _group_out(g: dict) -> dict:
        return {
            "id": g["id"],
            "name": g["name"],
            "color": g["color"],
            "parentId": g.get("parent_id"),
            "sortOrder": g.get("sort_order", 0),
            "monthlyLimit": g.get("monthly_limit"),
        }

    def list_expense_groups(self) -> list[dict]:
        return [self._group_out(g) for g in self.k.request("db", "get_expense_groups")]

    def create_expense_group(
        self, name: str, color: str, monthly_limit: float | None = None,
        parent_id: str | None = None,
    ) -> dict:
        g = self.k.request(
            "db", "create_expense_group", group_id=str(uuid.uuid4()), name=name,
            color=color, parent_id=parent_id, sort_order=0, monthly_limit=monthly_limit,
        )
        return self._group_out(g)

    def update_expense_group(
        self, group_id: str, *, name: str | None = None, color: str | None = None,
        monthly_limit: Any = _UNSET,
    ) -> dict | None:
        payload: dict = {"group_id": group_id, "name": name, "color": color}
        if monthly_limit is not _UNSET:
            payload["monthly_limit"] = monthly_limit
        g = self.k.request("db", "update_expense_group", **payload)
        return self._group_out(g) if g else None

    def delete_expense_group(self, group_id: str) -> None:
        self.k.request("db", "delete_expense_group", group_id=group_id)

    # ═══════════════════════ expenses ═══════════════════════

    @staticmethod
    def _expense_out(e: dict) -> dict:
        return {
            "id": str(e["id"]),
            "groupId": e.get("group_id"),
            "name": e["name"],
            "amount": e["amount"],
            "isInclusive": e.get("is_inclusive", False),
            "half": e.get("half", 1),
            "isRecurring": e.get("is_recurring", False),
            "recurringUntil": e.get("recurring_until"),
            "month": e["month"],
            "year": e["year"],
        }

    def list_expenses(self, month: int | None = None, year: int | None = None) -> list[dict]:
        return [
            self._expense_out(e)
            for e in self.k.request("db", "get_expenses", month=month, year=year)
        ]

    def create_expense(
        self, *, name: str, amount: float, half: int, month: int, year: int,
        is_recurring: bool = False, group_id: str | None = None,
        recurring_until: str | None = None,
    ) -> dict:
        if recurring_until:
            validate_iso_date(recurring_until, "recurringUntil")
        res = self.k.request(
            "db", "add_expense", name=name, amount=amount, month=month, year=year,
            half=half, is_recurring=is_recurring, group_id=group_id,
            recurring_until=recurring_until,
        )
        return self._expense_out({
            "id": res["id"], "group_id": group_id, "name": name, "amount": amount,
            "half": half, "is_recurring": is_recurring, "recurring_until": recurring_until,
            "month": month, "year": year,
        })

    def update_expense(
        self, item_id: str, *, name: str | None = None, amount: float | None = None,
        half: int | None = None, is_recurring: bool | None = None,
        group_id: Any = _UNSET, recurring_until: Any = _UNSET,
    ) -> dict | None:
        if isinstance(recurring_until, str) and recurring_until:
            validate_iso_date(recurring_until, "recurringUntil")
        payload: dict = {
            "eid": int(item_id), "name": name, "amount": amount, "half": half,
            "is_recurring": is_recurring,
        }
        if group_id is not _UNSET:
            payload["group_id"] = group_id
        if recurring_until is not _UNSET:
            payload["recurring_until"] = recurring_until
        e = self.k.request("db", "update_expense", **payload)
        return self._expense_out(e) if e else None

    def delete_expense(self, item_id: str) -> None:
        self.k.request("db", "delete_expense", eid=int(item_id))

    # ═══════════════════════ vacations ═══════════════════════

    @staticmethod
    def _vacation_out(v: dict) -> dict:
        return {
            "id": str(v.get("id", "")),
            "totalAmount": v["total_amount"],
            "payoutDate": v["payout_date"],
            "startDate": v.get("start_date"),
            "endDate": v.get("end_date"),
        }

    def list_vacations(self, month: int | None = None, year: int | None = None) -> list[dict]:
        return [
            self._vacation_out(v)
            for v in self.k.request("db", "get_vacations", month=month, year=year)
        ]

    def create_vacation(
        self, *, total_amount: float, payout_date: str,
        start_date: str | None = None, end_date: str | None = None,
    ) -> dict:
        validate_iso_date(payout_date, "payoutDate")
        if start_date:
            validate_iso_date(start_date, "startDate")
        if end_date:
            validate_iso_date(end_date, "endDate")
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Начало отпуска не может быть позже конца")
        res = self.k.request(
            "db", "add_vacation", total_amount=total_amount, payout_date=payout_date,
            start_date=start_date, end_date=end_date,
        )
        return self._vacation_out({
            "id": res["id"], "total_amount": total_amount, "payout_date": payout_date,
            "start_date": start_date or payout_date, "end_date": end_date or payout_date,
        })

    def delete_vacation(self, vacation_id: str) -> None:
        self.k.request("db", "delete_vacation", vid=int(vacation_id))

    # ═══════════════════════ birthdays ═══════════════════════

    @staticmethod
    def _birthday_out(b: dict) -> dict:
        return {
            "id": str(b.get("id", "")),
            "name": b["name"],
            "birthDate": b["birth_date"],
            "giftAmount": b["gift_amount"],
        }

    def list_birthdays(self) -> list[dict]:
        return [self._birthday_out(b) for b in self.k.request("db", "get_birthdays")]

    def create_birthday(self, *, name: str, birth_date: str, gift_amount: float) -> dict:
        validate_birth_date(birth_date)
        res = self.k.request(
            "db", "add_birthday", name=name, birth_date=birth_date, gift_amount=gift_amount
        )
        return self._birthday_out({
            "id": res["id"], "name": name, "birth_date": birth_date, "gift_amount": gift_amount,
        })

    def update_birthday(
        self, birthday_id: str, *, name: str | None = None,
        birth_date: str | None = None, gift_amount: float | None = None,
    ) -> dict | None:
        bid = int(birthday_id)
        current = next((b for b in self.k.request("db", "get_birthdays") if b["id"] == bid), None)
        if current is None:
            return None
        if birth_date is not None:
            validate_birth_date(birth_date)
        new_name = name if name is not None else current["name"]
        new_bd = birth_date if birth_date is not None else current["birth_date"]
        new_gift = gift_amount if gift_amount is not None else current["gift_amount"]
        self.k.request(
            "db", "update_birthday", bid=bid, name=new_name, birth_date=new_bd,
            gift_amount=new_gift,
        )
        return self._birthday_out({
            "id": bid, "name": new_name, "birth_date": new_bd, "gift_amount": new_gift,
        })

    def delete_birthday(self, birthday_id: str) -> None:
        self.k.request("db", "delete_birthday", bid=int(birthday_id))

    def upcoming_birthdays(self, days: int = 30) -> list[dict]:
        return [
            {
                "name": a["name"],
                "birthDate": a["birth_date"],
                "giftAmount": a["gift_amount"],
                "triggerDate": a["trigger_date"],
                "daysUntil": a["days_until"],
            }
            for a in self.k.request("birthdays", "upcoming", days=days)
        ]

    def auto_create_birthday_expenses(self) -> int:
        return self.k.request("birthdays", "auto_create_expenses")

    # ═══════════════════════ debts ═══════════════════════

    @staticmethod
    def _debt_out(d: dict) -> dict:
        return {
            "id": str(d["id"]),
            "title": d["title"],
            "totalAmount": d["total_amount"],
            "repayments": [
                {
                    "id": str(r["id"]),
                    "debtId": str(r["debt_id"]),
                    "amount": r["amount"],
                    "date": r["date"],
                    "note": r.get("note"),
                }
                for r in d.get("repayments", [])
            ],
            "createdAt": d["created_at"],
            "month": d["month"],
            "year": d["year"],
            "repaidAmount": d.get("repaid_amount", 0.0),
            "remainingAmount": d.get("remaining_amount", d["total_amount"]),
        }

    def list_debts(self) -> list[dict]:
        return [self._debt_out(d) for d in self.k.request("db", "get_debts")]

    def create_debt(
        self, *, title: str, total_amount: float,
        month: int | None = None, year: int | None = None,
    ) -> dict:
        from datetime import date

        today = date.today()
        res = self.k.request(
            "db", "create_debt", title=title, total_amount=total_amount,
            month=month or today.month, year=year or today.year,
        )
        created = next((d for d in self.k.request("db", "get_debts") if d["id"] == res["id"]), None)
        return self._debt_out(created) if created else {}

    def delete_debt(self, debt_id: str) -> None:
        self.k.request("db", "delete_debt", debt_id=int(debt_id))

    def add_repayment(
        self, debt_id: str, *, amount: float, when: str | None = None, note: str | None = None
    ) -> dict:
        from datetime import date

        when = when or date.today().isoformat()
        validate_iso_date(when, "date")
        res = self.k.request(
            "db", "add_debt_repayment", debt_id=int(debt_id), amount=amount, date=when, note=note
        )
        return {"id": str(res["id"]), "debtId": str(debt_id), "amount": amount,
                "date": when, "note": note}

    def delete_repayment(self, repayment_id: str) -> None:
        self.k.request("db", "delete_debt_repayment", repayment_id=int(repayment_id))

    # ═══════════════════════ settings ═══════════════════════

    def get_settings(self) -> dict:
        return self.k.request("finance", "settings_get")

    def update_settings(self, updates: dict[str, Any]) -> dict:
        return self.k.request("finance", "settings_update", updates=updates)

    # ═══════════════════════ aggregations ═══════════════════════

    def balance(self, month: int, year: int) -> dict:
        return self.k.request("finance", "balance", month=month, year=year)

    def analytics_summary(self, month: int | None = None, year: int | None = None) -> dict:
        return self.k.request("finance", "analytics_summary", month=month, year=year)

    def analytics_trend(self, month: int, year: int, months: int = 6) -> dict:
        return self.k.request("finance", "analytics_trend", month=month, year=year, months=months)

    # ═══════════════════════ calendar ═══════════════════════

    def ensure_calendar_year(self, year: int) -> None:
        import contextlib

        with contextlib.suppress(Exception):
            self.k.request("calendar", "build_and_cache_year", year=year)

    def available_calendar_years(self) -> list[int]:
        try:
            return self.k.request("calendar", "available_years")
        except Exception:  # noqa: BLE001
            return []

    def import_calendar_pdf(self, pdf_path: str) -> dict | None:
        return self.k.request("calendar", "import_pdf", pdf_path=pdf_path)

    # ═══════════════════════ backup ═══════════════════════

    def backup_bytes(self) -> bytes:
        tmp = Path(tempfile.gettempdir()) / f"budget-backup-{uuid.uuid4().hex}.db"
        self.k.request("db", "backup_to", target_path=str(tmp))
        try:
            return tmp.read_bytes()
        finally:
            tmp.unlink(missing_ok=True)

    def backup_to(self, target_path: str) -> None:
        self.k.request("db", "backup_to", target_path=target_path)

    # ═══════════════════════ debt projection (re-export) ═══════════════════════

    @staticmethod
    def project_debt_payoff(remaining: float, repayments: list[dict]) -> DebtProjection:
        return project_debt_payoff(remaining, repayments)

    @staticmethod
    def project_payoff_at_rate(remaining: float, rate: float):
        return project_payoff_at_rate(remaining, rate)
