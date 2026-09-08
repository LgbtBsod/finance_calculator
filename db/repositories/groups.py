"""db.repositories.groups — таблица expense_groups (категории расходов)."""

from __future__ import annotations

from db.query import _UNSET, build_update
from db.repositories.base import _Repo


class ExpenseGroupRepo(_Repo):
    def create_expense_group(
        self,
        group_id: str,
        name: str,
        color: str,
        parent_id: str | None = None,
        sort_order: int = 0,
        monthly_limit: float | None = None,
    ) -> None:
        with self._tx(invalidates=("expense_groups",)) as c:
            c.execute(
                "INSERT INTO expense_groups (id, name, color, parent_id, sort_order, monthly_limit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (group_id, name, color, parent_id, sort_order, monthly_limit),
            )

    def get_expense_groups(self) -> list[dict]:
        """Горячее целотабличное чтение (finance дёргает его на каждый
        analytics/trend) -> read-through кэш; сортировка кэшируется пост-запрос,
        на выход — свежие dict'ы (finance по ним строит {id: g} и мутирует g)."""
        return [dict(r) for r in self._engine.read_cached("expense_groups", self._load_groups)]

    def _load_groups(self) -> list[dict]:
        with self._tx() as c:
            rows = c.execute(
                "SELECT id, name, color, parent_id, sort_order, monthly_limit "
                "FROM expense_groups ORDER BY sort_order, name"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_expense_group(self, group_id: str) -> dict | None:
        with self._tx() as c:
            row = c.execute(
                "SELECT id, name, color, parent_id, sort_order, monthly_limit "
                "FROM expense_groups WHERE id=?",
                (group_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_expense_group(
        self,
        group_id: str,
        name: str | None = None,
        color: str | None = None,
        parent_id: str | None | object = _UNSET,
        sort_order: int | None = None,
        monthly_limit: float | None | object = _UNSET,
    ) -> None:
        """parent_id/monthly_limit — трёхзначные поля (см. update_expense):
        `_UNSET` по умолчанию значит "не менять", явный `None` — "снять
        значение" (нужно, например, чтобы разгруппировать подкатегорию или
        убрать лимит у группы). Порядок ключей = порядку старого ручного
        конструктора -> строка SQL не изменилась."""
        sql, params = build_update("expense_groups", {
            "name": name if name is not None else _UNSET,
            "color": color if color is not None else _UNSET,
            "parent_id": parent_id,
            "sort_order": sort_order if sort_order is not None else _UNSET,
            "monthly_limit": monthly_limit,
        }, {"id": group_id})
        if sql is None:
            return
        with self._tx(invalidates=("expense_groups",)) as c:
            c.execute(sql, params)

    def delete_expense_group(self, group_id: str) -> None:
        """Удаляет группу; расходы этой группы не удаляются — становятся
        "без группы" (group_id=NULL), иначе удаление упало бы с
        FOREIGN KEY constraint failed при наличии ссылающихся расходов."""
        with self._tx(invalidates=("expense_groups",)) as c:
            c.execute("UPDATE expenses SET group_id=NULL WHERE group_id=?", (group_id,))
            c.execute("DELETE FROM expense_groups WHERE id=?", (group_id,))
