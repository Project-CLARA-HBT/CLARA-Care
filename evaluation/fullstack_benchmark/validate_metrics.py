"""Validate measurements from PostgreSQL→GST→GLHS→THSS→API runs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

COLUMNS = frozenset({
    "operation", "history_depth", "concurrency", "p50_ms", "p95_ms", "p99_ms",
    "throughput_per_second", "db_reads", "db_writes", "write_amplification",
    "reconstruction_ms", "snapshot_compile_ms", "invalidation_rebuild_ms",
    "revocation_propagation_ms", "cpu_percent", "peak_rss_bytes",
})
REQUIRED_OPERATIONS = frozenset({
    "transition", "reconstruction", "snapshot_compile", "invalidation_rebuild",
    "revocation_propagation",
})


def validate(metrics: Path, manifest: Path) -> None:
    metadata = load_frozen_json(manifest)
    required = {"status", "architecture_path", "hardware", "worker_count", "environment"}
    if required - metadata.keys() or metadata.get("status") != "frozen":
        raise FreezeError("fullstack_manifest_not_frozen")
    if metadata.get("architecture_path") != "postgresql>gst>glhs>thss>api":
        raise FreezeError("fullstack_architecture_path_invalid")
    if not metadata.get("hardware") or not metadata.get("environment"):
        raise FreezeError("fullstack_environment_missing")
    with metrics.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("fullstack_metric_schema_incomplete")
        rows = list(reader)
    if {row["operation"] for row in rows} != REQUIRED_OPERATIONS:
        raise FreezeError("fullstack_operations_incomplete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.metrics, args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
