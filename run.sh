#!/bin/bash
set -e
cd "$(dirname "$0")"

# Предпочитаем протестированную версию (см. requirements.txt, CI — 3.14),
# если она есть, вместо первого попавшегося python3: слишком новая версия
# может остаться без готовых wheel-пакетов под зависимости flet.
PY_CMD=""
for v in 3.14 3.13 3.12; do
    if command -v "python$v" &> /dev/null; then
        PY_CMD="python$v"
        break
    fi
done
if [ -z "$PY_CMD" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "[ERROR] python3 не найден. Установите Python 3.12-3.14."
        exit 1
    fi
    PY_CMD="python3"
fi

if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения ($PY_CMD)..."
    "$PY_CMD" -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

# Вся логика запуска — в scripts/launch.py (обновление pip/зависимостей,
# проверка обновлений кода, старт приложения). Аргументы пробрасываются.
python scripts/launch.py "$@"
