"""Sample classes for Python data-coding interviews: log parsing, pandas, numpy, SQL.

Run: python interview_data_classes.py   (needs numpy, pandas; sqlite3 is built in)
"""
import heapq
import re
import sqlite3
from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

import numpy as np
import pandas as pd


# 1. LOG PARSING

@dataclass(frozen=True)
class LogRecord:
    ts: pd.Timestamp
    level: str
    service: str
    message: str


class LogParser:
    """Parses lines like: 2026-03-01T10:00:01Z ERROR svc=auth msg=timeout after 30s"""

    PATTERN = re.compile(
        r"^(?P<ts>\S+)\s+(?P<level>[A-Z]+)\s+svc=(?P<service>\w+)\s+msg=(?P<message>.*)$"
    )

    def __init__(self):
        self.bad_lines = 0

    def parse_line(self, line: str) -> Optional[LogRecord]:
        m = self.PATTERN.match(line.strip())
        if not m:
            self.bad_lines += 1  # count, don't crash, on malformed input
            return None
        return LogRecord(pd.Timestamp(m["ts"]), m["level"], m["service"], m["message"])

    def parse(self, lines: Iterable[str]) -> Iterator[LogRecord]:
        # generator: constant memory even for huge files
        for line in lines:
            rec = self.parse_line(line)
            if rec:
                yield rec

    @staticmethod
    def signature(message: str) -> str:
        """Collapse numbers/hex ids so similar messages group together."""
        message = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", message)
        return re.sub(r"\d+", "<N>", message)

    def top_error_signatures(self, records: Iterable[LogRecord], k: int = 3):
        counts = Counter(
            (r.service, self.signature(r.message)) for r in records if r.level == "ERROR"
        )
        return heapq.nlargest(k, counts.items(), key=lambda kv: kv[1])


# 2. PANDAS

class DeviceUsageAnalyzer:
    """Typical pandas tasks: clean, aggregate, window, flag."""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def clean(self) -> "DeviceUsageAnalyzer":
        df = self.df.copy()
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
        df["bytes"] = pd.to_numeric(df["bytes"], errors="coerce")
        df = df.dropna(subset=["ts", "device"])
        df = df.drop_duplicates(subset=["device", "ts"], keep="last")
        df["bytes"] = df["bytes"].fillna(0).clip(lower=0)
        self.df = df.sort_values(["device", "ts"]).reset_index(drop=True)
        return self

    def hourly_totals(self) -> pd.DataFrame:
        return (
            self.df.set_index("ts")
            .groupby("device")["bytes"]
            .resample("1h")
            .sum()
            .reset_index()
        )

    def add_rolling_zscore(self, window: int = 5) -> pd.DataFrame:
        g = self.df.groupby("device")["bytes"]
        # shift(1) so a point is compared with history that excludes itself
        mean = g.transform(lambda s: s.rolling(window, min_periods=3).mean().shift(1))
        std = g.transform(lambda s: s.rolling(window, min_periods=3).std().shift(1))
        out = self.df.copy()
        out["z"] = (out["bytes"] - mean) / std.replace(0, np.nan)
        return out

    def top_n_per_device(self, n: int = 2) -> pd.DataFrame:
        ranked = self.df.assign(
            rank=self.df.groupby("device")["bytes"].rank(method="first", ascending=False)
        )
        return ranked[ranked["rank"] <= n].sort_values(["device", "rank"])


# 3. NUMPY / STREAMING STATS

class RobustDetector:
    """Median/MAD detector: vectorised numpy, resistant to outliers."""

    def __init__(self, threshold: float = 3.5):
        self.threshold = threshold

    def detect(self, x) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        med = np.median(x)
        mad = np.median(np.abs(x - med))
        if mad == 0:
            return np.zeros(x.shape, dtype=bool)
        return np.abs(0.6745 * (x - med) / mad) > self.threshold


class StreamingEWMA:
    """O(1) memory per key: scales to many entities."""

    def __init__(self, alpha=0.1, threshold=4.0, warmup=20):
        self.alpha, self.threshold, self.warmup = alpha, threshold, warmup
        self.mean: Optional[float] = None
        self.var = 0.0
        self.n = 0

    def update(self, x: float) -> bool:
        self.n += 1
        if self.mean is None:
            self.mean = x
            return False
        std = self.var ** 0.5
        anomaly = self.n > self.warmup and std > 0 and abs(x - self.mean) > self.threshold * std
        if not anomaly:  # keep anomalies out of the baseline
            d = x - self.mean
            self.mean += self.alpha * d
            self.var = (1 - self.alpha) * (self.var + self.alpha * d * d)
        return anomaly


class SlidingWindowCounter:
    """Counts events in the last `seconds` (e.g. failed logins) with a deque."""

    def __init__(self, seconds: int):
        self.seconds = seconds
        self.events = deque()

    def add(self, t: float) -> int:
        self.events.append(t)
        while self.events and self.events[0] <= t - self.seconds:
            self.events.popleft()
        return len(self.events)


def cosine_top_k(query: np.ndarray, docs: np.ndarray, k: int = 3):
    q = query / np.linalg.norm(query)
    d = docs / np.linalg.norm(docs, axis=1, keepdims=True)
    sims = d @ q
    idx = np.argsort(-sims)[:k]
    return idx, sims[idx]


# 4. SQL (sqlite3, window functions)

class EventStore:
    """Small SQL wrapper. Window functions need SQLite >= 3.25 (bundled with modern Python)."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE events (device_id TEXT, ts TEXT, status TEXT, bytes INTEGER)"
        )

    def load(self, rows):
        self.conn.executemany("INSERT INTO events VALUES (?,?,?,?)", rows)  # parameterised, no string concat

    def query(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchall()

    def running_avg_and_delta(self):
        return self.query(
            """
            SELECT device_id, ts, bytes,
                   AVG(bytes) OVER (PARTITION BY device_id ORDER BY ts
                                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS avg3,
                   bytes - LAG(bytes) OVER (PARTITION BY device_id ORDER BY ts) AS delta
            FROM events ORDER BY device_id, ts
            """
        )

    def top_per_device(self, n: int):
        return self.query(
            """
            SELECT device_id, ts, bytes FROM (
              SELECT *, ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY bytes DESC) AS rn
              FROM events
            ) WHERE rn <= ? ORDER BY device_id, rn
            """,
            (n,),
        )

    def consecutive_failures(self, min_len: int = 3):
        # gaps-and-islands: row_number difference is constant inside a run of the same status
        return self.query(
            """
            WITH t AS (
              SELECT device_id, ts, status,
                     ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY ts)
                   - ROW_NUMBER() OVER (PARTITION BY device_id, status ORDER BY ts) AS grp
              FROM events
            )
            SELECT device_id, MIN(ts), COUNT(*) FROM t
            WHERE status = 'FAIL' GROUP BY device_id, grp HAVING COUNT(*) >= ?
            """,
            (min_len,),
        )


# DEMO / SELF-CHECK

def _demo():
    lines = [
        "2026-03-01T10:00:01Z ERROR svc=auth msg=timeout after 30s",
        "2026-03-01T10:00:02Z ERROR svc=auth msg=timeout after 31s",
        "2026-03-01T10:00:03Z WARN svc=billing msg=slow query 900ms",
        "garbage line",
        "2026-03-01T10:00:04Z ERROR svc=db msg=connection refused",
        "2026-03-01T10:00:05Z ERROR svc=auth msg=timeout after 29s",
    ]
    p = LogParser()
    top = p.top_error_signatures(p.parse(lines), k=2)
    assert top[0] == (("auth", "timeout after <N>s"), 3) and p.bad_lines == 1
    print("log parser ok:", top)

    raw = pd.DataFrame({
        "device": ["a", "a", "a", "a", "a", "a", "b", "b", None],
        "ts": ["2026-03-01 10:00", "2026-03-01 11:00", "2026-03-01 12:00", "2026-03-01 13:00",
               "2026-03-01 14:00", "2026-03-01 14:00", "2026-03-01 10:00", "bad-date", "2026-03-01 10:00"],
        "bytes": [100, 105, 98, 102, 5000, 5000, 50, 60, 1],
    })
    an = DeviceUsageAnalyzer(raw).clean()
    assert len(an.df) == 6  # bad date, null device, duplicate row removed
    z = an.add_rolling_zscore(window=4)
    assert z.loc[z["bytes"] == 5000, "z"].iloc[0] > 3
    print("pandas ok; hourly rows:", len(an.hourly_totals()), "top2:", len(an.top_n_per_device(2)))

    assert RobustDetector().detect([10, 11, 9, 10, 12, 10, 100])[-1]
    det, rng, hits = StreamingEWMA(), np.random.default_rng(1), []
    for i in range(300):
        x = 90.0 if i == 250 else rng.normal(50, 2)
        if det.update(x):
            hits.append(i)
    assert 250 in hits
    sw = SlidingWindowCounter(10)
    assert [sw.add(t) for t in (0, 3, 9, 11, 25)] == [1, 2, 3, 3, 1]
    idx, _ = cosine_top_k(np.array([1.0, 0, 0]), np.array([[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0]]), k=2)
    assert list(idx) == [0, 1]
    print("numpy ok; EWMA hits:", hits)

    s = EventStore()
    s.load([
        ("a", "10:00", "OK", 100), ("a", "10:01", "FAIL", 10), ("a", "10:02", "FAIL", 20),
        ("a", "10:03", "FAIL", 30), ("a", "10:04", "OK", 400), ("b", "10:00", "FAIL", 5),
    ])
    assert s.consecutive_failures(3) == [("a", "10:01", 3)]
    assert s.top_per_device(1) == [("a", "10:04", 400), ("b", "10:00", 5)]
    assert s.running_avg_and_delta()[1][4] == -90
    print("sql ok")


if __name__ == "__main__":
    _demo()
