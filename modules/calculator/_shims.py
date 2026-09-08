"""Kernel-backed адаптеры для конструктора SalaryCalculator.

SalaryCalculator принимает ``vacations`` (объект с .get_vacations) и
``calendar_reader`` (объект с .get_working_days / .classify_day). Вместо живых
модулей-соседей отдаём эти шимы: их методы — замыкания ТОЛЬКО над
``view.request(...)``. Модуль-потребитель определяет их внутри своего пакета —
так статический тест изоляции остаётся валиден, а runtime-ассерт
(``__module__.startswith('modules.calculator')``) ловит случайную подмену.

Шимы БЕЗ состояния: SalaryCalculator за один balance() зовёт classify_day
считанные разы (откат даты выплаты с выходного + рабочие дни отпуска), каждый
вызов — один hop к модулю calendar. Кэшировать классификацию года в шиме
нельзя: экземпляр живёт всё время процесса и не узнаёт про calendar:changed
(импорт PDF-поправок), а также делится между потоками сессий.
"""

from __future__ import annotations

from datetime import date

from models import DayKind


class KernelVacationReader:
    """models.VacationReader через ядро."""

    def __init__(self, view) -> None:
        self._k = view

    def get_vacations(self, month=None, year=None):  # noqa: ANN001
        return self._k.request("db", "get_vacations", month=month, year=year)


class KernelCalendarReader:
    """models.CalendarReader через ядро."""

    def __init__(self, view) -> None:
        self._k = view

    def get_working_days(self, year: int, month: int) -> tuple[float, float, float]:
        total, h1, h2 = self._k.request("calendar", "get_working_days", year=year, month=month)
        return total, h1, h2

    def classify_day(self, d: date) -> DayKind:
        return DayKind(self._k.request("calendar", "classify_day", iso=d.isoformat()))
