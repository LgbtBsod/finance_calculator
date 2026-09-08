"""models.py — Чистые immutable модели данных, Enum'ы, Protocol'ы, TypedDict'ы.

Нулевая бизнес-логика — только структура и контракты. Легаси-слой:
kernel-agnostic, обёрнут модулями (см. ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import IntEnum, StrEnum
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
    "CalendarReader",
    "VacationReader",
    # TypedDict'ы (структура строк БД)
    "ExpenseRow",
    "IncomeRow",
    "BirthdayRow",
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
    # Заполняются только методом "working_days" — прозрачность расчёта:
    # сколько рабочих дней легло в каждую половину месяца (после вычета
    # дней отпуска) и на основе какого дня отсечения. None для остальных
    # методов, где день расчёта не участвует в пропорции.
    calculation_method: str = "proportional"
    working_days_half_1: float | None = None
    working_days_half_2: float | None = None
    working_days_total: float | None = None
    advance_cutoff_day: int | None = None
    # Реальные даты выплат (ISO), с переносом на более ранний рабочий день
    # при move_weekend_to_friday — см. SalaryCalculator.payout_dates.
    payout_date_1: str | None = None
    payout_date_2: str | None = None
    # Номинальные даты (до переноса) — если отличаются от payout_date_*,
    # значит дата была сдвинута из-за выходного/праздника.
    payout_date_1_nominal: str | None = None
    payout_date_2_nominal: str | None = None


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
    extra_holidays: frozenset[date]
    shortened_days: frozenset[date]
    monthly_working_days: dict[int, int]
    monthly_hours_40: dict[int, float]
    transfers_raw: tuple[str, ...]


# ── Protocol'ы (контракты для dependency injection) ────────────
# SettingProvider/ExpenseReader/BirthdayReader существовали здесь, но не
# использовались ни в одной аннотации типа (DatabaseManager передаётся
# напрямую как конкретный класс везде, кроме двух мест ниже) — удалены,
# чтобы не поддерживать контракты без потребителей.


class CalendarReader(Protocol):
    """Протокол поставщика рабочих дней. Реализуется CalendarService."""

    def get_working_days(self, year: int, month: int) -> tuple[float, float, float]:
        """(total, half_1, half_2)."""
        ...

    def classify_day(self, d: date) -> DayKind:
        """Тип конкретного дня — нужен для вычитания дней отпуска из рабочих."""
        ...


class VacationReader(Protocol):
    """Протокол читателя отпускных. Реализуется DatabaseManager."""

    def get_vacations(
        self,
        month: int | None = ...,
        year: int | None = ...,
    ) -> list[VacationRow]: ...


# ── TypedDict'ы (структура строк из БД) ─────────────────────


class ExpenseRow(TypedDict):
    id: int
    name: str
    amount: float
    half: int
    month: int
    year: int
    is_recurring: bool
    group_id: str | None
    recurring_until: str | None
    # True для строки, спроецированной повторяющимся правилом на запрошенный
    # период (id/created — оригинала из другого месяца). Удаление такой строки
    # затронуло бы всю серию — GUI это блокирует; сумму можно переопределить
    # на конкретный месяц (overridden).
    projected: bool
    overridden: bool


class IncomeRow(TypedDict):
    id: int
    name: str
    amount: float
    half: int
    month: int
    year: int
    is_recurring: bool
    recurring_until: str | None
    projected: bool
    overridden: bool
    # kind='fixed' — разовая/повторяющаяся сумма (в баланс как «прочий доход»);
    # kind='salary' — оклad, считается SalaryCalculator (amount = оклад/мес).
    kind: str
    kef: float | None
    split_method: str | None
    first_half_ratio: float | None
    second_half_ratio: float | None


class BirthdayRow(TypedDict):
    id: int
    name: str
    birth_date: str
    gift_amount: float


class VacationRow(TypedDict):
    id: int
    total_amount: float
    payout_date: str
    start_date: str | None
    end_date: str | None


class CorrectionRow(TypedDict):
    date: str
    kind: str
    source: str


class CalendarRow(TypedDict):
    date: str
    is_working: int
    is_holiday: int
    is_shortened: int
