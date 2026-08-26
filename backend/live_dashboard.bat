@echo off
title AI-PBMS EV Live Telemetry Simulation
cd /d "%~dp0"

echo Starting BMS Dashboard Python Backend...
start "BMS Dashboard Backend" /min python bms_dashboard_backend.py

echo Waiting for backend to start...
timeout /t 2 /nobreak >nul

echo Opening Dashboard in Web Browser...
start "" "live_dashboard_v3.html"

echo.
echo ======================================================================
echo           Starting Telemetry Simulation Stream...
echo ======================================================================
echo.

:: Run the simulation script from the parent directory
python "..\inject_faults_simulation.py"

pause
