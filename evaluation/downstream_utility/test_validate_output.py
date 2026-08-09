from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluation.downstream_utility.validate_output import (
    REQUIRED_COLUMNS,
    validate_output,
)
from evaluation.evidence_program.freeze import FreezeError


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _manifests(tmp_path: Path) -> tuple[Path, Path, Path]:
    freeze = tmp_path / "freeze.json"
    tasks = tmp_path / "tasks.json"
    models = tmp_path / "models.json"
    _write_json(freeze, {
        "status": "frozen", "independent_curator_attestation": True,
        "protocol_version": "v1", "freeze_id": "f", "frozen_at": "t", "code_revision": "sha",
        "cohort_manifest_sha256": "x", "annotation_guide_sha256": "x",
        "domain_policy_manifest_sha256": "x", "comparator_version": "x",
        "task_manifest_sha256": "x", "model_manifest_sha256": "x", "statistics_plan_sha256": "x",
    })
    _write_json(tasks, {
        "status": "frozen",
        "conditions": ["full_authorized", "naive_rag", "btsa_or_tpr", "glhs_no_thss", "thss_default", "thss_strict"],
    })
    _write_json(models, {"status": "frozen", "models": [{"family": "family-a"}, {"family": "family-b"}]})
    return tasks, models, freeze


def test_utility_output_rejects_incomplete_context_grid(tmp_path: Path) -> None:
    tasks, models, freeze = _manifests(tmp_path)
    output = tmp_path / "utility.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerow({name: "x" for name in REQUIRED_COLUMNS} | {
            "task_id": "task-1", "model_id": "m1", "model_family": "family-a",
            "context_condition": "thss_default",
        })
    with pytest.raises(FreezeError, match="utility_output_two_model_families_required"):
        validate_output(output, tasks, models, freeze)
