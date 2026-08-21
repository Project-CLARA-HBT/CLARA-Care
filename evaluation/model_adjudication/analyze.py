"""Agreement analysis for blinded dual-model reviews; cases, not calls, are units."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def analyze(raw_dir: Path) -> dict[str, Any]:
    rows = [json.loads(path.read_text()) for path in sorted(raw_dir.glob("*.json"))]
    pairs = [
        (row["reviews"][0]["review"]["label"], row["reviews"][1]["review"]["label"]) for row in rows
    ]
    labels = sorted({item for pair in pairs for item in pair})
    observed = sum(a == b for a, b in pairs) / len(pairs) if pairs else 0.0
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = (
        sum((left[label] / len(pairs)) * (right[label] / len(pairs)) for label in labels)
        if pairs
        else 0.0
    )
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    return {
        "case_count": len(pairs),
        "pre_reconciliation_agreement": observed,
        "cohens_kappa": kappa,
        "unresolved_rate": None,
        "unit_of_analysis": "case; model calls and retries are not independent units",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(analyze(args.raw_dir), indent=2, sort_keys=True) + "\n")
    print(args.output)
