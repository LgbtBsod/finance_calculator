"""db.repositories.settings — таблица settings (ключ-значение)."""

from __future__ import annotations

from db.repositories.base import _Repo


class SettingsRepo(_Repo):
    def get_setting(self, key: str) -> str:
        with self._tx() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return r["value"] if r else ""

    def get_settings_bundle(self) -> dict[str, str]:
        """Все настройки одним запросом — снапшот для расчётчиков, чтобы не
        дёргать get_setting по ключу десятки раз за один balance(). Горячее
        целотабличное чтение -> read-through кэш в Engine; на выход — копия
        (finance строит по нему свои dict'ы)."""
        return dict(self._engine.read_cached("settings_bundle", self._load_bundle))

    def _load_bundle(self) -> dict[str, str]:
        with self._tx() as c:
            return {
                row["key"]: row["value"]
                for row in c.execute("SELECT key, value FROM settings").fetchall()
            }

    def set_setting(self, key: str, value: str) -> None:
        with self._tx(invalidates=("settings_bundle",)) as c:
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
