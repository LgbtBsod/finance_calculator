"""
Модульные тесты для модуля кэша (CacheModule).
"""

import pytest
import time
from core.modules.cache import CacheModule, CacheEntry


class TestCacheEntry:
    """Тесты для элемента кэша."""
    
    def test_create_entry_without_ttl(self):
        """Тест создания записи без TTL."""
        entry = CacheEntry('value')
        assert entry.value == 'value'
        assert entry.ttl is None
        assert entry.is_expired() is False
    
    def test_create_entry_with_ttl(self):
        """Тест создания записи с TTL."""
        entry = CacheEntry('value', ttl=10)
        assert entry.value == 'value'
        assert entry.ttl == 10
        assert entry.is_expired() is False
    
    def test_entry_expiration(self):
        """Тест истечения срока жизни записи."""
        entry = CacheEntry('value', ttl=1)
        assert entry.is_expired() is False
        
        time.sleep(1.1)
        
        assert entry.is_expired() is True


class TestCacheModule:
    """Тесты для модуля кэша."""
    
    def setup_method(self):
        """Создание нового экземпляра кэша перед каждым тестом."""
        self.cache = CacheModule(default_ttl=300)
    
    def test_set_and_get(self):
        """Тест установки и получения значения."""
        self.cache.set('key1', 'value1')
        assert self.cache.get('key1') == 'value1'
    
    def test_get_nonexistent_key(self):
        """Тест получения несуществующего ключа."""
        assert self.cache.get('nonexistent') is None
    
    def test_delete_existing_key(self):
        """Тест удаления существующего ключа."""
        self.cache.set('key1', 'value1')
        assert self.cache.delete('key1') is True
        assert self.cache.get('key1') is None
    
    def test_delete_nonexistent_key(self):
        """Тест удаления несуществующего ключа."""
        assert self.cache.delete('nonexistent') is False
    
    def test_clear_cache(self):
        """Тест очистки всего кэша."""
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        self.cache.set('key3', 'value3')
        
        self.cache.clear()
        
        assert self.cache.get('key1') is None
        assert self.cache.get('key2') is None
        assert self.cache.get('key3') is None
    
    def test_exists_method(self):
        """Тест проверки существования ключа."""
        self.cache.set('key1', 'value1')
        
        assert self.cache.exists('key1') is True
        assert self.cache.exists('nonexistent') is False
    
    def test_exists_with_expired_entry(self):
        """Тест проверки существования с просроченной записью."""
        self.cache.set('temp_key', 'temp_value', ttl=1)
        assert self.cache.exists('temp_key') is True
        
        time.sleep(1.1)
        
        assert self.cache.exists('temp_key') is False
    
    def test_get_or_set_when_key_exists(self):
        """Тест get_or_set когда ключ существует."""
        self.cache.set('key1', 'existing_value')
        
        call_count = [0]
        def default_func():
            call_count[0] += 1
            return 'default_value'
        
        result = self.cache.get_or_set('key1', default_func)
        
        assert result == 'existing_value'
        assert call_count[0] == 0  # Функция не вызывалась
    
    def test_get_or_set_when_key_not_exists(self):
        """Тест get_or_set когда ключ не существует."""
        call_count = [0]
        def default_func():
            call_count[0] += 1
            return 'computed_value'
        
        result = self.cache.get_or_set('new_key', default_func)
        
        assert result == 'computed_value'
        assert call_count[0] == 1  # Функция вызвана один раз
        assert self.cache.get('new_key') == 'computed_value'  # Значение сохранено
    
    def test_ttl_expiration(self):
        """Тест истечения TTL для записи."""
        self.cache.set('temp_key', 'temp_value', ttl=1)
        assert self.cache.get('temp_key') == 'temp_value'
        
        time.sleep(1.1)
        
        assert self.cache.get('temp_key') is None
    
    def test_default_ttl(self):
        """Тест TTL по умолчанию."""
        cache_short = CacheModule(default_ttl=1)
        cache_short.set('key', 'value')
        
        assert cache_short.get('key') == 'value'
        
        time.sleep(1.1)
        
        assert cache_short.get('key') is None
    
    def test_cleanup_expired(self):
        """Тест очистки просроченных записей."""
        self.cache.set('key1', 'value1', ttl=1)
        self.cache.set('key2', 'value2', ttl=100)
        self.cache.set('key3', 'value3', ttl=1)
        
        time.sleep(1.1)
        
        removed_count = self.cache.cleanup_expired()
        
        assert removed_count == 2
        assert self.cache.get('key1') is None
        assert self.cache.get('key2') == 'value2'
        assert self.cache.get('key3') is None
    
    def test_stats(self):
        """Тест статистики кэша."""
        self.cache.set('key1', 'value1', ttl=1)
        self.cache.set('key2', 'value2', ttl=100)
        self.cache.set('key3', 'value3', ttl=100)
        
        time.sleep(1.1)
        
        stats = self.cache.stats()
        
        assert stats['total_entries'] == 3
        assert stats['expired_entries'] == 1
        assert stats['active_entries'] == 2
    
    def test_thread_safety(self):
        """Тест потокобезопасности."""
        import threading
        
        results = []
        
        def worker(thread_id):
            for i in range(100):
                key = f'key_{thread_id}_{i}'
                self.cache.set(key, f'value_{i}')
                results.append(self.cache.get(key))
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Все записи должны быть корректными
        assert len(results) == 500
        assert all(r is not None for r in results)
    
    def test_custom_ttl_overrides_default(self):
        """Тест что индивидуальный TTL переопределяет default."""
        cache = CacheModule(default_ttl=100)
        
        cache.set('key', 'value', ttl=1)
        assert cache.get('key') == 'value'
        
        time.sleep(1.1)
        
        assert cache.get('key') is None  # Использовался индивидуальный TTL
    
    def test_none_value(self):
        """Тест хранения None значения."""
        self.cache.set('none_key', None)
        # None возвращается как при отсутствии ключа, так и при хранении None
        # Это ожидаемое поведение
        assert self.cache.get('none_key') is None
    
    def test_complex_objects(self):
        """Тест хранения сложных объектов."""
        complex_obj = {
            'id': 1,
            'name': 'Test',
            'nested': {'a': 1, 'b': 2},
            'list': [1, 2, 3]
        }
        
        self.cache.set('complex', complex_obj)
        retrieved = self.cache.get('complex')
        
        assert retrieved == complex_obj
        assert retrieved['nested']['a'] == 1
        assert retrieved['list'][2] == 3
