"""Evaluation metrics (pure Python) - use PR-based metrics for rare events, not accuracy."""
from __future__ import annotations

from typing import Sequence


def precision_recall_f1(y_true: Sequence[bool], y_pred: Sequence[bool]) -> tuple[float, float, float]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if p and not t)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1
