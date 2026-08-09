from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.fullstack_benchmark.validate_metrics import COLUMNS as METRIC_COLUMNS
from evaluation.fullstack_benchmark.validate_metrics import validate as validate_metrics
from evaluation.governance_adversarial.validate_results import (
    validate as validate_adversarial,
)
from evaluation.human_review.validate_results import COLUMNS as HUMAN_COLUMNS
from evaluation.human_review.validate_results import validate as validate_human


def _json(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _csv(path: Path, columns: frozenset[str]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(columns))
        writer.writeheader()
        writer.writerow({column: "x" for column in columns})
    return path


def test_human_review_rejects_unattested_manifest(tmp_path: Path) -> None:
    manifest = _json(tmp_path / "human.json", {"status": "frozen"})
    results = _csv(tmp_path / "human.csv", HUMAN_COLUMNS)
    with pytest.raises(FreezeError, match="human_review_manifest_not_frozen"):
        validate_human(results, manifest)


def test_adversarial_rejects_incomplete_attack_suite(tmp_path: Path) -> None:
    manifest = _json(tmp_path / "adversarial.json", {
        "status": "frozen",
        "execution_mode": "isolated_real_application_boundary",
        "endpoint_manifest_sha256": "x",
        "environment_attestation": "operator-provided",
    })
    results = _csv(tmp_path / "adversarial.csv", {
        "attack_id", "scenario", "target_environment", "execution_id",
        "unauthorized_disclosure", "successful_bypass", "stale_commit",
        "wrong_subject_exposure", "cache_index_revocation_failure",
        "policy_decision_correct", "audit_trace_complete",
    })
    with pytest.raises(FreezeError, match="adversarial_scenarios_incomplete"):
        validate_adversarial(results, manifest)


def test_fullstack_rejects_incomplete_operation_suite(tmp_path: Path) -> None:
    manifest = _json(tmp_path / "fullstack.json", {
        "status": "frozen",
        "architecture_path": "postgresql>gst>glhs>thss>api",
        "hardware": "operator-provided",
        "worker_count": 1,
        "environment": "operator-provided",
    })
    results = _csv(tmp_path / "metrics.csv", METRIC_COLUMNS)
    with pytest.raises(FreezeError, match="fullstack_operations_incomplete"):
        validate_metrics(results, manifest)
