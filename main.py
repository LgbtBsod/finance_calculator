"""Finance Calculator — точка входа.

Запускает Flet-GUI (локальный web-сервер, открывает вкладку браузера). В
собранной PyInstaller-версии все данные / логи лежат рядом с .exe, чтобы
пережить обновление (см. ``paths``).
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path


def _ensure_std_streams() -> None:
    """PyInstaller ``--windowed`` сборка не имеет консоли — ``sys.stdout`` /
    ``sys.stderr`` равны ``None`` и первый ``print()`` (наш, uvicorn'а, Flet'а)
    уронил бы приложение. Перенаправляем в лог-файл рядом с exe, иначе в
    /dev/null. Должно выполниться до любого вывода."""
    if not getattr(sys, "frozen", False):
        return
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is not None:
            continue
        stream = None
        try:
            log_path = Path(sys.executable).parent / "logs" / "console.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            stream = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")  # noqa: SIM115
        except OSError:
            try:
                stream = open(os.devnull, "w")  # noqa: SIM115
            except OSError:
                stream = None
        if stream is not None:
            setattr(sys, name, stream)
            setattr(sys, f"__{name}__", stream)


_ensure_std_streams()

# Bootstrap: положить корень (src/ бандла или папку этого файла) в sys.path.
_here = Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent)
for _p in (_here, Path(__file__).resolve().parent):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import paths  # noqa: E402

_ATTEMPTS_STAMP = "update_attempts"


def _digest(path: Path) -> str:
    import hashlib

    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _finish_pending_update(log) -> bool:
    """Файл ``<exe>.updated`` рядом с нами означает, что self-update скачал
    новый бинарник, но подмена могла не завершиться. Если staged-файл
    байт-в-байт совпадает с запущенным — подмена уже прошла, чистим мусор.
    Иначе отдаём свежему хелперу и выходим. Сдаёмся после 3 попыток."""
    exe = paths.exe_path or Path(sys.executable)
    staged = exe.with_name(exe.name + ".updated")
    stamp = paths.logs_dir / _ATTEMPTS_STAMP

    if not staged.is_file() or staged.stat().st_size < 1_000_000:
        stamp.unlink(missing_ok=True)
        return False

    try:
        if _digest(staged) == _digest(exe):
            log.info("Staged update is already the running version — cleaning up.")
            staged.unlink(missing_ok=True)
            stamp.unlink(missing_ok=True)
            return False
    except OSError:
        pass

    try:
        attempts = int(stamp.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        attempts = 0
    if attempts >= 3:
        log.error("Update swap failed %d times — running the current version.", attempts)
        staged.unlink(missing_ok=True)
        stamp.unlink(missing_ok=True)
        return False

    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(attempts + 1), encoding="utf-8")
    except OSError:
        pass

    log.warning("Staged update pending — handing to a fresh helper (attempt %d/3).", attempts + 1)
    try:
        from updater import AutoUpdater

        AutoUpdater()._relaunch_after_update()
        return True
    except Exception as e:
        log.error("Could not finish the pending update: %s", e)
        return False


def _cleanup_update_leftovers(log) -> None:
    exe = paths.exe_path or Path(sys.executable)
    for path in (exe.with_name(exe.name + ".old"),):
        for attempt in range(3):
            try:
                if path.exists():
                    path.unlink()
                    log.info("Removed update leftover: %s", path.name)
                break
            except OSError:
                time.sleep(0.3 * (attempt + 1))


def _get_logger():
    import logging

    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(paths.logs_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("main")


def main() -> None:
    log = _get_logger()
    log.info(
        "App dir: %s | frozen: %s | python: %s",
        paths.app_dir, paths.frozen, sys.version.split()[0],
    )
    log.info("Args: %s", sys.argv)

    args = sys.argv[1:]
    if paths.frozen:
        if _finish_pending_update(log):
            log.info("Pending update handed to the relaunch helper; exiting.")
            return
        _cleanup_update_leftovers(log)
        paths.sync_version_file()
        log.info("Running version: %s", paths.read_version())

    if paths.frozen and "--force-update" in args:
        try:
            from updater import check_updates

            if check_updates(auto=True, force=True):
                log.info("Update staged; exiting for relaunch.")
                return
        except Exception as e:
            log.warning("Forced update failed, continuing: %s", e)

    port = 8420
    if "--port" in args:
        with contextlib.suppress(ValueError, IndexError):
            port = int(args[args.index("--port") + 1])

    log.info("Starting Flet GUI on port %d", port)
    try:
        from core.bootstrap import build_kernel
        from gui.app import run_app

        kernel = build_kernel(str(paths.db_path))
        log.info("Ядро собрано: модули %s", ", ".join(kernel._order))
        run_app(kernel=kernel, port=port)
    except Exception as e:
        log.critical("Fatal error starting GUI: %s", e, exc_info=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
