"""FinanceModule — единственный оркестратор: считает то, для чего нужно
несколько соседей. НЕ проброс CRUD (это делает фасад напрямую в модуль db).

~5 actions: balance, analytics_summary, analytics_trend, settings_get, settings_update.
Результаты кэшируются в модуле cache; инвалидация — по db:changed (см. CacheModule).
"""

from __future__ import annotations

import math
from datetime import date

from config import SETTINGS
from core.module import Module

_DEFAULT_GROUP_COLOR = "#9ca3af"


def _debt_payment_active(debt: dict, year: int, month: int, today: date) -> bool:
    """Учитывать ли плановый ежемесячный платёж по долгу в балансе месяца
    ``(year, month)``.

    Платёж вычитается только за месяцы, в которых долг реально «жив»:
    начиная с месяца создания долга и заканчивая ориентировочным месяцем
    погашения (оценка от «сегодня» по плановой ставке). Иначе прошлые
    месяцы показывали бы несуществовавший платёж, а будущие — платёж уже
    после закрытия долга.
    """
    mp = debt.get("monthly_payment", 0) or 0
    if mp <= 0:
        return False
    remaining = debt.get("remaining_amount", debt.get("total_amount", 0))
    if remaining <= 0:
        return False

    viewed_idx = year * 12 + (month - 1)
    start_idx = debt["year"] * 12 + (debt["month"] - 1)
    today_idx = today.year * 12 + (today.month - 1)

    if viewed_idx < start_idx:
        return False              # долг ещё не существовал
    if viewed_idx <= today_idx:
        return True               # прошлое/текущее: remaining>0 ⇒ был активен
    # будущее: не позже ориентировочного месяца погашения по плановой ставке
    return viewed_idx <= today_idx + math.ceil(remaining / mp)


class FinanceModule(Module):
    name = "finance"
    requires = ("db", "calculator", "cache")

    def initialize(self) -> None:
        self._actions = {
            "balance": self._balance,
            "analytics_summary": self._analytics_summary,
            "analytics_trend": self._analytics_trend,
            "category_diff": self._category_diff,
            "settings_get": self._settings_get,
            "settings_update": self._settings_update,
        }

    # ── cache helper ─────────────────────────────────────────

    def _cached(self, key: str, compute):  # noqa: ANN001
        hit = self.k.request("cache", "get", key=key)
        if hit["hit"]:
            return hit["value"]
        value = compute()
        self.k.request("cache", "set", key=key, value=value)
        return value

    # ── balance ──────────────────────────────────────────────

    def _balance(self, month: int, year: int) -> dict:
        return self._cached(f"balance:{year}-{month:02d}", lambda: self._compute_balance(month, year))

    def _compute_balance(self, month: int, year: int) -> dict:
        r = self.k.request("calculator", "balance", year=year, month=month)
        s = r["salary"]

        # «Прочий доход» — только kind='fixed'; оклады (kind='salary') уже
        # посчитаны SalaryCalculator и лежат в r["salary"].
        income = [i for i in self.k.request("db", "get_income", month=month, year=year)
                  if i.get("kind", "fixed") == "fixed"]
        inc_h1 = sum(i["amount"] for i in income if i["half"] == 1)
        inc_h2 = sum(i["amount"] for i in income if i["half"] == 2)

        # Плановые ежемесячные платежи по долгам, «живым» в этом месяце.
        today = date.today()
        active = [d for d in self.k.request("db", "get_debts")
                  if _debt_payment_active(d, year, month, today)]
        pay_h1 = sum(d["monthly_payment"] for d in active if d.get("payment_half", 2) == 1)
        pay_h2 = sum(d["monthly_payment"] for d in active if d.get("payment_half", 2) == 2)

        return {
            "month": month,
            "year": year,
            "netSalary": s["net_salary"],
            "advance": s["advance"],
            "payout": s["payout"],
            "vacationHalf1": s["vacation_half_1"],
            "vacationHalf2": s["vacation_half_2"],
            "totalAccrued": s["total_accrued"],
            "toPayHalf1": s["to_pay_half_1"],
            "toPayHalf2": s["to_pay_half_2"],
            "incomeHalf1": inc_h1,
            "incomeHalf2": inc_h2,
            "expensesHalf1": r["expenses_h1"],
            "expensesHalf2": r["expenses_h2"],
            "debtPaymentHalf1": pay_h1,
            "debtPaymentHalf2": pay_h2,
            "balanceHalf1": r["balance_h1"] + inc_h1 - pay_h1,
            "balanceHalf2": r["balance_h2"] + inc_h2 - pay_h2,
            "calculationMethod": s["calculation_method"],
            "workingDaysHalf1": s["working_days_half_1"],
            "workingDaysHalf2": s["working_days_half_2"],
            "workingDaysTotal": s["working_days_total"],
            "advanceCutoffDay": s["advance_cutoff_day"],
            "payoutDate1": s["payout_date_1"],
            "payoutDate2": s["payout_date_2"],
            "payoutDate1Nominal": s["payout_date_1_nominal"],
            "payoutDate2Nominal": s["payout_date_2_nominal"],
        }

    # ── analytics ────────────────────────────────────────────

    def _analytics_summary(self, month: int | None = None, year: int | None = None) -> dict:
        key = f"analytics:summary:{year}-{month}"
        return self._cached(key, lambda: self._compute_summary(month, year))

    def _compute_summary(self, month: int | None, year: int | None) -> dict:
        if month is not None and year is not None:
            expenses = self.k.request("db", "get_expenses", month=month, year=year)
        else:
            expenses = self._expenses_all_time()   # «за всё время» — с разворотом повторов
        groups = {g["id"]: g for g in self.k.request("db", "get_expense_groups")}
        total = sum(e["amount"] for e in expenses)

        by_cat: dict[str | None, dict] = {}
        for e in expenses:
            gid = e.get("group_id")
            g = groups.get(gid) if gid else None
            if gid not in by_cat:
                by_cat[gid] = {
                    "name": g["name"] if g else "Без группы",
                    "color": g["color"] if g else _DEFAULT_GROUP_COLOR,
                    "amount": 0.0,
                    "groupId": gid,
                    "monthlyLimit": g.get("monthly_limit") if g else None,
                }
            by_cat[gid]["amount"] += e["amount"]

        cats = sorted(by_cat.values(), key=lambda c: c["amount"], reverse=True)
        return {"total": total, "count": len(expenses), "categories": cats}

    def _expenses_all_time(self) -> list[dict]:
        """Все расходы за всё время с помесячным разворотом повторяющихся
        строк (get_expenses без периода отдаёт сырьё — повтор посчитался бы
        один раз вместо раз-в-месяц). Диапазон: от самого раннего расхода до
        текущего месяца."""
        raw = self.k.request("db", "get_expenses")
        if not raw:
            return []
        start = min((e["year"], e["month"]) for e in raw)
        today = date.today()
        end = max(start, (today.year, today.month))
        out: list[dict] = []
        y, m = start
        while (y, m) <= end:
            out.extend(self.k.request("db", "get_expenses", month=m, year=y))
            m += 1
            if m == 13:
                m, y = 1, y + 1
        return out

    def _analytics_trend(self, month: int, year: int, months: int = 6) -> dict:
        key = f"analytics:trend:{year}-{month:02d}:{months}"
        return self._cached(key, lambda: self._compute_trend(month, year, months))

    def _compute_trend(self, month: int, year: int, months: int) -> dict:
        groups = {g["id"]: g for g in self.k.request("db", "get_expense_groups")}
        periods: list[tuple[int, int]] = []
        y, m = year, month
        for _ in range(months):
            periods.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        periods.reverse()

        out: list[dict] = []
        for py, pm in periods:
            expenses = self.k.request("db", "get_expenses", month=pm, year=py)
            by_group: dict[str | None, float] = {}
            for e in expenses:
                gid = e.get("group_id")
                by_group[gid] = by_group.get(gid, 0.0) + e["amount"]
            categories = [
                {
                    "groupId": gid,
                    "name": groups[gid]["name"] if gid in groups else "Без группы",
                    "color": groups[gid]["color"] if gid in groups else _DEFAULT_GROUP_COLOR,
                    "amount": amount,
                }
                for gid, amount in by_group.items()
            ]
            out.append(
                {"month": pm, "year": py, "total": sum(by_group.values()), "categories": categories}
            )
        return {"months": out}

    # ── изменение к прошлому месяцу ───────────────────────────

    def _category_diff(self, month: int, year: int) -> dict:
        key = f"analytics:diff:{year}-{month:02d}"
        return self._cached(key, lambda: self._compute_diff(month, year))

    def _compute_diff(self, month: int, year: int) -> dict:
        prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
        cur = {c["groupId"]: c for c in self._compute_summary(month, year)["categories"]}
        prev = {c["groupId"]: c for c in self._compute_summary(prev_m, prev_y)["categories"]}

        rows: list[dict] = []
        for gid in {*cur, *prev}:
            c_amt = cur.get(gid, {}).get("amount", 0.0)
            p_amt = prev.get(gid, {}).get("amount", 0.0)
            meta = cur.get(gid) or prev.get(gid)
            rows.append({
                "groupId": gid,
                "name": meta["name"],
                "color": meta["color"],
                "current": c_amt,
                "previous": p_amt,
                "delta": c_amt - p_amt,
            })
        rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
        cur_total = sum(r["current"] for r in rows)
        prev_total = sum(r["previous"] for r in rows)
        return {
            "month": month, "year": year, "prevMonth": prev_m, "prevYear": prev_y,
            "currentTotal": cur_total, "previousTotal": prev_total,
            "totalDelta": cur_total - prev_total, "categories": rows,
        }

    # ── settings ─────────────────────────────────────────────

    def _settings_get(self) -> dict:
        b = self.k.request("db", "get_settings_bundle")
        return {s.camel: s.parse(b.get(s.key)) for s in SETTINGS}

    def _settings_update(self, updates: dict) -> dict:
        for s in SETTINGS:
            if updates.get(s.camel) is not None:
                self.k.request("db", "set_setting", key=s.key, value=s.to_str(updates[s.camel]))
        return self._settings_get()
