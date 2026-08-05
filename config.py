"""config.py — Константы, дефолты, маппинги.

Только статические данные, никакого состояния.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

__all__ = [
    "DB_FILENAME",
    "UPLOAD_DIR",
    "Defaults",
    "DEFAULTS",
    "RU_BASE_HOLIDAYS",
    "MONTH_NAMES_GENITIVE",
    "MONTH_NAMES_NOMINATIVE",
    "MONTH_DISPLAY",
    "WEEKDAY_NAMES",
]


# ── Пути ─────────────────────────────────────────────────────

DB_FILENAME = "budget.db"
UPLOAD_DIR = Path(os.environ.get("FINANCE_UPLOAD_DIR", ".upload"))


# ── Дефолтные настройки (fallback при пустой БД) ─────────────

@dataclass(frozen=True, slots=True)
class Defaults:
    base_salary: str = "100000"
    tax_rate: str = "13"
    advance_cutoff_day: str = "15"
    current_year: str = field(default_factory=lambda: str(date.today().year))
    kef: str = "1.0"
    account_shortened: str = "0"        # 0 = как обычные, 1 = учитывать
    standard_hours: str = "40"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


DEFAULTS = Defaults()


# ── Базовые праздничные дни РФ (ст. 112 ТК РФ) ─────────────

# Только то, что задано законом — не yearly-переносы.
RU_BASE_HOLIDAYS: list[tuple[int, int]] = [
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
]


# ── Русские названия для парсинга PDF ───────────────────────

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

MONTH_DISPLAY: list[str] = [
    "", "Январь", "Февраль", "Март", "Апрель",
    "Май", "Июнь", "Июль", "Август",
    "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

WEEKDAY_NAMES: dict[str, int] = {
    "понедельник": 0, "вторник": 1, "среда": 2,
    "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6,
}
