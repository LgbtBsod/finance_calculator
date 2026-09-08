"""Тесты ядра: маршрутизация, жизненный цикл, события, изоляция."""

from __future__ import annotations

import pytest

from core.errors import (
    KernelError,
    PayloadError,
    UnknownActionError,
    UnknownModuleError,
    UserFacingError,
)
from core.kernel import Kernel, KernelView
from core.module import Module


class Echo(Module):
    name = "echo"

    def initialize(self) -> None:
        self.inited = True
        self._actions = {
            "ping": lambda: "pong",
            "add": lambda a, b: a + b,
            "boom": self._boom,
            "user_err": self._user_err,
            "leak": lambda: self,  # вернёт себя — не плоские данные
            "call_peer": lambda: self.k.request("other", "hi"),
        }

    def _boom(self):
        raise RuntimeError("internal failure")

    def _user_err(self):
        raise UserFacingError("понятная пользователю ошибка")


class Other(Module):
    name = "other"

    def initialize(self) -> None:
        self._actions = {"hi": lambda: "hi from other"}


class NeedsOther(Module):
    name = "needy"
    requires = ("other",)

    def initialize(self) -> None:
        self._actions = {}


def _kernel(*modules) -> Kernel:
    k = Kernel()
    for m in modules:
        k.register(m.name, m)
    k.initialize()
    return k


class TestRouting:
    def test_request_and_args(self):
        k = _kernel(Echo(), Other())
        assert k.view("t").request("echo", "ping") == "pong"
        assert k.view("t").request("echo", "add", a=2, b=3) == 5

    def test_unknown_module(self):
        k = _kernel(Echo())
        with pytest.raises(UnknownModuleError):
            k.view("t").request("nope", "x")

    def test_unknown_action(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(UnknownActionError) as ei:
            k.view("t").request("echo", "nosuch")
        assert "ping" in str(ei.value)

    def test_internal_error_wrapped(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(KernelError) as ei:
            k.view("t").request("echo", "boom")
        assert isinstance(ei.value.__cause__, RuntimeError)

    def test_user_facing_error_passthrough(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(UserFacingError) as ei:
            k.view("t").request("echo", "user_err")
        assert "понятная" in str(ei.value)
        assert not isinstance(ei.value, KernelError)

    def test_bad_kwargs_is_payload_error(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(PayloadError):
            k.view("t").request("echo", "add", a=1)  # b пропущен

    def test_peer_call_through_kernel(self):
        k = _kernel(Echo(), Other())
        assert k.view("t").request("echo", "call_peer") == "hi from other"


class TestPayloadValidation:
    def test_callable_rejected(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(PayloadError):
            k.view("t").request("echo", "ping", fn=lambda: 1)

    def test_object_rejected(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(PayloadError):
            k.view("t").request("echo", "ping", obj=object())

    def test_flat_data_ok(self):
        from datetime import date

        class Sink(Module):
            name = "sink"

            def initialize(self):
                self._actions = {"take": lambda **kw: sorted(kw)}

        k = _kernel(Sink(), Other())
        got = k.view("t").request(
            "sink", "take", x=[1, "a", {"k": date(2025, 1, 1)}], y=None
        )
        assert got == ["x", "y"]


class TestLifecycle:
    def test_init_order_and_ran(self):
        e, o = Echo(), Other()
        k = _kernel(o, e)
        assert e.inited is True
        assert k._order == ["other", "echo"]

    def test_missing_dependency_fails_on_init(self):
        k = Kernel()
        k.register("needy", NeedsOther())
        with pytest.raises(KernelError):
            k.initialize()

    def test_register_frozen_after_init(self):
        k = _kernel(Echo(), Other())
        with pytest.raises(KernelError):
            k.register("late", Other())

    def test_shutdown_clears(self):
        k = _kernel(Echo(), Other())
        k.shutdown()
        assert k._order == []
        assert "echo" not in k


class TestEvents:
    def test_emit_after_request_unwinds(self):
        seen = []

        class Emitter(Module):
            name = "em"

            def initialize(self):
                self._depth_at_emit = None
                self._actions = {"go": self._go}

            def _go(self):
                self.k.emit("thing:changed", n=1)
                # подписчик ещё не должен был отработать
                return list(seen)

        class Listener(Module):
            name = "ls"

            def initialize(self):
                self.k.subscribe("thing:changed", lambda n: seen.append(n))
                self._actions = {}

        k = _kernel(Emitter(), Listener())
        during = k.view("t").request("em", "go")
        assert during == []          # событие не диспатчилось внутри request
        assert seen == [1]           # но диспатчилось сразу после

    def test_event_data_must_be_flat(self):
        class Bad(Module):
            name = "bad"

            def initialize(self):
                self._actions = {"go": lambda: self.k.emit("x", fn=lambda: 1)}

        k = _kernel(Bad(), Other())
        with pytest.raises(PayloadError):
            k.view("t").request("bad", "go")


class TestIsolation:
    def test_module_gets_kernelview_not_kernel(self):
        e = Echo()
        _kernel(e, Other())
        assert isinstance(e.k, KernelView)
        assert not hasattr(e.k, "get_module")
        assert not hasattr(e.k, "_modules")
        assert not hasattr(e.k, "_kernel")  # name-mangled, не достать по имени

    def test_kernelview_has_check_only(self):
        e = Echo()
        k = _kernel(e, Other())
        assert e.k.has("other") is True
        assert e.k.has("nope") is False
        # но не даёт сам объект
        assert k.get_module("other") is not None  # это можно только на Kernel

    def test_strict_rejects_live_object_return(self):
        class Leaky(Module):
            name = "leaky"

            def initialize(self):
                self._actions = {"leak": lambda: self}

        k = Kernel(strict=True)
        k.register("leaky", Leaky())
        k.register("other", Other())
        k.initialize()
        with pytest.raises(PayloadError):
            k.view("t").request("leaky", "leak")


class TestConcurrency:
    def test_concurrent_requests_and_isolated_event_flush(self):
        """Общий Kernel, много потоков: глубина запроса и очередь событий
        per-thread — инкременты не теряются, события не дропаются."""
        import threading

        received: list[int] = []
        lock = threading.Lock()

        class Worker(Module):
            name = "w"

            def initialize(self):
                self._actions = {"work": self._work, "noop": lambda: None}

            def _work(self, n):
                self.k.request("w", "noop")  # вложенный -> глубина этого потока 2
                self.k.emit("did:work", n=n)
                return n

        class Listener(Module):
            name = "ls"

            def initialize(self):
                self.k.subscribe("did:work", self._on)
                self._actions = {}

            def _on(self, n):
                with lock:
                    received.append(n)

        k = Kernel()
        k.register("w", Worker())
        k.register("ls", Listener())
        k.initialize()

        def run(i):
            for j in range(20):
                k.view(f"t{i}").request("w", "work", n=i * 100 + j)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(received) == sorted(i * 100 + j for i in range(8) for j in range(20))
        assert k._ctx.depth == 0  # глубина текущего потока вернулась к 0
