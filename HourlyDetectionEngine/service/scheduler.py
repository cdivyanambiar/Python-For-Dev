"""Background workers: hourly scheduler and SLA watchdog (two *independent* schedules).

In production these map to Airflow (schedule + dagrun_timeout) and an external monitor
(Grafana/Datadog) - see README."""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Callable

from .catalog import RuleCatalog
from .engine import DetectionEngine
from .models import HourWindow, RunState, RunStatus, Severity, floor_hour, utcnow
from .notifier import Notification, NotificationHub
from .repository import DetectionStore

log = logging.getLogger(__name__)

Clock = Callable[[], datetime]


class BackgroundWorker(ABC):
    """Template Method: the loop is fixed; subclasses fill in `seconds_until_next` and `tick`."""

    name = "worker"

    def __init__(self, clock: Clock = utcnow) -> None:
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @abstractmethod
    def seconds_until_next(self) -> float: ...

    @abstractmethod
    def tick(self) -> None: ...

    def on_start(self) -> None:
        """Hook: runs once in the worker thread before the loop."""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name=self.name, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _loop(self) -> None:
        try:
            self.on_start()
        except Exception:
            log.exception("%s on_start failed", self.name)
        while not self._stop.wait(max(0.0, self.seconds_until_next())):
            try:
                self.tick()
            except Exception:  # keep the loop alive; the watchdog reports missed runs
                log.exception("%s tick failed", self.name)


class HourlyScheduler(BackgroundWorker):
    """Runs the previous hour shortly after each hour; catches up missed hours on start."""

    name = "hourly-scheduler"

    def __init__(self, engine: DetectionEngine, store: DetectionStore,
                 delay: timedelta = timedelta(minutes=5), clock: Clock = utcnow) -> None:
        super().__init__(clock)
        self.engine = engine
        self.store = store
        self.delay = delay   # gives late events a few minutes to arrive

    def next_fire(self, now: datetime) -> datetime:
        fire = floor_hour(now) + self.delay
        return fire if fire > now else fire + timedelta(hours=1)

    def seconds_until_next(self) -> float:
        now = self._clock()
        return (self.next_fire(now) - now).total_seconds()

    def tick(self) -> None:
        self.run_once()

    def on_start(self) -> None:
        self.backfill_missing()

    def run_once(self, now: datetime | None = None) -> list[RunStatus]:
        return self.engine.run_hour(HourWindow.previous(now or self._clock()))

    def backfill_missing(self, hours: int = 6, now: datetime | None = None) -> list[RunStatus]:
        """Re-run any of the last `hours` complete hours that has no successful run (safe: runs are idempotent)."""
        last = HourWindow.previous(now or self._clock())
        results: list[RunStatus] = []
        for back in range(hours - 1, -1, -1):
            window = HourWindow(last.start - timedelta(hours=back))
            missing = [s for s in self.engine.catalog.sources()
                       if not ((run := self.store.get_run(s, window.start)) and run.is_complete)]
            if missing:
                results.extend(self.engine.run_hour(window, missing))
        return results


class SLAWatchdog(BackgroundWorker):
    """Separate schedule that only reads the run table, so it still fires when the engine hangs."""

    name = "sla-watchdog"

    def __init__(self, store: DetectionStore, catalog: RuleCatalog, hub: NotificationHub, *,
                 sla: timedelta = timedelta(hours=1), warn_after: timedelta = timedelta(minutes=40),
                 interval: timedelta = timedelta(minutes=5), clock: Clock = utcnow) -> None:
        super().__init__(clock)
        self.store = store
        self.catalog = catalog
        self.hub = hub
        self.sla = sla
        self.warn_after = warn_after
        self.interval = interval
        self._notified: set[tuple[str, str, datetime]] = set()

    def seconds_until_next(self) -> float:
        return self.interval.total_seconds()

    def tick(self) -> None:
        self.check()

    def check(self, now: datetime | None = None) -> list[Notification]:
        now = now or self._clock()
        self._notified = {k for k in self._notified if k[2] > now - timedelta(days=1)}
        sent: list[Notification] = []

        # 1) Breach: the newest hour whose deadline (window.end + sla) has passed must be complete.
        window = HourWindow(floor_hour(now - self.sla) - timedelta(hours=1))
        for source in self.catalog.sources():
            run = self.store.get_run(source, window.start)
            if run is None or not run.is_complete:
                state = run.state.value if run else "NOT STARTED"
                sent += self._emit("sla.breach", Severity.CRITICAL, source, window.start,
                                   f"{source} detections for {window} not completed within {self.sla} (state={state})")

        # 2) Early warning: a run that has been going for too long.
        for run in self.store.list_runs(since=now - 2 * self.sla - timedelta(hours=1)):
            if run.state is RunState.RUNNING and now - run.started_at > self.warn_after:
                minutes = int((now - run.started_at).total_seconds() // 60)
                sent += self._emit("sla.warning", Severity.HIGH, run.source, run.run_hour,
                                   f"{run.source} run for {HourWindow(run.run_hour)} still RUNNING after {minutes} min")
        return sent

    def _emit(self, topic: str, severity: Severity, source: str, run_hour: datetime, message: str) -> list[Notification]:
        key = (topic, source, run_hour)
        if key in self._notified:   # alert once per problem, not every 5 minutes
            return []
        self._notified.add(key)
        notification = Notification(topic, severity, message, {"source": source, "run_hour": str(HourWindow(run_hour))})
        self.hub.publish(notification)
        return [notification]
