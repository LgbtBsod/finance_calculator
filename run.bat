@echo off
chcp 65001 >nul
title Finance Calculator - FastAPI + React
setlocal enabledelayedexpansion

echo ========================================================
echo   Personal Finance Calculator
echo   Architecture: Python FastAPI + React (TypeScript)
echo ========================================================
echo.

REM ============================================
REM Check Python
REM ============================================
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python detected
python --version
echo.

REM ============================================
REM Create and activate Virtual Environment (venv)
REM ============================================
echo [2/6] Setting up Python Virtual Environment...
if not exist "venv\Scripts\activate.bat" (
    echo Creating venv folder...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
) else (
    echo [OK] venv folder already exists.
)

echo Activating venv...
call venv\Scripts\activate
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)
echo.

REM ============================================
REM Run bootstrap script to update dependencies
REM ============================================
echo [3/6] Running bootstrap script...
python scripts\bootstrap.py
if errorlevel 1 (
    echo [WARN] Bootstrap script failed, continuing anyway...
)
echo.

REM ============================================
REM Check for updates from Git
REM ============================================
echo [4/6] Checking for updates...
python scripts\check_update.py
if errorlevel 1 (
    echo [WARN] Update check failed, continuing anyway...
)
echo.

REM ============================================
REM Build frontend (only if not already built)
REM ============================================
echo [5/6] Checking frontend build...
if exist "frontend\dist\index.html" (
    echo [OK] frontend\dist already built - skipping.
    echo      Delete frontend\dist to force a rebuild after pulling changes.
) else (
    echo Frontend not built yet - building now (requires Node.js 20+^)...
    node --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Node.js is not installed or not in PATH!
        echo Please install Node.js 20+: https://nodejs.org/
        pause
        exit /b 1
    )
    pushd frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        popd
        pause
        exit /b 1
    )
    call npm run build
    if errorlevel 1 (
        echo [ERROR] Frontend build failed!
        popd
        pause
        exit /b 1
    )
    popd
    echo [OK] Frontend built.
)
echo.

REM ============================================
REM Start the application
REM ============================================
echo [6/6] Starting application...
echo ========================================================
echo   main.py picks a free port automatically and opens
echo   your browser once the server is ready.
echo   Press Ctrl+C to stop the server.
echo ========================================================
echo.

python main.py

pause