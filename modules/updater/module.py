"""UpdaterModule — обёртка над updater.AutoUpdater для проверки обновлений.

Rate-limit (не чаще раза в 30 мин на IP — лимит GitHub API) инкапсулирован
здесь: action ``check`` сам сверяется с отметкой и ставит её.
"""

from __future__ import annotations

from core.module import Module
from updater import (
    AutoUpdater,
    _mark_checked,
    _recently_checked,
    get_current_version,
)


class UpdaterModule(Module):
    name = "updater"

    def initialize(self) -> None:
        self._actions = {
            "check": self._check,
            "current_version": self._current_version,
        }

    def _current_version(self) -> str:
        return get_current_version()

    def _check(self, force: bool = False) -> dict:
        """(has_update, version, url) + флаги сети. Пропускает проверку, если
        она уже была за последние 30 минут (кроме force)."""
        if not force and _recently_checked():
            return {
                "has_update": False, "version": None, "url": None,
                "rate_limited": False, "reachable": True, "skipped": True,
            }
        updater = AutoUpdater(current_version=get_current_version())
        has_update, version, url = updater.check_for_updates()
        if not updater._rate_limited and updater._network_reachable:
            _mark_checked()
        return {
            "has_update": bool(has_update),
            "version": version,
            "url": url,
            "rate_limited": updater._rate_limited,
            "reachable": updater._network_reachable,
            "skipped": False,
        }
