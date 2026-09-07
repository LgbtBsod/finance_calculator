"""Message — единица общения между модулями через ядро."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

_counter = itertools.count(1)


@dataclass(frozen=True, slots=True)
class Message:
    """Запрос ``source -> target`` с действием и плоским payload.

    Создаётся ядром внутри ``request()`` — модули не конструируют Message сами.
    ``id`` монотонно растёт в пределах процесса (для трейсинга/логов); время —
    naive-строка ISO, часовой пояс приложению не важен.
    """

    source: str
    target: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: int = field(default_factory=lambda: next(_counter))
    ts: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def __str__(self) -> str:  # для логов
        return f"#{self.id} {self.source}->{self.target}:{self.action}"


@dataclass(frozen=True, slots=True)
class Event:
    """Fire-and-forget оповещение (``db:changed``, ``calendar:changed``, …).

    Диспатчится ядром ПОСЛЕ раскрутки верхнеуровневого request() — не под
    открытой транзакцией БД и без реентрантности.
    """

    name: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    id: int = field(default_factory=lambda: next(_counter))
