"""Экран «Доходы».

Две разновидности строки дохода (поле kind):
  • fixed  — разовая/повторяющаяся сумма (фриланс, аренда, кэшбек), прямо
             прибавляется к балансу половины месяца;
  • salary — оклад: SalaryCalculator считает аванс/выплату по своим параметрам
             (kef, метод распределения, пропорции). Несколько окладов = несколько
             работ, они суммируются.
"""

from __future__ import annotations

import flet as ft

from ..format import MONTH_NAMES_RU, format_currency, format_date_ru
from ..theme import COLORS
from ..widgets import (
    card,
    card_grid,
    dropdown,
    empty_state,
    hint,
    icon_button,
    month_dropdown,
    primary_button,
    show_modal,
    switch_row,
    text_field,
    year_dropdown,
    year_options,
)
from ._base import View

_SPLIT_METHODS = [
    ("proportional", "Пропорционально (40% / 60%)"),
    ("custom_proportions", "Свои пропорции"),
    ("working_days", "По рабочим дням месяца"),
]
_METHOD_LABEL = dict(_SPLIT_METHODS)


class IncomeView(View):
    title = "Доходы"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.show_all = False

    # ── список ────────────────────────────────────────────────

    def content(self) -> list[ft.Control]:
        items = self.svc.list_income() if self.show_all \
            else self.svc.list_income(self.month, self.year)
        # оклады сверху, потом обычные доходы по периоду
        items.sort(key=lambda i: (i["kind"] != "salary", i["year"], i["month"],
                                  i["half"], i["id"]), reverse=False)

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
        buttons = ft.Row(
            [
                primary_button("+ Доход", lambda e: self._open_form(None, "fixed"),
                               icon=ft.Icons.ADD),
                primary_button("+ Зарплата", lambda e: self._open_form(None, "salary"),
                               icon=ft.Icons.PAYMENTS_OUTLINED),
            ],
            spacing=10,
        )

        if not items:
            body: ft.Control = empty_state(
                "Пока нет доходов. Добавьте зарплату или разовую сумму.",
                icon=ft.Icons.TRENDING_UP,
            )
        else:
            salary_sum = sum(i["amount"] for i in items if i["kind"] == "salary")
            other_sum = sum(i["amount"] for i in items if i["kind"] != "salary")
            parts = []
            if salary_sum:
                parts.append(f"оклады {format_currency(salary_sum)}/мес")
            if other_sum:
                parts.append(f"прочее {format_currency(other_sum)}")
            body = ft.Column(
                [hint(" · ".join(parts) or f"{len(items)} шт"),
                 card_grid([self._item_card(i) for i in items])],
                spacing=8,
            )
        return [period, buttons, body]

    def _item_card(self, item: dict) -> ft.Container:
        salary = item["kind"] == "salary"
        badges: list[ft.Control] = []
        if salary:
            badges.append(ft.Text("ЗАРПЛАТА", size=10, weight=ft.FontWeight.W_700,
                                  color=COLORS["accent"]))
            badges.append(hint(_METHOD_LABEL.get(item.get("splitMethod") or "proportional",
                                                 "пропорционально")))
            badges.append(hint(f"действует с {MONTH_NAMES_RU[item['month']]} {item['year']}"))
        else:
            badges.append(hint(f"{'1-я' if item['half'] == 1 else '2-я'} пол. · "
                               f"{MONTH_NAMES_RU[item['month']]} {item['year']}"))
        if item["isRecurring"] and item["recurringUntil"]:
            badges.append(hint(("по " if salary else "до ")
                               + format_date_ru(item["recurringUntil"])))
        elif item["isRecurring"] and not salary:
            badges.append(hint("повтор (оригинал в другом месяце)"
                               if item.get("projected") else "повтор"))
        if item.get("overridden"):
            badges.append(hint(("оклад" if salary else "сумма") + " изменён на этот месяц"))

        if salary:
            # Оклад правится с любого месяца (меняет строку, действует с её даты).
            # «Только на этот месяц» — отдельная кнопка-календарь (премия/пропуск).
            controls = [
                icon_button(ft.Icons.EDIT_CALENDAR_OUTLINED,
                            lambda e, it=item: self._open_month_amount(it),
                            tooltip="Оклад только на этот месяц"),
                icon_button(ft.Icons.EDIT_OUTLINED,
                            lambda e, it=item: self._open_form(it, "salary"),
                            tooltip="Изменить зарплату"),
                icon_button(ft.Icons.DELETE_OUTLINE, lambda e, it=item: self._delete(it),
                            tooltip="Удалить", color=COLORS["danger"]),
            ]
            if item.get("overridden"):
                controls.insert(1, icon_button(
                    ft.Icons.RESTORE, lambda e, it=item: self._reset_month_amount(it),
                    tooltip="Вернуть оклад как обычно"))
        elif item.get("projected"):
            controls = [icon_button(
                ft.Icons.EDIT_CALENDAR_OUTLINED,
                lambda e, it=item: self._open_month_amount(it),
                tooltip="Сумма только на этот месяц")]
            if item.get("overridden"):
                controls.append(icon_button(
                    ft.Icons.RESTORE, lambda e, it=item: self._reset_month_amount(it),
                    tooltip="Вернуть как обычно"))
        else:
            controls = [
                icon_button(ft.Icons.EDIT_OUTLINED,
                            lambda e, it=item: self._open_form(it, it["kind"]),
                            tooltip="Изменить"),
                icon_button(ft.Icons.DELETE_OUTLINE, lambda e, it=item: self._delete(it),
                            tooltip="Удалить", color=COLORS["danger"]),
            ]

        suffix = " / мес" if salary else ""
        return card(
            ft.Row([ft.Text(item["name"], size=14, weight=ft.FontWeight.W_600,
                            color=COLORS["text"], expand=True), *controls]),
            ft.Text(format_currency(item["amount"]) + suffix, size=18,
                    weight=ft.FontWeight.W_700, color=COLORS["success"]),
            ft.Row(badges, wrap=True, spacing=8),
            bgcolor=COLORS["accent_bg"] if salary else None,
        )

    # ── переопределение суммы на месяц (проекция повтора) ──────

    def _open_month_amount(self, item: dict) -> None:
        page = self.app.page
        word = "Оклад" if item["kind"] == "salary" else "Сумма"
        fld = text_field(f"{word} на {MONTH_NAMES_RU[item['month']]} {item['year']}",
                         str(item["amount"]), keyboard="number")

        def save(e):
            try:
                amt = float((fld.value or "").replace(",", "."))
            except ValueError:
                self.toast("Введите сумму", error=True)
                return
            if amt <= 0:
                self.toast("Сумма должна быть больше нуля", error=True)
                return
            page.pop_dialog()
            self.guard(lambda: self.svc.set_month_amount(
                "income", item["id"], year=item["year"], month=item["month"], amount=amt),
                ok=f"{word} на месяц изменён")

        show_modal(
            page, f"{word} на этот месяц",
            ft.Column([hint("Меняется только этот месяц; запись-оригинал не затрагивается."),
                       fld], tight=True, spacing=10),
            [ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
             ft.FilledButton("Сохранить", on_click=save)],
        )

    def _reset_month_amount(self, item: dict) -> None:
        self.guard(lambda: self.svc.clear_month_amount(
            "income", item["id"], year=item["year"], month=item["month"]),
            ok="Возвращено как обычно")

    def _toggle_all(self, e):
        self.show_all = e.control.value
        self.reload()

    def _delete(self, item: dict) -> None:
        label = "Зарплата" if item["kind"] == "salary" else "Доход"
        self.delete_undoable(lambda: self.svc.delete_income(item["id"]), label=label)

    # ── форма ─────────────────────────────────────────────────

    def _open_form(self, item: dict | None, kind: str) -> None:
        page = self.app.page
        editing = item is not None
        salary = kind == "salary"

        name = text_field("Название", item["name"] if editing else ("Зарплата" if salary else ""),
                          hint_text="Работа / фриланс / аренда…")
        amount = text_field("Оклад в месяц, ₽" if salary else "Сумма, ₽",
                            str(item["amount"]) if editing else "", keyboard="number")
        month_dd = dropdown("Месяц" if not salary else "Действует с месяца",
                            [(str(i), MONTH_NAMES_RU[i]) for i in range(1, 13)],
                            str(item["month"] if editing else self.month))
        year_dd = dropdown("Год", [(str(y), str(y)) for y in year_options()],
                           str(item["year"] if editing else self.year))
        if editing:
            month_dd.disabled = year_dd.disabled = True
        until = text_field("Работа по (ГГГГ-ММ-ДД)" if salary else "Повторять до (ГГГГ-ММ-ДД)",
                           (item["recurringUntil"] or "") if editing else "",
                           hint_text="пусто = бессрочно")

        fields: list[ft.Control] = [name, amount]

        if salary:
            kef = text_field("Коэффициент (КЕФ)",
                             str(item["kef"]) if editing and item.get("kef") else "1.0",
                             keyboard="number")
            method = dropdown("Метод распределения аванс/выплата", _SPLIT_METHODS,
                              (item.get("splitMethod") or "proportional") if editing
                              else "proportional")
            fr = text_field("Доля 1-й половины (0–1)",
                            str(item["firstHalfRatio"]) if editing and item.get("firstHalfRatio")
                            else "0.4", keyboard="number")
            sr = text_field("Доля 2-й половины (0–1)",
                            str(item["secondHalfRatio"]) if editing and item.get("secondHalfRatio")
                            else "0.6", keyboard="number")
            ratios = ft.Column([ft.Row([fr, sr], spacing=10)], tight=True,
                               visible=method.value == "custom_proportions")

            def _on_method(e):
                ratios.visible = method.value == "custom_proportions"
                page.update()

            method.on_select = _on_method
            fields += [ft.Row([month_dd, year_dd], spacing=10), kef, method, ratios, until]
        else:
            half_dd = dropdown("Половина месяца",
                               [("1", "1-я половина"), ("2", "2-я половина")],
                               str(item["half"]) if editing else "1")
            recurring = ft.Switch(label="Повторяющийся доход",
                                  value=item["isRecurring"] if editing else False,
                                  active_color=COLORS["accent"])
            fields += [half_dd, ft.Row([month_dd, year_dd], spacing=10), recurring, until]

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

            if salary:
                try:
                    kef_v = float((kef.value or "1").replace(",", "."))
                    fr_v = float((fr.value or "0.4").replace(",", "."))
                    sr_v = float((sr.value or "0.6").replace(",", "."))
                except ValueError:
                    self.toast("КЕФ и доли — числа", error=True)
                    return
                common = dict(name=name.value.strip(), amount=amt, kef=kef_v,
                              split_method=method.value, first_half_ratio=fr_v,
                              second_half_ratio=sr_v)
                if editing:
                    self.guard(lambda: self.svc.update_income(
                        item["id"], recurring_until=ru, **common), ok="Зарплата обновлена")
                else:
                    self.guard(lambda: self.svc.create_income(
                        kind="salary", half=1, month=int(month_dd.value),
                        year=int(year_dd.value), recurring_until=ru, **common),
                        ok="Зарплата добавлена")
                return

            if editing:
                self.guard(lambda: self.svc.update_income(
                    item["id"], name=name.value.strip(), amount=amt, half=int(half_dd.value),
                    is_recurring=recurring.value, recurring_until=ru), ok="Доход обновлён")
            else:
                self.guard(lambda: self.svc.create_income(
                    name=name.value.strip(), amount=amt, half=int(half_dd.value),
                    month=int(month_dd.value), year=int(year_dd.value),
                    is_recurring=recurring.value, recurring_until=ru), ok="Доход добавлен")

        heading = ("Редактирование зарплаты" if editing and salary
                   else "Новая зарплата" if salary
                   else "Редактирование дохода" if editing else "Новый доход")
        show_modal(page, heading, ft.Column(fields, tight=True, spacing=10),
                   [ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Сохранить", on_click=save)])
