@echo off
chcp 65001 >nul
title Finance Calculator (Flet)
setlocal

echo ============================================
echo   Личный финансовый калькулятор (Flet)
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден в PATH. Установите Python 3.12+: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Создание виртуального окружения...
    python -m venv venv
)
call venv\Scripts\activate

echo [2/3] Установка зависимостей...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo [3/3] Запуск приложения (откроется вкладка браузера)...
echo       Ctrl+C — остановить.
python main.py

pause
