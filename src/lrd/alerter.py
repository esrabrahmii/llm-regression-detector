"""Slack alerter — builds a Block-Kit payload and either:
  - posts it to SLACK_WEBHOOK_URL (real)
  - or writes it to alerts/<timestamp>_<run_id>.json (simulated)

The same payload structure is used for both, so what the dashboard renders
matches what Slack would have shown.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lrd.regression import RegressionReport

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALERTS_DIR = PROJECT_ROOT / "alerts"


@dataclass
class AlertResult:
    sent: bool             # True if real webhook fire; False if simulated
    payload_path: Path     # where the payload JSON was written
    webhook_status: int | None = None  # HTTP status if real send
    error: str | None = None


# ─── Block-Kit payload builder ──────────────────────────────────────────────

def build_payload(
    report: RegressionReport, reasons: list[str], severity: str = "CRITICAL"
) -> dict[str, Any]:
    """Slack Block-Kit format. Renders nicely in Slack; also nicely in the
    dashboard's 'Recent Slack Alerts' panel."""
    def pct(x: float) -> str:
        return f"{x * 100:.0f}%"
    delta = report.pass_rate_delta * 100
    delta_str = f"{delta:+.0f}%"

    # First N regressed cases for the message body
    top = report.regressed_cases[:6]
    case_lines = [
        f"• `{c.case_id}` · {c.method}: {c.baseline_score:.2f} → {c.current_score:.2f}"
        for c in top
    ]
    if len(report.regressed_cases) > len(top):
        case_lines.append(f"_…and {len(report.regressed_cases) - len(top)} more_")

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"❌ LLM Regression Detected — {severity}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*SUT*\n{report.sut_name}"},
                {"type": "mrkdwn", "text": f"*Run*\n`{report.current_run_id}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Pass rate*\n{pct(report.pass_rate_baseline)} → "
                            f"{pct(report.pass_rate_current)}  ({delta_str})",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Avg score*\n"
                            f"{report.avg_score_baseline:.2f} → "
                            f"{report.avg_score_current:.2f}  "
                            f"({report.avg_score_delta:+.2f})",
                },
            ],
        },
    ]
    if reasons:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Why this fired:*\n" + "\n".join(f"• {r}" for r in reasons),
            },
        })
    if case_lines:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Regressed cases:*\n" + "\n".join(case_lines),
            },
        })
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"baseline `{report.baseline_run_id}` · "
                        f"detected at {dt.datetime.utcnow().isoformat(timespec='seconds')}Z",
            }
        ],
    })

    return {
        "text": (f":x: LLM Regression Detected — {report.n_regressed} case(s) "
                 f"regressed in {report.sut_name}"),  # plain text fallback
        "blocks": blocks,
    }


# ─── Send (real Slack) or simulate (write JSON file) ────────────────────────

def send(
    payload: dict[str, Any], run_id: str, webhook_url: str = ""
) -> AlertResult:
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    out_path = ALERTS_DIR / f"{ts}_{run_id}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not webhook_url:
        return AlertResult(sent=False, payload_path=out_path)

    # Real send via stdlib (no extra dependency)
    import urllib.request

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return AlertResult(
                sent=True, payload_path=out_path, webhook_status=resp.status
            )
    except Exception as e:
        return AlertResult(
            sent=False, payload_path=out_path, error=f"{type(e).__name__}: {e}"
        )
