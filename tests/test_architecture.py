"""Статическая гарантия модульной изоляции — AST-анализ импортов, без импорта самих модулей.

Инвариант: модули общаются ТОЛЬКО через ядро.
  - ни один modules/<X> не импортирует modules/<Y>;
  - modules/<X> импортирует только: свой пакет, stdlib/third-party, core.*,
    models, config, paths, и СВОЙ легаси-модуль (по allowlist ниже);
  - services.py импортирует только core.* + stdlib (не modules, не легаси);
  - легаси (database/calculator/prod_calendar/models/config) не импортируют core/modules;
  - вне tests/ и core/ нет обращений к kernel.get_module / kernel._modules.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STDLIB = set(sys.stdlib_module_names)
THIRD_PARTY = {"flet", "packaging", "certifi", "pdfplumber", "work_calendar", "pydantic",
               "pydantic_settings", "dotenv"}

# Каждому модулю разрешён ровно один «свой» легаси-модуль.
LEGACY_ALLOW = {
    "db": {"database"},
    "cache": set(),
    "calendar": {"prod_calendar"},
    "calculator": {"calculator"},
    "birthdays": {"calculator"},
    "finance": set(),
    "updater": {"updater"},
}
COMMON_ALLOW = {"core", "models", "config", "paths"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _module_files(pkg: str) -> list[Path]:
    return list((ROOT / "modules" / pkg).rglob("*.py"))


def test_no_cross_module_imports():
    pkgs = [p.name for p in (ROOT / "modules").iterdir() if p.is_dir() and p.name != "__pycache__"]
    for pkg in pkgs:
        allowed = COMMON_ALLOW | STDLIB | THIRD_PARTY | {"modules"} | LEGACY_ALLOW.get(pkg, set())
        for f in _module_files(pkg):
            for root in _imports(f):
                assert root in allowed, (
                    f"{f.relative_to(ROOT)} импортирует '{root}' — не в allowlist модуля '{pkg}'"
                )


def test_modules_never_import_each_other_by_name():
    pkgs = {p.name for p in (ROOT / "modules").iterdir() if p.is_dir()}
    for pkg in pkgs:
        for f in _module_files(pkg):
            tree = ast.parse(f.read_text(encoding="utf-8"), str(f))
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                elif isinstance(node, ast.Import):
                    mod = node.names[0].name
                if mod and mod.startswith("modules."):
                    other = mod.split(".")[1]
                    assert other == pkg, (
                        f"{f.relative_to(ROOT)}: модуль '{pkg}' импортирует '{mod}' (соседа)"
                    )


def test_services_facade_imports_only_core():
    allowed = {"core", "services"} | STDLIB | THIRD_PARTY
    for root in _imports(ROOT / "services.py"):
        assert root in allowed, f"services.py импортирует '{root}' — фасад должен знать только core"


def test_legacy_stays_kernel_agnostic():
    for name in ("database", "calculator", "prod_calendar", "models", "config"):
        roots = _imports(ROOT / f"{name}.py")
        assert "core" not in roots, f"{name}.py импортирует core — легаси должно быть kernel-free"
        assert "modules" not in roots, f"{name}.py импортирует modules"


def test_no_get_module_outside_tests_and_core():
    for f in ROOT.rglob("*.py"):
        rel = f.relative_to(ROOT)
        parts = rel.parts
        if parts[0] in ("tests", "core", "venv", ".venv"):
            continue
        text = f.read_text(encoding="utf-8")
        assert "get_module(" not in text, f"{rel}: обращение к get_module вне tests/core"
        assert "._modules" not in text, f"{rel}: обращение к _modules вне tests/core"
