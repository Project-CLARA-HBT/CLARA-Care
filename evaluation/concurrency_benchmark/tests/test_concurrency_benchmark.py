"""Comprehensive Unit and Integration Tests for E09 In-Memory Concurrency Simulation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from evaluation.concurrency_benchmark.analyze import (
    analyze_concurrency_metrics,
    generate_markdown_summary,
)
from evaluation.concurrency_benchmark.multifactor_runner import (
    CellRunMetrics,
    ConcurrencyRegime,
    PartitionKey,
    SimulatedPartitionCoordinator,
    WorkloadCellConfig,
    ZipfianSampler,
    build_workload_family_cells,
    execute_dag_partition_writer,
    execute_monolithic_writer,
    generate_workload_tasks,
    run_single_cell_repetition,
)
from evaluation.concurrency_benchmark.seal import seal_experiment_e09
from reproduce_e09 import reproduce_and_verify


def test_zipfian_sampler_theta_zero() -> None:
    sampler = ZipfianSampler(n_items=10, theta=0.0, seed=42)
    assert len(sampler.probabilities) == 10
    assert pytest.approx(sum(sampler.probabilities), abs=1e-6) == 1.0
    for p in sampler.probabilities:
        assert pytest.approx(p, abs=1e-6) == 0.1

    samples = [sampler.sample() for _ in range(100)]
    assert all(0 <= s < 10 for s in samples)


def test_zipfian_sampler_skewed() -> None:
    sampler = ZipfianSampler(n_items=10, theta=1.4, seed=42)
    assert sampler.probabilities[0] > sampler.probabilities[-1]
    assert pytest.approx(sum(sampler.probabilities), abs=1e-6) == 1.0

    samples = [sampler.sample() for _ in range(500)]
    # Hot key (0) should be sampled most frequently
    counts = {i: samples.count(i) for i in range(10)}
    assert counts[0] > counts[9]


def test_canonical_lock_ordering() -> None:
    entities = [
        PartitionKey("medications", "rx_02"),
        PartitionKey("conditions", "cond_01"),
        PartitionKey("medications", "rx_01"),
    ]
    coord = SimulatedPartitionCoordinator(entities)
    locked_items = coord.get_partition_locks(entities)
    key_strs = [k for k, _ in locked_items]

    # Should be sorted lexicographically
    expected = ["conditions:cond_01", "medications:rx_01", "medications:rx_02"]
    assert key_strs == expected


def test_disjoint_partitions_zero_false_stale_dag() -> None:
    cfg = WorkloadCellConfig(
        cell_id="test_disjoint",
        family_name="disjoint_entity",
        concurrency=16,
        zipf_theta=0.0,
        overlap_ratio=0.0,
        dependency_width=1,
        read_ratio=0.0,
        write_ratio=1.0,
        tx_per_writer=1,
    )
    metrics = run_single_cell_repetition(cfg, ConcurrencyRegime.ENTITY_DAG_PARTITION_LOCKING, repetition_id=1)

    assert metrics.false_stale_count == 0
    assert metrics.false_stale_rate == 0.0
    assert metrics.deadlock_count == 0
    assert metrics.invariant_false_stale_zero is True
    assert metrics.invariant_deadlock_zero is True
    assert metrics.committed_count == 16


def test_monolithic_profile_locking_disjoint_false_stale() -> None:
    cfg = WorkloadCellConfig(
        cell_id="test_mono_disjoint",
        family_name="disjoint_entity",
        concurrency=16,
        zipf_theta=0.0,
        overlap_ratio=0.0,
        dependency_width=1,
        read_ratio=0.0,
        write_ratio=1.0,
        tx_per_writer=1,
    )
    metrics = run_single_cell_repetition(cfg, ConcurrencyRegime.MONOLITHIC_PROFILE_LOCK, repetition_id=1)

    # In monolithic mode, concurrent writers on disjoint entities cause false-stale rejections
    assert metrics.false_stale_count > 0
    assert metrics.committed_count < 16


def test_workload_families_generation() -> None:
    families = build_workload_family_cells()
    assert len(families) == 10

    family_names = [f.family_name for f in families]
    expected_names = [
        "same_entity_contention",
        "disjoint_entity",
        "partial_overlap",
        "multi_domain",
        "hot_key_zipfian",
        "governance_plus_entity",
        "evidence_plus_entity",
        "read_heavy",
        "write_heavy",
        "mixed",
    ]
    assert family_names == expected_names


def test_statistical_analysis_engine() -> None:
    records = []
    cfg = WorkloadCellConfig(
        cell_id="C02_disjoint",
        family_name="disjoint_entity",
        concurrency=16,
        zipf_theta=0.0,
        overlap_ratio=0.0,
        dependency_width=1,
        read_ratio=0.0,
        write_ratio=1.0,
    )
    for rep in range(1, 6):
        m = run_single_cell_repetition(cfg, ConcurrencyRegime.ENTITY_DAG_PARTITION_LOCKING, repetition_id=rep)
        records.append(m)

    report = analyze_concurrency_metrics(records)
    assert report.all_invariants_passed is True
    assert report.disjoint_false_stale_rate_dag == 0.0
    assert report.total_deadlocks_across_all_runs == 0
    assert report.min_repetitions_met is True
    assert report.validation_status == "VALIDATED"

    md = generate_markdown_summary(report)
    assert "# Phase 9 (E09)" in md
    assert "Disjoint Partitions:" in md


def test_seal_and_reproduce_e09_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        protocol_file = tmp_path / "protocol.json"
        artifact_dir = tmp_path / "E09_artifact"

        proto_doc = {
            "schema_version": "glhs-e09-concurrency-protocol-v1",
            "protocol_id": "E09-CONCURRENCY-BENCHMARK",
            "freeze_id": "GLHS-CONCURRENCY-E09-TEST",
            "status": "FROZEN_FINAL",
            "experiment_phase": "E09",
            "branch": "test",
            "git_sha": "81f040d3e05905cc384239c5ae130f629e722d3e",
            "invariants": {
                "false_stale_rate_disjoint_target": 0.0,
                "total_deadlocks_target": 0,
            },
        }
        protocol_file.write_text(json.dumps(proto_doc, indent=2), encoding="utf-8")

        # Seal
        seal_doc = seal_experiment_e09(
            protocol_path=protocol_file,
            artifact_dir=artifact_dir,
            repetitions=5,
            seed=42,
        )
        assert seal_doc["status"] == "SEALED"
        assert seal_doc["disjoint_false_stale_rate_dag"] == 0.0
        assert seal_doc["total_deadlocks"] == 0

        # Reproduce
        repro_report = reproduce_and_verify(
            artifact_dir=artifact_dir,
            protocol_path=protocol_file,
        )
        assert repro_report["status"] == "REPRODUCED_AND_VERIFIED"
        assert repro_report["disjoint_false_stale_rate_dag"] == 0.0
        assert repro_report["total_deadlocks"] == 0
        assert repro_report["claim_eligible"] is True
