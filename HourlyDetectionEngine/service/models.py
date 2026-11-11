"""Domain models: plain dataclasses + enums, no I/O."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def floor_hour(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("naive datetime; use timezone-aware UTC")
    return ts.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RunState(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ErrorType(str, Enum):
    COMPILE = "COMPILE"   # bad rule definition, found before scanning
    RUNTIME = "RUNTIME"   # rule raised while evaluating events
    INFRA = "INFRA"       # storage / network / worker crash


@dataclass(frozen=True, slots=True)
class HourWindow:
    """Half-open UTC range [start, end) of exactly one hour."""

    start: datetime

    def __post_init__(self) -> None:
        if self.start.utcoffset() != timedelta(0):
            raise ValueError("HourWindow.start must be UTC")
        if self.start != floor_hour(self.start):
            raise ValueError("HourWindow.start must be on the hour")

    @property
    def end(self) -> datetime:
        return self.start + timedelta(hours=1)

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts < self.end

    @classmethod
    def of(cls, ts: datetime) -> HourWindow:
        return cls(floor_hour(ts))

    @classmethod
    def previous(cls, now: datetime) -> HourWindow:
        """The last *complete* hour before `now`."""
        return cls(floor_hour(now) - timedelta(hours=1))

    def __str__(self) -> str:
        return self.start.strftime("%Y-%m-%dT%H:00Z")


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    source: str
    event_time: datetime
    attributes: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        return self.attributes.get(name, default)


@dataclass(frozen=True, slots=True)
class Finding:
    """What a rule returns; the engine turns it into an Alert."""

    event_id: str
    event_time: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Alert:
    run_hour: datetime
    source: str
    rule_id: str
    severity: Severity
    event_id: str
    event_time: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeadLetter:
    run_hour: datetime
    source: str
    rule_id: str
    error_type: ErrorType
    message: str
    logged_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class RunStatus:
    run_hour: datetime
    source: str
    state: RunState = RunState.RUNNING
    started_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None
    events_scanned: int = 0
    alerts_written: int = 0
    rules_total: int = 0
    rules_failed: int = 0
    message: str = ""

    @property
    def is_complete(self) -> bool:
        return self.state in (RunState.SUCCEEDED, RunState.PARTIAL)
