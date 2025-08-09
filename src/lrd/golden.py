"""Golden dataset — YAML schema + loader.

A golden file is a list of test cases. Each case has:
  id          — unique
  input       — what we feed the LLM under test
  expected    — what we expect the output to look/say (used for semantic + judge)
  tags        — optional list of strings (filter / group)
  scoring     — list of scoring methods to apply (defaults: structural+semantic+judge)

Example:
  - id: simple_lora_q
    input: "Does LoRA rank affect GSM8K accuracy on Pythia-160M?"
    expected: "A plan with hypothesis, method, metrics and a time estimate."
    tags: [llm-finetune]
    scoring:
      - method: structural
        rules:
          - regex: '\\*\\*Hypothesis\\*\\*'
          - regex: '\\*\\*Method\\*\\*'
          - regex: '\\*\\*Estimated time\\*\\*'
      - method: semantic_sim
        threshold: 0.45
      - method: llm_judge
        rubric: "Score 0-1: is this a concrete, runnable ML experimental plan?"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ScorerSpec:
    method: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoldenCase:
    id: str
    input: str
    expected: str
    tags: list[str] = field(default_factory=list)
    scoring: list[ScorerSpec] = field(default_factory=list)


@dataclass
class GoldenSet:
    path: Path
    cases: list[GoldenCase]

    def __len__(self) -> int:
        return len(self.cases)


def load(path: str | Path) -> GoldenSet:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Golden file not found: {p}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    if not isinstance(raw, list):
        raise ValueError(f"Golden file must be a list, got {type(raw).__name__}")

    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"case {i} must be a mapping")
        case_id = item.get("id")
        if not case_id:
            raise ValueError(f"case {i} missing required field: id")
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        scoring_raw = item.get("scoring") or []
        scoring = [
            ScorerSpec(method=s["method"], params={k: v for k, v in s.items() if k != "method"})
            for s in scoring_raw
        ]
        cases.append(
            GoldenCase(
                id=str(case_id),
                input=str(item.get("input", "")),
                expected=str(item.get("expected", "")),
                tags=list(item.get("tags") or []),
                scoring=scoring,
            )
        )
    return GoldenSet(path=p, cases=cases)
