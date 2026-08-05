"""database.py — SQLite: схемы, CRUD, миграции.

Единственный модуль, знающий о SQL. Все остальные работают через него.
Возвращаемые типы — TypedDict из models.py.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from config import get_settings
from models import (
    BirthdayRow,
    CalendarRow,
    CorrectionRow,
    ExpenseRow,
    MemoRow,
    VacationRow,
)

__all__ = ["DatabaseManager"]


class DatabaseManager:
    """Управляет всеми операциями с SQLite.

    Каждый метод возвращает TypedDict или list[TypedDict],
    а не сырой dict — потребители получают автодополнение полей.
    """

    def __init__(self, db_path: str = "budget.db") -> None:
        self.db_path = db_path
        self._conn_cache: sqlite3.Connection | None = None
        self._init_db()

    # ── соединение ────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        if self._conn_cache is not None:
            return self._conn_cache
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        if self.db_path == ":memory:":
            self._conn_cache = c
        return c

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection, None, None]:
        c = self._conn()
        try:
            yield c
            c.commit()
        except Exception:
            try:
                c.rollback()
            except sqlite3.ProgrammingError:
                pass  # DB already closed (in-memory case)
            raise
        finally:
            if self.db_path != ":memory:":
                c.close()

    # ── миграции ─────────────────────────────────────────────

    def _init_db(self) -> None:
        c = self._conn()
        try:
            c.executescript("""
                -- Настройки (ключ-значение)
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                -- Производственный календарь
                CREATE TABLE IF NOT EXISTS calendar_data (
                    date         TEXT PRIMARY KEY,
                    is_working   INTEGER NOT NULL DEFAULT 1,
                    is_holiday   INTEGER NOT NULL DEFAULT 0,
                    is_shortened INTEGER NOT NULL DEFAULT 0
                );

                -- Поправки к календарю (из PDF / вручную)
                CREATE TABLE IF NOT EXISTS calendar_corrections (
                    date      TEXT PRIMARY KEY,
                    kind      TEXT NOT NULL,
                    source    TEXT NOT NULL
                );

                -- Дни рождения
                CREATE TABLE IF NOT EXISTS birthdays (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    birth_date  TEXT    NOT NULL,
                    gift_amount REAL    NOT NULL DEFAULT 0.0
                );

                -- Расходы (влияют на баланс)
                CREATE TABLE IF NOT EXISTS expenses (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT    NOT NULL,
                    amount        REAL    NOT NULL DEFAULT 0.0,
                    half          INTEGER NOT NULL DEFAULT 1,
                    month         INTEGER NOT NULL,
                    year          INTEGER NOT NULL,
                    is_recurring  INTEGER NOT NULL DEFAULT 0
                );

                -- Памятка (НЕ влияет на баланс)
                CREATE TABLE IF NOT EXISTS memo_expenses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    amount      REAL    NOT NULL DEFAULT 0.0,
                    target_date TEXT
                );

                -- Отпускные
                CREATE TABLE IF NOT EXISTS vacations (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_amount REAL    NOT NULL DEFAULT 0.0,
                    payout_date  TEXT
                );
            """)
            c.commit()
            self._seed_defaults(c)
        finally:
            if self.db_path != ":memory:":
                c.close()

    def _seed_defaults(self, c: sqlite3.Connection) -> None:
        """Seed default settings from AppSettings (SSOT)."""
        settings = get_settings()
        defaults = {
            "base_salary": str(settings.base_salary),
            "tax_rate": str(settings.tax_rate),
            "kef": str(settings.kef),
            "standard_hours": str(settings.standard_hours),
            "advance_cutoff_day": str(settings.advance_cutoff_day),
            "is_advance_date_inclusive": str(settings.is_advance_date_inclusive).lower(),
            "account_shortened": str(settings.account_shortened).lower(),
        }
        for k, v in defaults.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v),
            )
        c.commit()

    # ═════════════════════════════════════════════════════════
    #  SETTINGS
    # ═════════════════════════════════════════════════════════

    def get_setting(self, key: str) -> str:
        with self._transaction() as c:
            r = c.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return r["value"] if r else ""

    def set_setting(self, key: str, value: str) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )

    def get_all_settings(self) -> dict[str, str]:
        with self._transaction() as c:
            return {
                r["key"]: r["value"]
                for r in c.execute(
                    "SELECT key, value FROM settings"
                ).fetchall()
            }

    # ═════════════════════════════════════════════════════════
    #  CALENDAR DATA (кэш)
    # ═════════════════════════════════════════════════════════

    def calendar_needs_fill(self, year: int) -> bool:
        with self._transaction() as c:
            n = c.execute(
                "SELECT COUNT(*) AS c FROM calendar_data WHERE date LIKE ?",
                (f"{year}-%",),
            ).fetchone()["c"]
            return n == 0

    def save_calendar_data(self, year: int, rows: list[tuple]) -> None:
        with self._transaction() as c:
            c.executemany(
                "INSERT OR REPLACE INTO calendar_data "
                "(date, is_working, is_holiday, is_shortened) VALUES (?, ?, ?, ?)",
                rows,
            )

    def clear_calendar_cache(self, year: int) -> None:
        with self._transaction() as c:
            c.execute(
                "DELETE FROM calendar_data WHERE date LIKE ?",
                (f"{year}-%",),
            )

    def get_calendar_month(
        self, year: int, month: int
    ) -> list[CalendarRow]:
        with self._transaction() as c:
            prefix = f"{year}-{month:02d}"
            rows = c.execute(
                "SELECT date, is_working, is_holiday, is_shortened "
                "FROM calendar_data WHERE date LIKE ? ORDER BY date",
                (f"{prefix}%",),
            ).fetchall()
            return [CalendarRow(**dict(r)) for r in rows]

    # ═════════════════════════════════════════════════════════
    #  CALENDAR CORRECTIONS
    # ═════════════════════════════════════════════════════════

    def get_corrections(self) -> list[CorrectionRow]:
        with self._transaction() as c:
            rows = c.execute(
                "SELECT date, kind, source FROM calendar_corrections "
                "ORDER BY date"
            ).fetchall()
            return [CorrectionRow(**dict(r)) for r in rows]

    def save_corrections(self, year: int, rows: list[tuple]) -> None:
        """rows = [(date_iso, kind, source), ...]"""
        with self._transaction() as c:
            c.execute(
                "DELETE FROM calendar_corrections WHERE date LIKE ?",
                (f"{year}-%",),
            )
            if rows:
                c.executemany(
                    "INSERT OR REPLACE INTO calendar_corrections "
                    "(date, kind, source) VALUES (?, ?, ?)",
                    rows,
                )

    def get_corrections_for_year(self, year: int) -> list[CorrectionRow]:
        with self._transaction() as c:
            rows = c.execute(
                "SELECT date, kind, source FROM calendar_corrections "
                "WHERE date LIKE ? ORDER BY date",
                (f"{year}-%",),
            ).fetchall()
            return [CorrectionRow(**dict(r)) for r in rows]

    # ═════════════════════════════════════════════════════════
    #  BIRTHDAYS
    # ═════════════════════════════════════════════════════════

    def add_birthday(
        self, name: str, birth_date: str, gift_amount: float
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO birthdays (name, birth_date, gift_amount) "
                "VALUES (?,?,?)",
                (name, birth_date, gift_amount),
            )

    def get_birthdays(self) -> list[BirthdayRow]:
        with self._transaction() as c:
            rows = c.execute(
                "SELECT id, name, birth_date, gift_amount "
                "FROM birthdays ORDER BY birth_date"
            ).fetchall()
            return [BirthdayRow(**dict(r)) for r in rows]

    def delete_birthday(self, bid: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM birthdays WHERE id=?", (bid,))

    def update_birthday(
        self,
        bid: int,
        name: str,
        birth_date: str,
        gift_amount: float,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "UPDATE birthdays SET name=?, birth_date=?, gift_amount=? "
                "WHERE id=?",
                (name, birth_date, gift_amount, bid),
            )

    # ═════════════════════════════════════════════════════════
    #  EXPENSES
    # ═════════════════════════════════════════════════════════

    def add_expense(
        self,
        name: str,
        amount: float,
        half: int,
        month: int,
        year: int,
        is_recurring: bool = False,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO expenses "
                "(name,amount,half,month,year,is_recurring) "
                "VALUES (?,?,?,?,?,?)",
                (name, amount, half, month, year, int(is_recurring)),
            )

    def get_expenses(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> list[ExpenseRow]:
        with self._transaction() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    "SELECT id, name, amount, half, month, year, is_recurring "
                    "FROM expenses WHERE month=? AND year=? ORDER BY half, id",
                    (month, year),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, name, amount, half, month, year, is_recurring "
                    "FROM expenses ORDER BY year, month, half, id"
                ).fetchall()
            return [_expense_from_row(r) for r in rows]

    def delete_expense(self, eid: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM expenses WHERE id=?", (eid,))

    def update_expense(
        self,
        eid: int,
        name: str,
        amount: float,
        half: int,
        is_recurring: bool,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "UPDATE expenses SET name=?, amount=?, half=?, is_recurring=? "
                "WHERE id=?",
                (name, amount, half, int(is_recurring), eid),
            )

    # ═════════════════════════════════════════════════════════
    #  MEMO EXPENSES (памятка)
    # ═════════════════════════════════════════════════════════

    def add_memo_expense(
        self, name: str, amount: float, target_date: str
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO memo_expenses (name, amount, target_date) "
                "VALUES (?,?,?)",
                (name, amount, target_date),
            )

    def get_memo_expenses(self) -> list[MemoRow]:
        with self._transaction() as c:
            rows = c.execute(
                "SELECT id, name, amount, target_date "
                "FROM memo_expenses ORDER BY target_date"
            ).fetchall()
            return [MemoRow(**dict(r)) for r in rows]

    def delete_memo_expense(self, mid: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM memo_expenses WHERE id=?", (mid,))

    # ═════════════════════════════════════════════════════════
    #  VACATIONS
    # ═════════════════════════════════════════════════════════

    def add_vacation(self, total_amount: float, payout_date: str) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO vacations (total_amount, payout_date) "
                "VALUES (?,?)",
                (total_amount, payout_date),
            )

    def get_vacations(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> list[VacationRow]:
        with self._transaction() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    "SELECT id, total_amount, payout_date FROM vacations "
                    "WHERE strftime('%m', payout_date)=? "
                    "AND strftime('%Y', payout_date)=? "
                    "ORDER BY payout_date",
                    (f"{month:02d}", str(year)),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, total_amount, payout_date FROM vacations "
                    "ORDER BY payout_date"
                ).fetchall()
            return [VacationRow(**dict(r)) for r in rows]

    def delete_vacation(self, vid: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM vacations WHERE id=?", (vid,))


# ── helper: правильно конвертировать sqlite3.Row -> ExpenseRow ──


def _expense_from_row(r: sqlite3.Row) -> ExpenseRow:
    """sqlite3.Row → ExpenseRow с корректным типом is_recurring (bool)."""
    d = dict(r)
    d["is_recurring"] = bool(d["is_recurring"])
    return ExpenseRow(**d)
