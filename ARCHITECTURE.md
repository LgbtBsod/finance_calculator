# Архитектура

## Модульная архитектура через ядро

Приложение построено на **ядре (Kernel) и модулях**. Модули общаются
**только через ядро** — не импортируют пакеты друг друга и не держат ссылок
друг на друга.

```
                     ┌──────────────────────────────┐
                     │        gui/ (Flet)           │
                     │   app.py · views/*.py        │
                     └──────────────┬───────────────┘
                                    │ FinanceService (фасад, KernelView 'gui')
                     ┌──────────────▼───────────────┐
                     │            Kernel            │
                     │  request(target,action,**p)  │   emit / subscribe
                     └──┬───┬────┬────┬────┬────┬────┘
              ┌─────────┘   │    │    │    │    │
        ┌─────▼────┐ ┌──────▼┐ ┌─▼───┐ ┌──▼──┐ ┌▼────────┐ ┌─────────┐ ┌────────┐
        │   db     │ │ cache │ │ cal │ │calc │ │birthdays│ │ finance │ │updater │
        │(SQLite)  │ │(TTL)  │ │endar│ │ulat.│ │         │ │(агрег.) │ │        │
        └────┬─────┘ └───────┘ └──┬──┘ └──┬──┘ └────┬────┘ └────┬────┘ └───┬────┘
        database.py         prod_calendar  calculator.py             updater.py
        (легаси, нетронутая — kernel-agnostic)
```

### Правила изоляции (проверяются `tests/test_architecture.py` — AST-анализ)

- ни один `modules/<X>` не импортирует `modules/<Y>`;
- `modules/<X>` импортирует только: свой пакет, stdlib/third-party, `core.*`,
  `models`, `config`, `paths`, и **свой** легаси-модуль (`modules/db` → `database`,
  `modules/calendar` → `prod_calendar`, `modules/{calculator,birthdays}` → `calculator`,
  `modules/updater` → `updater`);
- `services.py` (фасад) импортирует только `core.*` + stdlib;
- легаси `database.py` / `calculator.py` / `prod_calendar.py` / `models.py` /
  `config.py` не импортируют `core` / `modules` — остаются kernel-free, их
  прямые юнит-тесты не тронуты;
- `kernel.get_module()` / `kernel._modules` — только в `tests/` и `core/`.

### Ядро (`core/`)

| Файл | Что |
|------|-----|
| `kernel.py` | `Kernel` (явный экземпляр, НЕ singleton) + `KernelView` — узкий фасад, который получает модуль: `request` / `emit` / `subscribe` / `log`, **без `get_module`** |
| `module.py` | `Module` — база: `name`, `requires`, таблица `_actions`, `handle()` |
| `messages.py` | `Message` / `Event` (frozen dataclass) |
| `errors.py` | `KernelError`, `UnknownActionError`, `PayloadError`, `UserFacingError`/`ValidationError` |
| `_validate.py` | проверка «плоских данных»: в payload запроса и данных события — только `str/int/float/bool/None/date/Decimal/list/dict/frozen dataclass`. `callable` и объекты → `PayloadError` (механически запрещает утечку ссылок между модулями) |
| `bootstrap.py` | `build_kernel(db_path)` — регистрация модулей; порядок init/shutdown ядро выводит топосортом по `requires` (`Kernel._topo_order`), не по порядку регистрации |
| `projection.py` | чистый прогноз погашения долга |
| `validation.py` | валидация ввода (бросает `ValidationError`) |

### Два канала

- **`request(target, action, **payload) -> Any`** — синхронный вызов; ядро
  строит `Message`, ставит `source` = имя вызвавшего модуля, зовёт
  `target.handle(action, payload)`. Неизвестный модуль/action → `UnknownModuleError`/
  `UnknownActionError`. Исключение хендлера → `KernelError from e`; **подклассы
  `UserFacingError` пробрасываются нетронутыми** (снекбар GUI).
- **`emit(event, **data)` / `subscribe(event, handler)`** — fire-and-forget.
  События **копятся в очередь** и диспатчатся **после раскрутки верхнеуровневого
  `request()`** — без реентрантности и без `emit` при открытой транзакции БД.
  `db` шлёт `db:changed`(entity=…) после записей; `cache` подписан и чистит
  затронутые неймспейсы.

### Потокобезопасность

Один Kernel и один `FinanceService` делятся между всеми браузер-сессиями Flet,
каждая сессия — в своём потоке. Поэтому:

- **глубина запроса, очередь событий и флаг диспетчеризации — per-thread**
  (`threading.local`): «верхнеуровневый запрос» — свойство стека вызовов
  конкретного потока; общий счётчик терял бы инкременты и подвешивал очередь
  инвалидации кэша;
- реестр модулей и подписчиков — под `RLock` (снапшот подписчиков при диспатче);
- каждый модуль сам потокобезопасен для своего состояния (`CacheModule` — RLock;
  шимы календаря — без состояния);
- `Kernel(strict=True)` (тесты) дополнительно валидирует возвращаемые значения
  хендлеров — ловит модуль, случайно вернувший живой объект.

### Производительность

- `calculator` берёт **снапшот настроек** одним `db:get_settings_bundle` (а не
  ~10 вызовов `get_setting`);
- шим календаря (`modules/calculator/_shims.py`) при первом `classify_day`
  подтягивает классификацию всего года батчем (`calendar:classify_range`);
- `finance` кэширует `balance` / `analytics_*` в модуле `cache`, инвалидация по
  `db:changed`.

### Зарплата — это доход (`income.kind='salary'`)

Оклад НЕ настройка. Строка `income` c `kind='salary'` несёт параметры расчёта
как «подчинённые поля»: `amount` (оклад/мес), `kef`, `split_method`
(proportional / custom_proportions / working_days), `first/second_half_ratio`.
**Несколько окладов = несколько работ**: `SalaryCalculator` берёт все активные
на месяц salary-строки (через `KernelSalaryReader`) и суммирует
аванс/выплату/рабочие дни. `kind='fixed'` — прочий доход, прямо в баланс.
Миграция `_migrate_salary_settings_to_income` разово переносит старый
`base_salary` из settings в строку-зарплату и удаляет ключи.

### Состав баланса (модуль `finance`, `_compute_balance`)

На каждую половину месяца: `аванс/выплата по окладам + отпускные + прочий
доход (income kind='fixed') − расходы − плановый платёж по долгу`. Платёж по
долгу (`debts.monthly_payment`, по `debts.payment_half`) — только за месяцы,
где долг «жив»: от создания до ориентировочного погашения по плановой ставке
(`_debt_payment_active`). Повторяющиеся доходы/расходы проецируются вперёд.
Зарплата с отпуском — по ТК РФ для всех методов: оклад урезается
пропорционально отработанным дням, отпускные — отдельной суммой; граница
половины — по `advance_cutoff_day` (`_day_in_first_half`). НДФЛ: плоская
`taxRate` либо (`taxProgressive`) прогрессивная шкала 2025 — предельный налог
месяца = НДФЛ с дохода нарастающим итогом по этот месяц минус по предыдущий
(`calculator.progressive_ndfl`).

## Слои логики (легаси, не тронуты)

1. **`config.py` / `models.py`** — доменные константы, иммутабельные модели,
   Enum'ы, Protocol'ы. Настройки — **единый источник** `config.SETTINGS`
   (`tuple[SettingSpec]`: camelCase-имя GUI + ключ БД + дефолт + тип); из него
   выведены все три пути: `database._seed_defaults` (seed), `modules/finance`
   `_settings_get` (чтение, строка→тип), `_settings_update` (запись, тип→строка).
   Названия месяцев — SSOT в `config.MONTH_NOMINATIVE` / `MONTH_GENITIVE`
   (кортежи 1..12); словари «слово → номер» и `gui/format` выводятся из них.
2. **`database.py`** — единственный модуль, знающий про SQL. Схема, аддитивные
   миграции, CRUD → `TypedDict`. Аддитивно: `get_settings_bundle`; таблица
   `income` (зеркало `expenses` без групп) и общий с расходами SQL-фрагмент
   `_RECURRING_WHERE` (проекция повторяющихся строк вперёд, DRY); колонки
   `debts.monthly_payment` / `debts.payment_half` + `update_debt`.
   Спроецированная строка повтора помечается `projected=True` (id — оригинала
   из другого месяца) — удалить её нельзя, но сумму можно переопределить на
   один месяц: таблица `period_overrides (kind, row_id, year, month, amount)`,
   `set_period_override` / `clear_period_override`, применяется в
   `get_expenses`/`get_income` поверх проекции (`overridden=True`).
   Удаление обратимо: `snapshot_for_undo(kind, id)` снимает строку (+ платежи
   долга / + оверрайды) до `delete_*`, `restore_from_undo(snapshot)` вставляет
   её обратно 1-в-1 (`INSERT OR IGNORE`, тот же id); GUI — снекбар «Отменить».
3. **`calculator.py`** — чистая бизнес-логика (зарплата, баланс, триггеры ДР).
4. **`prod_calendar.py`** — производственный календарь РФ (`work-calendar` +
   декоратор ручных поправок + опциональный парсер PDF).

## Точка входа и пути

`paths.py` — единственный резолвер путей. Frozen: всё рядом с `.exe`. Из
исходников — корень репозитория. БД пользователя — в подпапке `db/`
(`db/budget.db` + WAL/SHM); `paths.ensure_db_dir()` создаёт её на старте и
однократно переносит БД из старой плоской раскладки (`budget.db` рядом с
приложением). Апдейтер бэкапит/восстанавливает всю `db/` и никогда её не
перезаписывает при обновлении кода (`SKIP_PATTERNS`).

`main.py` → настраивает логи, при frozen завершает отложенное обновление,
`ensure_db_dir()` → `build_kernel()` → `run_app(kernel)`.

`scripts/launch.py` — стартовый скрипт (обновление pip/зависимостей, проверка
обновлений кода, запуск `main.py`). `run.bat` / `run.sh` только вызывают его.

## Обновления

- `modules/updater` — action `check` (без сети-колбэков, rate-limit внутри),
  `current_version`;
- саму загрузку+установку бинарника с живым прогресс-колбэком GUI зовёт у
  `updater.AutoUpdater` напрямую (`gui/update_ui.py`) — это файловая/процессная
  операция, не доменная;
- `updater.py`: discovery через `releases.atom` (без лимита API), бэкап
  `budget.db` перед установкой, откат при ошибке, подмена `.exe` на месте +
  detached-перезапуск.

## Тесты

| Файл | Что |
|------|-----|
| `test_calculator/database/prod_calendar.py` | слои логики (без ядра) |
| `test_kernel.py` | маршрутизация, жизненный цикл, события, валидация payload, изоляция KernelView |
| `test_modules.py` | каждый модуль через ядро |
| `test_architecture.py` | статическая гарантия изоляции (AST) |
| `test_services.py` / `test_integration_e2e.py` | фасад и сквозные сценарии через ядро |
| `test_updater.py` | self-updater (сеть замокана) |
| `test_gui.py` | форматтеры, prefs, тема, «каждое вью строится без исключений» |
