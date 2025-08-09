import pytest

from lrd import golden


def test_loads_minimal_yaml(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text(
        "- id: a\n  input: foo\n  expected: bar\n"
        "- id: b\n  input: hello\n  expected: world\n"
    )
    gs = golden.load(p)
    assert len(gs) == 2
    assert gs.cases[0].id == "a"
    assert gs.cases[1].input == "hello"


def test_duplicate_ids_raise(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text("- id: x\n  input: a\n- id: x\n  input: b\n")
    with pytest.raises(ValueError, match="duplicate"):
        golden.load(p)


def test_missing_id_raises(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text("- input: nope\n")
    with pytest.raises(ValueError, match="id"):
        golden.load(p)


def test_scoring_specs_parsed(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text(
        "- id: a\n"
        "  input: in\n"
        "  expected: out\n"
        "  scoring:\n"
        "    - method: structural\n"
        "      threshold: 0.9\n"
        "      rules: [{regex: '^X'}, {contains: hello}]\n"
        "    - method: semantic_sim\n"
        "      threshold: 0.5\n"
    )
    gs = golden.load(p)
    case = gs.cases[0]
    assert len(case.scoring) == 2
    assert case.scoring[0].method == "structural"
    assert case.scoring[0].params["threshold"] == 0.9
    assert case.scoring[1].method == "semantic_sim"
