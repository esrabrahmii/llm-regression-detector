"""Alerter — payload structure + simulated-mode write."""
import json

from lrd.alerter import build_payload, send
from lrd.regression import CaseChange, RegressionReport


def make_report():
    return RegressionReport(
        baseline_run_id="abc1234567",
        current_run_id="def8901234",
        sut_name="mlra-planner",
        case_changes=[
            CaseChange("lora_q", "llm_judge", 1.0, 0.4, True, False),
            CaseChange("svm_q", "semantic_sim", 0.9, 0.5, True, False),
        ],
        pass_rate_baseline=1.0, pass_rate_current=0.33,
        avg_score_baseline=0.92, avg_score_current=0.55,
    )


def test_payload_has_required_fields():
    p = build_payload(make_report(), reasons=["2 cases regressed"], severity="CRITICAL")
    assert "blocks" in p
    assert "text" in p              # plain-text fallback
    types = [b["type"] for b in p["blocks"]]
    assert "header" in types
    assert "section" in types
    assert "context" in types       # the timestamp/baseline footer


def test_payload_mentions_sut_and_runs():
    p = build_payload(make_report(), reasons=["x"])
    flat = json.dumps(p)
    assert "mlra-planner" in flat
    assert "def8901234" in flat
    assert "abc1234567" in flat
    assert "lora_q" in flat


def test_send_simulated_writes_file(tmp_path, monkeypatch):
    """When SLACK_WEBHOOK_URL is empty, send() writes the payload to disk."""
    from lrd import alerter as al
    monkeypatch.setattr(al, "ALERTS_DIR", tmp_path)
    payload = build_payload(make_report(), ["2 cases"])
    result = send(payload, run_id="r1", webhook_url="")
    assert result.sent is False
    assert result.payload_path.exists()
    assert result.payload_path.parent == tmp_path
    body = json.loads(result.payload_path.read_text())
    assert body["text"].startswith(":x:")
