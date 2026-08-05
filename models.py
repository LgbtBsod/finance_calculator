"""models.py — Чистые immutable модели данных, Enum'ы, Protocol'ы, TypedDict'ы.

Нулевая бизнес-логика — только структура и контракты.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum, IntEnum
from typing import Protocol, TypedDict

__all__ = [
    # Enum'ы
    "DayKind",
    "ExpenseHalf",
    "CorrectionKind",
    # Frozen dataclass'ы
    "DayInfo",
    "SalaryBreakdown",
    "BalanceResult",
    "BirthdayAlert",
    "PDFParseResult",
    # Protocol'ы (контракты для DI)
    "SettingProvider",
    "CalendarReader",
    "ExpenseReader",
    "VacationReader",
    "BirthdayReader",
    # TypedDict'ы (структура строк БД)
    "ExpenseRow",
    "BirthdayRow",
    "MemoRow",
    "VacationRow",
    "CorrectionRow",
    "CalendarRow",
]


# ── Перечисления ──────────────────────────────────────────────


class DayKind(StrEnum):
    """Тип дня в производственном календаре."""

    WORKING = "working"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    SHORTENED = "shortened"  # рабочий, но на 1 ч короче


class ExpenseHalf(IntEnum):
    """Половина месяца для расхода."""

    FIRST = 1
    SECOND = 2


class CorrectionKind(StrEnum):
    """Тип поправки к календарю (из PDF или вручную)."""

    EXTRA_HOLIDAY = "extra_holiday"  # стало выходным (перенос)
    EXTRA_WORKING = "extra_working"  # стало рабочим (редко)
    SHORTENED = "shortened"  # предпраздничный


# ── Frozen dataclass'ы (immutable, slotted) ─────────────────


@dataclass(frozen=True, slots=True)
class DayInfo:
    date: date
    kind: DayKind


@dataclass(frozen=True, slots=True)
class SalaryBreakdown:
    net_salary: float
    advance: float
    payout: float
    vacation_half_1: float
    vacation_half_2: float
    total_accrued: float
    to_pay_half_1: float
    to_pay_half_2: float


@dataclass(frozen=True, slots=True)
class BalanceResult:
    salary: SalaryBreakdown
    expenses_h1: float
    expenses_h2: float
    balance_h1: float
    balance_h2: float


@dataclass(frozen=True, slots=True)
class BirthdayAlert:
    name: str
    birth_date: str  # "DD.MM"
    gift_amount: float
    trigger_date: date
    days_until: int


@dataclass(frozen=True, slots=True)
class PDFParseResult:
    year: int
    extra_holidays: frozenset[date]
    shortened_days: frozenset[date]
    monthly_working_days: dict[int, int]  # month -> count
    monthly_hours_40: dict[int, float]  # month -> hours
    transfers_raw: list[str]  # исходные строки переносов


# ── Protocol'ы (контракты для dependency injection) ────────────


class SettingProvider(Protocol):
    """Протокол поставщика настроек. Реализуется DatabaseManager."""

    def get_setting(self, key: str) -> str: ...
    def set_setting(self, key: str, value: str) -> None: ...


class CalendarReader(Protocol):
    """Протокол поставщика рабочих дней. Реализуется CalendarService."""

    def get_working_days(self, year: int, month: int) -> tuple[float, float, float]:
        """(total, half_1, half_2)."""
        ...


class ExpenseReader(Protocol):
    """Протокол читателя расходов. Реализуется DatabaseManager."""

    def get_expenses(
        self,
        month: int | None = ...,
        year: int | None = ...,
    ) -> list[ExpenseRow]: ...


class VacationReader(Protocol):
    """Протокол читателя отпускных. Реализуется DatabaseManager."""

    def get_vacations(
        self,
        month: int | None = ...,
        year: int | None = ...,
    ) -> list[VacationRow]: ...


class BirthdayReader(Protocol):
    """Протокол читателя дней рождений. Реализуется DatabaseManager."""

    def get_birthdays(self) -> list[BirthdayRow]: ...


# ── TypedDict'ы (структура строк из БД) ─────────────────────


class ExpenseRow(TypedDict):
    id: int
    name: str
    amount: float
    half: int
    month: int
    year: int
    is_recurring: bool


class BirthdayRow(TypedDict):
    id: int
    name: str
    birth_date: str
    gift_amount: float


class MemoRow(TypedDict):
    id: int
    name: str
    amount: float
    target_date: str


class VacationRow(TypedDict):
    id: int
    total_amount: float
    payout_date: str


class CorrectionRow(TypedDict):
    date: str
    kind: str
    source: str


class CalendarRow(TypedDict):
    date: str
    is_working: int
    is_holiday: int
    is_shortened: int
