"""Тесты фасада services.FinanceService и вспомогательных функций."""

from __future__ import annotations

from datetime import date

import pytest

from services import (
    FinanceService,
    ValidationError,
    project_debt_payoff,
    project_payoff_at_rate,
)


class TestExpenseGroups:
    def test_crud(self, service: FinanceService):
        g = service.create_expense_group(name="Еда", color="#112233", monthly_limit=5000)
        assert g["name"] == "Еда"
        assert g["monthlyLimit"] == 5000

        updated = service.update_expense_group(g["id"], name="Продукты")
        assert updated["name"] == "Продукты"
        assert updated["monthlyLimit"] == 5000  # не тронут

        cleared = service.update_expense_group(g["id"], monthly_limit=None)
        assert cleared["monthlyLimit"] is None

        service.delete_expense_group(g["id"])
        assert service.list_expense_groups() == []

    def test_delete_group_keeps_expenses_ungrouped(self, service: FinanceService):
        g = service.create_expense_group(name="X", color="#000000")
        e = service.create_expense(name="A", amount=100, half=1, month=1, year=2025,
                                   group_id=g["id"])
        service.delete_expense_group(g["id"])
        rows = service.list_expenses(1, 2025)
        assert len(rows) == 1
        assert rows[0]["id"] == e["id"]
        assert rows[0]["groupId"] is None


class TestIncome:
    def test_crud_and_recurring(self, service: FinanceService):
        i = service.create_income(name="Фриланс", amount=30000, half=1, month=3, year=2025,
                                  is_recurring=True)
        assert i["amount"] == 30000 and i["isRecurring"] is True
        assert len(service.list_income(3, 2025)) == 1
        assert len(service.list_income(9, 2025)) == 1  # спроецирован вперёд

        service.update_income(i["id"], amount=45000)
        assert service.list_income(3, 2025)[0]["amount"] == 45000
        service.delete_income(i["id"])
        assert service.list_income() == []

    def test_income_adds_to_balance(self, service: FinanceService):
        service.update_settings({"baseSalary": 100000, "taxRate": 0, "kef": 1.0})
        service.create_income(name="Аренда", amount=20000, half=1, month=6, year=2025)
        b = service.balance(6, 2025)
        assert b["incomeHalf1"] == 20000
        assert b["balanceHalf1"] == pytest.approx(b["toPayHalf1"] + 20000)


class TestDebtMonthlyPayment:
    def test_planned_payment_deducted_from_balance(self, service: FinanceService):
        service.update_settings({"baseSalary": 100000, "taxRate": 0, "kef": 1.0})
        service.create_debt(title="Кредит", total_amount=100000,
                            monthly_payment=8000, payment_half=2)
        b = service.balance(6, 2025)
        assert b["debtPaymentHalf2"] == 8000
        assert b["balanceHalf2"] == pytest.approx(b["toPayHalf2"] - 8000)

    def test_no_deduction_when_debt_repaid(self, service: FinanceService):
        d = service.create_debt(title="X", total_amount=5000, monthly_payment=1000)
        service.add_repayment(d["id"], amount=5000, when="2025-06-01")
        b = service.balance(6, 2025)
        assert b["debtPaymentHalf2"] == 0  # долг закрыт — платёж не вычитается

    def test_update_debt(self, service: FinanceService):
        d = service.create_debt(title="X", total_amount=5000)
        service.update_debt(d["id"], monthly_payment=500, payment_half=1)
        upd = service.list_debts()[0]
        assert upd["monthlyPayment"] == 500 and upd["paymentHalf"] == 1


class TestExpenses:
    def test_partial_update_keeps_untouched_fields(self, service: FinanceService):
        g = service.create_expense_group(name="G", color="#010203")
        e = service.create_expense(name="A", amount=100, half=1, month=3, year=2025,
                                   group_id=g["id"])
        upd = service.update_expense(e["id"], amount=250)
        assert upd["amount"] == 250
        assert upd["name"] == "A"
        assert upd["groupId"] == g["id"]

        upd2 = service.update_expense(e["id"], group_id=None)
        assert upd2["groupId"] is None

    def test_recurring_projection_in_list(self, service: FinanceService):
        service.create_expense(name="Sub", amount=500, half=1, month=1, year=2025,
                               is_recurring=True)
        assert len(service.list_expenses(1, 2025)) == 1
        assert len(service.list_expenses(6, 2025)) == 1  # спроецирован вперёд
        # без фильтра периода — только реальная строка
        assert len(service.list_expenses()) == 1


class TestAnalytics:
    def test_summary_groups_by_category(self, service: FinanceService):
        a = service.create_expense_group(name="A", color="#aa0000")
        service.create_expense(name="x", amount=100, half=1, month=5, year=2025, group_id=a["id"])
        service.create_expense(name="y", amount=50, half=2, month=5, year=2025, group_id=a["id"])
        service.create_expense(name="z", amount=30, half=1, month=5, year=2025)  # без группы

        s = service.analytics_summary(5, 2025)
        assert s["total"] == 180
        assert s["count"] == 3
        cats = {c["name"]: c["amount"] for c in s["categories"]}
        assert cats == {"A": 150, "Без группы": 30}
        # отсортировано по убыванию суммы
        assert s["categories"][0]["amount"] >= s["categories"][-1]["amount"]

    def test_trend_length_and_order(self, service: FinanceService):
        t = service.analytics_trend(2, 2025, months=5)["months"]
        assert [(m["month"], m["year"]) for m in t] == [
            (10, 2024), (11, 2024), (12, 2024), (1, 2025), (2, 2025)
        ]


class TestBalance:
    def test_balance_subtracts_expenses(self, service: FinanceService):
        service.update_settings({"baseSalary": 100000, "taxRate": 0, "kef": 1.0})
        service.create_expense(name="rent", amount=20000, half=1, month=6, year=2025)
        b = service.balance(6, 2025)
        assert b["netSalary"] == 100000
        assert b["expensesHalf1"] == 20000
        assert b["balanceHalf1"] == pytest.approx(b["toPayHalf1"] - 20000)


class TestDebtProjection:
    def test_no_repayments(self):
        p = project_debt_payoff(1000, [])
        assert p.months_to_payoff is None
        assert p.projected_date is None

    def test_rate_and_eta(self):
        today = date(2025, 3, 1)
        p = project_debt_payoff(
            8000,
            [{"amount": 1000, "date": "2025-01-01"}, {"amount": 1000, "date": "2025-02-01"}],
            today=today,
        )
        # 2000 погашено за 3 месяца (янв, фев, мар) -> ~666/мес
        assert p.avg_monthly_rate == pytest.approx(2000 / 3)
        assert p.months_to_payoff == 12

    def test_payoff_at_rate(self):
        d = project_payoff_at_rate(10000, 2500, today=date(2025, 1, 1))
        assert d == date(2025, 5, 1)
        assert project_payoff_at_rate(10000, 0) is None
        assert project_payoff_at_rate(0, 2500) is None


class TestValidation:
    def test_vacation_range_order(self, service: FinanceService):
        with pytest.raises(ValidationError):
            service.create_vacation(
                total_amount=1000, payout_date="2025-07-10",
                start_date="2025-07-20", end_date="2025-07-10",
            )
