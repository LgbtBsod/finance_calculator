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
    "progressive_ndfl",
]

# Прогрессивная шкала НДФЛ РФ с 2025 (годовой накопленный доход -> предельная
# ставка сверх порога). Ст. 224 НК РФ в ред. с 01.01.2025.
_NDFL_BRACKETS_2025: tuple[tuple[float, float], ...] = (
    (0.0, 0.13),
    (2_400_000.0, 0.15),
    (5_000_000.0, 0.18),
    (20_000_000.0, 0.20),
    (50_000_000.0, 0.22),
)


def progressive_ndfl(annual_gross: float) -> float:
    """НДФЛ с годового дохода ``annual_gross`` по прогрессивной шкале 2025."""
    tax = 0.0
    for i, (threshold, rate) in enumerate(_NDFL_BRACKETS_2025):
        if annual_gross <= threshold:
            break
        upper = (
            _NDFL_BRACKETS_2025[i + 1][0]
            if i + 1 < len(_NDFL_BRACKETS_2025)
            else float("inf")
        )
        tax += (min(annual_gross, upper) - threshold) * rate
    return tax


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

        # Полный оклад за месяц после налога и коэффициента (норма).
        gross = base * kef
        if self._get("tax_progressive") == "true":
            # Предельный налог именно этого месяца: НДФЛ с дохода нарастающим
            # итогом ПО этот месяц минус НДФЛ по ПРЕДЫДУЩИЙ (оклад считаем
            # постоянным в течение года).
            ytd_now = progressive_ndfl(gross * month)
            ytd_before = progressive_ndfl(gross * (month - 1))
            net = gross - (ytd_now - ytd_before)
        else:
            net = gross * (1.0 - tax / 100.0)

        wd_h1 = wd_h2 = wd_total = None
        cutoff_day = None

        # ТК РФ: за дни отпуска платят отпускные, а не оклад — оклад за месяц
        # уменьшается пропорционально отработанным дням. Это правило от метода
        # распределения не зависит: применяем ко ВСЕМ методам, если доступен
        # производственный календарь и в месяце реально есть рабочие дни
        # отпуска. Отпускные добавляются отдельно (см. _distribute_vacations).
        vac_wd_h1, vac_wd_h2 = self._vacation_working_days(year, month)
        if (vac_wd_h1 + vac_wd_h2) > 0 and self._calendar_reader is not None:
            norm_total, _, _ = self._calendar_reader.get_working_days(year, month)
            if norm_total > 0:
                worked = max(0.0, norm_total - vac_wd_h1 - vac_wd_h2)
                net = net * worked / norm_total

        # Распределение по половинам месяца в зависимости от метода
        match method:
            case "working_days" if self._calendar_reader:
                _, norm_h1, norm_h2 = self._calendar_reader.get_working_days(year, month)
                wd_h1 = max(0.0, norm_h1 - vac_wd_h1)
                wd_h2 = max(0.0, norm_h2 - vac_wd_h2)
                wd_total = wd_h1 + wd_h2
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

    def _day_in_first_half(self, day: int) -> bool:
        """К какой половине месяца отнести число ``day`` — по дню отсечения
        аванса из настроек (а не по захардкоженному 15-му). SSOT границы
        половины: используется и для рабочих дней отпуска, и для отпускных."""
        cutoff = int(self._get("advance_cutoff_day") or 15)
        inclusive = self._get("is_advance_date_inclusive") == "true"
        return day <= cutoff if inclusive else day < cutoff

    def _vacation_working_days(self, year: int, month: int) -> tuple[float, float]:
        """Сколько рабочих дней отпуска пришлось на каждую половину месяца."""
        if self._vacs is None or self._calendar_reader is None:
            return 0.0, 0.0

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
                        if self._day_in_first_half(d.day):
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
                # По дню отсечения аванса (как рабочие дни отпуска), а не по 15-му.
                if self._day_in_first_half(vd.day):
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

    @staticmethod
    def _occurrence(year: int, month: int, day: int) -> date | None:
        """Дата наступления ДР в конкретном году. 29 февраля в невисокосный
        год переносим на 28-е (иначе алерт и авто-подарок молча пропадали
        бы каждый невисокосный год)."""
        try:
            return date(year, month, day)
        except ValueError:
            if (month, day) == (2, 29):
                return date(year, 2, 28)
            return None

    def trigger_date(self, birth_date: str, ref_year: int) -> date | None:
        """Триггер = ДР в ref_year - 14 дней. Учитывает переход через год."""
        day, month = self._parse_bd(birth_date)
        if day is None or month is None:
            return None
        bd = self._occurrence(ref_year, month, day)
        return None if bd is None else bd - timedelta(days=self.TRIGGER_DAYS_BEFORE)

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

        birthday_marker = self._occurrence(ref_year, birth_month, birth_day) or date(
            ref_year, birth_month, 28
        )

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

            occurrence = self._occurrence(today.year, month, day)
            if occurrence is None:
                continue
            if occurrence < today:
                occurrence = self._occurrence(today.year + 1, month, day)
                if occurrence is None:
                    continue

            # occurrence.day/.month — уже с поправкой 29.02 -> 28.02, поэтому
            # gift_expense_period не упрётся в невалидную дату.
            half, exp_month, exp_year = self.gift_expense_period(
                occurrence.day, occurrence.month, occurrence.year
            )
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
