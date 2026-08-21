"""Fail-closed validation for PostgreSQL GLHS contention artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

from evaluation.contention_analysis.run_postgresql import (
    ATTEMPT_FIELDS,
    CONCURRENCY_LEVELS,
    IMPLEMENTATION_FILES,
    SUMMARY_FIELDS,
    WORKLOADS,
)
from evaluation.contention_analysis.strategy_model import STRATEGIES, matrix
from evaluation.evidence_program.freeze import FreezeError, load_frozen_json
from evaluation.fullstack_benchmark.run_postgresql import percentile

EXPECTED_GAPS = {
    "alternative_strategy_postgresql_performance",
    "consent_or_policy_change_workload",
    "mixed_read_snapshot_write_workload",
    "retry_success_study",
}


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(fields):
            raise FreezeError(f"contention_csv_schema_invalid:{path.name}")
        return list(reader)


def _integer(row: dict[str, str], field: str) -> int:
    try:
        value = int(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise FreezeError(f"contention_integer_invalid:{field}") from exc
    if value < 0:
        raise FreezeError(f"contention_integer_negative:{field}")
    return value


def _number(row: dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise FreezeError(f"contention_number_invalid:{field}") from exc
    if not math.isfinite(value) or value < 0:
        raise FreezeError(f"contention_number_nonfinite_or_negative:{field}")
    return value


def _validate_checksums(root: Path, paths: tuple[Path, ...]) -> None:
    inventory = root / "checksums.sha256"
    if not inventory.is_file():
        raise FreezeError("contention_checksum_inventory_missing")
    declared: dict[str, str] = {}
    for line in inventory.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] in declared:
            raise FreezeError("contention_checksum_inventory_invalid")
        declared[parts[1]] = parts[0]
    if set(declared) != {path.name for path in paths}:
        raise FreezeError("contention_checksum_file_set_invalid")
    for path in paths:
        if declared[path.name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise FreezeError(f"contention_checksum_mismatch:{path.name}")


def validate(root: Path) -> dict[str, object]:
    attempts_path = root / "attempts.csv"
    summary_path = root / "summary.csv"
    strategy_model_path = root / "strategy_model.json"
    manifest_path = root / "manifest.json"
    if not all(
        path.is_file() for path in (attempts_path, summary_path, strategy_model_path, manifest_path)
    ):
        raise FreezeError("contention_artifact_incomplete")
    manifest = load_frozen_json(manifest_path)
    if (
        manifest.get("schema_version") != "glhs-contention-analysis.v1"
        or manifest.get("status") != "EXECUTED_PARTIAL_PRODUCTION_STRATEGY"
        or manifest.get("strategy") != "production_profile_global_version"
        or manifest.get("workloads") != list(WORKLOADS)
        or manifest.get("concurrency_levels") != list(CONCURRENCY_LEVELS)
        or manifest.get("external_calls") != 0
        or manifest.get("fixture_contains_phi") is not False
        or manifest.get("inference") != "descriptive_no_hypothesis_test"
        or manifest.get("dependency_operationalization") != "assertion_semantic_key"
        or manifest.get("experimental_unit") != "independently_seeded_profile_race_batch"
        or manifest.get("observational_unit") != "writer_attempt"
        or manifest.get("aggregation") != "workload_by_concurrency_level"
        or manifest.get("missing_output_policy") != "missing_or_unclassified_attempt_is_failure"
        or manifest.get("retry_policy") != "no_retry_in_primary_race"
    ):
        raise FreezeError("contention_manifest_contract_invalid")
    repetitions = manifest.get("repetitions")
    if not isinstance(repetitions, int) or repetitions < 3:
        raise FreezeError("contention_repetitions_invalid")
    coverage_gaps = manifest.get("coverage_gaps")
    if not isinstance(coverage_gaps, list) or set(coverage_gaps) != EXPECTED_GAPS:
        raise FreezeError("contention_coverage_gaps_invalid")
    implementation = manifest.get("implementation")
    environment = manifest.get("environment")
    if (
        not isinstance(implementation, dict)
        or re.fullmatch(r"[0-9a-f]{40}", str(implementation.get("implementation_sha", ""))) is None
        or not isinstance(implementation.get("tracked_worktree_clean"), bool)
        or not isinstance(implementation.get("implementation_paths_tracked"), bool)
        or not isinstance(implementation.get("files_sha256"), dict)
        or set(implementation["files_sha256"]) != set(IMPLEMENTATION_FILES)
        or any(
            re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
            for value in implementation["files_sha256"].values()
        )
        or not isinstance(environment, dict)
        or environment.get("database") != "postgresql"
        or environment.get("alembic_revision") != "20260811_0055"
        or re.fullmatch(r"sha256:[0-9a-f]{64}", str(environment.get("database_image_digest", "")))
        is None
        or not isinstance(environment.get("database_size_bytes"), int)
    ):
        raise FreezeError("contention_environment_attestation_invalid")

    strategy_model = load_frozen_json(strategy_model_path)
    if (
        strategy_model.get("schema_version") != "glhs-version-strategy-model.v1"
        or strategy_model.get("status") != "DETERMINISTIC_MECHANISM_MODEL_NOT_PRODUCTION_EXECUTION"
        or strategy_model.get("latency_measured") is not False
        or strategy_model.get("strategies") != list(STRATEGIES)
        or strategy_model.get("rows") != matrix(WORKLOADS, CONCURRENCY_LEVELS)
    ):
        raise FreezeError("contention_strategy_model_invalid")

    attempts = _read_csv(attempts_path, ATTEMPT_FIELDS)
    summaries = _read_csv(summary_path, SUMMARY_FIELDS)
    expected_attempt_count = repetitions * len(WORKLOADS) * sum(CONCURRENCY_LEVELS)
    if len(attempts) != expected_attempt_count:
        raise FreezeError("contention_attempt_grid_incomplete")
    observed_keys: set[tuple[str, int, int, int]] = set()
    for row in attempts:
        workload = row["workload"]
        concurrency = _integer(row, "concurrency")
        batch = _integer(row, "batch")
        writer = _integer(row, "writer")
        key = (workload, concurrency, batch, writer)
        if (
            key in observed_keys
            or workload not in WORKLOADS
            or concurrency not in CONCURRENCY_LEVELS
            or batch >= repetitions
            or writer >= concurrency
        ):
            raise FreezeError("contention_attempt_grid_invalid")
        observed_keys.add(key)
        if _number(row, "latency_ms") <= 0 or _number(row, "batch_wall_ms") <= 0:
            raise FreezeError("contention_latency_invalid")
        _integer(row, "batch_db_reads")
        _integer(row, "batch_db_writes")

    summary_by_key = {(row["workload"], _integer(row, "concurrency")): row for row in summaries}
    expected_summary_keys = {
        (workload, concurrency) for workload in WORKLOADS for concurrency in CONCURRENCY_LEVELS
    }
    if len(summaries) != len(expected_summary_keys) or set(summary_by_key) != expected_summary_keys:
        raise FreezeError("contention_summary_grid_incomplete")

    for workload, concurrency in sorted(expected_summary_keys):
        rows = [
            row
            for row in attempts
            if row["workload"] == workload and _integer(row, "concurrency") == concurrency
        ]
        for batch in range(repetitions):
            batch_rows = [row for row in rows if _integer(row, "batch") == batch]
            for field in ("batch_wall_ms", "batch_db_reads", "batch_db_writes"):
                if len({row[field] for row in batch_rows}) != 1:
                    raise FreezeError("contention_batch_metric_inconsistent")
            accepted = [row for row in batch_rows if row["result"] == "accepted"]
            rejected = [row for row in batch_rows if row["result"] == "rejected"]
            expected_stale_class = "true_stale" if workload == "same_dependency" else "false_stale"
            if (
                len(accepted) != 1
                or len(rejected) != concurrency - 1
                or any(row["reason_code"] != "accepted" for row in accepted)
                or any(
                    row["reason_code"] != "stale_state_version"
                    or row["stale_class"] != expected_stale_class
                    for row in rejected
                )
            ):
                raise FreezeError("contention_atomic_outcome_invalid")
        summary = summary_by_key[(workload, concurrency)]
        expected_attempts = repetitions * concurrency
        expected_true = repetitions * (concurrency - 1) if workload == "same_dependency" else 0
        expected_false = repetitions * (concurrency - 1) if workload == "unrelated_slots" else 0
        expected_integers = {
            "independent_profile_batches": repetitions,
            "attempts": expected_attempts,
            "accepted_valid_commits": repetitions,
            "true_stale_rejections": expected_true,
            "false_stale_rejections": expected_false,
            "database_errors": 0,
            "retry_count": 0,
            "successful_retries": 0,
        }
        if any(_integer(summary, field) != value for field, value in expected_integers.items()):
            raise FreezeError("contention_summary_count_mismatch")
        latencies = [_number(row, "latency_ms") for row in rows]
        batch_wall = {_integer(row, "batch"): _number(row, "batch_wall_ms") for row in rows}
        batch_reads = {_integer(row, "batch"): _integer(row, "batch_db_reads") for row in rows}
        batch_writes = {_integer(row, "batch"): _integer(row, "batch_db_writes") for row in rows}
        expected_numbers = {
            "false_stale_rate_per_attempt": round(expected_false / expected_attempts, 6),
            "p50_ms": round(percentile(latencies, 0.50), 3),
            "p95_ms": round(percentile(latencies, 0.95), 3),
            "p99_ms": round(percentile(latencies, 0.99), 3),
            "throughput_per_second": round(1000 * expected_attempts / sum(batch_wall.values()), 3),
            "db_reads": float(sum(batch_reads.values())),
            "db_writes": float(sum(batch_writes.values())),
            "writes_per_accepted_commit": round(sum(batch_writes.values()) / repetitions, 3),
        }
        if any(_number(summary, field) != value for field, value in expected_numbers.items()):
            raise FreezeError("contention_summary_metric_mismatch")
        if _number(summary, "peak_rss_bytes") <= 0:
            raise FreezeError("contention_peak_rss_invalid")
    _validate_checksums(root, (attempts_path, summary_path, strategy_model_path, manifest_path))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps({"status": result["status"], "external_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
