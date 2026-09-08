"""test_database.py — CRUD-операции фасада ``Database`` (пакет ``db``) на
изолированной in-memory БД. Слоёная раскладка db/ этих тестов не касается —
поверхность методов сохранена 1-в-1."""

from __future__ import annotations

import pytest

from db import DatabaseManager


class TestSettings:
    def test_set_and_get_roundtrip(self, db: DatabaseManager):
        db.set_setting("base_salary", "150000")
        assert db.get_setting("base_salary") == "150000"

    def test_get_missing_setting_returns_empty_string(self, db: DatabaseManager):
        assert db.get_setting("does_not_exist") == ""

    def test_seeded_defaults_present_on_init(self, db: DatabaseManager):
        # _seed_defaults запускается в __init__ через _init_db
        assert db.get_setting("tax_rate") == "13.0"
        assert db.get_setting("advance_cutoff_day") == "15"
        # ТК РФ ст. 136 — перенос выплаты с выходного на более ранний рабочий
        # день обязателен по умолчанию, а не опционален.
        assert db.get_setting("move_weekend_to_friday") == "true"
        # оклад — не настройка (переехал в income kind='salary')
        assert db.get_setting("base_salary") == ""


class TestExpenseGroups:
    def test_create_and_list(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000")
        groups = db.get_expense_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "Продукты"

    def test_update(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000")
        db.update_expense_group("g1", name="Еда")
        assert db.get_expense_group("g1")["name"] == "Еда"

    def test_delete(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000")
        db.delete_expense_group("g1")
        assert db.get_expense_group("g1") is None

    def test_delete_group_with_expenses_unassigns_them_instead_of_failing(
        self, db: DatabaseManager
    ):
        """Регрессия: удаление группы с расходами падало с
        FOREIGN KEY constraint failed. Расходы должны стать "без группы"."""
        db.create_expense_group("g1", "Продукты", "#FF0000")
        db.add_expense("Молоко", 100.0, half=1, month=8, year=2026, group_id="g1")

        db.delete_expense_group("g1")

        assert db.get_expense_group("g1") is None
        expense = db.get_expenses()[0]
        assert expense["group_id"] is None

    def test_create_with_monthly_limit(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000", monthly_limit=15000.0)
        group = db.get_expense_group("g1")
        assert group["monthly_limit"] == 15000.0

    def test_update_can_set_and_clear_parent_id(self, db: DatabaseManager):
        db.create_expense_group("parent", "Родитель", "#111111")
        db.create_expense_group("g1", "Продукты", "#FF0000")

        db.update_expense_group("g1", parent_id="parent")
        assert db.get_expense_group("g1")["parent_id"] == "parent"

        db.update_expense_group("g1", parent_id=None)  # явная очистка
        assert db.get_expense_group("g1")["parent_id"] is None

    def test_update_without_parent_id_kwarg_leaves_it_unchanged(self, db: DatabaseManager):
        db.create_expense_group("parent", "Родитель", "#111111")
        db.create_expense_group("g1", "Продукты", "#FF0000", parent_id="parent")

        db.update_expense_group("g1", name="Еда")  # parent_id не передан вовсе

        assert db.get_expense_group("g1")["parent_id"] == "parent"

    def test_update_can_set_and_clear_monthly_limit(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000")

        db.update_expense_group("g1", monthly_limit=20000.0)
        assert db.get_expense_group("g1")["monthly_limit"] == 20000.0

        db.update_expense_group("g1", monthly_limit=None)
        assert db.get_expense_group("g1")["monthly_limit"] is None


class TestExpenses:
    def test_add_and_filter_by_month_year(self, db: DatabaseManager):
        db.add_expense("Молоко", 100.0, half=1, month=8, year=2026)
        db.add_expense("Бензин", 2000.0, half=2, month=9, year=2026)

        august = db.get_expenses(month=8, year=2026)
        assert len(august) == 1
        assert august[0]["name"] == "Молоко"

    def test_get_all_when_no_filter(self, db: DatabaseManager):
        db.add_expense("A", 1.0, half=1, month=1, year=2026)
        db.add_expense("B", 2.0, half=1, month=2, year=2026)
        assert len(db.get_expenses()) == 2

    def test_update_partial_fields(self, db: DatabaseManager):
        db.add_expense("Молоко", 100.0, half=1, month=8, year=2026)
        eid = db.get_expenses()[0]["id"]

        db.update_expense(eid, amount=250.0)

        updated = db.get_expenses()[0]
        assert updated["amount"] == 250.0
        assert updated["name"] == "Молоко"  # не изменилось

    def test_update_missing_expense_raises(self, db: DatabaseManager):
        with pytest.raises(ValueError):
            db.update_expense(9999, name="x")

    def test_delete(self, db: DatabaseManager):
        db.add_expense("Молоко", 100.0, half=1, month=8, year=2026)
        eid = db.get_expenses()[0]["id"]
        db.delete_expense(eid)
        assert db.get_expenses() == []

    def test_add_returns_the_new_rowid(self, db: DatabaseManager):
        eid = db.add_expense("Молоко", 100.0, half=1, month=8, year=2026)
        assert eid == db.get_expenses()[0]["id"]

    def test_update_can_set_and_clear_group_id(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000")
        eid = db.add_expense("Молоко", 100.0, half=1, month=8, year=2026, group_id="g1")

        db.update_expense(eid, group_id=None)  # явная очистка — "без группы"

        assert db.get_expenses()[0]["group_id"] is None

    def test_update_without_group_id_kwarg_leaves_it_unchanged(self, db: DatabaseManager):
        db.create_expense_group("g1", "Продукты", "#FF0000")
        eid = db.add_expense("Молоко", 100.0, half=1, month=8, year=2026, group_id="g1")

        db.update_expense(eid, amount=150.0)  # group_id не передан вовсе

        assert db.get_expenses()[0]["group_id"] == "g1"


class TestRecurringExpenseProjection:
    """Повторяющийся расход не копируется в БД на каждый месяц — get_expenses
    сама "продолжает" его вперёд, пока не наступит месяц recurring_until."""

    def test_recurring_expense_projects_into_later_month(self, db: DatabaseManager):
        db.add_expense("Кредит", 5000.0, half=1, month=8, year=2026, is_recurring=True)

        september = db.get_expenses(month=9, year=2026)

        assert len(september) == 1
        assert september[0]["name"] == "Кредит"

    def test_projected_expense_shows_the_viewed_period_not_its_origin(self, db: DatabaseManager):
        db.add_expense("Кредит", 5000.0, half=1, month=8, year=2026, is_recurring=True)

        projected = db.get_expenses(month=11, year=2026)[0]

        assert (projected["month"], projected["year"]) == (11, 2026)
        assert projected["projected"] is True          # строка из повтора
        origin = db.get_expenses(month=8, year=2026)[0]
        assert origin["projected"] is False            # оригинал в своём месяце

    def test_non_recurring_expense_does_not_project(self, db: DatabaseManager):
        db.add_expense("Разовая покупка", 500.0, half=1, month=8, year=2026, is_recurring=False)

        assert db.get_expenses(month=9, year=2026) == []

    def test_recurring_expense_does_not_appear_before_its_origin_month(self, db: DatabaseManager):
        db.add_expense("Кредит", 5000.0, half=1, month=8, year=2026, is_recurring=True)

        assert db.get_expenses(month=7, year=2026) == []

    def test_recurring_until_stops_projection_after_that_month(self, db: DatabaseManager):
        db.add_expense(
            "Кредит",
            5000.0,
            half=1,
            month=1,
            year=2026,
            is_recurring=True,
            recurring_until="2026-03-15",
        )

        assert len(db.get_expenses(month=3, year=2026)) == 1  # месяц окончания — ещё включается
        assert db.get_expenses(month=4, year=2026) == []  # а после — уже нет

    def test_recurring_until_across_year_boundary(self, db: DatabaseManager):
        db.add_expense(
            "Кредит",
            5000.0,
            half=1,
            month=11,
            year=2025,
            is_recurring=True,
            recurring_until="2026-01-31",
        )

        assert len(db.get_expenses(month=1, year=2026)) == 1
        assert db.get_expenses(month=2, year=2026) == []

    def test_show_all_periods_returns_raw_rows_without_projection(self, db: DatabaseManager):
        """month/year=None ("за все периоды" в UI) — не проецирует, просто
        отдаёт реальные строки БД как есть."""
        db.add_expense("Кредит", 5000.0, half=1, month=8, year=2026, is_recurring=True)

        rows = db.get_expenses()

        assert len(rows) == 1
        assert (rows[0]["month"], rows[0]["year"]) == (8, 2026)

    def test_update_can_set_and_then_clear_recurring_until(self, db: DatabaseManager):
        db.add_expense("Кредит", 5000.0, half=1, month=8, year=2026, is_recurring=True)
        eid = db.get_expenses()[0]["id"]

        db.update_expense(eid, recurring_until="2026-09-30")
        assert db.get_expenses(month=8, year=2026)[0]["recurring_until"] == "2026-09-30"
        assert db.get_expenses(month=10, year=2026) == []  # уже за пределами окончания

        db.update_expense(eid, recurring_until=None)  # явная очистка — снова бессрочно
        assert db.get_expenses(month=8, year=2026)[0]["recurring_until"] is None
        assert len(db.get_expenses(month=10, year=2026)) == 1

    def test_update_without_recurring_until_kwarg_leaves_it_unchanged(self, db: DatabaseManager):
        db.add_expense(
            "Кредит",
            5000.0,
            half=1,
            month=8,
            year=2026,
            is_recurring=True,
            recurring_until="2026-12-31",
        )
        eid = db.get_expenses()[0]["id"]

        db.update_expense(eid, amount=5500.0)  # recurring_until не передан вовсе

        assert db.get_expenses(month=8, year=2026)[0]["recurring_until"] == "2026-12-31"


class TestIncome:
    """Доходы — зеркало расходов без групп: та же проекция повторяющихся
    строк вперёд (см. TestRecurringExpenseProjection)."""

    def test_add_and_filter_by_month_year(self, db: DatabaseManager):
        db.add_income("Фриланс", 30000.0, half=1, month=8, year=2026)
        db.add_income("Аренда", 15000.0, half=2, month=9, year=2026)

        august = db.get_income(month=8, year=2026)
        assert len(august) == 1
        assert august[0]["name"] == "Фриланс"

    def test_add_returns_the_new_rowid(self, db: DatabaseManager):
        iid = db.add_income("Фриланс", 30000.0, half=1, month=8, year=2026)
        assert iid == db.get_income()[0]["id"]

    def test_get_all_when_no_filter_returns_raw_rows(self, db: DatabaseManager):
        db.add_income("A", 1.0, half=1, month=1, year=2026)
        db.add_income("B", 2.0, half=1, month=2, year=2026, is_recurring=True)
        rows = db.get_income()
        assert len(rows) == 2
        assert (rows[1]["month"], rows[1]["year"]) == (2, 2026)  # без проекции

    def test_recurring_income_projects_into_later_month(self, db: DatabaseManager):
        db.add_income("Аренда", 15000.0, half=1, month=8, year=2026, is_recurring=True)

        projected = db.get_income(month=11, year=2026)

        assert len(projected) == 1
        assert (projected[0]["month"], projected[0]["year"]) == (11, 2026)

    def test_non_recurring_income_does_not_project(self, db: DatabaseManager):
        db.add_income("Разовая премия", 50000.0, half=1, month=8, year=2026)

        assert db.get_income(month=9, year=2026) == []

    def test_recurring_until_stops_projection_after_that_month(self, db: DatabaseManager):
        db.add_income(
            "Аренда", 15000.0, half=1, month=1, year=2026,
            is_recurring=True, recurring_until="2026-03-15",
        )

        assert len(db.get_income(month=3, year=2026)) == 1
        assert db.get_income(month=4, year=2026) == []

    def test_update_partial_fields(self, db: DatabaseManager):
        db.add_income("Фриланс", 30000.0, half=1, month=8, year=2026)
        iid = db.get_income()[0]["id"]

        db.update_income(iid, amount=45000.0)

        updated = db.get_income()[0]
        assert updated["amount"] == 45000.0
        assert updated["name"] == "Фриланс"  # не изменилось

    def test_update_missing_income_raises(self, db: DatabaseManager):
        with pytest.raises(ValueError):
            db.update_income(9999, name="x")

    def test_update_can_set_and_then_clear_recurring_until(self, db: DatabaseManager):
        db.add_income("Аренда", 15000.0, half=1, month=8, year=2026, is_recurring=True)
        iid = db.get_income()[0]["id"]

        db.update_income(iid, recurring_until="2026-09-30")
        assert db.get_income(month=10, year=2026) == []

        db.update_income(iid, recurring_until=None)  # явная очистка — снова бессрочно
        assert len(db.get_income(month=10, year=2026)) == 1

    def test_delete(self, db: DatabaseManager):
        db.add_income("Фриланс", 30000.0, half=1, month=8, year=2026)
        iid = db.get_income()[0]["id"]
        db.delete_income(iid)
        assert db.get_income() == []


class TestVacations:
    def test_add_defaults_range_to_payout_date(self, db: DatabaseManager):
        db.add_vacation(total_amount=10000.0, payout_date="2025-07-04")
        v = db.get_vacations()[0]
        assert v["start_date"] == "2025-07-04"
        assert v["end_date"] == "2025-07-04"

    def test_add_with_explicit_range(self, db: DatabaseManager):
        db.add_vacation(
            total_amount=10000.0,
            payout_date="2025-07-04",
            start_date="2025-07-07",
            end_date="2025-07-20",
        )
        v = db.get_vacations()[0]
        assert v["start_date"] == "2025-07-07"
        assert v["end_date"] == "2025-07-20"

    def test_filter_by_month_year(self, db: DatabaseManager):
        db.add_vacation(total_amount=1.0, payout_date="2025-07-04")
        db.add_vacation(total_amount=2.0, payout_date="2025-08-04")
        july = db.get_vacations(month=7, year=2025)
        assert len(july) == 1

    def test_delete(self, db: DatabaseManager):
        db.add_vacation(total_amount=1.0, payout_date="2025-07-04")
        vid = db.get_vacations()[0]["id"]
        db.delete_vacation(vid)
        assert db.get_vacations() == []

    def test_add_returns_the_new_rowid(self, db: DatabaseManager):
        vid = db.add_vacation(total_amount=1.0, payout_date="2025-07-04")
        assert vid == db.get_vacations()[0]["id"]

    def test_migration_is_idempotent_for_pre_existing_columns(self, db: DatabaseManager):
        # Повторный вызов не должен падать, даже если колонки уже есть
        with db._transaction() as c:
            db._migrate_schema(c)
        assert db.get_vacations() == []


class TestCalendarCache:
    """Кэш производственного календаря (calendar_data) и поправки к нему
    (calendar_corrections) — используются CalendarService, чтобы не
    перестраивать календарь на каждый запрос."""

    def test_needs_fill_true_before_any_data_saved(self, db: DatabaseManager):
        assert db.calendar_needs_fill(2026) is True

    def test_needs_fill_false_after_saving(self, db: DatabaseManager):
        db.save_calendar_data(2026, [("2026-08-01", 1, 0, 0)])
        assert db.calendar_needs_fill(2026) is False

    def test_needs_fill_is_scoped_per_year(self, db: DatabaseManager):
        db.save_calendar_data(2026, [("2026-08-01", 1, 0, 0)])
        assert db.calendar_needs_fill(2025) is True

    def test_save_then_read_back_matches(self, db: DatabaseManager):
        rows = [
            ("2026-08-01", 1, 0, 0),
            ("2026-08-02", 0, 1, 0),  # выходной/праздник
            ("2026-08-03", 1, 0, 1),  # сокращённый рабочий день
        ]
        db.save_calendar_data(2026, rows)

        month = db.get_calendar_month(2026, 8)

        assert month == [
            {"date": "2026-08-01", "is_working": 1, "is_holiday": 0, "is_shortened": 0},
            {"date": "2026-08-02", "is_working": 0, "is_holiday": 1, "is_shortened": 0},
            {"date": "2026-08-03", "is_working": 1, "is_holiday": 0, "is_shortened": 1},
        ]

    def test_get_calendar_month_filters_out_other_months(self, db: DatabaseManager):
        db.save_calendar_data(
            2026,
            [
                ("2026-08-31", 1, 0, 0),
                ("2026-09-01", 1, 0, 0),
            ],
        )

        august = db.get_calendar_month(2026, 8)

        assert [r["date"] for r in august] == ["2026-08-31"]

    def test_clear_calendar_cache_resets_needs_fill(self, db: DatabaseManager):
        db.save_calendar_data(2026, [("2026-08-01", 1, 0, 0)])
        assert db.calendar_needs_fill(2026) is False

        db.clear_calendar_cache(2026)

        assert db.calendar_needs_fill(2026) is True
        assert db.get_calendar_month(2026, 8) == []

    def test_clear_calendar_cache_only_affects_given_year(self, db: DatabaseManager):
        db.save_calendar_data(2025, [("2025-08-01", 1, 0, 0)])
        db.save_calendar_data(2026, [("2026-08-01", 1, 0, 0)])

        db.clear_calendar_cache(2026)

        assert db.calendar_needs_fill(2026) is True
        assert db.calendar_needs_fill(2025) is False

    def test_save_calendar_data_overwrites_existing_row_for_same_date(self, db: DatabaseManager):
        """INSERT OR REPLACE — повторное сохранение той же даты должно
        обновить строку, а не завести дубликат/упасть на PRIMARY KEY."""
        db.save_calendar_data(2026, [("2026-08-01", 1, 0, 0)])
        db.save_calendar_data(2026, [("2026-08-01", 0, 1, 0)])

        month = db.get_calendar_month(2026, 8)

        assert len(month) == 1
        assert month[0] == {
            "date": "2026-08-01",
            "is_working": 0,
            "is_holiday": 1,
            "is_shortened": 0,
        }

    def test_corrections_roundtrip(self, db: DatabaseManager):
        rows = [
            ("2026-08-01", "extra_holiday", "manual"),
            ("2026-08-15", "shortened", "pdf"),
        ]
        db.save_corrections(2026, rows)

        corrections = db.get_corrections()

        assert corrections == [
            {"date": "2026-08-01", "kind": "extra_holiday", "source": "manual"},
            {"date": "2026-08-15", "kind": "shortened", "source": "pdf"},
        ]

    def test_get_corrections_empty_before_any_saved(self, db: DatabaseManager):
        assert db.get_corrections() == []

    def test_save_corrections_replaces_previous_corrections_for_that_year(
        self, db: DatabaseManager
    ):
        """save_corrections удаляет все поправки этого года перед вставкой
        новых — повторный вызов не должен накапливать старые записи."""
        db.save_corrections(2026, [("2026-08-01", "extra_holiday", "manual")])
        db.save_corrections(2026, [("2026-09-01", "extra_working", "manual")])

        corrections = db.get_corrections()

        assert corrections == [{"date": "2026-09-01", "kind": "extra_working", "source": "manual"}]

    def test_save_corrections_does_not_touch_other_years(self, db: DatabaseManager):
        db.save_corrections(2025, [("2025-08-01", "extra_holiday", "manual")])
        db.save_corrections(2026, [("2026-08-01", "shortened", "manual")])

        corrections = db.get_corrections()

        assert corrections == [
            {"date": "2025-08-01", "kind": "extra_holiday", "source": "manual"},
            {"date": "2026-08-01", "kind": "shortened", "source": "manual"},
        ]


class TestBirthdays:
    def test_add_and_list_sorted_by_date(self, db: DatabaseManager):
        db.add_birthday("Б", "20.05.1990", 1000.0)
        db.add_birthday("А", "10.01.1990", 2000.0)
        rows = db.get_birthdays()
        assert [r["name"] for r in rows] == ["А", "Б"]

    def test_sorted_by_calendar_order_not_lexicographic_string_order(self, db: DatabaseManager):
        """Регрессия: ORDER BY birth_date по строке целиком сортировал сначала
        по дню, а не по месяцу — "01.12" (1 декабря) оказывался раньше
        "02.01" (2 января), хотя календарно позже."""
        db.add_birthday("Декабрьский", "01.12.1990", 1000.0)
        db.add_birthday("Январский", "02.01.1990", 2000.0)

        rows = db.get_birthdays()

        assert [r["name"] for r in rows] == ["Январский", "Декабрьский"]

    def test_add_returns_the_new_rowid(self, db: DatabaseManager):
        bid = db.add_birthday("А", "10.01.1990", 2000.0)
        assert bid == db.get_birthdays()[0]["id"]

    def test_delete(self, db: DatabaseManager):
        db.add_birthday("А", "10.01.1990", 2000.0)
        bid = db.get_birthdays()[0]["id"]
        db.delete_birthday(bid)
        assert db.get_birthdays() == []


class TestDebts:
    def test_create_and_get_with_empty_repayments(self, db: DatabaseManager):
        debt_id = db.create_debt("Другу", 15000.0, month=8, year=2026)
        debts = db.get_debts()
        assert len(debts) == 1
        assert debts[0]["id"] == debt_id
        assert debts[0]["repayments"] == []

    def test_repayments_reduce_remaining_amount(self, db: DatabaseManager):
        debt_id = db.create_debt("Света", 29000.0, month=1, year=2026)
        db.add_debt_repayment(debt_id, 1100.0, "2026-01-05")
        db.add_debt_repayment(debt_id, 2700.0, "2026-01-10")

        debt = db.get_debts()[0]
        repaid = sum(r["amount"] for r in debt["repayments"])
        assert repaid == pytest.approx(3800.0)
        assert debt["total_amount"] - repaid == pytest.approx(25200.0)
        # get_debts теперь считает это сама — backend как единственный
        # источник правды вместо повторного пересчёта на фронтенде.
        assert debt["repaid_amount"] == pytest.approx(3800.0)
        assert debt["remaining_amount"] == pytest.approx(25200.0)

    def test_remaining_amount_does_not_go_negative_on_overpayment(self, db: DatabaseManager):
        debt_id = db.create_debt("X", 1000.0, month=1, year=2026)
        db.add_debt_repayment(debt_id, 1500.0, "2026-01-05")

        assert db.get_debts()[0]["remaining_amount"] == 0.0

    def test_add_repayment_returns_the_new_rowid(self, db: DatabaseManager):
        debt_id = db.create_debt("X", 1000.0, month=1, year=2026)
        rid = db.add_debt_repayment(debt_id, 500.0, "2026-01-05")
        assert rid == db.get_debts()[0]["repayments"][0]["id"]

    def test_repayments_grouped_correctly_across_multiple_debts(self, db: DatabaseManager):
        """Регрессия для фикса N+1: один общий запрос погашений группируется
        по debt_id в Python — каждому долгу должны попасть только его платежи."""
        debt_a = db.create_debt("Долг A", 1000.0, month=1, year=2026)
        debt_b = db.create_debt("Долг B", 2000.0, month=1, year=2026)
        db.add_debt_repayment(debt_a, 100.0, "2026-01-01")
        db.add_debt_repayment(debt_b, 200.0, "2026-01-02")
        db.add_debt_repayment(debt_b, 300.0, "2026-01-03")

        debts = {d["id"]: d for d in db.get_debts()}

        assert len(debts[debt_a]["repayments"]) == 1
        assert len(debts[debt_b]["repayments"]) == 2
        assert debts[debt_a]["repaid_amount"] == pytest.approx(100.0)
        assert debts[debt_b]["repaid_amount"] == pytest.approx(500.0)

    def test_delete_repayment(self, db: DatabaseManager):
        debt_id = db.create_debt("X", 1000.0, month=1, year=2026)
        db.add_debt_repayment(debt_id, 500.0, "2026-01-05")
        rid = db.get_debts()[0]["repayments"][0]["id"]

        db.delete_debt_repayment(rid)

        assert db.get_debts()[0]["repayments"] == []

    def test_delete_debt(self, db: DatabaseManager):
        debt_id = db.create_debt("X", 1000.0, month=1, year=2026)
        db.delete_debt(debt_id)
        assert db.get_debts() == []

    def test_planned_payment_fields_default_to_zero_and_second_half(self, db: DatabaseManager):
        db.create_debt("X", 1000.0, month=1, year=2026)
        d = db.get_debts()[0]
        assert d["monthly_payment"] == 0.0
        assert d["payment_half"] == 2

    def test_create_with_planned_payment(self, db: DatabaseManager):
        db.create_debt("Кредит", 100000.0, month=1, year=2026,
                       monthly_payment=8000.0, payment_half=1)
        d = db.get_debts()[0]
        assert d["monthly_payment"] == 8000.0
        assert d["payment_half"] == 1

    def test_update_debt_changes_only_given_fields(self, db: DatabaseManager):
        debt_id = db.create_debt("Кредит", 100000.0, month=1, year=2026)

        db.update_debt(debt_id, monthly_payment=5000.0, payment_half=1)

        d = db.get_debts()[0]
        assert d["monthly_payment"] == 5000.0
        assert d["payment_half"] == 1
        assert d["title"] == "Кредит"  # не тронут
        assert d["total_amount"] == 100000.0

    def test_update_debt_with_no_fields_is_a_noop(self, db: DatabaseManager):
        debt_id = db.create_debt("Кредит", 100000.0, month=1, year=2026,
                                 monthly_payment=3000.0)
        db.update_debt(debt_id)
        assert db.get_debts()[0]["monthly_payment"] == 3000.0


class TestBackup:
    def test_backup_to_produces_a_connectable_copy_with_matching_data(
        self, db: DatabaseManager, tmp_path
    ):
        db.add_expense("Молоко", 100.0, half=1, month=8, year=2026)
        backup_path = tmp_path / "backup.db"

        db.backup_to(str(backup_path))

        assert backup_path.exists()
        restored = DatabaseManager(str(backup_path))
        try:
            expenses = restored.get_expenses()
            assert len(expenses) == 1
            assert expenses[0]["name"] == "Молоко"
        finally:
            restored.close()
