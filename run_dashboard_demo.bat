@echo off
setlocal EnableExtensions
title AI-PBMS -- FAULT REPLAY DEMO LAUNCHER
cd /d "%~dp0"

:: ---------------------------------------------------------------------------
:: Low-memory safeguards (stops numpy/OpenBLAS grabbing one big buffer per CPU
:: thread, which caused "OpenBLAS error: Memory allocation still failed")
:: ---------------------------------------------------------------------------
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

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

:: ---------------------------------------------------------------------------
:: Pre-flight checks
:: ---------------------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH. Install Python 3.10+ and retry.
    goto END
)

if not exist "%~dp0run_dashboard_demo.py" (
    echo [ERROR] run_dashboard_demo.py is missing from %~dp0
    goto END
)
if not exist "%~dp0bms_data_labeled.xlsx" if not exist "%~dp0data\bms_data_labeled.xlsx" (
    echo [ERROR] Demo dataset bms_data_labeled.xlsx not found.
    goto END
)
if not exist "%~dp0.env" (
    echo [WARN] .env not found - copying from .env.example
    if exist "%~dp0.env.example" copy /y "%~dp0.env.example" "%~dp0.env" >nul
)

:: Install the few packages the demo needs, only if they are missing
python -c "import pandas, openpyxl, dotenv" >nul 2>nul
if errorlevel 1 (
    echo [*] Installing missing packages ^(pandas, openpyxl, python-dotenv^)...
    python -m pip install --quiet pandas openpyxl python-dotenv
)

:: ---------------------------------------------------------------------------
:: The demo streams to the cloud dashboard (INGEST_URL in .env), so the heavy
:: local ML backend (xgboost + torch) is NOT started - it wastes RAM.
:: It is started only if .env points at localhost, or with:  --local
:: ---------------------------------------------------------------------------
set START_LOCAL=0
if /I "%~1"=="--local" set START_LOCAL=1
findstr /I /R /C:"^INGEST_URL=.*localhost" /C:"^INGEST_URL=.*127.0.0.1" "%~dp0.env" >nul 2>nul
if not errorlevel 1 set START_LOCAL=1

if "%START_LOCAL%"=="1" (
    echo [1/2] Starting local backend server...
    start "AI-PBMS Backend Server" "%~dp0backend\start_backend.bat"
    timeout /t 8 /nobreak >nul
) else (
    echo [1/2] Using cloud dashboard server - local backend not needed.
)

echo [2/2] Launching fault replay demo...
echo.
python "%~dp0run_dashboard_demo.py"

:END
echo.
echo ============================================================
echo  Demo ended. Press any key to close this window...
echo ============================================================
pause >nul
endlocal
