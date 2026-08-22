"""Unit tests for publication vector charts generator."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from evaluation.glhs_systems_benchmark.generate_charts import (
    generate_all_charts,
    generate_deadlock_wfg_chart,
    generate_fallback_dataset,
    generate_latency_distribution_chart,
    generate_risk_coverage_pareto_chart,
    generate_throughput_scaling_chart,
    generate_tost_forest_plot,
)


def test_fallback_dataset_generation() -> None:
    data = generate_fallback_dataset()
    assert "concurrency_stress" in data
    assert len(data["concurrency_stress"]["results"]) == 128
    assert "deadlock_analysis" in data


def test_generate_all_charts_to_tmp_dir(tmp_path: Path) -> None:
    ret = generate_all_charts(output_dir=tmp_path)
    assert ret == 0

    expected_files = [
        "throughput_scaling.svg",
        "throughput_scaling.pdf",
        "latency_distribution.svg",
        "latency_distribution.pdf",
        "deadlock_wfg_analysis.svg",
        "deadlock_wfg_analysis.pdf",
        "tost_equivalence_forest_plot.svg",
        "tost_equivalence_forest_plot.pdf",
        "risk_coverage_pareto.svg",
        "risk_coverage_pareto.pdf",
    ]

    for fname in expected_files:
        fpath = tmp_path / fname
        assert fpath.is_file(), f"Expected file {fname} not found"
        assert fpath.stat().st_size > 0, f"File {fname} is empty"

        # Validate SVG XML structure
        if fname.endswith(".svg"):
            tree = ET.parse(fpath)
            root = tree.getroot()
            assert root.tag.endswith("svg")
            assert len(list(root.iter())) >= 10


def test_individual_chart_generators(tmp_path: Path) -> None:
    data = generate_fallback_dataset()

    svg_tps, pdf_tps = generate_throughput_scaling_chart(data, tmp_path)
    assert svg_tps.is_file() and pdf_tps.is_file()

    svg_lat, pdf_lat = generate_latency_distribution_chart(data, tmp_path)
    assert svg_lat.is_file() and pdf_lat.is_file()

    svg_dead, pdf_dead = generate_deadlock_wfg_chart(data, tmp_path)
    assert svg_dead.is_file() and pdf_dead.is_file()

    svg_tost, pdf_tost = generate_tost_forest_plot(tmp_path)
    assert svg_tost.is_file() and pdf_tost.is_file()

    svg_pareto, pdf_pareto = generate_risk_coverage_pareto_chart(tmp_path)
    assert svg_pareto.is_file() and pdf_pareto.is_file()
