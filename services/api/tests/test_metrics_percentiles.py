"""Unit tests for the per-route latency percentile projection (Task 5.1).

``MetricsPercentiles`` is the optional, flag-gated companion to
``APIMetricsStore``. It keeps a bounded per-route latency sample ring and
projects p50/p90/p99 by reusing the proven, monotonic ``_percentile`` helper
(Requirements 5.1, 5.2, 5.3). These tests stay at the store level so they are
fast and independent of full app wiring.
"""

from clara_api.core.metrics import MetricsPercentiles


def test_percentiles_are_monotonic_for_a_fixed_sample_set() -> None:
    store = MetricsPercentiles()
    for value in [120.0, 10.0, 50.0, 300.0, 75.0, 5.0]:
        store.record("/route", value)

    result = store.percentiles("/route")

    assert set(result) == {"p50_ms", "p90_ms", "p99_ms"}
    assert result["p50_ms"] <= result["p90_ms"] <= result["p99_ms"]


def test_unknown_route_projects_zeroed_percentiles() -> None:
    store = MetricsPercentiles()

    result = store.percentiles("/never-seen")

    assert result == {"p50_ms": 0.0, "p90_ms": 0.0, "p99_ms": 0.0}


def test_ring_is_bounded_and_keeps_most_recent_samples() -> None:
    store = MetricsPercentiles(max_samples=3)
    for value in [1.0, 2.0, 3.0, 4.0, 5.0]:
        store.record("/route", value)

    # Only the trailing 3 samples (3, 4, 5) are retained; p50 of {3,4,5} == 4.
    assert store.percentiles("/route")["p50_ms"] == 4.0


def test_invalid_latency_values_are_ignored() -> None:
    store = MetricsPercentiles()
    for value in (-1.0, float("nan"), float("inf"), "not-a-number", None):
        store.record("/route", value)  # type: ignore[arg-type]

    # No valid sample recorded → projection stays at the zeroed baseline.
    assert store.percentiles("/route") == {"p50_ms": 0.0, "p90_ms": 0.0, "p99_ms": 0.0}


def test_snapshot_projects_each_recorded_route() -> None:
    store = MetricsPercentiles()
    store.record("/a", 10.0)
    store.record("/b", 20.0)

    snapshot = store.snapshot()

    assert set(snapshot) == {"/a", "/b"}
    assert snapshot["/a"]["p50_ms"] == 10.0
    assert snapshot["/b"]["p50_ms"] == 20.0


def test_reset_clears_all_samples() -> None:
    store = MetricsPercentiles()
    store.record("/route", 42.0)

    store.reset()

    assert store.snapshot() == {}
