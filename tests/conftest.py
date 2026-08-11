"""conftest.py — общие фикстуры для тестов.

Все фикстуры используют SQLite ":memory:" — ничего не пишет на диск,
реальный budget.db не затрагивается.
"""

from __future__ import annotations

import pytest

from calculator import BirthdayService, SalaryCalculator
from database import DatabaseManager
from prod_calendar import CalendarService


@pytest.fixture
def db() -> DatabaseManager:
    """Изолированная in-memory БД с дефолтными настройками (см. config.AppSettings)."""
    manager = DatabaseManager(":memory:")
    yield manager
    manager.close()


@pytest.fixture
def calendar_service(db: DatabaseManager) -> CalendarService:
    """Тот же CalendarService, что собирается в api.get_calendar_service —
    реальный производственный календарь РФ, без БД-кэширования по годам."""
    return CalendarService(
        get_setting=db.get_setting,
        set_setting=db.set_setting,
        get_corrections=db.get_corrections,
        save_corrections=db.save_corrections,
        clear_calendar_cache=db.clear_calendar_cache,
        calendar_needs_fill=db.calendar_needs_fill,
        save_calendar_data=db.save_calendar_data,
        get_calendar_month=db.get_calendar_month,
    )


@pytest.fixture
def calculator(db: DatabaseManager, calendar_service: CalendarService) -> SalaryCalculator:
    """SalaryCalculator, собранный ровно так же, как api.get_salary_calculator."""
    return SalaryCalculator(
        get_setting=db.get_setting,
        vacations=db,
        calendar_reader=calendar_service,
    )


@pytest.fixture
def birthday_service(db: DatabaseManager) -> BirthdayService:
    return BirthdayService(get_setting=db.get_setting)
