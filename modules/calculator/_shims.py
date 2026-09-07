"""Kernel-backed адаптеры для конструктора SalaryCalculator.

SalaryCalculator принимает ``vacations`` (объект с .get_vacations) и
``calendar_reader`` (объект с .get_working_days / .classify_day). Вместо того
чтобы отдать ему живые модули-соседи, отдаём эти шимы: их методы —
замыкания ТОЛЬКО над ``view.request(...)``. Модуль-потребитель определяет их
внутри своего пакета — так статический тест изоляции остаётся валиден, а
runtime-ассерт (``__module__.startswith('modules.calculator')``) ловит
случайную подмену на настоящий модуль.
"""

from __future__ import annotations

from datetime import date

from models import DayKind


class KernelVacationReader:
    """Реализует models.VacationReader через ядро."""

    def __init__(self, view) -> None:
        self._k = view

    def get_vacations(self, month=None, year=None):  # noqa: ANN001
        return self._k.request("db", "get_vacations", month=month, year=year)


class KernelCalendarReader:
    """Реализует models.CalendarReader через ядро.

    ``classify_day`` зовётся SalaryCalculator в поцикловых обходах по дням —
    поэтому первый вызов подтягивает классификацию всего года батчем
    (``calendar.classify_range``), дальше — из локального словаря.
    """

    def __init__(self, view) -> None:
        self._k = view
        self._year_cache: dict[int, dict[str, str]] = {}

    def get_working_days(self, year: int, month: int) -> tuple[float, float, float]:
        total, h1, h2 = self._k.request(
            "calendar", "get_working_days", year=year, month=month
        )
        return total, h1, h2

    def _ensure_year(self, year: int) -> dict[str, str]:
        if year not in self._year_cache:
            self._year_cache[year] = self._k.request(
                "calendar", "classify_range",
                start=f"{year}-01-01", end=f"{year}-12-31",
            )
        return self._year_cache[year]

    def classify_day(self, d: date) -> DayKind:
        kinds = self._ensure_year(d.year)
        raw = kinds.get(d.isoformat())
        if raw is None:
            raw = self._k.request("calendar", "classify_day", iso=d.isoformat())
        return DayKind(raw)
