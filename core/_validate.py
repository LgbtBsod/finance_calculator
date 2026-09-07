"""Проверка «плоских данных» для payload запросов и данных событий.

Смысл: если модуль не может передать через ядро callable или произвольный
объект — он физически не может протащить ссылку на соседний модуль или
замыкание над ним. Инвариант «модули не держат ссылок друг на друга»
держится механически, а не на дисциплине.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from decimal import Decimal

_SCALARS = (str, int, float, bool, type(None), date, datetime, Decimal)


def is_flat(value: object, _depth: int = 0) -> bool:
    if _depth > 20:
        return False
    if isinstance(value, _SCALARS):
        return True
    if isinstance(value, (list, tuple)):
        return all(is_flat(v, _depth + 1) for v in value)
    if isinstance(value, dict):
        return all(
            isinstance(k, str) and is_flat(v, _depth + 1) for k, v in value.items()
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # только замороженные dataclass'ы (иммутабельный контракт)
        if not type(value).__dataclass_params__.frozen:
            return False
        return all(
            is_flat(getattr(value, f.name), _depth + 1)
            for f in dataclasses.fields(value)
        )
    return False


def first_bad(payload: dict[str, object]) -> str | None:
    """Имя первого ключа с не-плоским значением, либо None."""
    for k, v in payload.items():
        if not is_flat(v):
            return k
    return None
