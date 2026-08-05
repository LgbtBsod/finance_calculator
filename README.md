# Личный финансовый калькулятор

Python + Streamlit + SQLite приложение для учёта личных финансов с расчётом зарплаты по производственному календарю РФ.

## Стек

| Компонент | Технология |
|-----------|----------|
| UI | Streamlit |
| БД | SQLite (WAL) |
| Календарь | `work-calendar` (данные с consultant.ru) |
| Обработка | Pandas |

## Архитектура

```
models.py          — frozen dataclasses, Enum (0 логики)
config.py          — Константы, дефолты
prod_calendar.py   — CalendarProvider (ABC) + Strategy + Decorator
database.py        — DatabaseManager (единый модуль с SQL)
calculator.py      — SalaryCalculator + BirthdayService
app.py             — Streamlit UI (точка входа)
```

## Возможности

- 📊 **Баланс и ЗП**: расчёт аванса/получки с учётом производственного календаря, отпускных
- 💸 **Расходы**: добавление, удаление, повторяющиеся расходы
- 🎂 **Дни рождения**: триггер за 14 дней, авто-создание расходов
- 📝 **Памятка**: свободные расходы (не влияют на баланс)
- 📈 **Визуализация**: графики ЗП, расходов, остатков

## Установка и запуск

### Linux / macOS

```bash
cd finance-calculator
pip install -r requirements.txt
streamlit run app.py
```

### Windows

Двойной клик на `run.bat`, или:

```cmd
pip install -r requirements.txt
streamlit run app.py
```

## Настройки

Все настройки хранятся в SQLite (`budget.db`). При первом запуске применяются стандартные значения:

| Параметр | Значение |
|----------|---------|
| Оклад | 100 000 ₽ |
| НДФЛ | 13% |
| КЭФ | 1.0 |
| День отсечки аванса | 15 |
| Учитывать сокращённые дни | Нет |

## Производственный календарь

Используется библиотека `work-calendar` с данными с consultant.ru. Покрыты годы 2015–2026+. Все правительственные переносы выходных дней учтены автоматически.

Опционально можно загрузить PDF с consultant.ru для дополнительных лет (требуется `pdfplumber`).

## Python requirements

- Python 3.10+
- streamlit >= 1.30
- pandas >= 2.0
- work-calendar >= 1.1
