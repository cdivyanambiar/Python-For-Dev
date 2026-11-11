"""Rule catalog: rule *configs* are data (JSON reviewed in Git); rule *objects* are rebuilt for every run
because aggregate rules keep state during a scan."""
from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any, Iterable, Protocol

from .rules import Rule, RuleConfigError, create_rule


class RuleHealth(Protocol):
    def disabled_rules(self) -> set[str]: ...


class RuleCatalog:
    def __init__(self, configs: Iterable[dict[str, Any]], health: RuleHealth | None = None) -> None:
        self._configs = [dict(c) for c in configs]
        self._health = health
        self._lock = threading.RLock()

    @classmethod
    def from_file(cls, path: str | Path, health: RuleHealth | None = None) -> RuleCatalog:
        configs = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(configs, list):
            raise RuleConfigError("rules file must contain a JSON list")
        return cls(configs, health)

    def configs(self, source: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(c) for c in self._configs if source is None or c.get("source") == source]

    def sources(self) -> list[str]:
        with self._lock:
            return sorted({str(c["source"]) for c in self._configs if c.get("source") and c.get("enabled", True)})

    def build(self, source: str) -> tuple[list[Rule], list[tuple[str, str]]]:
        """Return (valid rules, [(rule_id, error)]). A bad config never raises here."""
        disabled = self._health.disabled_rules() if self._health else set()
        rules: list[Rule] = []
        errors: list[tuple[str, str]] = []
        for cfg in self.configs(source):
            rule_id = str(cfg.get("rule_id", "<missing id>"))
            if not cfg.get("enabled", True) or rule_id in disabled:
                continue
            try:
                rules.append(create_rule(cfg))
            except Exception as exc:  # any bad config becomes a COMPILE error for this rule only
                errors.append((rule_id, f"{type(exc).__name__}: {exc}"))
        return rules, errors

    def upsert(self, cfg: dict[str, Any]) -> Rule:
        """Validate first (fail fast), then add/replace. In-memory only: production rules come via Git + CI."""
        rule = create_rule(cfg)
        with self._lock:
            self._configs = [c for c in self._configs if c.get("rule_id") != rule.rule_id] + [dict(cfg)]
        return rule
