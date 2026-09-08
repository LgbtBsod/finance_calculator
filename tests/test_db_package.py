"""test_db_package.py — гарантии слоёного пакета db/ (сверх CRUD-тестов в
test_database.py, которые идут через фасад Database без изменений).
"""

from __future__ import annotations

from pathlib import Path

from db import Database, DatabaseManager
from db.query import _UNSET, build_update

_SNAPSHOT = Path(__file__).parent / "data" / "schema_snapshot.sql"


def _schema_dump(db: Database) -> str:
    with db._transaction() as c:
        rows = c.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY type, name"
        ).fetchall()
    parts: list[str] = []
    for r in rows:
        parts.append(f"-- {r['type']} {r['name']}")
        parts.append(r["sql"].strip() + ";")
        parts.append("")
    return "\n".join(parts) + "\n"


class TestSchemaSnapshot:
    def test_bootstrap_schema_is_byte_identical_to_golden(self):
        """Схема, созданная пакетом db/, символ-в-символ совпадает с зафиксированной
        от прежнего database.py. Ловит любой дрейф DDL при переносе/рефакторинге.
        Обновлять snapshot — только сознательной миграцией схемы."""
        db = Database(":memory:")
        try:
            assert _schema_dump(db) == _SNAPSHOT.read_text(encoding="utf-8")
        finally:
            db.close()


class TestFacadeSurface:
    # Полная публичная поверхность старого DatabaseManager (dir() минус дандеры
    # и приватные). Забытый/переименованный делегатор -> падение здесь.
    EXPECTED = {
        "get_setting", "get_settings_bundle", "set_setting",
        "calendar_needs_fill", "save_calendar_data", "clear_calendar_cache",
        "get_calendar_month", "get_corrections", "save_corrections",
        "add_birthday", "get_birthdays", "delete_birthday", "update_birthday",
        "add_expense", "get_expenses", "set_period_override", "clear_period_override",
        "delete_expense", "update_expense",
        "add_income", "get_income", "delete_income", "update_income",
        "add_vacation", "get_vacations", "delete_vacation",
        "create_expense_group", "get_expense_groups", "get_expense_group",
        "update_expense_group", "delete_expense_group",
        "create_debt", "update_debt", "get_debts", "delete_debt",
        "add_debt_repayment", "delete_debt_repayment",
        "snapshot_for_undo", "restore_from_undo",
        "close", "backup_to",
    }

    def test_facade_exposes_full_legacy_surface(self):
        missing = self.EXPECTED - set(dir(Database))
        assert not missing, f"фасад Database потерял методы: {sorted(missing)}"

    def test_alias_is_the_same_class(self):
        assert DatabaseManager is Database


class TestBuildUpdate:
    """build_update заменил ручные SET-конструкторы в update_expense_group /
    update_debt. Строка SQL должна остаться символ-в-символ прежней —
    иначе это молчаливое изменение поведения БД."""

    def test_expense_group_full_sql_matches_legacy(self):
        sql, params = build_update("expense_groups", {
            "name": "n", "color": "c", "parent_id": "p",
            "sort_order": 1, "monthly_limit": 2.0,
        }, {"id": "g1"})
        assert sql == (
            "UPDATE expense_groups SET name=?, color=?, parent_id=?, "
            "sort_order=?, monthly_limit=? WHERE id=?"
        )
        assert params == ["n", "c", "p", 1, 2.0, "g1"]

    def test_debt_full_sql_matches_legacy(self):
        sql, params = build_update("debts", {
            "title": "t", "total_amount": 1.0,
            "monthly_payment": 2.0, "payment_half": 1,
        }, {"id": 5})
        assert sql == (
            "UPDATE debts SET title=?, total_amount=?, "
            "monthly_payment=?, payment_half=? WHERE id=?"
        )
        assert params == ["t", 1.0, 2.0, 1, 5]

    def test_unset_skips_column_none_writes_null(self):
        sql, params = build_update("expense_groups", {
            "name": _UNSET, "color": _UNSET, "parent_id": None,
            "sort_order": _UNSET, "monthly_limit": _UNSET,
        }, {"id": "g1"})
        assert sql == "UPDATE expense_groups SET parent_id=? WHERE id=?"
        assert params == [None, "g1"]

    def test_empty_fieldset_returns_none(self):
        sql, params = build_update("debts", dict.fromkeys(
            ("title", "total_amount", "monthly_payment", "payment_half"), _UNSET,
        ), {"id": 5})
        assert sql is None and params == []
