"""Recompute registered endpoints directly from durable readbacks in an archive."""

import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

CUTS = (
    "clean",
    "producer_open",
    "decision_durable",
    "before_dispatch",
    "consumer_open",
    "sink_committed",
    "ack_durable",
)
PAYLOAD = "hotel-01/flight-02"


def verify(path):
    manifest = json.loads((path / "manifest.json").read_bytes())
    raw = (path / "histories.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["histories_sha256"]:
        raise ValueError("invalid history digest")
    arms = set(manifest["counts"])
    if arms not in ({"atomic", "journal"}, {"atomic", "journal", "confirmed"}):
        raise ValueError("unexpected arms")
    expected = set(itertools.product(arms, CUTS, range(3)))
    counts = {arm: Counter() for arm in arms}
    errors = []
    for line in raw.splitlines():
        row = json.loads(line)
        arm, cut, repetition = row["arm"], row["cut"], row["repetition"]
        expected.remove((arm, cut, repetition))
        op = f"booking-{repetition}-{cut}"
        before, after = row["before"], row["after"]
        applied_status = "APPLIED" if arm == "atomic" else "COMMITTED_EFFECT_APPLIED"
        premature = before["status"] == applied_status and before["orders"] != [[op, PAYLOAD]]
        readback = {
            "reservation": [[op, PAYLOAD]],
            "receipt": [[op, hashlib.sha256(PAYLOAD.encode()).hexdigest()]],
            "message": [[op, PAYLOAD, True]],
            "processed": [[op]],
            "orders": [[op, PAYLOAD]],
            "status": applied_status,
        }
        recovered = all(after[key] == value for key, value in readback.items())
        exit_expected = (0, "") if cut == "clean" else (-9, cut)
        failed = (row["first"]["code"], row["first"]["marker"]) != exit_expected or row["replay"][
            "code"
        ] != 0
        counts[arm].update(
            histories=1,
            execution_errors=int(failed),
            primary_losses=int(failed or not recovered),
            false_applied=int(premature),
        )
        if premature:
            errors.append((arm, cut, repetition))
    if expected or counts != manifest["counts"]:
        raise ValueError("incomplete grid or outcome mismatch")
    return {"arms": counts, "premature_claims": errors}


if __name__ == "__main__":
    for directory in sys.argv[1:]:
        print(directory, json.dumps(verify(Path(directory)), sort_keys=True))
