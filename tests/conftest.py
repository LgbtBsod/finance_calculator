"""conftest.py — общие фикстуры.

Низкоуровневые фикстуры (db / calendar_service / calculator / birthday_service)
конструируют легаси-классы напрямую — ядро им не нужно, легаси остаётся
kernel-agnostic. Фикстуры kernel / service поднимают полное ядро со всеми
модулями на изолированной in-memory БД (свежее ядро на каждый тест).
"""

from __future__ import annotations

import pytest

from calculator import BirthdayService, SalaryCalculator
from core.bootstrap import build_kernel
from database import DatabaseManager
from prod_calendar import CalendarService
from services import FinanceService


@pytest.fixture
def db() -> DatabaseManager:
    manager = DatabaseManager(":memory:")
    yield manager
    manager.close()


@pytest.fixture
def calendar_service(db: DatabaseManager) -> CalendarService:
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
    return SalaryCalculator(
        get_setting=db.get_setting,
        vacations=db,
        calendar_reader=calendar_service,
    )


@pytest.fixture
def birthday_service(db: DatabaseManager) -> BirthdayService:
    return BirthdayService(get_setting=db.get_setting)


@pytest.fixture
def kernel():
    """Полное ядро (7 модулей) на изолированной in-memory БД.

    strict=True — ядро валидирует и возвращаемые значения хендлеров (ловит
    модуль, случайно вернувший живой объект).
    """
    k = build_kernel(":memory:", strict=True)
    yield k
    k.shutdown()


@pytest.fixture
def service(kernel) -> FinanceService:
    """Фасад GUI поверх ядра из фикстуры kernel."""
    return FinanceService(kernel)


@pytest.fixture
def add_salary(service):
    """Хелпер: завести оклад-доход (kind='salary'). По умолчанию 100000/мес,
    пропорционально, действует с января 2000 (т.е. всегда активен)."""
    def _add(amount: float = 100000.0, *, method: str = "proportional", kef: float = 1.0,
             month: int = 1, year: int = 2000, name: str = "ЗП", **kw):
        return service.create_income(
            name=name, amount=amount, half=1, month=month, year=year, kind="salary",
            kef=kef, split_method=method, first_half_ratio=0.4, second_half_ratio=0.6, **kw,
        )
    return _add


@pytest.fixture
def file_service(tmp_path) -> FinanceService:
    """Фасад поверх ядра с файловой БД (нужен для backup)."""
    svc = FinanceService(build_kernel(str(tmp_path / "budget.db")))
    yield svc
    svc.close()
