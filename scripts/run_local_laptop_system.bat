@echo off
title AI-PBMS Local Laptop Controller
cd /d "%~dp0"

echo ======================================================================
echo           AI-PBMS Local Laptop System Controller
echo ======================================================================
echo This script will scan your Bluetooth devices, launch the local
echo Flask backend, connect to your battery BMS via your laptop's Bluetooth,
echo and open the live dashboard.
echo ======================================================================
echo.

:: 1. Check Python installation
py --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

:recheck_bt
echo Checking Bluetooth status on your laptop...
py "CLEANED DATA SETS\check_bluetooth_local.py" > temp_bt_status.txt 2>&1

findstr /C:"BT_OFF" temp_bt_status.txt >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======================================================================
    echo [ERROR] Bluetooth radio is turned OFF on your laptop!
    echo.
    echo Please:
    echo   1. Turn ON Bluetooth in Windows Settings (Settings -> Bluetooth & devices)
    echo   2. Make sure your laptop's Bluetooth is enabled.
    echo   3. Press any key in this window to check again.
    echo ======================================================================
    del temp_bt_status.txt
    pause
    goto recheck_bt
)

findstr /C:"NO_BLEAK" temp_bt_status.txt >nul
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Installing required Bluetooth library (bleak)...
    py -m pip install bleak
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install bleak. Please connect to the internet and try again.
        del temp_bt_status.txt
        pause
        exit /b 1
    )
    goto recheck_bt
)

:: Display Bluetooth scan results
type temp_bt_status.txt | findstr /V "BT_OK" | findstr /V "BT_OFF" | findstr /V "NO_BLEAK"
del temp_bt_status.txt
echo.

:: 2. Choose BMS Protocol
echo ======================================================================
echo Select your BMS model:
echo   [1] JBD BMS (Xiaoxiang) - Default MAC: A4:C1:37:04:28:FB
echo   [2] Daly BMS
echo   [3] Mock Simulation (for testing without battery)
echo   [4] Custom JBD MAC Address
echo ======================================================================
set /p CHOICE="Enter choice [1-4]: "

set "BMS_TYPE=JBD"
set "MAC=A4:C1:37:04:28:FB"

if "%CHOICE%"=="2" (
    set "BMS_TYPE=DALY"
    set /p MAC="Enter DALY BMS MAC Address (e.g. AB:CD:EF:01:23:45): "
)
if "%CHOICE%"=="3" (
    set "BMS_TYPE=MOCK"
)
if "%CHOICE%"=="4" (
    set "BMS_TYPE=JBD"
    set /p MAC="Enter JBD BMS MAC Address (e.g. A4:C1:37:04:28:FB): "
)

echo.
echo ======================================================================
echo Starting Local Flask Backend Server...
echo ======================================================================
start "AI-PBMS Local Backend" /Min py "CLEANED DATA SETS\bms_dashboard_backend.py"
timeout /t 3 >nul

echo.
echo ======================================================================
echo Starting Local Bluetooth BLE Gateway...
echo ======================================================================
if "%BMS_TYPE%"=="MOCK" (
    start "BMS Bluetooth Gateway (MOCK)" py "CLEANED DATA SETS\bms_bluetooth_gateway.py" --bms MOCK --url http://127.0.0.1:5000/api/telemetry
) else (
    echo Connecting to %BMS_TYPE% BMS at %MAC%...
    start "BMS Bluetooth Gateway" py "CLEANED DATA SETS\bms_bluetooth_gateway.py" --bms %BMS_TYPE% --mac %MAC% --url http://127.0.0.1:5000/api/telemetry
)
timeout /t 2 >nul

echo.
echo ======================================================================
echo Launching Browser Dashboard...
echo ======================================================================
py launch_dashboard.py

echo.
echo ======================================================================
echo Starting Local Laptop Telemetry Logger (Current Window)...
echo ======================================================================
py laptop_live_logger.py

pause
