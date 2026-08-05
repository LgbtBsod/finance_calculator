@echo off
chcp 65001 >nul
title Finance Calculator - FastAPI + Vanilla JS
setlocal enabledelayedexpansion

echo ========================================================
echo   Personal Finance Calculator
echo   Architecture: Python FastAPI + Vanilla JS Frontend
echo   Launch Mode: Direct (No Docker, No Node.js)
echo ========================================================
echo.

REM ============================================
REM Check Python
REM ============================================
echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8+: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python detected
python --version
echo.

REM ============================================
REM Install Python dependencies
REM ============================================
echo [2/3] Installing Python dependencies...
pip install -q -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies!
    pause
    exit /b 1
)

echo [OK] Python dependencies installed
echo.

REM ============================================
REM Start the application
REM ============================================
echo [3/3] Starting application...
echo ========================================================
echo.
echo   Application URL:    http://localhost:8000
echo   API Documentation:  http://localhost:8000/docs
echo   Health Check:       http://localhost:8000/api/health
echo.
echo   The browser will open automatically in 2 seconds...
echo   Press Ctrl+C to stop the server
echo ========================================================
echo.

REM Open browser after a short delay (allowing server to start)
timeout /t 2 /nobreak >nul
start http://localhost:8000

REM Start FastAPI backend with api.py (includes frontend serving)
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

pause
