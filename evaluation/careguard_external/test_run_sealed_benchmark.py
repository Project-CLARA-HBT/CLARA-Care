"""Unit tests for the sealed CareGuard-VN external benchmark runner."""
from __future__ import annotations

import pytest
from evaluation.careguard_external.run_sealed_benchmark import (
    run_full_careguard_external_benchmark,
    generate_careguard_latex_tables,
)


def test_careguard_sealed_benchmark_runs_and_satisfies_invariants() -> None:
    report = run_full_careguard_external_benchmark()
    assert report.schema_version == "careguard-vn.sealed-benchmark.v1"
    assert report.benchmark_seal_id == "CAREGUARD-VN-SEALED-20260821-V8"
    
    # Dataset partitions
    assert report.dataset_partitions["dav_vietnam_products"]["total_records"] == 25480
    assert report.dataset_partitions["ddinter_2_0"]["total_pairs"] == 302516
    
    # Upstream identity
    assert report.upstream_identity_metrics["dav_exact_match_f1"] >= 0.98
    assert report.upstream_identity_metrics["stale_identity_rejection_rate"] == 1.0
    
    # Downstream DDI
    assert report.downstream_ddi_metrics["severe_ddi_sensitivity"] >= 0.99
    assert report.downstream_ddi_metrics["false_negative_rate"] <= 0.005
    
    # Oracle decomposition
    assert report.oracle_decomposition["delta_identity_error"] <= 0.003
    
    # FIDES invariants
    assert report.fides_safety_invariants["unverified_assertion_blocking_rate"] == 1.0
    
    # LaTeX tables generated cleanly
    tables = generate_careguard_latex_tables(report)
    assert "DAV Vietnam Products" in tables["table_evidence"]
    assert "Drug Name F1-Score" in tables["table_multimodal"]
    assert "Source-Bound Medication Identity" in tables["table_comparative"]
