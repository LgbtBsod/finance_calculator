"""
Тесты для Flet UI приложения.

Best Practices:
- Изоляция тестов через моки
- Проверка создания компонентов
- Тестирование навигации
"""

from __future__ import annotations
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Добавляем путь к модулю flet_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))


class TestFletAppCreation:
    """Тесты создания Flet приложения."""
    
    def test_app_creation_without_kernel(self):
        """Создание приложения без ядра."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        
        assert app is not None
        assert app._kernel is None
        assert app._current_page == "dashboard"
    
    def test_app_creation_with_kernel(self):
        """Создание приложения с ядром."""
        from frontend.flet_app.app import FinanceApp
        
        mock_kernel = Mock()
        app = FinanceApp(kernel=mock_kernel)
        
        assert app is not None
        assert app._kernel is mock_kernel
    
    def test_create_app_factory(self):
        """Тест фабричной функции."""
        from frontend.flet_app.app import create_app, FinanceApp
        
        app = create_app()
        
        assert isinstance(app, FinanceApp)
        assert app._kernel is None
    
    def test_create_app_factory_with_kernel(self):
        """Тест фабричной функции с ядром."""
        from frontend.flet_app.app import create_app
        
        mock_kernel = Mock()
        app = create_app(kernel=mock_kernel)
        
        assert app is not None
        assert app._kernel is mock_kernel


class TestFletAppBuild:
    """Тесты построения UI."""
    
    @patch('flet.Column')
    @patch('flet.Row')
    @patch('flet.NavigationRail')
    def test_build_method(self, mock_rail, mock_row, mock_column):
        """Тест метода build."""
        from frontend.flet_app.app import FinanceApp
        
        # Мокируем возвращаемые значения
        mock_rail_instance = Mock()
        mock_rail.return_value = mock_rail_instance
        
        mock_row_instance = Mock()
        mock_row.return_value = mock_row_instance
        
        mock_column_instance = Mock()
        mock_column.return_value = mock_column_instance
        
        app = FinanceApp()
        result = app.build()
        
        # Проверяем что NavigationRail был создан
        assert mock_rail.called
        # Проверяем что был создан Column
        assert mock_column.called


class TestFletAppNavigation:
    """Тесты навигации."""
    
    def test_nav_change_to_dashboard(self):
        """Переключение на дашборд."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        app._content_area = Mock()
        app._content_area.content = Mock()
        app.update = Mock()
        
        # Создаем мок события
        mock_event = Mock()
        mock_event.control.selected_index = 0
        
        app._on_nav_change(mock_event)
        
        assert app._current_page == "dashboard"
        assert app.update.called
    
    def test_nav_change_to_balance(self):
        """Переключение на баланс."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        app._content_area = Mock()
        app._content_area.content = Mock()
        app.update = Mock()
        
        mock_event = Mock()
        mock_event.control.selected_index = 1
        
        app._on_nav_change(mock_event)
        
        assert app._current_page == "balance"
    
    def test_nav_change_to_expenses(self):
        """Переключение на расходы."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        app._content_area = Mock()
        app._content_area.content = Mock()
        app.update = Mock()
        
        mock_event = Mock()
        mock_event.control.selected_index = 2
        
        app._on_nav_change(mock_event)
        
        assert app._current_page == "expenses"
    
    def test_nav_change_to_calendar(self):
        """Переключение на календарь."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        app._content_area = Mock()
        app._content_area.content = Mock()
        app.update = Mock()
        
        mock_event = Mock()
        mock_event.control.selected_index = 3
        
        app._on_nav_change(mock_event)
        
        assert app._current_page == "calendar"
    
    def test_nav_change_to_settings(self):
        """Переключение на настройки."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        app._content_area = Mock()
        app._content_area.content = Mock()
        app.update = Mock()
        
        mock_event = Mock()
        mock_event.control.selected_index = 4
        
        app._on_nav_change(mock_event)
        
        assert app._current_page == "settings"
    
    def test_nav_change_invalid_index(self):
        """Обработка невалидного индекса."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        app._content_area = Mock()
        app._content_area.content = Mock()
        app.update = Mock()
        
        mock_event = Mock()
        mock_event.control.selected_index = 99
        
        app._on_nav_change(mock_event)
        
        # Страница не должна измениться при невалидном индексе
        assert app._current_page == "dashboard"


class TestFletAppPages:
    """Тесты страниц приложения."""
    
    def test_build_dashboard(self):
        """Построение дашборда."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        dashboard = app._build_dashboard()
        
        assert dashboard is not None
    
    def test_build_balance_page(self):
        """Построение страницы баланса."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        balance_page = app._build_balance_page()
        
        assert balance_page is not None
    
    def test_build_expenses_page(self):
        """Построение страницы расходов."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        expenses_page = app._build_expenses_page()
        
        assert expenses_page is not None
    
    def test_build_calendar_page(self):
        """Построение страницы календаря."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        calendar_page = app._build_calendar_page()
        
        assert calendar_page is not None
    
    def test_build_settings_page(self):
        """Построение страницы настроек."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        settings_page = app._build_settings_page()
        
        assert settings_page is not None
    
    def test_build_summary_card(self):
        """Построение карточки сводки."""
        from frontend.flet_app.app import FinanceApp
        
        app = FinanceApp()
        card = app._build_summary_card("Тест", "100 ₽", "blue")
        
        assert card is not None


class TestFletAppMain:
    """Тесты точки входа."""
    
    @patch('flet.app')
    def test_main_function(self, mock_flet_app):
        """Тест функции main."""
        from frontend.flet_app.app import main
        
        mock_page = Mock()
        main(mock_page)
        
        assert mock_page.title == "Финансовый Менеджер"
        assert mock_page.add.called
