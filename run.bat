@echo off
chcp 65001 >nul
title Finance Calculator
setlocal

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден в PATH. Установите Python 3.12+: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo Создание виртуального окружения...
    python -m venv venv
)
call venv\Scripts\activate

REM Вся логика запуска — в scripts\launch.py (обновление pip/зависимостей,
REM проверка обновлений кода, старт приложения). Аргументы пробрасываются.
python scripts\launch.py %*

pause
