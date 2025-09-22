"""Scorers turn (case, output) → ScoreResult."""
from __future__ import annotations

from lrd.golden import ScorerSpec
from lrd.scoring.base import Scorer, ScoreResult
from lrd.scoring.llm_judge import LLMJudgeScorer
from lrd.scoring.semantic_sim import SemanticSimScorer
from lrd.scoring.structural import StructuralScorer


def make_scorer(spec: ScorerSpec) -> Scorer:
    """Factory: build a Scorer instance from a YAML spec."""
    if spec.method == "structural":
        return StructuralScorer(rules=spec.params.get("rules", []),
                                threshold=spec.params.get("threshold", 0.999))
    if spec.method == "semantic_sim":
        return SemanticSimScorer(threshold=spec.params.get("threshold", 0.45))
    if spec.method == "llm_judge":
        return LLMJudgeScorer(rubric=spec.params.get("rubric", ""),
                              threshold=spec.params.get("threshold", 0.6))
    raise ValueError(f"unknown scorer method: {spec.method}")


__all__ = ["ScoreResult", "Scorer", "make_scorer", "StructuralScorer",
           "SemanticSimScorer", "LLMJudgeScorer"]
