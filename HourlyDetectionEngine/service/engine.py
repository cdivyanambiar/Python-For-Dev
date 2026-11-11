"""Detection engine: one pass over the hour per source, all rules evaluated per event,
alerts written in batches, failures isolated per rule."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from .catalog import RuleCatalog
from .models import (Alert, DeadLetter, ErrorType, Finding, HourWindow, RunState, RunStatus,
                     Severity, utcnow)
from .notifier import Notification, NotificationHub
from .repository import TRANSIENT_ERRORS, DetectionStore
from .rules import GuardedRule, Rule, RuleContext
from .utils import retry, timed

log = logging.getLogger(__name__)

_RUN_SEVERITY = {RunState.SUCCEEDED: Severity.LOW, RunState.PARTIAL: Severity.MEDIUM,
                 RunState.FAILED: Severity.CRITICAL}


class AlertWriter:
    """Buffers alerts and writes them in batches. Context manager flushes on clean exit."""

    def __init__(self, store: DetectionStore, batch_size: int = 5_000) -> None:
        self._store = store
        self._batch_size = batch_size
        self._buffer: list[Alert] = []
        self.written = 0

    def add(self, alert: Alert) -> None:
        self._buffer.append(alert)
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        if self._buffer:
            self.written += self._write(self._buffer)
            self._buffer = []

    @retry(attempts=3, base_delay=0.2, exceptions=TRANSIENT_ERRORS)
    def _write(self, alerts: list[Alert]) -> int:
        return self._store.add_alerts(alerts)

    def __enter__(self) -> AlertWriter:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.flush()
        return False


class DetectionEngine:
    def __init__(self, store: DetectionStore, catalog: RuleCatalog, hub: NotificationHub, *,
                 batch_size: int = 5_000, max_rule_errors: int = 3, disable_after: int = 3,
                 max_workers: int = 4) -> None:
        self.store = store
        self.catalog = catalog
        self.hub = hub
        self.batch_size = batch_size
        self.max_rule_errors = max_rule_errors
        self.disable_after = disable_after
        self.max_workers = max_workers

    def run_hour(self, window: HourWindow, sources: Iterable[str] | None = None) -> list[RunStatus]:
        """Run every source in parallel; a crash in one source never stops the others."""
        sources = list(sources) if sources else self.catalog.sources()
        results: list[RunStatus] = []
        if not sources:
            return results
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(sources)),
                                thread_name_prefix="detect") as pool:
            futures = {pool.submit(self.run_source, source, window): source for source in sources}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    log.exception("run for %s %s crashed", source, window)
                    results.append(self._mark_crashed(source, window, exc))
        return sorted(results, key=lambda s: s.source)

    def run_source(self, source: str, window: HourWindow) -> RunStatus:
        status = RunStatus(run_hour=window.start, source=source)
        self.store.save_run(status)

        rules, compile_errors = self.catalog.build(source)
        dead = [DeadLetter(window.start, source, rid, ErrorType.COMPILE, msg) for rid, msg in compile_errors]
        guarded = [GuardedRule(rule, self.max_rule_errors) for rule in rules]
        ctx = RuleContext(window=window, history=self.store)
        for g in guarded:
            g.start(ctx)

        self.store.delete_alerts(source, window.start)   # re-running an hour replaces its alerts
        with timed(f"detect {source} {window}"), AlertWriter(self.store, self.batch_size) as writer:
            for event in self.store.iter_events(source, window, self.batch_size):
                status.events_scanned += 1
                for g in guarded:
                    finding = g.observe(event)
                    if finding is not None:
                        writer.add(self._to_alert(g.rule, finding, window))
            for g in guarded:
                for finding in g.finish():
                    writer.add(self._to_alert(g.rule, finding, window))

        for g in guarded:
            if g.errors:
                note = " - stopped for this run" if g.tripped else " - events skipped"
                dead.append(DeadLetter(window.start, source, g.rule.rule_id, ErrorType.RUNTIME,
                                       f"{g.errors} error(s){note}; last: {g.last_error}"))
        if dead:
            self.store.add_dead_letters(dead)

        failed = {rid for rid, _ in compile_errors} | {g.rule.rule_id for g in guarded if g.tripped}
        all_rules = {rid for rid, _ in compile_errors} | {g.rule.rule_id for g in guarded}
        self._update_rule_health(source, all_rules, failed)

        status.alerts_written = writer.written
        status.rules_total = len(all_rules)
        status.rules_failed = len(failed)
        status.state = (RunState.SUCCEEDED if not failed
                        else RunState.FAILED if failed == all_rules else RunState.PARTIAL)
        status.finished_at = utcnow()
        self.store.save_run(status)
        self.hub.publish(Notification(
            topic=f"run.{status.state.value.lower()}", severity=_RUN_SEVERITY[status.state],
            message=(f"{source} {window}: {status.state.value}, {status.events_scanned} events, "
                     f"{status.alerts_written} alerts, {status.rules_failed}/{status.rules_total} rules failed"),
            data={"source": source, "run_hour": str(window)}))
        return status

    def _update_rule_health(self, source: str, rule_ids: set[str], failed: set[str]) -> None:
        for rule_id in sorted(rule_ids):
            if self.store.record_rule_outcome(rule_id, rule_id in failed, self.disable_after):
                self.hub.publish(Notification(
                    "rule.disabled", Severity.HIGH,
                    f"rule {rule_id} ({source}) disabled after {self.disable_after} consecutive failed runs",
                    {"rule_id": rule_id, "source": source}))

    def _mark_crashed(self, source: str, window: HourWindow, exc: Exception) -> RunStatus:
        status = RunStatus(window.start, source, RunState.FAILED, finished_at=utcnow(),
                           message=f"{type(exc).__name__}: {exc}")
        try:
            self.store.save_run(status)
            self.store.add_dead_letters([DeadLetter(window.start, source, "*", ErrorType.INFRA, status.message)])
        except Exception:
            log.exception("could not record crash for %s (store unavailable?)", source)
        self.hub.publish(Notification("run.failed", Severity.CRITICAL,
                                      f"{source} {window}: crashed - {status.message}",
                                      {"source": source, "run_hour": str(window)}))
        return status

    @staticmethod
    def _to_alert(rule: Rule, finding: Finding, window: HourWindow) -> Alert:
        return Alert(run_hour=window.start, source=rule.source, rule_id=rule.rule_id,
                     severity=rule.severity, event_id=finding.event_id,
                     event_time=finding.event_time, details=finding.details)
