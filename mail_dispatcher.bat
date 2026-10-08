@echo off
title AI-PBMS Mail Dispatcher
cd /d "%~dp0"
echo.
echo =================================================================
echo    AI-PBMS  ^|  MAIL DISPATCH MONITOR  ^|  Team ANS_4X / PSG iTech
echo =================================================================
echo.
echo   WARNING  --^> akshayavg1@gmail.com
echo   CRITICAL --^> 24e103@psgitech.ac.in, akshayavg1@psgitech.ac.in
echo.
echo   Waiting for fault alerts from the replay demo...
echo -----------------------------------------------------------------
echo.
python mail_dispatcher.py
pause
