"""
Модульная архитектура с ядром.

Архитектура:
============
1. Ядро (Kernel) - центральный компонент для взаимодействия всех модулей
2. Модули общаются ТОЛЬКО через ядро, никогда напрямую
3. DB Kernel - единственный модуль для работы с БД
4. Cache Manager - централизованное управление кэшем
5. Updater - проверка и установка обновлений из Git

Принципы:
=========
- Никакие модули не работают с БД напрямую
- Все запросы к БД идут через DB Kernel
- Кэш управляется централизованно через Cache Manager
- Обновления проверяются и устанавливаются через Updater Module
- SQLAlchemy используется для построения оптимизированных запросов

Структура:
==========
/workspace/
├── core/
│   └── kernel.py          # Ядро системы
├── modules/
│   ├── db_kernel/
│   │   └── db_kernel.py   # Модуль работы с БД
│   ├── cache/
│   │   └── cache_manager.py  # Модуль кэширования
│   └── updater/
│       └── updater.py     # Модуль обновлений
└── build/
    └── builders/          # Скрипты сборки

Использование:
==============

# Инициализация ядра
from core.kernel import get_kernel
from modules.db_kernel.db_kernel import create_db_kernel
from modules.cache.cache_manager import create_cache_manager
from modules.updater.updater import create_updater

kernel = get_kernel()

# Регистрация модулей
db_kernel = create_db_kernel("sqlite:///app.db")
cache_manager = create_cache_manager(max_size=1000, default_ttl=300)
updater = create_updater(current_version="1.0.0")

kernel.register_module("db_kernel", db_kernel)
kernel.register_module("cache_manager", cache_manager)
kernel.register_module("updater", updater)

# Инициализация
kernel.initialize()

# Работа с БД через ядро
result = kernel.request_db("execute_query", 
                          query="SELECT * FROM users WHERE id = :id",
                          params={"id": 1})

# Работа с кэшем через ядро
kernel.cache_set("user_1", {"name": "John"})
user = kernel.cache_get("user_1")

# Проверка обновлений
update_info = kernel.check_update()
if update_info.get("available"):
    kernel.perform_update("latest")

# Завершение работы
kernel.shutdown()
"""

__version__ = "2.0.0"
__author__ = "Modular Architecture Team"
