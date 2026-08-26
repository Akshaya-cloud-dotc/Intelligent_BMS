#!/usr/bin/env bash
# ==============================================================================
# AI-PBMS Unified Presentation Script (With Watchdog & Cloudflare Tunnel)
# ==============================================================================
# Starts everything: unblocks Bluetooth, starts the Flask server (CSV logging),
# starts the JBD BMS logger, starts the Cloudflare Tunnel, and starts the 
# Arduino serial watchdog monitor.
# Pressing Ctrl+C will stop all services and exit cleanly.
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================================"
echo "          Starting AI-PBMS Dashboard, Tunnel and Watchdog             "
echo "======================================================================"

# 1. Unblock and power on Bluetooth
echo "[1/5] Unblocking and powering on Bluetooth adapter..."
sudo rfkill unblock bluetooth
sudo hciconfig hci0 up
sleep 1

# 2. Activate Python virtual environment
if [ -d "venv" ]; then
    echo "[2/5] Activating Virtual Environment..."
    source venv/bin/activate
else
    echo "[!] Virtual Environment 'venv' not found. Please create it first."
    exit 1
fi

# 3. Stop any conflicting processes on Port 5000
echo "[3/5] Checking for processes occupying Port 5000..."
PORT_PID=$(lsof -t -i:5000 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo "    -> Port 5000 is occupied. Stopping process $PORT_PID..."
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
fi

# Stop systemd services to avoid port/adapter/tunnel conflicts
echo "    -> Stopping any active background systemd services..."
sudo systemctl stop bms-backend.service bms-bluetooth.service bms-watchdog.service bms-cloudflare.service 2>/dev/null

# 4. Start Flask Web Server (which now writes to CSV automatically)
echo "[4/5] Starting Flask Backend (bms_dashboard_backend.py)..."
python -u bms_dashboard_backend.py > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for Flask to initialize
sleep 2

# 5. Start Cloudflare Tunnel
echo "[5/5] Starting Cloudflare Tunnel (cloudflared)..."
echo "" > cloudflare.log
/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:5000 > cloudflare.log 2>&1 &
CLOUDFLARE_PID=$!

# Wait for Cloudflare to assign a URL
echo "    -> Waiting for Cloudflare Tunnel URL to generate..."
CLOUDFLARE_URL=""
for i in {1..10}; do
    sleep 1
    CLOUDFLARE_URL=$(grep -oE "https://[a-zA-Z0-9.-]+\.trycloudflare\.com" cloudflare.log | head -n 1)
    if [ ! -z "$CLOUDFLARE_URL" ]; then
        break
    fi
done

# 6. Start Bluetooth Gateway
echo "Starting Bluetooth Gateway (bms_bluetooth_gateway.py)..."
BMS_TYPE="JBD"
BMS_MAC="A4:C1:37:04:28:FB"

# Parse arguments passed to start_all.sh
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --bms) BMS_TYPE="$2"; shift ;;
        --mac) BMS_MAC="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

python -u bms_bluetooth_gateway.py --bms "$BMS_TYPE" --mac "$BMS_MAC" > bluetooth.log 2>&1 &
GATEWAY_PID=$!

# 7. Start Watchdog Monitor (watchdog.py)
echo "Starting Bidirectional Watchdog (watchdog.py)..."
python -u watchdog.py > watchdog.log 2>&1 &
WATCHDOG_PID=$!

# Cleanup handler on Ctrl+C
cleanup() {
    echo ""
    echo "======================================================================"
    echo "Stopping services and cleaning up..."
    kill $BACKEND_PID $GATEWAY_PID $WATCHDOG_PID $CLOUDFLARE_PID 2>/dev/null
    echo "✓ Stopped Flask server (PID: $BACKEND_PID)"
    echo "✓ Stopped Cloudflare tunnel (PID: $CLOUDFLARE_PID)"
    echo "✓ Stopped JBD Bluetooth gateway (PID: $GATEWAY_PID)"
    echo "✓ Stopped Watchdog process (PID: $WATCHDOG_PID)"
    echo "======================================================================"
    exit 0
}

# Trap Ctrl+C (SIGINT)
trap cleanup SIGINT

echo "======================================================================"
echo "✓ All services, Cloudflare, and watchdog launched successfully!"
echo "======================================================================"
PI_IP=$(hostname -I | awk '{print $1}')
echo "  Local Web URL     : http://127.0.0.1:5000"
echo "  Network Web URL   : http://$PI_IP:5000"
if [ ! -z "$CLOUDFLARE_URL" ]; then
    echo "  Cloudflare Tunnel : $CLOUDFLARE_URL"
else
    echo "  Cloudflare Tunnel : Still generating (check cloudflare.log)"
fi
echo "======================================================================"
echo "Streaming live Bluetooth gateway logs below (Press Ctrl+C to STOP ALL)..."
echo "----------------------------------------------------------------------"

# Clear old log files
echo "" > bluetooth.log

# Stream logs to terminal
tail -f bluetooth.log
