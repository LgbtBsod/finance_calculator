"""Форматирование сумм, дат и русских числительных — общее для всех вью.

Порт frontend/src/lib/format.ts.
"""

from __future__ import annotations

MONTH_NAMES_RU: tuple[str, ...] = (
    "",
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

_MONTH_GENITIVE_RU: tuple[str, ...] = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

BIRTHDAY_PLACEHOLDER_YEAR = 2000


def format_currency(amount: float | int | None) -> str:
    """1234567.5 -> '1 234 568 ₽' (без копеек, неразрывный пробел как разделитель тысяч)."""
    value = round(amount or 0)
    sign = "-" if value < 0 else ""
    digits = f"{abs(value):,}".replace(",", " ")
    return f"{sign}{digits} ₽"


def format_date_ru(iso_date: str | None) -> str:
    """'YYYY-MM-DD' -> 'DD.MM.YYYY'."""
    if not iso_date:
        return ""
    parts = iso_date[:10].split("-")
    if len(parts) != 3:
        return iso_date
    y, m, d = parts
    return f"{d}.{m}.{y}"


def format_date_long_ru(iso_date: str | None) -> str:
    """'2026-08-10' -> '10 августа 2026'."""
    if not iso_date:
        return ""
    try:
        y, m, d = (int(x) for x in iso_date[:10].split("-"))
    except ValueError:
        return iso_date
    return f"{d} {_MONTH_GENITIVE_RU[m - 1]} {y}"


def build_birth_date_for_api(day: int, month: int) -> str:
    """(15, 3) -> '15.03.2000' — для сохранения (backend требует полную дату)."""
    return f"{day:02d}.{month:02d}.{BIRTHDAY_PLACEHOLDER_YEAR}"


def parse_birth_date(birth_date: str) -> tuple[int, int] | None:
    """'DD.MM.YYYY' -> (day, month); год отбрасывается."""
    try:
        parts = birth_date.split(".")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def format_birth_date_ru(birth_date: str) -> str:
    """'DD.MM.YYYY' -> '15 марта' (без года)."""
    parsed = parse_birth_date(birth_date)
    if not parsed:
        return birth_date
    day, month = parsed
    return f"{day} {_MONTH_GENITIVE_RU[month - 1]}"


def pluralize_ru(n: int, one: str, few: str, many: str) -> str:
    """1 расход / 2 расхода / 5 расходов."""
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return many
    if n % 10 == 1:
        return one
    if 2 <= n % 10 <= 4:
        return few
    return many


def month_year_short(month: int, year: int) -> str:
    return f"{_MONTH_GENITIVE_RU[month - 1][:3]} {year}"
