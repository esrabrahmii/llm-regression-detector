"""DuckDB + alerts/ readers for the dashboard.

Everything here is read-only. The CLI writes; the dashboard only reads.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from lrd.alerter import ALERTS_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DB = PROJECT_ROOT / "runs.duckdb"


def _con(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=False)


# ─── Runs / scores ──────────────────────────────────────────────────────────

def list_runs(db_path: Path = DEFAULT_DB, limit: int = 100) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    con = _con(db_path)
    rows = con.execute(
        "SELECT run_id, started_at, finished_at, sut_name, golden_path, "
        "n_cases, n_passed, avg_score, regressed "
        "FROM runs WHERE finished_at IS NOT NULL "
        "ORDER BY started_at DESC LIMIT ?", [limit],
    ).fetchall()
    con.close()
    cols = ["run_id", "started_at", "finished_at", "sut_name", "golden_path",
            "n_cases", "n_passed", "avg_score", "regressed"]
    return [dict(zip(cols, r)) for r in rows]


def get_scores(run_id: str, db_path: Path = DEFAULT_DB) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    con = _con(db_path)
    rows = con.execute(
        "SELECT case_id, method, score, passed, detail FROM scores "
        "WHERE run_id = ? ORDER BY case_id, method", [run_id],
    ).fetchall()
    con.close()
    return [dict(zip(["case_id", "method", "score", "passed", "detail"], r)) for r in rows]


def get_results(run_id: str, db_path: Path = DEFAULT_DB) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    con = _con(db_path)
    rows = con.execute(
        "SELECT case_id, output, duration_ms, error FROM results "
        "WHERE run_id = ? ORDER BY case_id", [run_id],
    ).fetchall()
    con.close()
    return [dict(zip(["case_id", "output", "duration_ms", "error"], r)) for r in rows]


# ─── Aggregates for the dashboard summary cards ─────────────────────────────

def summary_stats(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    runs = list_runs(db_path, limit=200)
    if not runs:
        return {
            "active_models": 0,
            "latest_severity": "—",
            "drift_30d": 0,
            "latest_pass_rate": None,
            "latest_avg_score": None,
        }

    sut_set = {r["sut_name"] for r in runs if r["sut_name"]}
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=30)

    # A run is "drift-flagged" if its avg score is >= 5% lower than the prior run
    # for the same SUT — a cheap proxy for "drift indicator".
    drift = 0
    by_sut: dict[str, list[dict]] = {}
    for r in runs:
        by_sut.setdefault(r["sut_name"] or "?", []).append(r)
    for sut_runs in by_sut.values():
        # runs are sorted DESC, so iterate pairwise current→prior
        for i in range(len(sut_runs) - 1):
            cur, prev = sut_runs[i], sut_runs[i + 1]
            if cur["started_at"] is None or cur["started_at"] < cutoff:
                continue
            cs, ps = cur["avg_score"] or 0.0, prev["avg_score"] or 0.0
            if ps - cs >= 0.05:
                drift += 1

    latest = runs[0]
    severity = "OK"
    if (latest["n_passed"] or 0) < (latest["n_cases"] or 1):
        severity = "Critical" if latest["n_passed"] == 0 else "Degraded"

    return {
        "active_models": len(sut_set),
        "latest_severity": severity,
        "drift_30d": drift,
        "latest_pass_rate": (latest["n_passed"] or 0) / max(latest["n_cases"] or 1, 1),
        "latest_avg_score": latest["avg_score"] or 0.0,
        "latest_run_id": latest["run_id"],
        "latest_sut": latest["sut_name"],
    }


def perf_history(db_path: Path = DEFAULT_DB, limit: int = 50) -> list[dict[str, Any]]:
    """Time-series of (started_at, sut_name, avg_score, pass_rate) for the chart."""
    runs = list_runs(db_path, limit=limit)
    runs.reverse()  # ascending time for plotting
    out: list[dict[str, Any]] = []
    for r in runs:
        rate = (r["n_passed"] or 0) / max(r["n_cases"] or 1, 1)
        out.append({
            "started_at": r["started_at"],
            "sut_name": r["sut_name"],
            "avg_score": r["avg_score"] or 0.0,
            "pass_rate": rate,
            "run_id": r["run_id"],
        })
    return out


# ─── Latest regression — for the diff card ──────────────────────────────────

@dataclass
class LatestRegression:
    sut_name: str
    current_run_id: str
    baseline_run_id: str
    pass_rate_baseline: float
    pass_rate_current: float
    avg_score_baseline: float
    avg_score_current: float
    case_id: str
    method: str
    previous_output: str
    current_output: str


def latest_regression(db_path: Path = DEFAULT_DB) -> LatestRegression | None:
    """Find the most recent run where at least one case flipped pass→fail."""
    if not db_path.exists():
        return None
    con = _con(db_path)
    rows = con.execute(
        "SELECT run_id, sut_name FROM runs "
        "WHERE finished_at IS NOT NULL "
        "ORDER BY started_at DESC LIMIT 50",
    ).fetchall()
    if not rows:
        con.close()
        return None
    # Walk runs newest → oldest; for each, find prior run with same sut
    by_sut: dict[str, list[str]] = {}
    for rid, sut in rows:
        by_sut.setdefault(sut or "?", []).append(rid)

    for cur_rid, sut in rows:
        sut_runs = by_sut.get(sut or "?", [])
        try:
            i = sut_runs.index(cur_rid)
        except ValueError:
            continue
        if i + 1 >= len(sut_runs):
            continue
        prev_rid = sut_runs[i + 1]
        # find a case+method that flipped pass→fail
        cur_scores = {(s[0], s[1]): s for s in con.execute(
            "SELECT case_id, method, score, passed FROM scores WHERE run_id = ?",
            [cur_rid]).fetchall()}
        prev_scores = {(s[0], s[1]): s for s in con.execute(
            "SELECT case_id, method, score, passed FROM scores WHERE run_id = ?",
            [prev_rid]).fetchall()}
        for k, prev in prev_scores.items():
            cur = cur_scores.get(k)
            if not cur:
                continue
            if prev[3] and not cur[3]:  # was passed, now failed
                cur_out = con.execute(
                    "SELECT output FROM results WHERE run_id = ? AND case_id = ?",
                    [cur_rid, k[0]]).fetchone()
                prev_out = con.execute(
                    "SELECT output FROM results WHERE run_id = ? AND case_id = ?",
                    [prev_rid, k[0]]).fetchone()
                cur_run = con.execute(
                    "SELECT n_cases, n_passed, avg_score FROM runs WHERE run_id = ?",
                    [cur_rid]).fetchone()
                prev_run = con.execute(
                    "SELECT n_cases, n_passed, avg_score FROM runs WHERE run_id = ?",
                    [prev_rid]).fetchone()
                con.close()
                return LatestRegression(
                    sut_name=sut or "?",
                    current_run_id=cur_rid,
                    baseline_run_id=prev_rid,
                    pass_rate_baseline=(prev_run[1] or 0) / max(prev_run[0] or 1, 1),
                    pass_rate_current=(cur_run[1] or 0) / max(cur_run[0] or 1, 1),
                    avg_score_baseline=prev_run[2] or 0.0,
                    avg_score_current=cur_run[2] or 0.0,
                    case_id=k[0],
                    method=k[1],
                    previous_output=(prev_out[0] if prev_out else "") or "",
                    current_output=(cur_out[0] if cur_out else "") or "",
                )
    con.close()
    return None


# ─── Alerts (filesystem) ────────────────────────────────────────────────────

def list_alerts(alerts_dir: Path = ALERTS_DIR, limit: int = 20) -> list[dict[str, Any]]:
    """Read all alert JSONs from alerts/, newest first."""
    if not alerts_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(alerts_dir.iterdir(), reverse=True):
        if p.suffix != ".json":
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        # extract some headers from the block-kit payload
        run_id = ""
        sut = ""
        for block in payload.get("blocks", []):
            if block.get("type") == "section" and block.get("fields"):
                for field in block["fields"]:
                    txt = field.get("text", "")
                    if "*Run*" in txt:
                        run_id = txt.split("`")[1] if "`" in txt else ""
                    elif "*SUT*" in txt:
                        # text format: "*SUT*\n<name>"
                        parts = txt.split("\n", 1)
                        if len(parts) == 2:
                            sut = parts[1]
        out.append({
            "filename": p.name,
            "path": p,
            "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime),
            "text": payload.get("text", ""),
            "run_id": run_id,
            "sut_name": sut,
            "payload": payload,
        })
        if len(out) >= limit:
            break
    return out
