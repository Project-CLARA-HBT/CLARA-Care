"""Unit tests for benchmark harness master runner and CLI."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.glhs_systems_benchmark.runner import (
    format_ascii_baseline_table,
    main,
    run_baseline_suite,
)
from evaluation.glhs_systems_benchmark.workload_generator import generate_workload


def test_format_ascii_baseline_table() -> None:
    workload = generate_workload(count=20, seed=42)
    metrics = run_baseline_suite(workload=workload, workers=2)
    table_str = format_ascii_baseline_table(metrics)

    assert "GLHS SS2PL" in table_str
    assert "PostgreSQL SSI" in table_str
    assert "TPS" in table_str
    assert "Unsafe%" in table_str


def test_runner_cli_baselines_suite(tmp_path: Path) -> None:
    json_out = tmp_path / "report.json"
    csv_out = tmp_path / "summary.csv"

    args = [
        "--suite", "baselines",
        "--num-txns", "30",
        "--workers", "2",
        "--output-json", str(json_out),
        "--output-csv", str(csv_out),
        "--seed", "123",
    ]

    ret = main(args)
    assert ret == 0
    assert json_out.exists()
    assert csv_out.exists()

    with json_out.open("r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["num_txns"] == 30
        assert "GLHS SS2PL (Canonical Lock Hierarchy + Layer 1 Barrier)" in data["baseline_metrics"]


def test_runner_cli_fault_suite(tmp_path: Path) -> None:
    json_out = tmp_path / "fault_report.json"
    args = [
        "--suite", "fault",
        "--output-json", str(json_out),
    ]

    ret = main(args)
    assert ret == 0
    assert json_out.exists()

    with json_out.open("r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["fault_recovery"]["all_passed"] is True


def test_runner_cli_deadlock_suite() -> None:
    args = ["--suite", "deadlock", "--workers", "4", "--seed", "42"]
    ret = main(args)
    assert ret == 0
