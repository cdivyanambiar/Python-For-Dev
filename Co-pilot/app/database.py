import sqlite3
import time
from contextlib import closing
from pathlib import Path

SCHEMA = """Table switches:
id INTEGER, name TEXT, model TEXT, site TEXT, status TEXT ('online' or 'offline'),
firmware TEXT, cpu_percent REAL, temperature_c REAL, last_seen TEXT (UTC).
Table alerts:
id INTEGER, switch_id INTEGER, severity TEXT ('critical', 'warning', 'info'),
message TEXT, state TEXT ('open' or 'closed'), created_at TEXT (UTC).
alerts.switch_id references switches.id. Data is a fictional static snapshot."""


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS switches (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, model TEXT NOT NULL,
                site TEXT NOT NULL, status TEXT NOT NULL, firmware TEXT NOT NULL,
                cpu_percent REAL NOT NULL, temperature_c REAL NOT NULL, last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY, switch_id INTEGER NOT NULL REFERENCES switches(id),
                severity TEXT NOT NULL, message TEXT NOT NULL, state TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO switches VALUES
                (1, 'sw-lab-01', 'CX-6200', 'Lab', 'online', '10.13', 42, 48, '2026-11-18 08:00:00'),
                (2, 'sw-lab-02', 'CX-6200', 'Lab', 'offline', '10.12', 0, 0, '2026-11-18 07:10:00'),
                (3, 'sw-dc-01', 'CX-6300', 'Data Center', 'online', '10.13', 93, 72, '2026-11-18 08:00:00'),
                (4, 'sw-branch-01', 'CX-6100', 'Branch', 'online', '10.11', 23, 41, '2026-11-18 08:00:00');
            INSERT OR IGNORE INTO alerts VALUES
                (1, 2, 'critical', 'Switch unreachable', 'open', '2026-11-18 07:15:00'),
                (2, 3, 'warning', 'High CPU utilization', 'open', '2026-11-18 07:50:00'),
                (3, 1, 'info', 'Firmware update completed', 'closed', '2026-11-17 12:00:00');
        """)


def execute_read_only(path: Path, sql: str) -> dict:
    """Run untrusted model SQL against only the two demo tables."""
    allowed_functions = {
        "avg", "count", "min", "max", "sum", "round", "lower", "upper",
        "coalesce", "ifnull", "like", "length", "strftime", "date", "datetime",
        "julianday", "substr", "replace", "abs", "total",
    }

    def authorize(action, arg1, arg2, database, source):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and database == "main" and arg1 in {"switches", "alerts"}:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in allowed_functions:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.set_authorizer(authorize)
        deadline = time.monotonic() + 2
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            cursor = connection.execute(sql)
            if cursor.description is None:
                raise ValueError("The SQL query must return rows.")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(51)
        except sqlite3.Error as exc:
            raise ValueError(f"SQL query rejected or failed: {exc}") from exc
    return {"columns": columns, "rows": [list(row) for row in rows[:50]], "truncated": len(rows) > 50}
