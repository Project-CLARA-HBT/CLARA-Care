from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from evaluation.contention_analysis.run_postgresql import (
    ATTEMPT_FIELDS,
    CONCURRENCY_LEVELS,
    IMPLEMENTATION_FILES,
    SUMMARY_FIELDS,
    WORKLOADS,
    _summaries,
)
from evaluation.contention_analysis.strategy_model import (
    STRATEGIES,
    evaluate,
    matrix,
    proposals,
)
from evaluation.contention_analysis.validate import validate
from evaluation.evidence_program.freeze import FreezeError


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(root: Path, repetitions: int = 3) -> None:
    attempts: list[dict[str, object]] = []
    for workload in WORKLOADS:
        for concurrency in CONCURRENCY_LEVELS:
            for batch in range(repetitions):
                for writer in range(concurrency):
                    accepted = writer == 0
                    attempts.append(
                        {
                            "workload": workload,
                            "concurrency": concurrency,
                            "batch": batch,
                            "writer": writer,
                            "result": "accepted" if accepted else "rejected",
                            "reason_code": "accepted" if accepted else "stale_state_version",
                            "stale_class": (
                                "none"
                                if accepted
                                else "true_stale"
                                if workload == "same_dependency"
                                else "false_stale"
                            ),
                            "latency_ms": float(writer + 1),
                            "batch_wall_ms": float(concurrency + 1),
                            "batch_db_reads": concurrency * 2,
                            "batch_db_writes": 4,
                        }
                    )
    attempts_path = root / "attempts.csv"
    summary_path = root / "summary.csv"
    strategy_model_path = root / "strategy_model.json"
    manifest_path = root / "manifest.json"
    _write_csv(attempts_path, ATTEMPT_FIELDS, attempts)
    _write_csv(summary_path, SUMMARY_FIELDS, _summaries(attempts, repetitions=repetitions))
    strategy_model_path.write_text(
        json.dumps(
            {
                "schema_version": "glhs-version-strategy-model.v1",
                "status": "DETERMINISTIC_MECHANISM_MODEL_NOT_PRODUCTION_EXECUTION",
                "latency_measured": False,
                "strategies": list(STRATEGIES),
                "rows": matrix(WORKLOADS, CONCURRENCY_LEVELS),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "glhs-contention-analysis.v1",
                "status": "EXECUTED_PARTIAL_PRODUCTION_STRATEGY",
                "implementation": {
                    "implementation_sha": "a" * 40,
                    "tracked_worktree_clean": True,
                    "implementation_paths_tracked": True,
                    "files_sha256": {path: "c" * 64 for path in IMPLEMENTATION_FILES},
                },
                "experimental_unit": "independently_seeded_profile_race_batch",
                "observational_unit": "writer_attempt",
                "aggregation": "workload_by_concurrency_level",
                "false_stale_definition": "fixture",
                "dependency_operationalization": "assertion_semantic_key",
                "inference": "descriptive_no_hypothesis_test",
                "missing_output_policy": "missing_or_unclassified_attempt_is_failure",
                "strategy": "production_profile_global_version",
                "workloads": list(WORKLOADS),
                "concurrency_levels": list(CONCURRENCY_LEVELS),
                "repetitions": repetitions,
                "retry_policy": "no_retry_in_primary_race",
                "coverage_gaps": [
                    "alternative_strategy_postgresql_performance",
                    "consent_or_policy_change_workload",
                    "mixed_read_snapshot_write_workload",
                    "retry_success_study",
                ],
                "fixture_contains_phi": False,
                "external_calls": 0,
                "environment": {
                    "database": "postgresql",
                    "database_image_digest": "sha256:" + "b" * 64,
                    "alembic_revision": "20260811_0055",
                    "database_size_bytes": 1024,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths = (attempts_path, summary_path, strategy_model_path, manifest_path)
    (root / "checksums.sha256").write_text(
        "\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
            for path in paths
        )
        + "\n",
        encoding="utf-8",
    )


def test_contention_artifact_validates_and_detects_tamper(tmp_path: Path) -> None:
    _fixture(tmp_path)
    assert validate(tmp_path)["external_calls"] == 0

    manifest = tmp_path / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="contention_checksum_mismatch:manifest.json"):
        validate(tmp_path)


def test_contention_artifact_rejects_missing_attempt(tmp_path: Path) -> None:
    _fixture(tmp_path)
    attempts = tmp_path / "attempts.csv"
    lines = attempts.read_text(encoding="utf-8").splitlines()
    attempts.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="contention_attempt_grid_incomplete"):
        validate(tmp_path)


def test_strategy_model_isolates_version_granularity_without_latency_claim() -> None:
    unrelated = proposals("unrelated_slots", 8)
    assert evaluate("profile_global", unrelated) == {
        "attempts": 8,
        "accepted": 1,
        "true_stale": 0,
        "false_stale": 7,
    }
    assert evaluate("resource_partition", unrelated)["accepted"] == 8
    assert evaluate("dependency_hybrid", unrelated)["accepted"] == 8

    shared = proposals("same_dependency", 8)
    for strategy in STRATEGIES:
        assert evaluate(strategy, shared)["true_stale"] == 7
