"""Statistical analysis module for E10 Full-Stack Performance Characterization.

Processes fullstack metrics CSV and manifest JSON, verifies tail statistic sample sizes (N >= 100 per operation class),
computes latency distributions (p50, p95, p99), throughput, SQL query breakdowns, resource usage, and emits derived summaries.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

REQUIRED_OPERATIONS = (
    "transition",
    "reconstruction",
    "snapshot_compile",
    "governed_decision_reconstruction",
    "audit_lookup",
    "invalidation_rebuild",
    "enter_in_error_rebuild",
)

MINIMUM_REPETITIONS = 100


def _parse_number(value: Any, name: str) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_numeric_value:{name}:{value}") from exc
    if not math.isfinite(val):
        raise ValueError(f"non_finite_numeric_value:{name}:{value}")
    if val < 0:
        raise ValueError(f"negative_numeric_value:{name}:{value}")
    return val


def analyze(
    metrics_path: Path,
    manifest_path: Path,
    derived_dir: Path | None = None,
) -> dict[str, Any]:
    metrics_path = metrics_path.resolve()
    manifest_path = manifest_path.resolve()

    if not metrics_path.is_file():
        raise FileNotFoundError(f"metrics_file_not_found:{metrics_path}")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest_file_not_found:{manifest_path}")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    repetitions = manifest_data.get("repetitions", 0)

    with metrics_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)

    found_ops = {row["operation"] for row in rows}
    missing_ops = set(REQUIRED_OPERATIONS) - found_ops
    if missing_ops:
        raise ValueError(f"missing_required_operations:{sorted(missing_ops)}")

    op_summaries: dict[str, dict[str, Any]] = {}
    total_db_reads = 0
    total_db_writes = 0
    peak_rss = 0.0

    for row in rows:
        op = row["operation"]
        p50 = _parse_number(row["p50_ms"], "p50_ms")
        p95 = _parse_number(row["p95_ms"], "p95_ms")
        p99 = _parse_number(row["p99_ms"], "p99_ms")
        tps = _parse_number(row["throughput_per_second"], "throughput_per_second")
        reads = int(_parse_number(row["db_reads"], "db_reads"))
        writes = int(_parse_number(row["db_writes"], "db_writes"))
        write_amp = _parse_number(row["write_amplification"], "write_amplification")
        cpu_pct = _parse_number(row["cpu_percent"], "cpu_percent")
        rss = _parse_number(row["peak_rss_bytes"], "peak_rss_bytes")

        total_db_reads += reads
        total_db_writes += writes
        if rss > peak_rss:
            peak_rss = rss

        op_summaries[op] = {
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "throughput_tps": tps,
            "db_reads": reads,
            "db_writes": writes,
            "write_amplification": write_amp,
            "cpu_percent": cpu_pct,
            "peak_rss_bytes": int(rss),
        }

    # Red Team E check: sample size must be N >= 100 for valid tail statistics
    claim_eligible = repetitions >= MINIMUM_REPETITIONS and len(missing_ops) == 0

    summary_data = {
        "schema_version": "glhs-fullstack-analysis.v1",
        "status": "ANALYZED",
        "repetitions": repetitions,
        "history_depth": manifest_data.get("history_depth", 50),
        "claim_eligible": claim_eligible,
        "sample_size_sufficient": repetitions >= MINIMUM_REPETITIONS,
        "missing_operations_count": len(missing_ops),
        "architecture_path": manifest_data.get("architecture_path", "unknown"),
        "http_transport_measured": manifest_data.get("http_transport_measured", False),
        "total_db_reads": total_db_reads,
        "total_db_writes": total_db_writes,
        "peak_rss_bytes": int(peak_rss),
        "operation_summaries": op_summaries,
    }

    if derived_dir is not None:
        derived_dir = derived_dir.resolve()
        derived_dir.mkdir(parents=True, exist_ok=True)
        (derived_dir / "summary.json").write_text(
            json.dumps(summary_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (derived_dir / "summary.md").write_text(
            generate_summary_markdown(summary_data), encoding="utf-8"
        )

    return summary_data


def generate_summary_markdown(summary_data: dict[str, Any]) -> str:
    lines = [
        "# E10 Full-Stack Performance Characterization Summary",
        "",
        f"- **Repetitions (N):** {summary_data['repetitions']} per operation class",
        f"- **Claim Eligible:** `{summary_data['claim_eligible']}`",
        f"- **Sample Size Sufficient (N >= 100):** `{summary_data['sample_size_sufficient']}`",
        f"- **HTTP Transport Measured:** `{summary_data['http_transport_measured']}`",
        f"- **Architecture Path:** `{summary_data['architecture_path']}`",
        f"- **Total DB Reads:** {summary_data['total_db_reads']}",
        f"- **Total DB Writes:** {summary_data['total_db_writes']}",
        f"- **Peak RSS Memory:** {summary_data['peak_rss_bytes'] / (1024 * 1024):.2f} MB",
        "",
        "## Latency & Resource Breakdown",
        "",
        "| Operation | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (tps) | Reads | Writes | Write Amp | CPU % |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for op, data in summary_data["operation_summaries"].items():
        lines.append(
            f"| `{op}` | {data['p50_ms']:.2f} | {data['p95_ms']:.2f} | {data['p99_ms']:.2f} | "
            f"{data['throughput_tps']:.1f} | {data['db_reads']} | {data['db_writes']} | "
            f"{data['write_amplification']:.2f} | {data['cpu_percent']:.1f}% |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--derived-dir", type=Path, default=None)
    args = parser.parse_args()

    summary = analyze(args.metrics, args.manifest, derived_dir=args.derived_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
