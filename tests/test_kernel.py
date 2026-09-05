"""
Модульные тесты для ядра системы (Kernel).
Тестируют регистрацию модулей, маршрутизацию и кэширование.
"""

import pytest

from core.kernel import get_kernel as get_core
from core.kernel import reset_kernel


class TestCore:
    """Тесты для ядра системы."""

    def setup_method(self):
        """Сброс состояния ядра перед каждым тестом."""
        reset_kernel()

    def test_singleton_pattern(self):
        """Тест паттерна Singleton - ядро всегда один экземпляр."""
        core1 = get_core()
        core2 = get_core()
        assert core1 is core2

    def test_register_module(self):
        """Тест регистрации модуля в ядре."""
        core = get_core()

        class MockModule:
            def __init__(self):
                self.core_instance = None

            def set_core(self, core):
                self.core_instance = core

        module = MockModule()
        core.register_module("test_module", module)

        assert core.get_module("test_module") is module
        assert module.core_instance is core

    def test_get_nonexistent_module(self):
        """Тест получения несуществующего модуля."""
        core = get_core()
        assert core.get_module("nonexistent") is None

    def test_execute_operation(self):
        """Тест выполнения операции через ядро."""
        core = get_core()

        class MockModule:
            def __init__(self):
                self.core_instance = None

            def set_core(self, core):
                self.core_instance = core

            def handle_message(self, message):
                if message.action == "add":
                    return message.payload.get("a", 0) + message.payload.get("b", 0)
                return None

        module = MockModule()
        core.register_module("math", module)

        # Используем send_message вместо execute
        from core.kernel import Message

        message = Message(source="test", target="math", action="add", payload={"a": 5, "b": 3})
        result = core.send_message(message)
        assert result == 8

    def test_execute_nonexistent_module(self):
        """Тест выполнения операции несуществующего модуля."""
        core = get_core()

        from core.kernel import Message

        message = Message(source="test", target="nonexistent", action="operation")

        with pytest.raises(RuntimeError, match="Модуль nonexistent не найден"):
            core.send_message(message)

    def test_execute_nonexistent_operation(self):
        """Тест выполнения несуществующей операции."""
        core = get_core()

        class MockModule:
            def __init__(self):
                self.core_instance = None

            def set_core(self, core):
                self.core_instance = core

        module = MockModule()
        core.register_module("test", module)

        from core.kernel import Message

        message = Message(source="test", target="test", action="missing")

        with pytest.raises(RuntimeError, match="не имеет метода handle_message"):
            core.send_message(message)

    def test_set_cache_module(self):
        """Тест установки модуля кэша."""
        core = get_core()

        class MockCacheModule:
            def __init__(self):
                self.core_instance = None

            def set_core(self, core):
                self.core_instance = core

        cache_module = MockCacheModule()
        core.set_cache_module(cache_module)

        assert core.get_cache_module() is cache_module
        assert cache_module.core_instance is core

    def test_set_db_module(self):
        """Тест установки модуля БД."""
        core = get_core()

        class MockDBModule:
            def __init__(self):
                self.core_instance = None

            def set_core(self, core):
                self.core_instance = core

        db_module = MockDBModule()
        core.set_db_kernel(db_module)

        assert core.get_db_kernel() is db_module
        assert db_module.core_instance is core

    def test_request_db_without_module(self):
        """Тест запроса к БД без инициализированного модуля."""
        core = get_core()

        with pytest.raises(RuntimeError, match="DB kernel не инициализирован"):
            core.request_db("query")

    def test_request_db_operation(self):
        """Тест запроса к БД через ядро."""
        core = get_core()

        class MockDBModule:
            def __init__(self):
                self.core_instance = None

            def set_core(self, core):
                self.core_instance = core

            def get_data(self, id: int):
                return {"id": id, "value": f"data_{id}"}

        db_module = MockDBModule()
        core.set_db_kernel(db_module)

        result = core.request_db("get_data", id=42)
        assert result == {"id": 42, "value": "data_42"}

    def test_cache_operations(self):
        """Тест операций кэша через ядро."""
        core = get_core()

        from modules.cache.cache_manager import CacheManager

        cache_module = CacheManager()
        core.set_cache_module(cache_module)

        # Тест записи и чтения
        core.cache_set("key1", "value1")
        assert core.cache_get("key1") == "value1"

        # Тест удаления
        assert core.cache_delete("key1") is True
        assert core.cache_get("key1") is None

        # Тест очистки
        core.cache_set("key2", "value2")
        core.cache_set("key3", "value3")
        core.cache_clear()
        assert core.cache_get("key2") is None
        assert core.cache_get("key3") is None

    def test_cache_with_ttl(self):
        """Тест кэша с TTL."""
        from core.kernel import Kernel

        core = Kernel()

        from modules.cache.cache_manager import CacheManager

        cache_module = CacheManager(max_size=100, default_ttl=300)
        core.set_cache_module(cache_module)

        core.cache_set("temp_key", "temp_value", ttl=1)
        assert core.cache_get("temp_key") == "temp_value"

        import time

        time.sleep(1.1)  # Ждём истечения TTL

        assert core.cache_get("temp_key") is None


class TestModuleIsolation:
    """Тесты изоляции модулей - модули не должны общаться напрямую."""

    def setup_method(self):
        """Сброс состояния ядра."""
        reset_kernel()

    def test_modules_communicate_only_through_core(self):
        """Тест что модули общаются только через ядро."""
        core = get_core()

        # Создаем модули которые НЕ имеют прямых ссылок друг на друга
        class ModuleA:
            def __init__(self):
                self.core = None

            def set_core(self, core):
                self.core = core

            def handle_message(self, message):
                # Модуль A запрашивает данные у модуля B ТОЛЬКО через ядро
                from core.kernel import Message

                result = self.core.send_message(
                    Message(
                        source="module_a",
                        target="module_b",
                        action="process",
                        payload={"value": message.payload.get("value")},
                    )
                )
                return result * 2

        class ModuleB:
            def __init__(self):
                self.core = None
                self.module_a_ref = None  # ПРЯМАЯ ссылка запрещена!

            def set_core(self, core):
                self.core = core

            def handle_message(self, message):
                if message.action == "process":
                    return message.payload.get("value", 0) + 10
                return None

        module_a = ModuleA()
        module_b = ModuleB()

        core.register_module("module_a", module_a)
        core.register_module("module_b", module_b)

        # Модуль A вызывает операцию модуля B через ядро
        from core.kernel import Message

        message = Message(
            source="test", target="module_a", action="operation_a", payload={"value": 5}
        )
        result = core.send_message(message)
        assert result == 30  # (5 + 10) * 2

        # Проверяем что у модулей нет прямых ссылок друг на друга
        assert module_b.module_a_ref is None
