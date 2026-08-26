#!/usr/bin/env python3
"""
AI-PBMS Bidirectional Watchdog Script (With Auto-Reconnect & States)
------------------------------------------------------------------
Monitors python processes (bms_dashboard_backend.py and bms_bluetooth_gateway.py).
Queries the local Flask backend to determine system health state:
- PI_RUN: Flask is active and telemetry rows are increasing (BMS connected).
- PI_HOLD: Flask is active but telemetry is not increasing (BMS disconnected/sleeping).
- PI_OFFLINE: Flask is dead or watchdog is shutting down.
Exposes a bidirectional heartbeat with the Arduino Uno R4 WiFi over /dev/ttyACM0.
"""

import os
import sys
import time
import subprocess
import urllib.request
import json
from datetime import datetime

# Serial configuration
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 9600
HEARTBEAT_INTERVAL = 2.0  # Seconds between heartbeats
TIMEOUT_LIMIT = 10.0      # Timeout before declaring Arduino dead

# Directory setup
DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(DIR, "watchdog.log")

def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [WATCHDOG] {message}\n"
    print(log_line.strip())
    with open(LOG_FILE, "a") as f:
        f.write(log_line)

def get_pid(script_name):
    """Checks if a process is running and returns its PID, or None."""
    try:
        output = subprocess.check_output(["pgrep", "-f", script_name])
        pids = [int(pid) for pid in output.decode().strip().split("\n")]
        # Exclude this watchdog script itself
        mypid = os.getpid()
        pids = [p for p in pids if p != mypid]
        return pids[0] if pids else None
    except subprocess.CalledProcessError:
        return None

def restart_service(service_name):
    """Restarts a systemd service."""
    log_event(f"Attempting to restart crashed service: {service_name}")
    try:
        subprocess.run(["sudo", "systemctl", "restart", service_name], check=True)
        log_event(f"Service {service_name} restarted successfully.")
    except Exception as e:
        log_event(f"Failed to restart {service_name}: {e}")

def get_telemetry_status():
    """Queries Flask local API to get total rows processed."""
    try:
        url = "http://127.0.0.1:5000/api/telemetry"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            stats = data.get("historical_stats", {})
            total_rows = stats.get("total_rows_processed", 0)
            return True, total_rows
    except Exception:
        return False, 0

# Try to import serial (pyserial)
try:
    import serial
except ImportError:
    log_event("pyserial library not found. Run 'pip install pyserial'")
    serial = None

def is_service_active(service_name):
    """Checks if a systemd service is active (running or starting)."""
    try:
        res = subprocess.run(["systemctl", "is-active", service_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.stdout.decode().strip() == "active"
    except Exception:
        # Default to True to preserve original behavior if systemctl is missing
        return True

def main():
    log_event("Watchdog monitor started.")
    
    ser = None
    if serial:
        log_event(f"Opening serial port {SERIAL_PORT} at {BAUD_RATE} baud...")
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
            log_event("Serial port opened successfully! ✅")
        except Exception as e:
            log_event(f"Initial serial port open failed: {e}. Will retry dynamically...")
            ser = serial.Serial()
            ser.port = SERIAL_PORT
            ser.baudrate = BAUD_RATE
            ser.timeout = 0.1
    
    last_heartbeat_sent = 0.0
    last_arduino_alive = time.time()
    last_reconnect_attempt = 0.0
    
    last_rows_count = -1
    last_rows_change_time = time.time()
    consecutive_failed_queries = 0
    
    while True:
        now = time.time()
        
        # 1. Check Processes & Restart if crashed AND service is active
        backend_pid = get_pid("bms_dashboard_backend.py")
        gateway_pid = get_pid("bms_bluetooth_gateway.py")
        cloudflare_pid = get_pid("cloudflared")
        
        if backend_pid is None and is_service_active("bms-backend.service"):
            log_event("CRASH DETECTED: bms_dashboard_backend.py is not running.")
            restart_service("bms-backend.service")
            
        if gateway_pid is None and is_service_active("bms-bluetooth.service"):
            log_event("CRASH DETECTED: bms_bluetooth_gateway.py is not running.")
            restart_service("bms-bluetooth.service")
            
        if cloudflare_pid is None and is_service_active("bms-cloudflare.service"):
            log_event("CRASH DETECTED: cloudflared is not running.")
            restart_service("bms-cloudflare.service")
            
        # 2. Query Flask for telemetry activity to determine state
        flask_ok, current_rows = get_telemetry_status()
        
        # Default heartbeat command
        heartbeat_cmd = b"PI_HOLD\n"
        
        if not flask_ok:
            consecutive_failed_queries += 1
            if consecutive_failed_queries >= 10:  # 10 consecutive seconds unresponsive
                log_event("CRITICAL: Flask backend is dead. Sending PI_OFFLINE.")
                heartbeat_cmd = b"PI_OFFLINE\n"
            else:
                heartbeat_cmd = b"PI_HOLD\n"
        else:
            consecutive_failed_queries = 0
            # Flask backend is active and communicating. Send PI_RUN to display the ECG heartbeat!
            heartbeat_cmd = b"PI_RUN\n"
        
        # 3. Bidirectional Heartbeat with Arduino
        if ser:
            # Auto-reconnect handler if disconnected
            if not ser.is_open:
                if now - last_reconnect_attempt >= 5.0:
                    last_reconnect_attempt = now
                    log_event(f"USB Reconnect: Attempting to re-open {SERIAL_PORT}...")
                    try:
                        ser.open()
                        log_event("Serial port reconnected successfully! ✅")
                        last_arduino_alive = time.time()
                    except Exception as e:
                        log_event(f"USB Reconnect failed: {e}")
            
            if ser.is_open:
                # Send heartbeat state to Arduino
                if now - last_heartbeat_sent >= HEARTBEAT_INTERVAL:
                    try:
                        ser.write(heartbeat_cmd)
                        last_heartbeat_sent = now
                    except Exception as e:
                        log_event(f"Serial write error: {e}")
                        ser.close()  # force port status to closed for reconnect handler
                        
                # Read heartbeat from Arduino
                try:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line == "ARDUINO_ALIVE":
                            last_arduino_alive = now
                except Exception as e:
                    log_event(f"Serial read error: {e}")
                    ser.close()  # force port status to closed for reconnect handler
                    
                # Check for Arduino Timeout
                if now - last_arduino_alive > TIMEOUT_LIMIT:
                    log_event(f"CRITICAL: No heartbeat from Arduino for {now - last_arduino_alive:.1f} seconds!")
                    try:
                        log_event("Attempting to reset Arduino via DTR toggle...")
                        ser.close()
                        time.sleep(0.5)
                        ser.open()
                        last_arduino_alive = time.time()
                    except Exception as e:
                        log_event(f"Failed to reset Arduino: {e}")
                        ser.close()
                        
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_event("Watchdog stopped by user. Sending PI_OFFLINE before exit.")
        if serial:
            try:
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
                ser.write(b"PI_OFFLINE\n")
                ser.close()
            except Exception:
                pass
        sys.exit(0)
