"""test_paths.py — резолвер путей: раскладка БД в db/ и миграция со старой."""

from __future__ import annotations

from pathlib import Path

import paths


def _point_paths_at(tmp: Path, monkeypatch) -> None:
    """Переопределить модульные пути paths.* на изолированную папку."""
    monkeypatch.setattr(paths, "app_dir", tmp)
    monkeypatch.setattr(paths, "db_dir", tmp / "db")
    monkeypatch.setattr(paths, "db_path", tmp / "db" / "budget.db")
    monkeypatch.setattr(paths, "_legacy_db_path", tmp / "budget.db")


def test_ensure_db_dir_creates_folder(tmp_path, monkeypatch):
    _point_paths_at(tmp_path, monkeypatch)

    paths.ensure_db_dir()

    assert (tmp_path / "db").is_dir()


def test_ensure_db_dir_migrates_legacy_flat_db_with_wal_shm(tmp_path, monkeypatch):
    _point_paths_at(tmp_path, monkeypatch)
    (tmp_path / "budget.db").write_text("real-data")
    (tmp_path / "budget.db-wal").write_text("wal")
    (tmp_path / "budget.db-shm").write_text("shm")

    paths.ensure_db_dir()

    assert (tmp_path / "db" / "budget.db").read_text() == "real-data"
    assert (tmp_path / "db" / "budget.db-wal").exists()
    assert (tmp_path / "db" / "budget.db-shm").exists()
    assert not (tmp_path / "budget.db").exists()  # перенесён, не скопирован


def test_ensure_db_dir_does_not_touch_legacy_when_new_db_exists(tmp_path, monkeypatch):
    _point_paths_at(tmp_path, monkeypatch)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "budget.db").write_text("current")
    (tmp_path / "budget.db").write_text("stale-leftover")

    paths.ensure_db_dir()

    assert (tmp_path / "db" / "budget.db").read_text() == "current"
    assert (tmp_path / "budget.db").read_text() == "stale-leftover"  # не тронут


def test_ensure_db_dir_is_idempotent(tmp_path, monkeypatch):
    _point_paths_at(tmp_path, monkeypatch)
    (tmp_path / "budget.db").write_text("data")

    paths.ensure_db_dir()
    paths.ensure_db_dir()

    assert (tmp_path / "db" / "budget.db").read_text() == "data"
