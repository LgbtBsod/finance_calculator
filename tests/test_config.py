"""test_config.py — единый источник настроек (config.SETTINGS)."""

from __future__ import annotations

import pytest

from config import SETTINGS, SETTINGS_BY_KEY


class TestSettingSpec:
    def test_every_spec_roundtrips_its_default(self):
        for s in SETTINGS:
            assert s.parse(s.to_str(s.default)) == s.default

    def test_empty_and_none_parse_to_default(self):
        for s in SETTINGS:
            assert s.parse("") == s.default
            assert s.parse(None) == s.default

    def test_bool_specs_serialize_lowercase(self):
        for s in SETTINGS:
            if s.kind == "bool":
                assert s.to_str(True) == "true"
                assert s.to_str(False) == "false"

    def test_camel_and_key_are_unique(self):
        assert len({s.camel for s in SETTINGS}) == len(SETTINGS)
        assert len(SETTINGS_BY_KEY) == len(SETTINGS)

    def test_gui_settings_screen_keys_are_covered(self):
        # camelCase-поля, которые читает gui/views/settings.py (оклад/КЕФ/метод
        # переехали в сущность «доход» kind='salary', здесь их нет).
        gui_fields = {
            "taxRate", "taxProgressive", "advanceCutoffDay", "standardHours",
            "isAdvanceDateInclusive", "accountShortened", "payoutDay1", "payoutDay2",
            "moveWeekendToFriday",
        }
        assert gui_fields <= {s.camel for s in SETTINGS}

    def test_salary_keys_are_not_settings_anymore(self):
        camels = {s.camel for s in SETTINGS}
        assert camels.isdisjoint({"baseSalary", "kef", "salaryCalculationMethod",
                                  "firstHalfRatio", "secondHalfRatio"})


class TestSettingsSSOT:
    def test_seed_defaults_uses_the_spec(self, db):
        for s in SETTINGS:
            assert db.get_setting(s.key) == s.to_str(s.default)

    def test_finance_settings_get_returns_typed_values(self, kernel):
        got = kernel.view("t").request("finance", "settings_get")
        assert got["taxRate"] == 13.0
        assert got["advanceCutoffDay"] == 15 and isinstance(got["advanceCutoffDay"], int)
        assert got["moveWeekendToFriday"] is True
        assert got["taxProgressive"] is False

    def test_finance_settings_update_roundtrips_through_the_spec(self, kernel):
        v = kernel.view("t")
        v.request("finance", "settings_update", updates={
            "taxRate": 15, "moveWeekendToFriday": False, "advanceCutoffDay": 20,
        })
        got = v.request("finance", "settings_get")
        assert got["taxRate"] == 15.0
        assert got["moveWeekendToFriday"] is False
        assert got["advanceCutoffDay"] == 20
        # значение в БД — строка нужного вида
        assert kernel.view("t").request("db", "get_setting", key="move_weekend_to_friday") == "false"


@pytest.mark.parametrize("kind,raw,expected", [
    ("int", "20.0", 20),
    ("float", "0,4", None),   # запятая не парсится float() — GUI сам меняет на точку
])
def test_parse_edge_cases(kind, raw, expected):
    spec = next(s for s in SETTINGS if s.kind == kind)
    if expected is None:
        with pytest.raises(ValueError):
            spec.parse(raw)
    else:
        assert spec.parse(raw) == expected
