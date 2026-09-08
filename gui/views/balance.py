"""Экран «Баланс»: зарплата + отпускные − расходы, по половинам месяца."""

from __future__ import annotations

import flet as ft

from ..format import format_currency, format_date_long_ru
from ..theme import COLORS
from ..widgets import card, card_grid, hint, money_text, month_dropdown, year_dropdown
from ._base import View, kv_row


class BalanceView(View):
    title = "Баланс и зарплата"

    def content(self) -> list[ft.Control]:
        b = self.svc.balance(self.month, self.year)
        summary = self.svc.analytics_summary(self.month, self.year)

        picker = ft.Row(
            [month_dropdown(self.month, self._set_month), year_dropdown(self.year, self._set_year)],
            spacing=12,
        )

        totals = card(
            ft.Row(
                [
                    _stat("Зарплата (на руки)", b["netSalary"]),
                    _stat("Отпускные", b["vacationHalf1"] + b["vacationHalf2"]),
                    _stat("Итого начислено", b["totalAccrued"]),
                ],
                spacing=24,
            )
        )

        half1 = _half_card(
            "1-я половина", b["toPayHalf1"], b.get("incomeHalf1", 0), b["expensesHalf1"],
            b.get("debtPaymentHalf1", 0), b["balanceHalf1"],
            b.get("payoutDate1"), b.get("payoutDate1Nominal"), COLORS["success_bg"],
        )
        half2 = _half_card(
            "2-я половина", b["toPayHalf2"], b.get("incomeHalf2", 0), b["expensesHalf2"],
            b.get("debtPaymentHalf2", 0), b["balanceHalf2"],
            b.get("payoutDate2"), b.get("payoutDate2Nominal"), COLORS["warning_bg"],
        )

        blocks: list[ft.Control] = [
            picker, totals, card_grid([half1, half2], col_sm=6, col_lg=6),
        ]

        if (
            b.get("calculationMethod") == "working_days"
            and b.get("workingDaysTotal") is not None
        ):
            blocks.append(
                card(
                    ft.Text(
                        f"Как посчитано (день отсечения — {b.get('advanceCutoffDay')})",
                        size=12, weight=ft.FontWeight.W_600, color=COLORS["text"],
                    ),
                    hint(
                        f"1-я половина: {b['workingDaysHalf1']} раб. дней · "
                        f"2-я половина: {b['workingDaysHalf2']} раб. дней · "
                        f"всего {b['workingDaysTotal']}"
                    ),
                )
            )

        cats = summary["categories"][:5]
        cat_rows = [
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(width=8, height=8, bgcolor=c["color"], border_radius=999),
                            ft.Text(c["name"], size=12, color=COLORS["text"]),
                        ],
                        spacing=6,
                    ),
                    ft.Text(format_currency(c["amount"]), size=12, weight=ft.FontWeight.W_500,
                            color=COLORS["text"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            for c in cats
        ] or [hint("Нет расходов за этот месяц")]
        blocks.append(
            card(
                ft.Text("Расходы за месяц", size=12, color=COLORS["text_secondary"]),
                money_text(summary["total"], size=18),
                ft.Divider(height=8, color=COLORS["border"]),
                *cat_rows,
            )
        )
        return blocks


def _stat(label: str, value: float) -> ft.Column:
    return ft.Column(
        [
            ft.Text(label, size=11, color=COLORS["text_secondary"]),
            ft.Text(format_currency(value), size=16, weight=ft.FontWeight.BOLD,
                    color=COLORS["text"]),
        ],
        spacing=2,
    )


def _half_card(
    label: str, to_pay: float, income: float, expenses: float, debt_payment: float,
    balance: float, payout_date: str | None, nominal: str | None, bg: str,
) -> ft.Container:
    deficit = balance < 0
    lines = [
        ft.Text(f"К выплате · {label}", size=12, weight=ft.FontWeight.W_600,
                color=COLORS["text"]),
        money_text(to_pay, size=20),
    ]
    if payout_date:
        text = f"{format_date_long_ru(payout_date)}"
        if nominal and nominal != payout_date:
            text += f"  (перенесено с {format_date_long_ru(nominal)})"
        lines.append(hint(text))
    if income:
        lines.append(kv_row("+ Прочий доход", format_currency(income),
                            value_color=COLORS["success"]))
    lines.append(kv_row("− Расходы", format_currency(expenses)))
    if debt_payment:
        lines.append(kv_row("− Платёж по долгам", format_currency(debt_payment)))
    lines.append(
        ft.Text(
            ("Дефицит " if deficit else "Остаток ") + format_currency(abs(balance)),
            size=15, weight=ft.FontWeight.BOLD,
            color=COLORS["danger"] if deficit else COLORS["success"],
        )
    )
    return card(ft.Column(lines, spacing=6, tight=True), bgcolor=bg)
