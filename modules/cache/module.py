"""CacheModule — in-memory кэш с TTL, потокобезопасный, без внешних зависимостей.

Ключи в неймспейсах через ':' — например ``balance:2025-07``,
``analytics:summary:2025-07``. При ``db:changed`` чистятся неймспейсы,
затронутые сущностью; ``calendar_data`` не трогается никогда (его инвалидирует
только ``calendar:changed``).
"""

from __future__ import annotations

import threading
import time
from typing import Any

from core.module import Module

_DEFAULT_TTL = 300.0

# entity из db:changed -> какие неймспейсы кэша чистить.
_ENTITY_NAMESPACES: dict[str, tuple[str, ...]] = {
    "expenses": ("balance", "analytics"),
    "expense_groups": ("analytics",),
    "vacations": ("balance",),
    "settings": ("balance", "analytics", "settings"),
    "corrections": (),  # календарь чистит отдельное событие calendar:changed
    "birthdays": (),
    "debts": (),
}


class CacheModule(Module):
    name = "cache"

    def __init__(self, default_ttl: float = _DEFAULT_TTL) -> None:
        super().__init__()
        self._ttl = default_ttl
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def initialize(self) -> None:
        self._actions = {
            "get": self._get,
            "set": self._set,
            "delete": self._delete,
            "clear": self._clear,
            "clear_namespace": self._clear_namespace,
            "stats": self._stats,
        }
        self.k.subscribe("db:changed", self._on_db_changed)
        self.k.subscribe("calendar:changed", self._on_calendar_changed)

    # ── actions ──────────────────────────────────────────────

    def _get(self, key: str) -> Any:
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                self._misses += 1
                return {"hit": False, "value": None}
            expires, value = hit
            if expires < time.monotonic():
                del self._data[key]
                self._misses += 1
                return {"hit": False, "value": None}
            self._hits += 1
            return {"hit": True, "value": value}

    def _set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + (ttl or self._ttl), value)

    def _delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def _clear(self) -> int:
        with self._lock:
            n = len(self._data)
            self._data.clear()
            return n

    def _clear_namespace(self, namespace: str) -> int:
        prefix = namespace if namespace.endswith(":") else namespace + ":"
        with self._lock:
            keys = [k for k in self._data if k == namespace or k.startswith(prefix)]
            for k in keys:
                del self._data[k]
            return len(keys)

    def _stats(self) -> dict:
        with self._lock:
            return {
                "entries": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
            }

    # ── подписки ─────────────────────────────────────────────

    def _on_db_changed(self, entity: str = "", **_: Any) -> None:
        for ns in _ENTITY_NAMESPACES.get(entity, ()):
            self._clear_namespace(ns)

    def _on_calendar_changed(self, **_: Any) -> None:
        self._clear_namespace("calendar")
        self._clear_namespace("balance")
        self._clear_namespace("analytics")
