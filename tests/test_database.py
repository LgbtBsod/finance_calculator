"""test_database.py — CRUD-операции DatabaseManager на изолированной in-memory БД."""

from __future__ import annotations

import pytest

from database import DatabaseManager


class TestSettings:
    def test_set_and_get_roundtrip(self, db: DatabaseManager):
        db.set_setting("base_salary", "150000")
        assert db.get_setting("base_salary") == "150000"

    def test_get_missing_setting_returns_empty_string(self, db: DatabaseManager):
        assert db.get_setting("does_not_exist") == ""

    def test_seeded_defaults_present_on_init(self, db: DatabaseManager):
        # _seed_defaults запускается в __init__ через _init_db
        assert db.get_setting("base_salary") != ""
        assert db.get_setting("salary_calculation_method") == "proportional"


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

    def test_migration_is_idempotent_for_pre_existing_columns(self, db: DatabaseManager):
        # Повторный вызов не должен падать, даже если колонки уже есть
        with db._transaction() as c:
            db._migrate_schema(c)
        assert db.get_vacations() == []


class TestBirthdays:
    def test_add_and_list_sorted_by_date(self, db: DatabaseManager):
        db.add_birthday("Б", "20.05.1990", 1000.0)
        db.add_birthday("А", "10.01.1990", 2000.0)
        rows = db.get_birthdays()
        assert [r["name"] for r in rows] == ["А", "Б"]

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
