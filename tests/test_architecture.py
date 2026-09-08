"""Статическая гарантия модульной изоляции — AST-анализ импортов, без импорта самих модулей.

Инвариант: модули общаются ТОЛЬКО через ядро.
  - ни один modules/<X> не импортирует modules/<Y> (в т.ч. относительным импортом);
  - modules/<X> импортирует только: свой пакет, stdlib/third-party, core.*,
    models, config, paths, и СВОЙ легаси-модуль (по allowlist ниже);
  - services.py импортирует только core.* + stdlib (не modules, не легаси);
  - легаси (database/calculator/prod_calendar/models/config) не импортируют core/modules;
  - вне tests/ и core/ нет обращений к внутренностям ядра
    (get_module / _modules / _kernel) и нет динамических импортов (importlib / __import__).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STDLIB = set(sys.stdlib_module_names)
THIRD_PARTY = {"flet", "packaging", "certifi", "pdfplumber", "work_calendar", "openpyxl"}

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


def _resolve(node: ast.ImportFrom, file: Path) -> str | None:
    """Корневой пакет импорта, с учётом относительного уровня."""
    if node.level == 0:
        return node.module.split(".")[0] if node.module else None
    # относительный: подняться на (level-1) от пакета файла
    pkg = file.resolve().parent
    for _ in range(node.level - 1):
        pkg = pkg.parent
    rel = pkg.relative_to(ROOT)
    base = list(rel.parts)
    if node.module:
        base += node.module.split(".")
    return ".".join(base).split(".")[0] if base else None


def _import_targets(path: Path) -> set[str]:
    """Полные dotted-пути всех импортов (для проверки соседей)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                out.add(node.module)
            else:
                pkg = path.resolve().parent
                for _ in range(node.level - 1):
                    pkg = pkg.parent
                base = ".".join(pkg.relative_to(ROOT).parts)
                out.add(f"{base}.{node.module}" if node.module else base)
    return out


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            r = _resolve(node, path)
            if r:
                roots.add(r)
    return roots


def _module_files(pkg: str) -> list[Path]:
    return [p for p in (ROOT / "modules" / pkg).rglob("*.py") if "__pycache__" not in p.parts]


def _pkgs() -> list[str]:
    return [p.name for p in (ROOT / "modules").iterdir()
            if p.is_dir() and p.name != "__pycache__"]


def test_no_cross_module_imports():
    for pkg in _pkgs():
        allowed = COMMON_ALLOW | STDLIB | THIRD_PARTY | {"modules"} | LEGACY_ALLOW.get(pkg, set())
        for f in _module_files(pkg):
            for root in _import_roots(f):
                assert root in allowed, (
                    f"{f.relative_to(ROOT)} импортирует '{root}' — не в allowlist модуля '{pkg}'"
                )


def test_modules_never_import_each_other_by_name():
    for pkg in _pkgs():
        for f in _module_files(pkg):
            for target in _import_targets(f):
                if target.startswith("modules.") and target.split(".")[1] != pkg:
                    raise AssertionError(
                        f"{f.relative_to(ROOT)}: модуль '{pkg}' импортирует '{target}' (соседа)"
                    )


def test_services_facade_imports_only_core():
    allowed = {"core", "services"} | STDLIB | THIRD_PARTY
    for root in _import_roots(ROOT / "services.py"):
        assert root in allowed, f"services.py импортирует '{root}' — фасад должен знать только core"


def test_legacy_stays_kernel_agnostic():
    for name in ("database", "calculator", "prod_calendar", "models", "config"):
        roots = _import_roots(ROOT / f"{name}.py")
        assert "core" not in roots, f"{name}.py импортирует core — легаси должно быть kernel-free"
        assert "modules" not in roots, f"{name}.py импортирует modules"


def test_modules_and_gui_never_touch_kernel_internals():
    """modules/ и gui/ ходят только через KernelView / FinanceService —
    никаких get_module / _modules / _kernel / _order и динамических импортов.
    (services.py и main.py — композиционный корень, им можно держать Kernel.)"""
    forbidden = ("get_module(", "._modules", "._kernel", "._order",
                 "importlib", "__import__(")
    for sub in ("modules", "gui"):
        for f in (ROOT / sub).rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            text = f.read_text(encoding="utf-8")
            for token in forbidden:
                assert token not in text, (
                    f"{f.relative_to(ROOT)}: запрещённое обращение '{token}'"
                )
