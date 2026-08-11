"""database.py — SQLite: схемы, CRUD, миграции.

Единственный модуль, знающий о SQL. Все остальные работают через него.
Возвращаемые типы — TypedDict из models.py.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager, suppress

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

# Сентинел для трёхзначных PATCH-полей: отличает "аргумент не передан"
# (оставить как есть) от "передан явный None" (очистить значение в БД).
_UNSET = object()


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
        is_memory = self.db_path == ":memory:"
        # check_same_thread=False только для :memory: (используется в тестах,
        # где FastAPI TestClient диспетчеризует запросы в отдельный поток) —
        # для файловой БД в проде поведение не меняется.
        c = sqlite3.connect(self.db_path, check_same_thread=not is_memory)
        c.row_factory = sqlite3.Row
        if not is_memory:
            c.execute("PRAGMA journal_mode=WAL")
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
    def _transaction(self) -> Generator[sqlite3.Connection, None, None]:
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

    # ── миграции ─────────────────────────────────────────────

    def _init_db(self) -> None:
        c = self._conn()
        try:
            c.executescript("""
                -- Группы расходов (для категоризации)
                CREATE TABLE IF NOT EXISTS expense_groups (
                    id          TEXT    PRIMARY KEY,
                    name        TEXT    NOT NULL,
                    color       TEXT    NOT NULL,
                    parent_id   TEXT,
                    sort_order  INTEGER NOT NULL DEFAULT 0
                );

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
                    is_recurring  INTEGER NOT NULL DEFAULT 0,
                    is_inclusive  INTEGER NOT NULL DEFAULT 0,
                    group_id      TEXT,
                    FOREIGN KEY (group_id) REFERENCES expense_groups(id)
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
                    payout_date  TEXT,
                    start_date   TEXT,
                    end_date     TEXT
                );

                -- Долги
                CREATE TABLE IF NOT EXISTS debts (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    title        TEXT    NOT NULL,
                    total_amount REAL    NOT NULL DEFAULT 0.0,
                    month        INTEGER NOT NULL,
                    year         INTEGER NOT NULL,
                    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
                );

                -- Погашения долгов
                CREATE TABLE IF NOT EXISTS debt_repayments (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    debt_id   INTEGER NOT NULL,
                    amount    REAL    NOT NULL DEFAULT 0.0,
                    date      TEXT    NOT NULL,
                    note      TEXT,
                    FOREIGN KEY (debt_id) REFERENCES debts(id) ON DELETE CASCADE
                );
            """)
            c.commit()
            self._migrate_schema(c)
            self._seed_defaults(c)
        finally:
            if self.db_path != ":memory:":
                c.close()

    def _migrate_schema(self, c: sqlite3.Connection) -> None:
        """Аддитивные миграции для баз, созданных до появления новых колонок.

        `CREATE TABLE IF NOT EXISTS` не добавляет колонки к уже существующей
        таблице, поэтому недостающие столбцы добавляем явно (идемпотентно).
        """
        vacation_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(vacations)").fetchall()
        }
        for column in ("start_date", "end_date"):
            if column not in vacation_cols:
                c.execute(f"ALTER TABLE vacations ADD COLUMN {column} TEXT")

        expense_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(expenses)").fetchall()
        }
        if "recurring_until" not in expense_cols:
            c.execute("ALTER TABLE expenses ADD COLUMN recurring_until TEXT")

        c.commit()

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
            "payout_day1": str(getattr(settings, 'payout_day1', 10)),
            "payout_day2": str(getattr(settings, 'payout_day2', 25)),
            "move_weekend_to_friday": str(getattr(settings, 'move_weekend_to_friday', False)).lower(),
            "salary_calculation_method": getattr(settings, 'salary_calculation_method', 'proportional'),
            "first_half_ratio": str(getattr(settings, 'first_half_ratio', 0.4)),
            "second_half_ratio": str(getattr(settings, 'second_half_ratio', 0.6)),
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
        is_inclusive: bool = False,
        group_id: str | None = None,
        recurring_until: str | None = None,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO expenses "
                "(name,amount,half,month,year,is_recurring,is_inclusive,group_id,recurring_until) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    name, amount, half, month, year,
                    int(is_recurring), int(is_inclusive), group_id, recurring_until,
                ),
            )

    def get_expenses(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> list[ExpenseRow]:
        """Расходы за период.

        Без month/year — сырые строки как они есть в БД (используется
        режимом "за все периоды" в UI).

        С month/year — точное совпадение периода ПЛЮС спроецированные
        повторяющиеся расходы, чей период создания раньше запрошенного:
        повторяющийся расход не переносится в БД копией на каждый месяц,
        а автоматически "продолжается" вперёд, пока не наступит месяц
        recurring_until (включительно) — после него проекция прекращается.
        У спроецированных строк month/year в ответе подменяются на
        запрошенный период (см. _expense_from_row) — иначе карточка расхода
        показывала бы месяц своего создания, а не месяц, на который она
        сейчас распространяется.
        """
        with self._transaction() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    """
                    SELECT id, name, amount, half, month, year,
                           is_recurring, is_inclusive, group_id, recurring_until
                    FROM expenses
                    WHERE (month = :month AND year = :year)
                       OR (
                            is_recurring = 1
                            AND (year < :year OR (year = :year AND month < :month))
                            AND (
                                recurring_until IS NULL
                                OR CAST(strftime('%Y', recurring_until) AS INTEGER) > :year
                                OR (
                                    CAST(strftime('%Y', recurring_until) AS INTEGER) = :year
                                    AND CAST(strftime('%m', recurring_until) AS INTEGER) >= :month
                                )
                            )
                          )
                    ORDER BY half, id
                    """,
                    {"month": month, "year": year},
                ).fetchall()
                return [_expense_from_row(r, view_month=month, view_year=year) for r in rows]

            rows = c.execute(
                "SELECT id, name, amount, half, month, year, "
                "is_recurring, is_inclusive, group_id, recurring_until "
                "FROM expenses ORDER BY year, month, half, id"
            ).fetchall()
            return [_expense_from_row(r) for r in rows]

    def delete_expense(self, eid: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM expenses WHERE id=?", (eid,))

    def update_expense(
        self,
        eid: int,
        name: str | None = None,
        amount: float | None = None,
        half: int | None = None,
        is_recurring: bool | None = None,
        group_id: str | None = None,
        recurring_until: str | None | object = _UNSET,
    ) -> None:
        """Обновить расход с частичным обновлением полей (PATCH semantics).

        recurring_until — трёхзначное поле: значение по умолчанию `_UNSET`
        означает "не менять", а явно переданный `None` — "снять дату
        завершения повторения" (отличить "не передали" от "передали пустое"
        обычным None-дефолтом здесь нельзя, т.к. очистка даты — тоже None).
        """
        with self._transaction() as c:
            # Получаем текущие значения
            current = c.execute(
                "SELECT name, amount, half, is_recurring, group_id, recurring_until "
                "FROM expenses WHERE id=?",
                (eid,)
            ).fetchone()

            if not current:
                raise ValueError(f"Expense with id {eid} not found")

            # Используем новые значения или оставляем старые
            new_name = name if name is not None else current["name"]
            new_amount = amount if amount is not None else current["amount"]
            new_half = half if half is not None else current["half"]
            new_is_recurring = is_recurring if is_recurring is not None else bool(current["is_recurring"])
            new_group_id = group_id if group_id is not None else current["group_id"]
            new_recurring_until = (
                current["recurring_until"] if recurring_until is _UNSET else recurring_until
            )

            c.execute(
                "UPDATE expenses SET name=?, amount=?, half=?, is_recurring=?, "
                "group_id=?, recurring_until=? WHERE id=?",
                (
                    new_name, new_amount, new_half, int(new_is_recurring),
                    new_group_id, new_recurring_until, eid,
                ),
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

    def add_vacation(
        self,
        total_amount: float,
        payout_date: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO vacations (total_amount, payout_date, start_date, end_date) "
                "VALUES (?,?,?,?)",
                (total_amount, payout_date, start_date or payout_date, end_date or payout_date),
            )

    def get_vacations(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> list[VacationRow]:
        with self._transaction() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    "SELECT id, total_amount, payout_date, start_date, end_date FROM vacations "
                    "WHERE strftime('%m', payout_date)=? "
                    "AND strftime('%Y', payout_date)=? "
                    "ORDER BY payout_date",
                    (f"{month:02d}", str(year)),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, total_amount, payout_date, start_date, end_date FROM vacations "
                    "ORDER BY payout_date"
                ).fetchall()
            return [VacationRow(**dict(r)) for r in rows]

    def delete_vacation(self, vid: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM vacations WHERE id=?", (vid,))

    # ═════════════════════════════════════════════════════════
    #  EXPENSE GROUPS
    # ═════════════════════════════════════════════════════════

    def create_expense_group(
        self,
        group_id: str,
        name: str,
        color: str,
        parent_id: str | None = None,
        sort_order: int = 0,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO expense_groups (id, name, color, parent_id, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (group_id, name, color, parent_id, sort_order),
            )

    def get_expense_groups(self) -> list[dict]:
        with self._transaction() as c:
            rows = c.execute(
                "SELECT id, name, color, parent_id, sort_order "
                "FROM expense_groups ORDER BY sort_order, name"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_expense_group(self, group_id: str) -> dict | None:
        with self._transaction() as c:
            row = c.execute(
                "SELECT id, name, color, parent_id, sort_order "
                "FROM expense_groups WHERE id=?",
                (group_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_expense_group(
        self,
        group_id: str,
        name: str | None = None,
        color: str | None = None,
        parent_id: str | None = None,
        sort_order: int | None = None,
    ) -> None:
        with self._transaction() as c:
            updates = []
            values = []
            if name is not None:
                updates.append("name=?")
                values.append(name)
            if color is not None:
                updates.append("color=?")
                values.append(color)
            if parent_id is not None:
                updates.append("parent_id=?")
                values.append(parent_id)
            if sort_order is not None:
                updates.append("sort_order=?")
                values.append(sort_order)
            if updates:
                values.append(group_id)
                c.execute(
                    f"UPDATE expense_groups SET {', '.join(updates)} WHERE id=?",
                    values,
                )

    def delete_expense_group(self, group_id: str) -> None:
        """Удаляет группу; расходы этой группы не удаляются — становятся
        "без группы" (group_id=NULL), иначе удаление упало бы с
        FOREIGN KEY constraint failed при наличии ссылающихся расходов."""
        with self._transaction() as c:
            c.execute(
                "UPDATE expenses SET group_id=NULL WHERE group_id=?", (group_id,)
            )
            c.execute("DELETE FROM expense_groups WHERE id=?", (group_id,))

    # ═════════════════════════════════════════════════════════
    #  DEBTS
    # ═════════════════════════════════════════════════════════

    def create_debt(
        self,
        title: str,
        total_amount: float,
        month: int,
        year: int,
    ) -> int:
        with self._transaction() as c:
            cursor = c.execute(
                "INSERT INTO debts (title, total_amount, month, year, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (title, total_amount, month, year),
            )
            return cursor.lastrowid

    def get_debts(self) -> list[dict]:
        with self._transaction() as c:
            rows = c.execute(
                "SELECT d.id, d.title, d.total_amount, d.month, d.year, d.created_at, "
                "(SELECT COALESCE(SUM(r.amount), 0) FROM debt_repayments r WHERE r.debt_id = d.id) as repaid_amount "
                "FROM debts d ORDER BY d.year, d.month, d.created_at"
            ).fetchall()
            debts = []
            for row in rows:
                debt = dict(row)
                # Get repayments for this debt
                repayments = c.execute(
                    "SELECT id, debt_id, amount, date, note FROM debt_repayments WHERE debt_id=? ORDER BY date",
                    (debt['id'],)
                ).fetchall()
                debt['repayments'] = [dict(r) for r in repayments]
                debts.append(debt)
            return debts

    def delete_debt(self, debt_id: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM debts WHERE id=?", (debt_id,))

    def add_debt_repayment(
        self,
        debt_id: int,
        amount: float,
        date: str,
        note: str | None = None,
    ) -> None:
        with self._transaction() as c:
            c.execute(
                "INSERT INTO debt_repayments (debt_id, amount, date, note) "
                "VALUES (?, ?, ?, ?)",
                (debt_id, amount, date, note),
            )

    def delete_debt_repayment(self, repayment_id: int) -> None:
        with self._transaction() as c:
            c.execute("DELETE FROM debt_repayments WHERE id=?", (repayment_id,))


# ── helper: правильно конвертировать sqlite3.Row -> ExpenseRow ──


def _expense_from_row(
    r: sqlite3.Row, *, view_month: int | None = None, view_year: int | None = None
) -> ExpenseRow:
    """sqlite3.Row → ExpenseRow с корректным типом is_recurring (bool).

    Если задан view_month/view_year (запрос конкретного периода в
    get_expenses), месяц/год в результате подменяются на запрошенный
    период — иначе спроецированный повторяющийся расход показывал бы
    месяц своего создания, а не месяц, на который он сейчас
    распространяется.
    """
    d = dict(r)
    d["is_recurring"] = bool(d["is_recurring"])
    # Убеждаемся, что group_id/recurring_until присутствуют
    if "group_id" not in d:
        d["group_id"] = None
    if "recurring_until" not in d:
        d["recurring_until"] = None
    if view_month is not None and view_year is not None:
        d["month"] = view_month
        d["year"] = view_year
    return ExpenseRow(**d)
