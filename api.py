"""api.py — FastAPI REST API для бюджетного калькулятора.

Архитектура:
  - FastAPI приложение с CORS поддержкой
  - RESTful endpoints для всех сущностей
  - Интеграция с SQLite БД через DatabaseManager
  - Валидация данных через Pydantic DTO (SSOT)

Принципы:
  - SRP: каждый endpoint отвечает за одну сущность
  - SSOT: данные хранятся только в SQLite, настройки в pydantic-settings
  - DRY: используем dependency injection и общие DTO
  - SOLID: разделение ответственности между слоями
  - OCP: расширение через добавление новых endpoints без модификации существующих
"""

from __future__ import annotations

import tempfile
import threading
import uuid
from collections.abc import Generator
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from calculator import BirthdayService, SalaryCalculator
from config import get_settings as get_app_settings
from database import DatabaseManager
from prod_calendar import CalendarService

__all__ = ["app"]


# ═══════════════════════════════════════════════════════════════
#  DEPENDENCY INJECTION (SSOT, DRY)
# ═══════════════════════════════════════════════════════════════

# Один DatabaseManager на весь процесс, а не на каждый запрос: раньше
# get_db() создавал новый DatabaseManager (а значит — заново гонял полную
# схему/миграции/сиды настроек, database.py._init_db) на КАЖДЫЙ HTTP-запрос
# ко всем /api/* эндпоинтам. Кэшируем по db_path (в тестах get_db целиком
# подменяется через dependency_overrides, поэтому этот кэш там не участвует
# и никогда не трогает реальный budget.db).
_db_instances: dict[str, DatabaseManager] = {}
# Все /api/* эндпоинты — обычные def (см. историю правок), поэтому FastAPI
# диспетчеризует их в реальный threadpool: несколько запросов могут
# по-настоящему параллельно попасть в check-then-create ниже. Без лока два
# потока одновременно решат, что DatabaseManager ещё не создан, и оба
# запустят DatabaseManager.__init__ -> _init_db -> _migrate_schema, где
# "ALTER TABLE ... ADD COLUMN" не идемпотентен (в SQLite нет ADD COLUMN IF
# NOT EXISTS) — второй вызов упадёт с OperationalError "duplicate column
# name". Двойная проверка (double-checked locking): лок берём только на
# самое первое создание, а не на каждый запрос.
_db_instances_lock = threading.Lock()


def get_db() -> Generator[DatabaseManager, None, None]:
    """Factory для DatabaseManager (DI container) — один экземпляр на путь к БД."""
    settings = get_app_settings()
    if settings.db_path not in _db_instances:
        with _db_instances_lock:
            if settings.db_path not in _db_instances:
                _db_instances[settings.db_path] = DatabaseManager(settings.db_path)
    yield _db_instances[settings.db_path]


def get_calendar_service(db: DatabaseManager = Depends(get_db)) -> CalendarService:
    """Собирает CalendarService поверх текущего соединения с БД (DIP)."""
    return CalendarService(
        get_setting=db.get_setting,
        set_setting=db.set_setting,
        get_corrections=db.get_corrections,
        save_corrections=db.save_corrections,
        clear_calendar_cache=db.clear_calendar_cache,
        calendar_needs_fill=db.calendar_needs_fill,
        save_calendar_data=db.save_calendar_data,
        get_calendar_month=db.get_calendar_month,
    )


def get_salary_calculator(
    db: DatabaseManager = Depends(get_db),
    calendar: CalendarService = Depends(get_calendar_service),
) -> SalaryCalculator:
    """Собирает SalaryCalculator: зависит от Protocol'ов, не от реализаций (DIP)."""
    return SalaryCalculator(
        get_setting=db.get_setting,
        vacations=db,
        calendar_reader=calendar,
    )


def get_birthday_service(db: DatabaseManager = Depends(get_db)) -> BirthdayService:
    return BirthdayService(get_setting=db.get_setting)


# ═══════════════════════════════════════════════════════════════
#  PYDANTIC REQUEST/RESPONSE MODELS (DTO для API)
# ═══════════════════════════════════════════════════════════════


class ExpenseGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    parentId: str | None = None
    # Необязательный месячный лимит расходов по группе — используется
    # аналитикой, чтобы подсветить превышение (см. AnalyticsPage).
    monthlyLimit: float | None = Field(None, gt=0)


class ExpenseGroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    parentId: str | None = None
    sortOrder: int | None = None
    monthlyLimit: float | None = Field(None, gt=0)


class ExpenseGroupResponse(BaseModel):
    id: str
    name: str
    color: str
    parentId: str | None = None
    sortOrder: int = 0
    monthlyLimit: float | None = None


class ExpenseItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., gt=0)
    half: int = Field(..., ge=1, le=2)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2100)
    isRecurring: bool = Field(default=False)
    groupId: str | None = None
    # Необязательное "до какого месяца повторять" — YYYY-MM-DD. Актуально
    # только когда isRecurring=True; для разовых расходов игнорируется.
    recurringUntil: str | None = None


class ExpenseItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    amount: float | None = Field(None, gt=0)
    half: int | None = Field(None, ge=1, le=2)
    isRecurring: bool | None = None
    groupId: str | None = None
    recurringUntil: str | None = None


class ExpenseItemResponse(BaseModel):
    id: str
    groupId: str | None = None
    name: str
    amount: float
    isInclusive: bool = False
    half: int
    isRecurring: bool
    recurringUntil: str | None = None
    month: int
    year: int


class RepaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    date: str
    note: str | None = None


class RepaymentResponse(BaseModel):
    id: str
    debtId: str
    amount: float
    date: str
    note: str | None = None


class DebtCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    totalAmount: float = Field(..., gt=0)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2100)


class DebtResponse(BaseModel):
    id: str
    title: str
    totalAmount: float
    repayments: list[RepaymentResponse] = []
    createdAt: str
    month: int
    year: int
    # Backend — единственный источник правды по остатку долга (считался
    # в SQL и раньше, но терялся при сборке ответа — фронтенду приходилось
    # пересчитывать то же самое из repayments самостоятельно).
    repaidAmount: float = 0.0
    remainingAmount: float = 0.0


class AutoCreateResult(BaseModel):
    created: int


class DebtSettings(BaseModel):
    payoutDay1: int = Field(default=10, ge=1, le=31, description="Первый день выплаты")
    payoutDay2: int = Field(default=25, ge=1, le=31, description="Второй день выплаты")
    moveWeekendToFriday: bool = Field(default=True, description="Переносить выходные на пятницу")


class VacationCreate(BaseModel):
    totalAmount: float = Field(..., gt=0, description="Сумма отпускных")
    payoutDate: str = Field(..., description="Дата выплаты в формате YYYY-MM-DD")
    startDate: str | None = Field(
        None, description="Первый день отпуска (YYYY-MM-DD); по умолчанию = payoutDate"
    )
    endDate: str | None = Field(
        None, description="Последний день отпуска (YYYY-MM-DD); по умолчанию = payoutDate"
    )


class VacationResponse(BaseModel):
    id: str
    totalAmount: float
    payoutDate: str
    startDate: str | None = None
    endDate: str | None = None


class BirthdayCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    birthDate: str = Field(..., description="Дата рождения в формате DD.MM.YYYY")
    giftAmount: float = Field(..., gt=0, le=1000000)


class BirthdayUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    birthDate: str | None = Field(None, description="Дата рождения в формате DD.MM.YYYY")
    giftAmount: float | None = Field(None, gt=0, le=1000000)


class BirthdayResponse(BaseModel):
    id: str
    name: str
    birthDate: str
    giftAmount: float


class SalarySettingsResponse(BaseModel):
    baseSalary: float
    taxRate: float
    kef: float
    advanceCutoffDay: int
    isAdvanceDateInclusive: bool
    accountShortened: bool
    standardHours: int
    payoutDay1: int = 10
    payoutDay2: int = 25
    moveWeekendToFriday: bool = True
    salaryCalculationMethod: str = "proportional"
    firstHalfRatio: float = 0.4
    secondHalfRatio: float = 0.6


class BalanceResponse(BaseModel):
    """Полный расчёт баланса: зарплата + отпускные - расходы, по половинам месяца."""

    month: int
    year: int
    netSalary: float
    advance: float
    payout: float
    vacationHalf1: float
    vacationHalf2: float
    totalAccrued: float
    toPayHalf1: float
    toPayHalf2: float
    expensesHalf1: float
    expensesHalf2: float
    balanceHalf1: float
    balanceHalf2: float
    # Прозрачность расчёта для метода "working_days" — None для остальных.
    calculationMethod: str
    workingDaysHalf1: float | None = None
    workingDaysHalf2: float | None = None
    workingDaysTotal: float | None = None
    advanceCutoffDay: int | None = None
    # Реальные календарные даты выплат (ISO), с переносом на более ранний
    # рабочий день при включённой настройке moveWeekendToFriday.
    payoutDate1: str | None = None
    payoutDate2: str | None = None
    # Номинальные даты (до переноса) — если отличаются от payoutDate*,
    # значит дата была сдвинута из-за выходного/праздника.
    payoutDate1Nominal: str | None = None
    payoutDate2Nominal: str | None = None


class BirthdayAlertResponse(BaseModel):
    name: str
    birthDate: str
    giftAmount: float
    triggerDate: str
    daysUntil: int


class AnalyticsCategory(BaseModel):
    name: str
    amount: float
    color: str
    # groupId=None -> категория "Без группы" — по нему фронтенд ищет лимит
    # (ExpenseGroupResponse.monthlyLimit) для подсветки превышения.
    groupId: str | None = None
    monthlyLimit: float | None = None


class AnalyticsSummaryResponse(BaseModel):
    total: float
    count: int
    categories: list[AnalyticsCategory]


class TrendMonthCategory(BaseModel):
    groupId: str | None = None
    name: str
    color: str
    amount: float


class TrendMonth(BaseModel):
    month: int
    year: int
    total: float
    categories: list[TrendMonthCategory]


class AnalyticsTrendResponse(BaseModel):
    # В хронологическом порядке (старый -> новый) — фронтенду так удобнее
    # рисовать столбцы слева направо, не разворачивая массив самому.
    months: list[TrendMonth]


class SalarySettingsUpdate(BaseModel):
    # Границы зеркалят zod-схему SettingsPage.tsx — та защищает только UI;
    # без этих же Field(...) прямой PUT мимо формы (curl, будущий клиент)
    # мог записать taxRate=500 или отрицательную зарплату без какой-либо
    # проверки на сервере.
    baseSalary: float | None = Field(None, gt=0)
    taxRate: float | None = Field(None, ge=0, le=100)
    kef: float | None = Field(None, gt=0)
    advanceCutoffDay: int | None = Field(None, ge=1, le=31)
    isAdvanceDateInclusive: bool | None = None
    accountShortened: bool | None = None
    standardHours: int | None = Field(None, gt=0)
    payoutDay1: int | None = Field(None, ge=1, le=31)
    payoutDay2: int | None = Field(None, ge=1, le=31)
    moveWeekendToFriday: bool | None = None
    salaryCalculationMethod: str | None = Field(
        None, pattern=r"^(proportional|custom_proportions|working_days)$"
    )
    firstHalfRatio: float | None = Field(None, ge=0, le=1)
    secondHalfRatio: float | None = Field(None, ge=0, le=1)


# ═══════════════════════════════════════════════════════════════
#  FASTAPI APP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="Budget Calculator API",
    description="REST API для личного финансового калькулятора",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# В продакшене frontend и API — один и тот же процесс/порт (main.py
# отдаёт frontend/dist из этого же api.py), там CORS не нужен вовсе —
# same-origin. CORS реально нужен только для dev-сценария (Vite на 5173
# ходит на API на 8000/8420). allow_origins=["*"] + allow_credentials=True
# (как было раньше) — это не безвредный wildcard: Starlette в этом
# сочетании отражает Origin запроса обратно с Access-Control-Allow-Credentials,
# то есть по факту "любой источник с куками/авторизацией". Ни кук, ни
# авторизации в приложении нет, поэтому credentials выключаем, а origins
# сужаем до реальных dev-адресов.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  EXPENSE GROUPS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


def _group_to_response(g: dict) -> ExpenseGroupResponse:
    return ExpenseGroupResponse(
        id=g["id"],
        name=g["name"],
        color=g["color"],
        parentId=g["parent_id"],
        sortOrder=g["sort_order"],
        monthlyLimit=g.get("monthly_limit"),
    )


@app.get("/api/expense-groups", response_model=list[ExpenseGroupResponse])
def get_expense_groups(db: DatabaseManager = Depends(get_db)):
    """Получить все группы расходов."""
    return [_group_to_response(g) for g in db.get_expense_groups()]


@app.post("/api/expense-groups", response_model=ExpenseGroupResponse, status_code=201)
def create_expense_group(
    data: ExpenseGroupCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новую группу расходов."""
    # Регрессия: раньше при заданном parentId он ошибочно использовался и
    # как parent_id, И как собственный id новой группы (`case pid: group_id
    # = pid`) — вторая созданная подкатегория с тем же родителем падала с
    # UNIQUE constraint failed, потому что её id совпадал с id родителя.
    group_id = str(uuid.uuid4())
    db.create_expense_group(
        group_id=group_id,
        name=data.name,
        color=data.color,
        parent_id=data.parentId,
        sort_order=0,
        monthly_limit=data.monthlyLimit,
    )
    return ExpenseGroupResponse(
        id=group_id,
        name=data.name,
        color=data.color,
        parentId=data.parentId,
        sortOrder=0,
        monthlyLimit=data.monthlyLimit,
    )


@app.get("/api/expense-groups/{group_id}", response_model=ExpenseGroupResponse)
def get_expense_group(
    group_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Получить группу расходов по ID."""
    group = db.get_expense_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_response(group)


@app.put("/api/expense-groups/{group_id}", response_model=ExpenseGroupResponse)
def update_expense_group(
    group_id: str,
    data: ExpenseGroupUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить группу расходов (partial update).

    parentId/monthlyLimit — трёхзначные поля (см. DatabaseManager.update_expense_group):
    передаём их в БД только если клиент явно включил ключ в JSON — иначе
    null (снять родителя/лимит) неотличим от "поле не передавали".
    """
    update_kwargs: dict = dict(
        group_id=group_id,
        name=data.name,
        color=data.color,
        sort_order=data.sortOrder,
    )
    if "parentId" in data.model_fields_set:
        update_kwargs["parent_id"] = data.parentId
    if "monthlyLimit" in data.model_fields_set:
        update_kwargs["monthly_limit"] = data.monthlyLimit
    db.update_expense_group(**update_kwargs)

    group = db.get_expense_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_response(group)


@app.delete("/api/expense-groups/{group_id}", status_code=204)
def delete_expense_group(
    group_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить группу расходов."""
    db.delete_expense_group(group_id)
    return None


# ═══════════════════════════════════════════════════════════════
#  EXPENSE ITEMS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


def _expense_to_response(e: dict) -> ExpenseItemResponse:
    return ExpenseItemResponse(
        id=str(e["id"]),
        groupId=e.get("group_id"),
        name=e["name"],
        amount=e["amount"],
        isInclusive=e.get("is_inclusive", False),
        half=e.get("half", 1),
        isRecurring=e.get("is_recurring", False),
        recurringUntil=e.get("recurring_until"),
        month=e["month"],
        year=e["year"],
    )


def _validate_iso_date(value: str, field_name: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"{field_name}: неверный формат даты. Используйте YYYY-MM-DD"
        ) from e


@app.get("/api/expense-items", response_model=list[ExpenseItemResponse])
def get_expense_items(
    month: int | None = Query(None, ge=1, le=12, description="Месяц (1-12)"),
    year: int | None = Query(None, ge=2020, le=2100, description="Год (2020-2100)"),
    db: DatabaseManager = Depends(get_db),
):
    """Получить расходы с фильтрацией по месяцу/году."""
    return [_expense_to_response(e) for e in db.get_expenses(month=month, year=year)]


@app.post("/api/expense-items", response_model=ExpenseItemResponse, status_code=201)
def create_expense_item(
    data: ExpenseItemCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый расход с валидацией через ExpenseItemCreate."""
    if data.recurringUntil is not None:
        _validate_iso_date(data.recurringUntil, "recurringUntil")

    new_id = db.add_expense(
        name=data.name,
        amount=data.amount,
        month=data.month,
        year=data.year,
        half=data.half,
        is_recurring=data.isRecurring,
        group_id=data.groupId,
        recurring_until=data.recurringUntil,
    )
    return ExpenseItemResponse(
        id=str(new_id),
        groupId=data.groupId,
        name=data.name,
        amount=data.amount,
        isInclusive=False,
        half=data.half,
        isRecurring=data.isRecurring,
        recurringUntil=data.recurringUntil,
        month=data.month,
        year=data.year,
    )


@app.put("/api/expense-items/{item_id}", response_model=ExpenseItemResponse)
def update_expense_item(
    item_id: str,
    data: ExpenseItemUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить расход с поддержкой partial update (PATCH semantics).

    groupId/recurringUntil — трёхзначные поля (см. DatabaseManager.update_expense):
    передаём их в БД только если клиент явно включил ключ в JSON — иначе
    null (снять группу/дату завершения повторения) неотличим от "поле не
    передавали".
    """
    if data.recurringUntil is not None:
        _validate_iso_date(data.recurringUntil, "recurringUntil")

    try:
        eid = int(item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Item not found: {e}") from e

    update_kwargs: dict = dict(
        eid=eid,
        name=data.name,
        amount=data.amount,
        half=data.half,
        is_recurring=data.isRecurring,
    )
    if "groupId" in data.model_fields_set:
        update_kwargs["group_id"] = data.groupId
    if "recurringUntil" in data.model_fields_set:
        update_kwargs["recurring_until"] = data.recurringUntil

    try:
        db.update_expense(**update_kwargs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Item not found: {e}") from e

    updated = next((e for e in db.get_expenses() if e["id"] == eid), None)
    if updated is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _expense_to_response(updated)


@app.delete("/api/expense-items/{item_id}", status_code=204)
def delete_expense_item(
    item_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить расход."""
    try:
        eid = int(item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    db.delete_expense(eid)
    return None


# ═══════════════════════════════════════════════════════════════
#  VACATIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/vacations", response_model=list[VacationResponse])
def get_vacations(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2020, le=2100),
    db: DatabaseManager = Depends(get_db),
):
    """Получить все отпускные."""
    vacations = db.get_vacations(month=month, year=year)
    return [
        VacationResponse(
            id=str(v.get("id", uuid.uuid4())),
            totalAmount=v["total_amount"],
            payoutDate=v["payout_date"],
            startDate=v.get("start_date"),
            endDate=v.get("end_date"),
        )
        for v in vacations
    ]


@app.post("/api/vacations", response_model=VacationResponse, status_code=201)
def create_vacation(
    data: VacationCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новое начисление (отпускные) с валидацией через VacationCreate.

    startDate/endDate — необязательный диапазон отпуска: если указан, дни
    отпуска, попадающие на рабочие дни, вычитаются из базы расчёта обычной
    зарплаты методом "по рабочим дням" (см. SalaryCalculator). Без диапазона
    отпуск учитывается только как надбавка к выплате на дату payoutDate —
    как раньше.
    """
    try:
        date.fromisoformat(data.payoutDate)
        start = date.fromisoformat(data.startDate) if data.startDate else None
        end = date.fromisoformat(data.endDate) if data.endDate else None
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD"
        ) from e

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="startDate не может быть позже endDate")

    new_id = db.add_vacation(
        total_amount=data.totalAmount,
        payout_date=data.payoutDate,
        start_date=data.startDate,
        end_date=data.endDate,
    )
    return VacationResponse(
        id=str(new_id),
        totalAmount=data.totalAmount,
        payoutDate=data.payoutDate,
        startDate=data.startDate or data.payoutDate,
        endDate=data.endDate or data.payoutDate,
    )


@app.delete("/api/vacations/{vacation_id}", status_code=204)
def delete_vacation(
    vacation_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить начисление."""
    try:
        vid = int(vacation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Vacation not found") from e
    db.delete_vacation(vid)
    return None


# ═══════════════════════════════════════════════════════════════
#  BIRTHDAYS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/birthdays", response_model=list[BirthdayResponse])
def get_birthdays(db: DatabaseManager = Depends(get_db)):
    """Получить все дни рождения."""
    birthdays = db.get_birthdays()
    return [
        BirthdayResponse(
            id=str(b.get("id", uuid.uuid4())),
            name=b["name"],
            birthDate=b["birth_date"],
            giftAmount=b["gift_amount"],
        )
        for b in birthdays
    ]


def _validate_birth_date_format(value: str) -> None:
    """DD.MM.YYYY, реальная дата. Общая проверка для create/update —
    чтобы не дублировать её в каждом эндпоинте (DRY)."""
    try:
        parts = value.strip().split(".")
        match len(parts):
            case 3:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                date(year, month, day)
            case _:
                raise ValueError()
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400, detail="Неверный формат даты. Используйте DD.MM.YYYY"
        ) from e


@app.post("/api/birthdays", response_model=BirthdayResponse, status_code=201)
def create_birthday(
    data: BirthdayCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Добавить день рождения с валидацией через BirthdayCreate."""
    _validate_birth_date_format(data.birthDate)

    new_id = db.add_birthday(name=data.name, birth_date=data.birthDate, gift_amount=data.giftAmount)
    return BirthdayResponse(
        id=str(new_id), name=data.name, birthDate=data.birthDate, giftAmount=data.giftAmount
    )


@app.put("/api/birthdays/{birthday_id}", response_model=BirthdayResponse)
def update_birthday(
    birthday_id: str,
    data: BirthdayUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить день рождения (partial update). db.update_birthday требует
    полный набор полей, поэтому недостающие берём из текущей записи —
    тот же паттерн, что и update_expense_item."""
    try:
        bid = int(birthday_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Birthday not found") from e

    current = next((b for b in db.get_birthdays() if b["id"] == bid), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Birthday not found")

    if data.birthDate is not None:
        _validate_birth_date_format(data.birthDate)

    new_name = data.name if data.name is not None else current["name"]
    new_birth_date = data.birthDate if data.birthDate is not None else current["birth_date"]
    new_gift_amount = data.giftAmount if data.giftAmount is not None else current["gift_amount"]

    db.update_birthday(bid, new_name, new_birth_date, new_gift_amount)
    return BirthdayResponse(
        id=str(bid), name=new_name, birthDate=new_birth_date, giftAmount=new_gift_amount
    )


@app.delete("/api/birthdays/{birthday_id}", status_code=204)
def delete_birthday(
    birthday_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить день рождения."""
    try:
        bid = int(birthday_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Birthday not found") from e
    db.delete_birthday(bid)
    return None


@app.get("/api/birthdays/upcoming", response_model=list[BirthdayAlertResponse])
def get_upcoming_birthdays(
    days: int = Query(30, ge=1, le=365, description="Горизонт напоминания в днях"),
    db: DatabaseManager = Depends(get_db),
    service: BirthdayService = Depends(get_birthday_service),
):
    """Дни рождения, триггер напоминания которых попадает в ближайшие N дней."""
    alerts = service.upcoming(db.get_birthdays(), days_ahead=days)
    return [
        BirthdayAlertResponse(
            name=a.name,
            birthDate=a.birth_date,
            giftAmount=a.gift_amount,
            triggerDate=a.trigger_date.isoformat(),
            daysUntil=a.days_until,
        )
        for a in alerts
    ]


@app.post("/api/birthdays/auto-create-expenses", response_model=AutoCreateResult)
def auto_create_birthday_expenses(db: DatabaseManager = Depends(get_db)):
    """Создать расходы на подарки для ДР, чей триггер (-14 дней) попал в текущий месяц."""
    service = BirthdayService(get_setting=db.get_setting)
    today = date.today()
    existing = db.get_expenses(month=today.month, year=today.year)
    created = service.auto_create_expenses(
        db.get_birthdays(),
        existing,
        add_expense_fn=lambda **kw: db.add_expense(**kw),
    )
    return AutoCreateResult(created=created)


# ═══════════════════════════════════════════════════════════════
#  SETTINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/settings", response_model=SalarySettingsResponse)
def get_settings(db: DatabaseManager = Depends(get_db)):
    """Получить настройки зарплаты."""
    return SalarySettingsResponse(
        baseSalary=float(db.get_setting("base_salary") or "100000"),
        taxRate=float(db.get_setting("tax_rate") or "13"),
        kef=float(db.get_setting("kef") or "1.0"),
        advanceCutoffDay=int(db.get_setting("advance_cutoff_day") or "15"),
        isAdvanceDateInclusive=db.get_setting("is_advance_date_inclusive") == "true",
        accountShortened=db.get_setting("account_shortened") == "true",
        standardHours=int(db.get_setting("standard_hours") or "40"),
        payoutDay1=int(db.get_setting("payout_day1") or "10"),
        payoutDay2=int(db.get_setting("payout_day2") or "25"),
        moveWeekendToFriday=db.get_setting("move_weekend_to_friday") == "true",
        salaryCalculationMethod=db.get_setting("salary_calculation_method") or "proportional",
        firstHalfRatio=float(db.get_setting("first_half_ratio") or "0.4"),
        secondHalfRatio=float(db.get_setting("second_half_ratio") or "0.6"),
    )


# (pydantic-поле, ключ в settings, преобразование в строку для хранения) —
# каждое поле SalarySettingsUpdate обновляло настройку почти идентичным
# match/case блоком, отличавшимся только этими тремя вещами (DRY).
_SETTINGS_FIELD_MAP: list[tuple[str, str, object]] = [
    ("baseSalary", "base_salary", str),
    ("taxRate", "tax_rate", str),
    ("kef", "kef", str),
    ("advanceCutoffDay", "advance_cutoff_day", str),
    ("isAdvanceDateInclusive", "is_advance_date_inclusive", lambda v: str(v).lower()),
    ("accountShortened", "account_shortened", lambda v: str(v).lower()),
    ("standardHours", "standard_hours", str),
    ("payoutDay1", "payout_day1", str),
    ("payoutDay2", "payout_day2", str),
    ("moveWeekendToFriday", "move_weekend_to_friday", lambda v: str(v).lower()),
    ("salaryCalculationMethod", "salary_calculation_method", str),
    ("firstHalfRatio", "first_half_ratio", str),
    ("secondHalfRatio", "second_half_ratio", str),
]


@app.put("/api/settings", response_model=SalarySettingsResponse)
def update_settings(
    updates: SalarySettingsUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить настройки зарплаты (только переданные поля)."""
    for field, key, to_str in _SETTINGS_FIELD_MAP:
        value = getattr(updates, field)
        if value is not None:
            db.set_setting(key, to_str(value))

    return get_settings(db)


# ═══════════════════════════════════════════════════════════════
#  BALANCE ENDPOINT (SalaryCalculator — ранее не был подключен к API)
# ═══════════════════════════════════════════════════════════════


@app.get("/api/balance", response_model=BalanceResponse)
def get_balance(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    db: DatabaseManager = Depends(get_db),
    calc: SalaryCalculator = Depends(get_salary_calculator),
):
    """Полный расчёт баланса за период: ЗП (с учётом выбранного метода
    распределения по половинам месяца) + отпускные - расходы."""
    expenses = db.get_expenses(month=month, year=year)
    result = calc.balance(year, month, expenses)
    s = result.salary
    return BalanceResponse(
        month=month,
        year=year,
        netSalary=s.net_salary,
        advance=s.advance,
        payout=s.payout,
        vacationHalf1=s.vacation_half_1,
        vacationHalf2=s.vacation_half_2,
        totalAccrued=s.total_accrued,
        toPayHalf1=s.to_pay_half_1,
        toPayHalf2=s.to_pay_half_2,
        expensesHalf1=result.expenses_h1,
        expensesHalf2=result.expenses_h2,
        balanceHalf1=result.balance_h1,
        balanceHalf2=result.balance_h2,
        calculationMethod=s.calculation_method,
        workingDaysHalf1=s.working_days_half_1,
        workingDaysHalf2=s.working_days_half_2,
        workingDaysTotal=s.working_days_total,
        advanceCutoffDay=s.advance_cutoff_day,
        payoutDate1=s.payout_date_1,
        payoutDate2=s.payout_date_2,
        payoutDate1Nominal=s.payout_date_1_nominal,
        payoutDate2Nominal=s.payout_date_2_nominal,
    )


# ═══════════════════════════════════════════════════════════════
#  DEBTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


def _debt_to_response(d: dict) -> DebtResponse:
    return DebtResponse(
        id=str(d["id"]),
        title=d["title"],
        totalAmount=d["total_amount"],
        repayments=[
            RepaymentResponse(
                id=str(r["id"]),
                debtId=str(r["debt_id"]),
                amount=r["amount"],
                date=r["date"],
                note=r["note"],
            )
            for r in d.get("repayments", [])
        ],
        createdAt=d["created_at"],
        month=d["month"],
        year=d["year"],
        repaidAmount=d.get("repaid_amount", 0.0),
        remainingAmount=d.get("remaining_amount", d["total_amount"]),
    )


@app.get("/api/debts", response_model=list[DebtResponse])
def get_debts(db: DatabaseManager = Depends(get_db)):
    """Получить все долги."""
    return [_debt_to_response(d) for d in db.get_debts()]


@app.get("/api/debts/{debt_id}", response_model=DebtResponse)
def get_debt(
    debt_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Получить конкретный долг."""
    try:
        did = int(debt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Debt not found") from e
    
    debts = db.get_debts()
    debt = next((d for d in debts if d["id"] == did), None)
    if debt is None:
        raise HTTPException(status_code=404, detail="Debt not found")
    return _debt_to_response(debt)


@app.post("/api/debts", response_model=DebtResponse, status_code=201)
def create_debt(
    data: DebtCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый долг."""
    debt_id = db.create_debt(
        title=data.title, total_amount=data.totalAmount, month=data.month, year=data.year
    )
    created_debt = next((d for d in db.get_debts() if d["id"] == debt_id), None)
    if created_debt is None:
        raise HTTPException(status_code=500, detail="Failed to fetch created debt")
    return _debt_to_response(created_debt)


@app.delete("/api/debts/{debt_id}", status_code=204)
def delete_debt(
    debt_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить долг."""
    try:
        did = int(debt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Debt not found") from e
    db.delete_debt(did)
    return None


@app.post("/api/debts/{debt_id}/repayments", response_model=RepaymentResponse, status_code=201)
def add_debt_repayment(
    debt_id: str,
    data: RepaymentCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Добавить погашение долга."""
    _validate_iso_date(data.date, "date")

    try:
        did = int(debt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Debt not found: {e}") from e

    try:
        new_id = db.add_debt_repayment(
            debt_id=did, amount=data.amount, date=data.date, note=data.note
        )
    except Exception as e:
        # FOREIGN KEY constraint failed — долга с таким id не существует.
        raise HTTPException(status_code=404, detail=f"Debt not found: {e}") from e

    # Все поля ответа уже есть в запросе + только что полученном id —
    # не нужно повторно вычитывать долг из БД и угадывать "последнее"
    # погашение в отсортированном по дате списке (могло совпасть с чужим).
    return RepaymentResponse(
        id=str(new_id),
        debtId=str(did),
        amount=data.amount,
        date=data.date,
        note=data.note,
    )


@app.delete("/api/debts/repayments/{repayment_id}", status_code=204)
def delete_debt_repayment(
    repayment_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить погашение долга."""
    try:
        rid = int(repayment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Repayment not found") from e
    db.delete_debt_repayment(rid)
    return None


# ═══════════════════════════════════════════════════════════════
#  ANALYTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/analytics/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2020, le=2100),
    db: DatabaseManager = Depends(get_db),
):
    """Получить сводную аналитику расходов."""
    expenses = db.get_expenses(month=month, year=year)
    total = sum(e["amount"] for e in expenses)

    # Все группы одним запросом заранее — раньше db.get_expense_group(gid)
    # вызывался внутри цикла по каждому расходу (N+1: отдельное SQL-соединение
    # на каждый расход с группой).
    groups_by_id = {g["id"]: g for g in db.get_expense_groups()}

    # Группируем по group_id (не по имени группы) — имена в теории могут
    # совпасть у разных групп, id — нет; так же сразу протаскиваем groupId/
    # monthlyLimit в ответ, чтобы фронтенд мог подсветить превышение лимита.
    by_category: dict[str | None, dict] = {}
    for expense in expenses:
        group_id = expense.get("group_id")
        group = groups_by_id.get(group_id) if group_id else None

        if group_id not in by_category:
            by_category[group_id] = {
                "name": group["name"] if group else "Без группы",
                "color": group["color"] if group else "#9ca3af",
                "amount": 0.0,
                "groupId": group_id,
                "monthlyLimit": group.get("monthly_limit") if group else None,
            }
        by_category[group_id]["amount"] += expense["amount"]

    sorted_categories = sorted(by_category.values(), key=lambda c: c["amount"], reverse=True)

    return AnalyticsSummaryResponse(
        total=total,
        count=len(expenses),
        categories=[AnalyticsCategory(**cat) for cat in sorted_categories],
    )


@app.get("/api/analytics/trend", response_model=AnalyticsTrendResponse)
def get_analytics_trend(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    months: int = Query(6, ge=2, le=24),
    db: DatabaseManager = Depends(get_db),
):
    """Расходы по месяцам (и по категориям внутри каждого) за `months` месяцев,
    заканчивая на (month, year) включительно — для графика тренда на
    /analytics. Переиспользует db.get_expenses(), которая уже сама
    проецирует повторяющиеся расходы вперёд (см. её докстринг), поэтому
    здесь достаточно просто перебрать нужные периоды в цикле, без новой
    SQL-логики.
    """
    groups_by_id = {g["id"]: g for g in db.get_expense_groups()}

    # Идём назад от (year, month), потом разворачиваем -> хронологический порядок.
    periods: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(months):
        periods.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    periods.reverse()

    result: list[TrendMonth] = []
    for py, pm in periods:
        expenses = db.get_expenses(month=pm, year=py)
        by_group: dict[str | None, float] = {}
        for e in expenses:
            gid = e.get("group_id")
            by_group[gid] = by_group.get(gid, 0.0) + e["amount"]

        categories = [
            TrendMonthCategory(
                groupId=gid,
                name=groups_by_id[gid]["name"] if gid else "Без группы",
                color=groups_by_id[gid]["color"] if gid else "#9ca3af",
                amount=amount,
            )
            for gid, amount in by_group.items()
        ]
        result.append(
            TrendMonth(month=pm, year=py, total=sum(by_group.values()), categories=categories)
        )

    return AnalyticsTrendResponse(months=result)


# ═══════════════════════════════════════════════════════════════
#  BACKUP (все реальные финансовые данные живут в одном файле —
#  без этого нет вообще никакой страховки на случай порчи диска)
# ═══════════════════════════════════════════════════════════════


@app.get("/api/backup")
def download_backup(db: DatabaseManager = Depends(get_db)):
    """Скачать копию текущей БД. Через SQLite backup API (DatabaseManager.backup_to),
    а не просто отдать файл budget.db напрямую — так копия остаётся
    консистентной, даже если БД в этот момент используется (WAL).

    Копия читается в память и временный файл удаляется сразу же, в этом же
    запросе — не через FileResponse(background=...): на Windows попытка
    удалить файл из отложенной BackgroundTask иногда натыкается на
    PermissionError, потому что ОС ещё не до конца освободила хендл после
    стриминга ответа.
    """
    # db.db_path, а не get_app_settings().db_path: в тестах db приходит из
    # переопределённого get_db (изолированная ":memory:"), а глобальные
    # настройки всё равно указывали бы на реальный путь к budget.db.
    if db.db_path == ":memory:":
        raise HTTPException(status_code=400, detail="Резервная копия недоступна для in-memory БД")

    tmp_path = Path(tempfile.gettempdir()) / f"budget-backup-{uuid.uuid4().hex}.db"
    db.backup_to(str(tmp_path))
    try:
        content = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    filename = f"budget-backup-{datetime.now():%Y-%m-%d}.db"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ═══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════════════════


@app.get("/api/health")
def health_check():
    """Проверка здоровья API."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════
#  STATIC FILES (React SPA — frontend/dist, собранный `npm run build`)
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    """SPA-fallback: любой путь, не совпавший ни с одним /api/... эндпоинтом
    выше и не с /assets, отдаёт index.html — дальше маршрутизацией занимается
    React Router на клиенте (поэтому прямой переход на /settings, /expenses
    и т.д. по URL или обновление страницы работает без 404).

    Регистрация в самом конце файла обязательна: FastAPI матчит маршруты по
    порядку регистрации, и этот catch-all не должен перехватывать /api/*.
    """
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend не собран. Выполните: cd frontend && npm install && npm run build",
        )
    return FileResponse(str(index_path))


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    # 127.0.0.1, не 0.0.0.0 — как в main.py. Приложение однопользовательское,
    # без авторизации; 0.0.0.0 открыл бы полный доступ на чтение/запись
    # реальных финансовых данных всем в локальной сети.
    uvicorn.run(app, host="127.0.0.1", port=8000)
