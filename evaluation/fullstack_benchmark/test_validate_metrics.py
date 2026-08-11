from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.fullstack_benchmark.validate_metrics import (
    COLUMNS,
    REQUIRED_OPERATION_ORDER,
    validate,
)


def _seal(root: Path, metrics: Path, manifest: Path) -> None:
    (root / "checksums.sha256").write_text(
        "\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
            for path in (metrics, manifest)
        )
        + "\n",
        encoding="utf-8",
    )


def _artifact(root: Path) -> tuple[Path, Path]:
    metrics = root / "fullstack_metrics.csv"
    duration_fields = {
        "reconstruction": "reconstruction_ms",
        "snapshot_compile": "snapshot_compile_ms",
        "governed_decision_reconstruction": "governed_decision_reconstruction_ms",
        "audit_lookup": "audit_lookup_ms",
        "invalidation_rebuild": "invalidation_rebuild_ms",
        "enter_in_error_rebuild": "enter_in_error_rebuild_ms",
    }
    rows = []
    for operation in REQUIRED_OPERATION_ORDER:
        row = {column: "" for column in COLUMNS}
        row.update(
            {
                "operation": operation,
                "history_depth": "20",
                "concurrency": "1",
                "p50_ms": "1",
                "p95_ms": "2",
                "p99_ms": "3",
                "throughput_per_second": "100",
                "db_reads": "2",
                "db_writes": "1",
                "write_amplification": "0.5",
                "cpu_percent": "10",
                "peak_rss_bytes": "1024",
            }
        )
        duration = duration_fields.get(operation)
        if duration is not None:
            row[duration] = "2"
        rows.append(row)
    with metrics.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    manifest = root / "fullstack_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "glhs-fullstack-service-layer.v2",
                "status": "EXECUTED_PARTIAL_SERVICE_LAYER",
                "architecture_path": "postgresql>gst>glhs>thss>api",
                "hardware": {"cpu_count": 8},
                "worker_count": 1,
                "fixture_contains_phi": False,
                "production_services_modified": False,
                "http_transport_measured": False,
                "environment": {
                    "database": "postgresql",
                    "server_version": "16.10",
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
                "row_counts": {"transitions": 1, "assertions": 1, "snapshots": 1},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _seal(root, metrics, manifest)
    return metrics, manifest


def test_fullstack_artifact_validates_and_detects_tampering(tmp_path: Path) -> None:
    metrics, manifest = _artifact(tmp_path)
    validate(metrics, manifest)

    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="fullstack_checksum_mismatch"):
        validate(metrics, manifest)


def test_fullstack_artifact_rejects_non_finite_metrics(tmp_path: Path) -> None:
    metrics, manifest = _artifact(tmp_path)
    with metrics.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["p50_ms"] = "NaN"
    with metrics.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    _seal(tmp_path, metrics, manifest)

    with pytest.raises(FreezeError, match="fullstack_metric_non_finite:p50_ms"):
        validate(metrics, manifest)
