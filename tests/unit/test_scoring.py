"""Scoring tests — only the offline scorer (structural). Embedding + judge
scorers hit external APIs and are tested in integration tests."""
from lrd.golden import GoldenCase
from lrd.scoring.structural import StructuralScorer


def case(id_="x", expected="bar"):
    return GoldenCase(id=id_, input="foo", expected=expected)


def test_structural_all_pass():
    s = StructuralScorer(rules=[
        {"regex": r"\bHello\b"},
        {"contains": "world"},
        {"min_length": 5},
    ])
    r = s.score(case(), "Hello world!")
    assert r.score == 1.0
    assert r.passed is True


def test_structural_partial_fail_below_threshold():
    s = StructuralScorer(rules=[
        {"regex": r"^MISSING"},
        {"contains": "world"},
    ], threshold=1.0)
    r = s.score(case(), "Hello world")
    assert r.score == 0.5
    assert r.passed is False


def test_structural_max_length_violation():
    s = StructuralScorer(rules=[{"max_length": 3}])
    r = s.score(case(), "abcdef")
    assert r.passed is False
    assert "max_length" in r.detail


def test_structural_no_rules_passes():
    r = StructuralScorer(rules=[]).score(case(), "anything")
    assert r.score == 1.0 and r.passed is True
