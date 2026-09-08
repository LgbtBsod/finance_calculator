"""Совместимость: ``database.py`` разбит на слоёный пакет ``db/``.

Импортируйте из ``db`` напрямую. Этот shim удаляется на стадии 4 рефакторинга.
"""

from db import Database, DatabaseManager

__all__ = ["Database", "DatabaseManager"]
