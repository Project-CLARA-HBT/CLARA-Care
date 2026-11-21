"""Check the frozen paired grid, including the observed loss and revision control."""

import json

from .reuse_derivation import ROOT, bank_rows, clinical_rows, summarize


def test_all_paired_rows_reproduce():
    saved = ROOT / "research/venue2027/compsac/derivation/paired.jsonl"
    rows = [json.loads(line) for line in saved.read_text().splitlines()]
    regenerated = json.loads(json.dumps([*bank_rows(), *clinical_rows()]))
    assert regenerated == rows
    keys = {
        (r["family"], str(r["case"]), tuple(r["before"].items()), tuple(r["after"].items()))
        for r in rows
    }
    assert len(keys) == len(rows) == 432
    totals = summarize(rows)
    assert totals["2977d152"]["lag_false_admit"] == 36
    assert totals["2977d152"]["vs_manual_tie"] == 192
    assert totals["deposit"]["vs_manual_loss"] == 8
    assert totals["check"]["manual_false_reject"] == totals["check"]["derived_false_reject"] == 6
