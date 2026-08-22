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
    load_benchmark_data,
)


def test_fallback_dataset_generation() -> None:
    data = generate_fallback_dataset()
    assert "concurrency_stress" in data
    assert len(data["concurrency_stress"]["results"]) == 128
    assert "deadlock_analysis" in data
    assert "tost_study" in data
    assert "risk_coverage" in data


def test_load_benchmark_data() -> None:
    data = load_benchmark_data()
    assert "concurrency_stress" in data
    assert "deadlock_analysis" in data
    assert "tost_study" in data
    assert data["tost_study"]["n"] == 384


def test_generate_all_charts_to_tmp_dir(tmp_path: Path) -> None:
    ret = generate_all_charts(output_dir=tmp_path)
    assert ret == 0

    expected_svg_files = [
        "throughput_scaling.svg",
        "latency_distribution.svg",
        "deadlock_wfg_analysis.svg",
        "tost_equivalence_forest_plot.svg",
        "risk_coverage_pareto.svg",
    ]

    for fname in expected_svg_files:
        fpath = tmp_path / fname
        assert fpath.is_file(), f"Expected file {fname} not found"
        assert fpath.stat().st_size > 0, f"File {fname} is empty"

        # Validate clean standalone XML SVG structure
        tree = ET.parse(fpath)
        root = tree.getroot()
        assert root.tag.endswith("svg"), f"Root element for {fname} is not svg: {root.tag}"
        assert len(list(root.iter())) >= 10, f"SVG {fname} has insufficient XML elements"

    # Verify no fake PDF shells are emitted
    for f in tmp_path.iterdir():
        assert f.suffix == ".svg", f"Unexpected non-SVG file emitted: {f.name}"


def test_individual_chart_generators(tmp_path: Path) -> None:
    data = generate_fallback_dataset()

    svg_tps = generate_throughput_scaling_chart(data, tmp_path / "custom_tps.svg")
    assert svg_tps.is_file()
    assert svg_tps.stat().st_size > 0
    tree = ET.parse(svg_tps)
    assert tree.getroot().tag.endswith("svg")

    svg_lat = generate_latency_distribution_chart(data, tmp_path / "custom_lat.svg")
    assert svg_lat.is_file()
    assert svg_lat.stat().st_size > 0
    tree = ET.parse(svg_lat)
    assert tree.getroot().tag.endswith("svg")

    svg_dead = generate_deadlock_wfg_chart(data, tmp_path / "custom_dead.svg")
    assert svg_dead.is_file()
    assert svg_dead.stat().st_size > 0
    tree = ET.parse(svg_dead)
    assert tree.getroot().tag.endswith("svg")

    svg_tost = generate_tost_forest_plot(data, tmp_path / "custom_tost.svg")
    assert svg_tost.is_file()
    assert svg_tost.stat().st_size > 0
    tree = ET.parse(svg_tost)
    assert tree.getroot().tag.endswith("svg")

    svg_pareto = generate_risk_coverage_pareto_chart(data, tmp_path / "custom_pareto.svg")
    assert svg_pareto.is_file()
    assert svg_pareto.stat().st_size > 0
    tree = ET.parse(svg_pareto)
    assert tree.getroot().tag.endswith("svg")
