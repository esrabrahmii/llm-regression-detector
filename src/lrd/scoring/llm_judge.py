"""LLM-as-judge scorer — Gemini Flash reads (input, expected, output, rubric)
and returns a 0–1 score with reasoning.

Output schema is enforced via prompt + light parsing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from lrd.config import settings
from lrd.golden import GoldenCase
from lrd.scoring.base import ScoreResult

JUDGE_SYSTEM = """You are an impartial expert reviewing the OUTPUT of a system under test against a stated EXPECTATION and RUBRIC.

Reply ONLY with a single JSON object on one line, in this EXACT shape:
{"score": <float between 0 and 1>, "reasoning": "<1 short sentence>"}

No markdown, no code fences, no extra keys.
"""


@dataclass
class LLMJudgeScorer:
    rubric: str = ""
    threshold: float = 0.6
    name: str = "llm_judge"

    def score(self, case: GoldenCase, output: str) -> ScoreResult:
        if not settings.google_api_key:
            return ScoreResult("llm_judge", 0.0, False, "no GOOGLE_API_KEY")
        rubric = self.rubric.strip() or "Score 0-1: does the OUTPUT satisfy the EXPECTATION?"
        user = (
            f"INPUT:\n{case.input}\n\n"
            f"EXPECTATION:\n{case.expected}\n\n"
            f"RUBRIC:\n{rubric}\n\n"
            f"OUTPUT (the system under test produced this):\n{output}\n"
        )
        try:
            text = _judge(user)
            score, reasoning = _parse(text)
        except Exception as e:
            return ScoreResult("llm_judge", 0.0, False, f"judge error: {e}")
        return ScoreResult(
            method="llm_judge",
            score=score,
            passed=score >= self.threshold,
            detail=reasoning,
        )


def _judge(user_msg: str) -> str:
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=[JUDGE_SYSTEM, user_msg],
    )
    return (resp.text or "").strip()


def _parse(text: str) -> tuple[float, str]:
    # Strip code fences if the model added them despite instructions
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    # Tolerate trailing prose by extracting the first {…} block
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return 0.0, f"unparseable judge output: {text[:120]!r}"
    obj = json.loads(m.group(0))
    score = float(obj.get("score", 0.0))
    reasoning = str(obj.get("reasoning", "")).strip()
    score = max(0.0, min(1.0, score))
    return score, reasoning
