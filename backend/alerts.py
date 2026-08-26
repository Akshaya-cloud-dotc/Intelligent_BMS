"""
alerts.py — persistent alert store for AI-PBMS.

Drop next to app.py. Call init_db() once at startup, then log_alert(...)
wherever you currently append to your in-memory alert list.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.getenv("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras

DB_PATH = os.getenv("BMS_DB", "bms_alerts.db")

# Suppress a repeat of the same (alert_type, parameter) for this long.
DEDUP_WINDOW_MIN = 60

if USE_PG:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS alerts (
        id             SERIAL PRIMARY KEY,
        ts             TEXT NOT NULL,
        alert_type     TEXT NOT NULL,
        severity       TEXT NOT NULL,
        parameter      TEXT,
        measured_value REAL,
        threshold      REAL,
        status         TEXT NOT NULL DEFAULT 'ACTIVE',
        resolved_at    TEXT,
        emailed        INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_emailed  ON alerts(emailed, ts);
    CREATE INDEX IF NOT EXISTS idx_dedup    ON alerts(alert_type, parameter, ts);

    CREATE TABLE IF NOT EXISTS recipients (
        id      SERIAL PRIMARY KEY,
        email   TEXT NOT NULL UNIQUE,
        name    TEXT,
        min_severity TEXT NOT NULL DEFAULT 'CRITICAL',
        active  INTEGER NOT NULL DEFAULT 1
    );
    """
else:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS alerts (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        ts             TEXT NOT NULL,
        alert_type     TEXT NOT NULL,
        severity       TEXT NOT NULL,
        parameter      TEXT,
        measured_value REAL,
        threshold      REAL,
        status         TEXT NOT NULL DEFAULT 'ACTIVE',
        resolved_at    TEXT,
        emailed        INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_emailed  ON alerts(emailed, ts);
    CREATE INDEX IF NOT EXISTS idx_dedup    ON alerts(alert_type, parameter, ts);

    CREATE TABLE IF NOT EXISTS recipients (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        email   TEXT NOT NULL UNIQUE,
        name    TEXT,
        min_severity TEXT NOT NULL DEFAULT 'CRITICAL',
        active  INTEGER NOT NULL DEFAULT 1
    );
    """


class UnifiedCursor:
    def __init__(self, cursor, is_pg=False):
        self.cursor = cursor
        self.is_pg = is_pg

    @property
    def lastrowid(self):
        if self.is_pg:
            try:
                row = self.cursor.fetchone()
                if row:
                    return row['id']
            except Exception:
                pass
            return None
        else:
            return self.cursor.lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __iter__(self):
        return iter(self.cursor)


def _rewrite_query(query, is_pg):
    if is_pg:
        query = query.replace("?", "%s")
        query = query.replace("ifnull", "coalesce")
        if query.strip().upper().startswith("INSERT INTO ALERTS"):
            query += " RETURNING id"
    return query


class UnifiedConnection:
    def __init__(self, conn, is_pg=False):
        self.conn = conn
        self.is_pg = is_pg

    def __enter__(self):
        self.cursor = None
        if self.is_pg:
            self.conn.__enter__()
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            self.conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_pg:
            if self.cursor:
                self.cursor.close()
            self.conn.__exit__(exc_type, exc_val, exc_tb)
            self.conn.close()
        else:
            self.conn.__exit__(exc_type, exc_val, exc_tb)
            self.conn.close()

    def execute(self, query, args=None):
        query = _rewrite_query(query, self.is_pg)
        if self.is_pg:
            if args is None:
                self.cursor.execute(query)
            else:
                self.cursor.execute(query, args)
            return UnifiedCursor(self.cursor, self.is_pg)
        else:
            if args is None:
                cur = self.conn.execute(query)
            else:
                cur = self.conn.execute(query, args)
            return UnifiedCursor(cur, self.is_pg)

    def executemany(self, query, args_list):
        query = _rewrite_query(query, self.is_pg)
        if self.is_pg:
            self.cursor.executemany(query, args_list)
            return UnifiedCursor(self.cursor, self.is_pg)
        else:
            cur = self.conn.executemany(query, args_list)
            return UnifiedCursor(cur, self.is_pg)

    def executescript(self, script):
        if self.is_pg:
            for statement in script.split(';'):
                stmt = statement.strip()
                if stmt:
                    self.cursor.execute(stmt)
        else:
            self.conn.executescript(script)


def _conn():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
        return UnifiedConnection(conn, is_pg=True)
    else:
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return UnifiedConnection(c, is_pg=False)


SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)
        if USE_PG:
            c.execute("ALTER TABLE recipients ADD COLUMN IF NOT EXISTS min_severity TEXT NOT NULL DEFAULT 'CRITICAL'")
        else:
            cols = [r[1] for r in c.execute("PRAGMA table_info(recipients)")]
            if "min_severity" not in cols:
                c.execute("ALTER TABLE recipients ADD COLUMN "
                          "min_severity TEXT NOT NULL DEFAULT 'CRITICAL'")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify(alert_type, measured, threshold, ml_confidence=None):
    """
    Three-tier severity, aligned with the project's confidence framework.

    CRITICAL -> hard threshold breach, or ML confidence >= 0.85
    WARNING  -> ML confidence 0.5-0.85, or within 80% of threshold
    INFO     -> everything else (resolutions, mode changes, reconnects)
    """
    if ml_confidence is not None:
        if ml_confidence >= 0.85:
            return "CRITICAL"
        if ml_confidence >= 0.50:
            return "WARNING"
        return "INFO"

    if measured is None or threshold is None:
        return "INFO"
    if measured >= threshold:
        return "CRITICAL"
    if measured >= 0.8 * threshold:
        return "WARNING"
    return "INFO"


def _recently_logged(c, alert_type, parameter):
    cutoff = (datetime.now(timezone.utc)
              - timedelta(minutes=DEDUP_WINDOW_MIN)).isoformat(timespec="seconds")
    row = c.execute(
        "SELECT 1 FROM alerts WHERE alert_type=? AND coalesce(parameter,'')=coalesce(?,'')"
        " AND ts >= ? LIMIT 1",
        (alert_type, parameter, cutoff),
    ).fetchone()
    return row is not None


def log_alert(alert_type, parameter=None, measured=None, threshold=None,
              ml_confidence=None, severity=None):
    """
    Record an alert. Returns the row id, or None if suppressed as a duplicate.

    Dedup matters here: cell_v1 sits chronically low, so cell-imbalance would
    otherwise fire on every polling cycle and flood the mailbox.
    """
    sev = severity or classify(alert_type, measured, threshold, ml_confidence)
    with _conn() as c:
        if _recently_logged(c, alert_type, parameter):
            return None
        cur = c.execute(
            "INSERT INTO alerts (ts, alert_type, severity, parameter,"
            " measured_value, threshold) VALUES (?,?,?,?,?,?)",
            (_now(), alert_type, sev, parameter, measured, threshold),
        )
        return cur.lastrowid


def resolve_alert(alert_type, parameter=None):
    with _conn() as c:
        c.execute(
            "UPDATE alerts SET status='RESOLVED', resolved_at=?"
            " WHERE alert_type=? AND coalesce(parameter,'')=coalesce(?,'')"
            " AND status='ACTIVE'",
            (_now(), alert_type, parameter),
        )


def history(limit=50):
    """Feed this to the System Alert History panel instead of the in-memory list."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def pending(severity=None):
    q = "SELECT * FROM alerts WHERE emailed=0"
    args = []
    if severity:
        q += " AND severity=?"
        args.append(severity)
    q += " ORDER BY id"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def mark_emailed(ids):
    if not ids:
        return
    with _conn() as c:
        c.executemany("UPDATE alerts SET emailed=1 WHERE id=?", [(i,) for i in ids])


def active_recipients(severity=None):
    with _conn() as c:
        rows = c.execute(
            "SELECT email, min_severity FROM recipients WHERE active=1"
        ).fetchall()
    if severity is None:
        return [r["email"] for r in rows]
    return [r["email"] for r in rows
            if r["min_severity"] == severity.upper()]


def add_recipient(email, name=None, min_severity="CRITICAL"):
    with _conn() as c:
        c.execute(
            "INSERT INTO recipients (email, name, min_severity) VALUES (?,?,?)"
            " ON CONFLICT(email) DO UPDATE SET name=excluded.name,"
            " min_severity=excluded.min_severity, active=1",
            (email, name, min_severity.upper()),
        )


if __name__ == "__main__":
    init_db()
    print(f"initialised {DB_PATH}")
