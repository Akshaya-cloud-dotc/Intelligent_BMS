@echo off
setlocal
title AI-PBMS -- FAULT REPLAY DEMO LAUNCHER
cd /d "%~dp0"

:: Activate virtual environment if one exists
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

echo.
echo ============================================================
echo   AI-PBMS  Fault Replay Demo  --  Team ANS_4X / PSG iTech
echo ============================================================
echo.

:: Step 1 - Start backend server in a separate window
echo [1/2] Starting backend server...
start "AI-PBMS Backend Server" "%~dp0backend\start_backend.bat"

:: Wait 3 seconds for backend to initialize
timeout /t 3 /nobreak >nul

:: Step 2 - Run the demo (it will auto-open Mail Dispatcher window itself)
echo [2/2] Launching fault replay demo...
python "%~dp0run_dashboard_demo.py"

echo.
echo ============================================================
echo  Demo ended. Press any key to close this window...
echo ============================================================
pause >nul
