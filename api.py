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
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import get_settings as get_app_settings
from database import DatabaseManager
from models import ExpenseDTO, VacationDTO, BirthdayDTO

__all__ = ["app"]


# ═══════════════════════════════════════════════════════════════
#  DEPENDENCY INJECTION (SSOT, DRY)
# ═══════════════════════════════════════════════════════════════

def get_db() -> DatabaseManager:
    """Factory для DatabaseManager (DI container)."""
    settings = get_app_settings()
    return DatabaseManager(settings.db_path)


# ═══════════════════════════════════════════════════════════════
#  PYDANTIC REQUEST/RESPONSE MODELS (DTO для API)
# ═══════════════════════════════════════════════════════════════

class ExpenseGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    parentId: str | None = None


class ExpenseGroupResponse(BaseModel):
    id: str
    name: str
    color: str
    parentId: str | None = None
    sortOrder: int = 0


class ExpenseItemResponse(BaseModel):
    id: str
    groupId: str
    name: str
    amount: float
    date: str
    isInclusive: bool
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
    year: int


class DebtResponse(BaseModel):
    id: str
    title: str
    totalAmount: float
    repayments: list[RepaymentResponse] = []
    createdAt: str
    month: int
    year: int


class VacationResponse(BaseModel):
    id: str
    totalAmount: float
    payoutDate: str


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


class SalarySettingsUpdate(BaseModel):
    baseSalary: float | None = None
    taxRate: float | None = None
    kef: float | None = None
    advanceCutoffDay: int | None = None
    isAdvanceDateInclusive: bool | None = None
    accountShortened: bool | None = None
    standardHours: int | None = None


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
    # Пока возвращаем пустой список, т.к. в БД нет таблицы групп
    return []


@app.post("/api/expense-groups", response_model=ExpenseGroupResponse, status_code=201)
async def create_expense_group(
    data: ExpenseGroupCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новую группу расходов."""
    group_id = str(uuid.uuid4())
    return ExpenseGroupResponse(
        id=group_id,
        name=data.name,
        color=data.color,
        parentId=data.parentId,
        sortOrder=0
    )


@app.delete("/api/expense-groups/{group_id}", status_code=204)
async def delete_expense_group(
    group_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить группу расходов."""
    raise HTTPException(status_code=404, detail="Not implemented")


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
    data: ExpenseDTO,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый расход с валидацией через ExpenseDTO."""
    db.add_expense(
        name=data.name,
        amount=data.amount,
        month=data.month,
        year=data.year,
        half=data.half,
        is_recurring=data.is_recurring
    )
    # Возвращаем созданную запись
    expenses = db.get_expenses(month=data.month, year=data.year)
    last_expense = expenses[-1] if expenses else {}
    return ExpenseItemResponse(
        id=str(last_expense.get("id", uuid.uuid4())),
        groupId="default",
        name=data.name,
        amount=data.amount,
        date=date.today().isoformat(),
        isInclusive=False,
        half=data.half,
        isRecurring=data.is_recurring,
        month=data.month,
        year=data.year
    )


@app.delete("/api/expense-items/{item_id}", status_code=204)
async def delete_expense_item(
    item_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить расход."""
    try:
        eid = int(item_id)
        db.delete_expense(eid)
    except (ValueError, Exception):
        raise HTTPException(status_code=404, detail="Item not found")
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
            payoutDate=v["payout_date"]
        )
        for v in vacations
    ]


@app.post("/api/vacations", response_model=VacationResponse, status_code=201)
async def create_vacation(
    data: VacationDTO,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новое начисление (отпускные) с валидацией через VacationDTO."""
    db.add_vacation(
        total_amount=data.total_amount,
        payout_date=data.payout_date
    )
    vacations = db.get_vacations()
    last = vacations[-1] if vacations else {}
    return VacationResponse(
        id=str(last.get("id", uuid.uuid4())),
        totalAmount=data.total_amount,
        payoutDate=data.payout_date
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
    except (ValueError, Exception):
        raise HTTPException(status_code=404, detail="Vacation not found")
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


@app.post("/api/birthdays", response_model=BirthdayResponse, status_code=201)
async def create_birthday(
    data: BirthdayDTO,
    db: DatabaseManager = Depends(get_db),
):
    """Добавить день рождения с валидацией через BirthdayDTO."""
    db.add_birthday(
        name=data.name,
        birth_date=data.birth_date,
        gift_amount=data.gift_amount
    )
    birthdays = db.get_birthdays()
    last = birthdays[-1] if birthdays else {}
    return BirthdayResponse(
        id=str(last.get("id", uuid.uuid4())),
        name=data.name,
        birthDate=data.birth_date,
        giftAmount=data.gift_amount
    )


@app.delete("/api/birthdays/{birthday_id}", status_code=204)
async def delete_birthday(
    birthday_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить день рождения."""
    try:
        bid = int(birthday_id)
        db.delete_birthday(bid)
    except (ValueError, Exception):
        raise HTTPException(status_code=404, detail="Birthday not found")
    return None


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
        standardHours=int(db.get_setting("standard_hours") or "40")
    )


@app.put("/api/settings", response_model=SalarySettingsResponse)
async def update_settings(
    updates: SalarySettingsUpdate,
    db: DatabaseManager = Depends(get_db),
):
    """Обновить настройки зарплаты."""
    if updates.baseSalary is not None:
        db.set_setting("base_salary", str(updates.baseSalary))
    if updates.taxRate is not None:
        db.set_setting("tax_rate", str(updates.taxRate))
    if updates.kef is not None:
        db.set_setting("kef", str(updates.kef))
    if updates.advanceCutoffDay is not None:
        db.set_setting("advance_cutoff_day", str(updates.advanceCutoffDay))
    if updates.isAdvanceDateInclusive is not None:
        db.set_setting("is_advance_date_inclusive", str(updates.isAdvanceDateInclusive).lower())
    if updates.accountShortened is not None:
        db.set_setting("account_shortened", str(updates.accountShortened).lower())
    if updates.standardHours is not None:
        db.set_setting("standard_hours", str(updates.standardHours))
    
    return await get_settings(db)


# ═══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    """Проверка здоровья API."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════
#  STATIC FILES (Frontend)
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent


@app.get("/")
async def serve_frontend():
    """Отдаёт index.html для корневого пути."""
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(str(index_path))


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
