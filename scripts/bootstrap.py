#!/usr/bin/env python3
"""
scripts/bootstrap.py - Скрипт инициализации и обновления зависимостей.
Запускается перед основным приложением.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Выполнить команду и вернуть результат."""
    print(f"\n[INFO] {description}...")
    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print(f"[OK] {description} завершено успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {description} не удалось: {e}")
        return False
    except FileNotFoundError:
        print(f"[ERROR] Команда не найдена: {cmd[0]}")
        return False


def upgrade_pip() -> bool:
    """Обновить pip до последней версии."""
    return run_command(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"], "Обновление pip"
    )


def install_requirements(requirements_file: str = "requirements.txt") -> bool:
    """Установить/обновить зависимости из requirements.txt."""
    req_path = Path(requirements_file)
    if not req_path.exists():
        print(f"[WARN] Файл {requirements_file} не найден, пропускаем установку зависимостей")
        return True

    return run_command(
        [sys.executable, "-m", "pip", "install", "-r", requirements_file, "--upgrade"],
        "Установка зависимостей",
    )


def install_dev_requirements() -> bool:
    """Установить dev-зависимости если есть requirements-dev.txt."""
    req_path = Path("requirements-dev.txt")
    if not req_path.exists():
        return True

    return run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
        "Установка dev-зависимостей",
    )


def build_frontend() -> bool:
    """Собрать frontend если есть dist директория или package.json."""
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("[INFO] Frontend директория не найдена, пропускаем сборку")
        return True

    package_json = frontend_dir / "package.json"
    dist_dir = frontend_dir / "dist"

    if not package_json.exists():
        print("[INFO] package.json не найден, пропускаем сборку frontend")
        return True

    # Если dist уже существует, пропускаем сборку
    if dist_dir.exists():
        print("[INFO] Frontend уже собран (dist существует), пропускаем сборку")
        print("[INFO] Удалите frontend/dist для принудительной пересборки")
        return True

    # Проверяем наличие Node.js
    try:
        subprocess.run(["node", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] Node.js не найден! Установите Node.js 20+ для сборки frontend")
        return False

    print("[INFO] Сборка frontend...")

    # npm install и npm run build
    return (
        run_command(["npm", "install"], "Установка npm зависимостей")
        and run_command(["npm", "run", "build"], "Сборка frontend")
    )


def main():
    """Основная функция bootstrap."""
    print("=" * 60)
    print("  Finance Calculator - Bootstrap Script")
    print("  Инициализация окружения и установка зависимостей")
    print("=" * 60)

    # Определяем рабочую директорию
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    original_dir = Path.cwd()

    try:
        # Переходим в корень проекта
        import os

        os.chdir(project_root)
        print(f"\n[INFO] Рабочая директория: {project_root}")

        # Шаг 1: Обновляем pip
        if not upgrade_pip():
            print("\n[WARN] Не удалось обновить pip, продолжаем...")

        # Шаг 2: Устанавливаем основные зависимости
        if not install_requirements():
            print("\n[ERROR] Критическая ошибка установки зависимостей!")
            sys.exit(1)

        # Шаг 3: Устанавливаем dev-зависимости (опционально)
        install_dev_requirements()

        # Шаг 4: Собираем frontend (если нужно)
        if not build_frontend():
            print("\n[ERROR] Не удалось собрать frontend!")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("  Bootstrap завершен успешно!")
        print("  Все зависимости установлены и обновлены")
        print("=" * 60)

    finally:
        # Возвращаемся в исходную директорию
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
