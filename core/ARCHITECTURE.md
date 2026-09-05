# Модульная архитектура системы

## Обзор

Система реализована с использованием **модульной архитектуры с центральным ядром (Core)**. Все модули общаются друг с другом **только через ядро**, никогда напрямую. Это обеспечивает:

- **Изоляцию модулей** - каждый модуль независим
- **Единую точку управления** - ядро контролирует все взаимодействия
- **Упрощённое тестирование** - модули можно тестировать изолированно
- **Гибкость** - легко добавлять новые модули или заменять существующие

## Компоненты архитектуры

```
┌─────────────────────────────────────────────────────────────┐
│                        API Module                           │
│                    (HTTP интерфейс)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CORE (Ядро системы)                            │
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │   Управление    │         │      Кэш (Cache)        │   │
│  │    модулями     │◄───────►│  ┌───────────────────┐  │   │
│  └────────┬────────┘         │  │  In-memory cache  │  │   │
│           │                  │  │  с TTL поддержкой │  │   │
│           ▼                  │  └───────────────────┘  │   │
│  ┌─────────────────┐         └─────────────────────────┘   │
│  │  DB Access Mod  │                                       │
│  │  ┌───────────┐  │                                       │
│  │  │SQLAlchemy │  │                                       │
│  │  │ ORM/Query │  │                                       │
│  │  └───────────┘  │                                       │
│  └────────┬────────┘                                       │
└───────────┼─────────────────────────────────────────────────┘
            │
            ▼
    ┌───────────────┐
    │  Calculator   │
    │    Module     │
    └───────────────┘
```

## Структура директорий

```
core/
├── kernel.py              # Ядро системы (Core)
├── main.py                # Инициализация и демонстрация
└── modules/
    ├── __init__.py
    ├── db_access/         # Модуль работы с БД
    │   └── __init__.py    # SQLAlchemy + CRUD операции
    ├── cache/             # Модуль кэширования
    │   └── __init__.py    # In-memory кэш с TTL
    ├── calculator/        # Модуль калькулятора зарплаты
    │   └── __init__.py    # Расчёт зарплат, налогов, бонусов
    └── api/               # API модуль
        └── __init__.py    # HTTP endpoints
```

## Детали компонентов

### 1. Ядро (Core/kernel.py)

**Ответственность:**
- Регистрация и управление модулями
- Маршрутизация запросов между модулями
- Управление кэшем
- Доступ к БД только через db_access модуль

**Ключевые методы:**
```python
core.register_module(name, module)     # Регистрация модуля
core.execute(module, operation, **kw)  # Выполнение операции модуля
core.request_db(operation, **kw)       # Запрос к БД
core.cache_set(key, value, ttl)        # Запись в кэш
core.cache_get(key)                    # Чтение из кэша
core.cache_delete(key)                 # Удаление из кэша
```

**Паттерн Singleton:** Ядро всегда существует в единственном экземпляре.

### 2. Модуль БД (modules/db_access/__init__.py)

**Ответственность:**
- Единственный модуль имеющий доступ к БД
- Построение оптимизированных запросов через SQLAlchemy
- CRUD операции для сущностей
- Инвалидация кэша при изменении данных

**Никто не работает с БД напрямую!** Только через этот модуль и ядро.

**Операции:**
```python
db.create_employee(name, position, department, salary, birth_date)
db.get_employee(employee_id)
db.get_all_employees()
db.update_employee(employee_id, **kwargs)
db.delete_employee(employee_id)
db.get_employees_by_department(department)
db.get_employees_by_salary_range(min, max)
db.execute_query(sql_text, params)  # Для сложных запросов
```

### 3. Модуль кэша (modules/cache/__init__.py)

**Ответственность:**
- In-memory кэширование с поддержкой TTL
- Потокобезопасные операции
- Автоматическая очистка просроченных записей
- Статистика использования кэша

**Особенности:**
- TTL (Time To Live) для каждой записи
- Метод `get_or_set` для атомарного чтения/записи
- Thread-safe реализация через Lock

**Операции:**
```python
cache.set(key, value, ttl=None)      # Запись с опциональным TTL
cache.get(key)                       # Чтение (None если нет или истёк)
cache.delete(key)                    # Удаление
cache.exists(key)                    # Проверка существования
cache.get_or_set(key, default_func)  # Получить или вычислить
cache.clear()                        # Очистка всего кэша
cache.stats()                        # Статистика
```

### 4. Модуль калькулятора (modules/calculator/__init__.py)

**Ответственность:**
- Расчёт зарплаты сотрудников
- Расчёт налогов и бонусов
- Анализ зарплат по департаментам
- Фонд оплаты труда

**Важно:** Не обращается к БД напрямую! Получает данные через ядро.

**Операции:**
```python
calc.calculate_salary(employee_id, bonus, tax_rate)
calc.calculate_department_salaries(department, bonus, tax_rate)
calc.calculate_salary_range(min_salary, max_salary, bonus, tax_rate)
calc.get_total_payroll(department)
calc.calculate_bonus_percentage(employee_id, percentage)
```

### 5. API модуль (modules/api/__init__.py)

**Ответственность:**
- Предоставление HTTP интерфейса
- Кэширование ответов
- Валидация и форматирование данных

**Важно:** Не обращается к другим модулям напрямую! Только через ядро.

**Endpoints:**
```python
api.create_employee(...)
api.get_employee(employee_id)
api.get_all_employees()
api.update_employee(employee_id, **kwargs)
api.delete_employee(employee_id)
api.calculate_salary(employee_id, bonus, tax_rate)
api.get_department_salaries(department)
api.get_total_payroll(department)
api.clear_cache()
api.get_cache_stats()
```

## Примеры использования

### Инициализация системы

```python
from core.main import initialize_system

# Инициализация всех модулей
core = initialize_system(db_url="sqlite:///mydb.db")

# Получение доступа к модулям
api = core.get_module('api')
calculator = core.get_module('calculator')
```

### Работа через ядро

```python
from core.kernel import get_core

core = get_core()

# Создание сотрудника через API -> Core -> DB
result = core.execute('api', 'create_employee',
                      name="Иван Иванов",
                      position="Разработчик",
                      salary=150000.0)

# Расчёт зарплаты через Core -> Calculator -> DB
salary = core.execute('calculator', 'calculate_salary',
                      employee_id=1,
                      bonus=20000.0)

# Прямой запрос к БД через Core -> DB
employee = core.request_db('get_employee', employee_id=1)

# Работа с кэшем
core.cache_set('my_key', {'data': 'value'}, ttl=300)
cached = core.cache_get('my_key')
```

### Изоляция модулей

```python
# ПРАВИЛЬНО: Модули общаются через ядро
class CalculatorModule:
    def calculate_salary(self, employee_id):
        # Получаем данные через ядро
        employee = self._core.request_db('get_employee', employee_id=employee_id)
        ...

# НЕПРАВИЛЬНО: Прямое обращение к модулю БД
class CalculatorModule:
    def calculate_salary(self, employee_id):
        # ТАК НЕЛЬЗЯ! Нарушает изоляцию
        employee = db_module.get_employee(employee_id)
        ...
```

## Тестирование

Все модули покрыты модульными тестами:

```bash
# Тесты ядра
pytest tests/test_kernel.py -v

# Тесты кэша
pytest tests/test_cache_module.py -v

# Тесты БД
pytest tests/test_db_access_module.py -v

# Все тесты
pytest tests/ -v
```

**Статистика тестов:**
- `test_kernel.py`: 13 тестов (ядро, изоляция модулей)
- `test_cache_module.py`: 20 тестов (TTL, потокобезопасность, статистика)
- `test_db_access_module.py`: 17 тестов (CRUD, фильтрация, SQLAlchemy)
- **Всего: 201 тест** (включая существующие)

## Преимущества архитектуры

1. **Полная изоляция** - модули не зависят друг от друга
2. **Единая точка отказа** - если ядро работает, система работает
3. **Легкое масштабирование** - можно добавлять новые модули без изменения существующих
4. **Централизованное кэширование** - ядро управляет кэшем для всех модулей
5. **Безопасность БД** - только один модуль имеет доступ к БД
6. **Тестируемость** - каждый модуль можно тестировать изолированно
7. **Заменяемость** - можно заменить реализацию модуля без изменения других частей

## Демонстрация

Запуск демонстрации работы системы:

```bash
python -m core.main
```

Вы увидите:
- Создание сотрудников через цепочку API → Core → DB
- Кэширование запросов
- Расчёт зарплат через Calculator → Core → DB
- Статистику кэша
- Корректную работу всех модулей через ядро
