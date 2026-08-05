"""models.py — Чистые immutable модели данных, Enum'ы, Protocol'ы, TypedDict'ы.

Нулевая бизнес-логика — только структура и контракты.
Используем pydantic для валидации DTO (Data Transfer Objects).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum, IntEnum
from typing import Protocol, TypedDict, FrozenSet

from pydantic import BaseModel, Field, field_validator

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
    # Pydantic DTO для API
    "ExpenseDTO",
    "VacationDTO",
    "BirthdayDTO",
]


# ── Перечисления ──────────────────────────────────────────────

class DayKind(StrEnum):
    """Тип дня в производственном календаре."""
    WORKING = "working"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    SHORTENED = "shortened"


class ExpenseHalf(IntEnum):
    """Половина месяца для расхода."""
    FIRST = 1
    SECOND = 2


class CorrectionKind(StrEnum):
    """Тип поправки к календарю (из PDF или вручную)."""
    EXTRA_HOLIDAY = "extra_holiday"
    EXTRA_WORKING = "extra_working"
    SHORTENED = "shortened"


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
    birth_date: str
    gift_amount: float
    trigger_date: date
    days_until: int


@dataclass(frozen=True, slots=True)
class PDFParseResult:
    year: int
    extra_holidays: FrozenSet[date]
    shortened_days: FrozenSet[date]
    monthly_working_days: dict[int, int]
    monthly_hours_40: dict[int, float]
    transfers_raw: tuple[str, ...]


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


# ── Pydantic DTO для API валидации ────────────────────────────

class ExpenseDTO(BaseModel):
    """DTO для валидации расходов в API."""
    name: str = Field(..., min_length=1, max_length=200, description="Название расхода")
    amount: float = Field(..., gt=0, description="Сумма должна быть положительной")
    half: int = Field(..., ge=1, le=2, description="Половина месяца (1 или 2)")
    month: int = Field(..., ge=1, le=12, description="Месяц (1-12)")
    year: int = Field(..., ge=2020, le=2100, description="Год (2020-2100)")
    is_recurring: bool = Field(default=False, description="Повторяющийся расход")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()


class VacationDTO(BaseModel):
    """DTO для валидации отпускных в API."""
    total_amount: float = Field(..., gt=0, description="Сумма отпускных")
    payout_date: str = Field(..., description="Дата выплаты в формате YYYY-MM-DD")

    @field_validator('payout_date')
    @classmethod
    def validate_payout_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD")
        return v


class BirthdayDTO(BaseModel):
    """DTO для валидации дней рождений в API."""
    name: str = Field(..., min_length=1, max_length=200, description="Имя человека")
    birth_date: str = Field(..., description="Дата рождения в формате DD.MM.YYYY")
    gift_amount: float = Field(..., gt=0, le=1000000, description="Сумма на подарок")

    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v: str) -> str:
        try:
            parts = v.strip().split(".")
            if len(parts) != 3:
                raise ValueError
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            date(year, month, day)
        except (ValueError, IndexError):
            raise ValueError("Неверный формат даты. Используйте DD.MM.YYYY")
        return v
