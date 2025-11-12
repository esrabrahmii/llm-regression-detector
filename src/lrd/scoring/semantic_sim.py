"""Semantic-similarity scorer — embed `expected` and `output`, compute cosine.

Uses Gemini's text-embedding-004 — free, fast, no local PyTorch dep.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from lrd.config import settings
from lrd.golden import GoldenCase
from lrd.scoring.base import ScoreResult


@dataclass
class SemanticSimScorer:
    threshold: float = 0.45
    name: str = "semantic_sim"

    def score(self, case: GoldenCase, output: str) -> ScoreResult:
        if not case.expected.strip():
            return ScoreResult("semantic_sim", 0.0, False, "no expected text → cannot score")
        if not settings.google_api_key:
            return ScoreResult("semantic_sim", 0.0, False, "no GOOGLE_API_KEY")
        a = _embed(case.expected)
        b = _embed(output)
        sim = _cosine(a, b)
        # cosine ∈ [-1, 1] — rescale to [0, 1] so it composes with other scorers
        score = max(0.0, sim)
        return ScoreResult(
            method="semantic_sim",
            score=float(score),
            passed=score >= self.threshold,
            detail=f"cosine={sim:.3f} (threshold {self.threshold})",
        )


def _embed(text: str) -> list[float]:
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    resp = client.models.embed_content(
        model=settings.gemini_embed_model,
        contents=text[:8000],  # API limit guard
    )
    # google-genai returns ContentEmbedding objects on .embeddings
    emb = resp.embeddings[0]
    return list(emb.values)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
