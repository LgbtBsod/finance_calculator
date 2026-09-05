# Модульная архитектура с ядром - Руководство

## Обзор архитектуры

```
┌─────────────────────────────────────────────────────────┐
│                      Kernel (Ядро)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Cache Manager│  │   DB Kernel  │  │   Updater    │  │
│  │              │  │              │  │   Module     │  │
│  │ - get/set    │  │ - execute    │  │ - check      │  │
│  │ - delete     │  │ - transaction│  │ - update     │  │
│  │ - clear      │  │ - migrate    │  │ - download   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↑ ↓
                    Только через ядро
                          ↑ ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Module A   │  │  Module B   │  │  Module C   │
└─────────────┘  └─────────────┘  └─────────────┘
```

## Принципы

1. **Все модули общаются ТОЛЬКО через ядро**
2. **Никакие модули не работают с БД напрямую** - только через DB Kernel
3. **Кэш управляется централизованно** - через Cache Manager
4. **Обновления через Updater Module** - проверка Git, скачивание, установка

## Структура проекта

```
/workspace/
├── core/
│   └── kernel.py           # Ядро системы
├── modules/
│   ├── db_kernel/
│   │   └── db_kernel.py    # Работа с БД (SQLAlchemy)
│   ├── cache/
│   │   └── cache_manager.py # Управление кэшем
│   └── updater/
│       └── updater.py      # Обновления из Git
├── build/
│   └── builders/
│       └── README.md       # Инструкции по сборке
├── MODULAR_ARCHITECTURE.md # Документация архитектуры
└── GIT_INSTRUCTIONS.md     # Git инструкции
```

## Быстрый старт

```python
from core.kernel import get_kernel, reset_kernel
from modules.db_kernel.db_kernel import create_db_kernel
from modules.cache.cache_manager import create_cache_manager
from modules.updater.updater import create_updater

# Сброс и создание ядра
reset_kernel()
kernel = get_kernel()

# Создание модулей
db_kernel = create_db_kernel("sqlite:///app.db")
cache_manager = create_cache_manager(max_size=1000, default_ttl=300)
updater = create_updater(current_version="1.0.0")

# Регистрация модулей в ядре
kernel.register_module("db_kernel", db_kernel)
kernel.register_module("cache_manager", cache_manager)
kernel.register_module("updater", updater)

# Инициализация всех модулей
kernel.initialize()

# === РАБОТА С КЭШЕМ ===
kernel.cache_set("user_1", {"name": "John", "age": 30}, ttl=300)
user = kernel.cache_get("user_1")
kernel.cache_delete("user_1")
kernel.cache_clear()

# === РАБОТА С БД ===
# Выполнение запроса
result = kernel.request_db(
    "execute_query", query="SELECT * FROM users WHERE id = :id", params={"id": 1}
)

# Транзакция
operations = [
    {
        "type": "insert",
        "query": "INSERT INTO users (name) VALUES (:name)",
        "params": {"name": "Alice"},
    },
    {
        "type": "update",
        "query": "UPDATE users SET name = :name WHERE id = :id",
        "params": {"name": "Bob", "id": 1},
    },
]
kernel.request_db("execute_transaction", operations=operations)

# Миграции
migration_result = kernel.request_db("run_migrations", version="latest")

# Аналитика
analytics = kernel.request_db(
    "build_analytics", analytics_type="summary", params={"table": "users", "field": "age"}
)

# === ПРОВЕРКА ОБНОВЛЕНИЙ ===
update_info = kernel.check_update()
if update_info.get("available"):
    print(
        f"Доступно обновление: {update_info['current_version']} -> {update_info['latest_version']}"
    )
    kernel.perform_update("latest")

# Завершение работы
kernel.shutdown()
```

## API Ядра

### Регистрация модулей

```python
kernel.register_module("module_name", module_instance)
```

### Работа с кэшем

```python
kernel.cache_set(key, value, ttl=None)  # ttl в секундах
kernel.cache_get(key)
kernel.cache_delete(key)
kernel.cache_clear()
```

### Работа с БД

```python
# Прямой запрос
kernel.request_db("execute_query", query="SELECT...", params={})

# Транзакция
kernel.request_db("execute_transaction", operations=[...])

# Миграции
kernel.request_db("run_migrations", version="latest")

# Аналитика
kernel.request_db("build_analytics", analytics_type="summary", params={})

# Построение запросов
builder = kernel.request_db(
    "build_query",
    table="users",
    conditions=[{"field": "id", "operator": ">", "value": 10}],
    fields=["id", "name"],
)
results = builder.execute()
```

### Обновления

```python
kernel.check_update()
kernel.perform_update("latest")  # или конкретную версию
```

## DB Kernel возможности

### Query Builder

```python
builder = db_kernel.build_query(
    table="users",
    conditions=[
        {"field": "age", "operator": ">=", "value": 18},
        {"field": "active", "operator": "=", "value": True},
    ],
    fields=["id", "name", "email"],
)
builder.order_by_field("name", ascending=True)
builder.limit_results(10, offset=0)
results = builder.execute()
```

### Условия

```python
condition = db_kernel.build_condition(field="status", operator="IN", value=["active", "pending"])
```

### Аналитика

Типы аналитики:
- `summary` - сводная статистика (count, avg, min, max, sum)
- `trend` - тренды (в разработке)
- `aggregation` - агрегация (в разработке)

## Cache Manager возможности

- TTL (время жизни) для каждой записи
- LRU eviction при достижении max_size
- Статистика использования
- Автоматическая очистка истекших записей

```python
stats = cache_manager.get_stats()
# {'size': 10, 'max_size': 1000, 'hits': 50, 'misses': 10, 'hit_rate': 83.33}
```

## Updater Module возможности

- Проверка версий на Git
- Семантическое версионирование
- Автоматическое скачивание обновлений
- История обновлений

## Сборка исполняемых файлов

См. `/workspace/build/builders/README.md`

### Windows (EXE)
```bash
pip install pyinstaller sqlalchemy
pyinstaller --onefile --name app core/main.py
```

### macOS
```bash
pip install pyinstaller sqlalchemy
pyinstaller --onefile --name app core/main.py
```

### Ubuntu/Linux
```bash
pip install pyinstaller sqlalchemy
pyinstaller --onefile --name app core/main.py
```

## Git инструкции

См. `/workspace/GIT_INSTRUCTIONS.md`

### Создание релиза
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin --tags
```

### CI/CD
GitHub Actions и GitLab CI конфигурации включены в документацию.

## Тестирование

```python
# Запуск тестов
python -m pytest tests/ -v

# Интеграционный тест
from core.kernel import get_kernel, reset_kernel
from modules.db_kernel.db_kernel import create_db_kernel
from modules.cache.cache_manager import create_cache_manager
from modules.updater.updater import create_updater

reset_kernel()
kernel = get_kernel()
kernel.register_module('db_kernel', create_db_kernel('sqlite:///:memory:'))
kernel.register_module('cache_manager', create_cache_manager())
kernel.register_module('updater', create_updater())
kernel.initialize()

# Тесты...
kernel.shutdown()
```

## Лучшие практики

1. **Всегда используйте ядро** для взаимодействия между модулями
2. **Никогда не обращайтесь к БД напрямую** - только через `kernel.request_db()`
3. **Используйте кэш** для часто запрашиваемых данных
4. **Регулярно проверяйте обновления** через Updater Module
5. **Используйте транзакции** для атомарных операций
6. **Следите за размером кэша** и устанавливайте разумный TTL

## Расширение архитектуры

### Добавление нового модуля

```python
class MyModule:
    def __init__(self):
        self._kernel = None

    def set_kernel(self, kernel):
        self._kernel = kernel

    def initialize(self):
        pass

    def handle_message(self, message):
        # Обработка сообщений от других модулей
        pass

    def shutdown(self):
        pass


# Регистрация
my_module = MyModule()
kernel.register_module("my_module", my_module)
```

### Отправка сообщений между модулями

```python
from core.kernel import Message

message = Message(
    source="module_a", target="module_b", action="do_something", payload={"data": "value"}
)
result = kernel.send_message(message)
```

## Лицензия

MIT License
