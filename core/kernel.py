"""
Ядро системы - центральный компонент для взаимодействия модулей.
Все модули общаются только через ядро, никогда напрямую друг с другом.

Архитектура:
- Ядро (Kernel) управляет всеми модулями
- Модуль cache_manager управляет кэшированием
- Модуль db_kernel управляет всеми операциями с БД
- Модуль updater проверяет обновления и скачивает новые версии
- Никакие модули не работают с БД напрямую, только через db_kernel

Best Practices:
- Singleton паттерн с потокобезопасной реализацией
- Type hints для всех методов
- Использование timezone-aware datetime
- Строгая инкапсуляция
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING
from threading import Lock, RLock
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import uuid

if TYPE_CHECKING:
    from core.modules.cache import CacheManager
    from modules.db_kernel.db_kernel import DBKernel
    from modules.updater.updater import UpdaterModule

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Сообщение для передачи между модулями через ядро.
    
    Attributes:
        source: Имя модуля-отправителя
        target: Имя модуля-получателя
        action: Действие, которое нужно выполнить
        payload: Данные для передачи
        message_id: Уникальный идентификатор сообщения
        timestamp: Время создания сообщения (timezone-aware)
    """
    source: str
    target: str
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация сообщения в словарь."""
        return {
            "source": self.source,
            "target": self.target,
            "action": self.action,
            "payload": self.payload,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Message:
        """Создание сообщения из словаря."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        return cls(
            source=data["source"],
            target=data["target"],
            action=data["action"],
            payload=data.get("payload", {}),
            message_id=data.get("message_id", str(uuid.uuid4())),
            timestamp=timestamp
        )


class Kernel:
    """
    Центральное ядро системы.
    
    Архитектура:
    - Все модули регистрируются в ядре
    - Модули общаются только через ядро (посылка сообщений)
    - Ядро управляет кэшем через cache_manager
    - Доступ к БД только через db_kernel модуль
    - Никакие модули не работают с БД напрямую
    
    Best Practices:
    - Singleton с двойной проверкой блокировки (double-checked locking)
    - RLock для рекурсивных вызовов
    - Строгая типизация
    """
    
    _instance: Optional[Kernel] = None
    _lock = RLock()  # Reentrant lock для безопасности
    
    def __new__(cls) -> Kernel:
        """Реализация паттерна Singleton с double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Инициализация ядра."""
        if self._initialized:
            return
        
        self._modules: Dict[str, Any] = {}
        self._cache_module: Optional[CacheManager] = None
        self._db_kernel: Optional[DBKernel] = None
        self._updater_module: Optional[UpdaterModule] = None
        self._message_log: list[Message] = []
        self._max_message_log_size: int = 1000
        self._initialized = True
        logger.info("Ядро создано")
    
    def register_module(self, name: str, module: Any) -> bool:
        """Регистрация модуля в ядре."""
        if name in self._modules:
            logger.warning(f"Модуль {name} уже зарегистрирован")
            return False
        
        self._modules[name] = module
        # Поддержка обоих методов для обратной совместимости
        if hasattr(module, 'set_kernel'):
            module.set_kernel(self)
        elif hasattr(module, 'set_core'):
            module.set_core(self)
        
        logger.info(f"Модуль {name} зарегистрирован")
        
        # Инициализация специальных модулей
        if name == "cache_manager":
            self._cache_module = module
        elif name == "db_kernel":
            self._db_kernel = module
        elif name == "updater":
            self._updater_module = module
            
        return True
    
    def get_module(self, name: str) -> Optional[Any]:
        """Получение модуля по имени."""
        return self._modules.get(name)
    
    def set_cache_module(self, module: Any) -> None:
        """Установка модуля кэша."""
        self._cache_module = module
        # Поддержка обоих методов для обратной совместимости
        if hasattr(module, 'set_kernel'):
            module.set_kernel(self)
        elif hasattr(module, 'set_core'):
            module.set_core(self)
    
    def get_cache_module(self) -> Optional[Any]:
        """Получение модуля кэша."""
        return self._cache_module
    
    def set_db_kernel(self, module: Any) -> None:
        """Установка DB kernel модуля."""
        self._db_kernel = module
        # Поддержка обоих методов для обратной совместимости
        if hasattr(module, 'set_kernel'):
            module.set_kernel(self)
        elif hasattr(module, 'set_core'):
            module.set_core(self)
    
    def get_db_kernel(self) -> Optional[Any]:
        """Получение DB kernel модуля."""
        return self._db_kernel
    
    def send_message(self, message: Message) -> Any:
        """
        Отправка сообщения от одного модуля к другому через ядро.
        
        Маршрутизация:
        - Если target = "cache", используется внутренний кэш менеджер
        - Если target = "db_kernel", используется внутренний DB kernel
        - Иначе сообщение передается зарегистрированному модулю
        """
        logger.debug(f"Сообщение: {message.source} -> {message.target}:{message.action}")
        
        # Обработка специальных модулей
        if message.target == "cache":
            if not self._cache_module:
                raise RuntimeError("Cache manager не инициализирован")
            return self._handle_cache_message(message)
        
        if message.target == "db_kernel":
            if not self._db_kernel:
                raise RuntimeError("DB kernel не инициализирован")
            return self._handle_db_message(message)
        
        # Обычная маршрутизация к модулю
        if message.target not in self._modules:
            raise RuntimeError(f"Модуль {message.target} не найден")
        
        module = self._modules[message.target]
        return self._dispatch_to_module(module, message)
    
    def _handle_cache_message(self, message: Message) -> Any:
        """Обработка сообщений для кэш менеджера."""
        action = message.action
        payload = message.payload
        
        if action == "get":
            return self._cache_module.get(payload.get("key"))
        elif action == "set":
            return self._cache_module.set(
                payload.get("key"), 
                payload.get("value"),
                ttl=payload.get("ttl")
            )
        elif action == "delete":
            return self._cache_module.delete(payload.get("key"))
        elif action == "clear":
            return self._cache_module.clear()
        else:
            raise ValueError(f"Неизвестное действие кэша: {action}")
    
    def _handle_db_message(self, message: Message) -> Any:
        """Обработка сообщений для DB kernel."""
        if not self._db_kernel:
            raise RuntimeError("DB kernel не инициализирован")
            
        action = message.action
        payload = message.payload
        
        if action == "execute":
            return self._db_kernel.execute_query(
                payload.get("query"),
                payload.get("params", {})
            )
        elif action == "transaction":
            return self._db_kernel.execute_transaction(
                payload.get("operations")
            )
        elif action == "migrate":
            return self._db_kernel.run_migrations(
                payload.get("version", "latest")
            )
        elif action == "analytics":
            return self._db_kernel.build_analytics(
                payload.get("type"),
                payload.get("params", {})
            )
        elif action == "build_condition":
            return self._db_kernel.build_condition(
                payload.get("field"),
                payload.get("operator"),
                payload.get("value")
            )
        elif action == "build_query":
            return self._db_kernel.build_query(
                payload.get("table"),
                payload.get("conditions", []),
                payload.get("fields", ["*"])
            )
        else:
            raise ValueError(f"Неизвестное действие БД: {action}")
    
    def _dispatch_to_module(self, module: Any, message: Message) -> Any:
        """Диспетчеризация сообщения к модулю."""
        if not hasattr(module, 'handle_message'):
            raise RuntimeError(f"Модуль не имеет метода handle_message")
        
        return module.handle_message(message)
    
    def request_db(self, operation: str, **kwargs) -> Any:
        """
        Запрос к БД через ядро и модуль db_kernel.
        Никто не работает с БД напрямую.
        """
        if not self._db_kernel:
            raise RuntimeError("DB kernel не инициализирован")
        
        # Проверяем наличие метода с префиксом или без
        operation_func = None
        if hasattr(self._db_kernel, operation):
            operation_func = getattr(self._db_kernel, operation)
        else:
            raise AttributeError(f"DB операция '{operation}' не найдена")
        
        return operation_func(**kwargs)
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Получение данных из кэша через ядро."""
        if not self._cache_module:
            return None
        return self._cache_module.get(key)
    
    def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранение данных в кэш через ядро."""
        if self._cache_module:
            self._cache_module.set(key, value, ttl)
    
    def cache_delete(self, key: str) -> bool:
        """Удаление данных из кэша через ядро."""
        if not self._cache_module:
            return False
        return self._cache_module.delete(key)
    
    def cache_clear(self) -> None:
        """Очистка всего кэша через ядро."""
        if self._cache_module:
            self._cache_module.clear()
    
    def check_update(self) -> Dict[str, Any]:
        """Проверка обновлений через модуль updater."""
        if not self._updater_module:
            return {"available": False, "reason": "Updater module not initialized"}
        
        return self._updater_module.check_for_updates()
    
    def perform_update(self, version: str) -> bool:
        """Выполнение обновления через модуль updater."""
        if not self._updater_module:
            return False
        
        return self._updater_module.update_to_version(version)
    
    def initialize(self):
        """Инициализация ядра и всех зарегистрированных модулей."""
        if self._initialized:
            # Сбрасываем флаг для возможности повторной инициализации в тестах
            pass
        
        logger.info("Инициализация ядра...")
        
        # Инициализация специальных модулей в правильном порядке
        init_order_special = [
            ("cache_manager", self._cache_module),
            ("db_kernel", self._db_kernel),
            ("updater", self._updater_module)
        ]
        
        for module_name, module in init_order_special:
            if module and hasattr(module, 'initialize'):
                logger.info(f"Инициализация модуля {module_name}...")
                module.initialize()
        
        # Инициализация остальных зарегистрированных модулей
        init_order = ["cache_manager", "db_kernel", "updater"]
        
        for module_name in init_order:
            if module_name in self._modules:
                module = self._modules[module_name]
                if hasattr(module, 'initialize'):
                    logger.info(f"Инициализация модуля {module_name}...")
                    module.initialize()
        
        self._initialized = True
        logger.info("Ядро успешно инициализировано")
        return True
    
    def shutdown(self):
        """Корректное завершение работы ядра и модулей."""
        logger.info("Завершение работы ядра...")
        
        for name, module in reversed(list(self._modules.items())):
            if hasattr(module, 'shutdown'):
                try:
                    module.shutdown()
                    logger.info(f"Модуль {name} завершен")
                except Exception as e:
                    logger.error(f"Ошибка при завершении {name}: {e}")
        
        self._modules.clear()
        self._cache_module = None
        self._db_kernel = None
        self._updater_module = None
        self._initialized = False
        
        logger.info("Ядро завершено")
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Глобальный экземпляр ядра
def get_kernel() -> Kernel:
    """Получение глобального экземпляра ядра."""
    return Kernel()


def reset_kernel():
    """Сброс ядра (для тестов)."""
    Kernel._instance = None
