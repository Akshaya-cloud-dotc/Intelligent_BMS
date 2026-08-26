@echo off
setlocal EnableDelayedExpansion
title Battery Dashboard Auto-Launcher
color 0A

:: Ensure working directory is the script's directory
cd /d "%~dp0"

echo ===================================================
echo     Battery Parameter Dashboard - Startup Script
echo ===================================================
echo.

:: 1. Create logs directory
if not exist "logs" mkdir logs
echo [INFO] Startup and installation logs will be stored in the 'logs' folder.
echo Startup Diagnostics > logs\startup_diagnostic.log
date /t >> logs\startup_diagnostic.log
time /t >> logs\startup_diagnostic.log

:: 2. Check Prerequisites
py --version >> logs\startup_diagnostic.log 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

call npm -v >> logs\startup_diagnostic.log 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] NPM is not installed or not in PATH.
    echo Please install Node.js and try again.
    pause
    exit /b 1
)

echo [INFO] Prerequisites met. Proceeding with startup...
echo.

:: 3. Backend Setup
echo [STEP 1/3] Setting up and starting Backend Server...
cd backend
if not exist "venv" (
    echo [INFO] Creating Python virtual environment...
    py -m venv venv
)
call venv\Scripts\activate.bat

echo [INFO] Installing missing Python packages...
venv\Scripts\python.exe -m pip install -r requirements.txt > "..\logs\backend_install.log" 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install Python dependencies. Check logs\backend_install.log.
    pause
    exit /b 1
)

echo [INFO] Starting Backend Server...
start "Backend Server (FastAPI)" cmd /k "title Backend Server && echo Starting FastAPI Backend... && venv\Scripts\activate.bat && venv\Scripts\python.exe main.py"
cd ..

echo [INFO] Starting ML Dashboard Server...
start "ML Dashboard Server (Flask)" cmd /k "title ML Dashboard Server && echo Starting Flask ML Dashboard... && cd /d ""C:\Users\Adith\Downloads\CLEANED DATA SETS"" && python bms_dashboard_backend.py"

:: 4. Wait
echo [INFO] Waiting 5 seconds for Backend to initialize...
timeout /t 5 >nul

:: 5. Frontend Setup
echo.
echo [STEP 2/3] Setting up and starting Frontend Server...
cd frontend

echo [INFO] Installing missing NPM packages... (This may take a moment)
call npm install > "..\logs\frontend_install.log" 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install NPM dependencies. Check logs\frontend_install.log.
    pause
    exit /b 1
)

echo [INFO] Starting Frontend Server...
start "Frontend Server (Vite)" cmd /k "title Frontend Server && echo Starting Vite Server... && npm run dev"
cd ..

:: 6. Wait
echo [INFO] Waiting 3 seconds for Frontend to initialize...
timeout /t 3 >nul

:: 7. Launch Browser
echo.
echo [STEP 3/3] Launching Dashboard in Browser...
start http://localhost:5173

echo.
echo ===================================================
echo     Startup Complete!
echo     Dashboard is opening in your browser.
echo     Keep the two command prompt windows open.
echo ===================================================
pause
