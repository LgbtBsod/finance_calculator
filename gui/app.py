"""Flet-приложение Finance Calculator: тема, навигация, переключение вью."""

from __future__ import annotations

import contextlib
import logging

import flet as ft

from services import FinanceService

from . import theme
from .prefs import Prefs
from .theme import COLORS
from .views.analytics import AnalyticsView
from .views.balance import BalanceView
from .views.birthdays import BirthdaysView
from .views.debts import DebtsView
from .views.expenses import ExpensesView, GroupsView
from .views.income import IncomeView
from .views.settings import SettingsView
from .views.vacations import VacationsView

log = logging.getLogger(__name__)

_NAV: list[tuple[str, str, object, object]] = [
    ("balance", "Баланс", ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, ft.Icons.ACCOUNT_BALANCE_WALLET),
    ("income", "Доходы", ft.Icons.TRENDING_UP_OUTLINED, ft.Icons.TRENDING_UP),
    ("expenses", "Расходы", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG),
    ("groups", "Группы", ft.Icons.FOLDER_OUTLINED, ft.Icons.FOLDER),
    ("vacations", "Отпускные", ft.Icons.BEACH_ACCESS_OUTLINED, ft.Icons.BEACH_ACCESS),
    ("birthdays", "Дни рождения", ft.Icons.CAKE_OUTLINED, ft.Icons.CAKE),
    ("debts", "Долги", ft.Icons.CREDIT_CARD_OUTLINED, ft.Icons.CREDIT_CARD),
    ("analytics", "Аналитика", ft.Icons.INSIGHTS_OUTLINED, ft.Icons.INSIGHTS),
    ("settings", "Настройки", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS),
]


class FinanceApp:
    """Слой данных (service + prefs) общий для всех сессий браузера;
    всё остальное (page, вью) — на сессию."""

    def __init__(self, service: FinanceService, prefs: Prefs | None = None):
        self.service = service
        self.prefs = prefs or _default_prefs()
        self.page: ft.Page | None = None
        self.current_view = "balance"
        self._views: dict[str, object] = {}
        self._rail: ft.NavigationRail | None = None
        self._rail_box: ft.Container | None = None
        self._divider: ft.VerticalDivider | None = None
        self._host: ft.Container | None = None
        self._scroll: ft.Column | None = None
        self._theme_mode: str | None = None

    # ── lifecycle ─────────────────────────────────────────────

    def main(self, page: ft.Page) -> None:
        self.page = page
        page.title = "Финансовый калькулятор"
        page.padding = 0
        self._apply_theme()

        self._views = {
            "balance": BalanceView(self),
            "income": IncomeView(self),
            "expenses": ExpensesView(self),
            "groups": GroupsView(self),
            "vacations": VacationsView(self),
            "birthdays": BirthdaysView(self),
            "debts": DebtsView(self),
            "analytics": AnalyticsView(self),
            "settings": SettingsView(self),
        }

        self._rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=72,
            min_extended_width=180,
            extended=True,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(icon=off, selected_icon=on, label=label)
                for _key, label, off, on in _NAV
            ],
            on_change=self._on_nav_change,
        )

        # Один постоянный прокручиваемый контейнер — при перестройке вью
        # меняем только его .controls, поэтому позиция прокрутки не слетает.
        self._scroll = ft.Column([], expand=True, scroll=ft.ScrollMode.AUTO)
        self._host = ft.Container(self._scroll, expand=True, padding=24, bgcolor=COLORS["bg"])
        self._rail_box = ft.Container(self._rail, bgcolor=COLORS["surface"])
        self._divider = ft.VerticalDivider(width=1, color=COLORS["border"])
        page.add(
            ft.Row(
                [self._rail_box, self._divider, self._host],
                expand=True,
                spacing=0,
            )
        )
        self.navigate("balance")

        try:
            from .update_ui import check_on_start

            page.run_task(check_on_start, self)
        except Exception:
            pass

    # ── theme ─────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        page = self.page
        mode = self.prefs.get("theme_mode") or "system"
        self._theme_mode = mode
        system_dark = getattr(page, "platform_brightness", None) == ft.Brightness.DARK
        theme.apply(mode, system_is_dark=system_dark)
        page.theme = theme.build_theme(dark=False)
        page.dark_theme = theme.build_theme(dark=True)
        page.theme_mode = ft.ThemeMode(mode)
        page.bgcolor = COLORS["bg"]
        # Перекрасить закешированные контейнеры оболочки (рейл/дивайдер/хост)
        # — они строятся один раз и сами тему не подхватывают.
        if self._host is not None:
            self._host.bgcolor = COLORS["bg"]
        if self._rail_box is not None:
            self._rail_box.bgcolor = COLORS["surface"]
        if self._divider is not None:
            self._divider.color = COLORS["border"]

    def _ensure_theme(self) -> None:
        """Пере-применить тему, если общий prefs изменился в другой сессии
        (один процесс Flet обслуживает несколько вкладок браузера)."""
        if (self.prefs.get("theme_mode") or "system") != self._theme_mode:
            self._apply_theme()

    def set_theme_mode(self, mode: str) -> None:
        self.prefs.update(theme_mode=mode)
        self._apply_theme()
        self.rerender()
        self.page.update()

    # ── navigation ───────────────────────────────────────────

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if 0 <= idx < len(_NAV):
            self.navigate(_NAV[idx][0])

    def navigate(self, key: str) -> None:
        self.current_view = key
        # Новый экран — свежий scroll-контейнер, т.е. с самого верха.
        self._scroll = ft.Column(
            [self._views[key].render()], expand=True, scroll=ft.ScrollMode.AUTO
        )
        self._host.content = self._scroll
        if self._rail is not None:
            self._rail.selected_index = next(
                (i for i, n in enumerate(_NAV) if n[0] == key), 0
            )
        self.page.update()

    def rerender(self) -> None:
        """Перестроить текущее вью после мутации данных — позицию прокрутки
        сохраняем (тот же контейнер, меняем только .controls)."""
        self._scroll.controls = [self._views[self.current_view].render()]
        self.page.update()

    # ── helpers ──────────────────────────────────────────────

    def show_snackbar(self, message: str, *, error: bool = False) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message),
                bgcolor=COLORS["danger"] if error else COLORS["success"],
                duration=3000,
            )
        )

    def show_undo_snackbar(self, message: str, snapshot: dict | None) -> None:
        """Снекбар с кнопкой «Отменить» после удаления. Без снимка —
        обычное уведомление."""
        def _undo(_e) -> None:
            try:
                self.service.restore_deleted(snapshot)
            except Exception as exc:  # noqa: BLE001
                self.show_snackbar(f"Не удалось отменить: {exc}", error=True)
                return
            self.rerender()
            self.show_snackbar("Восстановлено")

        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message),
                bgcolor=COLORS["surface_alt"],
                duration=6000,
                action="Отменить" if snapshot else None,
                on_action=_undo if snapshot else None,
            )
        )


def _default_kernel():
    from core.bootstrap import build_kernel
    from paths import db_path

    return build_kernel(str(db_path))


def _default_prefs() -> Prefs:
    from paths import app_dir

    return Prefs(app_dir / "gui_prefs.json")


def run_app(kernel=None, port: int = 8420) -> None:
    """Точка входа Flet-приложения (локальный web-сервер + вкладка браузера).

    ``kernel`` — собранное ядро (из main.py); если не передано, строится здесь.
    """
    from datetime import date

    from .single_instance import resolve_port

    kernel = kernel or _default_kernel()
    service = FinanceService(kernel)
    prefs = _default_prefs()
    with contextlib.suppress(Exception):
        service.ensure_calendar_year(date.today().year)
    port = resolve_port(port)

    def session_main(page: ft.Page) -> None:
        FinanceApp(service=service, prefs=prefs).main(page)

    ft.run(
        session_main,
        view=ft.AppView.WEB_BROWSER,
        port=port,
        web_renderer=ft.WebRenderer.CANVAS_KIT,
    )
