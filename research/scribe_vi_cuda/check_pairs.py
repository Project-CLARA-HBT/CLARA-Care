"""Verify the two recorded matrices against the same pinned FLEURS reference TSV."""

import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

EXPECTED_DEV = "c9bc17cede9765b1c75cb7a608f7066cb6bb6f8245cc75d721a5217a5dffb414"


def check(tsv, records):
    if hashlib.sha256(tsv.read_bytes()).hexdigest() != EXPECTED_DEV:
        raise ValueError("unexpected source transcript")
    expected = {}
    with tsv.open(encoding="utf8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            key = hashlib.sha256(row[1].encode()).hexdigest()[:16]
            text = unicodedata.normalize("NFC", row[3].casefold())
            expected[key] = int(row[0]), int(row[5]), len(re.findall(r"[^\W_]+", text))
    for path in records:
        entries = [json.loads(s) for s in path.read_text().splitlines()]
        observed = {r["key"]: (r["prompt"], r["samples"], r["ref"]) for r in entries}
        if expected != observed or len(entries) != 361:
            raise ValueError(f"incomplete or inconsistent development transcription file: {path}")
        for row in entries:
            for arm in ("greedy", "beam"):
                err, length = row[arm + "_errors"], row[arm + "_length"]
                if not (abs(row["ref"] - length) <= err <= max(row["ref"], length)):
                    raise ValueError("unattainable edit count")
    print(
        "Both models match all 361 published recording keys, prompt IDs, sample counts and token denominators."
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: check_pairs.py dev.tsv whisper.jsonl pho.jsonl")
    check(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]])
