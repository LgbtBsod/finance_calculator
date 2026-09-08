"""db.repositories.base — общий предок репозиториев.

Намеренно тривиален: только ссылка на Engine и шорткат ``self._tx`` к
``engine._transaction``. Никакого SQL-сахара (``_one``/``_all``/``_exec``) —
тела методов пишут ``with self._tx() as c: ...`` дословно, чтобы SQL, порядок
операторов и атомарность совпадали со старым ``DatabaseManager`` байт-в-байт.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.engine import Engine


class _Repo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._tx = engine._transaction
