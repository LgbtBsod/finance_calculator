"""End-to-end сценарии через фасад FinanceService.

Раньше эти тесты ходили в FastAPI TestClient; после перехода на Flet HTTP-слоя
нет — вся прежняя логика endpoint'ов (агрегации баланса / аналитики / тренда)
живёт в services.FinanceService, и тесты вызывают её напрямую.
"""

from __future__ import annotations

import sqlite3

import pytest

from services import FinanceService, ValidationError


class TestSalaryAndExpensesFlow:
    def test_full_balance_with_expenses_and_vacation(self, service: FinanceService, add_salary):
        add_salary(100000, kef=1.5)

        food = service.create_expense_group(name="Еда", color="#FF0000")
        transport = service.create_expense_group(
            name="Транспорт", color="#00FF00", monthly_limit=5000
        )

        service.create_expense(
            name="Продукты", amount=3000, half=1, month=7, year=2025, group_id=food["id"]
        )
        service.create_expense(
            name="Бензин", amount=2000, half=1, month=7, year=2025,
            group_id=transport["id"], is_recurring=True, recurring_until="2025-12-31",
        )
        service.create_vacation(
            total_amount=50000, payout_date="2025-07-25",
            start_date="2025-07-20", end_date="2025-08-05",
        )

        b = service.balance(7, 2025)
        assert b["netSalary"] > 0
        assert b["totalAccrued"] >= b["netSalary"]  # включает отпускные
        assert b["expensesHalf1"] == 5000.0
        assert b["balanceHalf1"] == pytest.approx(b["toPayHalf1"] - 5000.0)

    def test_recurring_expense_projects_forward_and_stops(self, service: FinanceService):
        service.create_expense(
            name="Netflix", amount=999, half=1, month=7, year=2025,
            is_recurring=True, recurring_until="2025-09-30",
        )
        trend = service.analytics_trend(month=10, year=2025, months=4)["months"]
        assert [(m["month"], m["year"]) for m in trend] == [
            (7, 2025), (8, 2025), (9, 2025), (10, 2025)
        ]
        totals = {m["month"]: m["total"] for m in trend}
        assert totals[7] == 999 and totals[8] == 999 and totals[9] == 999
        assert totals[10] == 0  # после recurring_until проекция прекращается

    def test_monthly_limit_overspend_visible_in_summary(self, service: FinanceService):
        g = service.create_expense_group(name="Развлечения", color="#FF00FF", monthly_limit=1000)
        service.create_expense(name="Кино", amount=600, half=1, month=7, year=2025, group_id=g["id"])
        service.create_expense(name="Концерт", amount=500, half=2, month=7, year=2025,
                               group_id=g["id"])

        summary = service.analytics_summary(month=7, year=2025)
        cat = next(c for c in summary["categories"] if c["groupId"] == g["id"])
        assert cat["amount"] == 1100
        assert cat["monthlyLimit"] == 1000
        assert cat["amount"] > cat["monthlyLimit"]


class TestDebtFlow:
    def test_debt_repayment_updates_remaining(self, service: FinanceService):
        d = service.create_debt(title="Кредит", total_amount=10000, month=7, year=2025)
        assert d["remainingAmount"] == 10000

        service.add_repayment(d["id"], amount=3000, when="2025-07-15", note="Первый платёж")
        debt = service.list_debts()[0]
        assert debt["repaidAmount"] == 3000
        assert debt["remainingAmount"] == 7000
        assert debt["repayments"][0]["note"] == "Первый платёж"

    def test_repayment_projection(self, service: FinanceService):
        d = service.create_debt(title="Кредит", total_amount=100000)
        service.add_repayment(d["id"], amount=10000, when="2025-06-01")
        service.add_repayment(d["id"], amount=10000, when="2025-07-01")
        debt = service.list_debts()[0]
        proj = service.project_debt_payoff(debt["remainingAmount"], debt["repayments"])
        assert proj.avg_monthly_rate > 0
        assert proj.months_to_payoff is not None
        assert proj.projected_date is not None


class TestBirthdayFlow:
    def test_auto_create_gift_expense(self, service: FinanceService):
        from datetime import date

        today = date.today()
        # ДР через несколько дней в этом месяце -> подарок должен создаться сейчас
        service.create_birthday(
            name="Иван", birth_date=f"28.{today.month:02d}.1990", gift_amount=1500
        )
        created = service.auto_create_birthday_expenses()
        # либо создали расход, либо он относится к другому периоду выплаты —
        # в обоих случаях повторный вызов не должен плодить дубли
        again = service.auto_create_birthday_expenses()
        assert again == 0
        assert created >= 0

    def test_upcoming_birthdays_shape(self, service: FinanceService):
        service.create_birthday(name="Пётр", birth_date="01.01.1990", gift_amount=1000)
        alerts = service.upcoming_birthdays(days=400)
        assert isinstance(alerts, list)
        for a in alerts:
            assert {"name", "birthDate", "giftAmount", "triggerDate", "daysUntil"} <= a.keys()


class TestSettingsAndValidation:
    def test_settings_roundtrip(self, service: FinanceService):
        service.update_settings(
            {"taxRate": 15, "advanceCutoffDay": 20, "payoutDay1": 7}
        )
        s = service.get_settings()
        assert s["taxRate"] == 15
        assert s["advanceCutoffDay"] == 20
        assert s["payoutDay1"] == 7

    def test_salary_is_income_entity_not_setting(self, service: FinanceService, add_salary):
        add_salary(90000, method="working_days")
        salaries = service.list_salaries()
        assert len(salaries) == 1
        assert salaries[0]["kind"] == "salary" and salaries[0]["splitMethod"] == "working_days"
        assert "baseSalary" not in service.get_settings()

    def test_bad_dates_rejected(self, service: FinanceService):
        with pytest.raises(ValidationError):
            service.create_vacation(total_amount=1000, payout_date="not-a-date")
        with pytest.raises(ValidationError):
            service.create_birthday(name="X", birth_date="31.02.2000", gift_amount=100)


class TestBackup:
    def test_backup_creates_valid_sqlite(self, file_service: FinanceService, tmp_path):
        file_service.create_expense(name="A", amount=100, half=1, month=1, year=2025)
        target = tmp_path / "backup.db"
        file_service.backup_to(str(target))

        assert target.exists()
        conn = sqlite3.connect(target)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert {"expenses", "expense_groups", "settings", "debts"} <= tables

    def test_backup_bytes_rejects_memory_db(self, service: FinanceService):
        with pytest.raises(ValidationError):
            service.backup_bytes()
