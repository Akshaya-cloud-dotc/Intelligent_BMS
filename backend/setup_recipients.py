import os
import sqlite3
import alerts

alerts.init_db()

# WARNING -> ONLY akshayavg1@gmail.com
alerts.add_recipient("akshayavg1@gmail.com", "Akshaya (Personal)", "WARNING")

# CRITICAL -> 24e103@psgitech.ac.in and akshayavg1@psgitech.ac.in
alerts.add_recipient("24e103@psgitech.ac.in", "Team Member", "CRITICAL")
alerts.add_recipient("akshayavg1@psgitech.ac.in", "Akshaya (College)", "CRITICAL")

target_emails = ('akshayavg1@gmail.com', '24e103@psgitech.ac.in', 'akshayavg1@psgitech.ac.in')

# Update both database files if they exist
db_paths = [
    alerts.DB_PATH,
    os.path.join(os.path.dirname(__file__), "bms_alerts.db"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "bms_alerts.db")
]

for p in set(db_paths):
    if os.path.exists(p):
        with sqlite3.connect(p) as c:
            c.execute(f"UPDATE recipients SET active=0 WHERE email NOT IN {target_emails}")
            c.execute("UPDATE recipients SET active=1, min_severity='WARNING' WHERE email='akshayavg1@gmail.com'")
            c.execute("INSERT OR REPLACE INTO recipients (email, name, min_severity, active) VALUES ('24e103@psgitech.ac.in', 'Team Member', 'CRITICAL', 1)")
            c.execute("INSERT OR REPLACE INTO recipients (email, name, min_severity, active) VALUES ('akshayavg1@psgitech.ac.in', 'Akshaya (College)', 'CRITICAL', 1)")

print("Active Recipients Configuration:")
print("  WARNING  (only):", alerts.active_recipients("WARNING"))
print("  CRITICAL        :", alerts.active_recipients("CRITICAL"))
