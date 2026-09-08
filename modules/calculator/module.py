"""CalculatorModule — обёртка над calculator.SalaryCalculator.

Настройки берутся снапшотом (один ``db:get_settings_bundle`` на операцию, а не
10 вызовов get_setting). Отпускные и календарь — через kernel-backed шимы,
определённые в этом же пакете (не живые модули-соседи).
"""

from __future__ import annotations

from typing import Any

from calculator import SalaryCalculator
from core.module import Module

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

    def _calculate(self, year: int, month: int) -> dict:
        return _breakdown_to_dict(self._make_calc().calculate(year, month))

    def _balance(self, year: int, month: int) -> dict:
        expenses = self.k.request("db", "get_expenses", month=month, year=year)
        result = self._make_calc().balance(year, month, expenses)
        return {
            "salary": _breakdown_to_dict(result.salary),
            "expenses_h1": result.expenses_h1,
            "expenses_h2": result.expenses_h2,
            "balance_h1": result.balance_h1,
            "balance_h2": result.balance_h2,
        }

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


def _breakdown_to_dict(s: Any) -> dict:
    return {
        "net_salary": s.net_salary,
        "advance": s.advance,
        "payout": s.payout,
        "vacation_half_1": s.vacation_half_1,
        "vacation_half_2": s.vacation_half_2,
        "total_accrued": s.total_accrued,
        "to_pay_half_1": s.to_pay_half_1,
        "to_pay_half_2": s.to_pay_half_2,
        "calculation_method": s.calculation_method,
        "working_days_half_1": s.working_days_half_1,
        "working_days_half_2": s.working_days_half_2,
        "working_days_total": s.working_days_total,
        "advance_cutoff_day": s.advance_cutoff_day,
        "payout_date_1": s.payout_date_1,
        "payout_date_2": s.payout_date_2,
        "payout_date_1_nominal": s.payout_date_1_nominal,
        "payout_date_2_nominal": s.payout_date_2_nominal,
    }
