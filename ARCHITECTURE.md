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
| `bootstrap.py` | `build_kernel(db_path)` — единый источник порядка регистрации |
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

## Слои логики (легаси, не тронуты)

1. **`config.py` / `models.py`** — константы, дефолты, иммутабельные модели,
   Enum'ы, Protocol'ы для DI.
2. **`database.py`** — единственный модуль, знающий про SQL. Схема, аддитивные
   миграции, CRUD → `TypedDict`. (Одно аддитивное изменение: `get_settings_bundle`.)
3. **`calculator.py`** — чистая бизнес-логика (зарплата, баланс, триггеры ДР).
4. **`prod_calendar.py`** — производственный календарь РФ (`work-calendar` +
   декоратор ручных поправок + опциональный парсер PDF).

## Точка входа и пути

`paths.py` — единственный резолвер путей. Frozen: всё рядом с `.exe`. Из
исходников — корень репозитория.

`main.py` → настраивает логи, при frozen завершает отложенное обновление,
`build_kernel()` → `run_app(kernel)`.

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
