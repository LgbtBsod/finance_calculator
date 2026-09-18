@echo off
title Finance Calculator
setlocal

cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" goto :have_venv

REM Prefer a tested Python version (see requirements.txt, CI: 3.14) via
REM py-launcher instead of blindly using the first "python" on PATH -- a
REM too-new interpreter may have no prebuilt wheels yet for flet's deps.
set "PY_CMD="
where py >nul 2>&1
if errorlevel 1 goto :no_launcher

py -3.14 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.14"
    goto :python_picked
)
py -3.13 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.13"
    goto :python_picked
)
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.12"
    goto :python_picked
)

:no_launcher
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12-3.14: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [WARN] No Python 3.12-3.14 found via py-launcher.
echo [WARN] Using python from PATH. If it is newer than 3.14, flet may
echo [WARN] have no prebuilt wheels yet and dependency install may fail.
echo [WARN] Install Python 3.14 from python.org for best compatibility.
set "PY_CMD=python"

:python_picked
echo Creating virtual environment using: %PY_CMD%
%PY_CMD% -m venv venv

:have_venv
call venv\Scripts\activate

REM All startup logic lives in scripts\launch.py.
python scripts\launch.py %*

pause
