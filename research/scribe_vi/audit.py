"""Inspect the development manifest without emitting reference text."""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

with Path(sys.argv[1]).open(encoding="utf8") as handle:
    rows = list(csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE))

refs = defaultdict(set)
for prompt, _, _, reference, _, _, _ in rows:
    refs[prompt].add(reference)
result = {
    "clips": len(rows),
    "unique_filenames": len({r[1] for r in rows}),
    "unique_ids": len(refs),
    "ids_with_multiple_normalized_references": sum(len(v) > 1 for v in refs.values()),
    "gender_field": dict(Counter(r[6] for r in rows)),
    "minutes_at_16khz": sum(int(r[5]) for r in rows) / 960000,
}
for label, pattern in (("digit", r"\d"), ("negation_string", r"\b(?:không|chưa|chẳng)\b")):
    hits = [r for r in rows if re.search(pattern, r[3], re.IGNORECASE)]
    result[label] = {"clips": len(hits), "prompt_ids": len({r[0] for r in hits})}
print(json.dumps(result, indent=2))
