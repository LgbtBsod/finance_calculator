"""
Модуль кэширования.
Управляется ядром, предоставляет возможности кэширования для всех модулей.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from threading import Lock


class CacheEntry:
    """Элемент кэша с TTL."""
    
    def __init__(self, value: Any, ttl: Optional[int] = None):
        self.value = value
        self.created_at = datetime.now()
        self.ttl = ttl  # время жизни в секундах
    
    def is_expired(self) -> bool:
        """Проверка истечения срока жизни."""
        if self.ttl is None:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl)


class CacheModule:
    """
    Модуль кэширования.
    Управляется ядром, предоставляет in-memory кэш с поддержкой TTL.
    """
    
    def __init__(self, default_ttl: int = 300):
        self._core = None
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._default_ttl = default_ttl
    
    def set_core(self, core) -> None:
        """Установка ссылки на ядро."""
        self._core = core
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                del self._cache[key]
                return None
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранение значения в кэш."""
        with self._lock:
            actual_ttl = ttl if ttl is not None else self._default_ttl
            self._cache[key] = CacheEntry(value, actual_ttl)
    
    def delete(self, key: str) -> bool:
        """Удаление значения из кэша."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Очистка всего кэша."""
        with self._lock:
            self._cache.clear()
    
    def exists(self, key: str) -> bool:
        """Проверка существования ключа в кэше."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            
            if entry.is_expired():
                del self._cache[key]
                return False
            
            return True
    
    def get_or_set(self, key: str, default_func, ttl: Optional[int] = None) -> Any:
        """
        Получение значения из кэша или вычисление и сохранение.
        default_func - функция для вычисления значения если ключ не найден.
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = default_func()
        self.set(key, value, ttl)
        return value
    
    def cleanup_expired(self) -> int:
        """Очистка просроченных записей. Возвращает количество удалённых записей."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """Статистика кэша."""
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for entry in self._cache.values() if entry.is_expired())
            return {
                'total_entries': total,
                'expired_entries': expired,
                'active_entries': total - expired
            }
