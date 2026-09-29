from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Ensure repo root and service packages are on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT, _REPO_ROOT / "services" / "api" / "src", _REPO_ROOT / "services" / "ml" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pytest

from evaluation.fullstack_benchmark.analyze import analyze
from evaluation.fullstack_benchmark.run_http import FIELDNAMES, OPERATIONS, run_http_benchmark
from evaluation.fullstack_benchmark.seal import seal_experiment
from reproduce_e10 import reproduce_and_verify, verify_checksums


def test_fullstack_http_benchmark_execution(tmp_path: Path) -> None:
    output_dir = tmp_path / "http_run_01"
    db_url = f"sqlite:///{tmp_path}/test_benchmark.db"

    manifest = run_http_benchmark(
        database_url=db_url,
        output_dir=output_dir,
        history_depth=10,
        repetitions=10,  # fast test run
        allow_sqlite=True,
    )

    assert manifest["status"] == "EXECUTED_FULLSTACK_HTTP"
    assert manifest["http_transport_measured"] is True
    assert (output_dir / "fullstack_metrics.csv").is_file()
    assert (output_dir / "fullstack_manifest.json").is_file()
    assert (output_dir / "raw_latencies.json").is_file()
    assert (output_dir / "checksums.sha256").is_file()

    with (output_dir / "fullstack_metrics.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == len(OPERATIONS)
    found_ops = {r["operation"] for r in rows}
    assert found_ops == set(OPERATIONS)


def test_analyze_sample_size_invariant(tmp_path: Path) -> None:
    metrics_path = tmp_path / "fullstack_metrics.csv"
    manifest_path = tmp_path / "fullstack_manifest.json"

    rows = []
    for op in OPERATIONS:
        rows.append(
            {
                "operation": op,
                "history_depth": "10",
                "concurrency": "1",
                "p50_ms": "1.5",
                "p95_ms": "2.5",
                "p99_ms": "3.5",
                "throughput_per_second": "100.0",
                "db_reads": "5",
                "db_writes": "2",
                "write_amplification": "0.2",
                "reconstruction_ms": "1.5" if op == "reconstruction" else "",
                "snapshot_compile_ms": "1.5" if op == "snapshot_compile" else "",
                "governed_decision_reconstruction_ms": "1.5" if op == "governed_decision_reconstruction" else "",
                "audit_lookup_ms": "1.5" if op == "audit_lookup" else "",
                "invalidation_rebuild_ms": "1.5" if op == "invalidation_rebuild" else "",
                "enter_in_error_rebuild_ms": "1.5" if op == "enter_in_error_rebuild" else "",
                "cpu_percent": "12.0",
                "peak_rss_bytes": "10485760",
            }
        )

    with metrics_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    # Test N = 30 (insufficient for headline claims -> claim_eligible = False)
    manifest_path.write_text(
        json.dumps({"repetitions": 30, "architecture_path": "test"}, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_small = analyze(metrics_path, manifest_path)
    assert summary_small["sample_size_sufficient"] is False
    assert summary_small["claim_eligible"] is False

    # Test N = 100 (sufficient sample size -> claim_eligible = True)
    manifest_path.write_text(
        json.dumps({"repetitions": 100, "architecture_path": "test"}, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_large = analyze(metrics_path, manifest_path)
    assert summary_large["sample_size_sufficient"] is True
    assert summary_large["claim_eligible"] is True


def test_seal_and_reproduce_e10_workflow(tmp_path: Path) -> None:
    protocol_path = Path("protocols/E10_fullstack/protocol.json")
    run_dir = tmp_path / "raw_run"
    db_url = f"sqlite:///{tmp_path}/test_seal.db"

    # 1. Run HTTP benchmark with N=100
    run_http_benchmark(
        database_url=db_url,
        output_dir=run_dir,
        history_depth=10,
        repetitions=100,
        allow_sqlite=True,
    )

    artifact_dir = tmp_path / "artifacts" / "E10_fullstack"

    # 2. Seal experiment
    seal_doc = seal_experiment(
        artifact_dir=artifact_dir,
        protocol_path=protocol_path,
        metrics_path=run_dir / "fullstack_metrics.csv",
        manifest_path=run_dir / "fullstack_manifest.json",
        raw_latencies_path=run_dir / "raw_latencies.json",
        run_id="GLHS-TEST-E10-RUN-01",
    )

    assert seal_doc["status"] == "SEALED"
    assert seal_doc["claim_eligible"] is True
    assert seal_doc["sample_size_sufficient"] is True

    # 3. Offline reproduce & verify
    report = reproduce_and_verify(
        artifact_dir=artifact_dir,
        protocol_path=protocol_path,
    )

    assert report["status"] == "REPRODUCED_AND_VERIFIED"
    assert report["seal_verified"] is True
    assert report["network_disabled"] is True
    assert report["claim_eligible"] is True


def test_tamper_detection(tmp_path: Path) -> None:
    protocol_path = Path("protocols/E10_fullstack/protocol.json")
    run_dir = tmp_path / "raw_run"
    db_url = f"sqlite:///{tmp_path}/test_tamper.db"

    run_http_benchmark(
        database_url=db_url,
        output_dir=run_dir,
        history_depth=10,
        repetitions=100,
        allow_sqlite=True,
    )

    artifact_dir = tmp_path / "artifacts" / "E10_fullstack"
    seal_experiment(
        artifact_dir=artifact_dir,
        protocol_path=protocol_path,
        metrics_path=run_dir / "fullstack_metrics.csv",
        manifest_path=run_dir / "fullstack_manifest.json",
        raw_latencies_path=run_dir / "raw_latencies.json",
        run_id="GLHS-TEST-TAMPER-01",
    )

    # Tamper with raw_metrics
    metrics_file = artifact_dir / "raw" / "fullstack_metrics.csv"
    metrics_file.write_text(metrics_file.read_text(encoding="utf-8") + "\n# tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum_mismatch"):
        verify_checksums(artifact_dir)
