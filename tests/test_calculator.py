"""test_calculator.py — SalaryCalculator и BirthdayService.

Главный тест здесь — test_working_days_matches_reference_spreadsheet:
он закрепляет числа из реальной таблицы финансового менеджера (июль 2025,
121003 ₽ оклада), на основе которой строился этот калькулятор. До
автоматизации подсчёта рабочих дней таблица требовала ручного ввода
G2/H2 и давала расхождения (тот самый "0.1% погрешности") — этот тест
доказывает, что автоматический расчёт через производственный календарь
воспроизводит эталонные суммы точно.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from calculator import SalaryCalculator
from database import DatabaseManager
from models import DayKind

# Эталонные значения из реальной таблицы (Лист1, строки 1-7):
# D2=121003 (оклад), кэф пуст -> 1.0, налог 13% (хардкод *0.87 в таблице)
# F2=23 (G2=11 + H2=12), I2=50347.77 (аванс), J2=54924.84 (выплата)
REFERENCE_BASE_SALARY = 121003.0
REFERENCE_NET_SALARY = 105272.61  # 121003 * 0.87, округлено как в таблице
REFERENCE_ADVANCE = 50347.77
REFERENCE_PAYOUT = 54924.84


def _set_common_settings(db: DatabaseManager, method: str) -> None:
    db.set_setting("base_salary", str(REFERENCE_BASE_SALARY))
    db.set_setting("tax_rate", "13")
    db.set_setting("kef", "1.0")
    db.set_setting("salary_calculation_method", method)
    db.set_setting("advance_cutoff_day", "15")
    db.set_setting("is_advance_date_inclusive", "true")


class _FakeCalendarReader:
    """Минимальная реализация Protocol'а CalendarReader (см. models.py) —
    без реального производственного календаря, чтобы тесты ниже не зависели
    от данных конкретного года/месяца."""

    def __init__(
        self,
        working_days: tuple[float, float, float] = (23.0, 11.0, 12.0),
        day_kind: DayKind = DayKind.WORKING,
    ) -> None:
        self._working_days = working_days
        self._day_kind = day_kind

    def get_working_days(self, year: int, month: int) -> tuple[float, float, float]:
        return self._working_days

    def classify_day(self, d: date) -> DayKind:
        return self._day_kind


class _FakeVacationReader:
    """Минимальная реализация Protocol'а VacationReader (см. models.py) —
    отдаёт заранее заданный список отпусков, минуя SQL-фильтрацию по датам
    (важно для теста с некорректной строкой даты — SQLite strftime() на
    невалидной дате просто вернул бы NULL и строка вовсе не попала бы в
    выборку, а нам нужно проверить обработку внутри самого калькулятора)."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def get_vacations(self, month: int | None = None, year: int | None = None) -> list[dict]:
        return self._rows


class TestProportionalMethod:
    def test_default_40_60_split(self, calculator: SalaryCalculator, db: DatabaseManager):
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "13")
        db.set_setting("kef", "1.0")
        db.set_setting("salary_calculation_method", "proportional")

        result = calculator.calculate(2026, 8)

        assert result.net_salary == pytest.approx(87000.0)
        assert result.advance == pytest.approx(34800.0)
        assert result.payout == pytest.approx(52200.0)
        assert result.advance + result.payout == pytest.approx(result.net_salary)

    def test_kef_multiplies_net_salary(self, calculator: SalaryCalculator, db: DatabaseManager):
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "13")
        db.set_setting("kef", "1.2")
        db.set_setting("salary_calculation_method", "proportional")

        result = calculator.calculate(2026, 8)

        assert result.net_salary == pytest.approx(100000 * 1.2 * 0.87)


class TestCustomProportionsMethod:
    def test_normalizes_ratios_that_dont_sum_to_one(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "0")
        db.set_setting("kef", "1.0")
        db.set_setting("salary_calculation_method", "custom_proportions")
        db.set_setting("first_half_ratio", "0.2")
        db.set_setting("second_half_ratio", "0.3")

        result = calculator.calculate(2026, 8)

        # 0.2/0.5=0.4, 0.3/0.5=0.6 — нормализовано к сумме 1.0
        assert result.advance == pytest.approx(40000.0)
        assert result.payout == pytest.approx(60000.0)

    def test_falls_back_to_40_60_when_both_ratios_zero(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "0")
        db.set_setting("salary_calculation_method", "custom_proportions")
        db.set_setting("first_half_ratio", "0")
        db.set_setting("second_half_ratio", "0")

        result = calculator.calculate(2026, 8)

        assert result.advance == pytest.approx(40000.0)
        assert result.payout == pytest.approx(60000.0)


class TestWorkingDaysMethod:
    def test_matches_reference_spreadsheet_july_2025(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        """Регрессия по реальным данным финансового менеджера — см. докстринг модуля."""
        _set_common_settings(db, "working_days")

        result = calculator.calculate(2025, 7)

        assert result.net_salary == pytest.approx(REFERENCE_NET_SALARY, abs=0.01)
        assert result.advance == pytest.approx(REFERENCE_ADVANCE, abs=0.01)
        assert result.payout == pytest.approx(REFERENCE_PAYOUT, abs=0.01)
        assert result.to_pay_half_1 == pytest.approx(REFERENCE_ADVANCE, abs=0.01)
        assert result.to_pay_half_2 == pytest.approx(REFERENCE_PAYOUT, abs=0.01)

    def test_exposes_day_count_breakdown_for_transparency(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        """Разбивка по дням должна быть видна фронтенду — как посчитали 11/12/23."""
        _set_common_settings(db, "working_days")

        result = calculator.calculate(2025, 7)

        assert result.calculation_method == "working_days"
        assert result.working_days_half_1 == pytest.approx(11.0)
        assert result.working_days_half_2 == pytest.approx(12.0)
        assert result.working_days_total == pytest.approx(23.0)
        assert result.advance_cutoff_day == 15

    def test_day_count_breakdown_absent_for_other_methods(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("base_salary", "100000")
        db.set_setting("salary_calculation_method", "proportional")

        result = calculator.calculate(2026, 8)

        assert result.calculation_method == "proportional"
        assert result.working_days_half_1 is None
        assert result.working_days_half_2 is None
        assert result.working_days_total is None
        assert result.advance_cutoff_day is None

    def test_vacation_days_reduce_salary_pro_rata_tk_rf(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        """ТК РФ: 3 рабочих дня отпуска (7-9 июля 2025, пн-ср). За эти дни
        платят отпускные, а не оклад — поэтому оклад за месяц уменьшается
        пропорционально: net * 20/23 (отработано 20 из 23 норм. дней), и
        уже эта сумма делится по половинам. Отпускные — отдельная надбавка."""
        _set_common_settings(db, "working_days")
        db.add_vacation(
            total_amount=15000.0,
            payout_date="2025-07-04",
            start_date="2025-07-07",
            end_date="2025-07-09",
        )

        result = calculator.calculate(2025, 7)

        # norm (11,12,23) -> worked (8,12,20); net за месяц = net * 20/23
        net_worked = REFERENCE_NET_SALARY * (20 / 23)
        expected_advance = net_worked * (8 / 20)
        expected_payout = net_worked * (12 / 20)
        assert result.advance == pytest.approx(expected_advance, abs=0.01)
        assert result.payout == pytest.approx(expected_payout, abs=0.01)
        assert result.net_salary == pytest.approx(net_worked, abs=0.01)
        assert result.working_days_total == pytest.approx(20.0)
        assert result.vacation_half_1 == pytest.approx(15000.0)
        assert result.vacation_half_2 == pytest.approx(0.0)
        assert result.to_pay_half_1 == pytest.approx(expected_advance + 15000.0, abs=0.01)
        # весь оклад за отработанное + отпускные
        assert result.total_accrued == pytest.approx(net_worked + 15000.0, abs=0.01)

    def test_weekend_vacation_days_dont_reduce_worked_days(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        """Отпуск на выходных (12-13 июля 2025, сб-вс) не меняет рабочие дни,
        потому что эти дни и так не считались отработанными."""
        _set_common_settings(db, "working_days")
        db.add_vacation(
            total_amount=5000.0,
            payout_date="2025-07-12",
            start_date="2025-07-12",
            end_date="2025-07-13",
        )

        result = calculator.calculate(2025, 7)

        assert result.advance == pytest.approx(REFERENCE_ADVANCE, abs=0.01)
        assert result.payout == pytest.approx(REFERENCE_PAYOUT, abs=0.01)

    def test_falls_back_to_40_60_without_calendar_reader(self, db: DatabaseManager):
        _set_common_settings(db, "working_days")
        calc = SalaryCalculator(get_setting=db.get_setting, vacations=db, calendar_reader=None)

        result = calc.calculate(2025, 7)

        assert result.advance == pytest.approx(REFERENCE_NET_SALARY * 0.4, abs=0.01)
        assert result.payout == pytest.approx(REFERENCE_NET_SALARY * 0.6, abs=0.01)

    def test_falls_back_to_40_60_when_calendar_reports_all_zero_days(self, db: DatabaseManager):
        """Если CalendarReader.get_working_days() вернул (0.0, 0.0, 0.0)
        (например, пустой/незаполненный производственный календарь на этот
        месяц), calculate() должен деградировать к fallback 40/60 — см.
        `match wd_total: case 0: ...` в calculator.py — а не упасть с
        ZeroDivisionError и не вернуть NaN."""
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "0")
        db.set_setting("salary_calculation_method", "working_days")
        fake_calendar = _FakeCalendarReader(working_days=(0.0, 0.0, 0.0))
        calc = SalaryCalculator(
            get_setting=db.get_setting, vacations=db, calendar_reader=fake_calendar
        )

        result = calc.calculate(2026, 8)  # не должно бросить ZeroDivisionError

        assert result.working_days_total == 0.0
        assert result.advance == pytest.approx(40000.0)
        assert result.payout == pytest.approx(60000.0)
        assert not math.isnan(result.advance)
        assert not math.isnan(result.payout)


class TestMalformedVacationDates:
    """Битая дата в записи об отпуске (повреждённые данные, ручное
    редактирование БД и т.п.) не должна ронять весь расчёт зарплаты —
    _distribute_vacations и _vacation_working_days ловят ValueError/TypeError
    при разборе даты и пропускают такую запись (см. try/except в
    calculator.py). Тест закрепляет это СУЩЕСТВУЮЩЕЕ защитное поведение."""

    def test_malformed_payout_date_is_skipped_by_distribute_vacations(self, db: DatabaseManager):
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "0")
        db.set_setting("salary_calculation_method", "proportional")
        bad_vacation = {
            "id": 1,
            "total_amount": 5000.0,
            "payout_date": "not-a-date",
            "start_date": "not-a-date",
            "end_date": "not-a-date",
        }
        calc = SalaryCalculator(
            get_setting=db.get_setting,
            vacations=_FakeVacationReader([bad_vacation]),
            calendar_reader=None,
        )

        result = calc.calculate(2026, 8)  # не должно бросить исключение

        assert result.vacation_half_1 == 0.0
        assert result.vacation_half_2 == 0.0

    def test_malformed_start_date_is_skipped_by_vacation_working_days(self, db: DatabaseManager):
        """Метод working_days дополнительно прогоняет отпуска через
        _vacation_working_days (вычитание из отработанных дней) — та же
        битая дата должна быть пропущена и там."""
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "0")
        db.set_setting("salary_calculation_method", "working_days")
        db.set_setting("advance_cutoff_day", "15")
        bad_vacation = {
            "id": 1,
            "total_amount": 5000.0,
            "payout_date": "2026-08-04",
            "start_date": "not-a-date",
            "end_date": "not-a-date",
        }
        fake_calendar = _FakeCalendarReader(working_days=(23.0, 11.0, 12.0))
        calc = SalaryCalculator(
            get_setting=db.get_setting,
            vacations=_FakeVacationReader([bad_vacation]),
            calendar_reader=fake_calendar,
        )

        result = calc.calculate(2026, 8)  # не должно бросить исключение

        # start_date/end_date не распарсились -> _vacation_working_days не
        # вычитает ничего из рабочих дней -> база осталась (11, 12).
        assert result.working_days_half_1 == pytest.approx(11.0)
        assert result.working_days_half_2 == pytest.approx(12.0)
        # payout_date распарсился нормально (2026-08-04, до 15-го) ->
        # _distribute_vacations (читает payout_date) всё же отнёс отпускные
        # в первую половину, хотя _vacation_working_days (читает start/end)
        # эту же запись пропустил — методы читают разные поля записи, так
        # что "частично битая" запись обрабатывается каждым по-своему.
        assert result.vacation_half_1 == pytest.approx(5000.0)
        assert result.vacation_half_2 == 0.0


class TestBalance:
    def test_balance_subtracts_expenses_per_half(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("base_salary", "100000")
        db.set_setting("tax_rate", "13")
        db.set_setting("kef", "1.0")
        db.set_setting("salary_calculation_method", "proportional")

        expenses = [
            {
                "id": 1,
                "name": "Продукты",
                "amount": 5000.0,
                "half": 1,
                "month": 8,
                "year": 2026,
                "is_recurring": False,
                "group_id": None,
            },
            {
                "id": 2,
                "name": "Бензин",
                "amount": 2000.0,
                "half": 2,
                "month": 8,
                "year": 2026,
                "is_recurring": False,
                "group_id": None,
            },
        ]

        result = calculator.balance(2026, 8, expenses)

        assert result.expenses_h1 == pytest.approx(5000.0)
        assert result.expenses_h2 == pytest.approx(2000.0)
        assert result.balance_h1 == pytest.approx(34800.0 - 5000.0)
        assert result.balance_h2 == pytest.approx(52200.0 - 2000.0)


class TestBirthdayService:
    def test_trigger_date_is_14_days_before_birthday(self, birthday_service):
        trigger = birthday_service.trigger_date("15.03.2025", 2025)
        assert trigger == date(2025, 3, 1)

    def test_trigger_date_handles_year_boundary(self, birthday_service):
        # ДР 5 января -> триггер 22 декабря ПРЕДЫДУЩЕГО года
        trigger = birthday_service.trigger_date("05.01.2025", 2025)
        assert trigger == date(2024, 12, 22)

    def test_upcoming_finds_birthday_within_window(self, birthday_service):
        today = date.today()
        # Подбираем ДР так, чтобы триггер был точно "через 5 дней" от сегодня
        from datetime import timedelta

        bd_date = today + timedelta(days=5 + 14)
        birthdays = [
            {
                "id": 1,
                "name": "Тест",
                "birth_date": bd_date.strftime("%d.%m.%Y"),
                "gift_amount": 3000.0,
            }
        ]

        alerts = birthday_service.upcoming(birthdays, days_ahead=30)

        assert len(alerts) == 1
        assert alerts[0].name == "Тест"
        assert alerts[0].days_until == 5

    def test_upcoming_ignores_birthday_outside_window(self, birthday_service):
        from datetime import timedelta

        far_future = date.today() + timedelta(days=200)
        birthdays = [
            {
                "id": 1,
                "name": "Далеко",
                "birth_date": far_future.strftime("%d.%m.%Y"),
                "gift_amount": 1000.0,
            }
        ]

        alerts = birthday_service.upcoming(birthdays, days_ahead=30)

        assert alerts == []

    def test_auto_create_expenses_is_idempotent(self, birthday_service):
        # ДР 11 августа -> относится к выплате 10 августа (см. gift_expense_period)
        today = date(2026, 8, 1)
        birthdays = [{"id": 1, "name": "Иванов", "birth_date": "11.08.2030", "gift_amount": 2000.0}]

        created_expenses = []

        def add_expense_fn(**kwargs):
            created_expenses.append(kwargs)

        count1 = birthday_service.auto_create_expenses(birthdays, [], add_expense_fn, today=today)
        assert count1 == 1
        assert created_expenses[0]["half"] == 1
        assert created_expenses[0]["month"] == 8
        assert created_expenses[0]["year"] == 2026

        # Повторный вызов с уже существующим расходом (тем же месяцем/годом) — не дублирует
        existing = [
            {
                "id": 1,
                "name": created_expenses[0]["name"],
                "amount": 2000.0,
                "half": created_expenses[0]["half"],
                "month": 8,
                "year": 2026,
                "is_recurring": False,
                "group_id": None,
            }
        ]
        count2 = birthday_service.auto_create_expenses(
            birthdays, existing, add_expense_fn, today=today
        )
        assert count2 == 0
        assert len(created_expenses) == 1

    def test_auto_create_expenses_skips_birthdays_outside_current_month(self, birthday_service):
        today = date(2026, 8, 1)
        # ДР 20 сентября -> относится к выплате 10 сентября — не текущий месяц
        birthdays = [{"id": 1, "name": "Далеко", "birth_date": "20.09.2030", "gift_amount": 1000.0}]

        created = []
        count = birthday_service.auto_create_expenses(
            birthdays, [], lambda **kw: created.append(kw), today=today
        )

        assert count == 0
        assert created == []


class TestBirthdayServiceMalformedInput:
    """_parse_bd ловит ValueError/IndexError при разборе "ДД.ММ" и
    возвращает (None, None) — все точки входа, использующие его, должны
    молча пропустить такую запись, а не бросить исключение наружу."""

    def test_trigger_date_returns_none_for_malformed_birth_date(self, birthday_service):
        assert birthday_service.trigger_date("not-a-date", 2026) is None

    def test_upcoming_skips_malformed_entry_without_raising(self, birthday_service):
        birthdays = [
            {"id": 1, "name": "Битый", "birth_date": "not-a-date", "gift_amount": 500.0},
        ]

        alerts = birthday_service.upcoming(birthdays, days_ahead=30)  # не должно бросить исключение

        assert alerts == []

    def test_upcoming_processes_valid_entries_alongside_a_malformed_one(self, birthday_service):
        """Одна битая запись не должна портить обработку остальных в списке."""
        from datetime import timedelta

        today = date.today()
        good_bd = (today + timedelta(days=5 + 14)).strftime("%d.%m.%Y")
        birthdays = [
            {"id": 1, "name": "Битый", "birth_date": "not-a-date", "gift_amount": 500.0},
            {"id": 2, "name": "Хороший", "birth_date": good_bd, "gift_amount": 1000.0},
        ]

        alerts = birthday_service.upcoming(birthdays, days_ahead=30)

        assert len(alerts) == 1
        assert alerts[0].name == "Хороший"

    def test_auto_create_expenses_skips_malformed_birth_date_without_raising(
        self, birthday_service
    ):
        birthdays = [
            {"id": 1, "name": "Битый", "birth_date": "not-a-date", "gift_amount": 500.0},
        ]
        created = []

        count = birthday_service.auto_create_expenses(
            birthdays, [], lambda **kw: created.append(kw), today=date(2026, 8, 1)
        )  # не должно бросить исключение

        assert count == 0
        assert created == []


class TestGiftExpensePeriod:
    """SalaryCalculator.payout_day1/2 по умолчанию 10/25 (см. фикстуру db)."""

    def test_birthday_on_payout_day_falls_back_to_previous_period(self, birthday_service):
        # ДР ровно 10-го — деньги с выплаты 10-го ещё не успевают, поэтому
        # относим к предыдущей выплате (25 июля).
        half, month, year = birthday_service.gift_expense_period(10, 8, 2026)
        assert (half, month, year) == (2, 7, 2026)

    def test_birthday_just_after_payout_day1_uses_this_months_payout1(self, birthday_service):
        half, month, year = birthday_service.gift_expense_period(11, 8, 2026)
        assert (half, month, year) == (1, 8, 2026)

    def test_birthday_just_after_payout_day2_uses_this_months_payout2(self, birthday_service):
        half, month, year = birthday_service.gift_expense_period(26, 8, 2026)
        assert (half, month, year) == (2, 8, 2026)

    def test_birthday_early_in_month_falls_back_to_previous_months_payout2(self, birthday_service):
        half, month, year = birthday_service.gift_expense_period(3, 8, 2026)
        assert (half, month, year) == (2, 7, 2026)

    def test_handles_january_year_boundary(self, birthday_service):
        # ДР 5 января -> нет более ранней выплаты в январе -> декабрь
        # предыдущего года.
        half, month, year = birthday_service.gift_expense_period(5, 1, 2026)
        assert (half, month, year) == (2, 12, 2025)


class TestPayoutDates:
    def test_returns_nominal_dates_when_move_disabled(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("payout_day1", "10")
        db.set_setting("payout_day2", "25")
        db.set_setting("move_weekend_to_friday", "false")

        d1, d2 = calculator.payout_dates(2026, 1)

        assert d1 == date(2026, 1, 10)
        assert d2 == date(2026, 1, 25)

    def test_rolls_back_to_earlier_working_day_when_enabled(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        """Регрессия на реальных данных календаря января 2026: расширенные
        новогодние каникулы толкают день 10 аж в декабрь 2025 (пересечение
        границы года), а день 25 — на пятницу 23-го."""
        db.set_setting("payout_day1", "10")
        db.set_setting("payout_day2", "25")
        db.set_setting("move_weekend_to_friday", "true")

        d1, d2 = calculator.payout_dates(2026, 1)

        assert d1 == date(2025, 12, 30)
        assert d2 == date(2026, 1, 23)

    def test_included_in_salary_breakdown(self, calculator: SalaryCalculator, db: DatabaseManager):
        db.set_setting("base_salary", "100000")
        db.set_setting("payout_day1", "10")
        db.set_setting("payout_day2", "25")
        db.set_setting("move_weekend_to_friday", "true")

        result = calculator.calculate(2026, 1)

        assert result.payout_date_1 == "2025-12-30"
        assert result.payout_date_2 == "2026-01-23"
        # Номинальные даты (до переноса) — отличаются от фактических,
        # это и есть сигнал "дата была сдвинута" для фронтенда.
        assert result.payout_date_1_nominal == "2026-01-10"
        assert result.payout_date_2_nominal == "2026-01-25"

    def test_nominal_equals_actual_when_move_disabled(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("base_salary", "100000")
        db.set_setting("payout_day1", "10")
        db.set_setting("payout_day2", "25")
        db.set_setting("move_weekend_to_friday", "false")

        result = calculator.calculate(2026, 1)

        assert result.payout_date_1 == result.payout_date_1_nominal == "2026-01-10"
        assert result.payout_date_2 == result.payout_date_2_nominal == "2026-01-25"

    def test_clamps_day_to_last_day_of_month(
        self, calculator: SalaryCalculator, db: DatabaseManager
    ):
        db.set_setting("payout_day1", "31")
        db.set_setting("payout_day2", "25")
        db.set_setting("move_weekend_to_friday", "false")

        d1, _ = calculator.payout_dates(2026, 4)  # апрель — 30 дней

        assert d1 == date(2026, 4, 30)

    def test_no_calendar_reader_returns_nominal_date(self, db: DatabaseManager):
        db.set_setting("payout_day1", "10")
        db.set_setting("move_weekend_to_friday", "true")
        calc = SalaryCalculator(get_setting=db.get_setting, vacations=db, calendar_reader=None)

        d1, _ = calc.payout_dates(2026, 1)

        assert d1 == date(2026, 1, 10)
