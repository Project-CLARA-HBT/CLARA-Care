"""Development oracle for switching beams on insertion-dominated greedy clips."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def rows(name):
    return json.loads((root / name).read_text())["rows"]

data = rows("features.json")
audit = rows("large.json")
assert len(data) == len(audit) == 168
for row, counts in zip(data, audit, strict=True):
    assert all(row[k] == counts[k] for k in ("ordinal", "recording", "speaker", "ref_tokens"))

def loss(row, weight):
    scores = [a + weight * lm for a, lm in row["features"]]
    return row["errors_by_rank"][scores.index(max(scores))]

print("recording weight clips tuned_errors ceiling_saved")
for rec in sorted({r["recording"] for r in data}):
    fit = [r for r in data if r["recording"] != rec]
    held = [(r, c) for r, c in zip(data, audit) if r["recording"] == rec]
    assert {r["speaker"] for r in fit}.isdisjoint(r["speaker"] for r, _ in held)
    weight = min([0, .01, .03, .1, .3, 1, 3, 10], key=lambda w: sum(loss(r, w) for r in fit))
    eligible = [r for r, c in held if c.get("ins", 0) > c.get("sub", 0) + c.get("del", 0)]
    saved = sum(loss(r, weight) - min(r["errors_by_rank"]) for r in eligible)
    print(rec, weight, len(eligible), sum(loss(r, weight) for r, _ in held), saved)
