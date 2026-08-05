@echo off
chcp 65001 >nul
title Finance Calculator - Docker Launch
setlocal enabledelayedexpansion

echo ========================================================
echo   Personal Finance Calculator
echo   Architecture: Python FastAPI + TypeScript OpenUI5
echo   Launch Mode: Docker Container
echo ========================================================
echo.

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH!
    echo Please install Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo [OK] Docker detected
echo.

REM Check if docker-compose is available (try both v1 and v2)
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] docker-compose is not installed!
        echo Please install Docker Compose.
        pause
        exit /b 1
    ) else (
        set COMPOSE_CMD=docker compose
    )
) else (
    set COMPOSE_CMD=docker-compose
)

echo [OK] Docker Compose detected
echo.

REM Build and start containers
echo [1/3] Building Docker images...
%COMPOSE_CMD% build

if errorlevel 1 (
    echo [ERROR] Failed to build Docker images!
    pause
    exit /b 1
)

echo [OK] Build completed
echo.

echo [2/3] Starting containers...
%COMPOSE_CMD% up -d

if errorlevel 1 (
    echo [ERROR] Failed to start containers!
    pause
    exit /b 1
)

echo [OK] Containers started
echo.

echo [3/3] Waiting for application to be ready...
timeout /t 5 /nobreak >nul

REM Health check
echo Checking application health...
for /l %%i in (1,1,10) do (
    curl -s http://localhost:8000/api/health >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Application is healthy!
        goto :app_ready
    )
    echo   Attempt %%i: Waiting...
    timeout /t 2 /nobreak >nul
)

echo [WARNING] Application may not be fully ready yet. Please check logs.
goto :show_urls

:app_ready
echo.

:show_urls
echo ========================================================
echo   APPLICATION READY!
echo ========================================================
echo.
echo   Frontend + Backend: http://localhost:8000
echo   API Documentation:  http://localhost:8000/docs
echo   Health Check:       http://localhost:8000/api/health
echo.
echo   To view logs: %COMPOSE_CMD% logs -f
echo   To stop:        %COMPOSE_CMD% down
echo   To restart:     %COMPOSE_CMD% restart
echo.
echo ========================================================
echo.

REM Open browser
start http://localhost:8000

echo Press any key to view live logs (Ctrl+C to exit)...
pause >nul

%COMPOSE_CMD% logs -f

echo.
echo ========================================================
echo [INFO] Script finished.
pause
