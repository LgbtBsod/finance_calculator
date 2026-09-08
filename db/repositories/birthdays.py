"""db.repositories.birthdays — таблица birthdays."""

from __future__ import annotations

from db.repositories.base import _Repo
from models import BirthdayRow


class BirthdayRepo(_Repo):
    def add_birthday(self, name: str, birth_date: str, gift_amount: float) -> int:
        with self._tx() as c:
            cursor = c.execute(
                "INSERT INTO birthdays (name, birth_date, gift_amount) VALUES (?,?,?)",
                (name, birth_date, gift_amount),
            )
            return cursor.lastrowid

    def get_birthdays(self) -> list[BirthdayRow]:
        with self._tx() as c:
            # birth_date хранится как "ДД.ММ.ГГГГ" (год — заглушка, см.
            # buildBirthDateForApi во фронтенде) — сортировка по строке
            # целиком была бы лексикографической (сначала по дню, а не по
            # месяцу), поэтому явно сортируем по месяцу, затем по дню.
            rows = c.execute(
                "SELECT id, name, birth_date, gift_amount FROM birthdays "
                "ORDER BY substr(birth_date, 4, 2), substr(birth_date, 1, 2)"
            ).fetchall()
            return [BirthdayRow(**dict(r)) for r in rows]

    def delete_birthday(self, bid: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM birthdays WHERE id=?", (bid,))

    def update_birthday(
        self,
        bid: int,
        name: str,
        birth_date: str,
        gift_amount: float,
    ) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE birthdays SET name=?, birth_date=?, gift_amount=? WHERE id=?",
                (name, birth_date, gift_amount, bid),
            )
