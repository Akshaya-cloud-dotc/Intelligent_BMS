@echo off
title AI-PBMS Unified System Controller
cd /d "%~dp0"

:: Smart directory finder: if run from Desktop/elsewhere, locate the main folder
if not exist "laptop_live_logger.py" (
    if exist "C:\Users\Adith\Downloads\CLEANED DATA SETS\laptop_live_logger.py" (
        cd /d "C:\Users\Adith\Downloads\CLEANED DATA SETS"
    )
)

echo ======================================================================
echo           Starting Raspberry Pi Services (via SSH)...
echo ======================================================================
ssh raspi@192.168.137.244 "sudo systemctl start bms-backend.service bms-bluetooth.service bms-cloudflare.service bms-watchdog.service"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Warning: Failed to connect to Raspberry Pi via SSH. 
    echo Please check that your Mobile Hotspot is ON and the Pi is connected.
    echo.
    goto launch_logger
) else (
    echo Successfully started all background services on Pi!
)

echo.
echo ======================================================================
echo           Launching Browser Dashboard...
echo ======================================================================

:: Determine if 'py' or 'python' should be used
set "PY_CMD=py"
py --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set "PY_CMD=python"
)

:: Run local browser dashboard launcher
%PY_CMD% -u launch_dashboard.py

:launch_logger
echo.
echo ======================================================================
echo           Starting Local Laptop Telemetry Logger...
echo ======================================================================
%PY_CMD% -u laptop_live_logger.py
if %ERRORLEVEL% NEQ 0 (
    echo Warning: "%PY_CMD%" failed. Trying fallback...
    py -u laptop_live_logger.py 2>nul || python -u laptop_live_logger.py
)
pause
