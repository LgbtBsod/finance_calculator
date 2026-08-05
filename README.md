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

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/health` | GET | Проверка статуса API |
| `/api/settings` | GET/PUT | Настройки зарплаты |
| `/api/expense-groups` | GET/POST | Группы расходов |
| `/api/debts` | GET/POST | Долги |
| `/docs` | GET | Swagger документация |

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
