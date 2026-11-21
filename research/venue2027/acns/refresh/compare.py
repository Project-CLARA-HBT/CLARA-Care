"""Compare catalogue states by key and count logical row writes."""

import argparse
import hashlib
import json
from pathlib import Path

WATERMARK = "2026-11-01"


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def project(row):
    return {"title": row[1], "year": row[2]}


def assess(old, new, oracle):
    initial = {key: project(row) for key, row in old.items()}
    added = new.keys() - old.keys()
    removed = old.keys() - new.keys()
    common = old.keys() & new.keys()
    edited = {key for key in common if old[key][1:] != new[key][1:]}
    dates_changed = {key for key in common if old[key][0] != new[key][0]}
    cohorts = {
        "old": len(old),
        "new": len(new),
        "added": len(added),
        "removed": len(removed),
        "retained": len(common),
        "retained_projected_edits": len(edited),
        "retained_date_changes": len(dates_changed),
        "edits_with_same_date": len(edited - dates_changed),
    }
    arms = {}
    for arm in ("frozen", "key_reconcile", "watermark", "date_equality", "exact_diff", "rebuild"):
        state = {} if arm == "rebuild" else initial.copy()
        writes = comparisons = 0
        if arm not in {"frozen", "rebuild"}:
            for key in removed:
                del state[key]
            writes += len(removed)
        for key, row in new.items():
            if arm == "frozen":
                break
            if key in state:
                if arm == "key_reconcile":
                    continue
                date = row[0]
                if arm == "watermark" and date and date < WATERMARK:
                    continue
                if arm == "date_equality" and date and date == old[key][0]:
                    continue
                comparisons += 1
                if project(row) == state[key]:
                    continue
            state[key] = project(row)
            writes += 1
        arms[arm] = {
            "missing": len(oracle.keys() - state.keys()),
            "extra": len(state.keys() - oracle.keys()),
            "wrong_value": sum(state[k] != oracle[k] for k in oracle.keys() & state.keys()),
            "row_writes": writes,
            "retained_payload_comparisons": comparisons,
            "catalogue_sha256": digest(state),
        }
    reference = digest(oracle)
    if arms["rebuild"]["catalogue_sha256"] != reference:
        raise ValueError("Extractor and independent oracle disagree")
    if arms["exact_diff"]["catalogue_sha256"] != reference:
        raise ValueError("Exact refresh failed")
    return {"scope": cohorts, "arms": arms, "oracle_sha256": reference}


def delta(old, new):
    return {
        "old_sha256": digest(old),
        "new_sha256": digest(new),
        "remove": sorted(old.keys() - new.keys()),
        "upsert": {key: row for key, row in new.items() if row != old.get(key)},
    }


def replay(old, patch):
    if digest(old) != patch["old_sha256"]:
        raise ValueError("Unexpected starting snapshot projection")
    new = old.copy()
    for key in patch["remove"]:
        del new[key]
    new.update(patch["upsert"])
    if digest(new) != patch["new_sha256"]:
        raise ValueError("Replayed projection differs")
    return new


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("delta", type=Path)
    args = parser.parse_args()
    old, new = read(args.old), read(args.new)
    report = assess(old, new, read(args.oracle))
    patch = delta(old, new)
    if replay(old, patch) != new:
        raise ValueError("Patch does not reproduce later input")
    write(args.report, report)
    write(args.delta, patch)
