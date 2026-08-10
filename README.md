# 🏦 Личный финансовый калькулятор

Простое и эффективное веб-приложение для управления личными финансами.

## 🚀 Быстрый старт

### Windows
```bash
run.bat
```

### Linux/Mac
```bash
./run.sh
```

Приложение откроется автоматически по адресу: **http://localhost:8000**

## 📁 Структура проекта

```
/workspace/
├── api.py              # FastAPI сервер (API + раздача frontend)
├── index.html          # Frontend (HTML + CSS + Vanilla JavaScript)
├── requirements.txt    # Python зависимости
├── run.bat             # Скрипт запуска для Windows
├── run.sh              # Скрипт запуска для Linux/Mac
│
├── config.py           # Конфигурация приложения
├── database.py         # Работа с SQLite БД
├── models.py           # Модели данных
├── calculator.py       # Бизнес-логика расчётов
├── prod_calendar.py    # Производственный календарь
└── budget.db           # База данных SQLite
```

## 🔧 Технологии

- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla HTML/CSS/JavaScript (без сборщиков, без Node.js)
- **Database**: SQLite
- **API**: RESTful

## 📊 Возможности

- 💰 Расчёт зарплаты с учётом налогов и коэффициентов
- 📅 Планирование расходов по группам
- 💳 Управление долгами
- ⚙️ Гибкие настройки
- 🎨 Современный UI с адаптивным дизайном
- ♿ Доступность (a11y) и поддержка клавиатуры

## 🔌 API Endpoints

### Общие
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/health` | GET | Проверка статуса API |
| `/` | GET | Frontend приложение |
| `/docs` | GET | Swagger документация (OpenAPI) |
| `/redoc` | GET | ReDoc документация |

### Настройки
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/settings` | GET | Получить настройки зарплаты |
| `/api/settings` | PUT | Обновить настройки зарплаты |

### Группы расходов
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/expense-groups` | GET | Получить все группы расходов |
| `/api/expense-groups` | POST | Создать группу расходов |
| `/api/expense-groups/{id}` | GET | Получить группу по ID |
| `/api/expense-groups/{id}` | PUT | Обновить группу |
| `/api/expense-groups/{id}` | DELETE | Удалить группу |

### Расходы
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/expense-items` | GET | Получить все расходы (с фильтрацией ?month=&year=) |
| `/api/expense-items` | POST | Создать расход |
| `/api/expense-items/{id}` | GET | Получить расход по ID |
| `/api/expense-items/{id}` | PUT | Обновить расход |
| `/api/expense-items/{id}` | DELETE | Удалить расход |

### Отпускные
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/vacations` | GET | Получить все отпускные |
| `/api/vacations` | POST | Создать отпускные |
| `/api/vacations/{id}` | DELETE | Удалить отпускные |

### Дни рождения
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/birthdays` | GET | Получить все дни рождения |
| `/api/birthdays` | POST | Добавить день рождения |
| `/api/birthdays/{id}` | DELETE | Удалить день рождения |

## 🛠️ Установка зависимостей

```bash
pip install -r requirements.txt
```

## 🎯 Запуск вручную

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

---
**Версия**: 2.1.0  
**Архитектура**: FastAPI + Vanilla JS (No Node.js, No Streamlit)  
**Лицензия**: MIT
