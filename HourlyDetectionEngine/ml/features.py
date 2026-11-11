"""Feature building for per-entity hourly behaviour."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable


def history_by_key(rows: Iterable[tuple[datetime, str, int]]) -> dict[str, list[float]]:
    """(hour, key, count) rows -> {key: [count for every hour that had data]}.

    Hours where a key had no events become 0, so a normally quiet user who suddenly
    becomes busy stands out."""
    counts: dict[tuple[datetime, str], int] = {}
    hours: set[datetime] = set()
    keys: set[str] = set()
    for hour, key, count in rows:
        counts[(hour, key)] = count
        hours.add(hour)
        keys.add(key)
    ordered_hours = sorted(hours)
    history: dict[str, list[float]] = defaultdict(list)
    for key in keys:
        history[key] = [float(counts.get((hour, key), 0)) for hour in ordered_hours]
    return dict(history)
