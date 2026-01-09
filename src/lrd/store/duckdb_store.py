"""Run store — DuckDB schema for runs / results / scores.

Layout:
  runs(run_id PK, started_at, finished_at, sut_name, golden_path,
       n_cases, n_passed, avg_score, regressed)
  results(run_id, case_id, output, duration_ms, error,
          PRIMARY KEY (run_id, case_id))
  scores(run_id, case_id, method, score, passed, detail,
         PRIMARY KEY (run_id, case_id, method))

DuckDB is in-process, file-backed, supports SQL → great for the dashboard's
analytics views.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from lrd.scoring.base import ScoreResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      VARCHAR PRIMARY KEY,
    started_at  TIMESTAMP,
    finished_at TIMESTAMP,
    sut_name    VARCHAR,
    golden_path VARCHAR,
    n_cases     INTEGER,
    n_passed    INTEGER,
    avg_score   DOUBLE,
    regressed   BOOLEAN
);

CREATE TABLE IF NOT EXISTS results (
    run_id      VARCHAR,
    case_id     VARCHAR,
    output      TEXT,
    duration_ms INTEGER,
    error       VARCHAR,
    PRIMARY KEY (run_id, case_id)
);

CREATE TABLE IF NOT EXISTS scores (
    run_id  VARCHAR,
    case_id VARCHAR,
    method  VARCHAR,
    score   DOUBLE,
    passed  BOOLEAN,
    detail  VARCHAR,
    PRIMARY KEY (run_id, case_id, method)
);
"""


@dataclass
class Store:
    path: Path

    def __post_init__(self):
        self.con = duckdb.connect(str(self.path))
        self.con.execute(_SCHEMA)

    def close(self) -> None:
        self.con.close()

    # ─── Run lifecycle ──────────────────────────────────────────────────────
    def start_run(self, sut_name: str, golden_path: str) -> str:
        run_id = uuid.uuid4().hex[:10]
        self.con.execute(
            "INSERT INTO runs (run_id, started_at, sut_name, golden_path, "
            "n_cases, n_passed, avg_score, regressed) "
            "VALUES (?, ?, ?, ?, 0, 0, 0.0, NULL)",
            [run_id, dt.datetime.utcnow(), sut_name, golden_path],
        )
        return run_id

    def finish_run(
        self, run_id: str, n_cases: int, n_passed: int, avg_score: float,
        regressed: bool | None = None,
    ) -> None:
        self.con.execute(
            "UPDATE runs SET finished_at = ?, n_cases = ?, n_passed = ?, "
            "avg_score = ?, regressed = ? WHERE run_id = ?",
            [dt.datetime.utcnow(), n_cases, n_passed, avg_score, regressed, run_id],
        )

    # ─── Per-case results + scores ──────────────────────────────────────────
    def add_result(
        self, run_id: str, case_id: str, output: str, duration_ms: int,
        error: str | None,
    ) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?)",
            [run_id, case_id, output, duration_ms, error],
        )

    def add_score(self, run_id: str, case_id: str, sr: ScoreResult) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, case_id, sr.method, sr.score, sr.passed, sr.detail],
        )

    # ─── Queries (dashboard / regression detector) ─────────────────────────
    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.con.execute(
            "SELECT run_id, started_at, finished_at, sut_name, golden_path, "
            "n_cases, n_passed, avg_score, regressed "
            "FROM runs ORDER BY started_at DESC LIMIT ?",
            [limit],
        ).fetchall()
        cols = ["run_id", "started_at", "finished_at", "sut_name", "golden_path",
                "n_cases", "n_passed", "avg_score", "regressed"]
        return [dict(zip(cols, r)) for r in rows]

    def latest_run_id(self, sut_name: str | None = None) -> str | None:
        q = "SELECT run_id FROM runs WHERE finished_at IS NOT NULL"
        params: list[Any] = []
        if sut_name:
            q += " AND sut_name = ?"
            params.append(sut_name)
        q += " ORDER BY finished_at DESC LIMIT 1"
        row = self.con.execute(q, params).fetchone()
        return row[0] if row else None

    def get_results(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.con.execute(
            "SELECT case_id, output, duration_ms, error FROM results "
            "WHERE run_id = ? ORDER BY case_id", [run_id],
        ).fetchall()
        cols = ["case_id", "output", "duration_ms", "error"]
        return [dict(zip(cols, r)) for r in rows]

    def get_scores(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.con.execute(
            "SELECT case_id, method, score, passed, detail FROM scores "
            "WHERE run_id = ? ORDER BY case_id, method", [run_id],
        ).fetchall()
        cols = ["case_id", "method", "score", "passed", "detail"]
        return [dict(zip(cols, r)) for r in rows]
