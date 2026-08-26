@echo off
title AI-PBMS Live Laptop Logger
cd /d "%~dp0"
py laptop_live_logger.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Warning: "py" command failed, trying "python" command...
    python laptop_live_logger.py
)
pause
