"""Kernel — маршрутизация запросов и событий между модулями.

Явный экземпляр (НЕ singleton): ``main.py`` строит один Kernel, регистрирует
модули, вызывает ``initialize()`` и передаёт ядро в ``run_app``. Тесты строят
свежий Kernel на каждый тест — настоящая изоляция.

Один Kernel и один FinanceService делятся между всеми браузер-сессиями Flet, а
каждая сессия обслуживается в своём потоке. Поэтому:
  - «глубина верхнеуровневого запроса», очередь отложенных событий и флаг
    диспетчеризации — per-thread (threading.local): «верхнеуровневый» — это
    свойство стека вызовов конкретного потока, общий счётчик был бы неверен;
  - реестр модулей/подписчиков защищён RLock;
  - каждый модуль сам потокобезопасен для своего состояния (см. CacheModule).

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


class _ThreadCtx(threading.local):
    """Контекст запроса, локальный для потока."""

    def __init__(self) -> None:
        self.depth: int = 0
        self.queue: list[Event] = []
        self.dispatching: bool = False


class KernelView:
    """То, что видит модуль: request / emit / subscribe / log. И больше ничего.

    Каждый модуль получает свой KernelView со своим именем — ядро проставляет
    его как ``source`` в Message, а модуль не может достучаться до соседа
    иначе как через ``request(name, action, ...)``. Ссылка на ядро — под
    name-mangled слотом ``__k`` (тест архитектуры также запрещает ``._kernel`` /
    ``get_module`` / ``._modules`` в прод-коде).
    """

    __slots__ = ("_KernelView__k", "name")

    def __init__(self, kernel: Kernel, name: str) -> None:
        self.__k = kernel
        self.name = name

    def request(self, target: str, action: str, /, **payload: Any) -> Any:
        return self.__k._dispatch_request(self.name, target, action, payload)

    def emit(self, event: str, /, **data: Any) -> None:
        self.__k._enqueue_event(self.name, event, data)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self.__k._subscribe(event, handler)

    def has(self, name: str) -> bool:
        """Зарегистрирован ли модуль. Возвращает bool — не даёт ссылку."""
        return self.__k._has(name)

    def log(self, msg: str, *args: Any) -> None:
        logger.info(f"[{self.name}] {msg}", *args)


class Kernel:
    def __init__(self, *, strict: bool = False) -> None:
        self._modules: dict[str, Module] = {}
        self._order: list[str] = []
        self._subscribers: dict[str, list[Callable[..., None]]] = {}
        self._lock = threading.RLock()
        self._initialized = False
        self._frozen = False
        self._ctx = _ThreadCtx()
        # strict=True (тесты): валидировать и возвращаемые значения хендлеров —
        # ловит модуль, случайно вернувший живой объект. В проде дорого (deep-walk
        # каждого результата), поэтому по умолчанию выключено.
        self._strict = strict

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
            for name in self._order:
                for dep in getattr(self._modules[name], "requires", ()):
                    if dep not in self._modules:
                        raise KernelError(
                            name, "initialize",
                            f"модулю '{name}' нужен незарегистрированный модуль '{dep}'",
                        )
            # Порядок init выводим из requires (зависимости раньше) —
            # не полагаемся на ручную корректность порядка регистрации.
            self._order = self._topo_order()
            for name in self._order:
                mod = self._modules[name]
                if hasattr(mod, "initialize"):
                    logger.info("initialize %s", name)
                    mod.initialize()
            self._frozen = True
            self._initialized = True

    def _topo_order(self) -> list[str]:
        """Топологическая сортировка по ``requires``. При равных приоритетах
        сохраняет порядок регистрации. Цикл → KernelError."""
        indeg = dict.fromkeys(self._order, 0)
        adj: dict[str, list[str]] = {n: [] for n in self._order}
        for n in self._order:
            for dep in getattr(self._modules[n], "requires", ()):
                adj[dep].append(n)
                indeg[n] += 1
        ready = [n for n in self._order if indeg[n] == 0]
        out: list[str] = []
        while ready:
            n = ready.pop(0)
            out.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
        if len(out) != len(self._order):
            cycle = [n for n in self._order if n not in out]
            raise KernelError(cycle[0], "initialize", f"цикл в requires: {cycle}")
        return out

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
        with self._lock:
            return name in self._modules

    def _has(self, name: str) -> bool:
        with self._lock:
            return name in self._modules

    def view(self, name: str) -> KernelView:
        """KernelView для внешнего потребителя (GUI-фасад). Не модуль —
        поэтому имя произвольное, в маршрутизации участвует только как source."""
        return KernelView(self, name)

    def module_names(self) -> list[str]:
        """Имена зарегистрированных модулей в порядке регистрации (для логов)."""
        with self._lock:
            return list(self._order)

    # ── маршрутизация запросов ────────────────────────────────

    def _dispatch_request(
        self, source: str, target: str, action: str, payload: dict[str, Any]
    ) -> Any:
        bad = first_bad(payload)
        if bad is not None:
            raise PayloadError(target, action, f"payload['{bad}'] — не плоские данные")

        with self._lock:
            module = self._modules.get(target)
        if module is None:
            raise UnknownModuleError(target, sorted(self._modules))

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "%s", Message(source=source, target=target, action=action, payload=payload)
            )

        ctx = self._ctx
        ctx.depth += 1
        try:
            try:
                result = module.handle(action, dict(payload))
            except (UserFacingError, KernelError):
                raise
            except TypeError as exc:
                raise PayloadError(target, action, str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                raise KernelError(target, action, f"{type(exc).__name__}: {exc}") from exc
        finally:
            ctx.depth -= 1

        if self._strict and (bad := first_bad({"result": result})) is not None:
            raise PayloadError(target, action, f"хендлер вернул не плоские данные ({bad})")

        # Верхнеуровневый request этого потока раскрутился — диспатчим его события.
        if ctx.depth == 0:
            self._flush_events(ctx)
        return result

    # ── события ──────────────────────────────────────────────

    def _subscribe(self, event: str, handler: Callable[..., None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event, []).append(handler)

    def _enqueue_event(self, source: str, event: str, data: dict[str, Any]) -> None:
        bad = first_bad(data)
        if bad is not None:
            raise PayloadError(event, "emit", f"data['{bad}'] — не плоские данные")
        ctx = self._ctx
        ctx.queue.append(Event(name=event, source=source, data=data))
        # emit вне request (например из initialize) — диспатчим сразу.
        if ctx.depth == 0 and not ctx.dispatching:
            self._flush_events(ctx)

    def _flush_events(self, ctx: _ThreadCtx) -> None:
        if ctx.dispatching:
            return
        ctx.dispatching = True
        try:
            while ctx.queue:
                ev = ctx.queue.pop(0)
                with self._lock:
                    handlers = list(self._subscribers.get(ev.name, ()))
                for handler in handlers:
                    try:
                        handler(**ev.data)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("подписчик %s упал: %s", ev.name, exc)
        finally:
            ctx.dispatching = False
