"""Module — базовый класс для всех модулей.

Каждый модуль:
  - объявляет ``name`` и (опционально) ``requires`` — имена нужных соседей;
  - строит ``self._actions`` — таблицу {action -> метод};
  - получает ``self.k`` (KernelView) через ``set_kernel``;
  - соседей зовёт только ``self.k.request("<сосед>", "<action>", ...)``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from core.errors import UnknownActionError

if TYPE_CHECKING:
    from core.kernel import KernelView


class Module:
    name: str = ""
    requires: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.k: KernelView | None = None
        self._actions: dict[str, Callable[..., Any]] = {}

    # ── жизненный цикл (ядро) ─────────────────────────────────

    def set_kernel(self, view: KernelView) -> None:
        self.k = view

    def initialize(self) -> None:  # noqa: B027 - намеренно пустой хук
        """Вызывается ядром в порядке регистрации, после set_kernel у всех.
        Здесь безопасно строить обёртки и слать request соседям."""

    def shutdown(self) -> None:  # noqa: B027
        """Вызывается ядром в обратном порядке."""

    # ── диспетчеризация ──────────────────────────────────────

    def handle(self, action: str, payload: dict[str, Any]) -> Any:
        handler = self._actions.get(action)
        if handler is None:
            raise UnknownActionError(self.name, action, sorted(self._actions))
        return handler(**payload)

    # ── хелпер ───────────────────────────────────────────────

    def actions(self) -> list[str]:
        return sorted(self._actions)
