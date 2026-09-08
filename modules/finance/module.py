"""FinanceModule — единственный оркестратор: считает то, для чего нужно
несколько соседей. НЕ проброс CRUD (это делает фасад напрямую в модуль db).

~5 actions: balance, analytics_summary, analytics_trend, settings_get, settings_update.
Результаты кэшируются в модуле cache; инвалидация — по db:changed (см. CacheModule).
"""

from __future__ import annotations

from typing import Any

from core.module import Module

_DEFAULT_GROUP_COLOR = "#9ca3af"

# (camelCase-поле GUI, ключ в settings, преобразование значения в строку)
_SETTINGS_MAP: list[tuple[str, str, Any]] = [
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


class FinanceModule(Module):
    name = "finance"
    requires = ("db", "calculator", "cache")

    def initialize(self) -> None:
        self._actions = {
            "balance": self._balance,
            "analytics_summary": self._analytics_summary,
            "analytics_trend": self._analytics_trend,
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

        income = self.k.request("db", "get_income", month=month, year=year)
        inc_h1 = sum(i["amount"] for i in income if i["half"] == 1)
        inc_h2 = sum(i["amount"] for i in income if i["half"] == 2)

        # Плановые ежемесячные платежи по непогашенным долгам.
        debts = self.k.request("db", "get_debts")
        pay_h1 = sum(
            d["monthly_payment"] for d in debts
            if d.get("monthly_payment", 0) > 0
            and d.get("remaining_amount", d["total_amount"]) > 0
            and d.get("payment_half", 2) == 1
        )
        pay_h2 = sum(
            d["monthly_payment"] for d in debts
            if d.get("monthly_payment", 0) > 0
            and d.get("remaining_amount", d["total_amount"]) > 0
            and d.get("payment_half", 2) == 2
        )

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
        expenses = self.k.request("db", "get_expenses", month=month, year=year)
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

    # ── settings ─────────────────────────────────────────────

    def _settings_get(self) -> dict:
        b = self.k.request("db", "get_settings_bundle")

        def g(key: str, default: str) -> str:
            return b.get(key) or default

        return {
            "baseSalary": float(g("base_salary", "100000")),
            "taxRate": float(g("tax_rate", "13")),
            "kef": float(g("kef", "1.0")),
            "advanceCutoffDay": int(g("advance_cutoff_day", "15")),
            "isAdvanceDateInclusive": b.get("is_advance_date_inclusive") == "true",
            "accountShortened": b.get("account_shortened") == "true",
            "standardHours": int(g("standard_hours", "40")),
            "payoutDay1": int(g("payout_day1", "10")),
            "payoutDay2": int(g("payout_day2", "25")),
            "moveWeekendToFriday": b.get("move_weekend_to_friday") == "true",
            "salaryCalculationMethod": g("salary_calculation_method", "proportional"),
            "firstHalfRatio": float(g("first_half_ratio", "0.4")),
            "secondHalfRatio": float(g("second_half_ratio", "0.6")),
        }

    def _settings_update(self, updates: dict) -> dict:
        for field, key, to_str in _SETTINGS_MAP:
            if field in updates and updates[field] is not None:
                self.k.request("db", "set_setting", key=key, value=to_str(updates[field]))
        return self._settings_get()
