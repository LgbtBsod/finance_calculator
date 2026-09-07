"""Исключения ядра."""

from __future__ import annotations


class UserFacingError(ValueError):
    """Ошибка, чей текст можно показать пользователю (снекбар GUI).

    Ядро НЕ оборачивает такие исключения в KernelError — пробрасывает как есть,
    чтобы gui.views._base.View.guard() показал ``str(exc)`` без искажения.
    """


class ValidationError(UserFacingError):
    """Некорректный ввод пользователя."""


class KernelError(RuntimeError):
    """Ошибка при обработке запроса модулем — оборачивает исходное исключение
    (кроме UserFacingError), сохраняя traceback через ``raise ... from``."""

    def __init__(self, target: str, action: str, message: str = "") -> None:
        self.target = target
        self.action = action
        super().__init__(message or f"{target}.{action} завершился ошибкой")


class UnknownActionError(KernelError):
    """Модуль не знает такого action."""

    def __init__(self, target: str, action: str, valid: list[str]) -> None:
        self.valid = valid
        super().__init__(
            target, action,
            f"{target}: неизвестное действие '{action}'. Доступно: {', '.join(valid)}",
        )


class UnknownModuleError(KernelError):
    """Нет модуля с таким именем."""

    def __init__(self, target: str, registered: list[str]) -> None:
        super().__init__(
            target, "",
            f"модуль '{target}' не зарегистрирован. Зарегистрированы: {', '.join(registered)}",
        )


class PayloadError(KernelError):
    """В payload запроса или данных события — не плоские данные
    (callable, произвольный объект, ссылка на соседний модуль)."""
