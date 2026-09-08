"""Тесты модулей через ядро (фикстура kernel из conftest)."""

from __future__ import annotations

import pytest


def req(kernel, target, action, **kw):
    return kernel.view("test").request(target, action, **kw)


class TestDBModule:
    def test_settings_bundle(self, kernel):
        b = req(kernel, "db", "get_settings_bundle")
        assert b["base_salary"] == "100000.0"

    def test_expense_crud_and_events(self, kernel):
        events = []
        kernel.view("t").subscribe("db:changed", lambda entity, **_: events.append(entity))

        g = req(kernel, "db", "create_expense_group", group_id="g1", name="X",
                color="#000000", parent_id=None, sort_order=0, monthly_limit=None)
        assert g["id"] == "g1"
        res = req(kernel, "db", "add_expense", name="a", amount=10, half=1, month=1,
                  year=2025, is_recurring=False, group_id="g1", recurring_until=None)
        eid = res["id"]
        upd = req(kernel, "db", "update_expense", eid=eid, amount=25)
        assert upd["amount"] == 25 and upd["name"] == "a"
        req(kernel, "db", "delete_expense", eid=eid)
        assert req(kernel, "db", "get_expenses") == []
        assert "expenses" in events and "expense_groups" in events

    def test_income_crud_and_events(self, kernel):
        events = []
        kernel.view("t").subscribe("db:changed", lambda entity, **_: events.append(entity))

        res = req(kernel, "db", "add_income", name="Аренда", amount=15000, half=1,
                  month=3, year=2025, is_recurring=True, recurring_until=None)
        iid = res["id"]
        assert len(req(kernel, "db", "get_income", month=9, year=2025)) == 1  # спроецирован
        upd = req(kernel, "db", "update_income", iid=iid, amount=20000)
        assert upd["amount"] == 20000
        req(kernel, "db", "delete_income", iid=iid)
        assert req(kernel, "db", "get_income") == []
        assert events.count("income") == 3

    def test_update_missing_income_is_user_facing(self, kernel):
        from core.errors import UserFacingError

        with pytest.raises(UserFacingError):
            req(kernel, "db", "update_income", iid=999999, amount=1)

    def test_debt_planned_payment_roundtrip(self, kernel):
        res = req(kernel, "db", "create_debt", title="Кредит", total_amount=100000,
                  month=1, year=2026, monthly_payment=8000, payment_half=1)
        req(kernel, "db", "update_debt", debt_id=res["id"], payment_half=2)
        d = req(kernel, "db", "get_debts")[0]
        assert d["monthly_payment"] == 8000 and d["payment_half"] == 2

    def test_backup_rejects_memory(self, kernel):
        from core.errors import ValidationError

        with pytest.raises(ValidationError):
            req(kernel, "db", "backup_to", target_path="/tmp/x.db")

    def test_update_missing_expense_is_user_facing(self, kernel):
        from core.errors import UserFacingError

        with pytest.raises(UserFacingError):  # не голый KernelError
            req(kernel, "db", "update_expense", eid=999999, amount=1)


class TestCalendarModule:
    def test_working_days(self, kernel):
        total, h1, h2 = req(kernel, "calendar", "get_working_days", year=2025, month=7)
        assert total > 0 and abs((h1 + h2) - total) < 1e-6

    def test_classify_range(self, kernel):
        out = req(kernel, "calendar", "classify_range", start="2025-01-01", end="2025-01-07")
        assert out["2025-01-01"] in {"holiday", "weekend", "working", "shortened"}
        assert len(out) == 7


class TestCalculatorModule:
    def test_balance_shape(self, kernel):
        b = req(kernel, "calculator", "balance", year=2025, month=7)
        assert set(b) == {"salary", "expenses_h1", "expenses_h2", "balance_h1", "balance_h2"}
        assert b["salary"]["net_salary"] > 0

    def test_settings_snapshot_used(self, kernel):
        req(kernel, "db", "set_setting", key="base_salary", value="200000")
        b = req(kernel, "calculator", "calculate", year=2025, month=7)
        # 200000 * 1.0 * (1 - 0.13)
        assert b["net_salary"] == pytest.approx(174000.0)


class TestBirthdaysModule:
    def test_upcoming(self, kernel):
        req(kernel, "db", "add_birthday", name="Иван", birth_date="01.01.1990", gift_amount=1000)
        alerts = req(kernel, "birthdays", "upcoming", days=400)
        assert isinstance(alerts, list)


class TestFinanceModule:
    def test_balance_cached(self, kernel):
        b1 = req(kernel, "finance", "balance", month=7, year=2025)
        b2 = req(kernel, "finance", "balance", month=7, year=2025)
        assert b1 == b2
        stats = req(kernel, "cache", "stats")
        assert stats["hits"] >= 1

    def test_cache_invalidated_on_expense_change(self, kernel):
        req(kernel, "finance", "analytics_summary", month=7, year=2025)
        req(kernel, "db", "add_expense", name="x", amount=999, half=1, month=7, year=2025,
            is_recurring=False, group_id=None, recurring_until=None)
        s = req(kernel, "finance", "analytics_summary", month=7, year=2025)
        assert s["total"] == 999  # пересчитано, не из кэша

    def test_settings_roundtrip(self, kernel):
        req(kernel, "finance", "settings_update", updates={"baseSalary": 123456})
        assert req(kernel, "finance", "settings_get")["baseSalary"] == 123456

    def test_settings_change_invalidates_balance_cache(self, kernel):
        b1 = req(kernel, "finance", "balance", month=7, year=2025)
        req(kernel, "finance", "settings_update",
            updates={"baseSalary": 999999, "taxRate": 0, "kef": 1.0})
        b2 = req(kernel, "finance", "balance", month=7, year=2025)
        assert b2["netSalary"] == 999999 and b2 != b1  # пересчитано, не из кэша

    def test_income_added_to_balance_half(self, kernel):
        b0 = req(kernel, "finance", "balance", month=7, year=2025)
        req(kernel, "db", "add_income", name="Аренда", amount=20000, half=1,
            month=7, year=2025, is_recurring=False, recurring_until=None)
        b1 = req(kernel, "finance", "balance", month=7, year=2025)
        assert b1["incomeHalf1"] == 20000  # инвалидация кэша по db:changed
        assert b1["balanceHalf1"] == pytest.approx(b0["balanceHalf1"] + 20000)

    def test_planned_debt_payment_deducted_from_balance_half(self, kernel):
        b0 = req(kernel, "finance", "balance", month=7, year=2025)
        req(kernel, "db", "create_debt", title="Кредит", total_amount=100000,
            month=1, year=2025, monthly_payment=8000, payment_half=2)
        b1 = req(kernel, "finance", "balance", month=7, year=2025)
        assert b1["debtPaymentHalf2"] == 8000
        assert b1["balanceHalf2"] == pytest.approx(b0["balanceHalf2"] - 8000)

    def test_repaid_debt_stops_deducting_planned_payment(self, kernel):
        res = req(kernel, "db", "create_debt", title="X", total_amount=5000,
                  month=1, year=2025, monthly_payment=1000, payment_half=2)
        req(kernel, "db", "add_debt_repayment", debt_id=res["id"], amount=5000,
            date="2025-01-05", note=None)
        b = req(kernel, "finance", "balance", month=7, year=2025)
        assert b["debtPaymentHalf2"] == 0


class TestUpdaterModule:
    def test_current_version(self, kernel):
        v = req(kernel, "updater", "current_version")
        assert isinstance(v, str)

    def test_check_skips_when_recently_checked(self, kernel):
        from unittest.mock import patch

        with patch("modules.updater.module._recently_checked", return_value=True):
            res = req(kernel, "updater", "check", force=False)
        assert res["skipped"] is True and res["has_update"] is False

    def test_check_reports_update(self, kernel):
        from unittest.mock import MagicMock, patch

        fake = MagicMock()
        fake.check_for_updates.return_value = (True, "9.9.9", "https://x/u.exe")
        fake._rate_limited = False
        fake._network_reachable = True
        with patch("modules.updater.module._recently_checked", return_value=False), \
             patch("modules.updater.module.AutoUpdater", return_value=fake), \
             patch("modules.updater.module._mark_checked") as mark:
            res = req(kernel, "updater", "check", force=True)
        assert res == {
            "has_update": True, "version": "9.9.9", "url": "https://x/u.exe",
            "rate_limited": False, "reachable": True, "skipped": False,
        }
        mark.assert_called_once()
