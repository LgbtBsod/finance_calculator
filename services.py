"""services.py — Фасад бизнес-логики для GUI (Flet).

Раньше эту роль играл api.py (FastAPI): endpoint'ы собирали DatabaseManager +
SalaryCalculator + CalendarService + BirthdayService через DI и добавляли
несколько агрегаций (баланс, аналитика, тренд). После перехода на Flet
HTTP-слой не нужен — GUI вызывает FinanceService напрямую, а вся прежняя
логика endpoint'ов (агрегации, маппинг снаружи -> camelCase-словарь) переехала
сюда без изменений.

Все методы возвращают обычные dict / list[dict] в camelCase — тот же контракт,
что видел React-фронтенд, чтобы перенос вью был механическим.
"""

from __future__ import annotations

import calendar as _cal
import contextlib
import math
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from calculator import BirthdayService, SalaryCalculator
from database import DatabaseManager
from prod_calendar import CalendarService

__all__ = ["FinanceService", "DebtProjection", "project_debt_payoff", "project_payoff_at_rate"]


# ═══════════════════════════════════════════════════════════════
#  Прогноз погашения долга (порт frontend/src/lib/debtProjection.ts)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DebtProjection:
    avg_monthly_rate: float
    months_to_payoff: int | None
    projected_date: date | None


def _add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def project_debt_payoff(
    remaining_amount: float,
    repayments: list[dict[str, Any]],
    today: date | None = None,
) -> DebtProjection:
    """Прогноз «при текущем темпе»: темп = весь погашенный объём / число
    месяцев с первого платежа (включительно), а не только по месяцам с
    платежами — нерегулярные платежи честно дают более медленный темп."""
    today = today or date.today()
    if remaining_amount <= 0 or not repayments:
        return DebtProjection(0.0, None, None)

    dates = []
    for r in repayments:
        try:
            dates.append(date.fromisoformat(str(r["date"])[:10]))
        except (ValueError, KeyError, TypeError):
            continue
    if not dates:
        return DebtProjection(0.0, None, None)

    earliest = min(dates)
    months_elapsed = max(1, _months_between(earliest, today) + 1)
    total_repaid = sum(float(r["amount"]) for r in repayments)
    avg = total_repaid / months_elapsed
    if avg <= 0:
        return DebtProjection(avg, None, None)

    months = math.ceil(remaining_amount / avg)
    return DebtProjection(avg, months, _add_months(today, months))


def project_payoff_at_rate(
    remaining_amount: float, monthly_rate: float, today: date | None = None
) -> date | None:
    today = today or date.today()
    if remaining_amount <= 0 or not (monthly_rate > 0):
        return None
    return _add_months(today, math.ceil(remaining_amount / monthly_rate))


# ═══════════════════════════════════════════════════════════════
#  Настройки: (поле camelCase, ключ в settings, преобразование в строку)
# ═══════════════════════════════════════════════════════════════

_SETTINGS_FIELD_MAP: list[tuple[str, str, Any]] = [
    ("baseSalary", "base_salary", str),
    ("taxRate", "tax_rate", str),
    ("kef", "kef", str),
    ("advanceCutoffDay", "advance_cutoff_day", str),
    ("isAdvanceDateInclusive", "is_advance_date_inclusive", lambda v: str(v).lower()),
    ("accountShortened", "account_shortened", lambda v: str(v).lower()),
    ("standardHours", "standard_hours", str),
    ("payoutDay1", "payout_day1", str),
    ("payoutDay2", "payout_day2", str),
    ("moveWeekendToFriday", "move_weekend_to_friday", lambda v: str(v).lower()),
    ("salaryCalculationMethod", "salary_calculation_method", str),
    ("firstHalfRatio", "first_half_ratio", str),
    ("secondHalfRatio", "second_half_ratio", str),
]

_DEFAULT_GROUP_COLOR = "#9ca3af"

# Сентинел для трёхзначных полей: "не передано" (не менять) vs явный None (очистить).
_UNSET: Any = object()


# ═══════════════════════════════════════════════════════════════
#  FinanceService
# ═══════════════════════════════════════════════════════════════


class FinanceService:
    """Единая точка входа GUI ко всей бизнес-логике и БД."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from config import get_settings

            db_path = get_settings().db_path
        self.db_path = str(db_path)
        self.db = DatabaseManager(self.db_path)
        self.calendar = CalendarService(
            get_setting=self.db.get_setting,
            set_setting=self.db.set_setting,
            get_corrections=self.db.get_corrections,
            save_corrections=self.db.save_corrections,
            clear_calendar_cache=self.db.clear_calendar_cache,
            calendar_needs_fill=self.db.calendar_needs_fill,
            save_calendar_data=self.db.save_calendar_data,
            get_calendar_month=self.db.get_calendar_month,
        )
        self.calc = SalaryCalculator(
            get_setting=self.db.get_setting,
            vacations=self.db,
            calendar_reader=self.calendar,
        )
        self.birthdays_svc = BirthdayService(get_setting=self.db.get_setting)

    def close(self) -> None:
        self.db.close()

    # ── expense groups ─────────────────────────────────────────

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
        return [self._group_out(g) for g in self.db.get_expense_groups()]

    def create_expense_group(
        self, name: str, color: str, monthly_limit: float | None = None,
        parent_id: str | None = None,
    ) -> dict:
        gid = str(uuid.uuid4())
        self.db.create_expense_group(
            group_id=gid, name=name, color=color, parent_id=parent_id,
            sort_order=0, monthly_limit=monthly_limit,
        )
        return self._group_out(self.db.get_expense_group(gid) or {"id": gid, "name": name, "color": color})

    def update_expense_group(
        self, group_id: str, *, name: str | None = None, color: str | None = None,
        monthly_limit: Any = _UNSET,
    ) -> dict | None:
        """``monthly_limit`` не передан -> не менять; ``None`` -> снять лимит."""
        kwargs: dict = {"group_id": group_id, "name": name, "color": color}
        if monthly_limit is not _UNSET:
            kwargs["monthly_limit"] = monthly_limit
        self.db.update_expense_group(**kwargs)
        g = self.db.get_expense_group(group_id)
        return self._group_out(g) if g else None

    def delete_expense_group(self, group_id: str) -> None:
        self.db.delete_expense_group(group_id)

    # ── expense items ──────────────────────────────────────────

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
        return [self._expense_out(e) for e in self.db.get_expenses(month=month, year=year)]

    def create_expense(
        self, *, name: str, amount: float, half: int, month: int, year: int,
        is_recurring: bool = False, group_id: str | None = None,
        recurring_until: str | None = None,
    ) -> dict:
        if recurring_until:
            _validate_iso(recurring_until, "recurringUntil")
        new_id = self.db.add_expense(
            name=name, amount=amount, month=month, year=year, half=half,
            is_recurring=is_recurring, group_id=group_id, recurring_until=recurring_until,
        )
        return self._expense_out({
            "id": new_id, "group_id": group_id, "name": name, "amount": amount,
            "half": half, "is_recurring": is_recurring, "recurring_until": recurring_until,
            "month": month, "year": year,
        })

    def update_expense(
        self, item_id: str, *, name: str | None = None, amount: float | None = None,
        half: int | None = None, is_recurring: bool | None = None,
        group_id: Any = _UNSET, recurring_until: Any = _UNSET,
    ) -> dict | None:
        """``group_id`` / ``recurring_until`` не переданы -> не менять;
        явный ``None`` -> снять группу / срок повторения."""
        if isinstance(recurring_until, str) and recurring_until:
            _validate_iso(recurring_until, "recurringUntil")
        eid = int(item_id)
        kwargs: dict = {"eid": eid, "name": name, "amount": amount, "half": half,
                        "is_recurring": is_recurring}
        if group_id is not _UNSET:
            kwargs["group_id"] = group_id
        if recurring_until is not _UNSET:
            kwargs["recurring_until"] = recurring_until
        self.db.update_expense(**kwargs)
        updated = next((e for e in self.db.get_expenses() if e["id"] == eid), None)
        return self._expense_out(updated) if updated else None

    def delete_expense(self, item_id: str) -> None:
        self.db.delete_expense(int(item_id))

    # ── vacations ──────────────────────────────────────────────

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
        return [self._vacation_out(v) for v in self.db.get_vacations(month=month, year=year)]

    def create_vacation(
        self, *, total_amount: float, payout_date: str,
        start_date: str | None = None, end_date: str | None = None,
    ) -> dict:
        _validate_iso(payout_date, "payoutDate")
        if start_date:
            _validate_iso(start_date, "startDate")
        if end_date:
            _validate_iso(end_date, "endDate")
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Начало отпуска не может быть позже конца")
        new_id = self.db.add_vacation(
            total_amount=total_amount, payout_date=payout_date,
            start_date=start_date, end_date=end_date,
        )
        return self._vacation_out({
            "id": new_id, "total_amount": total_amount, "payout_date": payout_date,
            "start_date": start_date or payout_date, "end_date": end_date or payout_date,
        })

    def delete_vacation(self, vacation_id: str) -> None:
        self.db.delete_vacation(int(vacation_id))

    # ── birthdays ──────────────────────────────────────────────

    @staticmethod
    def _birthday_out(b: dict) -> dict:
        return {
            "id": str(b.get("id", "")),
            "name": b["name"],
            "birthDate": b["birth_date"],
            "giftAmount": b["gift_amount"],
        }

    def list_birthdays(self) -> list[dict]:
        return [self._birthday_out(b) for b in self.db.get_birthdays()]

    def create_birthday(self, *, name: str, birth_date: str, gift_amount: float) -> dict:
        _validate_birth_date(birth_date)
        new_id = self.db.add_birthday(name=name, birth_date=birth_date, gift_amount=gift_amount)
        return self._birthday_out({
            "id": new_id, "name": name, "birth_date": birth_date, "gift_amount": gift_amount,
        })

    def update_birthday(
        self, birthday_id: str, *, name: str | None = None,
        birth_date: str | None = None, gift_amount: float | None = None,
    ) -> dict | None:
        bid = int(birthday_id)
        current = next((b for b in self.db.get_birthdays() if b["id"] == bid), None)
        if current is None:
            return None
        if birth_date is not None:
            _validate_birth_date(birth_date)
        new_name = name if name is not None else current["name"]
        new_bd = birth_date if birth_date is not None else current["birth_date"]
        new_gift = gift_amount if gift_amount is not None else current["gift_amount"]
        self.db.update_birthday(bid, new_name, new_bd, new_gift)
        return self._birthday_out({
            "id": bid, "name": new_name, "birth_date": new_bd, "gift_amount": new_gift,
        })

    def delete_birthday(self, birthday_id: str) -> None:
        self.db.delete_birthday(int(birthday_id))

    def upcoming_birthdays(self, days: int = 30) -> list[dict]:
        alerts = self.birthdays_svc.upcoming(self.db.get_birthdays(), days_ahead=days)
        return [
            {
                "name": a.name,
                "birthDate": a.birth_date,
                "giftAmount": a.gift_amount,
                "triggerDate": a.trigger_date.isoformat(),
                "daysUntil": a.days_until,
            }
            for a in alerts
        ]

    def auto_create_birthday_expenses(self) -> int:
        today = date.today()
        existing = self.db.get_expenses(month=today.month, year=today.year)
        return self.birthdays_svc.auto_create_expenses(
            self.db.get_birthdays(),
            existing,
            add_expense_fn=lambda **kw: self.db.add_expense(**kw),
        )

    # ── debts ──────────────────────────────────────────────────

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
        return [self._debt_out(d) for d in self.db.get_debts()]

    def create_debt(
        self, *, title: str, total_amount: float,
        month: int | None = None, year: int | None = None,
    ) -> dict:
        today = date.today()
        debt_id = self.db.create_debt(
            title=title, total_amount=total_amount,
            month=month or today.month, year=year or today.year,
        )
        created = next((d for d in self.db.get_debts() if d["id"] == debt_id), None)
        return self._debt_out(created) if created else {}

    def delete_debt(self, debt_id: str) -> None:
        self.db.delete_debt(int(debt_id))

    def add_repayment(
        self, debt_id: str, *, amount: float, when: str | None = None, note: str | None = None
    ) -> dict:
        when = when or date.today().isoformat()
        _validate_iso(when, "date")
        new_id = self.db.add_debt_repayment(debt_id=int(debt_id), amount=amount, date=when, note=note)
        return {
            "id": str(new_id), "debtId": str(debt_id), "amount": amount,
            "date": when, "note": note,
        }

    def delete_repayment(self, repayment_id: str) -> None:
        self.db.delete_debt_repayment(int(repayment_id))

    # ── settings ───────────────────────────────────────────────

    def get_settings(self) -> dict:
        g = self.db.get_setting
        return {
            "baseSalary": float(g("base_salary") or "100000"),
            "taxRate": float(g("tax_rate") or "13"),
            "kef": float(g("kef") or "1.0"),
            "advanceCutoffDay": int(g("advance_cutoff_day") or "15"),
            "isAdvanceDateInclusive": g("is_advance_date_inclusive") == "true",
            "accountShortened": g("account_shortened") == "true",
            "standardHours": int(g("standard_hours") or "40"),
            "payoutDay1": int(g("payout_day1") or "10"),
            "payoutDay2": int(g("payout_day2") or "25"),
            "moveWeekendToFriday": g("move_weekend_to_friday") == "true",
            "salaryCalculationMethod": g("salary_calculation_method") or "proportional",
            "firstHalfRatio": float(g("first_half_ratio") or "0.4"),
            "secondHalfRatio": float(g("second_half_ratio") or "0.6"),
        }

    def update_settings(self, updates: dict[str, Any]) -> dict:
        for field, key, to_str in _SETTINGS_FIELD_MAP:
            if field in updates and updates[field] is not None:
                self.db.set_setting(key, to_str(updates[field]))
        self.calendar.refresh_provider()
        return self.get_settings()

    # ── balance ────────────────────────────────────────────────

    def balance(self, month: int, year: int) -> dict:
        expenses = self.db.get_expenses(month=month, year=year)
        result = self.calc.balance(year, month, expenses)
        s = result.salary
        return {
            "month": month,
            "year": year,
            "netSalary": s.net_salary,
            "advance": s.advance,
            "payout": s.payout,
            "vacationHalf1": s.vacation_half_1,
            "vacationHalf2": s.vacation_half_2,
            "totalAccrued": s.total_accrued,
            "toPayHalf1": s.to_pay_half_1,
            "toPayHalf2": s.to_pay_half_2,
            "expensesHalf1": result.expenses_h1,
            "expensesHalf2": result.expenses_h2,
            "balanceHalf1": result.balance_h1,
            "balanceHalf2": result.balance_h2,
            "calculationMethod": s.calculation_method,
            "workingDaysHalf1": s.working_days_half_1,
            "workingDaysHalf2": s.working_days_half_2,
            "workingDaysTotal": s.working_days_total,
            "advanceCutoffDay": s.advance_cutoff_day,
            "payoutDate1": s.payout_date_1,
            "payoutDate2": s.payout_date_2,
            "payoutDate1Nominal": s.payout_date_1_nominal,
            "payoutDate2Nominal": s.payout_date_2_nominal,
        }

    # ── analytics ──────────────────────────────────────────────

    def analytics_summary(self, month: int | None = None, year: int | None = None) -> dict:
        expenses = self.db.get_expenses(month=month, year=year)
        total = sum(e["amount"] for e in expenses)
        groups_by_id = {g["id"]: g for g in self.db.get_expense_groups()}

        by_category: dict[str | None, dict] = {}
        for e in expenses:
            gid = e.get("group_id")
            group = groups_by_id.get(gid) if gid else None
            if gid not in by_category:
                by_category[gid] = {
                    "name": group["name"] if group else "Без группы",
                    "color": group["color"] if group else _DEFAULT_GROUP_COLOR,
                    "amount": 0.0,
                    "groupId": gid,
                    "monthlyLimit": group.get("monthly_limit") if group else None,
                }
            by_category[gid]["amount"] += e["amount"]

        categories = sorted(by_category.values(), key=lambda c: c["amount"], reverse=True)
        return {"total": total, "count": len(expenses), "categories": categories}

    def analytics_trend(self, month: int, year: int, months: int = 6) -> dict:
        groups_by_id = {g["id"]: g for g in self.db.get_expense_groups()}
        periods: list[tuple[int, int]] = []
        y, m = year, month
        for _ in range(months):
            periods.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        periods.reverse()

        result: list[dict] = []
        for py, pm in periods:
            expenses = self.db.get_expenses(month=pm, year=py)
            by_group: dict[str | None, float] = {}
            for e in expenses:
                gid = e.get("group_id")
                by_group[gid] = by_group.get(gid, 0.0) + e["amount"]
            categories = [
                {
                    "groupId": gid,
                    "name": groups_by_id[gid]["name"] if gid and gid in groups_by_id else "Без группы",
                    "color": groups_by_id[gid]["color"] if gid and gid in groups_by_id else _DEFAULT_GROUP_COLOR,
                    "amount": amount,
                }
                for gid, amount in by_group.items()
            ]
            result.append(
                {"month": pm, "year": py, "total": sum(by_group.values()), "categories": categories}
            )
        return {"months": result}

    # ── calendar ───────────────────────────────────────────────

    def ensure_calendar_year(self, year: int) -> None:
        with contextlib.suppress(Exception):
            self.calendar.build_and_cache_year(year)

    def available_calendar_years(self) -> list[int]:
        try:
            return self.calendar.available_years()
        except Exception:
            return []

    def import_calendar_pdf(self, pdf_path: str) -> Any | None:
        return self.calendar.import_pdf(pdf_path)

    # ── backup ─────────────────────────────────────────────────

    def backup_bytes(self) -> bytes:
        """Консистентная копия БД через SQLite backup API."""
        if self.db_path == ":memory:":
            raise ValidationError("Резервная копия недоступна для in-memory БД")
        tmp = Path(tempfile.gettempdir()) / f"budget-backup-{uuid.uuid4().hex}.db"
        self.db.backup_to(str(tmp))
        try:
            return tmp.read_bytes()
        finally:
            tmp.unlink(missing_ok=True)

    def backup_to(self, target_path: str) -> None:
        self.db.backup_to(target_path)

    # ── debt payoff projection (re-export для вью) ─────────────

    @staticmethod
    def project_debt_payoff(remaining: float, repayments: list[dict]) -> DebtProjection:
        return project_debt_payoff(remaining, repayments)

    @staticmethod
    def project_payoff_at_rate(remaining: float, rate: float) -> date | None:
        return project_payoff_at_rate(remaining, rate)


# ═══════════════════════════════════════════════════════════════
#  Валидация (перенос из api.py — теперь бросает ValidationError)
# ═══════════════════════════════════════════════════════════════


class ValidationError(ValueError):
    """Понятная пользователю ошибка ввода — GUI показывает её текст в снекбаре."""


def _validate_iso(value: str, field_name: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as e:
        raise ValidationError(
            f"{field_name}: неверный формат даты. Используйте ГГГГ-ММ-ДД"
        ) from e


def _validate_birth_date(value: str) -> None:
    """DD.MM.YYYY, реальная дата."""
    try:
        parts = value.strip().split(".")
        if len(parts) != 3:
            raise ValueError
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        date(year, month, day)
    except (ValueError, IndexError) as e:
        raise ValidationError("Неверный формат даты. Используйте ДД.ММ.ГГГГ") from e
