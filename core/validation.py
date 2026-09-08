"""Валидация пользовательского ввода. Бросает ValidationError (UserFacingError) —
ядро пробрасывает её нетронутой, GUI показывает текст в снекбаре.
"""

from __future__ import annotations

import re
from datetime import date

from core.errors import ValidationError

__all__ = ["validate_iso_date", "validate_birth_date"]

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_iso_date(value: str, field_name: str) -> None:
    # date.fromisoformat принимает и "20260131", и "2026-01-31T00:00" — но
    # SQLite сравнивает recurring_until как строку "ГГГГ-ММ-ДД" через
    # strftime, поэтому нестандартная форма молча ломает выборку. Требуем
    # ровно "ГГГГ-ММ-ДД".
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        raise ValidationError(
            f"{field_name}: неверный формат даты. Используйте ГГГГ-ММ-ДД"
        )
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"{field_name}: неверный формат даты. Используйте ГГГГ-ММ-ДД"
        ) from e


def validate_birth_date(value: str) -> None:
    """ДД.ММ.ГГГГ, реальная дата."""
    try:
        parts = str(value).strip().split(".")
        if len(parts) != 3:
            raise ValueError
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        date(year, month, day)
    except (ValueError, IndexError) as e:
        raise ValidationError("Неверный формат даты. Используйте ДД.ММ.ГГГГ") from e
