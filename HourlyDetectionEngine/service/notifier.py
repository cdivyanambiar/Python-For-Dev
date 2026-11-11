"""Notifications (Observer / pub-sub): publishers don't know who is listening."""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .models import Severity, utcnow
from .utils import retry

log = logging.getLogger(__name__)

Subscriber = Callable[["Notification"], None]


@dataclass(frozen=True, slots=True)
class Notification:
    topic: str            # run.succeeded | run.partial | run.failed | sla.breach | sla.warning | rule.disabled
    severity: Severity
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)


class NotificationHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, topic: str, subscriber: Subscriber) -> None:
        """Use topic '*' to receive everything."""
        with self._lock:
            self._subscribers[topic].append(subscriber)

    def publish(self, notification: Notification) -> None:
        with self._lock:
            targets = [*self._subscribers[notification.topic], *self._subscribers["*"]]
        for subscriber in targets:
            try:
                subscriber(notification)
            except Exception:  # a broken notifier must never break the detection run
                log.exception("subscriber %r failed for %s", subscriber, notification.topic)


class LogNotifier:
    _LEVELS = {Severity.LOW: logging.INFO, Severity.MEDIUM: logging.INFO,
               Severity.HIGH: logging.WARNING, Severity.CRITICAL: logging.ERROR}

    def __call__(self, n: Notification) -> None:
        log.log(self._LEVELS[n.severity], "[%s] %s", n.topic, n.message)


class MemoryNotifier:
    """Keeps the latest notifications (used by tests, the demo and GET /notifications)."""

    def __init__(self, maxlen: int = 500) -> None:
        self._items: deque[Notification] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def __call__(self, n: Notification) -> None:
        with self._lock:
            self._items.append(n)

    def recent(self, limit: int = 50, topic: str | None = None) -> list[Notification]:
        with self._lock:
            items = [n for n in self._items if topic is None or n.topic == topic]
        return items[-limit:][::-1]


class WebhookNotifier:
    """Slack / Teams / PagerDuty-style JSON webhook."""

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        if not url.startswith("https://"):
            raise ValueError("webhook URL must use https")
        self.url = url
        self.timeout = timeout

    @retry(attempts=3, base_delay=1.0, exceptions=(urllib.error.URLError, TimeoutError))
    def _post(self, body: bytes) -> None:
        request = urllib.request.Request(self.url, data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()

    def __call__(self, n: Notification) -> None:
        text = f"[{n.severity.value.upper()}] {n.topic}: {n.message}"
        self._post(json.dumps({"text": text}).encode("utf-8"))
