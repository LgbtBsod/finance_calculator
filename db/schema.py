"""db.schema — DDL пакета. Одна строка ``executescript`` (CREATE TABLE/INDEX),
перенесённая символ-в-символ из старого ``DatabaseManager._init_db``. Аддитивные
миграции для уже существующих баз — в ``db.migrations``.
"""

from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
                -- Группы расходов (для категоризации)
                CREATE TABLE IF NOT EXISTS expense_groups (
                    id            TEXT    PRIMARY KEY,
                    name          TEXT    NOT NULL,
                    color         TEXT    NOT NULL,
                    parent_id     TEXT,
                    sort_order    INTEGER NOT NULL DEFAULT 0,
                    monthly_limit REAL
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

                -- Доходы (прибавляются к балансу). kind='fixed' — разовая/
                -- повторяющаяся сумма; kind='salary' — оклад, который считает
                -- SalaryCalculator (amount = оклад в месяц, + kef/метод/пропорции).
                CREATE TABLE IF NOT EXISTS income (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    name              TEXT    NOT NULL,
                    amount            REAL    NOT NULL DEFAULT 0.0,
                    half              INTEGER NOT NULL DEFAULT 1,
                    month             INTEGER NOT NULL,
                    year              INTEGER NOT NULL,
                    is_recurring      INTEGER NOT NULL DEFAULT 0,
                    recurring_until   TEXT,
                    kind              TEXT    NOT NULL DEFAULT 'fixed',
                    kef               REAL,
                    split_method      TEXT,
                    first_half_ratio  REAL,
                    second_half_ratio REAL
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
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    title           TEXT    NOT NULL,
                    total_amount    REAL    NOT NULL DEFAULT 0.0,
                    month           INTEGER NOT NULL,
                    year            INTEGER NOT NULL,
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                    monthly_payment REAL    NOT NULL DEFAULT 0,
                    payment_half    INTEGER NOT NULL DEFAULT 2
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

                -- Переопределение суммы повторяющейся строки на конкретный
                -- месяц ("в этом месяце счёт был больше"). kind: expense|income.
                CREATE TABLE IF NOT EXISTS period_overrides (
                    kind    TEXT    NOT NULL,
                    row_id  INTEGER NOT NULL,
                    year    INTEGER NOT NULL,
                    month   INTEGER NOT NULL,
                    amount  REAL    NOT NULL,
                    PRIMARY KEY (kind, row_id, year, month)
                );

                -- Расходы/доходы почти всегда фильтруются по (year, month);
                -- погашения долга — по debt_id (см. get_expenses/get_debts).
                CREATE INDEX IF NOT EXISTS idx_expenses_year_month ON expenses(year, month);
                CREATE INDEX IF NOT EXISTS idx_income_year_month ON income(year, month);
                CREATE INDEX IF NOT EXISTS idx_debt_repayments_debt_id ON debt_repayments(debt_id);
            """


def create_schema(conn: sqlite3.Connection) -> None:
    """Создать таблицы/индексы (идемпотентно — все ``IF NOT EXISTS``)."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
