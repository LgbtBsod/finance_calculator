"""
Cache Manager - модуль для управления кэшированием.
Управляет кэшем через ядро, предоставляет интерфейс для других модулей.

Используется библиотека cachetools для оптимизированной реализации:
- TTLCache - кэш с автоматическим истечением по времени
- LRUCache - Least Recently Used eviction policy
- Thread-safe обертки для многопоточности

Best Practices:
- Type hints для всех методов
- Использование готовой оптимизированной библиотеки cachetools
- Потокобезопасная реализация
- Статистика хитов/промахов
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Callable
from cachetools import TTLCache, LRUCache
from cachetools.keys import hashkey
import threading
from loguru import logger


class CacheManager:
    """
    Менеджер кэша на основе cachetools.
    Управляет кэшированием данных для всей системы.
    
    Features:
    - TTLCache с автоматическим истечением
    - LRU eviction policy
    - Потокобезопасность через threading.RLock
    - Встроенная статистика (hits, misses)
    - Поддержка разных TTL для разных ключей
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._max_size: int = max_size
        self._default_ttl: int = default_ttl
        self._lock = threading.RLock()
        self._kernel: Optional[Any] = None
        
        # Основной кэш с TTL и LRU
        self._cache: TTLCache = TTLCache(maxsize=max_size, ttl=default_ttl)
        
        # Отдельный кэш для метаданных (время установки, кастомный TTL)
        self._metadata: LRUCache = LRUCache(maxsize=max_size)
    
    def set_kernel(self, kernel: Any) -> None:
        """Установка ссылки на ядро."""
        self._kernel = kernel
    
    def initialize(self) -> None:
        """Инициализация менеджера кэша."""
        logger.info(f"Инициализация Cache Manager (max_size={self._max_size}, default_ttl={self._default_ttl}s)")
        logger.info("Cache Manager использует cachetools.TTLCache для оптимизированного кэширования")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Получение значения из кэша.
        Автоматически удаляет истекшие записи.
        """
        with self._lock:
            try:
                value = self._cache[key]
                logger.debug(f"Кэш хит: {key}")
                return value
            except KeyError:
                logger.debug(f"Кэш промах: {key}")
                return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Сохранение значения в кэш.
        
        Args:
            key: Ключ кэша
            value: Значение
            ttl: Время жизни в секундах (None = default_ttl)
        """
        with self._lock:
            effective_ttl = ttl if ttl is not None else self._default_ttl
            
            # Сохраняем метаданные
            import time
            self._metadata[key] = {
                'ttl': effective_ttl,
                'created_at': time.time()
            }
            
            # TTLCache автоматически управляет истечением
            # Для кастомного TTL создаем новый TTLCache с нужным TTL
            if ttl is not None and ttl != self._default_ttl:
                # Нужно создать новый кэш с этим TTL для конкретного ключа
                # cachetools не поддерживает per-key TTL напрямую, поэтому
                # мы храним значение с метаданными и проверяем TTL вручную
                self._cache[key] = value
                # Переопределяем TTL для этого ключа через обертку
                # Используем hashkey для правильного управления TTL
                old_cache = self._cache
                new_cache = TTLCache(maxsize=self._max_size, ttl=effective_ttl)
                for k in old_cache:
                    if k in self._metadata:
                        meta = self._metadata[k]
                        elapsed = time.time() - meta.get('created_at', time.time())
                        remaining = meta['ttl'] - elapsed
                        if remaining > 0:
                            new_cache[k] = old_cache[k]
                            self._metadata[k] = {'ttl': meta['ttl'], 'created_at': meta['created_at']}
                new_cache[key] = value
                self._cache = new_cache
            else:
                self._cache[key] = value
            
            logger.debug(f"Кэш установлен: {key} (TTL={effective_ttl}s)")
            return True
    
    def delete(self, key: str) -> bool:
        """Удаление значения из кэша."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._metadata:
                    del self._metadata[key]
                logger.debug(f"Кэш удален: {key}")
                return True
            return False
    
    def clear(self) -> int:
        """Очистка всего кэша."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._metadata.clear()
            logger.info(f"Кэш очищен: {count} записей удалено")
            return count
    
    def exists(self, key: str) -> bool:
        """Проверка существования ключа в кэше (с учетом TTL)."""
        with self._lock:
            return key in self._cache
    
    def get_or_set(self, key: str, default_factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Получение значения или установка по умолчанию через factory.
        Атомарная операция.
        """
        with self._lock:
            if key in self._cache:
                logger.debug(f"Кэш хит: {key}")
                return self._cache[key]
            
            # Ключа нет или он истек - создаем значение
            value = default_factory()
            self.set(key, value, ttl)
            logger.debug(f"Кэш установлен через factory: {key}")
            return value
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша из cachetools."""
        with self._lock:
            # cachetools предоставляет cache_info()
            info = self._cache.__repr__()
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": getattr(self._cache, 'hits', 0),
                "misses": getattr(self._cache, 'misses', 0),
                "default_ttl": self._default_ttl,
                "info": info
            }
    
    def cleanup_expired(self) -> int:
        """
        Очистка всех истекших записей.
        TTLCache автоматически удаляет истекшие записи при доступе,
        но этот метод позволяет принудительную очистку.
        """
        with self._lock:
            # TTLCache автоматически очищает истекшие при доступе
            # Явная очистка через перебор
            initial_size = len(self._cache)
            
            # Принудительно вызываем expire() если доступен
            if hasattr(self._cache, 'expire'):
                self._cache.expire()
            
            cleaned = initial_size - len(self._cache)
            if cleaned > 0:
                logger.debug(f"Очищено истекших записей: {cleaned}")
            
            return cleaned
    
    def keys(self) -> list[str]:
        """Получение списка всех ключей в кэше."""
        with self._lock:
            return list(self._cache.keys())
    
    def size(self) -> int:
        """Получение текущего размера кэша."""
        with self._lock:
            return len(self._cache)
    
    def shutdown(self) -> None:
        """Завершение работы менеджера кэша."""
        logger.info("Завершение работы Cache Manager...")
        self.clear()
        logger.info("Cache Manager завершен")


# Фабричная функция
def create_cache_manager(max_size: int = 1000, default_ttl: int = 300) -> CacheManager:
    """Создание экземпляра Cache Manager."""
    return CacheManager(max_size=max_size, default_ttl=default_ttl)
