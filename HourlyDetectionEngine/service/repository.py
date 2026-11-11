"""Persistence (Repository pattern), backed by SQLite from the standard library.

The engine depends on the `DetectionStore` Protocol, not on SQLite, so this class can be
swapped for S3/Parquet + ClickHouse/Postgres implementations without touching the engine.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Protocol

from .models import (FIELD_NAME_RE, Alert, DeadLetter, ErrorType, Event, HourWindow, RunState,
                     RunStatus, Severity, floor_hour, utcnow)

TRANSIENT_ERRORS: tuple[type[Exception], ...] = (sqlite3.OperationalError,)

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"   # fixed width -> string order == time order


def to_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError("naive datetime; use timezone-aware UTC")
    return ts.astimezone(timezone.utc).strftime(_TS_FORMAT)


def from_iso(value: str) -> datetime:
    return datetime.strptime(value, _TS_FORMAT).replace(tzinfo=timezone.utc)


class DetectionStore(Protocol):
    def iter_events(self, source: str, window: HourWindow, batch_size: int = ...) -> Iterator[Event]: ...
    def hourly_counts(self, source: str, field: str, start: datetime, end: datetime) -> list[tuple[datetime, str, int]]: ...
    def delete_alerts(self, source: str, run_hour: datetime) -> int: ...
    def add_alerts(self, alerts: Iterable[Alert]) -> int: ...
    def add_dead_letters(self, items: Iterable[DeadLetter]) -> None: ...
    def save_run(self, status: RunStatus) -> None: ...
    def get_run(self, source: str, run_hour: datetime) -> RunStatus | None: ...
    def list_runs(self, since: datetime) -> list[RunStatus]: ...
    def record_rule_outcome(self, rule_id: str, failed: bool, disable_after: int) -> bool: ...
    def disabled_rules(self) -> set[str]: ...


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events (
    source      TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    event_hour  TEXT NOT NULL,          -- "partition" key: we only ever read one hour
    event_time  TEXT NOT NULL,
    attributes  TEXT NOT NULL,          -- JSON
    PRIMARY KEY (source, event_id)
);
CREATE INDEX IF NOT EXISTS ix_events_source_hour ON events (source, event_hour);

CREATE TABLE IF NOT EXISTS alerts (
    run_hour    TEXT NOT NULL,
    source      TEXT NOT NULL,
    rule_id     TEXT NOT NULL,
    severity    TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    event_time  TEXT NOT NULL,
    details     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (run_hour, rule_id, event_id)
);
CREATE INDEX IF NOT EXISTS ix_alerts_hour_source ON alerts (run_hour, source);

CREATE TABLE IF NOT EXISTS dead_letters (
    run_hour    TEXT NOT NULL,
    source      TEXT NOT NULL,
    rule_id     TEXT NOT NULL,
    error_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    logged_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dead_letters_hour ON dead_letters (run_hour);

CREATE TABLE IF NOT EXISTS runs (
    run_hour        TEXT NOT NULL,
    source          TEXT NOT NULL,
    state           TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    events_scanned  INTEGER NOT NULL DEFAULT 0,
    alerts_written  INTEGER NOT NULL DEFAULT 0,
    rules_total     INTEGER NOT NULL DEFAULT 0,
    rules_failed    INTEGER NOT NULL DEFAULT 0,
    message         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (run_hour, source)
);

CREATE TABLE IF NOT EXISTS rule_health (
    rule_id               TEXT PRIMARY KEY,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    disabled              INTEGER NOT NULL DEFAULT 0,
    updated_at            TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, path: str | Path = "detections.db") -> None:
        self.path = str(path)
        self._write_lock = threading.Lock()   # SQLite allows one writer at a time
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------ events

    def add_events(self, events: Iterable[Event]) -> int:
        rows = [(e.source, e.event_id, to_iso(floor_hour(e.event_time)), to_iso(e.event_time),
                 json.dumps(e.attributes, default=str)) for e in events]
        with self._write_lock, self._connect() as conn:
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO events (source, event_id, event_hour, event_time, attributes) "
                "VALUES (?, ?, ?, ?, ?)", rows)
            return conn.total_changes - before

    def iter_events(self, source: str, window: HourWindow, batch_size: int = 10_000) -> Iterator[Event]:
        """Stream one hour of events with constant memory (generator + fetchmany)."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT event_id, source, event_time, attributes FROM events "
                "WHERE source = ? AND event_hour = ?", (source, to_iso(window.start)))
            while rows := cursor.fetchmany(batch_size):
                for r in rows:
                    yield Event(r["event_id"], r["source"], from_iso(r["event_time"]), json.loads(r["attributes"]))

    def hourly_counts(self, source: str, field: str, start: datetime, end: datetime) -> list[tuple[datetime, str, int]]:
        """(hour, value of `field`, count) for [start, end) - used as ML baseline history."""
        if not FIELD_NAME_RE.match(field):
            raise ValueError(f"invalid field name {field!r}")
        path = f"$.{field}"
        sql = ("SELECT event_hour, json_extract(attributes, ?) AS k, COUNT(*) AS n FROM events "
               "WHERE source = ? AND event_hour >= ? AND event_hour < ? "
               "AND json_extract(attributes, ?) IS NOT NULL GROUP BY event_hour, k")
        with self._connect() as conn:
            rows = conn.execute(sql, (path, source, to_iso(start), to_iso(end), path)).fetchall()
        return [(from_iso(r["event_hour"]), str(r["k"]), int(r["n"])) for r in rows]

    # ------------------------------------------------------------ alerts

    def delete_alerts(self, source: str, run_hour: datetime) -> int:
        with self._write_lock, self._connect() as conn:
            return conn.execute("DELETE FROM alerts WHERE source = ? AND run_hour = ?",
                                (source, to_iso(run_hour))).rowcount

    def add_alerts(self, alerts: Iterable[Alert]) -> int:
        now = to_iso(utcnow())
        rows = [(to_iso(a.run_hour), a.source, a.rule_id, a.severity.value, a.event_id,
                 to_iso(a.event_time), json.dumps(a.details, default=str), now) for a in alerts]
        with self._write_lock, self._connect() as conn:
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO alerts (run_hour, source, rule_id, severity, event_id, event_time, "
                "details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
            return conn.total_changes - before

    def list_alerts(self, run_hour: datetime | None = None, source: str | None = None,
                    rule_id: str | None = None, limit: int = 100) -> list[Alert]:
        clauses, params = self._filters(run_hour=run_hour, source=source, rule_id=rule_id)
        # only fixed column names are formatted in; all values are bound parameters
        sql = f"SELECT * FROM alerts {clauses} ORDER BY run_hour DESC, rule_id, event_id LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(sql, (*params, limit)).fetchall()
        return [Alert(from_iso(r["run_hour"]), r["source"], r["rule_id"], Severity(r["severity"]),
                      r["event_id"], from_iso(r["event_time"]), json.loads(r["details"])) for r in rows]

    # ------------------------------------------------------------ dead letters

    def add_dead_letters(self, items: Iterable[DeadLetter]) -> None:
        rows = [(to_iso(d.run_hour), d.source, d.rule_id, d.error_type.value, d.message, to_iso(d.logged_at))
                for d in items]
        with self._write_lock, self._connect() as conn:
            conn.executemany("INSERT INTO dead_letters VALUES (?, ?, ?, ?, ?, ?)", rows)

    def list_dead_letters(self, run_hour: datetime | None = None, limit: int = 100) -> list[DeadLetter]:
        clauses, params = self._filters(run_hour=run_hour)
        sql = f"SELECT * FROM dead_letters {clauses} ORDER BY logged_at DESC LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(sql, (*params, limit)).fetchall()
        return [DeadLetter(from_iso(r["run_hour"]), r["source"], r["rule_id"], ErrorType(r["error_type"]),
                           r["message"], from_iso(r["logged_at"])) for r in rows]

    # ------------------------------------------------------------ runs

    def save_run(self, s: RunStatus) -> None:
        sql = """INSERT INTO runs (run_hour, source, state, started_at, finished_at, events_scanned,
                                   alerts_written, rules_total, rules_failed, message)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT (run_hour, source) DO UPDATE SET
                   state = excluded.state, started_at = excluded.started_at,
                   finished_at = excluded.finished_at, events_scanned = excluded.events_scanned,
                   alerts_written = excluded.alerts_written, rules_total = excluded.rules_total,
                   rules_failed = excluded.rules_failed, message = excluded.message"""
        with self._write_lock, self._connect() as conn:
            conn.execute(sql, (to_iso(s.run_hour), s.source, s.state.value, to_iso(s.started_at),
                               to_iso(s.finished_at) if s.finished_at else None, s.events_scanned,
                               s.alerts_written, s.rules_total, s.rules_failed, s.message))

    def get_run(self, source: str, run_hour: datetime) -> RunStatus | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE source = ? AND run_hour = ?",
                               (source, to_iso(run_hour))).fetchone()
        return self._to_run(row) if row else None

    def list_runs(self, since: datetime) -> list[RunStatus]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs WHERE run_hour >= ? ORDER BY run_hour DESC, source",
                                (to_iso(since),)).fetchall()
        return [self._to_run(r) for r in rows]

    def last_successful_run(self) -> datetime | None:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(finished_at) AS t FROM runs WHERE state IN (?, ?)",
                               (RunState.SUCCEEDED.value, RunState.PARTIAL.value)).fetchone()
        return from_iso(row["t"]) if row and row["t"] else None

    # ------------------------------------------------------------ rule health

    def record_rule_outcome(self, rule_id: str, failed: bool, disable_after: int = 3) -> bool:
        """Track consecutive failed runs; returns True when the rule has just been disabled."""
        now = to_iso(utcnow())
        with self._write_lock, self._connect() as conn:
            if not failed:
                conn.execute("INSERT INTO rule_health (rule_id, consecutive_failures, disabled, updated_at) "
                             "VALUES (?, 0, 0, ?) ON CONFLICT (rule_id) DO UPDATE SET "
                             "consecutive_failures = 0, updated_at = excluded.updated_at", (rule_id, now))
                return False
            conn.execute("INSERT INTO rule_health (rule_id, consecutive_failures, disabled, updated_at) "
                         "VALUES (?, 1, 0, ?) ON CONFLICT (rule_id) DO UPDATE SET "
                         "consecutive_failures = consecutive_failures + 1, updated_at = excluded.updated_at",
                         (rule_id, now))
            row = conn.execute("SELECT consecutive_failures, disabled FROM rule_health WHERE rule_id = ?",
                               (rule_id,)).fetchone()
            if row["consecutive_failures"] >= disable_after and not row["disabled"]:
                conn.execute("UPDATE rule_health SET disabled = 1 WHERE rule_id = ?", (rule_id,))
                return True
            return False

    def disabled_rules(self) -> set[str]:
        with self._connect() as conn:
            return {r["rule_id"] for r in conn.execute("SELECT rule_id FROM rule_health WHERE disabled = 1")}

    def enable_rule(self, rule_id: str) -> bool:
        with self._write_lock, self._connect() as conn:
            return conn.execute("UPDATE rule_health SET disabled = 0, consecutive_failures = 0 "
                                "WHERE rule_id = ?", (rule_id,)).rowcount > 0

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _filters(**filters: Any) -> tuple[str, list[Any]]:
        clauses, params = [], []
        for column, value in filters.items():
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(to_iso(value) if isinstance(value, datetime) else value)
        return ("WHERE " + " AND ".join(clauses)) if clauses else "", params

    @staticmethod
    def _to_run(r: sqlite3.Row) -> RunStatus:
        return RunStatus(
            run_hour=from_iso(r["run_hour"]), source=r["source"], state=RunState(r["state"]),
            started_at=from_iso(r["started_at"]),
            finished_at=from_iso(r["finished_at"]) if r["finished_at"] else None,
            events_scanned=r["events_scanned"], alerts_written=r["alerts_written"],
            rules_total=r["rules_total"], rules_failed=r["rules_failed"], message=r["message"])
