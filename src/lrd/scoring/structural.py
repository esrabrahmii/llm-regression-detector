"""Structural scorer — regex / contains / length-based rules.

YAML config:
  - method: structural
    threshold: 1.0     # require all rules to pass (1.0) or fewer
    rules:
      - regex: '\\*\\*Hypothesis\\*\\*'
      - contains: 'gsm8k'
      - min_length: 200
      - max_length: 4000
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lrd.golden import GoldenCase
from lrd.scoring.base import ScoreResult


@dataclass
class StructuralScorer:
    rules: list[dict[str, Any]]
    threshold: float = 0.999
    name: str = "structural"

    def score(self, case: GoldenCase, output: str) -> ScoreResult:
        if not self.rules:
            return ScoreResult("structural", 1.0, True, "no rules → pass")
        passed_count = 0
        details: list[str] = []
        for rule in self.rules:
            ok, msg = self._check_rule(rule, output)
            if ok:
                passed_count += 1
            details.append(("✓ " if ok else "✗ ") + msg)
        score = passed_count / len(self.rules)
        return ScoreResult(
            method="structural",
            score=score,
            passed=score >= self.threshold,
            detail=" · ".join(details),
        )

    def _check_rule(self, rule: dict[str, Any], output: str) -> tuple[bool, str]:
        if "regex" in rule:
            pat = rule["regex"]
            ok = re.search(pat, output) is not None
            return ok, f"regex `{pat}`"
        if "contains" in rule:
            needle = rule["contains"]
            ok = needle.lower() in output.lower()
            return ok, f"contains `{needle}`"
        if "min_length" in rule:
            n = int(rule["min_length"])
            return len(output) >= n, f"min_length {n} (got {len(output)})"
        if "max_length" in rule:
            n = int(rule["max_length"])
            return len(output) <= n, f"max_length {n} (got {len(output)})"
        return False, f"unknown rule: {rule}"
