@echo off
chcp 65001 >nul
title Finance Calculator - Launch

echo ========================================================
echo   Personal Finance Calculator (Virtual Env)
echo   Python + Streamlit
echo ========================================================
echo.

set VENV_PATH=%~dp0.venv
set VENV_PYTHON=%VENV_PATH%\Scripts\python.exe
set VENV_PIP=%VENV_PATH%\Scripts\pip.exe
set VENV_STREAMLIT=%VENV_PATH%\Scripts\streamlit.exe

REM Проверка: если .venv не существует или повреждён, пересоздаём
if not exist "%VENV_PYTHON%" (
    echo [INFO] Virtual environment not found or corrupted. Creating new one...
    if exist "%VENV_PATH%" rmdir /s /q "%VENV_PATH%"
    python -m venv "%VENV_PATH%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        echo Make sure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
    echo.
)

"%VENV_PYTHON%" --version
echo.

echo [1/3] Checking dependencies in .venv...
if exist "%~dp0requirements.txt" (
    echo [INFO] Installing/updating packages from requirements.txt...
    "%VENV_PIP%" install -r "%~dp0requirements.txt"
) else (
    echo [INFO] requirements.txt not found. Installing modules manually...
    "%VENV_PIP%" install streamlit pandas work-calendar pdfplumber
)
echo [OK] Dependencies checked.
echo.

if not exist "%~dp0.upload" mkdir "%~dp0.upload"

echo [2/3] Launching application...
echo.
echo   Application should open in your browser shortly.
echo   To stop the server, press Ctrl+C in this window.
echo.
echo ========================================================
echo.

"%VENV_STREAMLIT%" run "%~dp0app.py" --server.port 8501

echo.
echo ========================================================
echo [INFO] Script finished or crashed.
pause
