@echo off
title AI-PBMS Live Telemetry Simulation Controller
cd /d "%~dp0"

:: Smart directory finder: if run from elsewhere, locate the main folder
if not exist "inject_faults_simulation.py" (
    if exist "C:\Users\Adith\Downloads\CLEANED DATA SETS\inject_faults_simulation.py" (
        cd /d "C:\Users\Adith\Downloads\CLEANED DATA SETS"
    )
)

echo ======================================================================
echo           Launching Browser Dashboard...
echo ======================================================================

:: Determine if 'py' or 'python' should be used
set "PY_CMD=py"
py --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set "PY_CMD=python"
)

:: Start the Flask Backend Server
start "BMS Dashboard Backend" %PY_CMD% bms_dashboard_backend.py

:: Run local browser dashboard launcher in the background
:: start "BMS Dashboard Launcher" %PY_CMD% -u launch_dashboard.py

echo.
echo ======================================================================
echo           Starting Telemetry Simulation Stream...
echo ======================================================================
echo.

:: Run the simulation script in the foreground
%PY_CMD% -u inject_faults_simulation.py

pause
