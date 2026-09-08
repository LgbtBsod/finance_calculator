"""CalculatorModule — обёртка над calculator.SalaryCalculator.

Настройки берутся снапшотом (один ``db:get_settings_bundle`` на операцию, а не
10 вызовов get_setting). Отпускные и календарь — через kernel-backed шимы,
определённые в этом же пакете (не живые модули-соседи).

Возвращает frozen-dataclass'ы ``SalaryBreakdown`` / ``BalanceResult`` как есть —
ядро пропускает иммутабельные dataclass'ы (см. core/_validate). Потребитель
(finance) читает поля по имени, без промежуточной stringly-typed таблицы.
"""

from __future__ import annotations

from calculator import SalaryCalculator
from core.module import Module
from models import BalanceResult, SalaryBreakdown

from ._shims import KernelCalendarReader, KernelSalaryReader, KernelVacationReader


class CalculatorModule(Module):
    name = "calculator"
    requires = ("db", "calendar")

    def __init__(self) -> None:
        super().__init__()
        self._vacs: KernelVacationReader | None = None
        self._cal: KernelCalendarReader | None = None
        self._salaries: KernelSalaryReader | None = None

    def initialize(self) -> None:
        self._vacs = KernelVacationReader(self.k)
        self._cal = KernelCalendarReader(self.k)
        self._salaries = KernelSalaryReader(self.k)
        # Инвариант: коллабораторы SalaryCalculator определены в ЭТОМ пакете.
        assert type(self._vacs).__module__.startswith("modules.calculator")
        assert type(self._cal).__module__.startswith("modules.calculator")
        assert type(self._salaries).__module__.startswith("modules.calculator")
        self._actions = {
            "calculate": self._calculate,
            "balance": self._balance,
            "payout_dates": self._payout_dates,
        }

    def _make_calc(self) -> SalaryCalculator:
        snapshot = dict(self.k.request("db", "get_settings_bundle"))
        return SalaryCalculator(
            get_setting=lambda key: str(snapshot.get(key, "")),
            salaries=self._salaries,
            vacations=self._vacs,
            calendar_reader=self._cal,
        )

    # ── actions ──────────────────────────────────────────────

    def _calculate(self, year: int, month: int) -> SalaryBreakdown:
        return self._make_calc().calculate(year, month)

    def _balance(self, year: int, month: int) -> BalanceResult:
        expenses = self.k.request("db", "get_expenses", month=month, year=year)
        return self._make_calc().balance(year, month, expenses)

    def _payout_dates(self, year: int, month: int) -> dict:
        calc = self._make_calc()
        real1, real2 = calc.payout_dates(year, month)
        nom1, nom2 = calc.nominal_payout_dates(year, month)
        return {
            "payout_date_1": real1.isoformat(),
            "payout_date_2": real2.isoformat(),
            "nominal_1": nom1.isoformat(),
            "nominal_2": nom2.isoformat(),
        }
