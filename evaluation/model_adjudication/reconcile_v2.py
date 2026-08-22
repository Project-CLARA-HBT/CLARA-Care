"""One reconciliation round; separate prompt hashes per reviewer and both revised response hashes."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.model_adjudication.run_v2 import RETRY_COUNT, _call, _sha

UrlOpen = Callable[..., Any]


def _reconcile_prompt(other_review: dict[str, Any]) -> str:
    return (
        "Reconsider exactly once. Return strict JSON "
        "{label,rationale,evidence_ids,confidence}. Other anonymous review:\n"
        + json.dumps(
            {"label": other_review["label"], "rationale": other_review["rationale"]}, sort_keys=True
        )
    )


def reconcile(
    *, raw_dir: Path, output_dir: Path, retries: int = RETRY_COUNT, urlopen: UrlOpen | None = None
) -> dict[str, Any]:
    """Exactly one reconciliation round; remaining disagreement stays UNRESOLVED."""
    output_dir.mkdir(parents=True, exist_ok=True)
    unresolved = 0
    total = 0
    for path in sorted(raw_dir.glob("*.json")):
        row: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        reviews = row["reviews"]
        total += 1
        case_id = row["case_id"]
        allowed_labels = tuple(row["allowed_labels"])
        evidence_ids = row["evidence_ids"]
        if reviews[0]["review"]["label"] == reviews[1]["review"]["label"]:
            result: dict[str, Any] = {"case_id": case_id, "status": "AGREED", "reviews": reviews}
        else:
            prompts: dict[str, str] = {}
            revised_by_reviewer: dict[str, dict[str, Any]] = {}
            for reviewer_id, own, other in (
                ("reviewer_a", reviews[0], reviews[1]),
                ("reviewer_b", reviews[1], reviews[0]),
            ):
                prompt = _reconcile_prompt(other["review"])
                prompts[reviewer_id] = _sha(prompt)
                revised = _call(
                    model=own["model_id"],
                    prompt=prompt,
                    allowed_labels=allowed_labels,
                    available_evidence_ids=evidence_ids,
                    retries=retries,
                    urlopen=urlopen,
                )
                revised["reviewer_id"] = reviewer_id
                revised_by_reviewer[reviewer_id] = revised
            revised_reviews = [revised_by_reviewer["reviewer_a"], revised_by_reviewer["reviewer_b"]]
            status = (
                "AGREED_AFTER_RECONCILIATION"
                if revised_reviews[0]["review"]["label"] == revised_reviews[1]["review"]["label"]
                else "UNRESOLVED"
            )
            if status == "UNRESOLVED":
                unresolved += 1
            result = {
                "case_id": case_id,
                "status": status,
                "initial_reviews": reviews,
                "revised_reviews": revised_reviews,
                "reconciliation_prompts": prompts,
                "revised_response_hashes": {
                    "reviewer_a": revised_reviews[0]["provider"]["parsed_review_sha256"],
                    "reviewer_b": revised_reviews[1]["provider"]["parsed_review_sha256"],
                },
            }
        if row.get("frozen_duplicate"):
            result["frozen_duplicate"] = True
            result["duplicate_of"] = row["duplicate_of"]
        (output_dir / path.name).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return {
        "schema_version": "clara-model-reconcile.v2",
        "reconciliation_rounds": 1,
        "case_count": total,
        "unresolved_count": unresolved,
        "unresolved_rate": unresolved / total if total else 0.0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", "--run-dir", dest="raw_dir", type=Path, required=True)
    parser.add_argument("--output-dir", "--output", dest="output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None, help="Optional manifest path")
    parser.add_argument("--retries", type=int, default=RETRY_COUNT)
    args = parser.parse_args()

    raw_dir = args.raw_dir / "raw" if (args.raw_dir / "raw").is_dir() else args.raw_dir
    if args.output.suffix == ".json":
        output_dir = args.output.parent / args.output.stem
        output_file = args.output
    else:
        output_dir = args.output
        output_file = None

    summary = reconcile(raw_dir=raw_dir, output_dir=output_dir, retries=args.retries)
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, sort_keys=True))
