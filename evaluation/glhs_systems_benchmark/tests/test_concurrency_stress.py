"""Unit tests for multi-threaded concurrency stress and Zipfian skew sampler."""

from __future__ import annotations

from collections import Counter

from evaluation.glhs_systems_benchmark.baselines.glhs_ss2pl import GLHSSS2PLEngine
from evaluation.glhs_systems_benchmark.concurrency_stress import (
    ZipfianSampler,
    generate_skewed_workload,
    run_concurrency_stress_grid,
    run_single_stress_trial,
)


def test_zipfian_sampler_uniform() -> None:
    sampler = ZipfianSampler(n_items=10, alpha=0.0, seed=42)
    samples = [sampler.sample() for _ in range(1000)]
    counts = Counter(samples)
    assert len(counts) == 10
    # Uniform: each item should appear roughly 100 times (between 50 and 150)
    for c in counts.values():
        assert 50 <= c <= 150


def test_zipfian_sampler_skewed() -> None:
    sampler = ZipfianSampler(n_items=10, alpha=1.2, seed=42)
    samples = [sampler.sample() for _ in range(1000)]
    counts = Counter(samples)
    # Skewed: item 0 should have the highest frequency by far
    assert counts[0] > counts[1]
    assert counts[0] > counts[9]
    assert counts[0] > 300  # Highly skewed hot item


def test_generate_skewed_workload() -> None:
    workload = generate_skewed_workload(workers=4, tx_per_worker=25, alpha=0.9, seed=42)
    assert len(workload) == 100
    assert all(tx.workload_id.startswith("stress_w4_a0.9") for tx in workload)


def test_run_single_stress_trial() -> None:
    engine = GLHSSS2PLEngine()
    workload = generate_skewed_workload(workers=2, tx_per_worker=10, alpha=0.5, seed=42)
    res = run_single_stress_trial(engine=engine, workload=workload, workers=2, alpha=0.5)

    assert res.total_tx == 20
    assert res.throughput_tps > 0.0
    assert res.unsafe_commits == 0
    assert res.unsafe_commit_rate == 0.0


def test_run_concurrency_stress_grid_fast() -> None:
    report = run_concurrency_stress_grid(
        workers_list=[1, 2],
        alphas_list=[0.0, 0.9],
        paradigms=["glhs_ss2pl", "standard_occ"],
        tx_per_worker=5,
        seed=42,
    )
    assert report.total_experiments == 8  # 2 paradigms * 2 alphas * 2 worker levels
    assert len(report.results) == 8
