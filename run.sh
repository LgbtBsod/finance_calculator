#!/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 не найден. Установите Python 3.12+."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

# Вся логика запуска — в scripts/launch.py (обновление pip/зависимостей,
# проверка обновлений кода, старт приложения). Аргументы пробрасываются.
python scripts/launch.py "$@"
