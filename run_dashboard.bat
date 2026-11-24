@echo off
setlocal EnableExtensions
title AI-PBMS -- LIVE BLE GATEWAY LAUNCHER
cd /d "%~dp0"

:: Low-memory safeguards (prevents OpenBLAS "Memory allocation failed")
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
echo   AI-PBMS  Live BLE Gateway Launcher -- Team ANS_4X
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    goto END
)
if not exist "%~dp0run_dashboard.py" (
    echo [ERROR] run_dashboard.py is missing from %~dp0
    goto END
)
if not exist "%~dp0.env" (
    echo [ERROR] .env not found - it holds your BMS_MAC and INGEST_TOKEN.
    goto END
)

:: Step 1 - Start the local backend only if .env points at localhost.
:: When INGEST_URL is the cloud server, the gateway posts straight to it and the
:: heavy local ML backend (xgboost + torch) is skipped to save RAM.
set START_LOCAL=0
if /I "%~1"=="--local" set START_LOCAL=1
findstr /I /R /C:"^INGEST_URL=.*localhost" /C:"^INGEST_URL=.*127.0.0.1" "%~dp0.env" >nul 2>nul
if not errorlevel 1 set START_LOCAL=1

if "%START_LOCAL%"=="0" goto NO_LOCAL

echo [1/2] Starting local backend server...
start "AI-PBMS Backend Server" "%~dp0backend\start_backend.bat"
set /a TRIES=0
:WAITLOOP
powershell -NoProfile -Command "try{if((Invoke-WebRequest http://127.0.0.1:5000/health -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}" >nul 2>nul
if not errorlevel 1 goto BACKEND_UP
set /a TRIES+=1
if %TRIES% geq 30 goto BACKEND_TIMEOUT
timeout /t 3 /nobreak >nul
goto WAITLOOP

:BACKEND_TIMEOUT
echo [WARN] Backend did not answer in time - continuing anyway.
goto BACKEND_UP

:NO_LOCAL
echo [1/2] Using cloud dashboard server - local backend not needed.

:BACKEND_UP

:: Step 2 - Run the live BLE gateway
echo [2/2] Launching live BLE gateway...
echo.
python "%~dp0run_dashboard.py"

:END
echo.
echo ============================================================
echo  Process terminated. Press any key to close this window...
echo ============================================================
pause >nul
endlocal
