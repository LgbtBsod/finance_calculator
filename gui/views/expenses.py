"""Экраны «Расходы» и «Группы расходов»."""

from __future__ import annotations

import flet as ft

from ..format import MONTH_NAMES_RU, format_currency, format_date_ru, pluralize_ru
from ..theme import COLORS, SWATCHES
from ..widgets import (
    card,
    card_grid,
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

_SORT_OPTIONS = [
    ("date-desc", "Сначала новые"),
    ("date-asc", "Сначала старые"),
    ("amount-desc", "Сумма: больше"),
    ("amount-asc", "Сумма: меньше"),
]


class ExpensesView(View):
    title = "Расходы"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.show_all = False
        self.search = ""
        self.filter_group = ""       # "", "__none__", or group id
        self.filter_half = ""        # "", "1", "2"
        self.sort = "date-desc"

    # ── данные ────────────────────────────────────────────────

    def _visible(self) -> tuple[list[dict], list[dict]]:
        groups = self.svc.list_expense_groups()
        if self.show_all:
            items = self.svc.list_expenses()
        else:
            items = self.svc.list_expenses(self.month, self.year)

        q = self.search.strip().lower()
        if q:
            items = [i for i in items if q in i["name"].lower()]
        if self.filter_group == "__none__":
            items = [i for i in items if not i["groupId"]]
        elif self.filter_group:
            items = [i for i in items if i["groupId"] == self.filter_group]
        if self.filter_half in ("1", "2"):
            items = [i for i in items if i["half"] == int(self.filter_half)]

        reverse = self.sort.endswith("-desc")
        if self.sort.startswith("amount"):
            items.sort(key=lambda i: i["amount"], reverse=reverse)
        else:
            items.sort(key=lambda i: (i["year"], i["month"], i["id"]), reverse=reverse)
        return items, groups

    # ── UI ────────────────────────────────────────────────────

    def content(self) -> list[ft.Control]:
        items, groups = self._visible()
        gmap = {g["id"]: g for g in groups}

        period = ft.Row(
            [
                month_dropdown(self.month, self._set_month),
                year_dropdown(self.year, self._set_year),
                switch_row("За все периоды", self.show_all, self._toggle_all),
            ],
            spacing=12,
            wrap=True,
        )

        filters = ft.Row(
            [
                text_field("Поиск", self.search, width=200, on_submit=self._on_search),
                dropdown(
                    "Группа",
                    [("", "Все группы"), ("__none__", "Без группы")]
                    + [(g["id"], g["name"]) for g in groups],
                    self.filter_group or "",
                    on_select=self._on_group_filter,
                    width=180,
                ),
                dropdown(
                    "Половина",
                    [("", "Любая"), ("1", "1-я"), ("2", "2-я")],
                    self.filter_half or "",
                    on_select=self._on_half_filter,
                    width=120,
                ),
                dropdown("Сортировка", _SORT_OPTIONS, self.sort,
                         on_select=self._on_sort, width=180),
            ],
            spacing=12,
            wrap=True,
        )

        add_btn = primary_button("+ Добавить расход", lambda e: self._open_form(None, groups),
                                 icon=ft.Icons.ADD)

        if not items:
            body: ft.Control = empty_state("Нет расходов за выбранный период")
        else:
            total = sum(i["amount"] for i in items)
            cards = [self._item_card(i, gmap) for i in items]
            body = ft.Column(
                [
                    hint(f"{len(items)} шт · {format_currency(total)}"),
                    card_grid(cards),
                ],
                spacing=8,
            )

        return [card(period), card(filters), add_btn, body]

    def _item_card(self, item: dict, gmap: dict) -> ft.Container:
        group = gmap.get(item["groupId"])
        badges: list[ft.Control] = []
        if group:
            badges.append(
                ft.Container(
                    ft.Text(group["name"], size=11, color=group["color"]),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    border=ft.Border.all(1, group["color"]), border_radius=999,
                )
            )
        else:
            badges.append(hint("Без группы"))
        badges.append(hint(f"{'1-я' if item['half'] == 1 else '2-я'} пол. · "
                           f"{MONTH_NAMES_RU[item['month']]} {item['year']}"))
        if item["isRecurring"]:
            tail = f" до {format_date_ru(item['recurringUntil'])}" if item["recurringUntil"] else ""
            badges.append(hint(("повтор (оригинал в другом месяце)" if item.get("projected")
                                else "повтор") + tail))

        if item.get("projected"):
            controls = [icon_button(ft.Icons.LOCK_OUTLINE, lambda e: self._explain_projected(),
                                    tooltip="Повторяющаяся запись — правьте оригинал")]
        else:
            controls = [
                icon_button(ft.Icons.EDIT_OUTLINED, lambda e, it=item: self._open_form(it, None),
                            tooltip="Изменить"),
                icon_button(ft.Icons.DELETE_OUTLINE, lambda e, it=item: self._delete(it),
                            tooltip="Удалить", color=COLORS["danger"]),
            ]

        return card(
            ft.Row(
                [
                    ft.Text(item["name"], size=14, weight=ft.FontWeight.W_600,
                            color=COLORS["text"], expand=True),
                    *controls,
                ],
            ),
            money_text(item["amount"], size=18, color=COLORS["danger"]),
            ft.Row(badges, wrap=True, spacing=8),
        )

    def _explain_projected(self) -> None:
        self.toast("Это повторяющийся расход, показанный на этот месяц. Чтобы изменить "
                   "или удалить его, откройте «За все периоды» и правьте оригинал.", error=True)

    # ── обработчики фильтров ─────────────────────────────────

    def _toggle_all(self, e):
        self.show_all = e.control.value
        self.reload()

    def _on_search(self, e):
        self.search = e.control.value
        self.reload()

    def _on_group_filter(self, e):
        self.filter_group = e.control.value or ""
        self.reload()

    def _on_half_filter(self, e):
        self.filter_half = e.control.value or ""
        self.reload()

    def _on_sort(self, e):
        self.sort = e.control.value
        self.reload()

    # ── CRUD ────────────────────────────────────────────────

    def _delete(self, item: dict) -> None:
        # без диалога подтверждения — снекбар «Отменить» держится 6 секунд
        self.delete_undoable(lambda: self.svc.delete_expense(item["id"]), label="Расход")

    def _open_form(self, item: dict | None, groups: list[dict] | None) -> None:
        page = self.app.page
        groups = groups if groups is not None else self.svc.list_expense_groups()
        editing = item is not None

        name = text_field("Название", item["name"] if editing else "",
                          hint_text="Продукты, проезд…")
        amount = text_field("Сумма, ₽", str(item["amount"]) if editing else "",
                            keyboard="number")
        group_dd = dropdown(
            "Группа",
            [("", "Без группы")] + [(g["id"], g["name"]) for g in groups],
            (item["groupId"] or "") if editing else "",
        )
        half_dd = dropdown("Половина месяца", [("1", "1-я половина"), ("2", "2-я половина")],
                           str(item["half"]) if editing else "1")
        month_dd = dropdown("Месяц", [(str(i), MONTH_NAMES_RU[i]) for i in range(1, 13)],
                            str(item["month"] if editing else self.month))
        year_dd = dropdown("Год", [(str(y), str(y)) for y in year_options()],
                           str(item["year"] if editing else self.year))
        if editing:
            month_dd.disabled = True
            year_dd.disabled = True
        recurring = ft.Switch(label="Повторяющийся расход",
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
            gid = group_dd.value or None
            ru = (until.value or "").strip() or None
            page.pop_dialog()
            if editing:
                self.guard(
                    lambda: self.svc.update_expense(
                        item["id"], name=name.value.strip(), amount=amt,
                        half=int(half_dd.value), is_recurring=recurring.value,
                        group_id=gid, recurring_until=ru,
                    ),
                    ok="Расход обновлён",
                )
            else:
                self.guard(
                    lambda: self.svc.create_expense(
                        name=name.value.strip(), amount=amt, half=int(half_dd.value),
                        month=int(month_dd.value), year=int(year_dd.value),
                        is_recurring=recurring.value, group_id=gid, recurring_until=ru,
                    ),
                    ok="Расход добавлен",
                )

        show_modal(
            page,
            "Редактирование расхода" if editing else "Новый расход",
            ft.Column(
                [name, amount, group_dd, half_dd, ft.Row([month_dd, year_dd], spacing=10),
                 recurring, until],
                tight=True, spacing=10,
            ),
            [
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )


class GroupsView(View):
    title = "Группы расходов"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._new_color = SWATCHES[0]

    def content(self) -> list[ft.Control]:
        groups = self.svc.list_expense_groups()
        all_items = self.svc.list_expenses()
        counts: dict[str, int] = {}
        for it in all_items:
            if it["groupId"]:
                counts[it["groupId"]] = counts.get(it["groupId"], 0) + 1

        add_btn = primary_button("+ Добавить группу", lambda e: self._open_form(None),
                                 icon=ft.Icons.ADD)

        if not groups:
            return [add_btn, empty_state("Нет групп расходов")]

        cards = []
        for g in groups:
            n = counts.get(g["id"], 0)
            sub = f"{n} {pluralize_ru(n, 'расход', 'расхода', 'расходов')}"
            if g["monthlyLimit"] is not None:
                sub += f" · лимит {format_currency(g['monthlyLimit'])}/мес"
            c = card(
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(g["name"], size=15, weight=ft.FontWeight.W_600,
                                        color=g["color"]),
                                hint(sub),
                            ],
                            spacing=2, expand=True,
                        ),
                        icon_button(ft.Icons.EDIT_OUTLINED,
                                    lambda e, gg=g: self._open_form(gg), tooltip="Изменить"),
                        icon_button(ft.Icons.DELETE_OUTLINE,
                                    lambda e, gg=g: self._delete(gg),
                                    tooltip="Удалить", color=COLORS["danger"]),
                    ],
                ),
                accent=g["color"],
            )
            cards.append(c)
        return [add_btn, card_grid(cards, col_lg=6)]

    def _delete(self, g: dict) -> None:
        from ..widgets import confirm

        confirm(
            self.app.page, f"Удалить группу «{g['name']}»? Её расходы станут «без группы».",
            lambda: self.delete_undoable(
                lambda: self.svc.delete_expense_group(g["id"]), label="Группа"),
        )

    def _open_form(self, g: dict | None) -> None:
        page = self.app.page
        editing = g is not None
        selected = {"color": g["color"] if editing else SWATCHES[0]}

        name = text_field("Название", g["name"] if editing else "",
                          hint_text="Продукты, Транспорт…")
        limit = text_field("Месячный лимит, ₽ (необязательно)",
                           str(g["monthlyLimit"]) if editing and g["monthlyLimit"] else "",
                           keyboard="number")

        swatch_row = ft.Row(spacing=6, wrap=True)

        def render_swatches():
            swatch_row.controls = [
                ft.Container(
                    width=26, height=26, bgcolor=col, border_radius=6,
                    border=ft.Border.all(3, COLORS["text"] if col == selected["color"]
                                         else COLORS["border"]),
                    on_click=lambda e, c=col: pick(c),
                )
                for col in SWATCHES
            ]

        def pick(col: str):
            selected["color"] = col
            render_swatches()
            page.update()

        render_swatches()

        def save(e):
            if not (name.value or "").strip():
                self.toast("Введите название группы", error=True)
                return
            lim_raw = (limit.value or "").strip().replace(",", ".")
            lim = float(lim_raw) if lim_raw else None
            page.pop_dialog()
            if editing:
                self.guard(
                    lambda: self.svc.update_expense_group(
                        g["id"], name=name.value.strip(), color=selected["color"],
                        monthly_limit=lim,
                    ),
                    ok="Группа обновлена",
                )
            else:
                self.guard(
                    lambda: self.svc.create_expense_group(
                        name=name.value.strip(), color=selected["color"], monthly_limit=lim,
                    ),
                    ok="Группа добавлена",
                )

        show_modal(
            page,
            "Редактирование группы" if editing else "Новая группа расходов",
            ft.Column(
                [name, ft.Text("Цвет", size=12, color=COLORS["text_secondary"]),
                 swatch_row, limit],
                tight=True, spacing=10,
            ),
            [
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )
