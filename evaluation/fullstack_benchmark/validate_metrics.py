"""Validate measurements from PostgreSQL→GST→GLHS→THSS→API runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

COLUMNS = frozenset(
    {
        "operation",
        "history_depth",
        "concurrency",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "throughput_per_second",
        "db_reads",
        "db_writes",
        "write_amplification",
        "reconstruction_ms",
        "snapshot_compile_ms",
        "governed_decision_reconstruction_ms",
        "audit_lookup_ms",
        "invalidation_rebuild_ms",
        "enter_in_error_rebuild_ms",
        "cpu_percent",
        "peak_rss_bytes",
    }
)
REQUIRED_OPERATION_ORDER = (
    "transition",
    "reconstruction",
    "snapshot_compile",
    "governed_decision_reconstruction",
    "audit_lookup",
    "invalidation_rebuild",
    "enter_in_error_rebuild",
)
REQUIRED_OPERATIONS = frozenset(REQUIRED_OPERATION_ORDER)
EXPECTED_GAPS = frozenset(
    {"http_transport", "source_revocation_propagation", "concurrent_transition"}
)


def _validate_checksums(root: Path, expected: tuple[Path, ...]) -> None:
    checksum_path = root / "checksums.sha256"
    if not checksum_path.is_file():
        raise FreezeError("fullstack_checksum_inventory_missing")
    declared: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] in declared:
            raise FreezeError("fullstack_checksum_inventory_invalid")
        declared[parts[1]] = parts[0]
    if set(declared) != {path.name for path in expected}:
        raise FreezeError("fullstack_checksum_file_set_invalid")
    for path in expected:
        if declared[path.name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise FreezeError(f"fullstack_checksum_mismatch:{path.name}")


def _number(row: dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise FreezeError(f"fullstack_metric_not_numeric:{field}") from exc
    if not math.isfinite(value):
        raise FreezeError(f"fullstack_metric_non_finite:{field}")
    if value < 0:
        raise FreezeError(f"fullstack_metric_negative:{field}")
    return value


def validate(metrics: Path, manifest: Path) -> None:
    metadata = load_frozen_json(manifest)
    required = {
        "schema_version",
        "status",
        "architecture_path",
        "hardware",
        "worker_count",
        "environment",
        "implementation",
        "operations",
        "coverage_gaps",
        "row_counts",
        "fixture_contains_phi",
        "production_services_modified",
        "http_transport_measured",
    }
    if required - metadata.keys():
        raise FreezeError("fullstack_manifest_incomplete")
    if (
        metadata.get("schema_version") != "glhs-fullstack-service-layer.v2"
        or metadata.get("status") != "EXECUTED_PARTIAL_SERVICE_LAYER"
    ):
        raise FreezeError("fullstack_manifest_status_invalid")
    if metadata.get("architecture_path") != "postgresql>gst>glhs>thss>api":
        raise FreezeError("fullstack_architecture_path_invalid")
    if not metadata.get("hardware") or not metadata.get("environment"):
        raise FreezeError("fullstack_environment_missing")
    if (
        metadata.get("worker_count") != 1
        or metadata.get("fixture_contains_phi") is not False
        or metadata.get("production_services_modified") is not False
        or metadata.get("http_transport_measured") is not False
    ):
        raise FreezeError("fullstack_execution_boundary_invalid")
    if metadata.get("operations") != list(REQUIRED_OPERATION_ORDER):
        raise FreezeError("fullstack_manifest_operations_invalid")
    gaps = metadata.get("coverage_gaps")
    if not isinstance(gaps, list) or set(gaps) != EXPECTED_GAPS:
        raise FreezeError("fullstack_coverage_gaps_invalid")
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        raise FreezeError("fullstack_environment_invalid")
    if (
        environment.get("database") != "postgresql"
        or not str(environment.get("server_version", "")).strip()
        or environment.get("alembic_revision") != "20260811_0055"
        or re.fullmatch(r"sha256:[0-9a-f]{64}", str(environment.get("database_image_digest", "")))
        is None
    ):
        raise FreezeError("fullstack_database_attestation_invalid")
    implementation = metadata.get("implementation")
    if (
        not isinstance(implementation, dict)
        or re.fullmatch(r"[0-9a-f]{40}", str(implementation.get("implementation_sha", ""))) is None
        or not isinstance(implementation.get("tracked_worktree_clean"), bool)
    ):
        raise FreezeError("fullstack_implementation_attestation_invalid")
    with metrics.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("fullstack_metric_schema_incomplete")
        rows = list(reader)
    if (
        len(rows) != len(REQUIRED_OPERATIONS)
        or {row["operation"] for row in rows} != REQUIRED_OPERATIONS
    ):
        raise FreezeError("fullstack_operations_incomplete")
    duration_fields = {
        "reconstruction": "reconstruction_ms",
        "snapshot_compile": "snapshot_compile_ms",
        "governed_decision_reconstruction": "governed_decision_reconstruction_ms",
        "audit_lookup": "audit_lookup_ms",
        "invalidation_rebuild": "invalidation_rebuild_ms",
        "enter_in_error_rebuild": "enter_in_error_rebuild_ms",
    }
    for row in rows:
        if _number(row, "concurrency") != 1:
            raise FreezeError("fullstack_service_layer_concurrency_invalid")
        p50 = _number(row, "p50_ms")
        p95 = _number(row, "p95_ms")
        p99 = _number(row, "p99_ms")
        if p50 > p95 or p95 > p99 or _number(row, "throughput_per_second") <= 0:
            raise FreezeError("fullstack_latency_distribution_invalid")
        for field in (
            "history_depth",
            "db_reads",
            "db_writes",
            "write_amplification",
            "cpu_percent",
            "peak_rss_bytes",
        ):
            _number(row, field)
        expected_duration = duration_fields.get(row["operation"])
        for duration_field in duration_fields.values():
            if duration_field == expected_duration:
                if _number(row, duration_field) <= 0:
                    raise FreezeError("fullstack_operation_duration_invalid")
            elif row.get(duration_field, "") != "":
                raise FreezeError("fullstack_operation_duration_misattributed")
    row_counts = metadata.get("row_counts")
    if not isinstance(row_counts, dict) or any(
        not isinstance(row_counts.get(field), int) or row_counts[field] <= 0
        for field in ("transitions", "assertions", "snapshots")
    ):
        raise FreezeError("fullstack_row_counts_invalid")
    if metrics.parent != manifest.parent:
        raise FreezeError("fullstack_artifact_root_mismatch")
    _validate_checksums(manifest.parent, (metrics, manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.metrics, args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
