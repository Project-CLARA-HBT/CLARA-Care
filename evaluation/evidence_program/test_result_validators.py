from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.fullstack_benchmark.validate_metrics import COLUMNS as METRIC_COLUMNS
from evaluation.fullstack_benchmark.validate_metrics import (
    REQUIRED_OPERATION_ORDER,
)
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
    with pytest.raises(FreezeError, match="govred_manifest_missing"):
        validate_adversarial(results, manifest)


def test_fullstack_rejects_incomplete_operation_suite(tmp_path: Path) -> None:
    manifest = _json(tmp_path / "fullstack.json", {
        "schema_version": "glhs-fullstack-service-layer.v2",
        "status": "EXECUTED_PARTIAL_SERVICE_LAYER",
        "architecture_path": "postgresql>gst>glhs>thss>api",
        "hardware": {"cpu_count": 1},
        "worker_count": 1,
        "fixture_contains_phi": False,
        "production_services_modified": False,
        "http_transport_measured": False,
        "environment": {
            "database": "postgresql",
            "server_version": "16",
            "alembic_revision": "20260811_0055",
            "database_image_digest": "sha256:" + "b" * 64,
        },
        "implementation": {
            "implementation_sha": "a" * 40,
            "tracked_worktree_clean": True,
        },
        "operations": list(REQUIRED_OPERATION_ORDER),
        "coverage_gaps": [
            "http_transport",
            "source_revocation_propagation",
            "concurrent_transition",
        ],
        "row_counts": {},
    })
    results = _csv(tmp_path / "metrics.csv", METRIC_COLUMNS)
    with pytest.raises(FreezeError, match="fullstack_operations_incomplete"):
        validate_metrics(results, manifest)
