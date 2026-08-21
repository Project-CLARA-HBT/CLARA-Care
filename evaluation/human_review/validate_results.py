"""Validate clinician-collected burden data without deriving it from harness labels."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

COLUMNS = frozenset(
    {
        "case_id",
        "system",
        "reviewer_id",
        "escalated",
        "escalation_correct",
        "material_conflict_missed",
        "unnecessary_escalation",
        "review_seconds",
        "resolved",
        "reviewed_at",
    }
)


def validate(results: Path, manifest: Path) -> None:
    metadata = load_frozen_json(manifest)
    required = {"status", "human_attestation", "reviewer_ids", "qualifications", "blinding"}
    if required - metadata.keys() or metadata.get("status") != "frozen":
        raise FreezeError("human_review_manifest_not_frozen")
    if metadata.get("human_attestation") is not True or not metadata.get("reviewer_ids"):
        raise FreezeError("human_review_attestation_missing")
    with results.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("human_review_schema_incomplete")
        rows = list(reader)
    if not rows or any(row["reviewer_id"] not in metadata["reviewer_ids"] for row in rows):
        raise FreezeError("human_review_rows_missing_or_unrecognized")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.results, args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
