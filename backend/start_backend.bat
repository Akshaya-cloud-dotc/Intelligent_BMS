@echo off
title AI-PBMS Backend Server
cd /d "%~dp0"
echo Starting AI-PBMS Flask Backend Server...
python bms_dashboard_backend.py
pause
