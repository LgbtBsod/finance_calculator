"""Экран «Дни рождения»: список, напоминания, авто-создание расходов на подарки."""

from __future__ import annotations

import flet as ft

from ..format import (
    MONTH_NAMES_RU,
    build_birth_date_for_api,
    format_birth_date_ru,
    format_date_ru,
    parse_birth_date,
    pluralize_ru,
)
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
    show_modal,
    text_field,
)
from ._base import View

_UPCOMING_DAYS = 30


class BirthdaysView(View):
    title = "Дни рождения"

    def content(self) -> list[ft.Control]:
        birthdays = self.svc.list_birthdays()
        alerts = self.svc.upcoming_birthdays(_UPCOMING_DAYS)

        add_btn = ft.FilledButton("+ Добавить день рождения", icon=ft.Icons.ADD,
                                  on_click=lambda e: self._open_form(None))

        if not birthdays:
            list_body: ft.Control = empty_state("Нет добавленных дней рождения")
        else:
            cards = []
            for b in birthdays:
                c = card(
                    ft.Row(
                        [
                            ft.Text(b["name"], size=14, weight=ft.FontWeight.W_600,
                                    color=COLORS["text"], expand=True),
                            icon_button(ft.Icons.EDIT_OUTLINED,
                                        lambda e, bb=b: self._open_form(bb), tooltip="Изменить"),
                            icon_button(ft.Icons.DELETE_OUTLINE,
                                        lambda e, bb=b: self._delete(bb),
                                        tooltip="Удалить", color=COLORS["danger"]),
                        ],
                    ),
                    hint(f"{format_birth_date_ru(b['birthDate'])}"),
                    money_text(b["giftAmount"], size=17),
                )
                cards.append(c)
            list_body = card_grid(cards)

        reminders: list[ft.Control] = [section_title_small("Ближайшие напоминания")]
        reminders.append(hint("За 30 дней до дня рождения"))
        if alerts:
            reminders.append(
                ft.FilledButton(
                    "Создать расходы на подарки за этот месяц",
                    on_click=lambda e: self._auto_create(),
                )
            )
            reminders.append(
                card_grid([
                    card(
                        ft.Text(a["name"], size=13, weight=ft.FontWeight.W_600,
                                color=COLORS["text"]),
                        hint(f"Через {a['daysUntil']} "
                             f"{pluralize_ru(a['daysUntil'], 'день', 'дня', 'дней')} "
                             f"({format_date_ru(a['triggerDate'])})"),
                        money_text(a["giftAmount"], size=15),
                        bgcolor=COLORS["warning_bg"],
                    )
                    for a in alerts
                ])
            )
        else:
            reminders.append(hint("Нет напоминаний в ближайшие 30 дней"))

        return [
            add_btn,
            list_body,
            ft.Divider(height=8, color=COLORS["border"]),
            ft.Column(reminders, spacing=10),
        ]

    def _auto_create(self) -> None:
        try:
            created = self.svc.auto_create_birthday_expenses()
        except Exception as exc:
            self.toast(str(exc) or "Не удалось создать расходы", error=True)
            return
        self.toast(f"Создано расходов: {created}" if created else "Нет новых расходов для создания")
        self.reload()

    def _delete(self, b: dict) -> None:
        confirm(
            self.app.page, f"Удалить день рождения «{b['name']}»?",
            lambda: self.delete_undoable(
                lambda: self.svc.delete_birthday(b["id"]), label="День рождения"),
        )

    def _open_form(self, b: dict | None) -> None:
        page = self.app.page
        editing = b is not None
        parsed = parse_birth_date(b["birthDate"]) if editing else None
        cur_day, cur_month = parsed or (1, 1)

        name = text_field("Имя", b["name"] if editing else "")
        day_dd = dropdown("День", [(str(i), str(i)) for i in range(1, 32)], str(cur_day))
        month_dd = dropdown("Месяц", [(str(i), MONTH_NAMES_RU[i]) for i in range(1, 13)],
                            str(cur_month))
        gift = text_field("Сумма подарка, ₽",
                          str(b["giftAmount"]) if editing else "5000", keyboard="number")

        def save(e):
            try:
                amt = float((gift.value or "").replace(",", "."))
            except ValueError:
                self.toast("Введите сумму подарка", error=True)
                return
            if not (name.value or "").strip():
                self.toast("Введите имя", error=True)
                return
            bd = build_birth_date_for_api(int(day_dd.value), int(month_dd.value))
            page.pop_dialog()
            if editing:
                self.guard(
                    lambda: self.svc.update_birthday(
                        b["id"], name=name.value.strip(), birth_date=bd, gift_amount=amt),
                    ok="День рождения обновлён",
                )
            else:
                self.guard(
                    lambda: self.svc.create_birthday(
                        name=name.value.strip(), birth_date=bd, gift_amount=amt),
                    ok="День рождения добавлен",
                )

        show_modal(
            page,
            "Редактирование дня рождения" if editing else "Новый день рождения",
            ft.Column([name, ft.Row([day_dd, month_dd], spacing=10), gift], tight=True, spacing=10),
            [
                ft.TextButton("Отмена", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )


def section_title_small(text: str) -> ft.Text:
    return ft.Text(text, size=15, weight=ft.FontWeight.BOLD, color=COLORS["text"])
