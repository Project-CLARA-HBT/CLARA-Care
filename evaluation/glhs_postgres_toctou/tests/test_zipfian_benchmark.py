"""Tests for the parameterized Zipfian concurrency benchmark."""
from __future__ import annotations

import pytest
from evaluation.glhs_postgres_toctou.zipfian_concurrency_bench import (
    ZipfianGenerator,
    run_zipfian_simulation,
    run_full_benchmark_grid,
)


def test_zipfian_generator_uniform() -> None:
    gen = ZipfianGenerator(n_items=10, alpha=0.0, seed=123)
    assert len(gen.probabilities) == 10
    assert pytest.approx(sum(gen.probabilities), 1e-6) == 1.0
    for p in gen.probabilities:
        assert pytest.approx(p, 1e-6) == 0.1
    samples = [gen.sample() for _ in range(100)]
    assert all(0 <= s < 10 for s in samples)


def test_zipfian_generator_skewed() -> None:
    gen = ZipfianGenerator(n_items=10, alpha=1.2, seed=123)
    assert gen.probabilities[0] > gen.probabilities[1] > gen.probabilities[-1]
    samples = [gen.sample() for _ in range(1000)]
    # Top item should be most frequent
    assert samples.count(0) > samples.count(9)


def test_glhs_zero_false_stale_invariant() -> None:
    for alpha in [0.0, 0.5, 0.9, 1.2]:
        for w in [1, 16, 64, 128]:
            res = run_zipfian_simulation(alpha=alpha, writers=w, tx_per_writer=50)
            assert res["glhs"].false_stale_rate == 0.00
            assert res["glhs"].false_stale_aborts == 0
            if w > 1:
                assert res["monolithic"].false_stale_rate > 50.0


def test_full_benchmark_grid_runs() -> None:
    grid = run_full_benchmark_grid()
    # 4 skews * 8 writers * 3 paradigms = 96 benchmark results
    assert len(grid) == 96
