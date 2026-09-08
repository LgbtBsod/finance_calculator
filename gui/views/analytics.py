"""Экран «Аналитика»: сумма за период, тренд, категории, изменение к прошлому
месяцу, экспорт CSV."""

from __future__ import annotations

import flet as ft

from ..format import MONTH_NAMES_RU, format_currency, pluralize_ru
from ..theme import COLORS
from ..widgets import (
    card,
    empty_state,
    ghost_button,
    hint,
    money_text,
    month_dropdown,
    section_title,
    switch_row,
    year_dropdown,
)
from ._base import View


def _signed(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + format_currency(abs(v))

_TREND_MONTHS = 6


class AnalyticsView(View):
    title = "Аналитика"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.all_time = False

    def content(self) -> list[ft.Control]:
        if self.all_time:
            summary = self.svc.analytics_summary()          # None, None -> за всё время
        else:
            summary = self.svc.analytics_summary(self.month, self.year)
        trend = self.svc.analytics_trend(self.month, self.year, _TREND_MONTHS)["months"]

        picker = card(
            ft.Row(
                [month_dropdown(self.month, self._set_month),
                 year_dropdown(self.year, self._set_year),
                 switch_row("За всё время", self.all_time, self._toggle_all_time)],
                spacing=12, wrap=True,
            )
        )

        total_card = card(
            ft.Text("Общие расходы " + ("за всё время" if self.all_time else "за период"),
                    size=13, color=COLORS["text_secondary"]),
            money_text(summary["total"], size=28),
            hint(f"{summary['count']} "
                 f"{pluralize_ru(summary['count'], 'запись', 'записи', 'записей')}"),
            bgcolor=COLORS["accent_bg"],
        )

        blocks: list[ft.Control] = [picker, total_card,
                                    section_title("Тренд по месяцам"), self._trend_chart(trend)]

        if not self.all_time:
            blocks += [section_title("Изменение к прошлому месяцу"),
                       self._diff_card(self.svc.category_diff(self.month, self.year))]

        blocks.append(section_title(
            "Расходы по категориям — за всё время" if self.all_time
            else "Расходы по категориям"
        ))
        if not summary["categories"]:
            blocks.append(card(empty_state("Нет данных для отображения")))
        else:
            blocks.append(self._categories(summary["categories"], summary["total"]))

        blocks.append(card(
            hint("Выгрузить все записи (расходы, доходы, отпускные, долги) в CSV — "
                 "открывается в Excel / Google Таблицах."),
            ft.Row([
                ghost_button("Экспорт за период", lambda e: self._export(self.month, self.year),
                             icon=ft.Icons.DOWNLOAD_OUTLINED),
                ghost_button("Экспорт за всё время", lambda e: self._export(None, None),
                             icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED),
            ], spacing=8, wrap=True),
        ))
        return blocks

    def _export(self, month, year) -> None:
        from datetime import date

        from paths import app_dir, open_in_file_manager

        try:
            text = self.svc.export_csv(month=month, year=year)
            out_dir = app_dir / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            tag = f"{year}-{month:02d}" if month and year else "all"
            path = out_dir / f"finance-{tag}-{date.today():%Y%m%d}.csv"
            path.write_text(text, encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            self.toast(f"Не удалось экспортировать: {exc}", error=True)
            return
        self.toast(f"Сохранено: {path.name}")
        open_in_file_manager(path.parent)

    def _diff_card(self, diff: dict) -> ft.Container:
        total = diff["totalDelta"]
        colr = COLORS["danger"] if total > 0 else COLORS["success"] if total < 0 else COLORS["text"]
        head = ft.Row(
            [
                ft.Text(f"{MONTH_NAMES_RU[diff['prevMonth']]} → {MONTH_NAMES_RU[diff['month']]}",
                        size=12, color=COLORS["text_secondary"]),
                ft.Text(_signed(total), size=16, weight=ft.FontWeight.W_700, color=colr),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        rows: list[ft.Control] = [head, ft.Divider(height=8, color=COLORS["border"])]
        movers = [c for c in diff["categories"] if abs(c["delta"]) >= 1][:6]
        if not movers:
            rows.append(hint("Расходы по категориям почти не изменились."))
        for c in movers:
            d = c["delta"]
            rows.append(ft.Row(
                [
                    ft.Row([ft.Container(width=8, height=8, bgcolor=c["color"], border_radius=999),
                            ft.Text(c["name"], size=12, color=COLORS["text"])], spacing=6),
                    ft.Text(_signed(d), size=12, weight=ft.FontWeight.W_600,
                            color=COLORS["danger"] if d > 0 else COLORS["success"]),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ))
        return card(ft.Column(rows, spacing=6, tight=True))

    def _toggle_all_time(self, e) -> None:
        self.all_time = e.control.value
        self.reload()

    def _trend_chart(self, months: list[dict]) -> ft.Container:
        peak = max((m["total"] for m in months), default=0) or 1
        bars = []
        for m in months:
            h = max(4, round(m["total"] / peak * 140))
            bars.append(
                ft.Column(
                    [
                        ft.Text(format_currency(m["total"]), size=10,
                                color=COLORS["text_secondary"]),
                        ft.Container(
                            width=34, height=h, bgcolor=COLORS["accent"],
                            border_radius=ft.BorderRadius(top_left=4, top_right=4,
                                                         bottom_left=0, bottom_right=0),
                        ),
                        ft.Text(MONTH_NAMES_RU[m["month"]][:3], size=10,
                                color=COLORS["text_secondary"]),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )
            )
        return card(
            ft.Row(bars, alignment=ft.MainAxisAlignment.SPACE_AROUND,
                   vertical_alignment=ft.CrossAxisAlignment.END)
        )

    def _categories(self, categories: list[dict], total: float) -> ft.Container:
        rows: list[ft.Control] = []
        for c in categories:
            limit = c["monthlyLimit"]
            over = limit is not None and c["amount"] > limit
            head = ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(width=12, height=12, bgcolor=c["color"], border_radius=999),
                            ft.Text(c["name"], size=13, color=COLORS["text"]),
                            *([ft.Text("превышен лимит", size=11, color=COLORS["danger"])]
                              if over else []),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        format_currency(c["amount"])
                        + (f" / {format_currency(limit)}" if limit is not None else ""),
                        size=13, weight=ft.FontWeight.W_600,
                        color=COLORS["danger"] if over else COLORS["text"],
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            rows.append(head)
            frac = (c["amount"] / limit) if limit else (c["amount"] / total if total else 0)
            rows.append(
                ft.ProgressBar(
                    value=max(0.02, min(1.0, frac)), bar_height=6,
                    color=COLORS["danger"] if over else COLORS["accent"],
                    bgcolor=COLORS["surface_alt"],
                )
            )
        return card(ft.Column(rows, spacing=8, tight=True))
