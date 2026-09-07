"""Настройки самого GUI (тема, автопроверка обновлений) — маленький JSON-файл
рядом с приложением, независимый от budget.db.

Салярные настройки (зарплата/налог/метод расчёта и т.п.) живут в БД и
редактируются на экране «Настройки» — здесь их нет.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    "theme_mode": "system",          # system | light | dark
    "check_updates_on_start": True,
    "skipped_update_version": "",
    "last_month": 0,                  # 0 -> текущий
    "last_year": 0,
}

_VALID_THEME = {"system", "light", "dark"}


class Prefs:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k in _DEFAULTS:
                    if k in raw:
                        self.data[k] = raw[k]
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass
        if self.data.get("theme_mode") not in _VALID_THEME:
            self.data["theme_mode"] = "system"

    def get(self, key: str) -> Any:
        return self.data.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def update(self, **kwargs: Any) -> None:
        self.data.update(kwargs)
        self.save()

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            log.warning("Не удалось сохранить настройки GUI: %s", exc)
