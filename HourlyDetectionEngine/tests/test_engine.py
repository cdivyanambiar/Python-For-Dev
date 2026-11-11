from datetime import timedelta

import pytest

import ml.ml_rule  # noqa: F401  registers "ml_anomaly"
from ml.detectors import RobustZScoreDetector
from ml.metrics import precision_recall_f1
from service.catalog import RuleCatalog
from service.engine import DetectionEngine
from service.models import Event, HourWindow, RunState, utcnow
from service.notifier import MemoryNotifier, NotificationHub
from service.repository import SQLiteStore
from service.rules import RuleConfigError, create_rule
from service.scheduler import SLAWatchdog
from service.utils import batched, retry

WINDOW = HourWindow.previous(utcnow())

RULES = [
    {"rule_id": "ENC", "source": "edr", "severity": "high", "conditions": [
        {"field": "process_name", "op": "equals_ci", "value": "powershell.exe"},
        {"field": "process_args", "op": "contains_ci", "value": "-enc"}]},
    {"rule_id": "BROKEN", "source": "edr", "conditions": [{"field": "process_args", "op": "gt", "value": 1}]},
    {"rule_id": "BRUTE", "source": "auth", "type": "threshold", "group_by": "username", "threshold": 3,
     "conditions": [{"field": "outcome", "op": "eq", "value": "FAILURE"}]},
]


def ev(source: str, i: int, **attrs) -> Event:
    return Event(f"{source}-{i}", source, WINDOW.start + timedelta(seconds=i), attrs)


@pytest.fixture
def env(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    hub, inbox = NotificationHub(), MemoryNotifier()
    hub.subscribe("*", inbox)
    catalog = RuleCatalog(RULES, health=store)
    engine = DetectionEngine(store, catalog, hub, max_rule_errors=1, max_workers=2)
    store.add_events([
        ev("edr", 1, process_name="PowerShell.exe", process_args="-EncodedCommand abc"),
        ev("edr", 2, process_name="bash", process_args="-c ls"),
        *[ev("auth", i, username="eve", outcome="FAILURE") for i in range(3)],
        ev("auth", 10, username="ann", outcome="SUCCESS"),
    ])
    return store, catalog, engine, hub, inbox


def test_bad_rule_is_isolated(env):
    store, _, engine, _, _ = env
    statuses = {s.source: s for s in engine.run_hour(WINDOW)}
    assert statuses["edr"].state is RunState.PARTIAL
    assert [a.rule_id for a in store.list_alerts(source="edr")] == ["ENC"]
    assert [d.rule_id for d in store.list_dead_letters()] == ["BROKEN"]


def test_threshold_rule(env):
    store, _, engine, _, _ = env
    engine.run_hour(WINDOW, ["auth"])
    (alert,) = store.list_alerts(source="auth")
    assert alert.details == {"username": "eve", "count": 3, "threshold": 3}


def test_rerun_is_idempotent(env):
    store, _, engine, _, _ = env
    engine.run_hour(WINDOW)
    first = len(store.list_alerts())
    engine.run_hour(WINDOW)
    assert len(store.list_alerts()) == first


def test_rule_disabled_after_three_failed_runs(env):
    store, _, engine, _, inbox = env
    for _ in range(3):
        engine.run_hour(WINDOW, ["edr"])
    assert store.disabled_rules() == {"BROKEN"}
    assert inbox.recent(topic="rule.disabled")


@pytest.mark.parametrize("cfg", [
    {"rule_id": "X", "source": "edr", "conditions": [{"field": "a", "op": "regex", "value": "("}]},
    {"rule_id": "X", "source": "edr", "conditions": [{"field": "a", "op": "nope", "value": 1}]},
    {"rule_id": "X", "source": "edr", "type": "unknown"},
    {"rule_id": "X", "source": "edr", "type": "threshold", "group_by": "user"},
    {"source": "edr", "conditions": [{"field": "a", "op": "eq", "value": 1}]},
])
def test_invalid_config_rejected(cfg):
    with pytest.raises(RuleConfigError):
        create_rule(cfg)


def test_sla_watchdog(env):
    store, catalog, engine, hub, _ = env
    now = WINDOW.end + timedelta(hours=1, minutes=1)   # deadline for WINDOW has passed
    breaches = SLAWatchdog(store, catalog, hub).check(now=now)
    assert {n.data["source"] for n in breaches} == {"auth", "edr"}

    engine.run_hour(WINDOW)
    assert SLAWatchdog(store, catalog, hub).check(now=now) == []


def test_robust_zscore():
    detector = RobustZScoreDetector(threshold=3.5, min_history=10).fit({"a": [3, 4, 5, 4, 6] * 10})
    assert detector.is_anomaly("a", 40)
    assert not detector.is_anomaly("a", 5)
    assert RobustZScoreDetector.from_dict(detector.to_dict()).score("a", 40) == detector.score("a", 40)


def test_helpers():
    assert list(batched(range(5), 2)) == [[0, 1], [2, 3], [4]]
    calls = []

    @retry(attempts=3, base_delay=0)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError
        return "ok"

    assert flaky() == "ok" and len(calls) == 3
    assert precision_recall_f1([True, False, True], [True, True, False]) == (0.5, 0.5, 0.5)
