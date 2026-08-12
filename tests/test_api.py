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

    @pytest.mark.parametrize(
        "payload",
        [
            {"taxRate": 500},  # выше 100%
            {"taxRate": -1},  # отрицательный
            {"baseSalary": -1},  # отрицательная зарплата
            {"payoutDay1": 32},  # за пределами дней месяца
            {"firstHalfRatio": 1.5},  # выше 1.0
            {"salaryCalculationMethod": "not_a_real_method"},
        ],
    )
    def test_out_of_range_values_rejected(self, client: TestClient, payload):
        """Границы зеркалят zod-схему SettingsPage.tsx, но та защищает только
        UI — без Field(...) на бэкенде прямой PUT мимо формы мог записать
        любое значение без проверки."""
        response = client.put("/api/settings", json=payload)
        assert response.status_code == 422

    def test_account_shortened_toggle_actually_affects_working_days_calculation(
        self, client: TestClient
    ):
        """Регрессия: account_shortened сравнивался с "1" вместо "true" —
        переключатель не имел эффекта ни при каком положении."""
        client.put("/api/settings", json={
            "baseSalary": 100000, "taxRate": 13, "kef": 1.0,
            "salaryCalculationMethod": "working_days",
            "accountShortened": False,
        })
        off = client.get("/api/balance", params={"month": 7, "year": 2025}).json()

        client.put("/api/settings", json={"accountShortened": True})
        on = client.get("/api/balance", params={"month": 7, "year": 2025}).json()

        assert off["toPayHalf1"] != on["toPayHalf1"] or off["toPayHalf2"] != on["toPayHalf2"]


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

    def test_create_and_update_monthly_limit(self, client: TestClient):
        group = client.post("/api/expense-groups", json={
            "name": "Продукты", "color": "#FF0000", "monthlyLimit": 15000,
        }).json()
        assert group["monthlyLimit"] == 15000

        updated = client.put(f"/api/expense-groups/{group['id']}", json={"monthlyLimit": 20000})
        assert updated.json()["monthlyLimit"] == 20000

    def test_update_can_explicitly_clear_parent_id(self, client: TestClient):
        """Регрессия: null для parentId был неотличим от 'поле не передано' —
        подкатегорию нельзя было разгруппировать."""
        parent = client.post("/api/expense-groups", json={"name": "Родитель", "color": "#111111"}).json()
        child = client.post("/api/expense-groups", json={
            "name": "Дочерняя", "color": "#222222", "parentId": parent["id"],
        }).json()
        assert child["parentId"] == parent["id"]

        updated = client.put(f"/api/expense-groups/{child['id']}", json={"parentId": None})

        assert updated.json()["parentId"] is None

    def test_update_omitting_parent_id_leaves_it_unchanged(self, client: TestClient):
        parent = client.post("/api/expense-groups", json={"name": "Родитель", "color": "#111111"}).json()
        child = client.post("/api/expense-groups", json={
            "name": "Дочерняя", "color": "#222222", "parentId": parent["id"],
        }).json()

        updated = client.put(f"/api/expense-groups/{child['id']}", json={"name": "Переименована"})

        assert updated.json()["parentId"] == parent["id"]

    def test_creating_a_group_with_parent_id_gets_its_own_fresh_id(self, client: TestClient):
        """Регрессия: `parentId` ошибочно переиспользовался как ID новой
        группы — вторая подкатегория с тем же родителем падала с
        UNIQUE constraint failed (id совпадал с id родителя)."""
        parent = client.post("/api/expense-groups", json={"name": "Родитель", "color": "#111111"}).json()

        child1 = client.post("/api/expense-groups", json={
            "name": "Дочерняя 1", "color": "#222222", "parentId": parent["id"],
        })
        child2 = client.post("/api/expense-groups", json={
            "name": "Дочерняя 2", "color": "#333333", "parentId": parent["id"],
        })

        assert child1.status_code == 201
        assert child2.status_code == 201
        ids = {parent["id"], child1.json()["id"], child2.json()["id"]}
        assert len(ids) == 3  # все три id разные — не совпадают с id родителя


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

    def test_recurring_expense_is_projected_into_a_later_month(self, client: TestClient):
        client.post("/api/expense-items", json={
            "name": "Кредит", "amount": 5000, "half": 1, "month": 8, "year": 2026,
            "isRecurring": True,
        })

        september = client.get("/api/expense-items", params={"month": 9, "year": 2026}).json()

        assert len(september) == 1
        assert september[0]["name"] == "Кредит"
        assert september[0]["month"] == 9  # показан в контексте запрошенного периода
        assert september[0]["year"] == 2026

    def test_recurring_until_stops_the_projection(self, client: TestClient):
        client.post("/api/expense-items", json={
            "name": "Кредит", "amount": 5000, "half": 1, "month": 1, "year": 2026,
            "isRecurring": True, "recurringUntil": "2026-03-15",
        })

        assert len(client.get("/api/expense-items", params={"month": 3, "year": 2026}).json()) == 1
        assert client.get("/api/expense-items", params={"month": 4, "year": 2026}).json() == []

    def test_update_can_explicitly_clear_recurring_until(self, client: TestClient):
        created = client.post("/api/expense-items", json={
            "name": "Кредит", "amount": 5000, "half": 1, "month": 1, "year": 2026,
            "isRecurring": True, "recurringUntil": "2026-02-28",
        }).json()
        assert client.get("/api/expense-items", params={"month": 3, "year": 2026}).json() == []

        updated = client.put(f"/api/expense-items/{created['id']}", json={"recurringUntil": None})

        assert updated.status_code == 200
        assert updated.json()["recurringUntil"] is None
        assert len(client.get("/api/expense-items", params={"month": 3, "year": 2026}).json()) == 1

    def test_update_omitting_recurring_until_leaves_it_unchanged(self, client: TestClient):
        created = client.post("/api/expense-items", json={
            "name": "Кредит", "amount": 5000, "half": 1, "month": 1, "year": 2026,
            "isRecurring": True, "recurringUntil": "2026-06-30",
        }).json()

        updated = client.put(f"/api/expense-items/{created['id']}", json={"amount": 5500})

        assert updated.status_code == 200
        assert updated.json()["recurringUntil"] == "2026-06-30"

    def test_update_can_explicitly_clear_group_id(self, client: TestClient):
        """Регрессия: null для groupId был неотличим от 'поле не передано' —
        расход нельзя было вернуть 'без группы'."""
        group = client.post("/api/expense-groups", json={"name": "Продукты", "color": "#FF0000"}).json()
        created = client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
            "groupId": group["id"],
        }).json()
        assert created["groupId"] == group["id"]

        updated = client.put(f"/api/expense-items/{created['id']}", json={"groupId": None})

        assert updated.json()["groupId"] is None

    def test_update_omitting_group_id_leaves_it_unchanged(self, client: TestClient):
        group = client.post("/api/expense-groups", json={"name": "Продукты", "color": "#FF0000"}).json()
        created = client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
            "groupId": group["id"],
        }).json()

        updated = client.put(f"/api/expense-items/{created['id']}", json={"amount": 150})

        assert updated.json()["groupId"] == group["id"]

    def test_create_returns_the_actual_new_record_not_a_sibling_by_sort_order(
        self, client: TestClient
    ):
        """Регрессия: create_expense_item брал expenses[-1] из списка,
        отсортированного `ORDER BY half, id` — при создании half=1, когда в
        периоде уже есть half=2, [-1] был бы чужой записью."""
        client.post("/api/expense-items", json={
            "name": "Существующий (half=2)", "amount": 999, "half": 2, "month": 8, "year": 2026,
        })

        created = client.post("/api/expense-items", json={
            "name": "Новый (half=1)", "amount": 100, "half": 1, "month": 8, "year": 2026,
        }).json()

        assert created["name"] == "Новый (half=1)"
        assert created["amount"] == 100
        assert created["half"] == 1
        get_response = client.get("/api/expense-items", params={"month": 8, "year": 2026}).json()
        matching = [i for i in get_response if i["id"] == created["id"]]
        assert len(matching) == 1
        assert matching[0]["name"] == "Новый (half=1)"

    def test_recurring_until_malformed_date_rejected(self, client: TestClient):
        response = client.post("/api/expense-items", json={
            "name": "X", "amount": 100, "half": 1, "month": 8, "year": 2026,
            "isRecurring": True, "recurringUntil": "не дата",
        })
        assert response.status_code == 400


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

    def test_create_returns_the_actual_new_record_not_a_sibling_by_sort_order(
        self, client: TestClient
    ):
        """Регрессия: create_vacation брал vacations[-1] из списка,
        отсортированного `ORDER BY payout_date` — при создании отпускных с
        более РАННЕЙ датой выплаты, чем у уже существующих, [-1] был бы
        чужой записью."""
        existing = client.post("/api/vacations", json={
            "totalAmount": 999, "payoutDate": "2025-07-20",
        }).json()

        created = client.post("/api/vacations", json={
            "totalAmount": 5000, "payoutDate": "2025-07-01",  # раньше существующей
        }).json()

        assert created["totalAmount"] == 5000
        assert created["payoutDate"] == "2025-07-01"
        assert created["id"] != existing["id"]


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

    def test_create_returns_the_actual_new_record_not_a_sibling_by_sort_order(
        self, client: TestClient
    ):
        """Регрессия: create_birthday брал birthdays[-1] из списка,
        отсортированного по birth_date — при создании ДР, который в
        (тогда лексикографической) сортировке строк оказывался не последним,
        [-1] был бы чужой записью."""
        existing = client.post("/api/birthdays", json={
            "name": "Существующий", "birthDate": "20.05.1990", "giftAmount": 999,
        }).json()

        created = client.post("/api/birthdays", json={
            "name": "Новый", "birthDate": "01.01.1990", "giftAmount": 3000,
        }).json()

        assert created["name"] == "Новый"
        assert created["giftAmount"] == 3000
        assert created["id"] != existing["id"]

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

    def test_repayment_malformed_date_rejected(self, client: TestClient):
        debt = client.post("/api/debts", json={
            "title": "X", "totalAmount": 1000, "month": 1, "year": 2026,
        }).json()

        response = client.post(f"/api/debts/{debt['id']}/repayments", json={
            "amount": 100, "date": "не дата",
        })

        assert response.status_code == 400

    def test_debt_response_exposes_repaid_and_remaining_amount(self, client: TestClient):
        debt = client.post("/api/debts", json={
            "title": "Света", "totalAmount": 29000, "month": 1, "year": 2026,
        }).json()
        assert debt["repaidAmount"] == 0
        assert debt["remainingAmount"] == 29000

        client.post(f"/api/debts/{debt['id']}/repayments", json={
            "amount": 3800, "date": "2026-01-05",
        })

        listed = client.get("/api/debts").json()[0]
        assert listed["repaidAmount"] == pytest.approx(3800.0)
        assert listed["remainingAmount"] == pytest.approx(25200.0)

    def test_add_repayment_returns_the_actual_new_record_not_a_sibling_by_sort_order(
        self, client: TestClient
    ):
        """Регрессия: add_debt_repayment брал repayments[-1] из списка,
        отсортированного `ORDER BY date` — при добавлении погашения с более
        РАННЕЙ датой, чем у уже существующего, [-1] был бы чужой записью."""
        debt = client.post("/api/debts", json={
            "title": "X", "totalAmount": 10000, "month": 1, "year": 2026,
        }).json()
        existing = client.post(f"/api/debts/{debt['id']}/repayments", json={
            "amount": 999, "date": "2026-01-20",
        }).json()

        created = client.post(f"/api/debts/{debt['id']}/repayments", json={
            "amount": 500, "date": "2026-01-01",  # раньше существующего платежа
        }).json()

        assert created["amount"] == 500
        assert created["date"] == "2026-01-01"
        assert created["id"] != existing["id"]


class TestBackup:
    def test_backup_unavailable_for_in_memory_db_returns_400(self, client: TestClient):
        # Тестовая БД в этой фикстуре — ":memory:", как и должно быть у всех
        # тестов; резервное копирование для неё осмысленно недоступно.
        response = client.get("/api/backup")
        assert response.status_code == 400

    def test_download_backup_returns_a_valid_sqlite_file(self, tmp_path):
        # Резервная копия осмысленна только для файловой БД — здесь
        # переопределяем get_db на временный файл вместо ":memory:" из
        # стандартной фикстуры client.
        db_path = str(tmp_path / "test_budget.db")
        file_db = DatabaseManager(db_path)

        def override_get_db():
            yield file_db

        api_module.app.dependency_overrides[api_module.get_db] = override_get_db
        try:
            with TestClient(api_module.app) as c:
                c.post("/api/expense-items", json={
                    "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026,
                })
                response = c.get("/api/backup")

                assert response.status_code == 200
                assert response.content[:16] == b"SQLite format 3\x00"
        finally:
            api_module.app.dependency_overrides.clear()
            file_db.close()


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

    def test_summary_exposes_group_id_and_monthly_limit_for_overspend_highlighting(
        self, client: TestClient
    ):
        group = client.post("/api/expense-groups", json={
            "name": "Продукты", "color": "#FF0000", "monthlyLimit": 200,
        }).json()
        client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 250, "half": 1, "month": 8, "year": 2026,
            "groupId": group["id"],
        })
        client.post("/api/expense-items", json={
            "name": "Без группы", "amount": 50, "half": 1, "month": 8, "year": 2026,
        })

        response = client.get("/api/analytics/summary", params={"month": 8, "year": 2026})

        categories = {c["name"]: c for c in response.json()["categories"]}
        assert categories["Продукты"]["groupId"] == group["id"]
        assert categories["Продукты"]["monthlyLimit"] == 200
        assert categories["Продукты"]["amount"] > categories["Продукты"]["monthlyLimit"]  # превышение
        assert categories["Без группы"]["groupId"] is None
        assert categories["Без группы"]["monthlyLimit"] is None

    def test_trend_returns_months_in_chronological_order(self, client: TestClient):
        client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 6, "year": 2026,
        })
        client.post("/api/expense-items", json={
            "name": "Хлеб", "amount": 50, "half": 1, "month": 8, "year": 2026,
        })

        response = client.get("/api/analytics/trend", params={"month": 8, "year": 2026, "months": 3})

        data = response.json()["months"]
        assert [(m["year"], m["month"]) for m in data] == [(2026, 6), (2026, 7), (2026, 8)]
        assert data[0]["total"] == pytest.approx(100.0)
        assert data[1]["total"] == pytest.approx(0.0)
        assert data[2]["total"] == pytest.approx(50.0)

    def test_trend_handles_year_wraparound(self, client: TestClient):
        # Февраль 2026, 3 месяца -> должно уйти в декабрь 2025.
        response = client.get("/api/analytics/trend", params={"month": 2, "year": 2026, "months": 3})

        data = response.json()["months"]
        assert [(m["year"], m["month"]) for m in data] == [(2025, 12), (2026, 1), (2026, 2)]

    def test_trend_projects_recurring_expense_into_every_month(self, client: TestClient):
        client.post("/api/expense-items", json={
            "name": "Подписка", "amount": 500, "half": 1, "month": 6, "year": 2026,
            "isRecurring": True, "recurringUntil": None,
        })

        response = client.get("/api/analytics/trend", params={"month": 8, "year": 2026, "months": 3})

        totals = [m["total"] for m in response.json()["months"]]
        assert totals == [pytest.approx(500.0)] * 3

    def test_trend_groups_categories_by_group_id_with_color_and_none_bucket(self, client: TestClient):
        group = client.post("/api/expense-groups", json={"name": "Продукты", "color": "#FF0000"}).json()
        client.post("/api/expense-items", json={
            "name": "Молоко", "amount": 100, "half": 1, "month": 8, "year": 2026, "groupId": group["id"],
        })
        client.post("/api/expense-items", json={
            "name": "Прочее", "amount": 30, "half": 1, "month": 8, "year": 2026,
        })

        response = client.get("/api/analytics/trend", params={"month": 8, "year": 2026, "months": 2})

        last_month = response.json()["months"][-1]
        by_name = {c["name"]: c for c in last_month["categories"]}
        assert by_name["Продукты"]["groupId"] == group["id"]
        assert by_name["Продукты"]["color"] == "#FF0000"
        assert by_name["Без группы"]["groupId"] is None
