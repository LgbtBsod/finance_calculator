#!/bin/bash
set -e

echo "============================================"
echo "  Личный финансовый калькулятор (Flet)"
echo "============================================"

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 не найден. Установите Python 3.12+."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[1/3] Создание виртуального окружения..."
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "[2/3] Установка зависимостей..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo "[3/3] Запуск приложения (откроется вкладка браузера). Ctrl+C — остановить."
python main.py
