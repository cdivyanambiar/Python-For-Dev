"""Adapter: exposes an ML detector through the normal Rule interface,
so the engine runs it in the same single pass with no special handling."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from service.rules import GroupCountRule, RuleConfigError, RuleContext, parse_conditions, register, rule_header

from .detectors import RobustZScoreDetector
from .features import history_by_key


@register("ml_anomaly")
class MLAnomalyRule(GroupCountRule):
    """Alert when an entity's hourly count is far above its own historical baseline."""

    def __init__(self, lookback_hours: int = 168, z_threshold: float = 3.5, min_history: int = 24,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if lookback_hours < 1 or min_history < 1:
            raise RuleConfigError("lookback_hours and min_history must be >= 1")
        self.lookback_hours = lookback_hours
        self.z_threshold = z_threshold
        self.min_history = min_history
        self.detector = RobustZScoreDetector(z_threshold, min_history)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> MLAnomalyRule:
        try:
            lookback = int(cfg.get("lookback_hours", 168))
            z = float(cfg.get("z_threshold", 3.5))
            min_history = int(cfg.get("min_history", 24))
        except (TypeError, ValueError) as exc:
            raise RuleConfigError(f"invalid ml_anomaly parameter: {exc}") from exc
        return cls(lookback_hours=lookback, z_threshold=z, min_history=min_history,
                   group_by=cfg.get("group_by", ""),
                   conditions=parse_conditions(cfg.get("conditions"), required=False), **rule_header(cfg))

    def prepare(self, ctx: RuleContext) -> None:
        """'Train' on the lookback period right before this hour (no future data -> no leakage)."""
        start = ctx.window.start - timedelta(hours=self.lookback_hours)
        rows = ctx.history.hourly_counts(self.source, self.group_by, start, ctx.window.start)
        self.detector.fit(history_by_key(rows))

    def evaluate_group(self, key: str, count: int) -> dict[str, Any] | None:
        score = self.detector.score(key, count)
        if score <= self.z_threshold:
            return None
        baseline = self.detector.baseline_for(key)
        return {"score": round(score, 2),
                "baseline_median": baseline.median if baseline else None,
                "baseline": "entity" if key in self.detector.baselines else "population"}
