"""Обновление приложения из GUI: тихая проверка при старте, *спрашиваем*
перед скачиванием.

Пользователь без доступа к GitHub не должен блокироваться — проверка идёт в
фоне уже после появления окна, любые ошибки глотаются, без явного клика
ничего не скачивается.
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


def _make_updater(current_version: str):
    from updater import AutoUpdater

    return AutoUpdater(current_version=current_version)


async def check_on_start(app) -> None:
    """Тихая фоновая проверка при открытии приложения. Диалог — только при успехе."""
    if not _is_frozen() or "--no-update" in sys.argv:
        return
    try:
        if not app.prefs.get("check_updates_on_start"):
            return
        from updater import _recently_checked

        if _recently_checked():
            return
        await _run_check(app, manual=False)
    except Exception:
        pass


def check_now(app) -> None:
    """Ручная «проверить обновления» — всегда отвечает пользователю."""
    if not _is_frozen():
        app.show_snackbar("Обновление доступно только для собранной версии (.exe).")
        return
    app.page.run_task(_run_check, app, manual=True)


async def _run_check(app, *, manual: bool) -> None:
    from updater import _mark_checked, get_current_version

    current = get_current_version()
    updater = _make_updater(current)
    has_update, version, url = await asyncio.to_thread(updater.check_for_updates)

    if not (updater._rate_limited or not updater._network_reachable):
        _mark_checked()

    if has_update and url:
        if not manual and version and version == app.prefs.get("skipped_update_version"):
            return
        _prompt(app, current, version, url)
        return

    if not manual:
        return

    if updater._rate_limited:
        app.show_snackbar("GitHub временно ограничивает запросы — попробуйте позже.", error=True)
    elif not updater._network_reachable:
        app.show_snackbar("Сервер обновлений недоступен.", error=True)
    elif has_update and not url:
        app.show_snackbar(f"Версия {version} опубликована, но файл ещё не готов.")
    else:
        app.show_snackbar("У вас последняя версия.")


def _prompt(app, current: str, version: str, url: str) -> None:
    page = app.page

    def close():
        page.pop_dialog()

    def later(e):
        close()

    def skip(e):
        app.prefs.update(skipped_update_version=version)
        close()
        app.show_snackbar(f"Версия {version} пропущена.")

    def download(e):
        close()
        page.run_task(_download_and_restart, app, url, version)

    dlg = ft.AlertDialog(
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
                ft.Text(
                    "Скачать и установить сейчас? Приложение перезапустится.",
                    size=12, color=COLORS["text_secondary"],
                ),
            ],
            tight=True, width=380, spacing=2,
        ),
        actions=[
            ft.TextButton("Пропустить", on_click=skip),
            ft.TextButton("Позже", on_click=later),
            ft.FilledButton("Обновить", on_click=download),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)


async def _download_and_restart(app, url: str, version: str) -> None:
    from updater import get_current_version

    page = app.page
    bar = ft.ProgressBar(value=0, bar_height=8)
    status = ft.Text("Скачивание…", size=12, color=COLORS["text_secondary"])
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Установка {version}", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Column([status, ft.Container(height=8), bar], tight=True, width=360, spacing=0),
    )
    page.show_dialog(dlg)

    def on_progress(p):
        try:
            if p.total_bytes:
                bar.value = max(0.0, min(1.0, p.percent / 100))
                status.value = f"{p.percent:.0f}%   {p.formatted_speed}"
            else:
                status.value = f"{p.bytes_downloaded // 1024} КБ"
            page.update()
        except Exception:
            pass

    updater = _make_updater(get_current_version())
    updater.progress_callback = on_progress

    ok = await asyncio.to_thread(updater.download_update, url, version)
    page.pop_dialog()

    if not ok:
        app.show_snackbar("Не удалось установить обновление.", error=True)
        return

    done = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"]),
             ft.Text("Обновление установлено")],
            spacing=8,
        ),
        content=ft.Text("Приложение перезапустится через пару секунд.", size=12),
    )
    page.show_dialog(done)
    await asyncio.sleep(1.5)
    os._exit(0)
