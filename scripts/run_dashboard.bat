@echo off
setlocal EnableDelayedExpansion
title BMS Unified System Launcher
color 0B

echo ===================================================
echo     Intelligent BMS Unified Startup Script
echo ===================================================
echo.

:: 1. Move to the correct project directory
cd /d "%~dp0"
echo [*] Working directory: %CD%

:: 2. Check Python and npm
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] npm is required for the frontend but not found.
    pause
    exit /b 1
)

:: 3. Prevent duplicate instances
echo [*] Checking and cleaning up ports 5000, 8000, 5173...
for %%P in (5000 8000 5173) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R /C:"TCP.*:%%P.*LISTENING"') do (
        set PID=%%a
        if not "!PID!"=="" (
            echo [!] Port %%P is occupied by PID: !PID!. Closing process...
            taskkill /F /PID !PID! >nul 2>nul
        )
    )
)
:: Give it a brief moment to release ports
timeout /t 2 >nul

:: 4. Start Flask Telemetry Backend (Port 5000)
echo [*] Starting Flask Telemetry Backend (Port 5000)...
start "Prediction Backend (5000)" /D "%~dp0..\backend" python bms_dashboard_backend.py

:: 5. Start FastAPI Backend (Port 8000)
echo [*] Starting FastAPI Backend (Port 8000)...
start "FastAPI Backend (8000)" /D "%~dp0..\frontend\battery-dashboard\backend" python main.py

:: 6. Start VNet / Bluetooth Gateway
echo [*] Starting VNet / Bluetooth Gateway...
start "VNet Bluetooth Gateway" /D "%~dp0..\backend" python bms_bluetooth_gateway.py --bms JBD --mac A4:C1:37:04:28:FB

:: 7. Wait for Backends to initialize
echo [*] Initializing backend services...
timeout /t 5 >nul

:: 8. Start React/Vite Frontend (Port 5173)
echo [*] Starting React/Vite Frontend (Port 5173)...
cd ..\frontend\battery-dashboard\frontend
if not exist "node_modules" (
    echo [*] Installing npm packages...
    call npm install
)
start "Start Dashboard Frontend (5173)" cmd /k "npm run dev -- --host 0.0.0.0"

:: 9. Wait for Frontend to initialize
echo [*] Initializing dashboard interface...
timeout /t 4 >nul

:: 10. Open browser to the Dashboard
echo [+] Launching Dashboard in web browser...
start http://127.0.0.1:5173

echo.
echo ======================================================================
echo   BMS Unified System is LIVE!
echo.
echo   Local Dashboard URL : http://127.0.0.1:5173
echo.
echo   Do NOT close the running console windows to keep it active.
echo ======================================================================
echo.
pause
