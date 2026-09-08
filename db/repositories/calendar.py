"""db.repositories.calendar — производственный календарь (кэш) и поправки к нему.

Объединяет таблицы ``calendar_data`` и ``calendar_corrections``: у них общие
границы года/месяца и один тест-класс.
"""

from __future__ import annotations

from db.repositories.base import _Repo
from models import CalendarRow, CorrectionRow


class CalendarRepo(_Repo):
    # ── границы ──────────────────────────────────────────────

    @staticmethod
    def _year_bounds(year: int) -> tuple[str, str]:
        return f"{year:04d}-01-01", f"{year + 1:04d}-01-01"

    @staticmethod
    def _month_bounds(year: int, month: int) -> tuple[str, str]:
        nxt = (year + 1, 1) if month == 12 else (year, month + 1)
        return f"{year:04d}-{month:02d}-01", f"{nxt[0]:04d}-{nxt[1]:02d}-01"

    # ── calendar_data ───────────────────────────────────────

    def calendar_needs_fill(self, year: int) -> bool:
        lo, hi = self._year_bounds(year)
        with self._tx() as c:
            n = c.execute(
                "SELECT COUNT(*) AS c FROM calendar_data WHERE date >= ? AND date < ?",
                (lo, hi),
            ).fetchone()["c"]
            return n == 0

    def save_calendar_data(self, year: int, rows: list[tuple]) -> None:
        with self._tx() as c:
            c.executemany(
                "INSERT OR REPLACE INTO calendar_data "
                "(date, is_working, is_holiday, is_shortened) VALUES (?, ?, ?, ?)",
                rows,
            )

    def clear_calendar_cache(self, year: int) -> None:
        lo, hi = self._year_bounds(year)
        with self._tx() as c:
            c.execute("DELETE FROM calendar_data WHERE date >= ? AND date < ?", (lo, hi))

    def get_calendar_month(self, year: int, month: int) -> list[CalendarRow]:
        lo, hi = self._month_bounds(year, month)
        with self._tx() as c:
            rows = c.execute(
                "SELECT date, is_working, is_holiday, is_shortened "
                "FROM calendar_data WHERE date >= ? AND date < ? ORDER BY date",
                (lo, hi),
            ).fetchall()
            return [CalendarRow(**dict(r)) for r in rows]

    # ── calendar_corrections ────────────────────────────────

    def get_corrections(self) -> list[CorrectionRow]:
        with self._tx() as c:
            rows = c.execute(
                "SELECT date, kind, source FROM calendar_corrections ORDER BY date"
            ).fetchall()
            return [CorrectionRow(**dict(r)) for r in rows]

    def save_corrections(self, year: int, rows: list[tuple]) -> None:
        """rows = [(date_iso, kind, source), ...]"""
        lo, hi = self._year_bounds(year)
        with self._tx() as c:
            c.execute(
                "DELETE FROM calendar_corrections WHERE date >= ? AND date < ?", (lo, hi)
            )
            if rows:
                c.executemany(
                    "INSERT OR REPLACE INTO calendar_corrections "
                    "(date, kind, source) VALUES (?, ?, ?)",
                    rows,
                )
