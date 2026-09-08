"""db.migrations — первичная инициализация БД и аддитивные миграции.

``bootstrap(engine)`` повторяет порядок старого ``DatabaseManager._init_db``:
создать схему -> аддитивные ALTER -> перенос оклада из settings -> seed дефолтов.
Все тела перенесены символ-в-символ; ``migrate_schema(conn)`` сохраняет прежнюю
сигнатуру (тест вызывает её в своей транзакции) и идемпотентность.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from config import SETTINGS
from db.schema import create_schema


def _today_year() -> int:
    return date.today().year


def bootstrap(engine) -> None:  # noqa: ANN001 — Engine, но без цикла импорта
    """Инициализировать БД: схема + миграции + seed. Порядок и закрытие
    файлового соединения — как в старом ``_init_db``."""
    c = engine._conn()
    try:
        create_schema(c)
        migrate_schema(c)
        seed_defaults(c)
    finally:
        if engine.db_path != ":memory:":
            c.close()


def migrate_schema(c: sqlite3.Connection) -> None:
    """Аддитивные миграции для баз, созданных до появления новых колонок.

    `CREATE TABLE IF NOT EXISTS` не добавляет колонки к уже существующей
    таблице, поэтому недостающие столбцы добавляем явно (идемпотентно).
    """
    vacation_cols = {
        row["name"] for row in c.execute("PRAGMA table_info(vacations)").fetchall()
    }
    for column in ("start_date", "end_date"):
        if column not in vacation_cols:
            c.execute(f"ALTER TABLE vacations ADD COLUMN {column} TEXT")

    expense_cols = {row["name"] for row in c.execute("PRAGMA table_info(expenses)").fetchall()}
    if "recurring_until" not in expense_cols:
        c.execute("ALTER TABLE expenses ADD COLUMN recurring_until TEXT")

    group_cols = {
        row["name"] for row in c.execute("PRAGMA table_info(expense_groups)").fetchall()
    }
    if "monthly_limit" not in group_cols:
        c.execute("ALTER TABLE expense_groups ADD COLUMN monthly_limit REAL")

    # Плановый ежемесячный платёж по долгу — вычитается из баланса месяца.
    debt_cols = {row["name"] for row in c.execute("PRAGMA table_info(debts)").fetchall()}
    if "monthly_payment" not in debt_cols:
        c.execute("ALTER TABLE debts ADD COLUMN monthly_payment REAL NOT NULL DEFAULT 0")
    if "payment_half" not in debt_cols:
        c.execute("ALTER TABLE debts ADD COLUMN payment_half INTEGER NOT NULL DEFAULT 2")

    # Доход как сущность-оклад: kind + параметры расчёта зарплаты.
    income_cols = {row["name"] for row in c.execute("PRAGMA table_info(income)").fetchall()}
    for col, decl in (
        ("kind", "TEXT NOT NULL DEFAULT 'fixed'"),
        ("kef", "REAL"), ("split_method", "TEXT"),
        ("first_half_ratio", "REAL"), ("second_half_ratio", "REAL"),
    ):
        if col not in income_cols:
            c.execute(f"ALTER TABLE income ADD COLUMN {col} {decl}")

    c.commit()
    migrate_salary_settings_to_income(c)


def migrate_salary_settings_to_income(c: sqlite3.Connection) -> None:
    """Разовый перенос: оклад из таблицы settings -> строка income
    (kind='salary'). После переноса ключи оклада из settings удаляются —
    SSOT: оклад живёт как доход, а не как настройка."""
    if c.execute("SELECT 1 FROM income WHERE kind='salary' LIMIT 1").fetchone():
        return
    base_row = c.execute("SELECT value FROM settings WHERE key='base_salary'").fetchone()
    if base_row is None:
        return
    try:
        base_amount = float(base_row["value"])
    except (TypeError, ValueError):
        return

    def _s(key: str, default: str) -> str:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r and r["value"] not in (None, "") else default

    yr = c.execute(
        "SELECT MIN(y) FROM (SELECT year AS y FROM expenses "
        "UNION SELECT year FROM income UNION SELECT year FROM debts)"
    ).fetchone()
    eff_year = (yr[0] if yr and yr[0] else _today_year())
    if base_amount > 0:
        c.execute(
            "INSERT INTO income (name, amount, half, month, year, is_recurring, kind, "
            "kef, split_method, first_half_ratio, second_half_ratio) "
            "VALUES ('Зарплата', ?, 1, 1, ?, 1, 'salary', ?, ?, ?, ?)",
            (base_amount, eff_year, float(_s("kef", "1.0")),
             _s("salary_calculation_method", "proportional"),
             float(_s("first_half_ratio", "0.4")), float(_s("second_half_ratio", "0.6"))),
        )
    for key in ("base_salary", "kef", "salary_calculation_method",
                "first_half_ratio", "second_half_ratio"):
        c.execute("DELETE FROM settings WHERE key=?", (key,))
    c.commit()


def seed_defaults(c: sqlite3.Connection) -> None:
    """Первичное заполнение таблицы settings из config.SETTINGS —
    единственного источника доменных дефолтов. Оклад НЕ заводится:
    пустой калькулятор -> нулевая зарплата, пока пользователь не добавит
    строку дохода kind='salary' (несколько работ = несколько строк)."""
    for spec in SETTINGS:
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (spec.key, spec.to_str(spec.default)),
        )
    c.commit()
