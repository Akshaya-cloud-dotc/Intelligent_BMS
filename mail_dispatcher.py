#!/usr/bin/env python3
"""
mail_dispatcher.py — AI-PBMS Live Mail Dispatch Monitor
---------------------------------------------------------
This script is launched automatically by run_dashboard_demo.py as a
separate terminal window. It watches the alert queue and displays
real-time email dispatch logs when faults are detected during replay.

Keep this window open while the demo is running.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

IST = timezone(timedelta(hours=5, minutes=30))
def now_ist():
    return datetime.now(IST).strftime("%H:%M:%S")

# ── Banner ─────────────────────────────────────────────────────────────────────
print("=" * 65)
print("   AI-PBMS  ·  MAIL DISPATCH MONITOR  ·  Team ANS_4X / PSG iTech")
print("=" * 65)
print()
print("  Routing rules:")
print("    ⚠  WARNING  → akshayavg1@gmail.com")
print("    🔴 CRITICAL → 24e103@psgitech.ac.in, akshayavg1@psgitech.ac.in")
print()
print("  Waiting for fault alerts from the replay demo...")
print("-" * 65)

# ── Import mailer (with rich monkey-patch for live output) ─────────────────────
try:
    import backend.alerts.mailer as mailer_mod

    # Wrap the background worker so every dispatch prints a visible line here
    original_send = mailer_mod._send_smtp_message

    def _patched_send(to_addr, subject, body_text, body_html, csv_data=None):
        if isinstance(to_addr, (list, tuple, set)):
            dest = ", ".join(to_addr)
        else:
            dest = str(to_addr)
            
        if "[RESOLVED]" in subject:
            header_title = "── FAULT RESOLVED (RESTORED TO NORMAL) ───────────"
            sev_tag = "🟢 RESOLVED"
            fault = subject.replace("[RESOLVED]", "").replace("AI-PBMS:", "").replace("Cleared / Restored to Normal", "").replace("Cleared", "").strip()
        elif "[WARNING]" in subject:
            header_title = "── FAULT DETECTED ──────────────────────────────────"
            sev_tag = "⚠  WARNING"
            fault = subject.replace("[WARNING]", "").replace("AI-PBMS Alert:", "").replace("Detected", "").strip()
        elif "[CRITICAL]" in subject:
            header_title = "── FAULT DETECTED ──────────────────────────────────"
            sev_tag = "🔴 CRITICAL"
            fault = subject.replace("[CRITICAL]", "").replace("AI-PBMS Alert:", "").replace("Detected", "").strip()
        else:
            header_title = "── SYSTEM NOTIFICATION ────────────────────────────"
            sev_tag = "ℹ  INFO"
            fault = subject

        print(f"\n[{now_ist()}] {header_title}")
        print(f"  Status    : {sev_tag}")
        print(f"  Fault     : {fault}")
        print(f"  To        : {dest}")
        print(f"  Subject   : {subject}")
        print(f"  Status    : Sending via smtp.gmail.com:465 ...", flush=True)

        result = original_send(to_addr, subject, body_text, body_html, csv_data)

        print(f"  Status    : ✅ SENT successfully to {dest}")
        print("-" * 65, flush=True)
        return result

    mailer_mod._send_smtp_message = _patched_send
    print(f"[{now_ist()}] Mailer hooked. Listening for fault alerts...\n")

except Exception as e:
    print(f"[ERROR] Could not import mailer: {e}")
    print("Make sure you are running from the Intelligent_BMS root folder.")
    input("\nPress Enter to exit...")
    sys.exit(1)

# ── Keep alive loop ────────────────────────────────────────────────────────────
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\n[{now_ist()}] Mail Dispatch Monitor stopped. Goodbye!")
