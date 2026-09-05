#!/usr/bin/env python3
"""
scripts/check_update.py - Скрипт проверки обновлений из Git.
Проверяет наличие новой версии на удаленном репозитории.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

def get_current_version() -> Optional[str]:
    """Получить текущую версию (commit hash)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()[:7]  # Короткий hash
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_remote_version(branch: str = "main") -> Optional[str]:
    """Получить версию с удаленного репозитория."""
    try:
        # Сначала делаем fetch
        subprocess.run(
            ["git", "fetch", "origin", branch],
            capture_output=True,
            check=True
        )
        
        # Получаем hash последнего коммита на remote
        result = subprocess.run(
            ["git", "rev-parse", f"origin/{branch}"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()[:7]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def has_updates() -> bool:
    """Проверить, есть ли обновления."""
    current = get_current_version()
    remote = get_remote_version()
    
    if not current or not remote:
        return False
    
    return current != remote


def get_commit_messages() -> list[str]:
    """Получить список коммитов между локальной и remote версией."""
    try:
        result = subprocess.run(
            ["git", "log", f"HEAD..origin/main", "--oneline"],
            capture_output=True,
            text=True,
            check=True
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def pull_updates() -> bool:
    """Выполнить git pull для обновления."""
    try:
        print("[INFO] Выполняем обновление из репозитория...")
        subprocess.run(
            ["git", "pull", "origin", "main"],
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[ERROR] Не удалось обновить: {e}")
        return False


def main():
    """Основная функция проверки обновлений."""
    print("=" * 60)
    print("  Finance Calculator - Проверка обновлений")
    print("=" * 60)
    
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    original_dir = Path.cwd()
    
    try:
        import os
        os.chdir(project_root)
        
        # Проверяем, что это git репозиторий
        if not (project_root / ".git").exists():
            print("[INFO] Это не git репозиторий, проверка обновлений невозможна")
            return
        
        current = get_current_version()
        remote = get_remote_version()
        
        print(f"\nТекущая версия: {current or 'неизвестно'}")
        print(f"Версия в репозитории: {remote or 'неизвестно'}")
        
        if not current or not remote:
            print("\n[WARN] Не удалось получить информацию о версиях")
            return
        
        if current == remote:
            print("\n[OK] Установлена последняя версия!")
            return
        
        print(f"\n[INFO] Доступно обновление!")
        
        # Показываем список изменений
        commits = get_commit_messages()
        if commits:
            print("\nСписок изменений:")
            for commit in commits[:10]:  # Показываем максимум 10
                print(f"  - {commit}")
            if len(commits) > 10:
                print(f"  ... и еще {len(commits) - 10} коммитов")
        
        # Спрашиваем подтверждение
        response = input("\nОбновить до последней версии? (y/n): ").strip().lower()
        if response == 'y':
            if pull_updates():
                print("\n[OK] Обновление успешно загружено!")
                print("[INFO] Перезапустите приложение для применения обновлений")
            else:
                print("\n[ERROR] Не удалось выполнить обновление")
                sys.exit(1)
        else:
            print("\n[INFO] Обновление отменено пользователем")
            
    finally:
        import os
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
