"""
Комплексные тесты для проверки модульной архитектуры через ядро.
Тестируется взаимодействие всех модулей только через Kernel.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.kernel import Kernel, Message, get_kernel, reset_kernel


class TestKernelModuleCommunication:
    """Тесты взаимодействия модулей через ядро."""
    
    def setup_method(self):
        """Сброс ядра перед каждым тестом."""
        reset_kernel()
        self.kernel = get_kernel()
    
    def teardown_method(self):
        """Очистка после теста."""
        reset_kernel()
    
    def test_kernel_singleton(self):
        """Проверка что ядро работает как Singleton."""
        kernel1 = get_kernel()
        kernel2 = get_kernel()
        assert kernel1 is kernel2
    
    def test_register_module(self):
        """Регистрация модуля в ядре."""
        mock_module = Mock()
        result = self.kernel.register_module("test_module", mock_module)
        
        assert result is True
        assert self.kernel.get_module("test_module") is mock_module
    
    def test_register_duplicate_module(self):
        """Попытка регистрации дубликата модуля."""
        mock_module = Mock()
        self.kernel.register_module("test_module", mock_module)
        
        mock_module2 = Mock()
        result = self.kernel.register_module("test_module", mock_module2)
        
        assert result is False
        assert self.kernel.get_module("test_module") is mock_module
    
    def test_send_message_to_module(self):
        """Отправка сообщения модулю через ядро."""
        mock_module = Mock()
        mock_module.handle_message.return_value = {"status": "success"}
        
        self.kernel.register_module("test_module", mock_module)
        
        message = Message(
            source="test_source",
            target="test_module",
            action="test_action",
            payload={"key": "value"}
        )
        
        result = self.kernel.send_message(message)
        
        assert result == {"status": "success"}
        mock_module.handle_message.assert_called_once_with(message)
    
    def test_send_message_to_nonexistent_module(self):
        """Отправка сообщения несуществующему модулю."""
        message = Message(
            source="test_source",
            target="nonexistent_module",
            action="test_action"
        )
        
        with pytest.raises(RuntimeError, match="Модуль nonexistent_module не найден"):
            self.kernel.send_message(message)
    
    def test_message_routing_to_cache(self):
        """Маршрутизация сообщений к кэш модулю."""
        mock_cache = Mock()
        mock_cache.get.return_value = "cached_value"
        
        self.kernel.set_cache_module(mock_cache)
        
        message = Message(
            source="test_source",
            target="cache",
            action="get",
            payload={"key": "test_key"}
        )
        
        result = self.kernel.send_message(message)
        
        assert result == "cached_value"
        mock_cache.get.assert_called_once_with("test_key")
    
    def test_message_routing_to_db_kernel(self):
        """Маршрутизация сообщений к DB kernel модулю."""
        mock_db = Mock()
        mock_db.execute_query.return_value = [{"id": 1, "name": "test"}]
        
        self.kernel.set_db_kernel(mock_db)
        
        message = Message(
            source="test_source",
            target="db_kernel",
            action="execute",
            payload={"query": "SELECT * FROM test", "params": {}}
        )
        
        result = self.kernel.send_message(message)
        
        assert result == [{"id": 1, "name": "test"}]
        mock_db.execute_query.assert_called_once_with("SELECT * FROM test", {})


class TestKernelCacheOperations:
    """Тесты операций кэширования через ядро."""
    
    def setup_method(self):
        reset_kernel()
        self.kernel = get_kernel()
        self.mock_cache = Mock()
        self.kernel.set_cache_module(self.mock_cache)
    
    def teardown_method(self):
        reset_kernel()
    
    def test_cache_get(self):
        """Получение данных из кэша через ядро."""
        self.mock_cache.get.return_value = "test_value"
        
        result = self.kernel.cache_get("test_key")
        
        assert result == "test_value"
        self.mock_cache.get.assert_called_once_with("test_key")
    
    def test_cache_set(self):
        """Сохранение данных в кэш через ядро."""
        self.kernel.cache_set("test_key", "test_value", ttl=300)
        
        self.mock_cache.set.assert_called_once_with("test_key", "test_value", 300)
    
    def test_cache_delete(self):
        """Удаление данных из кэша через ядро."""
        self.mock_cache.delete.return_value = True
        
        result = self.kernel.cache_delete("test_key")
        
        assert result is True
        self.mock_cache.delete.assert_called_once_with("test_key")
    
    def test_cache_clear(self):
        """Очистка всего кэша через ядро."""
        self.kernel.cache_clear()
        
        self.mock_cache.clear.assert_called_once()
    
    def test_cache_get_without_cache_module(self):
        """Получение из кэша без инициализированного модуля."""
        reset_kernel()
        kernel = get_kernel()
        
        result = kernel.cache_get("test_key")
        
        assert result is None


class TestKernelDBOperations:
    """Тесты операций с БД через ядро и db_kernel."""
    
    def setup_method(self):
        reset_kernel()
        self.kernel = get_kernel()
        # Создаем Mock с spec для проверки реальных методов
        self.mock_db = Mock(spec=['execute_query', 'execute_transaction', 'run_migrations', 'build_analytics', 'build_condition'])
        self.kernel.set_db_kernel(self.mock_db)
    
    def teardown_method(self):
        reset_kernel()
    
    def test_request_db_execute(self):
        """Выполнение запроса к БД через ядро."""
        self.mock_db.execute_query.return_value = [{"id": 1}]
        
        result = self.kernel.request_db("execute_query", query="SELECT * FROM test")
        
        assert result == [{"id": 1}]
        self.mock_db.execute_query.assert_called_once_with(query="SELECT * FROM test")
    
    def test_request_db_transaction(self):
        """Выполнение транзакции через ядро."""
        operations = [
            {"type": "insert", "query": "INSERT INTO test VALUES (1)"},
            {"type": "update", "query": "UPDATE test SET val=2"}
        ]
        self.mock_db.execute_transaction.return_value = [{"id": 1}, {"affected_rows": 1}]
        
        result = self.kernel.request_db("execute_transaction", operations=operations)
        
        assert len(result) == 2
        self.mock_db.execute_transaction.assert_called_once_with(operations=operations)
    
    def test_request_db_migrate(self):
        """Запуск миграций через ядро."""
        self.mock_db.run_migrations.return_value = {"success": True, "version": "1.0.0"}
        
        result = self.kernel.request_db("run_migrations", version="1.0.0")
        
        assert result["success"] is True
        self.mock_db.run_migrations.assert_called_once_with(version="1.0.0")
    
    def test_request_db_analytics(self):
        """Построение аналитики через ядро."""
        self.mock_db.build_analytics.return_value = {"count": 100, "avg": 50.5}
        
        result = self.kernel.request_db("build_analytics", analytics_type="summary", params={"table": "sales"})
        
        assert result["count"] == 100
        self.mock_db.build_analytics.assert_called_once_with(analytics_type="summary", params={"table": "sales"})
    
    def test_request_db_build_condition(self):
        """Построение условия запроса через ядро."""
        self.mock_db.build_condition.return_value = {"field": "salary", "operator": ">", "value": 1000}
        
        result = self.kernel.request_db("build_condition", field="salary", operator=">", value=1000)
        
        assert result["field"] == "salary"
        self.mock_db.build_condition.assert_called_once_with(field="salary", operator=">", value=1000)
    
    def test_request_db_without_db_kernel(self):
        """Запрос к БД без инициализированного db_kernel."""
        reset_kernel()
        kernel = get_kernel()
        
        with pytest.raises(RuntimeError, match="DB kernel не инициализирован"):
            kernel.request_db("execute_query", query="SELECT * FROM test")
    
    def test_request_db_unknown_operation(self):
        """Запрос неизвестной операции к БД."""
        with pytest.raises(AttributeError, match="DB операция 'unknown_op' не найдена"):
            self.kernel.request_db("unknown_op", param="value")


class TestKernelUpdateOperations:
    """Тесты операций обновления через ядро."""
    
    def setup_method(self):
        reset_kernel()
        self.kernel = get_kernel()
        self.mock_updater = Mock()
        self.kernel._updater_module = self.mock_updater
    
    def teardown_method(self):
        reset_kernel()
    
    def test_check_update(self):
        """Проверка обновлений через ядро."""
        self.mock_updater.check_for_updates.return_value = {
            "available": True,
            "version": "1.2.0",
            "message": "Доступна новая версия"
        }
        
        result = self.kernel.check_update()
        
        assert result["available"] is True
        assert result["version"] == "1.2.0"
        self.mock_updater.check_for_updates.assert_called_once()
    
    def test_perform_update(self):
        """Выполнение обновления через ядро."""
        self.mock_updater.update_to_version.return_value = True
        
        result = self.kernel.perform_update("1.2.0")
        
        assert result is True
        self.mock_updater.update_to_version.assert_called_once_with("1.2.0")
    
    def test_check_update_without_updater(self):
        """Проверка обновлений без инициализированного updater."""
        reset_kernel()
        kernel = get_kernel()
        
        result = kernel.check_update()
        
        assert result["available"] is False
        assert "not initialized" in result["reason"]


class TestKernelInitialization:
    """Тесты инициализации ядра и модулей."""
    
    def setup_method(self):
        reset_kernel()
    
    def teardown_method(self):
        reset_kernel()
    
    def test_kernel_initialization(self):
        """Инициализация ядра."""
        kernel = get_kernel()
        
        result = kernel.initialize()
        
        assert result is True
        assert kernel.is_initialized is True
    
    def test_kernel_shutdown(self):
        """Завершение работы ядра."""
        kernel = get_kernel()
        kernel.initialize()
        
        mock_module = Mock()
        mock_module.shutdown = Mock()
        kernel.register_module("test_module", mock_module)
        
        kernel.shutdown()
        
        mock_module.shutdown.assert_called_once()
        assert not kernel.is_initialized
    
    def test_kernel_initialization_order(self):
        """Проверка порядка инициализации модулей."""
        kernel = get_kernel()
        
        # Модули должны быть установлены через set_* методы для инициализации
        cache_mock = Mock()
        db_mock = Mock()
        updater_mock = Mock()
        
        kernel.set_cache_module(cache_mock)
        kernel.set_db_kernel(db_mock)
        kernel._updater_module = updater_mock
        
        kernel.initialize()
        
        # Проверяем что initialize был вызван у всех модулей
        cache_mock.initialize.assert_called_once()
        db_mock.initialize.assert_called_once()
        updater_mock.initialize.assert_called_once()


class TestMessageClass:
    """Тесты класса Message."""
    
    def test_message_creation(self):
        """Создание сообщения."""
        message = Message(
            source="module_a",
            target="module_b",
            action="do_something",
            payload={"data": "value"}
        )
        
        assert message.source == "module_a"
        assert message.target == "module_b"
        assert message.action == "do_something"
        assert message.payload == {"data": "value"}
        assert message.message_id is not None  # Теперь message_id генерируется автоматически
        assert isinstance(message.message_id, str)
        assert len(message.message_id) > 0
    
    def test_message_with_id(self):
        """Создание сообщения с ID."""
        message = Message(
            source="module_a",
            target="module_b",
            action="do_something",
            payload={},
            message_id="msg_123"
        )
        
        assert message.message_id == "msg_123"
    
    def test_message_default_payload(self):
        """Сообщение с payload по умолчанию."""
        message = Message(
            source="module_a",
            target="module_b",
            action="do_something"
        )
        
        assert message.payload == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
