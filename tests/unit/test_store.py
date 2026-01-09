from lrd.scoring.base import ScoreResult
from lrd.store.duckdb_store import Store


def test_full_run_lifecycle(tmp_path):
    s = Store(tmp_path / "test.duckdb")
    rid = s.start_run(sut_name="mlra-planner", golden_path="ex.yaml")
    s.add_result(rid, "case_a", "hello", 12, None)
    s.add_score(rid, "case_a", ScoreResult("structural", 1.0, True, "all rules"))
    s.add_score(rid, "case_a", ScoreResult("semantic_sim", 0.8, True, "cos=0.8"))
    s.finish_run(rid, n_cases=1, n_passed=1, avg_score=0.9)

    runs = s.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == rid
    assert runs[0]["n_passed"] == 1

    results = s.get_results(rid)
    assert results[0]["case_id"] == "case_a"
    assert results[0]["output"] == "hello"

    scores = s.get_scores(rid)
    assert len(scores) == 2
    methods = {sc["method"] for sc in scores}
    assert methods == {"structural", "semantic_sim"}
    s.close()


def test_latest_run_id_filters_unfinished(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    a = s.start_run("sut1", "g.yaml")
    s.finish_run(a, 0, 0, 0.0)
    b = s.start_run("sut1", "g.yaml")  # not finished
    assert s.latest_run_id() == a
    s.finish_run(b, 0, 0, 0.0)
    assert s.latest_run_id() == b
    s.close()
