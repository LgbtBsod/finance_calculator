"""Finance Calculator — сборка standalone-исполняемого файла через PyInstaller.

    python build.py                # onefile-сборка под текущую ОС
    python build.py --onedir       # сборка папкой (быстрее холодный старт)
    python build.py --clean        # сначала стереть build/ и dist/
    python build.py --no-deps      # пропустить установку зависимостей

Вывод:
    Windows : dist/FinanceCalculator.exe
    Linux   : dist/FinanceCalculator
    macOS   : dist/FinanceCalculator

Приложение запускает Flet в web-browser режиме: запуск exe поднимает локальный
сервер и открывает браузер на http://localhost:8420.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
NAME = "FinanceCalculator"

BUILD_DEPS = [
    "pyinstaller>=6.10",
    "flet[web]==0.86.5",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    "packaging>=23.0",
    "certifi>=2024.2.2",
    "work-calendar>=1.1",
    "pdfplumber>=0.10.0",
]


def info(m):
    print(f"[INFO] {m}")


def err(m):
    print(f"[ERROR] {m}")


def install_deps() -> None:
    info("Installing / verifying build dependencies...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", *BUILD_DEPS], timeout=1200)
    if r.returncode != 0:
        err("Dependency install failed.")
        sys.exit(1)
    probe = subprocess.run(
        [sys.executable, "-c",
         "import flet, flet_web, pydantic, packaging, certifi, work_calendar, PyInstaller"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        err(f"Post-install import check failed:\n{probe.stderr}")
        sys.exit(1)


def main() -> None:
    os.chdir(APP_DIR)
    args = sys.argv[1:]
    onedir = "--onedir" in args

    print("=" * 60)
    print(f"  {NAME} — PyInstaller ({sys.platform}, py{sys.version_info.major}.{sys.version_info.minor})")
    print("=" * 60)

    if "--no-deps" not in args:
        install_deps()

    if "--clean" in args:
        for d in ("build", "dist"):
            shutil.rmtree(APP_DIR / d, ignore_errors=True)
        info("Cleaned build/ and dist/")

    empty_view = APP_DIR / "build" / "_no_flet_view"
    empty_view.mkdir(parents=True, exist_ok=True)
    os.environ["FLET_VIEW_PATH"] = str(empty_view)

    sep = os.pathsep
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", NAME,
        "--onedir" if onedir else "--onefile",
        "--add-data", f"version.txt{sep}.",
        "--collect-all", "flet",
        "--collect-all", "flet_web",
        "--collect-all", "certifi",
        "--collect-submodules", "gui",
        "--collect-data", "work_calendar",
        "--exclude-module", "flet_desktop",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--noupx",
    ]
    if sys.platform == "win32":
        cmd += ["--windowed"]
    cmd.append("main.py")

    info("Running PyInstaller...")
    print("  " + " ".join(cmd))
    r = subprocess.run(cmd, timeout=2400)
    if r.returncode != 0:
        err("PyInstaller failed.")
        sys.exit(1)

    dist = APP_DIR / "dist"
    try:
        dst = (dist / NAME / "version.txt") if onedir else (dist / "version.txt")
        shutil.copy2(APP_DIR / "version.txt", dst)
    except OSError:
        pass

    ext = ".exe" if sys.platform == "win32" else ""
    exe = (dist / NAME / (NAME + ext)) if onedir else (dist / (NAME + ext))
    print("=" * 60)
    if exe.exists():
        print(f"  BUILD OK -> {exe}   ({exe.stat().st_size / 1e6:.0f} MB)")
    else:
        err("Build finished but no executable found in dist/.")
        sys.exit(1)
    print("  budget.db хранится рядом с exe и не трогается обновлением.")
    print("=" * 60)


if __name__ == "__main__":
    main()
