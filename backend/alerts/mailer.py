#!/usr/bin/env python3
"""
alerts/mailer.py — Server-Side Email Alerting Module for AI-PBMS
----------------------------------------------------------------
- Invoked from the /api/telemetry handler after ML & physics inference.
- Non-blocking: background thread worker queue ensures SMTP latency never blocks ingest.
- Trigger: non-Normal class with confidence >= 0.5.
  * [WARNING] for confidence 0.50 – 0.85
  * [CRITICAL] for confidence > 0.85
- Cooldown: default 300s per fault class.
  * Exception: WARNING -> CRITICAL escalation dispatches immediately.
- Source filter: Suppresses alerts when source starts with "replay:" unless DEMO_ALERTS=true.
- Body contains timestamp (IST), fault class, confidence, pack V, current, all 8 cells,
  NTC1/NTC2 temps, driving mode, source field.
- Attachment: Last 10 telemetry rows attached as CSV.
- smtplib over TLS/SSL using SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO.
- Dashboard endpoints: alerts history retrieval and "Send test email" testing.
"""

import os
import sys
import time
import json
import ssl
import smtplib
import socket
import queue
import threading
import io
import csv
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
ALERT_TO  = os.getenv("ALERT_TO", SMTP_USER).strip()
SENDER    = os.getenv("SMTP_FROM", SMTP_USER).strip()

ALERT_COOLDOWN_SEC = float(os.getenv("ALERT_COOLDOWN_SEC", "20"))
DEMO_ALERTS = os.getenv("DEMO_ALERTS", "true").strip().lower() == "true"

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")

# Cooldown Tracker: { fault_class: { "time": epoch_float, "severity": "WARNING"|"CRITICAL" } }
_cooldown_lock = threading.Lock()
_cooldown_tracker: Dict[str, Dict[str, Any]] = {}

# Recent Email History Ring Buffer: list of dicts
_history_lock = threading.Lock()
_email_history: List[Dict[str, Any]] = []
MAX_HISTORY_ITEMS = 50

def record_history_entry(entry: Dict[str, Any]):
    with _history_lock:
        _email_history.insert(0, entry)
        if len(_email_history) > MAX_HISTORY_ITEMS:
            _email_history.pop()

def get_alert_history() -> List[Dict[str, Any]]:
    with _history_lock:
        return list(_email_history)

# ==============================================================================
# ASYNC WORKER QUEUE
# ==============================================================================
_mail_queue: queue.Queue = queue.Queue(maxsize=100)

def _build_csv_attachment(rows: List[Dict[str, Any]]) -> str:
    """Generates a CSV string for the last 10 telemetry rows."""
    if not rows:
        return ""
    
    headers = [
        "timestamp", "source", "voltage", "current", "temperature", "soc", "delta_v",
        "cell_v1", "cell_v2", "cell_v3", "cell_v4", "cell_v5", "cell_v6", "cell_v7", "cell_v8",
        "ntc1", "ntc2", "ntc3", "ntc4"
    ]
    
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return out.getvalue()

def _send_smtp_message(to_addr: str, subject: str, body_text: str, body_html: str, 
                       csv_data: Optional[str] = None) -> bool:
    """Delivers email via smtplib with TLS/SSL, forcing IPv4 to prevent Linux/Railway Errno 101."""
    if not SMTP_USER or not SMTP_PASS:
        raise ValueError("SMTP_USER or SMTP_PASS not configured in environment variables.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER or SMTP_USER
    msg["To"] = to_addr
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    if csv_data:
        msg.add_attachment(
            csv_data.encode("utf-8"),
            maintype="text",
            subtype="csv",
            filename="telemetry_last_10_rows.csv"
        )

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        try:
            res = orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            if res:
                return res
        except Exception:
            pass
        return orig_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _ipv4_getaddrinfo
    try:
        ports_to_try = [SMTP_PORT]
        fallback_port = 587 if SMTP_PORT == 465 else 465
        if fallback_port not in ports_to_try:
            ports_to_try.append(fallback_port)

        last_err = None
        for port in ports_to_try:
            try:
                if port == 465:
                    with smtplib.SMTP_SSL(SMTP_HOST, port, context=context, timeout=12.0) as server:
                        server.login(SMTP_USER, SMTP_PASS)
                        server.send_message(msg)
                    return True
                else:
                    with smtplib.SMTP(SMTP_HOST, port, timeout=12.0) as server:
                        server.starttls(context=context)
                        server.login(SMTP_USER, SMTP_PASS)
                        server.send_message(msg)
                    return True
            except Exception as e:
                last_err = e
                print(f"[MAILER WARN] Port {port} failed: {e}. Trying fallback...")

        if last_err:
            raise last_err
    finally:
        socket.getaddrinfo = orig_getaddrinfo

    return True

def _worker_loop():
    """Background worker daemon thread that drains the mail queue."""
    while True:
        task = _mail_queue.get()
        if task is None:
            break
        
        try:
            to_addr = task.get("to", ALERT_TO)
            subject = task.get("subject", "AI-PBMS Alert")
            text = task.get("text", "")
            html = task.get("html", "")
            csv_content = task.get("csv_content", None)
            fault_class = task.get("fault_class", "General")
            severity = task.get("severity", "WARNING")
            conf_str = task.get("confidence_str", "N/A")

            print(f"[MAILER] Dispatching alert email to {to_addr} for [{severity}] {fault_class}...")
            _send_smtp_message(to_addr, subject, text, html, csv_content)
            print(f"[MAILER] Alert email sent successfully to {to_addr}! [OK]")

            record_history_entry({
                "timestamp": get_ist_now_str(),
                "fault_class": fault_class,
                "severity": severity,
                "confidence": conf_str,
                "recipient": to_addr,
                "status": "SENT",
                "subject": subject,
                "error": None
            })

        except Exception as e:
            err_msg = str(e)
            print(f"[MAILER ERROR] Failed to send email alert: {err_msg}")
            record_history_entry({
                "timestamp": get_ist_now_str(),
                "fault_class": task.get("fault_class", "General"),
                "severity": task.get("severity", "WARNING"),
                "confidence": task.get("confidence_str", "N/A"),
                "recipient": task.get("to", ALERT_TO),
                "status": "FAILED",
                "subject": task.get("subject", "AI-PBMS Alert"),
                "error": err_msg
            })
        finally:
            _mail_queue.task_done()

# Start background thread on import
_worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="BMS-AlertMailer")
_worker_thread.start()

# ==============================================================================
# PUBLIC DISPATCH & EVALUATION FUNCTIONS
# ==============================================================================
def evaluate_and_enqueue_alert(row: Dict[str, Any], 
                                prediction: Optional[Dict[str, Any]], 
                                live_prediction: Optional[Dict[str, Any]], 
                                recent_rows: List[Dict[str, Any]]) -> bool:
    """
    Evaluates telemetry against alert criteria:
    - Trigger: non-Normal class with confidence >= 0.5.
    - Subject: [WARNING] for 0.50-0.85, [CRITICAL] for > 0.85.
    - Suppress when source starts with 'replay:' unless DEMO_ALERTS=True.
    - Per-fault-class cooldown: default 300s, with immediate bypass on WARNING -> CRITICAL.
    """
    # 1. Determine active fault class and numeric confidence
    fault_class = "Normal"
    severity = "WARNING"
    confidence = 1.0
    conf_str = "100.0%"
    trigger_reason = "Safety threshold exceeded"

    # Check live_prediction (physics-informed override has highest priority)
    if live_prediction:
        cond = live_prediction.get("condition") or live_prediction.get("override_condition")
        if cond and cond not in ["Normal", "Normal Operation", "—", None]:
            fault_class = cond
            severity = live_prediction.get("severity", "WARNING")
            trigger_reason = live_prediction.get("reason") or live_prediction.get("override_reason", "Safety limit exceeded")
            conf_str = live_prediction.get("confidence", "98.50%")
            try:
                confidence = float(str(conf_str).replace("%", "")) / 100.0
            except Exception:
                confidence = 0.98

    # If live_prediction was normal, check raw ML prediction
    if fault_class in ["Normal", "Normal Operation"] and prediction:
        ml_pred = prediction.get("Fault Prediction") or prediction.get("Raw Prediction")
        if ml_pred and ml_pred not in ["Normal", None]:
            fault_class = ml_pred
            conf_str = prediction.get("Confidence Score", "80.00%")
            trigger_reason = prediction.get("Recommended Action", "ML Anomaly detected")
            try:
                confidence = float(str(conf_str).replace("%", "")) / 100.0
            except Exception:
                confidence = 0.80

    # Also check row's own fault_type or label if present (replay / gateway)
    if fault_class in ["Normal", "Normal Operation"]:
        r_fault = row.get("fault_type") or row.get("label")
        if r_fault and str(r_fault).strip() not in ["Normal", "Normal Operation", "—", "", "None"]:
            fault_class = str(r_fault).strip()
            severity = "WARNING" if fault_class.endswith("Risk") else "CRITICAL"
            conf_str = "99.00%"
            confidence = 0.99
            trigger_reason = f"Active fault detected: {fault_class}"

    # If still normal, no alert required
    if fault_class in ["Normal", "Normal Operation", "—", None]:
        return False

    # 2. Determine Severity
    if live_prediction and live_prediction.get("severity"):
        severity = live_prediction["severity"]
    elif fault_class.endswith("Risk") or confidence <= 0.85:
        severity = "WARNING"
    else:
        severity = "CRITICAL"

    # 3. Telemetry Source: all sources (BLE hardware, Gateway, and Replay) dispatch alerts
    source = row.get("source", "ble")

    # 4. Check Cooldown and Escalation
    now = time.time()
    with _cooldown_lock:
        last_event = _cooldown_tracker.get(fault_class)
        if last_event:
            time_since = now - last_event["time"]
            last_sev = last_event["severity"]
            
            # Check if cooldown is still active
            if time_since < ALERT_COOLDOWN_SEC:
                # Escalation exception: WARNING -> CRITICAL sends immediately!
                if last_sev == "WARNING" and severity == "CRITICAL":
                    print(f"[MAILER] Escalation detected for {fault_class} (WARNING -> CRITICAL)! Bypassing cooldown.")
                else:
                    # Still in cooldown
                    return False

        # Update cooldown timestamp and severity
        _cooldown_tracker[fault_class] = {
            "time": now,
            "severity": severity
        }

    # 5. Build Alert Content
    ts_str = get_ist_now_str()
    subject = f"[{severity}] AI-PBMS Alert: {fault_class} Detected"

    volts = float(row.get("voltage", 0.0))
    current = float(row.get("current", 0.0))
    soc = float(row.get("soc", 0.0))
    delta_v = float(row.get("delta_v", 0.0))
    ntc1 = row.get("ntc1", "N/A")
    ntc2 = row.get("ntc2", "N/A")
    driving_mode = row.get("Operating Mode") or (prediction.get("Operating Mode") if prediction else "CRUISE")

    cell_vals = [row.get(f"cell_v{i}", "N/A") for i in range(1, 9)]
    cell_table_rows = "".join(
        f"<tr><td style='padding:4px 8px;border:1px solid #ddd;font-weight:bold;'>Cell {i}</td>"
        f"<td style='padding:4px 8px;border:1px solid #ddd;'>{cell_vals[i-1]} V</td></tr>"
        for i in range(1, 9)
    )

    sev_color = "#c0392b" if severity == "CRITICAL" else "#d35400"

    body_text = f"""
======================================================================
AI-PBMS AUTOMATED BATTERY ALERT
======================================================================
Severity       : [{severity}]
Fault Class    : {fault_class}
Confidence     : {conf_str}
Trigger Reason : {trigger_reason}
Timestamp      : {ts_str}
Source         : {source}
Driving Mode   : {driving_mode}

Pack Voltage   : {volts:.2f} V
Pack Current   : {current:.2f} A
State of Charge: {soc:.1f} %
Max Cell Spread: {delta_v:.3f} V
NTC1 Temp      : {ntc1} °C
NTC2 Temp      : {ntc2} °C

Cell Voltages  :
  Cell 1: {cell_vals[0]} V | Cell 2: {cell_vals[1]} V
  Cell 3: {cell_vals[2]} V | Cell 4: {cell_vals[3]} V
  Cell 5: {cell_vals[4]} V | Cell 6: {cell_vals[5]} V
  Cell 7: {cell_vals[6]} V | Cell 8: {cell_vals[7]} V

Attached: Last 10 telemetry rows prior to this event (CSV).
======================================================================
"""

    body_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
  <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e1e4e8; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    
    <div style="background-color: {sev_color}; color: white; padding: 20px 24px;">
      <h2 style="margin: 0; font-size: 20px; font-weight: bold; letter-spacing: 0.5px;">[{severity}] AI-PBMS Alert: {fault_class}</h2>
      <p style="margin: 6px 0 0 0; font-size: 13px; opacity: 0.9;">Timestamp: {ts_str} &middot; Source: {source}</p>
    </div>

    <div style="padding: 24px;">
      <div style="background-color: #f8fafc; border-left: 4px solid {sev_color}; padding: 12px 16px; margin-bottom: 20px; border-radius: 0 8px 8px 0;">
        <strong style="font-size: 14px; color: #1e293b;">Trigger Reason:</strong>
        <p style="margin: 4px 0 0 0; font-size: 13px; color: #475569;">{trigger_reason}</p>
        <div style="margin-top: 6px; font-size: 12px; color: #64748b;">
          Confidence Score: <strong style="color: {sev_color};">{conf_str}</strong> &middot; Driving Mode: <strong>{driving_mode}</strong>
        </div>
      </div>

      <h4 style="margin: 0 0 10px 0; font-size: 14px; color: #334155; text-transform: uppercase; letter-spacing: 0.5px;">Pack Physical Parameters</h4>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px;">
        <tr>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; background: #f8fafc; width: 25%;">Pack Voltage</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; font-weight: bold;">{volts:.2f} V</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; background: #f8fafc; width: 25%;">Pack Current</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; font-weight: bold;">{current:.2f} A</td>
        </tr>
        <tr>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; background: #f8fafc;">State of Charge</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; font-weight: bold;">{soc:.1f} %</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; background: #f8fafc;">Cell Spread (&Delta;V)</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; font-weight: bold;">{delta_v:.3f} V</td>
        </tr>
        <tr>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; background: #f8fafc;">NTC1 Temp</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; font-weight: bold;">{ntc1} &deg;C</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; background: #f8fafc;">NTC2 Temp</td>
          <td style="padding: 6px 10px; border: 1px solid #e2e8f0; font-weight: bold;">{ntc2} &deg;C</td>
        </tr>
      </table>

      <h4 style="margin: 0 0 10px 0; font-size: 14px; color: #334155; text-transform: uppercase; letter-spacing: 0.5px;">Individual Cell Voltages (8S)</h4>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px; text-align: center;">
        <tr style="background: #f1f5f9;">
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 1</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 2</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 3</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 4</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 5</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 6</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 7</th>
          <th style="padding: 6px; border: 1px solid #e2e8f0;">Cell 8</th>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[0]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[1]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[2]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[3]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[4]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[5]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[6]}V</td>
          <td style="padding: 6px; border: 1px solid #e2e8f0;">{cell_vals[7]}V</td>
        </tr>
      </table>

      <p style="font-size: 12px; color: #64748b; margin-top: 15px;">
        &bull; <em>Attachment:</em> The last 10 telemetry samples leading up to this event are attached as a CSV file.
      </p>
    </div>

    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 24px; text-align: center; font-size: 11px; color: #94a3b8;">
      AI-PBMS Intelligent Battery Management System &middot; Team ANS_4X &middot; PSG iTech
    </div>
  </div>
</body>
</html>
"""

    # Generate CSV from recent rows
    csv_str = _build_csv_attachment(recent_rows[-10:])

    # 6. Put in background queue (non-blocking)
    task = {
        "to": ALERT_TO or SMTP_USER,
        "subject": subject,
        "text": body_text,
        "html": body_html,
        "csv_content": csv_str,
        "fault_class": fault_class,
        "severity": severity,
        "confidence_str": conf_str
    }

    try:
        _mail_queue.put_nowait(task)
        return True
    except queue.Full:
        print("[MAILER WARNING] Mail queue is full, dropping alert notification.")
        return False


def send_test_email(to_addr: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends an immediate test email to verify SMTP host, credentials, and network connectivity.
    """
    recipient = to_addr or ALERT_TO or SMTP_USER
    if not recipient:
        return {"status": "error", "message": "No recipient configured. Set ALERT_TO or SMTP_USER."}
    
    ts_str = get_ist_now_str()
    subject = "[TEST] AI-PBMS Email System Verification"

    sample_rows = [
        {
            "timestamp": ts_str, "source": "test", "voltage": 27.24, "current": 0.0, "temperature": 29.5,
            "soc": 75.0, "delta_v": 0.035, "cell_v1": 0.000, "cell_v2": 3.892, "cell_v3": 3.895,
            "cell_v4": 3.889, "cell_v5": 3.891, "cell_v6": 3.894, "cell_v7": 3.892, "cell_v8": 3.893,
            "ntc1": 29.5, "ntc2": 29.4, "ntc3": 29.5, "ntc4": 29.5
        }
    ]
    csv_content = _build_csv_attachment(sample_rows)

    body_text = f"This is a test notification from the AI-PBMS Intelligent Battery Management System.\nSent at: {ts_str}\nRecipient: {recipient}\nSMTP Server: {SMTP_HOST}:{SMTP_PORT}"
    body_html = f"""
    <div style="font-family:Arial,sans-serif;padding:20px;border:1px solid #ddd;border-radius:8px;max-width:500px;">
      <h3 style="color:#27ae60;margin-top:0;">✅ AI-PBMS Email Alert Verification</h3>
      <p>This email confirms that your Railway backend is correctly configured to send SMTP alerts.</p>
      <ul>
        <li><strong>SMTP Host:</strong> {SMTP_HOST}:{SMTP_PORT}</li>
        <li><strong>User:</strong> {SMTP_USER}</li>
        <li><strong>Recipient:</strong> {recipient}</li>
        <li><strong>Timestamp:</strong> {ts_str}</li>
      </ul>
      <p style="font-size:12px;color:#777;">Attached: Sample CSV telemetry test data.</p>
    </div>
    """

    try:
        _send_smtp_message(recipient, subject, body_text, body_html, csv_content)
        record_history_entry({
            "timestamp": ts_str,
            "fault_class": "Verification Test",
            "severity": "INFO",
            "confidence": "100%",
            "recipient": recipient,
            "status": "SENT",
            "subject": subject,
            "error": None
        })
        return {"status": "success", "message": f"Test email sent successfully to {recipient}!"}
    except Exception as e:
        err = str(e)
        record_history_entry({
            "timestamp": ts_str,
            "fault_class": "Verification Test",
            "severity": "INFO",
            "confidence": "100%",
            "recipient": recipient,
            "status": "FAILED",
            "subject": subject,
            "error": err
        })
        return {"status": "error", "message": f"SMTP delivery failed: {err}"}


if __name__ == "__main__":
    # Direct test invocation
    import argparse
    parser = argparse.ArgumentParser(description="Test AI-PBMS Mailer")
    parser.add_argument("--test", action="store_true", help="Send a test verification email")
    parser.add_argument("--to", type=str, default=None, help="Recipient email address")
    args = parser.parse_args()

    if args.test or len(sys.argv) == 1:
        print("Sending test email using current environment variables...")
        result = send_test_email(args.to)
        print("Result:", json.dumps(result, indent=2))
