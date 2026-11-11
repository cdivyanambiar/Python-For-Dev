"""Composition root (Dependency Injection): the only place that wires concrete classes together."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .catalog import RuleCatalog
from .engine import DetectionEngine
from .notifier import LogNotifier, MemoryNotifier, NotificationHub, WebhookNotifier
from .repository import SQLiteStore
from .scheduler import HourlyScheduler, SLAWatchdog

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "config" / "rules.json"
_PAGE_TOPICS = ("run.partial", "run.failed", "sla.breach", "sla.warning", "rule.disabled")


@dataclass
class Container:
    store: SQLiteStore
    catalog: RuleCatalog
    hub: NotificationHub
    inbox: MemoryNotifier
    engine: DetectionEngine
    scheduler: HourlyScheduler
    watchdog: SLAWatchdog


def build_container(db_path: str | Path = "detections.db", rules_path: str | Path | None = None,
                    webhook_url: str | None = None) -> Container:
    import ml.ml_rule  # noqa: F401  plugin import: registers the "ml_anomaly" rule type

    store = SQLiteStore(db_path)
    catalog = RuleCatalog.from_file(rules_path or DEFAULT_RULES, health=store)

    hub = NotificationHub()
    inbox = MemoryNotifier()
    hub.subscribe("*", LogNotifier())
    hub.subscribe("*", inbox)
    if webhook_url:
        webhook = WebhookNotifier(webhook_url)
        for topic in _PAGE_TOPICS:
            hub.subscribe(topic, webhook)

    engine = DetectionEngine(store, catalog, hub)
    return Container(store=store, catalog=catalog, hub=hub, inbox=inbox, engine=engine,
                     scheduler=HourlyScheduler(engine, store),
                     watchdog=SLAWatchdog(store, catalog, hub))
