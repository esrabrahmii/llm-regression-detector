"""Regression detection — compares two runs case-by-case.

A regression fires on any of:
  - a case flipped pass → fail (any method)
  - aggregate pass-rate dropped below `fail_below_pass_rate`
  - aggregate avg score dropped by ≥ `regress_score_drop`
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lrd.store.duckdb_store import Store

# ─── Configuration ───────────────────────────────────────────────────────────

@dataclass
class AlertConfig:
    """Thresholds that decide whether to fire an alert."""
    fail_below_pass_rate: float = 0.80      # alert if pass rate drops below this
    regress_count_threshold: int = 1        # alert if N+ cases flipped pass→fail
    regress_score_drop: float = 0.10        # alert if avg score drops by this much
    score_delta_min: float = 0.05           # ignore score deltas smaller than this


# ─── Per-case + aggregate change records ────────────────────────────────────

@dataclass
class CaseChange:
    case_id: str
    method: str
    baseline_score: float
    current_score: float
    baseline_passed: bool
    current_passed: bool

    @property
    def delta(self) -> float:
        return self.current_score - self.baseline_score

    @property
    def regressed(self) -> bool:
        return self.baseline_passed and not self.current_passed

    @property
    def recovered(self) -> bool:
        return not self.baseline_passed and self.current_passed


@dataclass
class RegressionReport:
    baseline_run_id: str
    current_run_id: str
    sut_name: str
    case_changes: list[CaseChange] = field(default_factory=list)
    pass_rate_baseline: float = 0.0
    pass_rate_current: float = 0.0
    avg_score_baseline: float = 0.0
    avg_score_current: float = 0.0

    @property
    def regressed_cases(self) -> list[CaseChange]:
        return [c for c in self.case_changes if c.regressed]

    @property
    def recovered_cases(self) -> list[CaseChange]:
        return [c for c in self.case_changes if c.recovered]

    @property
    def n_regressed(self) -> int:
        return len(self.regressed_cases)

    @property
    def n_recovered(self) -> int:
        return len(self.recovered_cases)

    @property
    def pass_rate_delta(self) -> float:
        return self.pass_rate_current - self.pass_rate_baseline

    @property
    def avg_score_delta(self) -> float:
        return self.avg_score_current - self.avg_score_baseline


# ─── Detection logic ────────────────────────────────────────────────────────

def detect(
    store: Store, baseline_run_id: str, current_run_id: str
) -> RegressionReport:
    """Build the report. Pure DB queries — no thresholds applied yet."""
    runs = {r["run_id"]: r for r in store.list_runs(limit=200)}
    if baseline_run_id not in runs:
        raise ValueError(f"baseline run {baseline_run_id} not found")
    if current_run_id not in runs:
        raise ValueError(f"current run {current_run_id} not found")

    sa = {(s["case_id"], s["method"]): s for s in store.get_scores(baseline_run_id)}
    sb = {(s["case_id"], s["method"]): s for s in store.get_scores(current_run_id)}

    changes: list[CaseChange] = []
    for key in sorted(set(sa) | set(sb)):
        a = sa.get(key)
        b = sb.get(key)
        if not a or not b:
            continue  # case present only in one run — skip (set membership change)
        changes.append(
            CaseChange(
                case_id=key[0], method=key[1],
                baseline_score=a["score"], current_score=b["score"],
                baseline_passed=a["passed"], current_passed=b["passed"],
            )
        )

    a_run, b_run = runs[baseline_run_id], runs[current_run_id]
    pass_rate_a = (a_run["n_passed"] or 0) / max(a_run["n_cases"] or 1, 1)
    pass_rate_b = (b_run["n_passed"] or 0) / max(b_run["n_cases"] or 1, 1)

    return RegressionReport(
        baseline_run_id=baseline_run_id,
        current_run_id=current_run_id,
        sut_name=b_run["sut_name"] or "?",
        case_changes=changes,
        pass_rate_baseline=pass_rate_a,
        pass_rate_current=pass_rate_b,
        avg_score_baseline=a_run["avg_score"] or 0.0,
        avg_score_current=b_run["avg_score"] or 0.0,
    )


def should_alert(report: RegressionReport, config: AlertConfig) -> tuple[bool, list[str]]:
    """Apply thresholds. Returns (fire?, list of reasons)."""
    reasons: list[str] = []
    if report.n_regressed >= config.regress_count_threshold:
        reasons.append(
            f"{report.n_regressed} case(s) regressed (pass → fail) — "
            f"threshold: {config.regress_count_threshold}"
        )
    if report.pass_rate_current < config.fail_below_pass_rate:
        reasons.append(
            f"pass rate {report.pass_rate_current:.0%} fell below "
            f"{config.fail_below_pass_rate:.0%}"
        )
    if report.avg_score_baseline - report.avg_score_current >= config.regress_score_drop:
        reasons.append(
            f"avg score dropped by {report.avg_score_baseline - report.avg_score_current:.2f} "
            f"(threshold: {config.regress_score_drop:.2f})"
        )
    return (len(reasons) > 0, reasons)


def auto_baseline(
    store: Store, sut_name: str, golden_path: str, exclude: str | None = None
) -> str | None:
    """Find the most recent finished run with same sut + golden — for `lrd run`'s
    automatic baseline detection."""
    rows = store.list_runs(limit=200)
    for r in rows:
        if r["run_id"] == exclude:
            continue
        if r["sut_name"] != sut_name:
            continue
        if r["golden_path"] != golden_path:
            continue
        if r["finished_at"] is None:
            continue
        return r["run_id"]
    return None
