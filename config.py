"""config.py — доменные константы и ЕДИНЫЙ источник настроек.

Никаких путей (они в ``paths.py``) и никакой бизнес-логики — только данные:
праздники РФ, названия месяцев и декларативная спецификация настроек
(дефолт + имя в GUI + ключ в БД + тип), из которой выводятся все три пути
работы с настройками (seed / чтение / запись).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "RU_BASE_HOLIDAYS",
    "MONTH_NOMINATIVE",
    "MONTH_GENITIVE",
    "MONTH_NAMES_GENITIVE",
    "MONTH_NAMES_NOMINATIVE",
    "SettingSpec",
    "SETTINGS",
    "SETTINGS_BY_KEY",
]


# ── Базовые праздничные дни РФ (ст. 112 ТК РФ) ─────────────
RU_BASE_HOLIDAYS: frozenset[tuple[int, int]] = frozenset(
    [
        # Новогодние каникулы + Рождество
        (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
        (2, 23),   # День защитника Отечества
        (3, 8),    # Международный женский день
        (5, 1),    # Праздник Весны и Труда
        (5, 9),    # День Победы
        (6, 12),   # День России
        (11, 4),   # День народного единства
    ]
)


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


# ── Доменные настройки: единый источник ────────────────────
# Одна запись на настройку задаёт: имя в словаре GUI (camelCase), ключ строки
# в таблице ``settings`` (snake_case), дефолт и тип. Отсюда выводятся:
#   • database._seed_defaults      — первичное заполнение таблицы
#   • modules/finance _settings_get   — чтение (строка БД -> типизированное)
#   • modules/finance _settings_update — запись (значение GUI -> строка БД)
# Все булевы хранятся строками "true"/"false" — их так читают
# calculator.py / prod_calendar.py.
#
# Оклад (base_salary/kef/метод/пропорции) здесь НЕ живёт — это сущность
# «доход» с kind='salary' (несколько окладов = несколько работ). Здесь
# только «как устроена выплата»: налог, дни выплаты, отсечение, перенос.


@dataclass(frozen=True, slots=True)
class SettingSpec:
    camel: str                                # ключ в словаре настроек GUI
    key: str                                  # ключ строки в таблице settings
    default: float | int | bool | str
    kind: str                                 # "float" | "int" | "bool" | "str"

    def parse(self, raw: str | None) -> float | int | bool | str:
        """Строка из БД -> типизированное значение (или дефолт для пустого)."""
        if raw is None or raw == "":
            return self.default
        match self.kind:
            case "float":
                return float(raw)
            case "int":
                return int(float(raw))
            case "bool":
                return str(raw).strip().lower() == "true"
            case _:
                return raw

    def to_str(self, value: object) -> str:
        """Типизированное значение -> строка для хранения в БД."""
        if self.kind == "bool":
            return str(bool(value)).lower()
        return str(value)


SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("taxRate", "tax_rate", 13.0, "float"),
    # Прогрессивная шкала НДФЛ 2025 вместо плоской taxRate.
    SettingSpec("taxProgressive", "tax_progressive", False, "bool"),
    SettingSpec("standardHours", "standard_hours", 40, "int"),
    SettingSpec("advanceCutoffDay", "advance_cutoff_day", 15, "int"),
    SettingSpec("isAdvanceDateInclusive", "is_advance_date_inclusive", True, "bool"),
    SettingSpec("accountShortened", "account_shortened", False, "bool"),
    SettingSpec("payoutDay1", "payout_day1", 10, "int"),
    SettingSpec("payoutDay2", "payout_day2", 25, "int"),
    # ТК РФ ст. 136: выплату, попавшую на выходной, переносят на более ранний
    # рабочий день — это обязанность, а не опция, поэтому по умолчанию включено.
    SettingSpec("moveWeekendToFriday", "move_weekend_to_friday", True, "bool"),
)

SETTINGS_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in SETTINGS}
