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

import uuid
from collections.abc import Generator
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

def get_db() -> Generator[DatabaseManager, None, None]:
    """Factory для DatabaseManager (DI container) с закрытием соединения."""
    settings = get_app_settings()
    db = DatabaseManager(settings.db_path)
    try:
        yield db
    finally:
        db.close()


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
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    parentId: str | None = None


class ExpenseGroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    parentId: str | None = None
    sortOrder: int | None = None


class ExpenseGroupResponse(BaseModel):
    id: str
    name: str
    color: str
    parentId: str | None = None
    sortOrder: int = 0


class ExpenseItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., gt=0)
    half: int = Field(..., ge=1, le=2)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2100)
    isRecurring: bool = Field(default=False)
    groupId: str | None = None


class ExpenseItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    amount: float | None = Field(None, gt=0)
    half: int | None = Field(None, ge=1, le=2)
    isRecurring: bool | None = None
    groupId: str | None = None


class ExpenseItemResponse(BaseModel):
    id: str
    groupId: str | None = None
    name: str
    amount: float
    date: str | None = None
    isInclusive: bool = False
    half: int
    isRecurring: bool
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


class DebtSettings(BaseModel):
    payoutDay1: int = Field(default=10, ge=1, le=31, description="Первый день выплаты")
    payoutDay2: int = Field(default=25, ge=1, le=31, description="Второй день выплаты")
    moveWeekendToFriday: bool = Field(default=False, description="Переносить выходные на пятницу")


class VacationCreate(BaseModel):
    totalAmount: float = Field(..., gt=0, description="Сумма отпускных")
    payoutDate: str = Field(..., description="Дата выплаты в формате YYYY-MM-DD")
    startDate: str | None = Field(None, description="Первый день отпуска (YYYY-MM-DD); по умолчанию = payoutDate")
    endDate: str | None = Field(None, description="Последний день отпуска (YYYY-MM-DD); по умолчанию = payoutDate")


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
    moveWeekendToFriday: bool = False
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


class AnalyticsSummaryResponse(BaseModel):
    total: float
    count: int
    categories: list[AnalyticsCategory]


class SalarySettingsUpdate(BaseModel):
    baseSalary: float | None = None
    taxRate: float | None = None
    kef: float | None = None
    advanceCutoffDay: int | None = None
    isAdvanceDateInclusive: bool | None = None
    accountShortened: bool | None = None
    standardHours: int | None = None
    payoutDay1: int | None = None
    payoutDay2: int | None = None
    moveWeekendToFriday: bool | None = None
    salaryCalculationMethod: str | None = None
    firstHalfRatio: float | None = None
    secondHalfRatio: float | None = None


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  EXPENSE GROUPS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/expense-groups", response_model=list[ExpenseGroupResponse])
async def get_expense_groups(db: DatabaseManager = Depends(get_db)):
    """Получить все группы расходов."""
    groups = db.get_expense_groups()
    return [
        ExpenseGroupResponse(
            id=g["id"],
            name=g["name"],
            color=g["color"],
            parentId=g["parent_id"],
            sortOrder=g["sort_order"]
        )
        for g in groups
    ]


@app.post("/api/expense-groups", response_model=ExpenseGroupResponse, status_code=201)
async def create_expense_group(
    data: ExpenseGroupCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новую группу расходов."""
    match data.parentId:
        case None:
            group_id = str(uuid.uuid4())
        case pid:
            group_id = pid
    db.create_expense_group(
        group_id=group_id,
        name=data.name,
        color=data.color,
        parent_id=data.parentId,
        sort_order=0
    )
    return ExpenseGroupResponse(
        id=group_id,
        name=data.name,
        color=data.color,
        parentId=data.parentId,
        sortOrder=0
    )


@app.get("/api/expense-groups/{group_id}", response_model=ExpenseGroupResponse)
async def get_expense_group(
    group_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Получить группу расходов по ID."""
    group = db.get_expense_group(group_id)
    match group:
        case None:
            raise HTTPException(status_code=404, detail="Group not found")
        case g:
            return ExpenseGroupResponse(
                id=g["id"],
                name=g["name"],
                color=g["color"],
                parentId=g["parent_id"],
                sortOrder=g["sort_order"]
            )


@app.put("/api/expense-groups/{group_id}", response_model=ExpenseGroupResponse)
async def update_expense_group(
    group_id: str,
    data: ExpenseGroupUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить группу расходов."""
    db.update_expense_group(
        group_id=group_id,
        name=data.name,
        color=data.color,
        parent_id=data.parentId,
        sort_order=data.sortOrder
    )
    group = db.get_expense_group(group_id)
    match group:
        case None:
            raise HTTPException(status_code=404, detail="Group not found")
        case g:
            return ExpenseGroupResponse(
                id=g["id"],
                name=g["name"],
                color=g["color"],
                parentId=g["parent_id"],
                sortOrder=g["sort_order"]
            )


@app.delete("/api/expense-groups/{group_id}", status_code=204)
async def delete_expense_group(
    group_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить группу расходов."""
    db.delete_expense_group(group_id)
    return None


# ═══════════════════════════════════════════════════════════════
#  EXPENSE ITEMS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/expense-items", response_model=list[ExpenseItemResponse])
async def get_expense_items(
    month: int | None = Query(None, ge=1, le=12, description="Месяц (1-12)"),
    year: int | None = Query(None, ge=2020, le=2100, description="Год (2020-2100)"),
    db: DatabaseManager = Depends(get_db),
):
    """Получить расходы с фильтрацией по месяцу/году."""
    expenses = db.get_expenses(month=month, year=year)
    return [
        ExpenseItemResponse(
            id=str(e.get("id", uuid.uuid4())),
            groupId=e.get("group_id", "default"),
            name=e["name"],
            amount=e["amount"],
            date=e.get("date", date.today()).isoformat() if isinstance(e.get("date"), date) else str(e.get("date", date.today())),
            isInclusive=e.get("is_inclusive", False),
            half=e.get("half", 1),
            isRecurring=e.get("is_recurring", False),
            month=e["month"],
            year=e["year"]
        )
        for e in expenses
    ]


@app.post("/api/expense-items", response_model=ExpenseItemResponse, status_code=201)
async def create_expense_item(
    data: ExpenseItemCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый расход с валидацией через ExpenseItemCreate."""
    db.add_expense(
        name=data.name,
        amount=data.amount,
        month=data.month,
        year=data.year,
        half=data.half,
        is_recurring=data.isRecurring,
        group_id=data.groupId
    )
    # Возвращаем созданную запись
    expenses = db.get_expenses(month=data.month, year=data.year)
    last_expense = expenses[-1] if expenses else {}
    return ExpenseItemResponse(
        id=str(last_expense.get("id", uuid.uuid4())),
        groupId=data.groupId,
        name=data.name,
        amount=data.amount,
        date=date.today().isoformat(),
        isInclusive=False,
        half=data.half,
        isRecurring=data.isRecurring,
        month=data.month,
        year=data.year
    )


@app.get("/api/expense-items/{item_id}", response_model=ExpenseItemResponse)
async def get_expense_item(
    item_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Получить расход по ID."""
    try:
        eid = int(item_id)
        all_expenses = db.get_expenses()
        for expense in all_expenses:
            match expense["id"] == eid:
                case True:
                    return ExpenseItemResponse(
                        id=str(eid),
                        groupId=None,
                        name=expense["name"],
                        amount=expense["amount"],
                        date=None,
                        isInclusive=False,
                        half=expense["half"],
                        isRecurring=expense["is_recurring"],
                        month=expense["month"],
                        year=expense["year"]
                    )
                case False:
                    pass
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Expense item not found")


@app.put("/api/expense-items/{item_id}", response_model=ExpenseItemResponse)
async def update_expense_item(
    item_id: str,
    data: ExpenseItemUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить расход с поддержкой partial update (PATCH semantics)."""
    try:
        eid = int(item_id)
        
        # Используем обновленный метод update_expense с group_id
        db.update_expense(
            eid=eid,
            name=data.name,
            amount=data.amount,
            half=data.half,
            is_recurring=data.isRecurring,
            group_id=data.groupId
        )
        
        # Получаем обновленные данные
        all_expenses = db.get_expenses()
        updated = None
        for expense in all_expenses:
            match expense["id"] == eid:
                case True:
                    updated = expense
                    break
                case False:
                    pass
        
        match updated:
            case None:
                raise HTTPException(status_code=404, detail="Expense item not found")
            case u:
                return ExpenseItemResponse(
                    id=str(eid),
                    groupId=u.get("group_id"),
                    name=u["name"],
                    amount=u["amount"],
                    date=None,
                    isInclusive=False,
                    half=u["half"],
                    isRecurring=u["is_recurring"],
                    month=u["month"],
                    year=u["year"]
                )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Item not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating item: {e}") from e


@app.delete("/api/expense-items/{item_id}", status_code=204)
async def delete_expense_item(
    item_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить расход."""
    try:
        eid = int(item_id)
        db.delete_expense(eid)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    return None


# ═══════════════════════════════════════════════════════════════
#  VACATIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/vacations", response_model=list[VacationResponse])
async def get_vacations(
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
async def create_vacation(
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
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD") from e

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="startDate не может быть позже endDate")

    db.add_vacation(
        total_amount=data.totalAmount,
        payout_date=data.payoutDate,
        start_date=data.startDate,
        end_date=data.endDate,
    )
    vacations = db.get_vacations()
    match vacations:
        case []:
            last = {}
        case v_list:
            last = v_list[-1]
    return VacationResponse(
        id=str(last.get("id", uuid.uuid4())),
        totalAmount=data.totalAmount,
        payoutDate=data.payoutDate,
        startDate=last.get("start_date", data.startDate),
        endDate=last.get("end_date", data.endDate),
    )


@app.delete("/api/vacations/{vacation_id}", status_code=204)
async def delete_vacation(
    vacation_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить начисление."""
    try:
        vid = int(vacation_id)
        db.delete_vacation(vid)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Vacation not found") from e
    return None


# ═══════════════════════════════════════════════════════════════
#  BIRTHDAYS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/birthdays", response_model=list[BirthdayResponse])
async def get_birthdays(db: DatabaseManager = Depends(get_db)):
    """Получить все дни рождения."""
    birthdays = db.get_birthdays()
    return [
        BirthdayResponse(
            id=str(b.get("id", uuid.uuid4())),
            name=b["name"],
            birthDate=b["birth_date"],
            giftAmount=b["gift_amount"]
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
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте DD.MM.YYYY") from e


@app.post("/api/birthdays", response_model=BirthdayResponse, status_code=201)
async def create_birthday(
    data: BirthdayCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Добавить день рождения с валидацией через BirthdayCreate."""
    _validate_birth_date_format(data.birthDate)

    db.add_birthday(
        name=data.name,
        birth_date=data.birthDate,
        gift_amount=data.giftAmount
    )
    birthdays = db.get_birthdays()
    match birthdays:
        case []:
            last = {}
        case b_list:
            last = b_list[-1]
    return BirthdayResponse(
        id=str(last.get("id", uuid.uuid4())),
        name=data.name,
        birthDate=data.birthDate,
        giftAmount=data.giftAmount
    )


@app.put("/api/birthdays/{birthday_id}", response_model=BirthdayResponse)
async def update_birthday(
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
    return BirthdayResponse(id=str(bid), name=new_name, birthDate=new_birth_date, giftAmount=new_gift_amount)


@app.delete("/api/birthdays/{birthday_id}", status_code=204)
async def delete_birthday(
    birthday_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить день рождения."""
    try:
        bid = int(birthday_id)
        db.delete_birthday(bid)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Birthday not found") from e
    return None


@app.get("/api/birthdays/upcoming", response_model=list[BirthdayAlertResponse])
async def get_upcoming_birthdays(
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


@app.post("/api/birthdays/auto-create-expenses", response_model=dict)
async def auto_create_birthday_expenses(db: DatabaseManager = Depends(get_db)):
    """Создать расходы на подарки для ДР, чей триггер (-14 дней) попал в текущий месяц."""
    service = BirthdayService(get_setting=db.get_setting)
    today = date.today()
    existing = db.get_expenses(month=today.month, year=today.year)
    created = service.auto_create_expenses(
        db.get_birthdays(),
        existing,
        add_expense_fn=lambda **kw: db.add_expense(**kw),
    )
    return {"created": created}


# ═══════════════════════════════════════════════════════════════
#  SETTINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/settings", response_model=SalarySettingsResponse)
async def get_settings(db: DatabaseManager = Depends(get_db)):
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


@app.put("/api/settings", response_model=SalarySettingsResponse)
async def update_settings(
    updates: SalarySettingsUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить настройки зарплаты."""
    match updates:
        case SalarySettingsUpdate(baseSalary=b) if b is not None:
            db.set_setting("base_salary", str(b))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(taxRate=t) if t is not None:
            db.set_setting("tax_rate", str(t))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(kef=k) if k is not None:
            db.set_setting("kef", str(k))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(advanceCutoffDay=a) if a is not None:
            db.set_setting("advance_cutoff_day", str(a))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(isAdvanceDateInclusive=i) if i is not None:
            db.set_setting("is_advance_date_inclusive", str(i).lower())
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(accountShortened=a) if a is not None:
            db.set_setting("account_shortened", str(a).lower())
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(standardHours=s) if s is not None:
            db.set_setting("standard_hours", str(s))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(payoutDay1=p) if p is not None:
            db.set_setting("payout_day1", str(p))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(payoutDay2=p) if p is not None:
            db.set_setting("payout_day2", str(p))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(moveWeekendToFriday=m) if m is not None:
            db.set_setting("move_weekend_to_friday", str(m).lower())
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(salaryCalculationMethod=m) if m is not None:
            db.set_setting("salary_calculation_method", m)
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(firstHalfRatio=r) if r is not None:
            db.set_setting("first_half_ratio", str(r))
        case _:
            pass
    match updates:
        case SalarySettingsUpdate(secondHalfRatio=r) if r is not None:
            db.set_setting("second_half_ratio", str(r))
        case _:
            pass
    
    return await get_settings(db)


# ═══════════════════════════════════════════════════════════════
#  BALANCE ENDPOINT (SalaryCalculator — ранее не был подключен к API)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/balance", response_model=BalanceResponse)
async def get_balance(
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

@app.get("/api/debts", response_model=list[DebtResponse])
async def get_debts(db: DatabaseManager = Depends(get_db)):
    """Получить все долги."""
    debts = db.get_debts()
    return [
        DebtResponse(
            id=str(d["id"]),
            title=d["title"],
            totalAmount=d["total_amount"],
            repayments=[
                RepaymentResponse(
                    id=str(r["id"]),
                    debtId=str(r["debt_id"]),
                    amount=r["amount"],
                    date=r["date"],
                    note=r["note"]
                )
                for r in d.get("repayments", [])
            ],
            createdAt=d["created_at"],
            month=d["month"],
            year=d["year"]
        )
        for d in debts
    ]


@app.post("/api/debts", response_model=DebtResponse, status_code=201)
async def create_debt(
    data: DebtCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый долг."""
    debt_id = db.create_debt(
        title=data.title,
        total_amount=data.totalAmount,
        month=data.month,
        year=data.year
    )
    # Fetch the created debt
    debts = db.get_debts()
    created_debt = next((d for d in debts if str(d["id"]) == str(debt_id)), None)
    match created_debt:
        case None:
            raise HTTPException(status_code=500, detail="Failed to fetch created debt")
        case debt:
            return DebtResponse(
                id=str(debt["id"]),
                title=debt["title"],
                totalAmount=debt["total_amount"],
                repayments=[
                    RepaymentResponse(
                        id=str(r["id"]),
                        debtId=str(r["debt_id"]),
                        amount=r["amount"],
                        date=r["date"],
                        note=r["note"]
                    )
                    for r in debt.get("repayments", [])
                ],
                createdAt=debt["created_at"],
                month=debt["month"],
                year=debt["year"]
            )


@app.delete("/api/debts/{debt_id}", status_code=204)
async def delete_debt(
    debt_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить долг."""
    try:
        did = int(debt_id)
        db.delete_debt(did)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Debt not found") from e
    return None


@app.post("/api/debts/{debt_id}/repayments", response_model=RepaymentResponse, status_code=201)
async def add_debt_repayment(
    debt_id: str,
    data: RepaymentCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Добавить погашение долга."""
    try:
        did = int(debt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Debt not found: {e}") from e

    try:
        db.add_debt_repayment(
            debt_id=did,
            amount=data.amount,
            date=data.date,
            note=data.note
        )
    except Exception as e:
        # FOREIGN KEY constraint failed — долга с таким id не существует.
        raise HTTPException(status_code=404, detail=f"Debt not found: {e}") from e

    # Считать провал этой выборки багом, а не "долг не найден" — поэтому
    # вне try/except выше: настоящая ошибка сервера должна остаться 500.
    debts = db.get_debts()
    for debt in debts:
        if str(debt["id"]) == str(did) and debt["repayments"]:
            last_repayment = debt["repayments"][-1]
            return RepaymentResponse(
                id=str(last_repayment["id"]),
                debtId=str(last_repayment["debt_id"]),
                amount=last_repayment["amount"],
                date=last_repayment["date"],
                note=last_repayment["note"]
            )
    raise HTTPException(status_code=500, detail="Failed to fetch created repayment")


@app.delete("/api/debts/repayments/{repayment_id}", status_code=204)
async def delete_debt_repayment(
    repayment_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить погашение долга."""
    try:
        rid = int(repayment_id)
        db.delete_debt_repayment(rid)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Repayment not found") from e
    return None


# ═══════════════════════════════════════════════════════════════
#  ANALYTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/analytics/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2020, le=2100),
    db: DatabaseManager = Depends(get_db),
):
    """Получить сводную аналитику расходов."""
    expenses = db.get_expenses(month=month, year=year)
    
    total = sum(e["amount"] for e in expenses)
    
    # Группировка по категориям
    by_category: dict[str, dict] = {}
    for expense in expenses:
        group_id = expense.get("group_id")
        match group_id:
            case None:
                g_name = "Без группы"
                g_color = "#9ca3af"
            case gid:
                group = db.get_expense_group(gid)
                g_name = group["name"] if group else "Без группы"
                g_color = group["color"] if group else "#9ca3af"
        
        match g_name in by_category:
            case False:
                by_category[g_name] = {"amount": 0, "color": g_color}
            case _:
                pass
        by_category[g_name]["amount"] += expense["amount"]
    
    # Сортировка по сумме
    sorted_categories = sorted(by_category.items(), key=lambda x: x[1]["amount"], reverse=True)
    
    return {
        "total": total,
        "count": len(expenses),
        "categories": [{"name": k, **v} for k, v in sorted_categories]
    }


# ═══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
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
async def serve_spa(full_path: str):
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
