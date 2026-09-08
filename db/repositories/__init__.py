"""db.repositories — CRUD по сущностям, по одному репозиторию на раздел БД.

Каждый репозиторий берёт ``Engine`` и пишет ``with self._tx() as c: ...``
дословно как старый ``DatabaseManager``. Межрепозиторных зависимостей нет.
"""

from __future__ import annotations

from db.repositories.birthdays import BirthdayRepo
from db.repositories.calendar import CalendarRepo
from db.repositories.debts import DebtRepo
from db.repositories.expenses import ExpenseRepo
from db.repositories.groups import ExpenseGroupRepo
from db.repositories.income import IncomeRepo
from db.repositories.settings import SettingsRepo
from db.repositories.undo import UndoRepo
from db.repositories.vacations import VacationRepo

__all__ = [
    "SettingsRepo",
    "CalendarRepo",
    "BirthdayRepo",
    "ExpenseRepo",
    "IncomeRepo",
    "VacationRepo",
    "ExpenseGroupRepo",
    "DebtRepo",
    "UndoRepo",
]
