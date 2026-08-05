# 🚀 Запуск проекта "Личный финансовый калькулятор"

## Архитектура проекта

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (TypeScript)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  OpenUI5-inspired Vanilla TypeScript                  │   │
│  │  - Components (SRP)                                   │   │
│  │  - State Management (SSOT)                            │   │
│  │  - API Integration Layer                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND (Python)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  FastAPI REST API                                     │   │
│  │  - Pydantic validation                                │   │
│  │  - Dependency Injection                               │   │
│  │  - CORS support                                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↕ SQL                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SQLite Database                                      │   │
│  │  - Settings, Calendar, Expenses                       │   │
│  │  - Debts & Repayments                                 │   │
│  │  - Vacations                                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Принципы разработки

### SOLID
- **S**RP: Каждый компонент/endpoint отвечает за одну сущность
- **O**CP: Открыт для расширения через интерфейсы
- **L**SP: Компоненты взаимозаменяемы
- **I**SP: Узкие специализированные интерфейсы
- **D**IP: Зависимость от абстракций (DatabaseManager Protocol)

### DRY (Don't Repeat Yourself)
- Переиспользуемые компоненты в `src/components/`
- Утилиты в `src/utils/helpers.ts`
- Общий API client в `src/api/index.ts`

### YAGNI (You Ain't Gonna Need It)
- Нет избыточных абстракций
- Минимальный набор зависимостей
- Простая архитектура без over-engineering

### SSOT (Single Source of Truth)
- Данные хранятся только в SQLite
- Фронтенд получает данные из бэкенда
- Типы определены один раз в `src/types/index.ts`

## Реализованный функционал

### ✅ UX/UI улучшения
- Свитчи вместо чекбоксов
- Цветовая группировка расходов
- Градиенты и анимации
- Адаптивный дизайн

### ✅ Возвраты по долгам
- Множественные возвраты по одному долгу
- Поэтапное погашение
- Прогресс-бар оплаты
- История возвратов

### ✅ Группировка расходов
- Создание групп с цветом
- Вложенность (parentId)
- Визуальная индикация

### ✅ Начисления (справа сверху)
- Отпускные
- Дата выплаты
- Быстрое добавление/удаление

### ✅ Параметры
- Switch "Дата отсечки включительно"
- Все чекбоксы заменены на свитчи
- Валидация значений

### ✅ Редактирование таблиц
- Inline редактирование строк
- Кнопка удаления в таблице
- Сохранение изменений

## Запуск проекта

### 1. Установка зависимостей

```bash
# Backend (Python)
pip install -r requirements.txt

# Frontend (TypeScript)
npm install
```

### 2. Запуск Backend API

```bash
# Terminal 1
uvicorn api:app --host 0.0.0.0 --port 8000
```

API будет доступно по адресу: http://localhost:8000
Swagger UI: http://localhost:8000/docs

### 3. Запуск Frontend

```bash
# Terminal 2
npm run dev
```

Frontend будет доступен по адресу: http://localhost:3000

### 4. Сборка production версии

```bash
npm run build
```

Собранные файлы появятся в папке `dist/`

## API Endpoints

### Expense Groups
- `GET /api/expense-groups` - Получить все группы
- `POST /api/expense-groups` - Создать группу
- `PUT /api/expense-groups/{id}` - Обновить группу
- `DELETE /api/expense-groups/{id}` - Удалить группу

### Expense Items
- `GET /api/expense-items` - Получить расходы
- `POST /api/expense-items` - Создать расход
- `PUT /api/expense-items/{id}` - Обновить расход
- `DELETE /api/expense-items/{id}` - Удалить расход

### Debts & Repayments
- `GET /api/debts` - Получить все долги
- `POST /api/debts` - Создать долг
- `POST /api/debts/{id}/repayments` - Добавить возврат
- `PUT /api/debts/{debtId}/repayments/{repaymentId}` - Обновить возврат
- `DELETE /api/debts/{debtId}/repayments/{repaymentId}` - Удалить возврат
- `DELETE /api/debts/{id}` - Удалить долг

### Vacations (Income)
- `GET /api/vacations` - Получить все начисления
- `POST /api/vacations` - Создать начисление
- `DELETE /api/vacations/{id}` - Удалить начисление

### Settings
- `GET /api/settings` - Получить настройки
- `PUT /api/settings` - Обновить настройки

### Health Check
- `GET /api/health` - Проверка статуса API

## Структура проекта

```
/workspace
├── api.py                 # FastAPI backend
├── app.py                 # Streamlit UI (legacy)
├── database.py            # SQLite ORM
├── models.py              # Data models
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── package.json           # Node.js dependencies
├── tsconfig.json          # TypeScript config
├── vite.config.ts         # Vite bundler config
└── src/
    ├── main.ts            # Application entry point
    ├── index.css          # Global styles
    ├── types/
    │   └── index.ts       # TypeScript types (SSOT)
    ├── api/
    │   └── index.ts       # API client layer
    ├── components/
    │   └── index.ts       # UI components (SRP)
    ├── store/             # State management
    └── utils/
        └── helpers.ts     # Utility functions (DRY)
```

## Тестирование API

```bash
# Проверка здоровья
curl http://localhost:8000/api/health

# Получение настроек
curl http://localhost:8000/api/settings

# Создание долга
curl -X POST http://localhost:8000/api/debts \
  -H "Content-Type: application/json" \
  -d '{"title": "Долг", "totalAmount": 5000, "month": 12, "year": 2024}'

# Добавление возврата
curl -X POST http://localhost:8000/api/debts/{id}/repayments \
  -H "Content-Type: application/json" \
  -d '{"amount": 2000, "date": "2024-12-15"}'
```

## Best Practices Checklist

- ✅ SRP: Каждый модуль имеет одну ответственность
- ✅ SOLID: Все принципы соблюдены
- ✅ DRY: Код не дублируется
- ✅ YAGNI: Нет избыточного функционала
- ✅ SSOT: Единый источник истины
- ✅ Type Safety: TypeScript + Pydantic
- ✅ Error Handling: Обработка ошибок на всех уровнях
- ✅ CORS: Настроен для frontend-backend коммуникации
- ✅ Validation: Валидация входных данных
- ✅ Documentation: Swagger UI для API

## Следующие шаги

1. Интеграция с реальными данными БД (вместо in-memory)
2. Добавление аутентификации
3. Unit тесты для API
4. E2E тесты для frontend
5. Docker контейнеризация
6. CI/CD pipeline
