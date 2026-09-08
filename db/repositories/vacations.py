"""db.repositories.vacations — таблица vacations (отпускные)."""

from __future__ import annotations

from db.repositories.base import _Repo
from models import VacationRow


class VacationRepo(_Repo):
    def add_vacation(
        self,
        total_amount: float,
        payout_date: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> int:
        with self._tx() as c:
            cursor = c.execute(
                "INSERT INTO vacations (total_amount, payout_date, start_date, end_date) "
                "VALUES (?,?,?,?)",
                (total_amount, payout_date, start_date or payout_date, end_date or payout_date),
            )
            return cursor.lastrowid

    def get_vacations(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> list[VacationRow]:
        with self._tx() as c:
            if month is not None and year is not None:
                rows = c.execute(
                    "SELECT id, total_amount, payout_date, start_date, end_date FROM vacations "
                    "WHERE strftime('%m', payout_date)=? "
                    "AND strftime('%Y', payout_date)=? "
                    "ORDER BY payout_date",
                    (f"{month:02d}", str(year)),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, total_amount, payout_date, start_date, end_date FROM vacations "
                    "ORDER BY payout_date"
                ).fetchall()
            return [VacationRow(**dict(r)) for r in rows]

    def delete_vacation(self, vid: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM vacations WHERE id=?", (vid,))
