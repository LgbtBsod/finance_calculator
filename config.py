"""config.py — Централизованная конфигурация приложения (SSOT).

Единый источник истины для всех настроек и констант.
Используем pydantic-settings для типизированных настроек.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "RU_BASE_HOLIDAYS",
    "MONTH_NOMINATIVE",
    "MONTH_GENITIVE",
    "MONTH_NAMES_GENITIVE",
    "MONTH_NAMES_NOMINATIVE",
    "AppSettings",
    "get_settings",
]


# ── Базовые праздничные дни РФ (ст. 112 ТК РФ) ─────────────
# Immutable frozenset для безопасности
RU_BASE_HOLIDAYS: frozenset[tuple[int, int]] = frozenset(
    [
        # Новогодние каникулы + Рождество
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 5),
        (1, 6),
        (1, 7),
        (1, 8),
        # День защитника Отечества
        (2, 23),
        # Международный женский день
        (3, 8),
        # Праздник Весны и Труда
        (5, 1),
        # День Победы
        (5, 9),
        # День России
        (6, 12),
        # День народного единства
        (11, 4),
    ]
)


# ── Pydantic Settings для типизированных настроек приложения ─────
class AppSettings(BaseSettings):
    """Дефолты доменных настроек (оклад, метод расчёта, дни выплат…).

    Единственный потребитель — ``database._seed_defaults`` (первичное
    заполнение таблицы ``settings``). Переопределяются переменными
    окружения ``FINANCE_*`` / ``.env``. Пути приложения живут в ``paths.py``,
    не здесь.
    """

    model_config = SettingsConfigDict(
        env_prefix="FINANCE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Salary calculation defaults
    base_salary: float = 100000.0
    tax_rate: float = 13.0
    kef: float = 1.0
    standard_hours: int = 40

    # Advance payment settings
    advance_cutoff_day: int = 15
    is_advance_date_inclusive: bool = True

    # Salary calculation method: "proportional" (40/60), "custom_proportions" (user-defined), or "working_days"
    salary_calculation_method: str = "proportional"

    # Custom proportions for salary split (first_half_ratio, second_half_ratio)
    # Only used when salary_calculation_method == "custom_proportions"
    first_half_ratio: float = 0.4
    second_half_ratio: float = 0.6

    # Account settings
    account_shortened: bool = False

    # Payout settings
    payout_day1: int = 10
    payout_day2: int = 25
    # ТК РФ ст. 136: если день выплаты зарплаты приходится на выходной или
    # праздничный день, зарплата должна быть выплачена накануне этого дня —
    # это обязательное правило, а не опция, поэтому по умолчанию включено.
    move_weekend_to_friday: bool = True


def get_settings() -> AppSettings:
    """Factory для получения настроек (SSOT)."""
    return AppSettings()


# ── Русские названия месяцев (SSOT) ─────────────────────────
# 1-индексированные кортежи (индекс 0 = "") — единственный источник.
# Словари «слово → номер» для парсинга PDF выводятся из них же.
MONTH_NOMINATIVE: tuple[str, ...] = (
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

MONTH_GENITIVE: tuple[str, ...] = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

MONTH_NAMES_NOMINATIVE: dict[str, int] = {
    name.lower(): i for i, name in enumerate(MONTH_NOMINATIVE) if name
}
MONTH_NAMES_GENITIVE: dict[str, int] = {
    name: i for i, name in enumerate(MONTH_GENITIVE) if name
}
