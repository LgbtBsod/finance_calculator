"""calculator.py — Чистая бизнес-логика (ЗП, ДР, баланс).

Не знает о БД — получает данные через Protocol'ы / callable.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from models import (
    BalanceResult,
    BirthdayAlert,
    BirthdayRow,
    CalendarReader,
    ExpenseRow,
    SalaryBreakdown,
    VacationReader,
)

__all__ = [
    "SalaryCalculator",
    "BirthdayService",
]


# ═══════════════════════════════════════════════════════════════
#  SalaryCalculator
# ═══════════════════════════════════════════════════════════════


class SalaryCalculator:
    """Расчёт зарплаты.

    Зависит от CalendarReader (протокол) для кол-ва рабочих дней
    и от VacationReader для отпускных — не знает о БД и провайдерах.
    """

    def __init__(
        self,
        get_setting: Callable[[str], str],
        calendar: CalendarReader,
        vacations: VacationReader,
    ) -> None:
        self._get = get_setting
        self._cal = calendar
        self._vacs = vacations

    def calculate(self, year: int, month: int) -> SalaryBreakdown:
        base = float(self._get("base_salary") or 0)
        tax = float(self._get("tax_rate") or 13)
        kef = float(self._get("kef") or 1.0)
        cutoff = int(self._get("advance_cutoff_day") or 15)

        total, h1, h2 = self._cal.get_working_days(year, month)
        if total == 0:
            total = 1.0  # защита от /0

        net = base * kef * (1.0 - tax / 100.0)
        advance = net * (h1 / total)
        payout = net * (h2 / total)

        vac_h1, vac_h2 = self._distribute_vacations(year, month, cutoff)

        accrued = net + vac_h1 + vac_h2
        return SalaryBreakdown(
            net_salary=net,
            advance=advance,
            payout=payout,
            vacation_half_1=vac_h1,
            vacation_half_2=vac_h2,
            total_accrued=accrued,
            to_pay_half_1=advance + vac_h1,
            to_pay_half_2=payout + vac_h2,
        )

    def balance(
        self,
        year: int,
        month: int,
        expenses: list[ExpenseRow],
    ) -> BalanceResult:
        sal = self.calculate(year, month)
        e_h1 = sum(float(e["amount"]) for e in expenses if e["half"] == 1)
        e_h2 = sum(float(e["amount"]) for e in expenses if e["half"] == 2)
        return BalanceResult(
            salary=sal,
            expenses_h1=e_h1,
            expenses_h2=e_h2,
            balance_h1=sal.to_pay_half_1 - e_h1,
            balance_h2=sal.to_pay_half_2 - e_h2,
        )

    # ── отпускные ────────────────────────────────────────────

    def _distribute_vacations(
        self, year: int, month: int, cutoff: int
    ) -> tuple[float, float]:
        """Распределяет отпускные по половинам через VacationReader."""
        vacs = self._vacs.get_vacations(month, year)
        h1 = h2 = 0.0
        for v in vacs:
            try:
                vd = date.fromisoformat(v["payout_date"])
                amt = float(v["total_amount"])
                if vd.day <= cutoff:
                    h1 += amt
                else:
                    h2 += amt
            except (ValueError, TypeError):
                pass
        return h1, h2


# ═══════════════════════════════════════════════════════════════
#  BirthdayService
# ═══════════════════════════════════════════════════════════════


class BirthdayService:
    """Логика триггеров дней рождений.

    Зависит от БД только через callable / TypedDict.
    """

    TRIGGER_DAYS_BEFORE = 14

    def __init__(self, get_setting: Callable[[str], str]) -> None:
        self._get = get_setting

    def trigger_date(
        self, birth_date: str, ref_year: int
    ) -> date | None:
        """Триггер = ДР в ref_year - 14 дней. Учитывает переход через год."""
        day, month = self._parse_bd(birth_date)
        if day is None:
            return None
        try:
            bd = date(ref_year, month, day)
        except ValueError:
            return None
        return bd - timedelta(days=self.TRIGGER_DAYS_BEFORE)

    def upcoming(
        self,
        birthdays: list[BirthdayRow],
        days_ahead: int = 30,
    ) -> list[BirthdayAlert]:
        today = date.today()
        alerts: list[BirthdayAlert] = []
        for bd in birthdays:
            alert = self._check_one(bd, today, days_ahead)
            if alert:
                alerts.append(alert)
        alerts.sort(key=lambda a: a.days_until)
        return alerts

    def auto_create_expenses(
        self,
        birthdays: list[BirthdayRow],
        existing_expenses: list[ExpenseRow],
        add_expense_fn: Callable[..., None],
        cutoff: int,
    ) -> int:
        """Создать расходы по триггерам ДР за текущий месяц. Возвращает кол-во."""
        today = date.today()
        created = 0
        for bd in birthdays:
            trigger = self.trigger_date(bd["birth_date"], today.year)
            if trigger is None:
                continue
            if trigger.year != today.year or trigger.month != today.month:
                continue

            half = 1 if trigger.day <= cutoff else 2
            label = f"🎂 {bd['name']} (ДР {bd['birth_date']})"

            if any(e["name"] == label for e in existing_expenses):
                continue

            add_expense_fn(
                name=label,
                amount=float(bd["gift_amount"]),
                half=half,
                month=today.month,
                year=today.year,
            )
            created += 1
        return created

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _parse_bd(bd: str) -> tuple[int | None, int | None]:
        try:
            parts = bd.strip().split(".")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return None, None

    def _check_one(
        self, bd: dict, today: date, days_ahead: int
    ) -> BirthdayAlert | None:
        for year in (today.year, today.year + 1):
            trigger = self.trigger_date(bd["birth_date"], year)
            if trigger is None:
                continue
            delta = (trigger - today).days
            if 0 <= delta <= days_ahead:
                return BirthdayAlert(
                    name=bd["name"],
                    birth_date=bd["birth_date"],
                    gift_amount=float(bd["gift_amount"]),
                    trigger_date=trigger,
                    days_until=delta,
                )
        return None
