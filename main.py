"""main.py — Точка входа для standalone-запуска (в т.ч. собранного PyInstaller exe).

Отличия от `uvicorn api:app`:
  - БД всегда рядом с исполняемым файлом (а не во временной папке
    распаковки PyInstaller и не в текущей рабочей директории) — данные
    переживают перезапуск и не зависят от того, откуда запущен exe.
  - Автоматически открывает браузер после старта сервера — так же, как
    делал run.bat, только без обёртки в bat-скрипт.

Обычная разработка (`python -m uvicorn api:app --reload`) продолжает
работать как прежде — этот файл её не заменяет, а дополняет.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
# Порт 8000 занят чуть ли не чаще любого другого (Django, другие dev-серверы
# и т.п.) — начинаем с менее распространённого, а если и он занят, ОС сама
# выдаёт свободный (см. _find_free_port).
PREFERRED_PORT = 8420


def _app_base_dir() -> Path:
    """Папка рядом с exe (frozen) или рядом с этим файлом (обычный запуск)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _configure_db_path() -> None:
    """БД — рядом с exe/скриптом, если пользователь не указал FINANCE_DB_PATH явно."""
    os.environ.setdefault("FINANCE_DB_PATH", str(_app_base_dir() / "budget.db"))


def _find_free_port(preferred: int) -> int:
    """Предпочитаемый порт, если свободен; иначе — любой свободный от ОС."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))  # 0 -> ОС назначает свободный порт
        return s.getsockname()[1]


def _open_browser_when_ready(port: int) -> None:
    import time
    import urllib.request

    url = f"http://{HOST}:{port}"
    for _ in range(50):  # до ~10 секунд
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    _configure_db_path()
    port = _find_free_port(PREFERRED_PORT)

    # Импорт после настройки FINANCE_DB_PATH — AppSettings читает env при создании.
    import uvicorn

    from api import app

    print(f"Finance Calculator: http://{HOST}:{port}")
    threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="info")


if __name__ == "__main__":
    main()
