@echo off
chcp 65001 >nul
title Finance Calculator - Direct Launch
setlocal enabledelayedexpansion

echo ========================================================
echo   Personal Finance Calculator
echo   Architecture: Python FastAPI + TypeScript OpenUI5
echo   Launch Mode: Direct (No Docker)
echo ========================================================
echo.

REM ============================================
REM Check Python
REM ============================================
echo [1/4] Checking Python...
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
echo [2/4] Installing Python dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies!
    pause
    exit /b 1
)

echo [OK] Python dependencies installed
echo.

REM ============================================
REM Check Node.js
REM ============================================
echo [3/4] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo Please install Node.js: https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Node.js detected
node --version
echo.

REM ============================================
REM Install Node.js dependencies
REM ============================================
echo Installing Node.js dependencies...
call npm install

if errorlevel 1 (
    echo [ERROR] Failed to install Node.js dependencies!
    pause
    exit /b 1
)

echo [OK] Node.js dependencies installed
echo.

REM ============================================
REM Start the application
REM ============================================
echo [4/4] Starting application...
echo ========================================================
echo.
echo   Backend (FastAPI): http://localhost:8000
echo   API Documentation: http://localhost:8000/docs
echo   Health Check:      http://localhost:8000/api/health
echo.
echo   Press Ctrl+C to stop the server
echo ========================================================
echo.

REM Open browser
start http://localhost:8000

REM Start FastAPI backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
