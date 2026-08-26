@echo off
title AI-PBMS EV Data Dashboard (Historical Viewer)
cd /d "%~dp0"

echo Opening Dashboard in Web Browser...
start "" "live_dashboard_v3.html"

echo Starting BMS Dashboard Python Backend...
python bms_dashboard_backend.py

pause
