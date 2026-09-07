"""Экран «Аналитика»: сумма за период, тренд по месяцам, расходы по категориям."""

from __future__ import annotations

import flet as ft

from ..format import MONTH_NAMES_RU, format_currency, pluralize_ru
from ..theme import COLORS
from ..widgets import (
    card,
    empty_state,
    hint,
    money_text,
    month_dropdown,
    section_title,
    year_dropdown,
)
from ._base import View

_TREND_MONTHS = 6


class AnalyticsView(View):
    title = "Аналитика"

    def content(self) -> list[ft.Control]:
        summary = self.svc.analytics_summary(self.month, self.year)
        trend = self.svc.analytics_trend(self.month, self.year, _TREND_MONTHS)["months"]

        picker = card(
            ft.Row(
                [month_dropdown(self.month, self._set_month),
                 year_dropdown(self.year, self._set_year)],
                spacing=12,
            )
        )

        total_card = card(
            ft.Text("💰 Общие расходы за период", size=13, color=COLORS["text_secondary"]),
            money_text(summary["total"], size=28),
            hint(f"{summary['count']} "
                 f"{pluralize_ru(summary['count'], 'запись', 'записи', 'записей')}"),
            bgcolor=COLORS["accent_bg"],
        )

        blocks: list[ft.Control] = [picker, total_card,
                                    section_title("Тренд по месяцам"), self._trend_chart(trend)]

        blocks.append(section_title("Расходы по категориям"))
        if not summary["categories"]:
            blocks.append(card(empty_state("📊 Нет данных для отображения")))
        else:
            blocks.append(self._categories(summary["categories"], summary["total"]))
        return blocks

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
                            *([ft.Text("⚠️ превышен лимит", size=11, color=COLORS["danger"])]
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
