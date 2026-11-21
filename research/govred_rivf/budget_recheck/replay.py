"""Replay completed pytest invocations from the immutable W8 freeze."""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

SEALED = "c59768dced443bb9cde6ba78762b728522cc9f581e30556b008f4b054e7cb6ce"
METHODS = ("M0_regression", "M1_stateless_property", "M2_state_machine", "M3_combined")
PORTFOLIO = "regression_then_alternate"


def extract(source):
    blob = (source / "seal/govmut-soict-2026-final_run-v2").read_bytes()
    if hashlib.sha256(blob).hexdigest() != SEALED:
        raise ValueError("W8 checksum mismatch")
    w8 = json.loads(blob, parse_float=Decimal)
    freeze = (source / "final_freeze.json").read_bytes()
    if hashlib.sha256(freeze).hexdigest() != w8["manifest_sha256"]:
        raise ValueError("invalid freeze")
    frozen = json.loads(freeze)
    plans = frozen["methods"]
    seeds = frozen["hypothesis"]["ordered_seeds"]
    calibration = json.loads((source / "budget_calibration.json").read_bytes())
    assert calibration["ordered_seeds"] == seeds
    assert calibration["budget_seconds"] == 233 and calibration["status"] == "completed"
    assert plans[METHODS[3]]["targets"] == sum((plans[m]["targets"] for m in METHODS[:3]), [])
    revisions = Counter()
    mutant_hashes = defaultdict(set)
    rows = {}
    slots = {m: [(m, s) for s in ([None] if i == 0 else seeds)] for i, m in enumerate(METHODS)}
    for entry in w8["executions"]:
        result = entry["result"]
        method = entry["method"]
        seed = entry["hypothesis_seed"]
        assert result["hypothesis_seed"] == seed
        revisions[result["repository_revision"]] += 1
        mutant_hashes[result["mutant_id"]].add(
            (result["original_sha256"], result["mutated_sha256"])
        )
        for field, pinned in (
            ("pytest_targets", "targets"),
            ("pytest_target_sha256", "target_sha256"),
        ):
            assert result[field] == plans[method][pinned]
        for stream in ("stdout", "stderr"):
            assert hashlib.sha256(result[stream].encode()).hexdigest() == result[stream + "_sha256"]
        killed = result["classification"] == "KILLED_TEST_ASSERTION"
        assert (killed and result["returncode"] == 1 and " failed" in result["stdout"]) or (
            result["classification"] == "SURVIVED" and result["returncode"] == 0
        )
        us = result["runtime_ms"] * 1000
        assert us == int(us) and us > 0
        key = result["mutant_id"], method, seed
        assert key not in rows
        rows[key] = int(us), killed
    ids = w8["included_mutant_ids"]
    assert len(set(ids)) == len(ids) == 45
    assert set(rows) == {(i, *slot) for i in ids for runs in slots.values() for slot in runs}
    slots[PORTFOLIO] = slots[METHODS[0]] + [(m, s) for s in seeds for m in METHODS[1:3]]
    assert all(len(hashes) == 1 for hashes in mutant_hashes.values())
    return rows, ids, slots, calibration["budget_seconds"] * 1_000_000, revisions


def observe(schedule, budget):
    used = 0
    for index, (cost, killed) in enumerate(schedule, 1):
        used += cost
        if used > budget:
            return budget, index - 1, 0, "capped"
        if killed:
            return used, index, 1, "detected"
    return used, len(schedule), 0, "exhausted"


def replay(source, dest):
    rows, ids, plans, cap, revisions = extract(source)
    dest.mkdir()
    (dest / "revision_counts.json").write_text(
        json.dumps(revisions, indent=2, sort_keys=True) + "\n"
    )
    with (dest / "mutants.csv").open("w") as f, (dest / "summary.csv").open("w") as sf:
        writer = csv.writer(f, lineterminator="\n")
        summary = csv.writer(sf, lineterminator="\n")
        writer.writerow(
            ["budget_us", "mutant", "method", "charged_us", "completed", "detected", "exit"]
        )
        summary.writerow(
            ["budget_us", "method", "kills", "capped", "charged_us", "m3_only", "other_only"]
        )
        for b in (cap // 8, cap // 4, cap // 2, cap):
            detected, cost, capped = defaultdict(set), defaultdict(int), defaultdict(int)
            for i in ids:
                for method, plan in plans.items():
                    used, n, positive, status = observe([rows[i, *slot] for slot in plan], b)
                    writer.writerow([b, i, method, used, n, positive, status])
                    if positive:
                        detected[method].add(i)
                    cost[method] += used
                    capped[method] += status == "capped"
            for method in plans:
                a, c = detected[METHODS[3]], detected[method]
                summary.writerow(
                    [b, method, len(c), capped[method], cost[method], len(a - c), len(c - a)]
                )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    replay(args.source, args.out)
