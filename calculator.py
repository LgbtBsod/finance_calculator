"""calculator.py — Чистая бизнес-логика (ЗП, ДР, баланс).

Не знает о БД — получает данные через Protocol'ы / callable.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
import calendar

from models import (
    BalanceResult,
    BirthdayAlert,
    BirthdayRow,
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

    Поддерживает три метода расчета:
    - proportional: фиксированные проценты (40%/60%) по настройке
    - custom_proportions: пользовательские пропорции из настроек
    - working_days: пропорционально рабочим дням в каждой половине месяца
    """

    def __init__(
        self,
        get_setting: Callable[[str], str],
        vacations: VacationReader | None = None,
        calendar_reader: Callable[[int, int], list] | None = None,
    ) -> None:
        self._get = get_setting
        self._vacs = vacations
        self._calendar_reader = calendar_reader

    def calculate(self, year: int, month: int) -> SalaryBreakdown:
        base = float(self._get("base_salary") or 0)
        tax = float(self._get("tax_rate") or 13)
        kef = float(self._get("kef") or 1.0)
        method = self._get("salary_calculation_method") or "proportional"

        # Расчет зарплаты после налогов и коэффициента
        net = base * kef * (1.0 - tax / 100.0)
        
        # Распределение по половинам месяца в зависимости от метода
        match method:
            case "working_days" if self._calendar_reader:
                advance_ratio, payout_ratio = self._calculate_by_working_days(year, month)
            case "custom_proportions":
                # Пользовательские пропорции из настроек
                first_half = float(self._get("first_half_ratio") or "0.4")
                second_half = float(self._get("second_half_ratio") or "0.6")
                # Нормализуем чтобы сумма была 1.0
                total = first_half + second_half
                match total:
                    case 0:
                        advance_ratio, payout_ratio = 0.4, 0.6
                    case _:
                        advance_ratio = first_half / total
                        payout_ratio = second_half / total
            case _:
                # Пропорциональный метод: 40% аванс, 60% основная выплата
                advance_ratio = 0.4
                payout_ratio = 0.6
        
        advance = net * advance_ratio
        payout = net * payout_ratio

        vac_h1, vac_h2 = self._distribute_vacations(year, month)

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

    def _calculate_by_working_days(
        self, year: int, month: int
    ) -> tuple[float, float]:
        """Расчет пропорций на основе рабочих дней.
        
        Возвращает (advance_ratio, payout_ratio).
        Считаем рабочие дни до 15 числа (включительно) и после.
        """
        cutoff_day = int(self._get("advance_cutoff_day") or 15)
        is_inclusive = self._get("is_advance_date_inclusive") == "true"
        
        match self._calendar_reader:
            case None:
                return 0.4, 0.6  # fallback
            case reader:
                cal_days = reader(year, month)
        
        match cal_days:
            case [] | None:
                return 0.4, 0.6  # fallback
            case days_list:
                first_half_days = 0
                second_half_days = 0
                
                for day_info in days_list:
                    day = day_info.get("day", 0)
                    is_working = day_info.get("is_working", True)
                    is_holiday = day_info.get("is_holiday", False)
                    
                    match (is_working, is_holiday):
                        case (False, _) | (_, True):
                            continue
                    
                    match is_inclusive:
                        case True if day <= cutoff_day:
                            first_half_days += 1
                        case True:
                            second_half_days += 1
                        case False if day < cutoff_day:
                            first_half_days += 1
                        case _:
                            second_half_days += 1
                
                total = first_half_days + second_half_days
                match total:
                    case 0:
                        return 0.4, 0.6
                    case _:
                        return first_half_days / total, second_half_days / total

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
        self, year: int, month: int
    ) -> tuple[float, float]:
        """Распределяет отпускные по половинам через VacationReader."""
        vacs = self._vacs.get_vacations(month, year)
        h1 = h2 = 0.0
        for v in vacs:
            try:
                vd = date.fromisoformat(v["payout_date"])
                amt = float(v["total_amount"])
                # Отпускные до 15 числа включительно - в первую половину, после - во вторую
                match vd.day <= 15:
                    case True:
                        h1 += amt
                    case False:
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
        match day:
            case None:
                return None
            case _:
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
            match alert:
                case None:
                    pass
                case _:
                    alerts.append(alert)
        alerts.sort(key=lambda a: a.days_until)
        return alerts

    def auto_create_expenses(
        self,
        birthdays: list[BirthdayRow],
        existing_expenses: list[ExpenseRow],
        add_expense_fn: Callable[..., None],
    ) -> int:
        """Создать расходы по триггерам ДР за текущий месяц. Возвращает кол-во."""
        today = date.today()
        created = 0
        for bd in birthdays:
            trigger = self.trigger_date(bd["birth_date"], today.year)
            match trigger:
                case None:
                    continue
                case t if t.year != today.year or t.month != today.month:
                    continue
            
            # Расходы до 15 числа включительно - в первую половину, после - во вторую
            half = 1 if trigger.day <= 15 else 2
            label = f"🎂 {bd['name']} (ДР {bd['birth_date']})"

            match any(e["name"] == label for e in existing_expenses):
                case True:
                    continue
                case False:
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
            match trigger:
                case None:
                    continue
                case _:
                    delta = (trigger - today).days
                    match 0 <= delta <= days_ahead:
                        case True:
                            return BirthdayAlert(
                                name=bd["name"],
                                birth_date=bd["birth_date"],
                                gift_amount=float(bd["gift_amount"]),
                                trigger_date=trigger,
                                days_until=delta,
                            )
                        case False:
                            pass
        return None
