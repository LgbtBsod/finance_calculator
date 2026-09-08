"""Экран «Доходы» — зеркало Расходов без групп: разовые и повторяющиеся
суммы (фриланс, аренда, кэшбек…), прибавляются к балансу месяца.
"""

from __future__ import annotations

import flet as ft

from ..format import MONTH_NAMES_RU, format_currency, format_date_ru
from ..theme import COLORS
from ..widgets import (
    card,
    card_grid,
    confirm,
    dropdown,
    empty_state,
    hint,
    icon_button,
    money_text,
    month_dropdown,
    primary_button,
    show_modal,
    switch_row,
    text_field,
    year_dropdown,
    year_options,
)
from ._base import View


class IncomeView(View):
    title = "Доходы"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.show_all = False

    def content(self) -> list[ft.Control]:
        items = self.svc.list_income() if self.show_all else self.svc.list_income(self.month, self.year)
        items.sort(key=lambda i: (i["year"], i["month"], i["half"], i["id"]), reverse=True)

        period = card(
            ft.Row(
                [
                    month_dropdown(self.month, self._set_month),
                    year_dropdown(self.year, self._set_year),
                    switch_row("За все периоды", self.show_all, self._toggle_all),
                ],
                spacing=12, wrap=True,
            )
        )
        add_btn = primary_button("+ Добавить доход", lambda e: self._open_form(None), icon=ft.Icons.ADD)

        if not items:
            body: ft.Control = empty_state(
                "Нет доходов за период. Зарплата считается отдельно (экран «Баланс»)."
            )
        else:
            total = sum(i["amount"] for i in items)
            body = ft.Column(
                [hint(f"{len(items)} шт · {format_currency(total)}"),
                 card_grid([self._item_card(i) for i in items])],
                spacing=8,
            )
        return [period, add_btn, body]

    def _item_card(self, item: dict) -> ft.Container:
        badges: list[ft.Control] = [
            hint(f"{'1-я' if item['half'] == 1 else '2-я'} пол. · "
                 f"{MONTH_NAMES_RU[item['month']]} {item['year']}")
        ]
        if item["isRecurring"]:
            tail = f" до {format_date_ru(item['recurringUntil'])}" if item["recurringUntil"] else ""
            badges.append(hint("повтор" + tail))
        return card(
            ft.Row(
                [
                    ft.Text(item["name"], size=14, weight=ft.FontWeight.W_600,
                            color=COLORS["text"], expand=True),
                    icon_button(ft.Icons.EDIT_OUTLINED, lambda e, it=item: self._open_form(it),
                                tooltip="Изменить"),
                    icon_button(ft.Icons.DELETE_OUTLINE, lambda e, it=item: self._delete(it),
                                tooltip="Удалить", color=COLORS["danger"]),
                ],
            ),
            money_text(item["amount"], size=18, color=COLORS["success"]),
            ft.Row(badges, wrap=True, spacing=8),
        )

    def _toggle_all(self, e):
        self.show_all = e.control.value
        self.reload()

    def _delete(self, item: dict) -> None:
        confirm(
            self.app.page, f"Удалить доход «{item['name']}»?",
            lambda: self.guard(lambda: self.svc.delete_income(item["id"]), ok="Доход удалён"),
        )

    def _open_form(self, item: dict | None) -> None:
        page = self.app.page
        editing = item is not None
        name = text_field("Название", item["name"] if editing else "",
                          hint_text="Фриланс, аренда, кэшбек…")
        amount = text_field("Сумма, ₽", str(item["amount"]) if editing else "", keyboard="number")
        half_dd = dropdown("Половина месяца", [("1", "1-я половина"), ("2", "2-я половина")],
                           str(item["half"]) if editing else "1")
        month_dd = dropdown("Месяц", [(str(i), MONTH_NAMES_RU[i]) for i in range(1, 13)],
                            str(item["month"] if editing else self.month))
        year_dd = dropdown("Год", [(str(y), str(y)) for y in year_options()],
                           str(item["year"] if editing else self.year))
        if editing:
            month_dd.disabled = year_dd.disabled = True
        recurring = ft.Switch(label="Повторяющийся доход",
                              value=item["isRecurring"] if editing else False,
                              active_color=COLORS["accent"])
        until = text_field("Повторять до (ГГГГ-ММ-ДД)",
                           (item["recurringUntil"] or "") if editing else "",
                           hint_text="пусто = бессрочно")

        def save(e):
            try:
                amt = float((amount.value or "").replace(",", "."))
            except ValueError:
                self.toast("Введите корректную сумму", error=True)
                return
            if not (name.value or "").strip() or amt <= 0:
                self.toast("Заполните название и сумму", error=True)
                return
            ru = (until.value or "").strip() or None
            page.pop_dialog()
            if editing:
                self.guard(
                    lambda: self.svc.update_income(
                        item["id"], name=name.value.strip(), amount=amt,
                        half=int(half_dd.value), is_recurring=recurring.value, recurring_until=ru),
                    ok="Доход обновлён",
                )
            else:
                self.guard(
                    lambda: self.svc.create_income(
                        name=name.value.strip(), amount=amt, half=int(half_dd.value),
                        month=int(month_dd.value), year=int(year_dd.value),
                        is_recurring=recurring.value, recurring_until=ru),
                    ok="Доход добавлен",
                )

        show_modal(
            page,
            "Редактирование дохода" if editing else "Новый доход",
            ft.Column([name, amount, half_dd, ft.Row([month_dd, year_dd], spacing=10),
                       recurring, until], tight=True, spacing=10),
            [
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )
