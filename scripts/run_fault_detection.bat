@echo off
title ML Fault Detection Server (Port 5000)
color 0B

echo ===================================================
echo     Fault Detection Server - Startup Helper
echo ===================================================

cd /d "%~dp0..\backend"

:: Determine if 'py' or 'python' should be used
set "PY_CMD=py"
py --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set "PY_CMD=python"
)

echo [INFO] Starting Fault Detection Backend on Port 5000...
%PY_CMD% bms_dashboard_backend.py

pause
