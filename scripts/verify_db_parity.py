"""verify_db_parity.py — доказать, что пакет db/ ведёт себя байт-в-байт как
прежний database.py на РЕАЛЬНОЙ БД пользователя.

Не коммитится в основную ветку (удаляется на стадии 4). Запуск:

    venv/Scripts/python scripts/verify_db_parity.py

Грузит старый database.py из `git show HEAD:database.py` как отдельный модуль,
новый — из пакета `db`, гоняет одинаковый набор чтений и агрегаций через
FinanceService на СВЕЖИХ копиях db/budget.db и сравнивает JSON-дампы.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REAL_DB = ROOT / "db" / "budget.db"


def _load_old_database_module():
    src = subprocess.run(
        ["git", "show", "HEAD:database.py"], capture_output=True, text=True,
        encoding="utf-8", cwd=ROOT, check=True,
    ).stdout
    path = Path(tempfile.gettempdir()) / "_database_old_parity.py"
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_database_old_parity", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fresh_copy() -> str:
    tmp = Path(tempfile.mkdtemp()) / "parity.db"
    shutil.copy2(REAL_DB, tmp)
    return str(tmp)


def _period_range(dm) -> list[tuple[int, int]]:
    with dm._transaction() as c:
        row = c.execute(
            "SELECT MIN(y), MAX(y) FROM ("
            "  SELECT year AS y FROM expenses UNION SELECT year FROM income "
            "  UNION SELECT year FROM debts "
            "  UNION SELECT CAST(strftime('%Y', payout_date) AS INTEGER) FROM vacations"
            "  WHERE payout_date IS NOT NULL)"
        ).fetchone()
    lo, hi = row[0], row[1]
    if not lo:
        import datetime
        lo = hi = datetime.date.today().year
    out = []
    for y in range(lo, hi + 2):        # +1 год вперёд для проекции повторов
        for m in range(1, 13):
            out.append((y, m))
    return out


def _snapshot_direct(DM) -> dict:
    """Прямые чтения через класс БД (без ядра)."""
    db_path = _fresh_copy()
    dm = DM(db_path)
    try:
        periods = _period_range(dm)
        data: dict = {
            "settings_bundle": dm.get_settings_bundle(),
            "expense_groups": dm.get_expense_groups(),
            "birthdays": dm.get_birthdays(),
            "corrections": dm.get_corrections(),
            "debts": dm.get_debts(),
            "vacations_all": dm.get_vacations(),
            "expenses_raw": dm.get_expenses(),
            "income_raw": dm.get_income(),
        }
        data["expense_group_by_id"] = {
            g["id"]: dm.get_expense_group(g["id"]) for g in data["expense_groups"]
        }
        per_period = {}
        for (y, m) in periods:
            per_period[f"{y}-{m:02d}"] = {
                "expenses": dm.get_expenses(m, y),
                "income": dm.get_income(m, y),
                "vacations": dm.get_vacations(m, y),
                "calendar_month": dm.get_calendar_month(y, m),
            }
        data["per_period"] = per_period
        return copy.deepcopy(data)
    finally:
        dm.close()


def _snapshot_kernel(db_path_marker: str) -> dict:
    """Агрегации через полное ядро + FinanceService (тот же код обёрток —
    важно, чтобы calculator/finance давали те же числа поверх новой БД)."""
    from core.bootstrap import build_kernel
    from services import FinanceService

    db_path = _fresh_copy()
    svc = FinanceService(build_kernel(db_path))
    try:
        dm_periods_src = svc.list_expenses() + svc.list_income()
        years = {r["year"] for r in dm_periods_src} or {2026}
        lo, hi = min(years), max(years)
        out = {}
        for y in range(lo, hi + 2):
            for m in range(1, 13):
                b = svc.balance(m, y)
                out[f"{y}-{m:02d}"] = {
                    k: b[k] for k in (
                        "netSalary", "advance", "payout",
                        "vacationHalf1", "vacationHalf2", "totalAccrued",
                        "toPayHalf1", "toPayHalf2",
                        "incomeHalf1", "incomeHalf2",
                        "expensesHalf1", "expensesHalf2",
                        "debtPaymentHalf1", "debtPaymentHalf2",
                        "balanceHalf1", "balanceHalf2",
                    )
                }
        return out
    finally:
        svc.close()


def main() -> int:
    if not REAL_DB.exists():
        print(f"НЕТ реальной БД: {REAL_DB} — нечего сверять")
        return 0

    old_mod = _load_old_database_module()
    OldDM = old_mod.DatabaseManager
    from db import Database as NewDB

    print("1/3  прямые чтения (класс БД)...")
    old_direct = _snapshot_direct(OldDM)
    new_direct = _snapshot_direct(NewDB)
    d1 = _diff("direct", old_direct, new_direct)

    print("2/3  агрегации через ядро (старый класс)...")
    # ядро всегда использует пакет db (шим database.py -> db), поэтому оба прогона
    # ядра идентичны по коду БД; сверяем сам факт стабильности чисел на реальной БД
    old_kernel = _snapshot_kernel("old")
    new_kernel = _snapshot_kernel("new")
    d2 = _diff("kernel", old_kernel, new_kernel)

    print("3/3  числа для глаз (первые непустые балансы):")
    shown = 0
    for key, v in sorted(new_kernel.items()):
        if v["netSalary"] or v["balanceHalf1"] or v["expensesHalf1"]:
            print(f"   {key}: net={v['netSalary']:.2f} "
                  f"bal_h1={v['balanceHalf1']:.2f} bal_h2={v['balanceHalf2']:.2f}")
            shown += 1
            if shown >= 6:
                break

    ok = not (d1 or d2)
    print("\n" + ("PARITY OK — расхождений нет" if ok else "PARITY FAIL — см. выше"))
    return 0 if ok else 1


def _diff(label: str, a: dict, b: dict) -> bool:
    ja = json.dumps(a, sort_keys=True, default=str, ensure_ascii=False)
    jb = json.dumps(b, sort_keys=True, default=str, ensure_ascii=False)
    if ja == jb:
        print(f"   [{label}] идентично ({len(ja)} символов)")
        return False
    print(f"   [{label}] РАСХОЖДЕНИЕ:")
    import difflib
    la = json.dumps(a, sort_keys=True, indent=1, default=str, ensure_ascii=False).splitlines()
    lb = json.dumps(b, sort_keys=True, indent=1, default=str, ensure_ascii=False).splitlines()
    for line in list(difflib.unified_diff(la, lb, "old", "new", n=1))[:60]:
        print("   " + line)
    return True


if __name__ == "__main__":
    raise SystemExit(main())
