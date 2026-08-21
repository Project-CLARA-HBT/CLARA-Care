"""Tests for the GLHS DAG Concurrency Benchmark.

Verifies:
1. Arm 1: Monolithic profile locking produces ~93.75% false-stale rejection rate on 16 disjoint entities.
2. Arm 2: Entity DAG partition locking produces 0.0% false-stale rejection rate on 16 disjoint entities.
3. Arm 3: Entity DAG partition locking produces atomic winner and true-stale rejections on overlapping entities.
4. Correct metric computation (rates, percentiles, latency aggregation).
5. Output generation (ASCII table summary and structured JSON serialization).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.glhs_postgres_toctou.dag_concurrency_benchmark import (
    DEFAULT_BENCHMARK_DOMAIN,
    DEFAULT_SHARED_SEMANTIC_KEY,
    BenchmarkArmType,
    SimulatedLockCoordinator,
    calculate_percentile,
    execute_benchmark_arm,
    main,
    run_dag_concurrency_benchmark,
)


def test_percentile_calculation_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert calculate_percentile(values, 0.50) == 50.0
    assert calculate_percentile(values, 0.95) == 100.0
    assert calculate_percentile([], 0.50) == 0.0


def test_arm1_monolithic_profile_locking_disjoint_entities_16_writers() -> None:
    """Arm 1: 16 writers on disjoint entities -> 1 winner, 15 false-stale rejections (93.75%)."""
    coordinator = SimulatedLockCoordinator()
    coordinator.profile_versions[1] = 1
    for i in range(16):
        coordinator.partition_versions[f"{DEFAULT_BENCHMARK_DOMAIN}:rx_entity_{i:02d}"] = 1

    result = execute_benchmark_arm(
        BenchmarkArmType.MONOLITHIC_DISJOINT,
        writer_count=16,
        simulated_coordinator=coordinator,
    )

    assert result.num_writers == 16
    assert result.total_attempts == 16
    assert result.committed_count == 1
    assert result.false_stale_count == 15
    assert result.true_stale_count == 0
    assert result.operational_error_count == 0
    assert result.false_stale_rejection_rate == 0.9375
    assert result.commit_success_rate == 0.0625
    assert result.invariant_passed is True
    assert "93.75%" in result.verification_message


def test_arm2_dag_partition_locking_disjoint_entities_16_writers() -> None:
    """Arm 2: 16 writers on disjoint entities -> 16 winners, 0 rejections (0.0% false-stale)."""
    coordinator = SimulatedLockCoordinator()
    coordinator.profile_versions[1] = 1
    for i in range(16):
        coordinator.partition_versions[f"{DEFAULT_BENCHMARK_DOMAIN}:rx_entity_{i:02d}"] = 1

    result = execute_benchmark_arm(
        BenchmarkArmType.DAG_DISJOINT,
        writer_count=16,
        simulated_coordinator=coordinator,
    )

    assert result.num_writers == 16
    assert result.total_attempts == 16
    assert result.committed_count == 16
    assert result.false_stale_count == 0
    assert result.true_stale_count == 0
    assert result.operational_error_count == 0
    assert result.false_stale_rejection_rate == 0.0
    assert result.commit_success_rate == 1.0
    assert result.invariant_passed is True
    assert "0.00% false-stale" in result.verification_message


def test_arm3_dag_partition_locking_overlapping_entities_16_writers() -> None:
    """Arm 3: 16 writers on overlapping entities -> 1 atomic winner, 15 true-stale rejections."""
    coordinator = SimulatedLockCoordinator()
    coordinator.profile_versions[1] = 1
    coordinator.partition_versions[f"{DEFAULT_BENCHMARK_DOMAIN}:{DEFAULT_SHARED_SEMANTIC_KEY}"] = 1

    result = execute_benchmark_arm(
        BenchmarkArmType.DAG_OVERLAPPING,
        writer_count=16,
        simulated_coordinator=coordinator,
    )

    assert result.num_writers == 16
    assert result.total_attempts == 16
    assert result.committed_count == 1
    assert result.true_stale_count == 15
    assert result.false_stale_count == 0
    assert result.operational_error_count == 0
    assert result.true_stale_rejection_rate == 0.9375
    assert result.false_stale_rejection_rate == 0.0
    assert result.commit_success_rate == 0.0625
    assert result.invariant_passed is True
    assert "atomic winner" in result.verification_message


@pytest.mark.parametrize(
    "writer_count, expected_rejections, expected_rate",
    [
        (1, 0, 0.0),
        (2, 1, 0.5),
        (4, 3, 0.75),
        (8, 7, 0.875),
        (16, 15, 0.9375),
    ],
)
def test_concurrency_scaling_monolithic_disjoint(
    writer_count: int,
    expected_rejections: int,
    expected_rate: float,
) -> None:
    """Contention grid scales deterministically: (W-1)/W false-stale rejection rate."""
    coordinator = SimulatedLockCoordinator()
    coordinator.profile_versions[1] = 1
    for i in range(writer_count):
        coordinator.partition_versions[f"{DEFAULT_BENCHMARK_DOMAIN}:rx_entity_{i:02d}"] = 1

    result = execute_benchmark_arm(
        BenchmarkArmType.MONOLITHIC_DISJOINT,
        writer_count=writer_count,
        simulated_coordinator=coordinator,
    )

    assert result.committed_count == 1
    assert result.false_stale_count == expected_rejections
    assert abs(result.false_stale_rejection_rate - expected_rate) < 1e-4


def test_full_benchmark_runner_and_summary_report() -> None:
    """Test full benchmark orchestration and report generation."""
    report = run_dag_concurrency_benchmark(writer_count=16, use_simulation_fallback=True)

    assert report.all_invariants_passed is True
    assert len(report.arms) == 3
    assert "monolithic_disjoint" in report.arms
    assert "dag_disjoint" in report.arms
    assert "dag_overlapping" in report.arms

    # Arm 1 verification
    arm1 = report.arms["monolithic_disjoint"]
    assert arm1.false_stale_rejection_rate == 0.9375
    assert arm1.committed_count == 1

    # Arm 2 verification
    arm2 = report.arms["dag_disjoint"]
    assert arm2.false_stale_rejection_rate == 0.0
    assert arm2.committed_count == 16

    # Arm 3 verification
    arm3 = report.arms["dag_overlapping"]
    assert arm3.true_stale_rejection_rate == 0.9375
    assert arm3.false_stale_rejection_rate == 0.0
    assert arm3.committed_count == 1

    # Summary table formatting
    table = report.summary_table
    assert "GLHS OPTIMISTIC CONCURRENCY BENCHMARK" in table
    assert "1. Monolithic (16 Disjoint Entities)" in table
    assert "2. Entity DAG (16 Disjoint Entities)" in table
    assert "3. Entity DAG (16 Overlapping Entities)" in table
    assert "93.75%" in table
    assert "0.00%" in table


def test_cli_runner_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI execution with file and stdout output."""
    out_file = tmp_path / "bench_results.json"
    exit_code = main(["--writers", "16", "--output", str(out_file), "--json"])

    assert exit_code == 0
    assert out_file.exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["all_invariants_passed"] is True
    assert data["num_writers"] == 16
    assert data["arms"]["monolithic_disjoint"]["false_stale_rejection_rate"] == 0.9375
    assert data["arms"]["dag_disjoint"]["false_stale_rejection_rate"] == 0.0
    assert data["arms"]["dag_overlapping"]["true_stale_rejection_rate"] == 0.9375
