"""Обновление приложения из GUI.

Проверка новой версии идёт через ядро (модуль updater). Сама загрузка+установка
бинарника с живым прогресс-колбэком — файловая/процессная операция, GUI зовёт
updater.AutoUpdater напрямую (edge-инфраструктура, не доменная операция).

Пользователь без доступа к GitHub не блокируется — проверка в фоне после
появления окна, любые ошибки глотаются, без клика ничего не скачивается.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import flet as ft

from .theme import COLORS

log = logging.getLogger(__name__)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


async def check_on_start(app) -> None:
    if not _is_frozen() or "--no-update" in sys.argv:
        return
    try:
        if not app.prefs.get("check_updates_on_start"):
            return
        await _run_check(app, manual=False)
    except Exception:  # noqa: BLE001
        pass


def check_now(app) -> None:
    if not _is_frozen():
        app.show_snackbar("Обновление доступно только для собранной версии (.exe).")
        return
    app.page.run_task(_run_check, app, manual=True)


async def _run_check(app, *, manual: bool) -> None:
    res = await asyncio.to_thread(app.service.check_updates, force=manual)

    if res.get("skipped"):
        return

    if res["has_update"] and res["url"]:
        version = res["version"]
        if not manual and version and version == app.prefs.get("skipped_update_version"):
            return
        _prompt(app, res["url"], version)
        return

    if not manual:
        return
    if res["rate_limited"]:
        app.show_snackbar("GitHub временно ограничивает запросы — попробуйте позже.", error=True)
    elif not res["reachable"]:
        app.show_snackbar("Сервер обновлений недоступен.", error=True)
    elif res["has_update"]:
        app.show_snackbar(f"Версия {res['version']} опубликована, но файл ещё не готов.")
    else:
        app.show_snackbar("У вас последняя версия.")


def _prompt(app, url: str, version: str) -> None:
    page = app.page
    current = app.service.current_version()

    def close():
        page.pop_dialog()

    def skip(e):
        app.prefs.update(skipped_update_version=version)
        close()
        app.show_snackbar(f"Версия {version} пропущена.")

    def download(e):
        close()
        page.run_task(_download_and_restart, app, url, version)

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.Icons.SYSTEM_UPDATE, color=COLORS["accent"]),
                 ft.Text("Доступно обновление")],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Text(f"Новая версия: {version}", size=14, weight=ft.FontWeight.W_600),
                    ft.Text(f"Текущая версия: {current}", size=12, color=COLORS["text_secondary"]),
                    ft.Container(height=6),
                    ft.Text("Скачать и установить сейчас? Приложение перезапустится.",
                            size=12, color=COLORS["text_secondary"]),
                ],
                tight=True, width=380, spacing=2,
            ),
            actions=[
                ft.TextButton("Пропустить", on_click=skip),
                ft.TextButton("Позже", on_click=lambda e: close()),
                ft.FilledButton("Обновить", on_click=download),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


async def _download_and_restart(app, url: str, version: str) -> None:
    # Прямой вызов движка загрузки — файловая/процессная операция с живым
    # прогресс-колбэком, её нельзя провести через ядро (см. модуль docstring).
    from updater import AutoUpdater

    page = app.page
    bar = ft.ProgressBar(value=0, bar_height=8)
    status = ft.Text("Скачивание…", size=12, color=COLORS["text_secondary"])
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Установка {version}", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Column([status, ft.Container(height=8), bar], tight=True, width=360, spacing=0),
        )
    )

    def on_progress(p):
        try:
            if p.total_bytes:
                bar.value = max(0.0, min(1.0, p.percent / 100))
                status.value = f"{p.percent:.0f}%   {p.formatted_speed}"
            else:
                status.value = f"{p.bytes_downloaded // 1024} КБ"
            page.update()
        except Exception:  # noqa: BLE001
            pass

    updater = AutoUpdater(current_version=app.service.current_version())
    updater.progress_callback = on_progress
    ok = await asyncio.to_thread(updater.download_update, url, version)
    page.pop_dialog()

    if not ok:
        app.show_snackbar("Не удалось установить обновление.", error=True)
        return

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"]),
                 ft.Text("Обновление установлено")],
                spacing=8,
            ),
            content=ft.Text("Приложение перезапустится через пару секунд.", size=12),
        )
    )
    await asyncio.sleep(1.5)
    os._exit(0)
