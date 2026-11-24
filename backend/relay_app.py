"""
relay_app.py  -  lightweight cloud relay for the Intelligent BMS dashboard (Render).

The Raspberry Pi runs the full backend (Bluetooth, ML, alerts) and pushes its
finished /api/telemetry snapshot here every second. This app only stores the
latest snapshot in memory and serves it, with the same static frontend.
Dependencies: Flask + gunicorn only (no pandas / xgboost / sklearn).

Env vars:
  INGEST_TOKEN        required - must match the Pi's render.env
  DASHBOARD_USER      optional - enables HTTP basic auth on the dashboard
  DASHBOARD_PASSWORD  optional
  STALE_AFTER_SEC     optional - default 15
"""
import hmac
import os
import threading
import time

from flask import Flask, Response, jsonify, request, send_from_directory

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
DIST_DIR = os.path.join(BACKEND_DIR, "dist")
CONFIGURATOR_DIR = os.path.join(ROOT_DIR, "frontend", "battery-dashboard")

INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "")
DASH_USER = os.environ.get("DASHBOARD_USER", "")
DASH_PASS = os.environ.get("DASHBOARD_PASSWORD", "")
STALE_AFTER_SEC = float(os.environ.get("STALE_AFTER_SEC", "15"))

app = Flask(__name__)
_lock = threading.Lock()
_snapshot = None        # last JSON pushed by the Pi
_received_at = 0.0      # time.time() when it arrived

PUBLIC_PATHS = {"/health", "/api/relay/push"}


def _eq(a, b):
    return hmac.compare_digest(a.encode(), b.encode())


@app.before_request
def basic_auth():
    if not (DASH_USER and DASH_PASS) or request.path in PUBLIC_PATHS or request.method == "OPTIONS":
        return None
    auth = request.authorization
    if auth and _eq(auth.username or "", DASH_USER) and _eq(auth.password or "", DASH_PASS):
        return None
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Intelligent BMS"'})


@app.after_request
def no_cache(resp):
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- ingest from the Pi ----------
@app.route("/api/relay/push", methods=["POST"])
def relay_push():
    global _snapshot, _received_at
    if not INGEST_TOKEN:
        return jsonify({"error": "INGEST_TOKEN not set on server"}), 503
    if not _eq(request.headers.get("X-Ingest-Token", ""), INGEST_TOKEN):
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "expected a JSON object"}), 400
    with _lock:
        _snapshot = data
        _received_at = time.time()
    return jsonify({"status": "ok"})


# ---------- read side (same shape as the Pi's /api/telemetry) ----------
def _current():
    with _lock:
        snap, recv = _snapshot, _received_at
    age = time.time() - recv if recv else None
    if snap is None:
        return {
            "status": "Waiting for the Raspberry Pi to send data",
            "is_stale": True, "bluetooth_connected": False,
            "prediction": None, "live_prediction": None, "live_row": None, "raw_row": None,
            "buffer_length": 0, "data_age_seconds": None, "last_packet_time": None,
            "active_alerts": [], "alert_history": [], "historical_stats": {},
            "relay_age_seconds": None,
        }
    out = dict(snap)
    out["relay_age_seconds"] = round(age, 1)
    if age > STALE_AFTER_SEC:
        # Pi stopped pushing: never show old numbers as live
        out.update({
            "status": "Pi offline - no data for %ds" % int(age),
            "is_stale": True, "bluetooth_connected": False,
            "prediction": None, "live_prediction": None, "live_row": None,
            "active_alerts": [], "data_age_seconds": round(age, 1),
        })
    return out


@app.route("/api/telemetry", methods=["GET"])
@app.route("/api/live-bms-data", methods=["GET"])
def telemetry():
    return jsonify(_current())


@app.route("/api/alerts", methods=["GET"])
def alerts():
    cur = _current()
    active = cur.get("active_alerts") or []
    level = "NORMAL"
    for a in active:
        if a.get("level") == "CRITICAL":
            level = "CRITICAL"
            break
        if a.get("level") == "WARNING":
            level = "WARNING"
    return jsonify({"active_alerts": active, "alert_history": cur.get("alert_history") or [],
                    "system_level": level})


@app.route("/health")
def health():
    with _lock:
        recv = _received_at
    return jsonify({"status": "ok", "mode": "relay",
                    "last_push_age_sec": round(time.time() - recv, 1) if recv else None})


@app.route("/api/<path:_any>", methods=["GET", "POST"])
def pi_only(_any):
    return jsonify({"error": "This feature runs on the Raspberry Pi only (cloud view is read-only)."}), 501


# ---------- static frontend (unchanged files) ----------
@app.route("/")
def root():
    if os.path.exists(os.path.join(DIST_DIR, "index.html")):
        return send_from_directory(DIST_DIR, "index.html")
    return send_from_directory(BACKEND_DIR, "live_dashboard_v3.html")


@app.route("/assets/<path:path>")
def assets(path):
    return send_from_directory(os.path.join(DIST_DIR, "assets"), path)


@app.route("/live-monitor")
def live_monitor():
    return send_from_directory(BACKEND_DIR, "live_dashboard_v3.html")


@app.route("/configurator")
@app.route("/configurator/<path:path>")
def configurator(path=None):
    target = DIST_DIR if os.path.exists(DIST_DIR) else CONFIGURATOR_DIR
    if path and os.path.exists(os.path.join(target, path)):
        return send_from_directory(target, path)
    return send_from_directory(target, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
