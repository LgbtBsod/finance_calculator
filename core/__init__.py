"""core — ядро модульной архитектуры.

Модули общаются ТОЛЬКО через ядро (Kernel), никогда напрямую: не импортируют
пакеты друг друга, не держат ссылок друг на друга. Гарантируется:
  - статически: tests/test_architecture.py (AST-проверка импортов)
  - в рантайме: модуль получает узкий KernelView (request/emit/subscribe/log,
    без get_module), а ядро валидирует, что в payload и событиях — только
    плоские данные (callable/объекты не пройдут).
"""

from core.errors import (
    KernelError,
    PayloadError,
    UnknownActionError,
    UserFacingError,
    ValidationError,
)
from core.kernel import Kernel, KernelView
from core.messages import Message
from core.module import Module

__all__ = [
    "Kernel",
    "KernelView",
    "Message",
    "Module",
    "KernelError",
    "UnknownActionError",
    "PayloadError",
    "UserFacingError",
    "ValidationError",
]
