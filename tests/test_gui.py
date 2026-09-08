"""Лёгкие тесты GUI-слоя: форматтеры, prefs, тема и то, что каждое вью
строится без исключений (без запуска Flet-сервера)."""

from __future__ import annotations

from datetime import date

import pytest

from core.bootstrap import build_kernel
from gui import theme
from gui.format import (
    build_birth_date_for_api,
    format_currency,
    format_date_long_ru,
    format_date_ru,
    parse_birth_date,
    pluralize_ru,
)
from gui.prefs import Prefs
from services import FinanceService

NBSP = " "


class TestFormat:
    def test_currency(self):
        assert format_currency(0) == f"0{NBSP}₽"
        assert format_currency(1234567.5) == f"1{NBSP}234{NBSP}568{NBSP}₽"
        assert format_currency(-500) == f"-500{NBSP}₽"
        assert format_currency(None) == f"0{NBSP}₽"

    def test_dates(self):
        assert format_date_ru("2026-08-10") == "10.08.2026"
        assert format_date_ru(None) == ""
        assert format_date_long_ru("2026-08-10") == "10 августа 2026"

    def test_birthday_helpers(self):
        assert build_birth_date_for_api(5, 3) == "05.03.2000"
        assert parse_birth_date("05.03.2000") == (5, 3)
        assert parse_birth_date("junk") is None

    def test_plural(self):
        assert pluralize_ru(1, "a", "b", "c") == "a"
        assert pluralize_ru(3, "a", "b", "c") == "b"
        assert pluralize_ru(5, "a", "b", "c") == "c"
        assert pluralize_ru(11, "a", "b", "c") == "c"


class TestPrefs:
    def test_roundtrip(self, tmp_path):
        p = Prefs(tmp_path / "prefs.json")
        assert p.get("theme_mode") == "system"
        p.update(theme_mode="dark", skipped_update_version="2.0.0")

        p2 = Prefs(tmp_path / "prefs.json")
        assert p2.get("theme_mode") == "dark"
        assert p2.get("skipped_update_version") == "2.0.0"

    def test_invalid_theme_falls_back(self, tmp_path):
        path = tmp_path / "prefs.json"
        path.write_text('{"theme_mode": "neon"}', encoding="utf-8")
        assert Prefs(path).get("theme_mode") == "system"

    def test_corrupt_file_tolerated(self, tmp_path):
        path = tmp_path / "prefs.json"
        path.write_text("{ not json", encoding="utf-8")
        assert Prefs(path).get("check_updates_on_start") is True


class TestTheme:
    def test_apply_light_dark(self):
        theme.apply("light")
        assert theme.COLORS["bg"] == "#f5f6f8"
        theme.apply("dark")
        assert theme.COLORS["bg"] == "#0f141a"
        theme.apply("system", system_is_dark=True)
        assert theme.COLORS["bg"] == "#0f141a"
        theme.apply("light")

    def test_build_theme_ok(self):
        assert theme.build_theme(dark=True) is not None
        assert theme.build_theme(dark=False) is not None


class _FakeApp:
    def __init__(self, svc, prefs):
        self.service = svc
        self.page = None
        self.prefs = prefs

    def _ensure_theme(self):  # вью вызывает при render(); в тестах — no-op
        pass


@pytest.fixture
def fake_app(tmp_path):
    svc = FinanceService(build_kernel(":memory:"))
    g = svc.create_expense_group(name="Food", color="#ff0000", monthly_limit=5000)
    svc.create_expense(name="x", amount=1500, half=1, month=date.today().month,
                       year=date.today().year, group_id=g["id"])
    svc.create_vacation(total_amount=30000, payout_date=f"{date.today().year}-06-15")
    svc.create_birthday(name="Ivan", birth_date="15.06.1990", gift_amount=2000)
    d = svc.create_debt(title="Loan", total_amount=50000)
    svc.add_repayment(d["id"], amount=5000)
    app = _FakeApp(svc, Prefs(tmp_path / "p.json"))
    yield app
    svc.close()


def test_all_views_render(fake_app):
    from gui.views.analytics import AnalyticsView
    from gui.views.balance import BalanceView
    from gui.views.birthdays import BirthdaysView
    from gui.views.debts import DebtsView
    from gui.views.expenses import ExpensesView, GroupsView
    from gui.views.income import IncomeView
    from gui.views.settings import SettingsView
    from gui.views.vacations import VacationsView

    fake_app.service.create_income(name="Аренда", amount=20000, half=1,
                                   month=date.today().month, year=date.today().year)

    for cls in (
        BalanceView, IncomeView, ExpensesView, GroupsView, VacationsView,
        BirthdaysView, DebtsView, AnalyticsView, SettingsView,
    ):
        assert cls(fake_app).render() is not None
