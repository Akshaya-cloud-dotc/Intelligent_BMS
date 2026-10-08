@echo off
title AI-PBMS -- GLOBAL CLOUD DASHBOARD LAUNCHER
cd /d "%~dp0"

echo =================================================================
echo   AI-PBMS  |  GLOBAL CLOUD TUNNEL LAUNCHER  |  Team ANS_4X
echo =================================================================
echo.
echo [1/2] Starting local backend server on port 5000...
start "AI-PBMS Backend Server" "%~dp0backend\start_backend.bat"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Cloudflare Global Secure HTTPS Tunnel...
echo.
echo Your Global Public Dashboard URL will appear below:
echo -----------------------------------------------------------------
"%~dp0backend\cloudflared.exe" tunnel --url http://127.0.0.1:5000
pause
