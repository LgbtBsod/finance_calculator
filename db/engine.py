"""db.engine — ядро доступа к SQLite: жизненный цикл соединения, транзакция,
безопасная резервная копия, read-through кэш горячих чтений.

НЕ содержит entity-SQL и DDL (это schema.py / migrations.py / repositories/*).

Конкурентный доступ: оптимистическая блокировка (version/row-versioning для
конфликтов при одновременном редактировании) сознательно НЕ реализована —
приложение однопользовательское, побеждает последняя запись (last-write-wins).
Кэш живёт на Engine (НЕ на соединении: для файловой БД соединение
пересоздаётся на каждый _transaction, а кэш должен переживать). Два экземпляра
Engine на одном файле (тест backup, run.bat дважды) кэш не разделяют — для
однопользовательского инструмента с last-write-wins это приемлемо.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any


class Engine:
    def __init__(self, db_path: str = "budget.db") -> None:
        self.db_path = db_path
        self._conn_cache: sqlite3.Connection | None = None
        self._read_cache: dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        self._cache_gen = 0
        if db_path != ":memory:":
            # sqlite не создаёт отсутствующие директории — заводим сами,
            # чтобы БД в подпапке (db/budget.db) открывалась «из коробки».
            with suppress(OSError):
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # ── соединение ────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        if self._conn_cache is not None:
            return self._conn_cache
        is_memory = self.db_path == ":memory:"
        # check_same_thread=False только для :memory: (тестовая БД, к которой
        # обращаются из разных потоков) — для файловой БД в проде каждое
        # соединение живёт в рамках одного _transaction() и не шарится.
        c = sqlite3.connect(self.db_path, check_same_thread=not is_memory)
        c.row_factory = sqlite3.Row
        if not is_memory:
            c.execute("PRAGMA journal_mode=WAL")
            # Если два процесса (например, run.bat запущен дважды) держат
            # файл одновременно, короткое ожидание блокировки вместо
            # немедленного "database is locked" — на локальном приложении
            # почти всегда достаточно нескольких секунд, чтобы конкурентная
            # запись успела закончиться сама.
            c.execute("PRAGMA busy_timeout=8000")
        c.execute("PRAGMA foreign_keys=ON")
        if is_memory:
            self._conn_cache = c
        return c

    def close(self) -> None:
        """Закрыть соединение с базой данных и освободить ресурсы."""
        if self._conn_cache is not None:
            try:
                self._conn_cache.close()
            except Exception:
                pass
            finally:
                self._conn_cache = None

    @contextmanager
    def _transaction(
        self, *, invalidates: tuple[str, ...] = (),
    ) -> Generator[sqlite3.Connection, None, None]:
        c = self._conn()
        try:
            yield c
            c.commit()
        except Exception:
            with suppress(sqlite3.ProgrammingError):  # DB already closed (in-memory case)
                c.rollback()
            raise
        finally:
            if self.db_path != ":memory:":
                c.close()
        # Достижимо только при успешном commit (в except — raise). Чистим кэш
        # после фиксации и закрытия файлового соединения.
        if invalidates:
            self.invalidate(*invalidates)

    # ── read-through кэш горячих целотабличных чтений ─────────

    def read_cached(self, key: str, loader: Callable[[], Any]) -> Any:
        """Вернуть кэшированное «сырое» значение по ключу либо загрузить через
        ``loader()`` (сам открывает ``_transaction``). Вызывающий репозиторий
        делает КОПИЮ на выход — объект в кэше общий и не должен мутироваться.

        Если во время ``loader()`` прошла инвалидация (изменилось поколение),
        свежезагруженное значение НЕ кладём в кэш — вернём его этому вызову,
        следующий перечитает."""
        with self._cache_lock:
            if key in self._read_cache:
                return self._read_cache[key]
            gen = self._cache_gen
        value = loader()
        with self._cache_lock:
            if gen == self._cache_gen:
                self._read_cache.setdefault(key, value)
            return self._read_cache.get(key, value)

    def invalidate(self, *keys: str) -> None:
        with self._cache_lock:
            self._cache_gen += 1
            for k in keys:
                self._read_cache.pop(k, None)

    def invalidate_all(self) -> None:
        with self._cache_lock:
            self._cache_gen += 1
            self._read_cache.clear()

    # ── backup ───────────────────────────────────────────────

    def backup_to(self, target_path: str) -> None:
        """Безопасная копия БД через SQLite backup API — в отличие от
        обычного копирования файла, не заденет незакоммиченные страницы
        WAL и не конфликтует с другим процессом, который сейчас пишет
        в тот же файл.

        `with sqlite3.connect(...) as target` управляет только транзакцией
        (commit/rollback), а НЕ закрывает соединение сам — без явного
        target.close() файловый хендл остаётся открытым, и на Windows
        последующее удаление временного файла падает с PermissionError.

        Источник (`_conn()`) для файловой БД — тоже свежее соединение вне
        `_transaction()`, поэтому закрываем и его: иначе read-хендл на
        budget.db + WAL/SHM висит до сборки мусора и мешает свопу бинарника
        апдейтером на Windows.
        """
        target = sqlite3.connect(target_path)
        source = self._conn()
        try:
            source.backup(target)
            target.commit()  # на всякий случай — backup() коммитит сам, но явный commit() дешёв
        finally:
            target.close()
            if self.db_path != ":memory:":
                source.close()
