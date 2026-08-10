"""Compute transparent inter-rater agreement from independent human label rows.

This code only aggregates labels supplied by qualified humans. It neither creates
labels nor infers reviewer identity, qualification, or independence.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.clinical_adjudication.validate_manifest import (
    validate as validate_annotation,
)
from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

REQUIRED_LABEL_COLUMNS = frozenset({"case_id", "annotator_id", "field", "label"})


def _cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    observed = sum(left == right for left, right in pairs) / len(pairs)
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    expected = sum(
        (left_counts[label] / len(pairs)) * (right_counts[label] / len(pairs))
        for label in set(left_counts).union(right_counts)
    )
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def analyze(labels_path: Path, annotation_manifest_path: Path) -> dict[str, object]:
    validate_annotation(annotation_manifest_path)
    manifest = load_frozen_json(annotation_manifest_path)
    annotators = tuple(manifest["annotator_ids"])
    if len(annotators) != 2:
        raise FreezeError("cohen_kappa_requires_exactly_two_annotators")
    with labels_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not REQUIRED_LABEL_COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("invalid_label_csv_schema")
        rows = list(reader)
    indexed: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        case_id, annotator_id, field, label = (
            row["case_id"].strip(),
            row["annotator_id"].strip(),
            row["field"].strip(),
            row["label"].strip(),
        )
        if not case_id or not field or not label or annotator_id not in annotators:
            raise FreezeError("invalid_or_unexpected_label_row")
        key = (case_id, field)
        if annotator_id in indexed[key]:
            raise FreezeError("duplicate_annotator_label")
        indexed[key][annotator_id] = label

    per_field: dict[str, list[tuple[str, str]]] = defaultdict(list)
    incomplete = 0
    for (_case_id, field), labels in indexed.items():
        if set(labels) == set(annotators):
            per_field[field].append((labels[annotators[0]], labels[annotators[1]]))
        else:
            incomplete += 1
    fields: dict[str, object] = {}
    for field, pairs in sorted(per_field.items()):
        agreements = sum(left == right for left, right in pairs)
        fields[field] = {
            "paired_cases": len(pairs),
            "agreements": agreements,
            "disagreements": len(pairs) - agreements,
            "disagreement_rate": (len(pairs) - agreements) / len(pairs) if pairs else None,
            "cohen_kappa": _cohen_kappa(pairs),
        }
    return {
        "status": "human_labels_aggregated_not_clinical_claim",
        "annotator_count": 2,
        "fields": fields,
        "incomplete_case_fields": incomplete,
        "krippendorff_alpha": "not_computed; two-annotator Cohen kappa reported per field",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--annotation-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.labels, args.annotation_manifest)
    except FreezeError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
