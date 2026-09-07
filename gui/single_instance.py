"""Единственный экземпляр / арбитраж порта для локального Flet web-сервера.

Flet в режиме ``WEB_BROWSER`` — это локальный сервер + вкладка браузера;
закрытие вкладки не останавливает сервер, и события «окно закрыто» нет.
Без арбитража каждый перезапуск плодил бы очередной осиротевший сервер.
Поэтому ``run_app`` один раз при старте вызывает :func:`resolve_port`, и та
безусловно завершает всё, что уже слушает наш порт: в один момент времени
порт держит не больше одного экземпляра. Убиваются только процессы,
опознаваемые как это приложение (``FinanceCalculator.exe`` или Python,
запускающий ``main.py`` / ``finance_calculator``).
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time

_PORT_SCAN_SPAN = 40


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _pids_listening_on(port: int) -> list[int]:
    if sys.platform != "win32":
        return []
    try:
        out = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"Get-NetTCPConnection -LocalPort {port} -State Listen -EA SilentlyContinue "
                "| Select-Object -Expand OwningProcess -Unique",
            ],
            capture_output=True, text=True, timeout=8,
        ).stdout
    except Exception:
        return []
    pids = []
    for line in out.split():
        with contextlib.suppress(ValueError):
            pids.append(int(line.strip()))
    return pids


def _looks_like_our_process(pid: int) -> bool:
    try:
        info = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}';"
                '"$($p.Name)|$($p.CommandLine)"',
            ],
            capture_output=True, text=True, timeout=8,
        ).stdout.lower()
    except Exception:
        info = ""
    return "financecalculator.exe" in info or (
        "python" in info and ("main.py" in info or "finance_calculator" in info)
    )


def _kill_stale_on_port(port: int) -> None:
    me = os.getpid()
    for pid in _pids_listening_on(port):
        if pid == me or not _looks_like_our_process(pid):
            continue
        try:
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    f"Stop-Process -Id {pid} -Force -EA SilentlyContinue",
                ],
                capture_output=True, timeout=8,
            )
            print(f"[single-instance] завершён прежний экземпляр (PID {pid}) на порту {port}")
        except Exception:
            pass


def resolve_port(port: int) -> int:
    """См. докстринг модуля: всегда остаёмся единственным экземпляром на ``port``."""
    if port_is_free(port):
        return port

    _kill_stale_on_port(port)
    for _ in range(15):
        if port_is_free(port):
            return port
        time.sleep(0.2)

    for cand in range(port + 1, port + _PORT_SCAN_SPAN):
        if port_is_free(cand):
            print(f"[single-instance] порт {port} занят, использую {cand}")
            return cand
    return port
