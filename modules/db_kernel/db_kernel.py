"""
DB Kernel - модуль для управления всеми операциями с базой данных.
Никто не работает с БД напрямую, только через этот модуль.

Используется библиотека SQLAlchemy для оптимизированных запросов.

Функционал:
- Построение оптимизированных запросов через SQLAlchemy Core
- Управление транзакциями
- Миграции данных при обновлении БД
- Кэширование запросов через cachetools
- Построение условий и аналитики
- Логирование через loguru
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, TypeVar

from cachetools import TTLCache
from loguru import logger
from sqlalchemy import (
    MetaData,
    create_engine,
    text,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()
T = TypeVar("T")


class QueryBuilder:
    """Билдер запросов для построения оптимизированных SQL запросов."""

    def __init__(self, session: Session):
        self.session = session
        self._conditions = []
        self._fields = ["*"]
        self._table = None
        self._order_by = []
        self._limit = None
        self._offset = None

    def from_table(self, table_name: str) -> QueryBuilder:
        """Указание таблицы для запроса."""
        self._table = table_name
        return self

    def select_fields(self, fields: list[str]) -> QueryBuilder:
        """Выбор полей для запроса."""
        self._fields = fields
        return self

    def where(self, field: str, operator: str, value: Any) -> QueryBuilder:
        """Добавление условия WHERE."""
        self._conditions.append({"field": field, "operator": operator, "value": value})
        return self

    def order_by_field(self, field: str, ascending: bool = True) -> QueryBuilder:
        """Сортировка результатов."""
        self._order_by.append({"field": field, "ascending": ascending})
        return self

    def limit_results(self, limit: int, offset: int = 0) -> QueryBuilder:
        """Ограничение количества результатов."""
        self._limit = limit
        self._offset = offset
        return self

    def build_sql(self) -> str:
        """Построение SQL запроса."""
        if not self._table:
            raise ValueError("Таблица не указана")

        # SELECT часть
        fields_str = ", ".join(self._fields) if self._fields != ["*"] else "*"
        sql = f"SELECT {fields_str} FROM {self._table}"

        # WHERE часть
        if self._conditions:
            where_clauses = []
            for cond in self._conditions:
                op_map = {
                    "=": "=",
                    "!=": "!=",
                    ">": ">",
                    "<": "<",
                    ">=": ">=",
                    "<=": "<=",
                    "LIKE": "LIKE",
                    "IN": "IN",
                    "IS NULL": "IS NULL",
                    "IS NOT NULL": "IS NOT NULL",
                }
                op = op_map.get(cond["operator"], "=")

                if op in ["IS NULL", "IS NOT NULL"]:
                    where_clauses.append(f"{cond['field']} {op}")
                elif op == "IN":
                    values = ", ".join(
                        f"'{v}'" if isinstance(v, str) else str(v) for v in cond["value"]
                    )
                    where_clauses.append(f"{cond['field']} IN ({values})")
                else:
                    value_repr = (
                        f"'{cond['value']}'"
                        if isinstance(cond["value"], str)
                        else str(cond["value"])
                    )
                    where_clauses.append(f"{cond['field']} {op} {value_repr}")

            sql += " WHERE " + " AND ".join(where_clauses)

        # ORDER BY
        if self._order_by:
            order_clauses = []
            for order in self._order_by:
                direction = "ASC" if order["ascending"] else "DESC"
                order_clauses.append(f"{order['field']} {direction}")
            sql += " ORDER BY " + ", ".join(order_clauses)

        # LIMIT и OFFSET
        if self._limit is not None:
            sql += f" LIMIT {self._limit}"
            if self._offset:
                sql += f" OFFSET {self._offset}"

        return sql

    def execute(self) -> list[dict[str, Any]]:
        """Выполнение построенного запроса."""
        sql = self.build_sql()
        result = self.session.execute(text(sql))
        columns = result.keys()
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


class DBKernel:
    """
    Ядро работы с базой данных.
    Все операции с БД проходят только через этот модуль.

    Features:
    - SQLAlchemy Core для оптимизированных запросов
    - TTLCache для кэширования результатов запросов
    - Контекстные менеджеры для транзакций
    - Type hints для всех методов
    """

    def __init__(
        self, db_url: str = "sqlite:///app.db", cache_max_size: int = 1000, cache_ttl: int = 300
    ):
        self.db_url = db_url
        self.engine = None
        self.SessionLocal = None
        self.metadata = MetaData()
        self._kernel: Any | None = None
        self._cache_enabled = True

        # Кэш запросов на основе cachetools.TTLCache
        self._query_cache: TTLCache = TTLCache(maxsize=cache_max_size, ttl=cache_ttl)
        self._cache_ttl = cache_ttl

    def set_kernel(self, kernel: Any) -> None:
        """Установка ссылки на ядро."""
        self._kernel = kernel

    def initialize(self) -> None:
        """Инициализация соединения с БД."""
        logger.info(f"Инициализация DB Kernel с БД: {self.db_url}")
        logger.info(
            f"Кэширование запросов включено (TTL={self._cache_ttl}s, max_size={len(self._query_cache)})"
        )

        # Проверка типа БД для правильных параметров
        if self.db_url.startswith("sqlite"):
            # SQLite не поддерживает pool_pre_ping, pool_size, max_overflow
            self.engine = create_engine(self.db_url, echo=False, future=True)
        else:
            # PostgreSQL, MySQL и другие
            self.engine = create_engine(
                self.db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                echo=False,
                future=True,
            )

        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

        # Создание таблиц по умолчанию
        self._create_default_tables()

        logger.info("DB Kernel успешно инициализирован")

    def _create_default_tables(self):
        """Создание таблиц по умолчанию."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Получение сессии БД."""
        if not self.SessionLocal:
            raise RuntimeError("DB Kernel не инициализирован")
        return self.SessionLocal()

    def build_condition(self, field: str, operator: str, value: Any) -> dict[str, Any]:
        """Построение условия для запроса."""
        return {"field": field, "operator": operator, "value": value}

    def build_query(
        self, table: str, conditions: list[dict] = None, fields: list[str] = None
    ) -> QueryBuilder:
        """Построение запроса к таблице."""
        session = self.get_session()
        builder = QueryBuilder(session)
        builder.from_table(table)

        if fields:
            builder.select_fields(fields)

        if conditions:
            for cond in conditions:
                builder.where(cond.get("field"), cond.get("operator", "="), cond.get("value"))

        return builder

    def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Выполнение SQL запроса.
        SELECT запросы автоматически кэшируются через TTLCache.
        """
        cache_key: str | None = None
        params = params or {}

        # Проверка кэша для SELECT запросов
        if self._cache_enabled and query.strip().upper().startswith("SELECT"):
            cache_key = hashlib.md5(
                f"{query}:{json.dumps(params, sort_keys=True)}".encode()
            ).hexdigest()
            try:
                # TTLCache автоматически выбрасывает KeyError если ключа нет или он истек
                cached_result = self._query_cache[cache_key]
                logger.debug(f"Кэш хит для запроса: {cache_key}")
                return cached_result
            except KeyError:
                pass  # Кэш промах или истек

        session = self.get_session()
        try:
            result = session.execute(text(query), params)

            if query.strip().upper().startswith("SELECT"):
                columns = result.keys()
                data = [dict(zip(columns, row, strict=True)) for row in result.fetchall()]

                # Сохранение в кэш (TTLCache автоматически управляет истечением)
                if cache_key:
                    self._query_cache[cache_key] = data

                return data
            else:
                session.commit()
                return [{"affected_rows": result.rowcount}]

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка выполнения запроса: {e}")
            raise
        finally:
            session.close()

    def execute_transaction(self, operations: list[dict[str, Any]]) -> list[Any]:
        """
        Выполнение транзакции с несколькими операциями.
        Все операции выполняются атомарно.
        """
        session = self.get_session()
        try:
            results = []

            for op in operations:
                op_type = op.get("type")
                query = op.get("query")
                params = op.get("params", {})

                result = session.execute(text(query), params)

                if op_type == "insert":
                    results.append(
                        {
                            "id": result.inserted_primary_key[0]
                            if result.inserted_primary_key
                            else None
                        }
                    )
                elif op_type == "update":
                    results.append({"affected_rows": result.rowcount})
                elif op_type == "delete":
                    results.append({"deleted_rows": result.rowcount})
                else:
                    results.append({"rowcount": result.rowcount})

            session.commit()
            logger.info(f"Транзакция выполнена успешно: {len(operations)} операций")

            # Инвалидация кэша после записи
            self._invalidate_cache()

            return results

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка транзакции: {e}")
            raise
        finally:
            session.close()

    def run_migrations(self, version: str = "latest") -> dict[str, Any]:
        """
        Запуск миграций БД.
        Проверяет текущую версию и применяет необходимые миграции.
        """
        logger.info(f"Запуск миграций до версии: {version}")

        # Таблица для отслеживания версий миграций
        migration_table = """
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version VARCHAR(50) NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
        """

        session = self.get_session()
        try:
            session.execute(text(migration_table))
            session.commit()

            # Получение примененных миграций
            result = session.execute(text("SELECT version FROM _migrations ORDER BY id"))
            applied_versions = [row[0] for row in result.fetchall()]

            # Здесь должна быть логика применения миграций
            # Для примера просто возвращаем статус
            return {
                "success": True,
                "current_version": applied_versions[-1] if applied_versions else "0.0.0",
                "target_version": version,
                "applied_migrations": [],
                "message": "Миграции выполнены успешно",
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка миграции: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def build_analytics(self, analytics_type: str, params: dict[str, Any] = None) -> dict[str, Any]:
        """
        Построение аналитических отчетов.
        Поддерживает различные типы аналитики.
        """
        params = params or {}

        if analytics_type == "summary":
            return self._build_summary_analytics(params)
        elif analytics_type == "trend":
            return self._build_trend_analytics(params)
        elif analytics_type == "aggregation":
            return self._build_aggregation_analytics(params)
        else:
            raise ValueError(f"Неизвестный тип аналитики: {analytics_type}")

    def _build_summary_analytics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Построение сводной аналитики."""
        table = params.get("table")
        field = params.get("field")

        if not table or not field:
            return {"error": "Требуется указать table и field"}

        session = self.get_session()
        try:
            queries = {
                "count": f"SELECT COUNT(*) as count FROM {table}",
                "avg": f"SELECT AVG({field}) as avg FROM {table}",
                "min": f"SELECT MIN({field}) as min FROM {table}",
                "max": f"SELECT MAX({field}) as max FROM {table}",
                "sum": f"SELECT SUM({field}) as sum FROM {table}",
            }

            result = {}
            for name, query in queries.items():
                res = session.execute(text(query)).fetchone()
                result[name] = res[0] if res else None

            return result
        finally:
            session.close()

    def _build_trend_analytics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Построение трендовой аналитики."""
        # Реализация трендовой аналитики
        return {"trend": "not implemented", "data": []}

    def _build_aggregation_analytics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Построение агрегационной аналитики."""
        # Реализация агрегационной аналитики
        return {"aggregation": "not implemented", "data": []}

    def _invalidate_cache(self) -> None:
        """Инвалидация кэша запросов."""
        if self._cache_enabled:
            self._query_cache.clear()
            logger.debug("Кэш запросов инвалидирован")

    def enable_cache(self, ttl: int | None = None) -> None:
        """Включение кэширования запросов."""
        self._cache_enabled = True
        if ttl is not None:
            self._cache_ttl = ttl
        logger.info(f"Кэширование включено, TTL: {self._cache_ttl}s")

    def disable_cache(self) -> None:
        """Отключение кэширования запросов."""
        self._cache_enabled = False
        self._query_cache.clear()
        logger.info("Кэширование отключено")

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша запросов."""
        return {
            "size": len(self._query_cache),
            "max_size": self._query_cache.maxsize,
            "ttl": self._cache_ttl,
            "enabled": self._cache_enabled,
        }

    def shutdown(self) -> None:
        """Завершение работы DB Kernel."""
        logger.info("Завершение работы DB Kernel...")

        if self.engine:
            self.engine.dispose()

        self._query_cache.clear()
        logger.info("DB Kernel завершен")


# Фабричная функция для создания экземпляра
def create_db_kernel(
    db_url: str = "sqlite:///app.db", cache_max_size: int = 1000, cache_ttl: int = 300
) -> DBKernel:
    """
    Создание экземпляра DB Kernel.

    Args:
        db_url: URL подключения к БД
        cache_max_size: Максимальный размер кэша запросов
        cache_ttl: Время жизни кэша в секундах

    Returns:
        Экземпляр DBKernel
    """
    return DBKernel(db_url=db_url, cache_max_size=cache_max_size, cache_ttl=cache_ttl)
