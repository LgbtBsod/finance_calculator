"""Экран «Настройки»: налог и параметры выплат, резервная копия, тема, обновления.

Оклад/КЕФ/метод распределения — не здесь: это сущность «доход» kind='salary'
(экран «Доходы»), чтобы вести несколько работ.
"""

from __future__ import annotations

from datetime import date

import flet as ft

from ..theme import COLORS
from ..widgets import card, dropdown, hint, section_title, text_field
from ._base import View


class SettingsView(View):
    title = "Настройки"

    def content(self) -> list[ft.Control]:
        s = self.svc.get_settings()

        tax = text_field("Налог (НДФЛ), %", str(s["taxRate"]), keyboard="number")
        tax_progressive = ft.Switch(
            label="Прогрессивная шкала НДФЛ 2025 (13→22%, поле «Налог, %» игнорируется)",
            value=s["taxProgressive"], active_color=COLORS["accent"],
        )
        cutoff = text_field("День отсечения аванса", str(s["advanceCutoffDay"]), keyboard="number")
        std_hours = text_field("Стандартные часы", str(s["standardHours"]), keyboard="number")
        inclusive = ft.Switch(label="День отсечения включён в 1-ю половину",
                              value=s["isAdvanceDateInclusive"], active_color=COLORS["accent"])
        acc_short = ft.Switch(label="Учитывать сокращённые дни отдельно",
                              value=s["accountShortened"], active_color=COLORS["accent"])
        payout1 = text_field("Первый день выплаты", str(s["payoutDay1"]), keyboard="number")
        payout2 = text_field("Второй день выплаты", str(s["payoutDay2"]), keyboard="number")
        move_weekend = ft.Switch(label="Переносить выходные дни выплат на более ранний рабочий день",
                                 value=s["moveWeekendToFriday"], active_color=COLORS["accent"])

        def save(e):
            def num(field, cast=float):
                return cast(str(field.value).replace(",", "."))

            try:
                updates = {
                    "taxRate": num(tax),
                    "taxProgressive": tax_progressive.value,
                    "advanceCutoffDay": num(cutoff, int),
                    "standardHours": num(std_hours, int),
                    "isAdvanceDateInclusive": inclusive.value,
                    "accountShortened": acc_short.value,
                    "payoutDay1": num(payout1, int),
                    "payoutDay2": num(payout2, int),
                    "moveWeekendToFriday": move_weekend.value,
                }
            except ValueError:
                self.toast("Проверьте числовые поля — где-то не число", error=True)
                return
            self.guard(lambda: self.svc.update_settings(updates), ok="Настройки сохранены")

        payroll_card = card(
            ft.Column(
                [
                    hint("Оклад, коэффициент и метод распределения теперь задаются в "
                         "разделе «Доходы» (тип «Зарплата») — можно вести несколько работ."),
                    tax, tax_progressive,
                    ft.Row([cutoff, std_hours], spacing=10),
                    inclusive, acc_short,
                    ft.Divider(color=COLORS["border"]),
                    ft.Text("Дни выплаты зарплаты", size=14, weight=ft.FontWeight.W_600,
                            color=COLORS["text"]),
                    ft.Row([payout1, payout2], spacing=10),
                    move_weekend,
                    ft.FilledButton("Сохранить настройки", on_click=save),
                ],
                spacing=12, tight=True,
            )
        )

        return [
            section_title("Налог и выплаты"),
            payroll_card,
            section_title("Резервное копирование"),
            self._backup_card(),
            section_title("Оформление"),
            self._theme_card(),
            section_title("Обновления"),
            self._updates_card(),
        ]

    # ── backup ────────────────────────────────────────────────

    def _backup_card(self) -> ft.Container:
        status = ft.Text("", size=12, color=COLORS["text_secondary"])

        def do_backup(e):
            from paths import app_dir, open_in_file_manager

            try:
                target_dir = app_dir / "backups"
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / f"budget-backup-{date.today():%Y-%m-%d}.db"
                self.svc.backup_to(str(target))
            except Exception as exc:
                status.value = f"Ошибка: {exc}"
                status.color = COLORS["danger"]
                self.app.page.update()
                return
            status.value = f"Сохранено: {target}"
            status.color = COLORS["success"]
            self.app.page.update()
            open_in_file_manager(target_dir)

        return card(
            hint(
                "Все расходы, долги, дни рождения и отпускные хранятся в одном файле на этом "
                "компьютере. Сделайте копию и держите её отдельно (облако, флешка)."
            ),
            ft.FilledButton("Сохранить резервную копию", on_click=do_backup),
            status,
        )

    # ── theme ─────────────────────────────────────────────────

    def _theme_card(self) -> ft.Container:
        def on_theme(e):
            self.app.set_theme_mode(e.control.value)

        return card(
            dropdown(
                "Тема",
                [("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")],
                self.app.prefs.get("theme_mode") or "system",
                on_select=on_theme,
                width=220,
            )
        )

    # ── updates ───────────────────────────────────────────────

    def _updates_card(self) -> ft.Container:
        current = self.app.service.current_version()

        auto = ft.Switch(
            label="Проверять обновления при запуске",
            value=bool(self.app.prefs.get("check_updates_on_start")),
            active_color=COLORS["accent"],
            on_change=lambda e: self.app.prefs.update(check_updates_on_start=e.control.value),
        )

        def check(e):
            from .. import update_ui

            update_ui.check_now(self.app)

        return card(
            hint(f"Текущая версия: {current}"),
            auto,
            ft.FilledButton("Проверить обновления", icon=ft.Icons.SYSTEM_UPDATE, on_click=check),
            hint("Автоматическое обновление работает только в собранной версии (.exe)."),
        )
