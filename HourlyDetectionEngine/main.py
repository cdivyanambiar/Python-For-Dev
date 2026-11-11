"""End-to-end demo with synthetic data. No external services needed.

    python main.py
"""
from __future__ import annotations

import logging
import random
import tempfile
import uuid
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

from service.container import Container, build_container
from service.models import Event, HourWindow, RunStatus, utcnow

USERS = [f"user{i:02d}" for i in range(20)]
NORMAL_PROCESSES = [
    ("chrome.exe", "--type=renderer", "C:/Program Files/Google/Chrome"),
    ("bash", "-c ls -la", "/usr/bin"),
    ("python", "app.py --port 8080", "/usr/bin"),
    ("powershell.exe", "-File backup.ps1", "C:/Windows/System32"),
]


def _event(source: str, window: HourWindow, rng: random.Random, **attrs: Any) -> Event:
    ts = window.start + timedelta(seconds=rng.randrange(3600), microseconds=rng.randrange(1_000_000))
    return Event(uuid.uuid4().hex, source, ts, attrs)


def edr_events(window: HourWindow, rng: random.Random, normal: int = 5_000) -> Iterator[Event]:
    for _ in range(normal):
        name, args, path = rng.choice(NORMAL_PROCESSES)
        yield _event("edr", window, rng, process_name=name, process_args=args, process_path=path,
                     uid=rng.choice([0, 1000, 1001]), username=rng.choice(USERS))
    for _ in range(3):
        yield _event("edr", window, rng, process_name="PowerShell.exe", process_args="-NoP -Enc SQBFAFgA",
                     process_path="C:/Windows/System32", uid=1000, username="user03")
    for _ in range(2):
        yield _event("edr", window, rng, process_name="xmrig", process_args="--donate-level 1",
                     process_path="/tmp/.x/xmrig", uid=0, username="root")


def auth_events(window: HourWindow, rng: random.Random, attack: bool = False) -> Iterator[Event]:
    for user in USERS:
        for _ in range(rng.randint(2, 6)):
            yield _event("auth", window, rng, username=user, outcome="SUCCESS", ip=f"10.0.0.{rng.randint(1, 254)}")
    if attack:
        for _ in range(25):   # brute force -> threshold rule (and ML)
            yield _event("auth", window, rng, username="mallory", outcome="FAILURE", ip="203.0.113.7")
        for _ in range(40):   # stolen session reused -> only the ML rule notices
            yield _event("auth", window, rng, username="user07", outcome="SUCCESS", ip="198.51.100.9")


def show(c: Container, title: str, statuses: list[RunStatus], window: HourWindow) -> None:
    print(f"\n== {title} ==")
    print(f"{'source':8} {'state':10} {'events':>8} {'alerts':>7} {'failed':>7}")
    for s in statuses:
        print(f"{s.source:8} {s.state.value:10} {s.events_scanned:>8,} {s.alerts_written:>7} "
              f"{s.rules_failed:>3}/{s.rules_total}")
    by_rule = Counter(a.rule_id for a in c.store.list_alerts(run_hour=window.start, limit=10_000))
    print("alerts by rule:", dict(sorted(by_rule.items())))


def main() -> None:
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")
    rng = random.Random(7)
    with tempfile.TemporaryDirectory() as tmp:
        c = build_container(db_path=Path(tmp) / "demo.db")
        window = HourWindow.previous(utcnow())
        print(f"Target hour: {window}")

        history = (e for h in range(168, 0, -1)
                   for e in auth_events(HourWindow(window.start - timedelta(hours=h)), rng))
        loaded = c.store.add_events(history)
        loaded += c.store.add_events(auth_events(window, rng, attack=True))
        loaded += c.store.add_events(edr_events(window, rng))
        print(f"Loaded {loaded:,} events (7 days of auth history + the target hour)")

        show(c, "Run 1", c.engine.run_hour(window), window)
        print("dead letters (bad rules isolated, other rules still alerted):")
        for d in c.store.list_dead_letters(run_hour=window.start):
            print(f"  {d.rule_id} [{d.error_type.value}] {d.message[:100]}")
        print("ML alerts:")
        for a in c.store.list_alerts(run_hour=window.start, rule_id="AUTH-002"):
            print(f"  {a.details}")

        show(c, "Run 2 - same hour again (idempotent: same alert count)", c.engine.run_hour(window), window)
        show(c, "Run 3 - broken rules fail a 3rd time in a row", c.engine.run_hour(window), window)
        for n in c.inbox.recent(topic="rule.disabled"):
            print(f"  NOTIFY {n.topic}: {n.message}")

        print("\n== SLA watchdog, 2h later: the next hour was never run ==")
        for n in c.watchdog.check(now=window.end + timedelta(hours=2, minutes=1)):
            print(f"  NOTIFY {n.topic}: {n.message}")


if __name__ == "__main__":
    main()
