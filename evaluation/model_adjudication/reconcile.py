"""One optional anonymized reconciliation round; unresolved disagreement is retained."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.model_adjudication.run import _call, _sha


def reconcile(*, raw_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unresolved = 0
    total = 0
    for path in sorted(raw_dir.glob("*.json")):
        row: dict[str, Any] = json.loads(path.read_text())
        reviews = row["reviews"]
        total += 1
        if reviews[0]["review"]["label"] == reviews[1]["review"]["label"]:
            result = {"case_id": row["case_id"], "status": "AGREED", "reviews": reviews}
        else:
            revised = []
            for own, other in ((reviews[0], reviews[1]), (reviews[1], reviews[0])):
                prompt = (
                    "Reconsider exactly once. Return strict JSON {label,rationale,evidence_ids,confidence}. Other anonymous review:\n"
                    + json.dumps(
                        {
                            "label": other["review"]["label"],
                            "rationale": other["review"]["rationale"],
                        },
                        sort_keys=True,
                    )
                )
                revised.append(_call(model=own["model_id"], prompt=prompt))
            status = (
                "AGREED_AFTER_RECONCILIATION"
                if revised[0]["review"]["label"] == revised[1]["review"]["label"]
                else "UNRESOLVED"
            )
            unresolved += status == "UNRESOLVED"
            result = {
                "case_id": row["case_id"],
                "status": status,
                "initial_reviews": reviews,
                "revised_reviews": revised,
                "reconciliation_prompt_sha256": _sha(prompt),
            }
        (output_dir / path.name).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return {
        "case_count": total,
        "unresolved_count": unresolved,
        "unresolved_rate": unresolved / total if total else 0.0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile(raw_dir=args.raw_dir, output_dir=args.output_dir), sort_keys=True))
