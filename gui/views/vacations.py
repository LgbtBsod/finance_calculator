"""Экран «Отпускные»."""

from __future__ import annotations

import flet as ft

from ..format import format_currency, format_date_ru
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


class VacationsView(View):
    title = "Отпускные"

    def content(self) -> list[ft.Control]:
        vacations = sorted(self.svc.list_vacations(), key=lambda v: v["payoutDate"])

        intro = hint(
            "Укажите точный период отпуска (начало и конец) — тогда при методе "
            "«По рабочим дням» эти дни исключатся из расчёта отработанных. Дата выплаты "
            "определяет, в какую половину месяца попадут сами отпускные."
        )
        add_btn = ft.FilledButton("+ Добавить отпускные", icon=ft.Icons.ADD,
                                  on_click=lambda e: self._open_form())

        if not vacations:
            body: ft.Control = empty_state("Нет отпускных выплат")
        else:
            cards = []
            for v in vacations:
                if v["startDate"] and v["endDate"] and v["startDate"] != v["endDate"]:
                    title = f"{format_date_ru(v['startDate'])} — {format_date_ru(v['endDate'])}"
                else:
                    title = format_date_ru(v["payoutDate"])
                c = card(
                    ft.Row(
                        [
                            ft.Text(title, size=14, weight=ft.FontWeight.W_600,
                                    color=COLORS["text"], expand=True),
                            icon_button(ft.Icons.DELETE_OUTLINE,
                                        lambda e, vv=v: self._delete(vv),
                                        tooltip="Удалить", color=COLORS["danger"]),
                        ],
                    ),
                    money_text(v["totalAmount"], size=18),
                    hint(f"Выплата {format_date_ru(v['payoutDate'])}"),
                )
                cards.append(c)
            body = card_grid(cards)

        return [intro, add_btn, body]

    def _delete(self, v: dict) -> None:
        confirm(
            self.app.page,
            f"Удалить отпускные {format_currency(v['totalAmount'])} "
            f"от {format_date_ru(v['payoutDate'])}?",
            lambda: self.delete_undoable(
                lambda: self.svc.delete_vacation(v["id"]), label="Отпускные"),
        )

    def _open_form(self) -> None:
        page = self.app.page
        amount = text_field("Сумма отпускных, ₽", keyboard="number")
        payout = text_field("Дата выплаты (ГГГГ-ММ-ДД)", hint_text="2026-07-15")
        start = text_field("Начало отпуска (необязательно)", hint_text="ГГГГ-ММ-ДД")
        end = text_field("Конец отпуска (необязательно)", hint_text="ГГГГ-ММ-ДД")

        def save(e):
            try:
                amt = float((amount.value or "").replace(",", "."))
            except ValueError:
                self.toast("Введите сумму", error=True)
                return
            if amt <= 0 or not (payout.value or "").strip():
                self.toast("Заполните сумму и дату выплаты", error=True)
                return
            page.pop_dialog()
            self.guard(
                lambda: self.svc.create_vacation(
                    total_amount=amt, payout_date=payout.value.strip(),
                    start_date=(start.value or "").strip() or None,
                    end_date=(end.value or "").strip() or None,
                ),
                ok="Отпускные добавлены",
            )

        show_modal(
            page, "Новые отпускные",
            ft.Column([amount, payout, start, end], tight=True, spacing=10),
            [
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )
