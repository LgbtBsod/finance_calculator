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
        self._host: ft.Container | None = None

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

        self._host = ft.Container(expand=True, padding=24, bgcolor=COLORS["bg"])
        page.add(
            ft.Row(
                [
                    ft.Container(self._rail, bgcolor=COLORS["surface"]),
                    ft.VerticalDivider(width=1, color=COLORS["border"]),
                    self._host,
                ],
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
        system_dark = getattr(page, "platform_brightness", None) == ft.Brightness.DARK
        theme.apply(mode, system_is_dark=system_dark)
        page.theme = theme.build_theme(dark=False)
        page.dark_theme = theme.build_theme(dark=True)
        page.theme_mode = ft.ThemeMode(mode)
        page.bgcolor = COLORS["bg"]

    def set_theme_mode(self, mode: str) -> None:
        self.prefs.update(theme_mode=mode)
        self._apply_theme()
        if self._host is not None:
            self._host.bgcolor = COLORS["bg"]
        self.rerender()
        self.page.update()

    # ── navigation ───────────────────────────────────────────

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if 0 <= idx < len(_NAV):
            self.navigate(_NAV[idx][0])

    def navigate(self, key: str) -> None:
        self.current_view = key
        view = self._views[key]
        self._host.content = ft.Column(
            [view.render()], expand=True, scroll=ft.ScrollMode.AUTO
        )
        if self._rail is not None:
            self._rail.selected_index = next(
                (i for i, n in enumerate(_NAV) if n[0] == key), 0
            )
        self.page.update()

    def rerender(self) -> None:
        """Перестроить текущее вью с нуля (после мутации данных)."""
        view = self._views[self.current_view]
        self._host.content = ft.Column(
            [view.render()], expand=True, scroll=ft.ScrollMode.AUTO
        )
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
