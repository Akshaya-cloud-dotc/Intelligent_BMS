import alerts
import sqlite3

alerts.init_db()

alerts.add_recipient("akshayavg1@gmail.com", "Akshaya", "WARNING")
alerts.add_recipient("24e102@psgitech.ac.in", "Team", "CRITICAL")
alerts.add_recipient("24e103@psgitech.ac.in", "Team", "CRITICAL")

# deactivate anyone not in the current list
with sqlite3.connect("bms_alerts.db") as c:
    c.execute("UPDATE recipients SET active=0 WHERE email NOT IN "
              "('akshayavg1@gmail.com','24e102@psgitech.ac.in','24e103@psgitech.ac.in')")

print("WARNING :", alerts.active_recipients("WARNING"))
print("CRITICAL:", alerts.active_recipients("CRITICAL"))
