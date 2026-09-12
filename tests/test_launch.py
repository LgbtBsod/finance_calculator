"""test_launch.py — гейт синхронизации зависимостей в scripts/launch.py."""

from __future__ import annotations

import time

import pytest

launch = pytest.importorskip("scripts.launch")


@pytest.fixture
def stamp(tmp_path, monkeypatch):
    s = tmp_path / "logs" / ".dep_sync"
    req = tmp_path / "requirements.txt"
    req.write_text("flet\n")
    monkeypatch.setattr(launch, "_DEP_STAMP", s)
    monkeypatch.setattr(launch, "ROOT", tmp_path)
    return s, req


def test_no_stamp_means_not_fresh(stamp):
    assert launch._deps_fresh() is False


def test_recent_stamp_is_fresh(stamp):
    launch._mark_deps_synced()
    assert launch._deps_fresh() is True


def test_old_stamp_is_stale(stamp):
    s, _ = stamp
    launch._mark_deps_synced()
    old = time.time() - launch._DEP_TTL - 10
    import os

    os.utime(s, (old, old))
    assert launch._deps_fresh() is False


def test_requirements_changed_after_sync_forces_resync(stamp):
    s, req = stamp
    launch._mark_deps_synced()
    assert launch._deps_fresh() is True
    time.sleep(0.01)
    req.write_text("flet\npackaging\n")   # изменили requirements.txt
    assert launch._deps_fresh() is False


class TestDepsImportability:
    """Регрессия: run.bat пересоздаёт venv/ с нуля, если его нет. Штамп
    logs/.dep_sync — просто файл со временем, ничего не знает о venv, в
    котором был записан. Если он "свежий" по времени, а venv только что
    создан пустым, без явной проверки импорта зависимости молча
    пропустились бы -> main.py падает с ModuleNotFoundError."""

    def test_fresh_stamp_but_missing_module_is_not_fresh(self, stamp, monkeypatch):
        launch._mark_deps_synced()
        assert launch._deps_fresh() is True   # обычный случай — модули реально стоят

        monkeypatch.setattr(launch, "_REQUIRED_MODULES", ("flet", "__definitely_not_installed__"))
        assert launch._deps_importable() is False
        assert launch._deps_fresh() is False  # venv "пустой" -> не свежо, даже если штамп новый

    def test_missing_modules_lists_only_absent_ones(self, monkeypatch):
        monkeypatch.setattr(launch, "_REQUIRED_MODULES", ("flet", "__nope_a__", "__nope_b__"))
        assert launch._missing_modules() == ["__nope_a__", "__nope_b__"]

    def test_main_exits_when_sync_leaves_modules_missing(self, stamp, monkeypatch, capsys):
        """После неудачной попытки установки main() не должен молча
        запускать main.py в гарантированный крэш — явный exit(1)."""
        monkeypatch.setattr(launch, "_REQUIRED_MODULES", ("__still_missing__",))
        monkeypatch.setattr(launch.sys, "argv", ["launch.py", "--skip-update"])
        monkeypatch.setattr(launch.os, "chdir", lambda *_: None)        # не трогаем реальный cwd
        monkeypatch.setattr(launch, "upgrade_pip", lambda: None)
        monkeypatch.setattr(launch, "sync_deps", lambda: None)          # "установка" не помогла
        monkeypatch.setattr(launch, "start_app", lambda *_: pytest.fail("не должен запускать main.py"))

        with pytest.raises(SystemExit) as exc:
            launch.main()
        assert exc.value.code == 1
        assert "__still_missing__" in capsys.readouterr().out
