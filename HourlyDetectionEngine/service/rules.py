"""Detection rules.

Patterns used here:
- Strategy:         every rule type implements the same `Rule` interface.
- Registry/Factory: `@register("type")` + `create_rule(cfg)` -> new rule types need no engine change.
- Template Method:  `GroupCountRule` does the counting; subclasses only decide which groups alert.
- Decorator:        `GuardedRule` wraps any rule and isolates its exceptions (per-run circuit breaker).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, ClassVar, Iterable, Protocol

from .models import FIELD_NAME_RE, Event, Finding, HourWindow, Severity


class RuleConfigError(ValueError):
    """Invalid rule definition. Caught at load time and recorded as a COMPILE error."""


class HistoryProvider(Protocol):
    def hourly_counts(
        self, source: str, field: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, str, int]]: ...


@dataclass(frozen=True, slots=True)
class RuleContext:
    window: HourWindow
    history: HistoryProvider


# Dispatch table instead of a long if/elif chain.
OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda actual, expected: actual == expected,
    "ne": lambda actual, expected: actual != expected,
    "gt": lambda actual, expected: actual is not None and actual > expected,
    "gte": lambda actual, expected: actual is not None and actual >= expected,
    "lt": lambda actual, expected: actual is not None and actual < expected,
    "lte": lambda actual, expected: actual is not None and actual <= expected,
    "in": lambda actual, expected: actual in expected,
    "equals_ci": lambda actual, expected: actual is not None and str(actual).lower() == str(expected).lower(),
    "contains_ci": lambda actual, expected: actual is not None and str(expected).lower() in str(actual).lower(),
    "startswith_ci": lambda actual, expected: actual is not None and str(actual).lower().startswith(str(expected).lower()),
}


@dataclass(slots=True)
class Condition:
    field: str
    op: str
    value: Any
    _fn: Callable[[Any, Any], bool] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not FIELD_NAME_RE.match(self.field):
            raise RuleConfigError(f"invalid field name {self.field!r}")
        if self.op == "regex":
            try:
                pattern = re.compile(str(self.value))
            except re.error as exc:
                raise RuleConfigError(f"bad regex {self.value!r}: {exc}") from exc
            self._fn = lambda actual, _expected: actual is not None and pattern.search(str(actual)) is not None
        elif self.op in OPERATORS:
            if self.op == "in" and not isinstance(self.value, (list, tuple, set)):
                raise RuleConfigError("operator 'in' needs a list value")
            self._fn = OPERATORS[self.op]
        else:
            raise RuleConfigError(f"unknown operator {self.op!r}; known: {sorted([*OPERATORS, 'regex'])}")

    def test(self, event: Event) -> bool:
        return self._fn(event.get(self.field), self.value)


def parse_conditions(raw: Any, *, required: bool = True) -> list[Condition]:
    raw = [] if raw is None else raw
    if not isinstance(raw, list):
        raise RuleConfigError("'conditions' must be a list")
    if required and not raw:
        raise RuleConfigError("at least one condition is required")
    conditions = []
    for item in raw:
        if not isinstance(item, dict):
            raise RuleConfigError("each condition must be an object")
        try:
            conditions.append(Condition(field=item["field"], op=item["op"], value=item.get("value")))
        except KeyError as exc:
            raise RuleConfigError(f"condition missing key {exc}") from exc
    return conditions


def rule_header(cfg: dict[str, Any]) -> dict[str, Any]:
    """Common keys every rule type has."""
    try:
        return {
            "rule_id": str(cfg["rule_id"]),
            "source": str(cfg["source"]),
            "severity": Severity(str(cfg.get("severity", "medium")).lower()),
            "description": str(cfg.get("description", "")),
        }
    except KeyError as exc:
        raise RuleConfigError(f"missing required key {exc}") from exc
    except ValueError as exc:
        raise RuleConfigError(str(exc)) from exc


# ---------------------------------------------------------------- base + registry

class Rule(ABC):
    kind: ClassVar[str] = "abstract"

    def __init__(self, rule_id: str, source: str, severity: Severity, description: str = "") -> None:
        self.rule_id = rule_id
        self.source = source
        self.severity = severity
        self.description = description

    @classmethod
    @abstractmethod
    def from_config(cls, cfg: dict[str, Any]) -> Rule: ...

    def start(self, ctx: RuleContext) -> None:
        """Called once per run, before the scan. Reset state here."""

    @abstractmethod
    def observe(self, event: Event) -> Finding | None:
        """Called once per event during the single pass."""

    def finish(self) -> Iterable[Finding]:
        """Called after the scan. Aggregate rules emit their findings here."""
        return ()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.rule_id!r}, source={self.source!r})"


RULE_TYPES: dict[str, type[Rule]] = {}


def register(kind: str) -> Callable[[type[Rule]], type[Rule]]:
    def decorator(cls: type[Rule]) -> type[Rule]:
        if kind in RULE_TYPES and RULE_TYPES[kind] is not cls:
            raise ValueError(f"rule type {kind!r} already registered")
        cls.kind = kind
        RULE_TYPES[kind] = cls
        return cls

    return decorator


def create_rule(cfg: dict[str, Any]) -> Rule:
    """Factory: config dict -> rule object."""
    if not isinstance(cfg, dict):
        raise RuleConfigError("rule config must be an object")
    kind = cfg.get("type", "pattern")
    try:
        cls = RULE_TYPES[kind]
    except KeyError:
        raise RuleConfigError(f"unknown rule type {kind!r}; known: {sorted(RULE_TYPES)}") from None
    return cls.from_config(cfg)


# ---------------------------------------------------------------- concrete rules

@register("pattern")
class PatternRule(Rule):
    """Row rule: alert on every event that matches all/any conditions."""

    def __init__(self, conditions: list[Condition], match: str = "all", **header: Any) -> None:
        super().__init__(**header)
        if match not in ("all", "any"):
            raise RuleConfigError("match must be 'all' or 'any'")
        self.conditions = conditions
        self._combine = all if match == "all" else any

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> PatternRule:
        return cls(parse_conditions(cfg.get("conditions")), cfg.get("match", "all"), **rule_header(cfg))

    def observe(self, event: Event) -> Finding | None:
        if self._combine(c.test(event) for c in self.conditions):
            return Finding(event.event_id, event.event_time,
                           {c.field: event.get(c.field) for c in self.conditions})
        return None


class GroupCountRule(Rule):
    """Template Method: count matching events per group during the scan;
    subclasses implement `evaluate_group` (and optionally `prepare`)."""

    def __init__(self, group_by: str, conditions: Iterable[Condition] = (), **header: Any) -> None:
        super().__init__(**header)
        if not isinstance(group_by, str) or not FIELD_NAME_RE.match(group_by):
            raise RuleConfigError(f"invalid group_by {group_by!r}")
        self.group_by = group_by
        self.conditions = list(conditions)
        self._counts: Counter[str] = Counter()
        self._first_seen: dict[str, datetime] = {}
        self._window: HourWindow | None = None

    def start(self, ctx: RuleContext) -> None:
        self._counts = Counter()
        self._first_seen = {}
        self._window = ctx.window
        self.prepare(ctx)

    def prepare(self, ctx: RuleContext) -> None:
        """Hook for subclasses (e.g. load a baseline)."""

    def observe(self, event: Event) -> Finding | None:
        if all(c.test(event) for c in self.conditions):
            key = event.get(self.group_by)
            if key is not None:
                key = str(key)
                self._counts[key] += 1
                self._first_seen.setdefault(key, event.event_time)
        return None

    def finish(self) -> Iterable[Finding]:
        for key, count in self._counts.items():
            details = self.evaluate_group(key, count)
            if details is not None:
                yield Finding(
                    event_id=f"{self.rule_id}:{key}:{self._window}",
                    event_time=self._first_seen[key],
                    details={self.group_by: key, "count": count, **details},
                )

    @abstractmethod
    def evaluate_group(self, key: str, count: int) -> dict[str, Any] | None:
        """Return alert details if this group should alert, else None."""


@register("threshold")
class ThresholdRule(GroupCountRule):
    """e.g. >= 10 failed logins per user per hour."""

    def __init__(self, threshold: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if threshold < 1:
            raise RuleConfigError("threshold must be >= 1")
        self.threshold = threshold

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> ThresholdRule:
        try:
            threshold = int(cfg["threshold"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuleConfigError("threshold rule needs an integer 'threshold'") from exc
        return cls(threshold=threshold, group_by=cfg.get("group_by", ""),
                   conditions=parse_conditions(cfg.get("conditions"), required=False), **rule_header(cfg))

    def evaluate_group(self, key: str, count: int) -> dict[str, Any] | None:
        return {"threshold": self.threshold} if count >= self.threshold else None


# ---------------------------------------------------------------- error isolation

class GuardedRule:
    """Decorator around a Rule: exceptions are counted, never raised.
    After `max_errors` the rule is 'tripped' and skipped for the rest of the run."""

    def __init__(self, rule: Rule, max_errors: int = 3) -> None:
        self.rule = rule
        self.max_errors = max_errors
        self.errors = 0
        self.last_error: str | None = None

    def __getattr__(self, name: str) -> Any:
        if name == "rule":
            raise AttributeError(name)
        return getattr(self.rule, name)

    @property
    def tripped(self) -> bool:
        return self.errors >= self.max_errors

    def _call(self, fn: Callable[..., Any], *args: Any, default: Any, fatal: bool = False) -> Any:
        if self.tripped:
            return default
        try:
            return fn(*args)
        except Exception as exc:  # isolation boundary: one rule must not fail the run
            self.errors = self.max_errors if fatal else self.errors + 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return default

    def start(self, ctx: RuleContext) -> None:
        self._call(self.rule.start, ctx, default=None, fatal=True)

    def observe(self, event: Event) -> Finding | None:
        return self._call(self.rule.observe, event, default=None)

    def finish(self) -> list[Finding]:
        return self._call(lambda: list(self.rule.finish()), default=[], fatal=True)
