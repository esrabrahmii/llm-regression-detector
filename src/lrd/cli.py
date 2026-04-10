"""`lrd` CLI — Typer-based.

Commands:
  lrd run <golden.yaml>        Run goldens through the SUT, persist + summarise.
                               Auto-detects a baseline from the most recent run
                               with the same SUT + golden file, and exits non-zero
                               if regressions are detected (CI signal).
  lrd runs                     List recent runs
  lrd diff <run_a> <run_b>     Compare two runs (regression view)
  lrd alert <run_id>           Re-fire a Slack alert for an existing run
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from lrd.alerter import build_payload, send
from lrd.config import settings
from lrd.regression import AlertConfig, auto_baseline, detect, should_alert
from lrd.runner import run as run_goldens
from lrd.store.duckdb_store import Store
from lrd.sut.mlra_planner import MlraPlannerSUT

app = typer.Typer(help="LLM Regression Detector — CI/CD for LLM behavior.")
console = Console()


# ─── lrd run ────────────────────────────────────────────────────────────────

@app.command()
def run(
    golden: Path = typer.Argument(..., exists=True, help="path to a golden YAML file"),
    db: Path = typer.Option(Path("runs.duckdb"), help="DuckDB file (default: runs.duckdb)"),
    sut: str = typer.Option("mlra-planner", help="which SUT (currently: mlra-planner)"),
    baseline: str = typer.Option("", help="run_id to compare against (default: auto)"),
    no_alert: bool = typer.Option(False, "--no-alert", help="skip alert even if regressions detected"),
    fail_below: float = typer.Option(0.80, help="alert if pass rate below this"),
):
    """Run a golden set through the SUT and persist the results.

    On regression vs baseline: writes a Slack-formatted alert payload + exits 1.
    """
    store = Store(db)

    if sut == "mlra-planner":
        sut_obj = MlraPlannerSUT()
    else:
        raise typer.BadParameter(f"unknown sut: {sut}")

    console.print(f"[bold cyan]→[/] running goldens [bold]{golden.name}[/] against [bold]{sut}[/]")

    def progress(i, total, case_id):
        if case_id is None:
            return
        console.print(f"  [{i+1}/{total}] {case_id}", style="dim")

    summary = run_goldens(golden, sut_obj, store, progress_cb=progress)
    store.close()

    # ── pretty summary ──
    pass_rate = summary.pass_rate * 100
    color = "green" if pass_rate >= 80 else ("yellow" if pass_rate >= 50 else "red")
    console.print()
    console.print(
        f"[bold {color}]✓ run {summary.run_id}[/] · "
        f"{summary.n_passed}/{summary.n_cases} passed "
        f"({pass_rate:.0f}%) · avg score {summary.avg_score:.3f}"
    )
    # per-case breakdown
    t = Table(show_header=True, header_style="bold")
    t.add_column("case")
    t.add_column("dur (ms)", justify="right")
    t.add_column("structural", justify="right")
    t.add_column("semantic", justify="right")
    t.add_column("llm-judge", justify="right")
    t.add_column("verdict")
    def _fmt(method: str, by_method: dict) -> str:
        s = by_method.get(method)
        if not s:
            return "-"
        mark = "[green]✓[/]" if s.passed else "[red]✗[/]"
        return f"{s.score:.2f} {mark}"

    for c in summary.cases:
        s_by_method = {s.method: s for s in c.scores}
        verdict = "[green]PASS[/]" if c.passed else "[red]FAIL[/]"
        if c.error:
            verdict = "[red]ERR[/]"
        t.add_row(
            c.case_id, str(c.duration_ms),
            _fmt("structural", s_by_method),
            _fmt("semantic_sim", s_by_method),
            _fmt("llm_judge", s_by_method),
            verdict,
        )
    console.print(t)

    # ── Regression detection vs baseline ──
    re_open_store = Store(db)
    if not baseline:
        baseline = auto_baseline(
            re_open_store, sut_name=summary.sut_name,
            golden_path=str(summary.golden_path), exclude=summary.run_id,
        ) or ""
    if not baseline:
        console.print()
        console.print("[dim]no prior run found — skipping regression check (this is the new baseline)[/]")
        re_open_store.close()
        raise typer.Exit(code=0)

    cfg = AlertConfig(fail_below_pass_rate=fail_below)
    report = detect(re_open_store, baseline, summary.run_id)
    fire, reasons = should_alert(report, cfg)
    re_open_store.close()

    console.print()
    console.print(f"[bold]Regression check[/] vs baseline `{baseline}`:")
    console.print(
        f"  pass rate {report.pass_rate_baseline:.0%} → {report.pass_rate_current:.0%}  "
        f"({report.pass_rate_delta * 100:+.0f} pp)"
    )
    console.print(
        f"  avg score {report.avg_score_baseline:.3f} → {report.avg_score_current:.3f}  "
        f"({report.avg_score_delta:+.3f})"
    )
    console.print(f"  regressed cases: {report.n_regressed}  ·  recovered: {report.n_recovered}")

    if not fire:
        console.print("[bold green]✓ no regression[/]")
        raise typer.Exit(code=0)

    console.print("[bold red]✗ REGRESSION DETECTED[/]")
    for r in reasons:
        console.print(f"  • {r}")
    if no_alert:
        console.print("[dim](--no-alert: skipping Slack send)[/]")
        raise typer.Exit(code=1)

    payload = build_payload(report, reasons, severity="CRITICAL")
    result = send(payload, run_id=summary.run_id, webhook_url=settings.slack_webhook_url)
    if result.sent:
        console.print(f"[cyan]→[/] Slack webhook fired (HTTP {result.webhook_status})")
    elif result.error:
        console.print(f"[yellow]⚠[/] webhook failed: {result.error}")
    console.print(f"[dim]payload written to {result.payload_path.relative_to(Path.cwd())}[/]")
    raise typer.Exit(code=1)


# ─── lrd runs ───────────────────────────────────────────────────────────────

@app.command()
def runs(
    db: Path = typer.Option(Path("runs.duckdb"), help="DuckDB file"),
    limit: int = typer.Option(20, help="how many to show"),
):
    """List recent runs."""
    store = Store(db)
    rows = store.list_runs(limit=limit)
    store.close()
    if not rows:
        console.print("[dim]no runs yet[/]")
        return
    t = Table(show_header=True, header_style="bold")
    t.add_column("run_id")
    t.add_column("started")
    t.add_column("sut")
    t.add_column("cases", justify="right")
    t.add_column("passed", justify="right")
    t.add_column("pass-rate", justify="right")
    t.add_column("avg score", justify="right")
    for r in rows:
        rate = (r["n_passed"] or 0) / (r["n_cases"] or 1)
        col = "green" if rate >= 0.8 else ("yellow" if rate >= 0.5 else "red")
        t.add_row(
            r["run_id"], str(r["started_at"])[:19], r["sut_name"] or "?",
            str(r["n_cases"] or 0), str(r["n_passed"] or 0),
            f"[{col}]{rate*100:.0f}%[/]",
            f"{(r['avg_score'] or 0):.3f}",
        )
    console.print(t)


# ─── lrd diff ───────────────────────────────────────────────────────────────

@app.command()
def diff(
    run_a: str = typer.Argument(..., help="baseline run id"),
    run_b: str = typer.Argument(..., help="candidate run id"),
    db: Path = typer.Option(Path("runs.duckdb"), help="DuckDB file"),
):
    """Compare two runs case-by-case (case-level pass/fail flips)."""
    store = Store(db)
    sa = {(s["case_id"], s["method"]): s for s in store.get_scores(run_a)}
    sb = {(s["case_id"], s["method"]): s for s in store.get_scores(run_b)}
    store.close()

    keys = sorted(set(sa) | set(sb))
    t = Table(show_header=True, header_style="bold")
    t.add_column("case·method")
    t.add_column(f"{run_a[:8]}", justify="right")
    t.add_column(f"{run_b[:8]}", justify="right")
    t.add_column("Δ", justify="right")
    t.add_column("flip")
    flips = 0
    for k in keys:
        a = sa.get(k)
        b = sb.get(k)
        sa_v = a["score"] if a else 0.0
        sb_v = b["score"] if b else 0.0
        d = sb_v - sa_v
        flip = ""
        if a and b and a["passed"] != b["passed"]:
            flip = "[red]REGRESSED[/]" if a["passed"] else "[green]RECOVERED[/]"
            if a["passed"]:
                flips += 1
        d_str = f"{d:+.3f}"
        col = "red" if d < -0.05 else ("green" if d > 0.05 else "dim")
        t.add_row(f"{k[0]} · {k[1]}", f"{sa_v:.2f}", f"{sb_v:.2f}",
                  f"[{col}]{d_str}[/]", flip)
    console.print(t)
    console.print()
    if flips > 0:
        console.print(f"[bold red]✗ {flips} case(s) regressed[/]")
    else:
        console.print("[bold green]✓ no regressions[/]")


# ─── lrd alert ──────────────────────────────────────────────────────────────

@app.command()
def alert(
    run_id: str = typer.Argument(..., help="run_id to alert on"),
    baseline: str = typer.Option("", help="baseline run_id (default: auto)"),
    db: Path = typer.Option(Path("runs.duckdb"), help="DuckDB file"),
):
    """Re-fire a Slack alert for an existing run (manual / debug)."""
    store = Store(db)
    runs_rows = {r["run_id"]: r for r in store.list_runs(limit=200)}
    if run_id not in runs_rows:
        console.print(f"[red]run {run_id} not found[/]")
        raise typer.Exit(code=2)
    if not baseline:
        cur = runs_rows[run_id]
        baseline = auto_baseline(
            store, sut_name=cur["sut_name"], golden_path=cur["golden_path"],
            exclude=run_id,
        ) or ""
    if not baseline:
        console.print("[red]no baseline available — alerts compare two runs[/]")
        raise typer.Exit(code=2)

    cfg = AlertConfig()
    report = detect(store, baseline, run_id)
    fire, reasons = should_alert(report, cfg)
    store.close()
    if not fire:
        console.print("[green]no regression vs baseline — nothing to alert on[/]")
        raise typer.Exit(code=0)

    payload = build_payload(report, reasons, severity="CRITICAL")
    result = send(payload, run_id=run_id, webhook_url=settings.slack_webhook_url)
    if result.sent:
        console.print(f"[cyan]→[/] Slack webhook fired (HTTP {result.webhook_status})")
    elif result.error:
        console.print(f"[yellow]⚠[/] webhook failed: {result.error}")
    console.print(f"[dim]payload written to {result.payload_path}[/]")
