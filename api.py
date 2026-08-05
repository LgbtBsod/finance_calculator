"""api.py — FastAPI REST API для бюджетного калькулятора.

Архитектура:
  - FastAPI приложение с CORS поддержкой
  - RESTful endpoints для всех сущностей
  - Dependency injection для сервисов
  - Pydantic модели для валидации данных
  - Интеграция с существующей БД

Принципы:
  - SRP: каждый endpoint отвечает за одну сущность
  - SOLID: зависимость от абстракций (DatabaseManager)
  - DRY: переиспользование моделей из database.py
  - SSOT: данные хранятся только в SQLite
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import DB_FILENAME
from database import DatabaseManager


# ═══════════════════════════════════════════════════════════════
#  PYDANTIC MODELS (DTOs для API)
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


class ExpenseItemCreate(BaseModel):
    groupId: str
    name: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    date: str
    isInclusive: bool = False
    half: int = Field(..., ge=1, le=2)
    isRecurring: bool = False
    month: int = Field(..., ge=1, le=12)
    year: int


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


class VacationCreate(BaseModel):
    totalAmount: float = Field(..., gt=0)
    payoutDate: str


class VacationResponse(BaseModel):
    id: str
    totalAmount: float
    payoutDate: str


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
#  DEPENDENCY INJECTION
# ═══════════════════════════════════════════════════════════════

def get_db() -> DatabaseManager:
    """Factory для DatabaseManager (singleton в рамках запроса)."""
    return DatabaseManager(DB_FILENAME)


# ═══════════════════════════════════════════════════════════════
#  FASTAPI APP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="Budget Calculator API",
    description="REST API для личного финансового калькулятора",
    version="1.0.0",
)

# CORS middleware для frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  EXPENSE GROUPS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# In-memory хранилище для групп расходов (можно вынести в БД)
_expense_groups: dict[str, dict[str, Any]] = {}


@app.get("/api/expense-groups", response_model=list[ExpenseGroupResponse])
async def get_expense_groups(db: DatabaseManager = Depends(get_db)):
    """Получить все группы расходов."""
    groups = [
        ExpenseGroupResponse(**group) 
        for group in _expense_groups.values()
    ]
    return groups


@app.post("/api/expense-groups", response_model=ExpenseGroupResponse, status_code=201)
async def create_expense_group(
    data: ExpenseGroupCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новую группу расходов."""
    group_id = str(uuid.uuid4())
    group = {
        "id": group_id,
        "name": data.name,
        "color": data.color,
        "parentId": data.parentId,
        "sortOrder": len(_expense_groups),
    }
    _expense_groups[group_id] = group
    return ExpenseGroupResponse(**group)


@app.put("/api/expense-groups/{group_id}", response_model=ExpenseGroupResponse)
async def update_expense_group(
    group_id: str,
    updates: dict[str, Any],
    db: DatabaseManager = Depends(get_db),
):
    """Обновить группу расходов."""
    if group_id not in _expense_groups:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = _expense_groups[group_id]
    for key, value in updates.items():
        if key in group and key != "id":
            group[key] = value
    
    return ExpenseGroupResponse(**group)


@app.delete("/api/expense-groups/{group_id}", status_code=204)
async def delete_expense_group(
    group_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить группу расходов."""
    if group_id not in _expense_groups:
        raise HTTPException(status_code=404, detail="Group not found")
    
    del _expense_groups[group_id]
    return None


# ═══════════════════════════════════════════════════════════════
#  EXPENSE ITEMS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

_expense_items: dict[str, dict[str, Any]] = {}


@app.get("/api/expense-items", response_model=list[ExpenseItemResponse])
async def get_expense_items(
    month: int | None = Query(None),
    year: int | None = Query(None),
    db: DatabaseManager = Depends(get_db),
):
    """Получить расходы с фильтрацией по месяцу/году."""
    items = list(_expense_items.values())
    
    if month is not None:
        items = [i for i in items if i["month"] == month]
    if year is not None:
        items = [i for i in items if i["year"] == year]
    
    return [ExpenseItemResponse(**item) for item in items]


@app.post("/api/expense-items", response_model=ExpenseItemResponse, status_code=201)
async def create_expense_item(
    data: ExpenseItemCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый расход."""
    item_id = str(uuid.uuid4())
    item = {
        "id": item_id,
        "groupId": data.groupId,
        "name": data.name,
        "amount": data.amount,
        "date": data.date,
        "isInclusive": data.isInclusive,
        "half": data.half,
        "isRecurring": data.isRecurring,
        "month": data.month,
        "year": data.year,
    }
    _expense_items[item_id] = item
    return ExpenseItemResponse(**item)


@app.put("/api/expense-items/{item_id}", response_model=ExpenseItemResponse)
async def update_expense_item(
    item_id: str,
    updates: dict[str, Any],
    db: DatabaseManager = Depends(get_db),
):
    """Обновить расход."""
    if item_id not in _expense_items:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item = _expense_items[item_id]
    for key, value in updates.items():
        if key in item and key not in ("id",):
            item[key] = value
    
    return ExpenseItemResponse(**item)


@app.delete("/api/expense-items/{item_id}", status_code=204)
async def delete_expense_item(
    item_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить расход."""
    if item_id not in _expense_items:
        raise HTTPException(status_code=404, detail="Item not found")
    
    del _expense_items[item_id]
    return None


# ═══════════════════════════════════════════════════════════════
#  DEBTS & REPAYMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

_debts: dict[str, dict[str, Any]] = {}


@app.get("/api/debts", response_model=list[DebtResponse])
async def get_debts(
    month: int | None = Query(None),
    year: int | None = Query(None),
    db: DatabaseManager = Depends(get_db),
):
    """Получить все долги с возвратами."""
    debts = list(_debts.values())
    
    if month is not None:
        debts = [d for d in debts if d["month"] == month]
    if year is not None:
        debts = [d for d in debts if d["year"] == year]
    
    return [DebtResponse(**debt) for debt in debts]


@app.post("/api/debts", response_model=DebtResponse, status_code=201)
async def create_debt(
    data: DebtCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новый долг."""
    debt_id = str(uuid.uuid4())
    debt = {
        "id": debt_id,
        "title": data.title,
        "totalAmount": data.totalAmount,
        "repayments": [],
        "createdAt": datetime.now().isoformat(),
        "month": data.month,
        "year": data.year,
    }
    _debts[debt_id] = debt
    return DebtResponse(**debt)


@app.post("/api/debts/{debt_id}/repayments", response_model=RepaymentResponse, status_code=201)
async def add_repayment(
    debt_id: str,
    data: RepaymentCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Добавить возврат по долгу (поддержка множественных возвратов)."""
    if debt_id not in _debts:
        raise HTTPException(status_code=404, detail="Debt not found")
    
    repayment_id = str(uuid.uuid4())
    repayment = {
        "id": repayment_id,
        "debtId": debt_id,
        "amount": data.amount,
        "date": data.date,
        "note": data.note,
    }
    
    _debts[debt_id]["repayments"].append(repayment)
    return RepaymentResponse(**repayment)


@app.put("/api/debts/{debt_id}/repayments/{repayment_id}", response_model=RepaymentResponse)
async def update_repayment(
    debt_id: str,
    repayment_id: str,
    updates: dict[str, Any],
    db: DatabaseManager = Depends(get_db),
):
    """Обновить возврат по долгу."""
    if debt_id not in _debts:
        raise HTTPException(status_code=404, detail="Debt not found")
    
    debt = _debts[debt_id]
    repayment = next(
        (r for r in debt["repayments"] if r["id"] == repayment_id),
        None
    )
    
    if not repayment:
        raise HTTPException(status_code=404, detail="Repayment not found")
    
    for key, value in updates.items():
        if key in repayment and key not in ("id", "debtId"):
            repayment[key] = value
    
    return RepaymentResponse(**repayment)


@app.delete("/api/debts/{debt_id}/repayments/{repayment_id}", status_code=204)
async def delete_repayment(
    debt_id: str,
    repayment_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить возврат по долгу."""
    if debt_id not in _debts:
        raise HTTPException(status_code=404, detail="Debt not found")
    
    debt = _debts[debt_id]
    debt["repayments"] = [
        r for r in debt["repayments"] if r["id"] != repayment_id
    ]
    return None


@app.delete("/api/debts/{debt_id}", status_code=204)
async def delete_debt(
    debt_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить долг."""
    if debt_id not in _debts:
        raise HTTPException(status_code=404, detail="Debt not found")
    
    del _debts[debt_id]
    return None


# ═══════════════════════════════════════════════════════════════
#  VACATIONS (INCOME) ENDPOINTS
# ═══════════════════════════════════════════════════════════════

_vacations: dict[str, dict[str, Any]] = {}


@app.get("/api/vacations", response_model=list[VacationResponse])
async def get_vacations(
    month: int | None = Query(None),
    year: int | None = Query(None),
    db: DatabaseManager = Depends(get_db),
):
    """Получить все отпускные (начисления)."""
    vacations = list(_vacations.values())
    
    # Фильтрация по дате выплаты
    if month is not None or year is not None:
        filtered = []
        for v in vacations:
            payout_date = datetime.fromisoformat(v["payoutDate"]).date()
            if month is not None and payout_date.month != month:
                continue
            if year is not None and payout_date.year != year:
                continue
            filtered.append(v)
        vacations = filtered
    
    return [VacationResponse(**v) for v in vacations]


@app.post("/api/vacations", response_model=VacationResponse, status_code=201)
async def create_vacation(
    data: VacationCreate,
    db: DatabaseManager = Depends(get_db),
):
    """Создать новое начисление (отпускные)."""
    vacation_id = str(uuid.uuid4())
    vacation = {
        "id": vacation_id,
        "totalAmount": data.totalAmount,
        "payoutDate": data.payoutDate,
    }
    _vacations[vacation_id] = vacation
    return VacationResponse(**vacation)


@app.delete("/api/vacations/{vacation_id}", status_code=204)
async def delete_vacation(
    vacation_id: str,
    db: DatabaseManager = Depends(get_db),
):
    """Удалить начисление."""
    if vacation_id not in _vacations:
        raise HTTPException(status_code=404, detail="Vacation not found")
    
    del _vacations[vacation_id]
    return None


# ═══════════════════════════════════════════════════════════════
#  SETTINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/settings", response_model=SalarySettingsResponse)
async def get_settings(db: DatabaseManager = Depends(get_db)):
    """Получить настройки зарплаты."""
    settings = {
        "baseSalary": float(db.get_setting("base_salary") or "100000"),
        "taxRate": float(db.get_setting("tax_rate") or "13"),
        "kef": float(db.get_setting("kef") or "1.0"),
        "advanceCutoffDay": int(db.get_setting("advance_cutoff_day") or "15"),
        "isAdvanceDateInclusive": db.get_setting("is_advance_date_inclusive") == "true",
        "accountShortened": db.get_setting("account_shortened") == "true",
        "standardHours": int(db.get_setting("standard_hours") or "40"),
    }
    return SalarySettingsResponse(**settings)


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
    
    # Возвращаем обновленные настройки
    return await get_settings(db)


# ═══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    """Проверка здоровья API."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
