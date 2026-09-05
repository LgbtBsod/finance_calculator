"""
Flet UI приложение для управления финансами.

Best Practices:
- Модульная архитектура с разделением компонентов
- Типизация через type hints
- Взаимодействие с API через ядро
- Responsive дизайн
"""

from __future__ import annotations
import flet as ft
from typing import Optional, Dict, Any, List
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


class FinanceApp(ft.Column):
    """Основное приложение Flet для управления финансами."""
    
    def __init__(self, kernel: Optional[Any] = None):
        super().__init__()
        self._kernel = kernel
        self._current_page: str = "dashboard"
        self._rail: Optional[ft.NavigationRail] = None
        self._content_area: Optional[ft.Container] = None
        self.expand = True
        
    def did_mount(self) -> None:
        """Инициализация при монтировании."""
        logger.info("FinanceApp mounted")
    
    def build(self) -> ft.Column:
        """Построение UI (вызывается Flet)."""
        return self.build_ui()
    
    def build_ui(self) -> ft.Column:
        """Построение UI."""
        # Боковая панель навигации
        self._rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=400,
            group_alignment=-0.95,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.DASHBOARD_OUTLINED,
                    selected_icon=ft.Icons.DASHBOARD,
                    label="Дашборд",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                    selected_icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                    label="Баланс",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.RECEIPT_LONG_OUTLINED,
                    selected_icon=ft.Icons.RECEIPT_LONG,
                    label="Расходы",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    selected_icon=ft.Icons.CALENDAR_MONTH,
                    label="Календарь",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Настройки",
                ),
            ],
            on_change=self._on_nav_change,
        )
        
        # Контент в зависимости от выбранной страницы
        self._content_area = ft.Container(
            content=self._build_dashboard(),
            expand=True,
            padding=20,
        )
        
        self.controls = [
            ft.Row(
                controls=[
                    self._rail,
                    ft.VerticalDivider(width=1),
                    self._content_area,
                ],
                expand=True,
            ),
        ]
        
        return self
    
    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        """Обработка изменения навигации."""
        index = e.control.selected_index
        pages = ["dashboard", "balance", "expenses", "calendar", "settings"]
        
        if 0 <= index < len(pages):
            self._current_page = pages[index]
            page_content = {
                "dashboard": self._build_dashboard(),
                "balance": self._build_balance_page(),
                "expenses": self._build_expenses_page(),
                "calendar": self._build_calendar_page(),
                "settings": self._build_settings_page(),
            }
            
            self._content_area.content = page_content.get(self._current_page, self._build_dashboard())
            self.update()
    
    def _build_dashboard(self) -> ft.Column:
        """Построение дашборда."""
        return ft.Column(
            controls=[
                ft.Text("Дашборд", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row(
                    controls=[
                        self._build_summary_card("Баланс", "0 ₽", "blue"),
                        self._build_summary_card("Расходы", "0 ₽", "red"),
                        self._build_summary_card("Доходы", "0 ₽", "green"),
                    ],
                    spacing=20,
                ),
            ],
            expand=True,
        )
    
    def _build_summary_card(self, title: str, value: str, color: str) -> ft.Card:
        """Создание карточки сводки."""
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(title, size=16, color="grey600"),
                        ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=color),
                    ],
                    spacing=5,
                ),
                padding=20,
                width=200,
            ),
            elevation=2,
        )
    
    def _build_balance_page(self) -> ft.Column:
        """Страница баланса."""
        return ft.Column(
            controls=[
                ft.Text("Баланс", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Здесь будет информация о балансе"),
            ],
            expand=True,
        )
    
    def _build_expenses_page(self) -> ft.Column:
        """Страница расходов."""
        return ft.Column(
            controls=[
                ft.Text("Расходы", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Управление расходами"),
            ],
            expand=True,
        )
    
    def _build_calendar_page(self) -> ft.Column:
        """Страница календаря."""
        return ft.Column(
            controls=[
                ft.Text("Календарь", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Производственный календарь"),
            ],
            expand=True,
        )
    
    def _build_settings_page(self) -> ft.Column:
        """Страница настроек."""
        return ft.Column(
            controls=[
                ft.Text("Настройки", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text("Настройки приложения"),
            ],
            expand=True,
        )


def create_app(kernel: Optional[Any] = None) -> FinanceApp:
    """Фабричная функция для создания приложения."""
    return FinanceApp(kernel=kernel)


def main(page: ft.Page) -> None:
    """Точка входа для Flet приложения."""
    page.title = "Финансовый Менеджер"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    
    app = create_app()
    page.add(app)


if __name__ == "__main__":
    ft.app(target=main)
