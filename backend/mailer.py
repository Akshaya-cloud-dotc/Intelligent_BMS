"""
mailer.py — SMTP delivery for AI-PBMS alerts.

Two paths:
  send_critical()  called inline the moment a CRITICAL alert is logged
  send_digest()    called on a timer for WARNING / INFO

Run directly to send a digest:  python3 mailer.py
Run with --test to mail yourself a sample:  python3 mailer.py --test
"""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from datetime import datetime

import alerts
from dotenv import load_dotenv
load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")          # Gmail App Password, never the login password
SENDER    = os.getenv("SMTP_FROM", SMTP_USER)

SEV_COLOR = {"CRITICAL": "#c0392b", "WARNING": "#b8860b", "INFO": "#555555"}


def _format_ts(ts_str):
    try:
        _ts = datetime.fromisoformat(ts_str).astimezone()
        return _ts.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts_str


def _row_html(a):
    color = SEV_COLOR.get(a["severity"], "#555")
    val = "" if a["measured_value"] is None else f'{a["measured_value"]:.3f}'
    thr = "" if a["threshold"] is None else f'{a["threshold"]:.3f}'
    ts_local = _format_ts(a["ts"])
    return (
        "<tr>"
        f'<td style="padding:6px 10px;border-bottom:1px solid #eee">{ts_local}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #eee">{a["alert_type"]}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:{color};'
        f'font-weight:600">{a["severity"]}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #eee">{a["parameter"] or ""}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #eee">{val}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #eee">{thr}</td>'
        "</tr>"
    )


def _build_html(rows, heading):
    head = "".join(
        f'<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #ddd">{h}</th>'
        for h in ("Timestamp", "Alert", "Severity", "Parameter", "Measured", "Threshold")
    )
    body = "".join(_row_html(r) for r in rows)
    return (
        '<div style="font-family:Arial,sans-serif;font-size:14px">'
        f"<h2 style='margin:0 0 4px'>{heading}</h2>"
        "<p style='color:#666;margin:0 0 14px'>AI-PBMS &middot; Team ANS_4X</p>"
        "<table style='border-collapse:collapse;width:100%'>"
        f"<thead>{head}</thead><tbody>{body}</tbody></table>"
        "<p style='color:#888;font-size:12px;margin-top:16px'>"
        "Automated message from the AI-PBMS battery monitoring system.</p></div>"
    )


def _plain(rows):
    return "\n".join(
        f'{_format_ts(r["ts"])}  [{r["severity"]}]  {r["alert_type"]}  '
        f'{r["parameter"] or ""}={r["measured_value"]}'
        for r in rows
    )


def _send(subject, rows, heading, recipients):
    """Returns True only if SMTP accepted the message."""
    if not recipients:
        print("no active recipients")
        return False
    if not (SMTP_USER and SMTP_PASS):
        print("SMTP_USER / SMTP_PASS not set")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = SENDER               # clients go in Bcc so they can't see each other
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(_plain(rows))
    msg.add_alternative(_build_html(rows, heading), subtype="html")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=30) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        return True
    except Exception as e:
        print(f"send failed: {e}")
        return False


def send_alert(alert_id):
    rows = [a for a in alerts.pending() if a["id"] == alert_id]
    if not rows:
        return False
    a = rows[0]
    sev = a["severity"]
    to = alerts.active_recipients(sev)
    if not to:
        alerts.mark_emailed([a["id"]])
        return False
    heading = {"CRITICAL": "Critical fault detected",
               "WARNING":  "Warning raised",
               "INFO":     "System event"}.get(sev, "Alert")
    ok = _send(f'[{sev}] {a["alert_type"]} — AI-PBMS', rows, heading, to)
    if ok:
        alerts.mark_emailed([a["id"]])
    return ok


def send_critical(alert_id):
    return send_alert(alert_id)


def send_digest():
    """Call on a timer. Mails everything not yet sent."""
    rows = alerts.pending()
    if not rows:
        print("nothing pending")
        return False
    crit = sum(1 for r in rows if r["severity"] == "CRITICAL")
    subject = f"AI-PBMS alert digest — {len(rows)} event(s)"
    if crit:
        subject = f"[{crit} CRITICAL] " + subject
    ok = _send(subject, rows, "Alert digest", alerts.active_recipients())
    if ok:
        alerts.mark_emailed([r["id"] for r in rows])
        print(f"sent {len(rows)} alert(s)")
    return ok


if __name__ == "__main__":
    alerts.init_db()
    if "--test" in sys.argv:
        alerts.add_recipient(SMTP_USER)
        alerts.log_alert("Cell Imbalance", "Delta V", 0.499, 0.150)
        send_digest()
    else:
        send_digest()
