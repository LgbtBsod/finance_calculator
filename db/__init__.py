"""db — слоёный пакет доступа к SQLite (бывший ``database.py``).

Единственный слой, знающий SQL. Kernel-agnostic (импортирует только stdlib +
``config`` + ``models``), обёрнут модулем ``modules/db``.

Состав:
  - ``db.engine``       — ядро доступа: соединение, транзакция, backup, кэш
  - ``db.schema``       — DDL (CREATE TABLE/INDEX)
  - ``db.migrations``   — первичный bootstrap + аддитивные ALTER + seed
  - ``db.query``        — ``_UNSET``, ``RECURRING_WHERE``, ``period_overrides``, ``build_update``
  - ``db.rows``         — мапперы ``sqlite3.Row`` -> ``TypedDict``
  - ``db.repositories`` — CRUD по сущностям (по одному репозиторию на раздел)
  - ``db.facade``       — класс ``Database`` (публичная поверхность 1-в-1 со старым ``DatabaseManager``)

Каталог ``db/`` также хранит рантайм-файл ``db/budget.db`` (данные пользователя,
в .gitignore) — пакет и данные сосуществуют, различие явно в ``.gitignore``.
"""

from __future__ import annotations

from db.facade import Database, DatabaseManager

__all__ = ["Database", "DatabaseManager"]
