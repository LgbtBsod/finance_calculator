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
from typing import IO

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


def _acquire_single_instance_lock(lock_path: Path) -> IO[str] | None:
    """Захватывает эксклюзивную ОС-блокировку lock-файла, чтобы второй запущенный
    экземпляр не писал в ту же budget.db одновременно с первым.

    Блокировка именно на уровне ОС, а не проверка PID из lock-файла — та была бы
    ненадёжной: PID освободившегося процесса может быть переиспользован системой
    для совсем другой программы. ОС же снимает блокировку сама при завершении
    процесса-владельца, в том числе аварийном, так что отдельная логика
    "жив ли процесс" не нужна.

    Возвращает открытый файловый объект при успехе — его нужно сохранить в
    переменной на весь жизненный цикл процесса (сборка мусора закрыла бы файл
    и тем самым сняла блокировку раньше времени). Возвращает None, если файл
    уже заблокирован другим процессом.
    """
    # `with open(...)` тут не годится: файл обязан остаться открытым ПОСЛЕ
    # выхода из этой функции (иначе ОС снимет блокировку немедленно).
    lock_file = open(lock_path, "a")  # noqa: SIM115
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    return lock_file


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

    # Держим файловый объект живым до конца main() — до сюда доходит только
    # после блокирующего uvicorn.run(), т.е. на весь жизненный цикл процесса.
    lock_file = _acquire_single_instance_lock(_app_base_dir() / "app.lock")
    if lock_file is None:
        print("Приложение уже запущено — второй экземпляр не может открыть ту же базу данных.")
        sys.exit(1)

    port = _find_free_port(PREFERRED_PORT)

    # Импорт после настройки FINANCE_DB_PATH — AppSettings читает env при создании.
    import uvicorn

    from api import app

    print(f"Finance Calculator: http://{HOST}:{port}")
    threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="info")


if __name__ == "__main__":
    main()
