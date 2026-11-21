import json

from .reuse_derivation import ROOT, summarize
from .reuse_predicates import rows


def test_predicate_pairs_reproduce_and_tie_semantic_manual():
    paired = list(rows())
    saved = ROOT / "research/venue2027/compsac/derivation/semantic.jsonl"
    assert [json.loads(line) for line in saved.read_text().splitlines()] == json.loads(
        json.dumps(paired)
    )
    assert len(paired) == 48
    assert all(r["valid"] == r["admit"]["derived"] == r["admit"]["manual"] for r in paired)
    totals = summarize(paired)
    assert totals["deposit"]["vs_coordinate_derived_win"] == 8
    assert totals["check"]["vs_coordinate_derived_win"] == 6
