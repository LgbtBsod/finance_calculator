"""Тесты self-updater (updater.AutoUpdater)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from updater import AutoUpdater, DownloadProgress, UpdateError, normalize_version


@pytest.fixture
def updater() -> AutoUpdater:
    return AutoUpdater(current_version="1.0.0")


class TestVersioning:
    def test_normalize_strips_prefix_and_space(self):
        assert normalize_version("v1.2.3") == "1.2.3"
        assert normalize_version("V1.2.3") == "1.2.3"
        assert normalize_version("v.1.2.3") == "1.2.3"
        assert normalize_version(" 1.2.3 \n") == "1.2.3"

    def test_is_newer(self, updater):
        assert updater._is_newer_version("2.0.0", "1.0.0") is True
        assert updater._is_newer_version("1.0.1", "1.0.0") is True
        assert updater._is_newer_version("1.0.0", "1.0.0") is False
        assert updater._is_newer_version("0.9.9", "1.0.0") is False


class TestAssets:
    def test_platform_asset(self, updater):
        updater.is_frozen = False
        assert updater._platform_asset() is None

        updater.is_frozen = True
        with patch.object(sys, "platform", "win32"):
            assert updater._platform_asset() == "FinanceCalculator-windows.exe"
        with patch.object(sys, "platform", "darwin"):
            assert updater._platform_asset() == "FinanceCalculator-macos"
        with patch.object(sys, "platform", "linux"):
            assert updater._platform_asset() == "FinanceCalculator-linux"

    def test_asset_keywords(self, updater):
        updater.is_frozen = False
        assert ".zip" in updater._asset_keywords()

        updater.is_frozen = True
        with patch.object(sys, "platform", "win32"):
            assert "windows" in updater._asset_keywords()
        with patch.object(sys, "platform", "linux"):
            assert "linux" in updater._asset_keywords()

    def test_resolve_download_url_by_platform(self, updater):
        release = {
            "assets": [
                {"name": "FinanceCalculator-windows.exe", "browser_download_url": "u/win"},
                {"name": "FinanceCalculator-linux", "browser_download_url": "u/linux"},
            ]
        }
        updater.is_frozen = True
        with patch.object(sys, "platform", "win32"):
            assert updater._resolve_download_url(release) == "u/win"
        with patch.object(sys, "platform", "linux"):
            assert updater._resolve_download_url(release) == "u/linux"

    def test_pick_release_skips_drafts_and_missing_assets(self, updater):
        updater.is_frozen = False
        releases = [
            {"tag_name": "v3.0.0", "draft": True},
            {"tag_name": "v2.0.0", "draft": False,
             "assets": [{"name": "x.zip", "browser_download_url": "u/zip"}]},
        ]
        chosen = updater._pick_release(releases)
        assert chosen and chosen["tag_name"] == "v2.0.0"

        with patch.object(updater, "_resolve_download_url", return_value=None):
            assert updater._pick_release([{"tag_name": "v2.0.0", "draft": False}]) is None


class TestDiscovery:
    @patch("updater.urlopen")
    def test_check_via_web(self, mock_urlopen, updater):
        resp = MagicMock()
        resp.read.return_value = (
            b'<feed><link href="https://github.com/LgbtBsod/finance_calculator'
            b'/releases/tag/v2.0.0"/></feed>'
        )
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        mock_urlopen.return_value = resp
        with patch.object(updater, "_asset_available", return_value=True), \
             patch.object(updater, "_platform_asset", return_value="FinanceCalculator-linux"):
            updater.is_frozen = True
            has, version, url = updater._check_via_web()
        assert has is True
        assert version == "v2.0.0"
        assert "v2.0.0" in url

    def test_run_update_check_no_update(self, updater):
        with patch.object(updater, "check_for_updates", return_value=(False, "1.0.0", None)):
            assert updater.run_update_check(auto=False) is False

    def test_run_update_check_auto_downloads(self, updater):
        with patch.object(updater, "check_for_updates",
                          return_value=(True, "2.0.0", "u/update.zip")), \
             patch.object(updater, "download_update", return_value=True) as dl:
            assert updater.run_update_check(auto=True) is True
            dl.assert_called_once()


class TestDownloadAndBackup:
    @patch("updater.urlopen")
    def test_download_with_progress(self, mock_urlopen, updater):
        resp = MagicMock()
        resp.getheader.return_value = "2048"
        resp.read.side_effect = [b"x" * 512] * 4 + [b""]
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        mock_urlopen.return_value = resp

        cb = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "u.zip"
            ok, err = updater._download_with_progress("https://example.com/u.zip", dest, cb)
            assert ok is True, err
            assert err == ""
            assert cb.called
            assert dest.stat().st_size == 2048

    def test_checksum(self, updater):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            p = Path(f.name)
        try:
            assert updater._calculate_checksum(p) == (
                "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
            )
        finally:
            p.unlink()

    def test_backup_and_restore(self, updater):
        with tempfile.TemporaryDirectory() as tmp:
            updater.app_dir = Path(tmp)
            (updater.app_dir / "version.txt").write_text("1.0.0")
            (updater.app_dir / "budget.db").write_text("db-bytes")

            backup = updater._create_backup()
            assert backup and (backup / "version.txt").exists()
            assert (backup / "budget.db").exists()

            (updater.app_dir / "version.txt").write_text("9.9.9")
            assert updater._restore_from_backup() is True
            assert (updater.app_dir / "version.txt").read_text() == "1.0.0"

    def test_backup_and_restore_covers_db_folder(self, updater):
        """Пользовательская БД лежит в db/ — бэкап/откат должны её захватывать."""
        with tempfile.TemporaryDirectory() as tmp:
            updater.app_dir = Path(tmp)
            (updater.app_dir / "version.txt").write_text("1.0.0")
            (updater.app_dir / "db").mkdir()
            (updater.app_dir / "db" / "budget.db").write_text("real-data")

            backup = updater._create_backup()
            assert backup and (backup / "db" / "budget.db").read_text() == "real-data"

            (updater.app_dir / "db" / "budget.db").write_text("corrupted-by-update")
            assert updater._restore_from_backup() is True
            assert (updater.app_dir / "db" / "budget.db").read_text() == "real-data"

    def test_copy_update_files_never_overwrites_db_folder(self, updater):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            (src / "db").mkdir(parents=True)
            (src / "db" / "budget.db").write_text("release-placeholder")
            (src / "main.py").write_text("# main")

            dest = Path(tmp) / "dest"
            (dest / "db").mkdir(parents=True)
            (dest / "db" / "budget.db").write_text("user-data")
            updater.app_dir = dest

            updater._copy_update_files(src)

            assert (dest / "db" / "budget.db").read_text() == "user-data"

    def test_copy_update_files_skips_junk(self, updater):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            (src / "venv").mkdir(parents=True)
            (src / "venv" / "python").write_text("x")
            (src / "main.py").write_text("# main")
            (src / "gui").mkdir()
            (src / "gui" / "app.py").write_text("# app")
            (src / "budget.db").write_text("db")

            dest = Path(tmp) / "dest"
            dest.mkdir()
            updater.app_dir = dest
            copied = updater._copy_update_files(src)
            assert copied == 2  # main.py + gui/app.py; venv/ и budget.db пропущены
            assert (dest / "main.py").exists()
            assert (dest / "gui" / "app.py").exists()
            assert not (dest / "venv").exists()
            assert not (dest / "budget.db").exists()

    def test_update_version_file(self, updater):
        with tempfile.TemporaryDirectory() as tmp:
            updater.app_dir = Path(tmp)
            updater._update_version_file("v2.5.0")
            assert (updater.app_dir / "version.txt").read_text().strip() == "2.5.0"


class TestProgressAndErrors:
    def test_download_progress_props(self):
        p = DownloadProgress(bytes_downloaded=50, total_bytes=100, speed_bps=1024 * 1024)
        assert p.percent == 50.0
        assert p.is_complete is False
        assert p.speed_mbps == 1.0
        p.bytes_downloaded = 100
        assert p.is_complete is True

    def test_update_error(self):
        assert UpdateError("x", recoverable=True).recoverable is True
        assert UpdateError("y", recoverable=False).recoverable is False


class TestCheckUpdatesEntry:
    @patch("updater._recently_checked", return_value=True)
    def test_skips_recent(self, _recent):
        from updater import check_updates

        assert check_updates(auto=True, force=False) is False

    @patch("updater._recently_checked", return_value=False)
    @patch("updater.AutoUpdater")
    def test_marks_checked(self, mock_cls, _recent):
        inst = Mock()
        inst.run_update_check.return_value = False
        inst._rate_limited = False
        inst._network_reachable = True
        mock_cls.return_value = inst
        from updater import check_updates

        with patch("updater._mark_checked") as mark:
            check_updates(auto=False, force=True)
            mark.assert_called_once()
