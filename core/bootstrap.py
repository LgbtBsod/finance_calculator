"""Сборка ядра со всеми модулями. Один источник порядка регистрации —
используется и main.py, и тестами.
"""

from __future__ import annotations

from core.kernel import Kernel

# Порядок важен: db открывает соединение/миграции; finance гаснет раньше db.
_ORDER = ("db", "cache", "calendar", "calculator", "birthdays", "finance", "updater")


def build_kernel(db_path: str, *, initialize: bool = True) -> Kernel:
    from modules.birthdays import BirthdaysModule
    from modules.cache import CacheModule
    from modules.calculator import CalculatorModule
    from modules.calendar import CalendarModule
    from modules.db import DBModule
    from modules.finance import FinanceModule
    from modules.updater import UpdaterModule

    factories = {
        "db": lambda: DBModule(db_path),
        "cache": CacheModule,
        "calendar": CalendarModule,
        "calculator": CalculatorModule,
        "birthdays": BirthdaysModule,
        "finance": FinanceModule,
        "updater": UpdaterModule,
    }

    kernel = Kernel()
    for name in _ORDER:
        kernel.register(name, factories[name]())
    if initialize:
        kernel.initialize()
    return kernel
