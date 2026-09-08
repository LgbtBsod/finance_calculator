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
