@echo off
setlocal
title Intelligent BMS - FAULT REPLAY DEMO LAUNCHER

:: Change directory to project root regardless of how File Explorer launched it
cd /d "%~dp0"

:: Activate virtual environment if one exists
if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: Run the fault replay demo launcher
python run_dashboard_demo.py

:: Keep the console window open so errors can be read
echo.
echo ============================================================
echo Process terminated. Press any key to close this window...
echo ============================================================
pause >nul
