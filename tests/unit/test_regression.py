"""Regression detector — pure logic tests (no LLM calls)."""
from lrd.regression import AlertConfig, CaseChange, RegressionReport, should_alert
from lrd.scoring.base import ScoreResult
from lrd.store.duckdb_store import Store


def test_case_change_flags():
    pass_to_fail = CaseChange("c1", "structural", 0.9, 0.4, True, False)
    assert pass_to_fail.regressed
    assert not pass_to_fail.recovered

    fail_to_pass = CaseChange("c2", "structural", 0.4, 0.9, False, True)
    assert fail_to_pass.recovered
    assert not fail_to_pass.regressed

    drift_inside_pass = CaseChange("c3", "structural", 0.95, 0.85, True, True)
    assert not drift_inside_pass.regressed
    assert not drift_inside_pass.recovered


def test_should_alert_fires_on_regression_count():
    rep = RegressionReport(
        baseline_run_id="a", current_run_id="b", sut_name="sut",
        case_changes=[CaseChange("c1", "x", 1.0, 0.0, True, False)],
        pass_rate_baseline=1.0, pass_rate_current=0.5,
        avg_score_baseline=1.0, avg_score_current=0.5,
    )
    fire, reasons = should_alert(rep, AlertConfig(regress_count_threshold=1))
    assert fire
    assert any("regress" in r.lower() for r in reasons)


def test_should_alert_fires_on_pass_rate_drop():
    rep = RegressionReport(
        baseline_run_id="a", current_run_id="b", sut_name="sut",
        case_changes=[],
        pass_rate_baseline=0.95, pass_rate_current=0.50,
        avg_score_baseline=0.9, avg_score_current=0.85,
    )
    fire, reasons = should_alert(rep, AlertConfig(fail_below_pass_rate=0.80))
    assert fire
    assert any("pass rate" in r.lower() for r in reasons)


def test_should_alert_silent_on_clean_run():
    rep = RegressionReport(
        baseline_run_id="a", current_run_id="b", sut_name="sut",
        case_changes=[CaseChange("c1", "x", 0.95, 0.94, True, True)],
        pass_rate_baseline=1.0, pass_rate_current=1.0,
        avg_score_baseline=0.95, avg_score_current=0.94,
    )
    fire, reasons = should_alert(rep, AlertConfig())
    assert not fire
    assert reasons == []


def test_detect_round_trip(tmp_path):
    """Build two runs in a fresh store, run detect(), check the report."""
    from lrd.regression import detect
    s = Store(tmp_path / "t.duckdb")

    rid_a = s.start_run("test-sut", "g.yaml")
    s.add_score(rid_a, "case1", ScoreResult("structural", 1.0, True, ""))
    s.add_score(rid_a, "case2", ScoreResult("structural", 1.0, True, ""))
    s.finish_run(rid_a, n_cases=2, n_passed=2, avg_score=1.0)

    rid_b = s.start_run("test-sut", "g.yaml")
    # case1 regresses
    s.add_score(rid_b, "case1", ScoreResult("structural", 0.3, False, ""))
    s.add_score(rid_b, "case2", ScoreResult("structural", 1.0, True, ""))
    s.finish_run(rid_b, n_cases=2, n_passed=1, avg_score=0.65)

    report = detect(s, rid_a, rid_b)
    assert report.n_regressed == 1
    assert report.regressed_cases[0].case_id == "case1"
    assert report.pass_rate_baseline == 1.0
    assert report.pass_rate_current == 0.5
    s.close()
