"""Базовый класс вью и общие мелочи."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import flet as ft

from ..theme import COLORS
from ..widgets import section_title

if TYPE_CHECKING:
    from ..app import FinanceApp


class View:
    """Каждое вью читает свежие данные при каждом render().

    Локальное состояние (выбранный период, фильтры) хранится в атрибутах
    экземпляра и переживает перестройку, т.к. вью-объекты создаются один раз
    в FinanceApp.main.
    """

    title: str = ""

    def __init__(self, app: FinanceApp) -> None:
        self.app = app
        now = date.today()
        self.month = now.month
        self.year = now.year

    # подклассы переопределяют
    def content(self) -> list[ft.Control]:  # pragma: no cover - интерфейс
        return []

    def render(self) -> ft.Control:
        # Один процесс Flet обслуживает несколько вкладок; тема (общий prefs)
        # могла смениться в другой вкладке — синхронизируемся перед сборкой.
        self.app._ensure_theme()
        children: list[ft.Control] = []
        if self.title:
            children.append(section_title(self.title))
        children.extend(self.content())
        return ft.Column(children, spacing=16, tight=True)

    # ── общие обработчики ─────────────────────────────────────

    @property
    def svc(self):
        return self.app.service

    def reload(self) -> None:
        self.app.rerender()

    def toast(self, msg: str, *, error: bool = False) -> None:
        self.app.show_snackbar(msg, error=error)

    def guard(self, fn, *, ok: str | None = None) -> None:
        """Выполнить мутацию, показать ошибку в снекбаре, перестроить вью."""
        try:
            fn()
        except Exception as exc:  # ValidationError и прочее
            self.toast(str(exc) or "Не удалось выполнить операцию", error=True)
            return
        if ok:
            self.toast(ok)
        self.reload()

    def delete_undoable(self, delete_fn, *, label: str) -> None:
        """Удалить и показать снекбар «Отменить» (delete_fn возвращает
        {"undo": <снимок>} из services.delete_*)."""
        try:
            result = delete_fn()
        except Exception as exc:  # noqa: BLE001
            self.toast(str(exc) or "Не удалось удалить", error=True)
            return
        self.app.show_undo_snackbar(f"{label} удалён", (result or {}).get("undo"))
        self.reload()

    def _set_month(self, e: ft.ControlEvent) -> None:
        self.month = int(e.control.value)
        self.reload()

    def _set_year(self, e: ft.ControlEvent) -> None:
        self.year = int(e.control.value)
        self.reload()


def kv_row(label: str, value: str, *, value_color: str | None = None,
           bold: bool = False) -> ft.Row:
    return ft.Row(
        [
            ft.Text(label, size=12, color=COLORS["text_secondary"]),
            ft.Text(
                value, size=13,
                weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                color=value_color or COLORS["text"],
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
