"""Kernel — маршрутизация запросов и событий между модулями.

Явный экземпляр (НЕ singleton): ``main.py`` строит один Kernel, регистрирует
модули, вызывает ``initialize()`` и передаёт ядро в ``run_app``. Тесты строят
свежий Kernel на каждый тест — настоящая изоляция.

Два канала:
  request(target, action, **payload) -> Any   — синхронный вызов, нужен ответ
  emit(event, **data) / subscribe(event, fn)  — fire-and-forget оповещение

Модуль получает не сам Kernel, а :class:`KernelView` — узкий фасад без
``get_module``. ``get_module`` есть только на Kernel и используется тестами.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from core._validate import first_bad
from core.errors import (
    KernelError,
    PayloadError,
    UnknownModuleError,
    UserFacingError,
)
from core.messages import Event, Message

if TYPE_CHECKING:
    from core.module import Module

logger = logging.getLogger(__name__)


class KernelView:
    """То, что видит модуль: request / emit / subscribe / log. И больше ничего.

    Каждый модуль получает свой KernelView со своим именем — ядро проставляет
    его как ``source`` в Message, а модуль не может достучаться до соседа
    иначе как через ``request(name, action, ...)``.
    """

    __slots__ = ("_kernel", "name")

    def __init__(self, kernel: Kernel, name: str) -> None:
        self._kernel = kernel
        self.name = name

    def request(self, target: str, action: str, /, **payload: Any) -> Any:
        return self._kernel._dispatch_request(self.name, target, action, payload)

    def emit(self, event: str, /, **data: Any) -> None:
        self._kernel._enqueue_event(self.name, event, data)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self._kernel._subscribe(event, handler)

    def has(self, name: str) -> bool:
        """Зарегистрирован ли модуль. Возвращает bool — не даёт ссылку."""
        return name in self._kernel._modules

    def log(self, msg: str, *args: Any) -> None:
        logger.info(f"[{self.name}] {msg}", *args)


class Kernel:
    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}
        self._order: list[str] = []
        self._subscribers: dict[str, list[Callable[..., None]]] = {}
        self._lock = threading.RLock()
        self._initialized = False
        self._frozen = False
        # Очередь событий + признак «внутри верхнеуровневого request».
        self._event_queue: list[Event] = []
        self._request_depth = 0
        self._dispatching_events = False

    # ── регистрация / жизненный цикл ──────────────────────────

    def register(self, name: str, module: Module) -> None:
        with self._lock:
            if self._frozen:
                raise KernelError(name, "register", "регистрация закрыта после initialize()")
            if name in self._modules:
                raise KernelError(name, "register", f"модуль '{name}' уже зарегистрирован")
            self._modules[name] = module
            self._order.append(name)
            module.set_kernel(KernelView(self, name))

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            # 1. Проверить, что зависимости каждого модуля зарегистрированы —
            #    громкое падение на boot, а не на первом balance().
            for name in self._order:
                for dep in getattr(self._modules[name], "requires", ()):  # noqa: B009
                    if dep not in self._modules:
                        raise KernelError(
                            name, "initialize",
                            f"модулю '{name}' нужен незарегистрированный модуль '{dep}'",
                        )
            # 2. initialize() в порядке регистрации.
            for name in self._order:
                mod = self._modules[name]
                if hasattr(mod, "initialize"):
                    logger.info("initialize %s", name)
                    mod.initialize()
            self._frozen = True
            self._initialized = True

    def shutdown(self) -> None:
        with self._lock:
            for name in reversed(self._order):
                mod = self._modules[name]
                if hasattr(mod, "shutdown"):
                    try:
                        mod.shutdown()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("shutdown %s: %s", name, exc)
            self._modules.clear()
            self._order.clear()
            self._subscribers.clear()
            self._initialized = False
            self._frozen = False

    # ── для тестов ────────────────────────────────────────────

    def get_module(self, name: str) -> Module:
        """Только для тестов. В прод-коде запрещено (см. tests/test_architecture.py)."""
        return self._modules[name]

    def __contains__(self, name: str) -> bool:
        return name in self._modules

    def view(self, name: str) -> KernelView:
        """KernelView для внешнего потребителя (GUI-фасад). Не модуль —
        поэтому имя произвольное, в маршрутизации участвует только как source."""
        return KernelView(self, name)

    # ── маршрутизация запросов ────────────────────────────────

    def _dispatch_request(
        self, source: str, target: str, action: str, payload: dict[str, Any]
    ) -> Any:
        bad = first_bad(payload)
        if bad is not None:
            raise PayloadError(target, action, f"payload['{bad}'] — не плоские данные")

        module = self._modules.get(target)
        if module is None:
            raise UnknownModuleError(target, sorted(self._modules))

        msg = Message(source=source, target=target, action=action, payload=payload)
        logger.debug("%s", msg)

        self._request_depth += 1
        try:
            try:
                result = module.handle(action, dict(payload))
            except (UserFacingError, KernelError):
                raise
            except TypeError as exc:
                # неверный набор kwargs хендлера
                raise PayloadError(target, action, str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                raise KernelError(target, action, f"{type(exc).__name__}: {exc}") from exc
        finally:
            self._request_depth -= 1

        # Верхнеуровневый request раскрутился — можно диспатчить накопленные события.
        if self._request_depth == 0:
            self._flush_events()
        return result

    # ── события ──────────────────────────────────────────────

    def _subscribe(self, event: str, handler: Callable[..., None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event, []).append(handler)

    def _enqueue_event(self, source: str, event: str, data: dict[str, Any]) -> None:
        bad = first_bad(data)
        if bad is not None:
            raise PayloadError(event, "emit", f"data['{bad}'] — не плоские данные")
        self._event_queue.append(Event(name=event, source=source, data=data))
        # emit вне request (например из initialize) — диспатчим сразу.
        if self._request_depth == 0 and not self._dispatching_events:
            self._flush_events()

    def _flush_events(self) -> None:
        if self._dispatching_events:
            return
        self._dispatching_events = True
        try:
            # Новые события, порождённые обработчиками, тоже уйдут в этом цикле.
            while self._event_queue:
                ev = self._event_queue.pop(0)
                for handler in list(self._subscribers.get(ev.name, ())):
                    try:
                        handler(**ev.data)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("подписчик %s упал: %s", ev.name, exc)
        finally:
            self._dispatching_events = False
