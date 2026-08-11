"""test_api.py — HTTP-контракт FastAPI-приложения через TestClient.

get_db переопределяется на изолированную in-memory БД — реальный
budget.db никогда не трогается тестами.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api as api_module
from database import DatabaseManager


@pytest.fixture
def client():
    test_db = DatabaseManager(":memory:")

    def override_get_db():
        yield test_db

    api_module.app.dependency_overrides[api_module.get_db] = override_get_db
    with TestClient(api_module.app) as c:
        yield c
    api_module.app.dependency_overrides.clear()
    test_db.close()


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


class TestSettings:
    def test_get_returns_defaults(self, client: TestClient):
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["salaryCalculationMethod"] == "proportional"

    def test_put_updates_only_provided_fields(self, client: TestClient):
        client.put("/api/settings", json={"baseSalary": 150000})
        response = client.get("/api/settings")
        data = response.json()
        assert data["baseSalary"] == 150000
        assert data["taxRate"] == 13.0  # не изменилось


class TestBalanceEndpoint:
    def test_default_proportional_split(self, client: TestClient):
        client.put("/api/settings", json={
            "baseSalary": 100000, "taxRate": 13, "kef": 1.0,
            "salaryCalculationMethod": "proportional",
        })

        response = client.get("/api/balance", params={"month": 8, "year": 2026})

        assert response.status_code == 200
        data = response.json()
        assert data["netSalary"] == pytest.approx(87000.0)
        assert data["toPayHalf1"] == pytest.approx(34800.0)
        assert data["toPayHalf2"] == pytest.approx(52200.0)

    def test_matches_reference_spreadsheet_via_working_days(self, client: TestClient):
        client.put("/api/settings", json={
            "baseSalary": 121003, "taxRate": 13, "kef": 1.0,
            "salaryCalculationMethod": "working_days",
            "advanceCutoffDay": 15, "isAdvanceDateInclusive": True,
        })

        response = client.get("/api/balance", params={"month": 7, "year": 2025})

        data = response.json()
        assert data["toPayHalf1"] == pytest.approx(50347.77, abs=0.01)
        assert data["toPayHalf2"] == pytest.approx(54924.84, abs=0.01)

    def test_subtracts_expenses(self, client: TestClient):
        client.put("/api/settings", json={
            "baseSalary": 100000, "taxRate": 13, "kef": 1.0,
            "salaryCalculationMethod": "proportional",
        })
        client.post("/api/expense-items", json={
            "name": "Продукты", "amount": 5000, "half": 1, "month": 8, "year": 2026,
        })

        response = client.get("/api/balance", params={"month": 8, "year": 2026})

        data = response.json()
        assert data["expensesHalf1"] == pytest.approx(5000.0)
        assert data["balanceHalf1"] == pytest.approx(34800.0 - 5000.0)

    def test_missing_required_params_returns_422(self, client: TestClient):
        response = client.get("/api/balance")
        assert response.status_code == 422


class TestExpenseGroups:
    def test_create_get_update_delete(self, client: TestClient):
        create = client.post("/api/expense-groups", json={"name": "Продукты", "color": "#FF0000"})
        assert create.status_code == 201
        group_id = create.json()["id"]

        listed = client.get("/api/expense-groups").json()
        assert len(listed) == 1

        updated = client.put(f"/api/expense-groups/{group_id}", json={"name": "Еда"})
        assert updated.json()["name"] == "Еда"

        deleted = client.delete(f"/api/expense-groups/{group_id}")
        assert deleted.status_code == 204
        assert client.get("/api/expense-groups").json() == []

    def test_delete_group_with_expenses_does_not_500(self, client: TestClient):
        """Регрессия: удаление группы, у которой есть расходы, падало с
        необработанным FOREIGN KEY constraint failed (HTTP 500)."""
        group = client.post("/api/expense-groups", json={"name": "Продукты", "color": "#FF0000"}).json()
        client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
            "groupId": group["id"],
        })

        response = client.delete(f"/api/expense-groups/{group['id']}")

        assert response.status_code == 204
        items = client.get("/api/expense-items", params={"month": 8, "year": 2026}).json()
        assert items[0]["groupId"] is None

    def test_invalid_color_rejected(self, client: TestClient):
        response = client.post("/api/expense-groups", json={"name": "X", "color": "not-a-color"})
        assert response.status_code == 422


class TestExpenseItems:
    def test_create_and_filter_by_period(self, client: TestClient):
        client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
        })
        client.post("/api/expense-items", json={
            "name": "Бензин", "amount": 2000, "half": 2, "month": 9, "year": 2026,
        })

        august = client.get("/api/expense-items", params={"month": 8, "year": 2026}).json()
        assert len(august) == 1
        assert august[0]["name"] == "Молоко"

    def test_negative_amount_rejected(self, client: TestClient):
        response = client.post("/api/expense-items", json={
            "name": "X", "amount": -5, "half": 1, "month": 8, "year": 2026,
        })
        assert response.status_code == 422

    def test_delete(self, client: TestClient):
        created = client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
        }).json()
        response = client.delete(f"/api/expense-items/{created['id']}")
        assert response.status_code == 204


class TestVacations:
    def test_create_with_range_and_get(self, client: TestClient):
        created = client.post("/api/vacations", json={
            "totalAmount": 15000, "payoutDate": "2025-07-04",
            "startDate": "2025-07-07", "endDate": "2025-07-09",
        })
        assert created.status_code == 201
        body = created.json()
        assert body["startDate"] == "2025-07-07"
        assert body["endDate"] == "2025-07-09"

    def test_create_without_range_defaults_to_payout_date(self, client: TestClient):
        created = client.post("/api/vacations", json={
            "totalAmount": 5000, "payoutDate": "2025-07-04",
        }).json()
        assert created["startDate"] == "2025-07-04"
        assert created["endDate"] == "2025-07-04"

    def test_start_after_end_rejected(self, client: TestClient):
        response = client.post("/api/vacations", json={
            "totalAmount": 5000, "payoutDate": "2025-07-04",
            "startDate": "2025-07-20", "endDate": "2025-07-10",
        })
        assert response.status_code == 400

    def test_delete(self, client: TestClient):
        created = client.post("/api/vacations", json={
            "totalAmount": 5000, "payoutDate": "2025-07-04",
        }).json()
        response = client.delete(f"/api/vacations/{created['id']}")
        assert response.status_code == 204


class TestBirthdays:
    def test_create_and_list(self, client: TestClient):
        created = client.post("/api/birthdays", json={
            "name": "Иванов", "birthDate": "15.03.1990", "giftAmount": 3000,
        })
        assert created.status_code == 201
        assert len(client.get("/api/birthdays").json()) == 1

    def test_invalid_date_format_rejected(self, client: TestClient):
        # Формат ДД.ММ.ГГГГ проверяется вручную в create_birthday (400),
        # а не через pydantic field-валидатор (что дало бы 422).
        response = client.post("/api/birthdays", json={
            "name": "Иванов", "birthDate": "1990-03-15", "giftAmount": 3000,
        })
        assert response.status_code == 400

    def test_update_partial_fields(self, client: TestClient):
        created = client.post("/api/birthdays", json={
            "name": "Иванов", "birthDate": "15.03.1990", "giftAmount": 3000,
        }).json()

        updated = client.put(f"/api/birthdays/{created['id']}", json={"giftAmount": 4500})

        assert updated.status_code == 200
        body = updated.json()
        assert body["giftAmount"] == 4500
        assert body["name"] == "Иванов"  # не изменилось
        assert body["birthDate"] == "15.03.1990"  # не изменилось

    def test_update_invalid_date_rejected(self, client: TestClient):
        created = client.post("/api/birthdays", json={
            "name": "Иванов", "birthDate": "15.03.1990", "giftAmount": 3000,
        }).json()

        response = client.put(f"/api/birthdays/{created['id']}", json={"birthDate": "not-a-date"})

        assert response.status_code == 400

    def test_update_missing_birthday_returns_404(self, client: TestClient):
        response = client.put("/api/birthdays/9999", json={"giftAmount": 100})
        assert response.status_code == 404

    def test_upcoming_endpoint(self, client: TestClient):
        from datetime import date, timedelta
        bd_date = date.today() + timedelta(days=5 + 14)
        client.post("/api/birthdays", json={
            "name": "Скоро", "birthDate": bd_date.strftime("%d.%m.%Y"), "giftAmount": 3000,
        })

        response = client.get("/api/birthdays/upcoming", params={"days": 30})

        assert response.status_code == 200
        alerts = response.json()
        assert len(alerts) == 1
        assert alerts[0]["daysUntil"] == 5

    def test_auto_create_expenses(self, client: TestClient):
        """Расход на подарок относится к ближайшей ПРЕДЫДУЩЕЙ дате выплаты
        (см. BirthdayService.gift_expense_period) — ожидаемый месяц/половину
        считаем тем же алгоритмом, чтобы тест не зависел от того, в какой
        день реально запускается (без флейкийности по календарю)."""
        from datetime import date, timedelta

        from calculator import BirthdayService

        today = date.today()
        bd_date = today + timedelta(days=5)
        client.post("/api/birthdays", json={
            "name": "Тест", "birthDate": bd_date.strftime("%d.%m.%Y"), "giftAmount": 2000,
        })

        default_settings = {"payout_day1": "10", "payout_day2": "25"}
        service = BirthdayService(get_setting=lambda k: default_settings.get(k, ""))
        expected_half, expected_month, expected_year = service.gift_expense_period(
            bd_date.day, bd_date.month, bd_date.year
        )

        response = client.post("/api/birthdays/auto-create-expenses")
        assert response.status_code == 200

        if (expected_month, expected_year) != (today.month, today.year):
            # Подарок относится не к текущему месяцу — эндпоинт пока не создаёт расход.
            assert response.json()["created"] == 0
            return

        assert response.json()["created"] == 1
        expenses = client.get("/api/expense-items", params={
            "month": expected_month, "year": expected_year,
        }).json()
        assert len(expenses) == 1
        assert expenses[0]["amount"] == 2000
        assert expenses[0]["half"] == expected_half


class TestDebts:
    def test_create_add_repayment_and_delete(self, client: TestClient):
        debt = client.post("/api/debts", json={
            "title": "Свете", "totalAmount": 29000, "month": 1, "year": 2026,
        }).json()

        repayment = client.post(f"/api/debts/{debt['id']}/repayments", json={
            "amount": 1100, "date": "2026-01-05",
        })
        assert repayment.status_code == 201

        listed = client.get("/api/debts").json()
        assert len(listed[0]["repayments"]) == 1

        response = client.delete(f"/api/debts/{debt['id']}")
        assert response.status_code == 204

    def test_repayment_on_missing_debt_returns_404(self, client: TestClient):
        response = client.post("/api/debts/9999/repayments", json={
            "amount": 100, "date": "2026-01-05",
        })
        assert response.status_code == 404


class TestAnalytics:
    def test_summary_groups_by_category(self, client: TestClient):
        group = client.post("/api/expense-groups", json={"name": "Продукты", "color": "#FF0000"}).json()
        client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
            "groupId": group["id"],
        })
        client.post("/api/expense-items", json={
            "name": "Без группы", "amount": 50, "half": 1, "month": 8, "year": 2026,
        })

        response = client.get("/api/analytics/summary", params={"month": 8, "year": 2026})

        data = response.json()
        assert data["total"] == pytest.approx(150.0)
        assert data["count"] == 2
        names = {c["name"] for c in data["categories"]}
        assert names == {"Продукты", "Без группы"}
