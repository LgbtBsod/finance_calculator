"""calculator.py — Чистая бизнес-логика (ЗП, ДР, баланс).

Не знает о БД — получает данные через Protocol'ы / callable.
"""

from __future__ import annotations

import calendar as cal_lib
from collections.abc import Callable
from datetime import date, timedelta

from models import (
    BalanceResult,
    BirthdayAlert,
    BirthdayRow,
    CalendarReader,
    DayKind,
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
        calendar_reader: CalendarReader | None = None,
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

        wd_h1 = wd_h2 = wd_total = None
        cutoff_day = None

        # Распределение по половинам месяца в зависимости от метода
        match method:
            case "working_days" if self._calendar_reader:
                wd_h1, wd_h2, wd_total = self._working_days_breakdown(year, month)
                cutoff_day = int(self._get("advance_cutoff_day") or 15)
                match wd_total:
                    case 0:
                        advance_ratio, payout_ratio = 0.4, 0.6  # fallback
                    case _:
                        advance_ratio, payout_ratio = wd_h1 / wd_total, wd_h2 / wd_total
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
        nominal_1, nominal_2 = self.nominal_payout_dates(year, month)
        payout_date_1 = self._roll_back_to_working_day(nominal_1)
        payout_date_2 = self._roll_back_to_working_day(nominal_2)

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
            payout_date_1=payout_date_1.isoformat(),
            payout_date_2=payout_date_2.isoformat(),
            payout_date_1_nominal=nominal_1.isoformat(),
            payout_date_2_nominal=nominal_2.isoformat(),
            calculation_method=method,
            working_days_half_1=wd_h1,
            working_days_half_2=wd_h2,
            working_days_total=wd_total,
            advance_cutoff_day=cutoff_day,
        )

    def _working_days_breakdown(self, year: int, month: int) -> tuple[float, float, float]:
        """Рабочие дни каждой половины месяца (после вычета дней отпуска).

        Возвращает (h1, h2, total) по данным производственного календаря
        (CalendarReader.get_working_days), который уже учитывает cutoff_day /
        сокращённые дни через свои собственные настройки — дублировать эту
        логику здесь не нужно (DRY). Используется и для пропорции выплаты,
        и для отображения "как посчитано" на фронтенде.

        Дни отпуска, попавшие в этот месяц, вычитаются из отработанных дней
        каждой половины — ровно так же, как в исходной таблице финансового
        менеджера (там это было ручной коррекцией G7=G2-G5, H7=H2-H5).
        Сама выплата отпускных при этом остаётся отдельной надбавкой
        (см. _distribute_vacations) — здесь мы только уменьшаем базу для
        расчёта обычной зарплаты за отработанное время.
        """
        match self._calendar_reader:
            case None:
                return 0.0, 0.0, 0.0
            case reader:
                total, h1, h2 = reader.get_working_days(year, month)

        vac_h1, vac_h2 = self._vacation_working_days(year, month)
        h1 = max(0.0, h1 - vac_h1)
        h2 = max(0.0, h2 - vac_h2)
        return h1, h2, h1 + h2

    # ── даты выплат ──────────────────────────────────────────────

    def payout_dates(self, year: int, month: int) -> tuple[date, date]:
        """Реальные (возможно перенесённые) даты выплат — см. nominal_payout_dates
        для номинальных дат до переноса."""
        nominal_1, nominal_2 = self.nominal_payout_dates(year, month)
        return self._roll_back_to_working_day(nominal_1), self._roll_back_to_working_day(nominal_2)

    def nominal_payout_dates(self, year: int, month: int) -> tuple[date, date]:
        """Номинальные даты выплат (день 1 / день 2 из настроек) БЕЗ переноса
        на рабочий день — используются, чтобы показать пользователю, что
        дата была сдвинута (и с какой на какую)."""
        day1 = int(self._get("payout_day1") or 10)
        day2 = int(self._get("payout_day2") or 25)
        return self._clamp_to_month(year, month, day1), self._clamp_to_month(year, month, day2)

    @staticmethod
    def _clamp_to_month(year: int, month: int, day: int) -> date:
        _, last_day = cal_lib.monthrange(year, month)
        return date(year, month, min(max(day, 1), last_day))

    def _roll_back_to_working_day(self, d: date) -> date:
        """Если move_weekend_to_friday включён и d — выходной/праздник,
        переносит на ближайший более ранний рабочий день (10 число —
        субботa -> перенос на 8/9)."""
        should_move = self._get("move_weekend_to_friday") == "true"
        if not should_move or self._calendar_reader is None:
            return d

        while self._calendar_reader.classify_day(d) not in (DayKind.WORKING, DayKind.SHORTENED):
            d -= timedelta(days=1)
        return d

    def _vacation_working_days(self, year: int, month: int) -> tuple[float, float]:
        """Сколько рабочих дней отпуска пришлось на каждую половину месяца."""
        if self._vacs is None or self._calendar_reader is None:
            return 0.0, 0.0

        cutoff_day = int(self._get("advance_cutoff_day") or 15)
        is_inclusive = self._get("is_advance_date_inclusive") == "true"

        h1 = h2 = 0.0
        for v in self._vacs.get_vacations(month, year):
            try:
                start = date.fromisoformat(v.get("start_date") or v["payout_date"])
                end = date.fromisoformat(v.get("end_date") or v["payout_date"])
            except (ValueError, TypeError, KeyError):
                continue

            d = start
            while d <= end:
                if d.year == year and d.month == month:
                    kind = self._calendar_reader.classify_day(d)
                    if kind in (DayKind.WORKING, DayKind.SHORTENED):
                        in_first_half = d.day <= cutoff_day if is_inclusive else d.day < cutoff_day
                        if in_first_half:
                            h1 += 1
                        else:
                            h2 += 1
                d += timedelta(days=1)
        return h1, h2

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

    def _distribute_vacations(self, year: int, month: int) -> tuple[float, float]:
        """Распределяет отпускные по половинам через VacationReader."""
        if self._vacs is None:
            return 0.0, 0.0
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

    def trigger_date(self, birth_date: str, ref_year: int) -> date | None:
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

    def gift_expense_period(
        self, birth_day: int, birth_month: int, ref_year: int
    ) -> tuple[int, int, int]:
        """К какой выплате отнести расход на подарок: к ближайшей ПРЕДЫДУЩЕЙ
        (относительно даты ДР) дате выплаты — деньги должны быть на руках
        заранее, а не только с этой же выплаты.

        Пример при payout_day1=10, payout_day2=25: ДР 10-го числа -> деньги
        нужны ДО 10-го, а не с выплаты В 10-е — значит расход относится к
        выплате 25-го ПРЕДЫДУЩЕГО месяца. ДР 11-го -> уже успевает выплата
        10-го этого же месяца.

        Возвращает (half, month, year) — half=1 соответствует payout_day1
        (аванс), half=2 — payout_day2 (осн. выплата), т.к. именно в этом
        соответствии Expense.half используется при вычитании из баланса
        (см. SalaryCalculator.balance).
        """
        day1 = int(self._get("payout_day1") or 10)
        day2 = int(self._get("payout_day2") or 25)

        birthday_marker = date(ref_year, birth_month, birth_day)

        candidates: list[tuple[date, int, int, int]] = []
        for month_offset in (0, -1):
            m = birth_month + month_offset
            y = ref_year
            while m < 1:
                m += 12
                y -= 1
            _, last_day = cal_lib.monthrange(y, m)
            for day, half in ((day1, 1), (day2, 2)):
                clamped = min(max(day, 1), last_day)
                candidates.append((date(y, m, clamped), half, m, y))

        prior = [c for c in candidates if c[0] < birthday_marker]
        chosen = max(prior, key=lambda c: c[0]) if prior else min(candidates, key=lambda c: c[0])
        _, half, month, year = chosen
        return half, month, year

    def auto_create_expenses(
        self,
        birthdays: list[BirthdayRow],
        existing_expenses: list[ExpenseRow],
        add_expense_fn: Callable[..., None],
        today: date | None = None,
    ) -> int:
        """Создать расходы на подарки для ближайшего наступления каждого ДР,
        если период выплаты, к которому он относится (см.
        gift_expense_period), — текущий месяц. Возвращает количество.

        `today` внедряется явно (а не читается из date.today() неявно)
        именно для тестируемости — тест не должен зависеть от реальной
        календарной даты запуска."""
        today = today or date.today()
        created = 0
        for bd in birthdays:
            day, month = self._parse_bd(bd["birth_date"])
            if day is None or month is None:
                continue

            try:
                occurrence = date(today.year, month, day)
            except ValueError:
                continue
            if occurrence < today:
                try:
                    occurrence = date(today.year + 1, month, day)
                except ValueError:
                    continue

            half, exp_month, exp_year = self.gift_expense_period(day, month, occurrence.year)
            if (exp_month, exp_year) != (today.month, today.year):
                continue  # относится не к текущему месяцу — пока не создаём

            label = f"🎂 {bd['name']} (ДР {bd['birth_date']})"
            already_exists = any(
                e["name"] == label and e["month"] == exp_month and e["year"] == exp_year
                for e in existing_expenses
            )
            if already_exists:
                continue

            add_expense_fn(
                name=label,
                amount=float(bd["gift_amount"]),
                half=half,
                month=exp_month,
                year=exp_year,
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

    def _check_one(self, bd: dict, today: date, days_ahead: int) -> BirthdayAlert | None:
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
