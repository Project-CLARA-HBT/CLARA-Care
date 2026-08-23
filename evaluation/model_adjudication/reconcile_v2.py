"""One reconciliation round; separate prompt hashes per reviewer and both revised response hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.model_adjudication.run_v2 import (
    RETRY_COUNT,
    _atomic_promote_dir,
    _call,
    _sha,
    _write_atomic_file,
)

UrlOpen = Callable[..., Any]


def _reconcile_prompt(other_review: dict[str, Any]) -> str:
    return (
        "Reconsider exactly once. Return strict JSON "
        "{label,rationale,evidence_ids,confidence}. Other anonymous review:\n"
        + json.dumps(
            {"label": other_review["label"], "rationale": other_review["rationale"]}, sort_keys=True
        )
    )


def _load_run_manifest(manifest_path: Path, raw_dir: Path) -> tuple[dict[str, Any], list[Path]]:
    """Validate a run manifest schema and return valid listed case paths (EVAL-MAN-01)."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("model_review_manifest_malformed") from exc

    if not isinstance(manifest, dict):
        raise TypeError("model_review_manifest_not_object")

    if manifest.get("schema_version") != "clara-model-review-run.v2":
        raise ValueError("model_review_manifest_schema_version_unsupported")

    if manifest.get("status") != "independent_reviews_complete":
        raise ValueError(f"model_review_manifest_not_terminal:{manifest.get('status')}")

    case_paths: list[Path] = []
    if "raw_inventory" in manifest:
        inventory = manifest["raw_inventory"]
        if not isinstance(inventory, list):
            raise TypeError("model_review_manifest_inventory_invalid")
        for item in inventory:
            if not isinstance(item, dict):
                raise TypeError("model_review_manifest_inventory_item_invalid")
            case_id = item.get("case_id")
            path_str = item.get("path")
            expected_sha = item.get("sha256")
            terminal_state = item.get("terminal_state")

            if terminal_state != "completed":
                raise ValueError(f"model_review_manifest_case_not_terminal:{case_id}")

            if not path_str or not isinstance(path_str, str):
                raise ValueError(f"model_review_manifest_path_invalid:{case_id}")

            # Resolve file path
            candidate_paths = [
                manifest_path.parent / path_str,
                raw_dir / Path(path_str).name,
                raw_dir / path_str,
            ]
            case_file: Path | None = next((p for p in candidate_paths if p.is_file()), None)
            if case_file is None:
                raise ValueError(f"model_review_manifest_file_missing:{path_str}")

            if expected_sha:
                actual_sha = hashlib.sha256(case_file.read_bytes()).hexdigest()
                if actual_sha != expected_sha:
                    raise ValueError(f"model_review_manifest_sha_mismatch:{case_id}")

            case_paths.append(case_file)
    elif "raw_outputs" in manifest:
        outputs = manifest["raw_outputs"]
        if not isinstance(outputs, list):
            raise TypeError("model_review_manifest_outputs_invalid")
        for path_str in outputs:
            if not path_str or not isinstance(path_str, str):
                raise ValueError("model_review_manifest_path_invalid")
            candidate_paths = [
                manifest_path.parent / path_str,
                raw_dir / Path(path_str).name,
                raw_dir / path_str,
            ]
            case_file = next((p for p in candidate_paths if p.is_file()), None)
            if case_file is None:
                raise ValueError(f"model_review_manifest_file_missing:{path_str}")
            case_paths.append(case_file)
    else:
        raise ValueError("model_review_manifest_inventory_missing")

    return manifest, case_paths


def reconcile(
    *,
    raw_dir: Path,
    output_dir: Path,
    manifest_path: Path | None = None,
    retries: int = RETRY_COUNT,
    urlopen: UrlOpen | None = None,
) -> dict[str, Any]:
    """Exactly one reconciliation round; remaining disagreement stays UNRESOLVED."""
    # Discover or validate run manifest if available
    resolved_manifest_path = manifest_path
    if resolved_manifest_path is None:
        for candidate in (
            raw_dir / "model_review_results.json",
            raw_dir.parent / "model_review_results.json",
        ):
            if candidate.is_file():
                resolved_manifest_path = candidate
                break

    if resolved_manifest_path is not None and resolved_manifest_path.is_file():
        _, case_paths = _load_run_manifest(resolved_manifest_path, raw_dir)
    else:
        # If no manifest found, enumerate only valid case JSON files (ignoring non-case files)
        case_paths = []
        for path in sorted(raw_dir.glob("*.json")):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(row, dict) and "case_id" in row and "reviews" in row:
                    case_paths.append(path)
            except Exception:
                continue

    staging_dir = output_dir.parent / f"{output_dir.name}.staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    journal_path = staging_dir / "journal.jsonl"
    journal_records: dict[str, dict[str, Any]] = {}
    if journal_path.exists():
        try:
            for line in journal_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    if isinstance(item, dict) and "case_id" in item and "result" in item:
                        journal_records[item["case_id"]] = item["result"]
        except Exception:
            journal_records = {}

    unresolved = 0
    total = 0
    records: list[dict[str, Any]] = []

    for path in sorted(case_paths):
        row = json.loads(path.read_text(encoding="utf-8"))
        case_id = row["case_id"]
        total += 1
        reconciled_file = staging_dir / f"{case_id}.json"

        # Check if already reconciled in journal and present on disk
        if case_id in journal_records and reconciled_file.exists():
            result = journal_records[case_id]
            if result.get("status") == "UNRESOLVED":
                unresolved += 1
            records.append(result)
            continue

        reviews = row["reviews"]
        allowed_labels = tuple(row["allowed_labels"])
        evidence_ids = row["evidence_ids"]

        if reviews[0]["review"]["label"] == reviews[1]["review"]["label"]:
            result = {"case_id": case_id, "status": "AGREED", "reviews": reviews}
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
            revised_reviews = [
                revised_by_reviewer["reviewer_a"],
                revised_by_reviewer["reviewer_b"],
            ]
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

        _write_atomic_file(
            reconciled_file, json.dumps(result, indent=2, sort_keys=True) + "\n"
        )

        journal_entry = (
            json.dumps({"case_id": case_id, "result": result}, sort_keys=True) + "\n"
        )
        with open(journal_path, "a", encoding="utf-8") as jf:
            jf.write(journal_entry)
            jf.flush()
            os.fsync(jf.fileno())

        records.append(result)

    summary = {
        "schema_version": "clara-model-reconcile.v2",
        "reconciliation_rounds": 1,
        "case_count": total,
        "unresolved_count": unresolved,
        "unresolved_rate": unresolved / total if total else 0.0,
    }

    _write_atomic_file(
        staging_dir / "reconcile_summary.json",
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )

    # Atomically promote staging_dir to output_dir
    _atomic_promote_dir(staging_dir, output_dir)

    return summary


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

    summary = reconcile(
        raw_dir=raw_dir,
        output_dir=output_dir,
        manifest_path=args.manifest,
        retries=args.retries,
    )
    if output_file is not None:
        _write_atomic_file(
            output_file, json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
    print(json.dumps(summary, sort_keys=True))
