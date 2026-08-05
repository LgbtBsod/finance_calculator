"""config.py — Централизованная конфигурация приложения.

SSOT: Единый источник истины для всех настроек и констант.
Используем pydantic-settings для типизированных настроек.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import FrozenSet, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "DB_FILENAME",
    "UPLOAD_DIR",
    "RU_BASE_HOLIDAYS",
    "MONTH_NAMES_GENITIVE",
    "MONTH_NAMES_NOMINATIVE",
    "MONTH_DISPLAY",
    "WEEKDAY_NAMES",
    "AppSettings",
    "get_settings",
]


# ── Пути (SSOT) ──────────────────────────────────────────────
DB_FILENAME = os.environ.get("FINANCE_DB_PATH", "budget.db")
UPLOAD_DIR = Path(os.environ.get("FINANCE_UPLOAD_DIR", ".upload"))


# ── Pydantic Settings для типизированных настроек приложения ─────
class AppSettings(BaseSettings):
    """Типизированные настройки приложения (SSOT).
    
    Все дефолтные значения определены ТОЛЬКО здесь.
    Поддержка переменных окружения с префиксом FINANCE_.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="FINANCE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # Database & Storage
    db_path: str = DB_FILENAME
    upload_dir: Path = UPLOAD_DIR
    
    # Salary calculation defaults
    base_salary: float = 100000.0
    tax_rate: float = 13.0
    kef: float = 1.0
    standard_hours: int = 40
    
    # Advance payment settings
    advance_cutoff_day: int = 15
    is_advance_date_inclusive: bool = True
    
    # Account settings
    account_shortened: bool = False
    
    @property
    def net_salary(self) -> float:
        """Расчёт чистой зарплаты после налога."""
        return self.base_salary * self.kef * (1.0 - self.tax_rate / 100.0)


def get_settings() -> AppSettings:
    """Factory для получения настроек (SSOT)."""
    return AppSettings()


# ── Базовые праздничные дни РФ (ст. 112 ТК РФ) ─────────────
# Immutable frozenset для безопасности
RU_BASE_HOLIDAYS: FrozenSet[Tuple[int, int]] = frozenset([
    # Новогодние каникулы + Рождество
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
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
])


# ── Русские названия для парсинга PDF ───────────────────────
# Immutable mappings
MONTH_NAMES_GENITIVE: dict[str, int] = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

MONTH_NAMES_NOMINATIVE: dict[str, int] = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}

MONTH_DISPLAY: tuple[str, ...] = (
    "", "Январь", "Февраль", "Март", "Апрель",
    "Май", "Июнь", "Июль", "Август",
    "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

WEEKDAY_NAMES: dict[str, int] = {
    "понедельник": 0, "вторник": 1, "среда": 2,
    "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6,
}
