from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lrd.golden import GoldenCase


@dataclass
class ScoreResult:
    method: str       # "structural" | "semantic_sim" | "llm_judge"
    score: float      # in [0, 1]
    passed: bool      # score >= threshold
    detail: str = ""  # human-readable note (regex hits, similarity, judge reasoning)


class Scorer(Protocol):
    name: str

    def score(self, case: GoldenCase, output: str) -> ScoreResult: ...
