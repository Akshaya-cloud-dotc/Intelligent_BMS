@echo off
setlocal
title AI-PBMS -- LIVE BLE GATEWAY LAUNCHER
cd /d "%~dp0"

:: Activate virtual environment if one exists
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

echo.
echo ============================================================
echo   AI-PBMS  Live BLE Gateway Launcher -- Team ANS_4X
echo ============================================================
echo.

:: Step 1 - Start backend server in a separate window
echo [1/2] Starting backend server...
start "AI-PBMS Backend Server" "%~dp0backend\start_backend.bat"

:: Wait 3 seconds for backend to initialize
timeout /t 3 /nobreak >nul

:: Step 2 - Run the live BLE dashboard (it will auto-open Mail Dispatcher window)
echo [2/2] Launching live BLE gateway...
python "%~dp0run_dashboard.py"

echo.
echo ============================================================
echo Process terminated. Press any key to close this window...
echo ============================================================
pause >nul
