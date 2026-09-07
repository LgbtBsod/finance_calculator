"""CalendarModule — обёртка над prod_calendar.CalendarService.

CalendarService принимает 8 callable доступа к БД. Здесь они собираются как
замыкания над ``self.k.request("db", ...)`` — сосед (модуль db) в конструктор
CalendarService не передаётся, только kernel-backed функции.
"""

from __future__ import annotations

from datetime import date, timedelta

from core.module import Module
from models import CalendarRow, CorrectionRow
from prod_calendar import CalendarService


class CalendarModule(Module):
    name = "calendar"
    requires = ("db",)

    def __init__(self) -> None:
        super().__init__()
        self.service: CalendarService | None = None

    def initialize(self) -> None:
        k = self.k
        self.service = CalendarService(
            get_setting=lambda key: k.request("db", "get_setting", key=key),
            set_setting=lambda key, value: k.request("db", "set_setting", key=key, value=value),
            get_corrections=lambda: [
                CorrectionRow(**r) for r in k.request("db", "get_corrections")
            ],
            save_corrections=lambda year, rows: k.request(
                "db", "save_corrections", year=year, rows=[list(r) for r in rows]
            ),
            clear_calendar_cache=lambda year: k.request(
                "db", "clear_calendar_cache", year=year
            ),
            calendar_needs_fill=lambda year: k.request(
                "db", "calendar_needs_fill", year=year
            ),
            save_calendar_data=lambda year, rows: k.request(
                "db", "save_calendar_data", year=year, rows=[list(r) for r in rows]
            ),
            get_calendar_month=lambda year, month: [
                CalendarRow(**r)
                for r in k.request("db", "get_calendar_month", year=year, month=month)
            ],
        )
        self._actions = {
            "get_working_days": self._get_working_days,
            "classify_day": self._classify_day,
            "classify_range": self._classify_range,
            "build_and_cache_year": self._build_and_cache_year,
            "get_monthly_info": self._get_monthly_info,
            "available_years": self._available_years,
            "import_pdf": self._import_pdf,
        }

    # ── actions ──────────────────────────────────────────────

    def _get_working_days(self, year: int, month: int) -> list[float]:
        total, h1, h2 = self.service.get_working_days(year, month)
        return [total, h1, h2]

    def _classify_day(self, iso: str) -> str:
        return str(self.service.classify_day(date.fromisoformat(iso)))

    def _classify_range(self, start: str, end: str) -> dict[str, str]:
        d, last = date.fromisoformat(start), date.fromisoformat(end)
        out: dict[str, str] = {}
        while d <= last:
            out[d.isoformat()] = str(self.service.classify_day(d))
            d += timedelta(days=1)
        return out

    def _build_and_cache_year(self, year: int) -> None:
        self.service.build_and_cache_year(year)

    def _get_monthly_info(self, year: int, month: int) -> list[dict]:
        return [dict(r) for r in self.service.get_monthly_info(year, month)]

    def _available_years(self) -> list[int]:
        return list(self.service.available_years())

    def _import_pdf(self, pdf_path: str) -> dict | None:
        result = self.service.import_pdf(pdf_path)
        if result is None:
            return None
        self.k.emit("calendar:changed", year=result.year)
        return {
            "year": result.year,
            "extra_holidays": [d.isoformat() for d in sorted(result.extra_holidays)],
            "shortened_days": [d.isoformat() for d in sorted(result.shortened_days)],
            "monthly_working_days": dict(result.monthly_working_days),
        }

    def shutdown(self) -> None:
        self.service = None

    # helper для внутренних нужд (не action)
    def refresh(self) -> None:
        if self.service is not None:
            self.service.refresh_provider()
