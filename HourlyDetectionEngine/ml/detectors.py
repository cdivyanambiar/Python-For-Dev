"""Anomaly detectors.

RobustZScoreDetector  - per-entity baseline with median/MAD (pure Python, explainable, default).
IsolationForestDetector - multivariate option (needs scikit-learn).
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol, Sequence


class AnomalyDetector(Protocol):
    def fit(self, history: Mapping[str, Sequence[float]]) -> AnomalyDetector: ...
    def score(self, key: str, value: float) -> float: ...
    def is_anomaly(self, key: str, value: float) -> bool: ...


@dataclass(frozen=True, slots=True)
class Baseline:
    median: float
    mad: float
    n: int


class RobustZScoreDetector:
    """score = 0.6745 * (x - median) / MAD.

    Median/MAD are not pulled up by the outliers we are trying to find (mean/std are).
    Keys with too little history fall back to the population baseline."""

    def __init__(self, threshold: float = 3.5, min_history: int = 24, min_mad: float = 1.0) -> None:
        self.threshold = threshold
        self.min_history = min_history
        self.min_mad = min_mad
        self.baselines: dict[str, Baseline] = {}
        self.global_baseline: Baseline | None = None

    def fit(self, history: Mapping[str, Sequence[float]]) -> RobustZScoreDetector:
        all_values: list[float] = []
        self.baselines = {}
        for key, values in history.items():
            values = list(values)
            all_values.extend(values)
            if len(values) >= self.min_history:
                self.baselines[key] = self._baseline(values)
        self.global_baseline = self._baseline(all_values) if all_values else None
        return self

    def _baseline(self, values: Sequence[float]) -> Baseline:
        median = statistics.median(values)
        mad = statistics.median(abs(v - median) for v in values)
        return Baseline(median, max(mad, self.min_mad), len(values))

    def baseline_for(self, key: str) -> Baseline | None:
        return self.baselines.get(key) or self.global_baseline

    def score(self, key: str, value: float) -> float:
        baseline = self.baseline_for(key)
        if baseline is None:
            return 0.0
        return 0.6745 * (value - baseline.median) / baseline.mad

    def is_anomaly(self, key: str, value: float) -> bool:
        return self.score(key, value) > self.threshold   # only unusually *high* activity

    # JSON-safe persistence (never unpickle model files from untrusted storage)
    def to_dict(self) -> dict[str, Any]:
        return {"threshold": self.threshold, "min_history": self.min_history, "min_mad": self.min_mad,
                "baselines": {k: asdict(b) for k, b in self.baselines.items()},
                "global": asdict(self.global_baseline) if self.global_baseline else None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RobustZScoreDetector:
        detector = cls(data["threshold"], data["min_history"], data["min_mad"])
        detector.baselines = {k: Baseline(**v) for k, v in data["baselines"].items()}
        detector.global_baseline = Baseline(**data["global"]) if data.get("global") else None
        return detector


class IsolationForestDetector:
    """Use when one count is not enough, e.g. features per user-hour:
    [logins, failed_logins, distinct_ips, distinct_countries]."""

    def __init__(self, contamination: float = 0.01, random_state: int = 42) -> None:
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError as exc:
            raise RuntimeError("IsolationForestDetector needs scikit-learn: pip install scikit-learn") from exc
        self.model = IsolationForest(contamination=contamination, random_state=random_state)

    def fit(self, rows: Sequence[Sequence[float]]) -> IsolationForestDetector:
        self.model.fit(rows)
        return self

    def predict(self, rows: Sequence[Sequence[float]]) -> list[bool]:
        return [label == -1 for label in self.model.predict(rows)]
