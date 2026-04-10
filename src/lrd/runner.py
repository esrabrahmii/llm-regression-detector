"""Runner — orchestrates: load goldens → call SUT → score → persist.

Returns a RunSummary the CLI / dashboard / alerter can read.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from lrd.golden import GoldenSet, ScorerSpec
from lrd.golden import load as load_goldens
from lrd.scoring import make_scorer
from lrd.scoring.base import Scorer, ScoreResult
from lrd.store.duckdb_store import Store
from lrd.sut.base import SUT

# ─── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_SCORING: list[ScorerSpec] = [
    ScorerSpec(method="structural", params={
        "rules": [
            {"min_length": 200},
            {"max_length": 4000},
        ],
        "threshold": 0.999,
    }),
    ScorerSpec(method="semantic_sim", params={"threshold": 0.40}),
    ScorerSpec(method="llm_judge", params={
        "rubric": "Score 0-1: does the output meet the stated expectation?",
        "threshold": 0.6,
    }),
]


@dataclass
class CaseSummary:
    case_id: str
    output: str
    error: str | None
    duration_ms: int
    scores: list[ScoreResult]

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.scores)

    @property
    def avg_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)


@dataclass
class RunSummary:
    run_id: str
    sut_name: str
    golden_path: str
    cases: list[CaseSummary]

    @property
    def n_cases(self) -> int:
        return len(self.cases)

    @property
    def n_passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 0.0
        return self.n_passed / self.n_cases

    @property
    def avg_score(self) -> float:
        if not self.cases:
            return 0.0
        return sum(c.avg_score for c in self.cases) / len(self.cases)


# ─── The runner ──────────────────────────────────────────────────────────────

def run(
    goldens: GoldenSet | str | Path,
    sut: SUT,
    store: Store,
    *,
    progress_cb=None,
) -> RunSummary:
    if not isinstance(goldens, GoldenSet):
        goldens = load_goldens(goldens)

    run_id = store.start_run(sut.name, str(goldens.path))
    summaries: list[CaseSummary] = []

    for i, case in enumerate(goldens.cases):
        if progress_cb:
            progress_cb(i, len(goldens.cases), case.id)

        # 1) Call the SUT
        t0 = time.perf_counter()
        output = ""
        err: str | None = None
        try:
            output = sut.call(case.input)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        dur_ms = int((time.perf_counter() - t0) * 1000)

        # 2) Score the output (use case-specific scoring or default)
        specs = case.scoring if case.scoring else DEFAULT_SCORING
        scorers: list[Scorer] = [make_scorer(s) for s in specs]
        score_results: list[ScoreResult] = []
        for sc in scorers:
            try:
                score_results.append(sc.score(case, output))
            except Exception as e:
                from lrd.scoring.base import ScoreResult as _SR
                score_results.append(_SR(sc.name, 0.0, False, f"scorer crashed: {e}"))

        # 3) Persist
        store.add_result(run_id, case.id, output, dur_ms, err)
        for sr in score_results:
            store.add_score(run_id, case.id, sr)

        summaries.append(CaseSummary(case.id, output, err, dur_ms, score_results))

    summary = RunSummary(
        run_id=run_id, sut_name=sut.name,
        golden_path=str(goldens.path), cases=summaries,
    )
    store.finish_run(run_id, summary.n_cases, summary.n_passed, summary.avg_score)
    if progress_cb:
        progress_cb(len(goldens.cases), len(goldens.cases), None)
    return summary
