"""
Tests for the Updater Module.
Проверка функционала авто-обновления через GitHub Releases.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch


class TestUpdaterModule:
    """Тесты для модуля обновлений."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        from modules.updater.updater import UpdaterModule, normalize_version

        self.updater = UpdaterModule(
            repo_owner="LgbtBsod", repo_name="finance_calculator", current_version="1.0.0"
        )
        self.normalize_version = normalize_version

    def test_normalize_version_strips_v_prefix(self):
        """Тест нормализации версий - удаление префикса v."""
        assert self.normalize_version("v1.2.3") == "1.2.3"
        assert self.normalize_version("V1.2.3") == "1.2.3"
        assert self.normalize_version("v.1.2.3") == "1.2.3"
        assert self.normalize_version("1.2.3") == "1.2.3"

    def test_normalize_version_strips_whitespace(self):
        """Тест нормализации версий - удаление пробелов."""
        assert self.normalize_version(" 1.2.3 ") == "1.2.3"
        assert self.normalize_version("1.2.3\n") == "1.2.3"
        assert self.normalize_version("\t1.2.3\r\n") == "1.2.3"

    def test_is_newer_version_semantic(self):
        """Тест сравнения версий через packaging."""
        assert self.updater._is_newer_version("2.0.0", "1.0.0") is True
        assert self.updater._is_newer_version("1.1.0", "1.0.0") is True
        assert self.updater._is_newer_version("1.0.1", "1.0.0") is True
        assert self.updater._is_newer_version("1.0.0", "1.0.0") is False
        assert self.updater._is_newer_version("0.9.9", "1.0.0") is False

    def test_platform_asset_returns_correct_name(self):
        """Тест определения имени ассета для платформы."""
        original_platform = sys.platform

        try:
            # Тест для Windows
            with patch.object(sys, "platform", "win32"):
                self.updater.is_frozen = True
                asset = self.updater._platform_asset()
                assert asset == "FinanceCalculator-windows.exe"

            # Тест для macOS
            with patch.object(sys, "platform", "darwin"):
                self.updater.is_frozen = True
                asset = self.updater._platform_asset()
                assert asset == "FinanceCalculator-macos"

            # Тест для Linux
            with patch.object(sys, "platform", "linux"):
                self.updater.is_frozen = True
                asset = self.updater._platform_asset()
                assert asset == "FinanceCalculator-linux"

            # Тест для не-frozen версии
            self.updater.is_frozen = False
            asset = self.updater._platform_asset()
            assert asset is None

        finally:
            # Восстановление оригинальной платформы
            with patch.object(sys, "platform", original_platform):
                pass

    def test_asset_keywords_for_platform(self):
        """Тест ключевых слов для поиска ассетов."""
        original_platform = sys.platform

        try:
            # Windows
            with patch.object(sys, "platform", "win32"):
                self.updater.is_frozen = True
                keywords = self.updater._asset_keywords()
                assert "windows" in keywords or ".exe" in keywords

            # macOS
            with patch.object(sys, "platform", "darwin"):
                self.updater.is_frozen = True
                keywords = self.updater._asset_keywords()
                assert any(k in keywords for k in ["macos", "mac", "darwin"])

            # Linux
            with patch.object(sys, "platform", "linux"):
                self.updater.is_frozen = True
                keywords = self.updater._asset_keywords()
                assert "linux" in keywords

            # Не-frozen версия
            self.updater.is_frozen = False
            keywords = self.updater._asset_keywords()
            assert ".zip" in keywords

        finally:
            with patch.object(sys, "platform", original_platform):
                self.updater.is_frozen = False  # Reset to default

    @patch("modules.updater.updater.urlopen")
    def test_check_via_web_success(self, mock_urlopen):
        """Тест успешной проверки через releases.atom."""
        # Мокируем ответ с atom feed
        mock_response = MagicMock()
        mock_response.read.return_value = b"""<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <link href="https://github.com/LgbtBsod/finance_calculator/releases/tag/v2.0.0"/>
            </entry>
        </feed>""".replace(b"\n", b" ")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_response

        # Мокируем проверку доступности ассета и platform asset
        with (
            patch.object(self.updater, "_asset_available", return_value=True),
            patch.object(self.updater, "_platform_asset", return_value="FinanceCalculator-linux"),
        ):
            result = self.updater._check_via_web()

            if result is not None:
                has_update, latest_version, download_url = result
                assert has_update is True
                assert latest_version == "v2.0.0"

    def test_resolve_download_url_from_assets(self):
        """Тест получения URL загрузки из ассетов релиза."""
        release_info = {
            "assets": [
                {
                    "name": "FinanceCalculator-windows.exe",
                    "browser_download_url": "https://example.com/win.exe",
                },
                {
                    "name": "FinanceCalculator-macos",
                    "browser_download_url": "https://example.com/mac",
                },
                {
                    "name": "FinanceCalculator-linux",
                    "browser_download_url": "https://example.com/linux",
                },
            ]
        }

        original_platform = sys.platform

        try:
            # Windows
            with patch.object(sys, "platform", "win32"):
                self.updater.is_frozen = True
                url = self.updater._resolve_download_url(release_info)
                assert url == "https://example.com/win.exe"

            # macOS
            with patch.object(sys, "platform", "darwin"):
                self.updater.is_frozen = True
                url = self.updater._resolve_download_url(release_info)
                assert url == "https://example.com/mac"

            # Linux
            with patch.object(sys, "platform", "linux"):
                self.updater.is_frozen = True
                url = self.updater._resolve_download_url(release_info)
                assert url == "https://example.com/linux"

        finally:
            with patch.object(sys, "platform", original_platform):
                pass

    def test_pick_release_skips_drafts(self):
        """Тест что черновики пропускаются при выборе релиза."""
        releases = [
            {"tag_name": "v3.0.0", "draft": True},
            {
                "tag_name": "v2.0.0",
                "draft": False,
                "assets": [
                    {"name": "test.zip", "browser_download_url": "https://example.com/test.zip"}
                ],
            },
        ]

        # Для не-frozen версии .zip является валидным ассетом
        self.updater.is_frozen = False
        result = self.updater._pick_release(releases)
        assert result is not None
        assert result["tag_name"] == "v2.0.0"

    def test_pick_release_requires_asset(self):
        """Тест что релиз без ассета для платформы пропускается."""
        releases = [{"tag_name": "v2.0.0", "draft": False, "assets": []}]

        self.updater.is_frozen = False
        with patch.object(self.updater, "_resolve_download_url", return_value=None):
            result = self.updater._pick_release(releases)
            assert result is None

    def test_create_backup(self):
        """Тест создания бэкапа перед обновлением."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.updater.app_dir = Path(tmpdir)

            # Создаем фейковые файлы
            (self.updater.app_dir / "version.txt").write_text("1.0.0")
            (self.updater.app_dir / "requirements.txt").write_text("pytest")
            db_dir = self.updater.app_dir / "data" / "db"
            db_dir.mkdir(parents=True)
            (db_dir / "app.db").write_text("fake db")

            backup_dir = self.updater._create_backup()

            assert backup_dir is not None
            assert backup_dir.exists()
            assert (backup_dir / "version.txt").exists()
            assert (backup_dir / "requirements.txt").exists()
            assert (backup_dir / "data" / "db" / "app.db").exists()

    def test_restore_from_backup(self):
        """Тест восстановления из бэкапа."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            self.updater.app_dir = tmp_path / "app"
            self.updater.app_dir.mkdir()

            # Создаем бэкап
            backup_dir = tmp_path / "backup"
            backup_dir.mkdir()
            (backup_dir / "version.txt").write_text("1.0.0")
            db_backup = backup_dir / "data" / "db"
            db_backup.mkdir(parents=True)
            (db_backup / "app.db").write_text("restored db")

            self.updater.backup_dir = backup_dir

            # Создаем текущие файлы которые будут перезаписаны
            (self.updater.app_dir / "version.txt").write_text("2.0.0")
            current_db = self.updater.app_dir / "data" / "db"
            current_db.mkdir(parents=True)
            (current_db / "app.db").write_text("current db")

            # Восстанавливаем
            success = self.updater._restore_from_backup()

            assert success is True
            assert (self.updater.app_dir / "version.txt").read_text() == "1.0.0"

    def test_calculate_checksum(self):
        """Тест расчета checksum файла."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            checksum = self.updater._calculate_checksum(temp_path)
            assert len(checksum) == 64  # SHA256 hex length
            assert checksum == "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
        finally:
            temp_path.unlink()

    def test_find_source_root(self):
        """Тест поиска корня исходников в распакованном архиве."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Создаем структуру как в ZIP
            extracted = tmp_path / "extracted"
            extracted.mkdir()
            source_root = extracted / "finance_calculator-2.0.0"
            source_root.mkdir()
            (source_root / "main.py").write_text("# main")
            (extracted / "README.md").write_text("# README")

            result = self.updater._find_source_root(extracted)
            assert result == source_root

    def test_copy_update_files(self):
        """Тест копирования файлов обновления."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Source folder
            source = tmp_path / "source"
            source.mkdir()
            (source / "main.py").write_text("# main")
            (source / "utils.py").write_text("# utils")

            # Skip patterns
            venv = source / "venv"
            venv.mkdir()
            (venv / "python.exe").write_text("fake")

            git_dir = source / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_text("config")

            # Dest folder
            dest = tmp_path / "dest"
            dest.mkdir()
            self.updater.app_dir = dest

            files_copied = self.updater._copy_update_files(source)

            assert files_copied == 2  # main.py и utils.py
            assert (dest / "main.py").exists()
            assert (dest / "utils.py").exists()
            assert not (dest / "venv").exists()
            assert not (dest / ".git").exists()

    def test_update_version_file(self):
        """Тест обновления файла версии."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.updater.app_dir = Path(tmpdir)

            self.updater._update_version_file("v2.0.0")

            version_file = self.updater.app_dir / "version.txt"
            assert version_file.exists()
            assert version_file.read_text().strip() == "2.0.0"

    @patch("modules.updater.updater.urlopen")
    def test_download_with_progress(self, mock_urlopen):
        """Тест загрузки с отслеживанием прогресса."""
        # Мокируем ответ с файлом - размер должен быть больше MIN_UPDATE_SIZE (1024 байта)
        file_size = 2048  # Больше чем MIN_UPDATE_SIZE
        mock_response = MagicMock()
        mock_response.getheader.return_value = str(file_size)  # Content-Length
        chunk_size = 512
        mock_response.read.side_effect = [b"x" * chunk_size for _ in range(4)] + [
            b""
        ]  # 4 chunks of 512 = 2048 bytes
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_response

        progress_callback = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_path = Path(tmpdir) / "test.zip"

            success, error_msg = self.updater._download_with_progress(
                "https://example.com/test.zip", dest_path, progress_callback
            )

            assert success is True
            assert error_msg == ""
            assert dest_path.exists()
            assert progress_callback.called

    def test_download_progress_properties(self):
        """Тест свойств DownloadProgress."""
        from modules.updater.updater import DownloadProgress

        progress = DownloadProgress(bytes_downloaded=50, total_bytes=100, speed_bps=1024 * 1024)

        assert progress.percent == 50.0
        assert progress.is_complete is False
        assert progress.speed_mbps == 1.0
        assert "MB/s" in progress.formatted_speed

        progress.bytes_downloaded = 100
        assert progress.is_complete is True

        progress.total_bytes = 0
        assert progress.percent == 0.0

    def test_update_error_exception(self):
        """Тест исключения UpdateError."""
        from modules.updater.updater import UpdateError

        exc = UpdateError("Test error", recoverable=True)
        assert str(exc) == "Test error"
        assert exc.recoverable is True

        exc2 = UpdateError("Fatal error", recoverable=False)
        assert exc2.recoverable is False

    def test_set_kernel(self):
        """Тест установки ядра."""
        mock_kernel = Mock()
        self.updater.set_kernel(mock_kernel)
        assert self.updater._kernel is mock_kernel

    def test_initialize_reads_version(self):
        """Тест инициализации читает версию."""
        with patch("modules.updater.updater.read_version", return_value="1.5.0"):
            self.updater.initialize()
            assert self.updater.current_version == "1.5.0"

    def test_get_update_history_empty(self):
        """Тест получения пустой истории обновлений."""
        history = self.updater.get_update_history()
        assert history == []

    def test_shutdown(self):
        """Тест завершения работы модуля."""
        # Просто проверяем что метод существует и не падает
        self.updater.shutdown()

    def test_run_update_check_no_update(self):
        """Тест проверки обновлений когда обновлений нет."""
        with patch.object(self.updater, "check_for_updates", return_value=(False, "1.0.0", None)):
            result = self.updater.run_update_check(auto=False)
            assert result is False

    def test_run_update_check_auto_download(self):
        """Тест авто-загрузки обновлений."""
        with patch.object(
            self.updater,
            "check_for_updates",
            return_value=(True, "2.0.0", "https://example.com/update.zip"),
        ), patch.object(self.updater, "download_update", return_value=True) as mock_download:
            result = self.updater.run_update_check(auto=True)
            assert result is True
            mock_download.assert_called_once()

    def test_create_updater_factory(self):
        """Тест фабричной функции create_updater."""
        from modules.updater.updater import create_updater

        updater = create_updater(
            repo_owner="test_user", repo_name="test_repo", current_version="1.0.0"
        )

        assert updater.repo_owner == "test_user"
        assert updater.repo_name == "test_repo"
        assert updater.current_version == "1.0.0"


class TestCheckUpdatesFunction:
    """Тесты для функции check_updates."""

    @patch("modules.updater.updater._recently_checked", return_value=True)
    def test_check_updates_skips_recent_check(self, mock_recent):
        """Тест что проверка пропускается если недавно проверяли."""
        from modules.updater.updater import check_updates

        result = check_updates(auto=True, force=False)
        assert result is False

    @patch("modules.updater.updater._recently_checked", return_value=False)
    @patch("modules.updater.updater.UpdaterModule")
    def test_check_updates_marks_checked(self, mock_updater_class, mock_recent):
        """Тест что отметка о проверке ставится."""
        from modules.updater.updater import check_updates

        mock_instance = Mock()
        mock_instance.run_update_check.return_value = False
        mock_instance._rate_limited = False
        mock_instance._network_reachable = True
        mock_updater_class.return_value = mock_instance

        with (
            patch("modules.updater.updater.read_version", return_value="1.0.0"),
            patch("modules.updater.updater._mark_checked") as mock_mark,
        ):
            check_updates(auto=False, force=True)
            mock_mark.assert_called_once()
