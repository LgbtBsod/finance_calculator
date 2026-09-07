"""paths.py — Единственное место, определяющее где что лежит.

Frozen (PyInstaller one-file): всё рядом с .exe, чтобы пользовательская БД,
логи и version.txt пережили обновление.  Из исходников: всё в корне репозитория.

``main.py``, ``gui.app``, ``updater`` и ``config`` читают отсюда, а не
переопределяют цепочки ``sys.executable`` / ``__file__`` каждый у себя.
"""

from __future__ import annotations

import sys
from pathlib import Path

frozen: bool = bool(getattr(sys, "frozen", False))
meipass: Path | None = Path(sys._MEIPASS) if getattr(sys, "_MEIPASS", None) else None

if frozen:
    app_dir: Path = Path(sys.executable).resolve().parent
    exe_path: Path | None = Path(sys.executable).resolve()
else:
    app_dir = Path(__file__).resolve().parent
    exe_path = None

db_path: Path = app_dir / "budget.db"
logs_dir: Path = app_dir / "logs"


def version_file_candidates() -> list[Path]:
    """Все места, где может лежать ``version.txt``, самое авторитетное первым.

    Для frozen-сборки бандленный ``_MEIPASS/version.txt`` авторитетен: он
    лежит ВНУТРИ запущенного бинарника, то есть всегда отражает истинную
    версию исполняемого кода — даже если self-update заменил .exe, но рядом
    остался устаревший ``app_dir/version.txt`` (или наоборот). Из исходников
    файл один — в корне репозитория.
    """
    out: list[Path] = []
    if meipass:
        out.append(meipass / "version.txt")
    out.append(app_dir / "version.txt")
    return out


def read_version() -> str:
    """Текущая версия из ``version.txt`` либо ``"unknown"``.

    Срезает префикс релиз-тега (``v`` / ``v.``), чтобы файл, записанный
    старой версией апдейтера (оставлявшей ведущую точку), тоже читался чисто.
    """
    for path in version_file_candidates():
        try:
            if path.is_file():
                text = path.read_text(encoding="utf-8").strip().lstrip("vV").strip(". \t\r\n")
                if text:
                    return text
        except OSError:
            pass
    return "unknown"


def sync_version_file() -> None:
    """Frozen only: зеркалит бандленный ``_MEIPASS/version.txt`` в
    ``app_dir/version.txt``, чтобы внешние инструменты (и atom-feed проверка
    обновлений) видели версию реально запущенного бинарника. Апдейтер сам
    ``app_dir/version.txt`` не пишет — это единственный писатель.
    """
    if not (frozen and meipass):
        return
    src, dst = meipass / "version.txt", app_dir / "version.txt"
    try:
        want = src.read_text(encoding="utf-8")
        if not dst.is_file() or dst.read_text(encoding="utf-8") != want:
            dst.write_text(want, encoding="utf-8")
    except OSError:
        pass


def open_in_file_manager(path: Path | str) -> bool:
    """Показать ``path`` в файловом менеджере ОС. Возвращает, была ли команда
    отправлена (не факт появления окна)."""
    import subprocess

    target = str(path)
    match sys.platform:
        case "win32":
            argv = ["explorer.exe", target]
        case "darwin":
            argv = ["open", target]
        case _:
            argv = ["xdg-open", target]
    try:
        subprocess.Popen(argv)
        return True
    except OSError:
        return False
