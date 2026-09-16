#!/usr/bin/env python3
"""
run_dashboard.py — Live Intelligent BMS BLE Gateway Orchestrator
-----------------------------------------------------------------
- Loads configuration securely from .env via python-dotenv.
- Connects directly to physical BMS hardware over BLE.
- Connect retries 3x with backoff. On total failure, exits with clear prompt:
  "BMS not found — use run_dashboard_demo.bat for a data replay".
  Never silently substitutes generated data in live mode.
- Opens default browser upon first confirmed HTTP 200 telemetry POST.
- Missing token or 401 on first POST -> stops with clear message.
- Mid-run BLE dropouts -> retries in background and POSTs status: "disconnected"
  heartbeat to prevent frozen dashboard charts.
- Every payload carries "source": "ble".
"""

import os
import sys
import time
import json
import asyncio
import webbrowser
import urllib.request
import urllib.error
from datetime import datetime

# Load environment variables from .env
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

# Add backend to module path for gateway imports
backend_dir = os.path.join(project_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
INGEST_URL = os.getenv("INGEST_URL", "https://intelligentbms-production.up.railway.app/api/telemetry")
INGEST_TOKEN = os.getenv("INGEST_TOKEN", "").strip()
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://intelligentbms-production.up.railway.app/live-monitor")
BMS_TYPE = os.getenv("BMS_TYPE", "JBD")
BMS_MAC = os.getenv("BMS_MAC", "A4:C1:37:04:28:FB")
BLE_CONNECT_RETRIES = int(os.getenv("BLE_CONNECT_RETRIES", "3"))
BLE_BACKOFF_BASE_SEC = float(os.getenv("BLE_BACKOFF_BASE_SEC", "2.0"))

# Check bleak availability
try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None

from bms_bluetooth_gateway import (
    BMSGateway, 
    JBD_NOTIFY_UUID, 
    JBD_WRITE_UUID, 
    JBD_CMD_BASIC, 
    JBD_CMD_CELL, 
    parse_jbd_basic, 
    parse_jbd_cells, 
    DEFAULT_POLL_INTERVAL
)


class LiveDashboardGateway(BMSGateway):
    """
    Subclass of BMSGateway that enforces live mode guarantees:
    - No mock data fallback
    - Browser auto-opening on first confirmed HTTP 200 POST
    - 401 detection and termination
    - Background reconnect loop with disconnected heartbeats
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser_opened = False
        self.first_post_verified = False

    def post_telemetry(self) -> bool:
        """POSTs telemetry and verifies auth / opens browser on first success."""
        self.latest_data["source"] = "ble"
        
        # Save telemetry locally
        self.log_to_local_csv()
        self.log_to_local_xlsx()
        
        try:
            req_data = json.dumps(self.latest_data).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "X-Ingest-Token": INGEST_TOKEN
            }
            req = urllib.request.Request(self.api_url, data=req_data, headers=headers)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                status = result.get("status")
                buf_len = result.get("buffer_length", 0)
                pred = result.get("prediction")
                
                volts = self.latest_data.get('voltage', 0.0)
                curr = self.latest_data.get('current', 0.0)
                soc = self.latest_data.get('soc', 0.0)
                if status == "success" and pred:
                    self.log(f"Row sent! Buffer: {buf_len}/60 | V={volts}V, I={curr}A, SOC={soc}% | Fault: {pred.get('Fault Prediction')} ({pred.get('Confidence Score')})")
                else:
                    self.log(f"Row sent! Buffer: {buf_len}/60 | V={volts}V, I={curr}A, SOC={soc}% (Accumulating window)")

                # On first confirmed successful POST, open the dashboard in browser
                if not self.browser_opened:
                    self.browser_opened = True
                    self.first_post_verified = True
                    self.log(f"First telemetry row confirmed! Launching browser at: {DASHBOARD_URL}")
                    try:
                        webbrowser.open(DASHBOARD_URL)
                    except Exception as wb_err:
                        self.log(f"Note: Could not open browser automatically: {wb_err}")

                return True

        except urllib.error.HTTPError as he:
            if he.code == 401:
                print("\n" + "=" * 65)
                print("[ERROR] 401 Unauthorized: Ingest token rejected by backend!")
                print("Please verify the INGEST_TOKEN in your .env file.")
                print("=" * 65)
                sys.exit(1)
            else:
                self.log(f"HTTP Error POSTing to backend: {he.code} {he.reason}")
                return False
        except Exception as e:
            self.log(f"Error POSTing to backend: {e}")
            return False


async def run_live_gateway():
    print("=" * 65)
    print("       INTELLIGENT BMS -- LIVE BLUETOOTH GATEWAY LAUNCHER      ")
    print("=" * 65)
    print(f" Target BMS Type    : {BMS_TYPE}")
    print(f" BMS MAC Address    : {BMS_MAC}")
    print(f" Ingest Endpoint    : {INGEST_URL}")
    print(f" Dashboard URL      : {DASHBOARD_URL}")
    print(f" Telemetry Source   : ble")
    print("=" * 65)

    # 1. Validate INGEST_TOKEN
    if not INGEST_TOKEN:
        print("\n[ERROR] Missing INGEST_TOKEN!")
        print("Please specify INGEST_TOKEN in your .env file before running.")
        print("Exiting.\n")
        sys.exit(1)

    # 2. Validate Bleak installation
    if BleakClient is None:
        print("\n[ERROR] Bleak Bluetooth library is not installed!")
        print("Run: pip install -r requirements.txt")
        print("Exiting.\n")
        sys.exit(1)

    gateway = LiveDashboardGateway(
        bms_type=BMS_TYPE,
        mac_address=BMS_MAC,
        api_url=INGEST_URL,
        poll_interval=DEFAULT_POLL_INTERVAL,
        source="ble"
    )

    # 3. Initial connection attempts with retry & backoff
    initial_connected = False
    for attempt in range(1, BLE_CONNECT_RETRIES + 1):
        gateway.log(f"Connecting to {BMS_TYPE} BMS at {BMS_MAC} (Attempt {attempt}/{BLE_CONNECT_RETRIES})...")
        try:
            # Attempt BLE connection
            client = BleakClient(BMS_MAC, timeout=12.0)
            await client.connect()
            if client.is_connected:
                gateway.log("Connected to BMS hardware! ✅")
                initial_connected = True
                await client.disconnect()
                break
        except Exception as conn_err:
            gateway.log(f"Connection attempt {attempt} failed: {conn_err}")
            if attempt < BLE_CONNECT_RETRIES:
                backoff = BLE_BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                gateway.log(f"Retrying in {backoff:.1f} seconds...")
                await asyncio.sleep(backoff)

    if not initial_connected:
        print("\n" + "=" * 65)
        print("BMS not found — use run_dashboard_demo.bat for a data replay")
        print("=" * 65 + "\n")
        sys.exit(1)

    # 4. Main Streaming Loop with Mid-Run Dropout Recovery
    gateway.log("Starting real-time BLE telemetry stream...")
    while True:
        try:
            if BMS_TYPE == "JBD":
                await gateway.run_jbd()
            elif BMS_TYPE == "DALY":
                await gateway.run_daly()
            else:
                gateway.log(f"Unsupported live BMS type: {BMS_TYPE}")
                sys.exit(1)
        except Exception as drop_err:
            gateway.log(f"Mid-run BLE connection dropped: {drop_err}")
            gateway.log("Posting disconnected status heartbeat to server...")
            gateway.post_heartbeat("disconnected")
            gateway.log("Retrying background reconnect in 3 seconds...")
            await asyncio.sleep(3.0)


def main():
    try:
        asyncio.run(run_live_gateway())
    except KeyboardInterrupt:
        print("\nGateway stopped by user. Exiting cleanly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
