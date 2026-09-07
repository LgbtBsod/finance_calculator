"""Экран «Долги»: создание, платежи, прогноз погашения."""

from __future__ import annotations

import flet as ft

from ..format import format_currency, format_date_ru, month_year_short
from ..theme import COLORS
from ..widgets import (
    card,
    card_grid,
    confirm,
    empty_state,
    hint,
    icon_button,
    money_text,
    show_modal,
    text_field,
)
from ._base import View


class DebtsView(View):
    title = "Долги"

    def content(self) -> list[ft.Control]:
        debts = self.svc.list_debts()

        add_btn = ft.FilledButton("+ Добавить долг", icon=ft.Icons.ADD,
                                  on_click=lambda e: self._open_form())

        if not debts:
            return [add_btn, empty_state("💳 Нет долгов")]

        cards = [self._debt_card(d) for d in debts]
        return [add_btn, card_grid(cards, col_lg=6)]

    def _debt_card(self, d: dict) -> ft.Container:
        remaining = d["remainingAmount"]
        rows: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(d["title"], size=15, weight=ft.FontWeight.W_600,
                            color=COLORS["text"], expand=True),
                    icon_button(ft.Icons.DELETE_OUTLINE, lambda e, dd=d: self._delete(dd),
                                tooltip="Удалить", color=COLORS["danger"]),
                ],
            ),
        ]
        if remaining > 0:
            rows.append(money_text(remaining, size=19, color=COLORS["danger"]))
            sub = f"из {format_currency(d['totalAmount'])}"
            if d["repaidAmount"] > 0:
                sub += f" · погашено {format_currency(d['repaidAmount'])}"
            rows.append(hint(sub))
        else:
            rows.append(ft.Text("✅ Погашено", size=17, weight=ft.FontWeight.BOLD,
                                color=COLORS["success"]))

        for r in d["repayments"]:
            rows.append(
                ft.Row(
                    [
                        hint(format_date_ru(r["date"]) + (f" · {r['note']}" if r.get("note") else "")),
                        ft.Row(
                            [
                                ft.Text(format_currency(r["amount"]), size=12,
                                        color=COLORS["text"]),
                                icon_button(ft.Icons.CLOSE,
                                            lambda e, rr=r, dd=d: self._delete_repayment(dd, rr),
                                            tooltip="Удалить платёж", color=COLORS["text_secondary"]),
                            ],
                            spacing=2,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

        if remaining > 0:
            amount_field = text_field("Сумма платежа, ₽", keyboard="number", width=160)

            def add_pay(e, field=amount_field, debt=d):
                try:
                    amt = float((field.value or "").replace(",", "."))
                except ValueError:
                    self.toast("Введите сумму платежа", error=True)
                    return
                if not (0 < amt <= debt["remainingAmount"]):
                    self.toast(f"Платёж должен быть от 0 до "
                               f"{format_currency(debt['remainingAmount'])}", error=True)
                    return
                self.guard(lambda: self.svc.add_repayment(debt["id"], amount=amt),
                           ok="Платёж добавлен")

            rows.append(
                ft.Row(
                    [amount_field, ft.FilledButton("+", on_click=add_pay)],
                    spacing=8,
                )
            )

            proj = self.svc.project_debt_payoff(remaining, d["repayments"])
            if proj.months_to_payoff and proj.projected_date:
                rows.append(
                    hint(
                        f"📈 При темпе ~{format_currency(proj.avg_monthly_rate)}/мес — "
                        f"закроется к {month_year_short(proj.projected_date.month, proj.projected_date.year)} "
                        f"(≈{proj.months_to_payoff} мес.)"
                    )
                )
            elif d["repayments"]:
                rows.append(hint("Темп погашения пока не определить."))
            else:
                rows.append(hint("Добавьте платёж, чтобы увидеть прогноз погашения."))

        return card(ft.Column(rows, spacing=6, tight=True), bgcolor=COLORS["danger_bg"])

    def _delete(self, d: dict) -> None:
        confirm(
            self.app.page, f"Удалить долг «{d['title']}»?",
            lambda: self.guard(lambda: self.svc.delete_debt(d["id"]), ok="Долг удалён"),
        )

    def _delete_repayment(self, d: dict, r: dict) -> None:
        confirm(
            self.app.page,
            f"Удалить платёж {format_currency(r['amount'])} от {format_date_ru(r['date'])} "
            f"по долгу «{d['title']}»?",
            lambda: self.guard(lambda: self.svc.delete_repayment(r["id"]), ok="Платёж удалён"),
        )

    def _open_form(self) -> None:
        page = self.app.page
        title = text_field("Название долга", hint_text="Например, кредит")
        amount = text_field("Сумма долга, ₽", keyboard="number")

        def save(e):
            try:
                amt = float((amount.value or "").replace(",", "."))
            except ValueError:
                self.toast("Введите сумму долга", error=True)
                return
            if not (title.value or "").strip() or amt <= 0:
                self.toast("Заполните название и сумму долга", error=True)
                return
            page.pop_dialog()
            self.guard(
                lambda: self.svc.create_debt(title=title.value.strip(), total_amount=amt),
                ok="Долг добавлен",
            )

        show_modal(
            page, "Новый долг",
            ft.Column([title, amount], tight=True, spacing=10),
            [
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )
