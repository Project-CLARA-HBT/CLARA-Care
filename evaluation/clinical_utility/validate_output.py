"""Validate raw downstream-utility output accounting before a headline seal."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from evaluation.clinical_utility.validate_manifest import CONDITIONS
from evaluation.clinical_utility.validate_manifest import (
    validate as validate_manifests,
)
from evaluation.evidence_program.freeze import FreezeError

REQUIRED_COLUMNS = frozenset({
    "task_id",
    "context_condition",
    "model_id",
    "model_family",
    "correct",
    "critical_omission",
    "unsupported_assertion",
    "conflict_handling",
    "evidence_fidelity",
    "authorized_disclosure",
    "prohibited_disclosure",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "provider_cost",
    "completion_status",
    "error_code",
})


def validate_output(
    output_path: Path,
    task_manifest: Path,
    model_manifest: Path,
    freeze_manifest: Path,
) -> None:
    validate_manifests(task_manifest, model_manifest, freeze_manifest)
    with output_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("utility_output_schema_incomplete")
        groups: dict[tuple[str, str], set[str]] = defaultdict(set)
        families: set[str] = set()
        for row in reader:
            task_id = row["task_id"].strip()
            model_id = row["model_id"].strip()
            condition = row["context_condition"].strip()
            family = row["model_family"].strip()
            if not task_id or not model_id or not family or condition not in CONDITIONS:
                raise FreezeError("utility_output_invalid_identity_or_condition")
            key = (task_id, model_id)
            if condition in groups[key]:
                raise FreezeError("utility_output_duplicate_task_model_condition")
            groups[key].add(condition)
            families.add(family)
    if not groups:
        raise FreezeError("utility_output_empty")
    if len(families) < 2:
        raise FreezeError("utility_output_two_model_families_required")
    incomplete = [f"{task}:{model}" for (task, model), values in groups.items() if values != CONDITIONS]
    if incomplete:
        raise FreezeError("utility_output_incomplete_condition_grid:" + ",".join(sorted(incomplete)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_output(args.output, args.tasks, args.models, args.freeze)
    except FreezeError as exc:
        parser.error(str(exc))
