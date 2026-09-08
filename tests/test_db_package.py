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


class TestReadThroughCache:
    """Engine кэширует ровно 2 горячих целотабличных чтения; write-путь по
    settings / expense_groups сам сбрасывает соответствующий ключ."""

    def _db(self):
        db = Database(":memory:")
        return db

    def test_settings_bundle_is_served_from_cache(self):
        db = self._db()
        try:
            first = db.get_settings_bundle()
            # пишем в обход set_setting -> инвалидации НЕ будет
            with db._transaction() as c:
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('tax_rate', '99')")
            assert db.get_settings_bundle() == first          # всё ещё из кэша
            assert db.get_settings_bundle()["tax_rate"] != "99"
        finally:
            db.close()

    def test_set_setting_invalidates_bundle(self):
        db = self._db()
        try:
            db.get_settings_bundle()
            db.set_setting("tax_rate", "17")
            assert db.get_settings_bundle()["tax_rate"] == "17"
        finally:
            db.close()

    def test_group_writes_invalidate_group_cache(self):
        db = self._db()
        try:
            assert db.get_expense_groups() == []
            db.create_expense_group("g1", "Еда", "#111")
            assert [g["id"] for g in db.get_expense_groups()] == ["g1"]
            db.update_expense_group("g1", name="Продукты")
            assert db.get_expense_groups()[0]["name"] == "Продукты"
            db.delete_expense_group("g1")
            assert db.get_expense_groups() == []
        finally:
            db.close()

    def test_restore_deleted_group_invalidates_cache(self):
        db = self._db()
        try:
            db.create_expense_group("g1", "Еда", "#111")
            snap = db.snapshot_for_undo("expense_group", "g1")
            db.delete_expense_group("g1")
            assert db.get_expense_groups() == []
            db.restore_from_undo(snap)
            assert [g["id"] for g in db.get_expense_groups()] == ["g1"]
        finally:
            db.close()

    def test_returned_objects_are_independent_copies(self):
        db = self._db()
        try:
            db.create_expense_group("g1", "Еда", "#111")
            first = db.get_expense_groups()
            first[0]["name"] = "МУТАЦИЯ"
            first.append({"junk": True})
            assert db.get_expense_groups()[0]["name"] == "Еда"
            assert len(db.get_expense_groups()) == 1

            b1 = db.get_settings_bundle()
            b1["tax_rate"] = "МУТАЦИЯ"
            assert db.get_settings_bundle()["tax_rate"] != "МУТАЦИЯ"
        finally:
            db.close()


class TestUndoTablesIntegrity:
    def test_undo_column_tuples_are_subset_of_actual_schema(self):
        """_UNDO_TABLES перечисляет колонки для INSERT OR IGNORE при восстановлении —
        если схема уедет, восстановление молча потеряет данные или упадёт."""
        from db.repositories.undo import _UNDO_TABLES

        db = Database(":memory:")
        try:
            with db._transaction() as c:
                for _kind, (table, cols) in _UNDO_TABLES.items():
                    actual = {r["name"] for r in c.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()}
                    assert set(cols) <= actual, f"{table}: {set(cols) - actual}"
        finally:
            db.close()
