"""Master CLI & Comprehensive Orchestrator for GLHS Systems Benchmarking.

Executes all experimental evaluation suites:
1. Baseline Comparative Suite: 5-scenario workload across all 6 concurrency paradigms.
2. Concurrency Stress Suite: Scaling across W in {1..128} and Zipfian skew alpha in {0.0..1.2}.
3. Fault & Recovery Suite: Crash aborts, rollbacks, signature corruption, and Merkle ledger audit.
4. Deadlock Analysis Suite: Dynamic Wait-For Graph (WFG) monitoring and formal cycle verification.

Emits structured JSON/CSV reports and renders formatted ASCII comparison tables.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.glhs_systems_benchmark.baselines import (
    BaselineEngine,
    BaselineMetrics,
    FHIRBundleAdapterEngine,
    GLHSSS2PLEngine,
    PostgresSSIEngine,
    Standard2PLEngine,
    StandardOCCEngine,
    TxnResult,
    ZanzibarModelEngine,
    compute_metrics,
)
from evaluation.glhs_systems_benchmark.concurrency_stress import (
    ConcurrencyStressReport,
    run_concurrency_stress_grid,
)
from evaluation.glhs_systems_benchmark.deadlock_analyzer import (
    DeadlockAnalysisReport,
    run_deadlock_analysis,
)
from evaluation.glhs_systems_benchmark.fault_and_recovery import (
    FaultInjectionSuite,
    FaultRecoveryReport,
)
from evaluation.glhs_systems_benchmark.workload_generator import (
    ClinicalWorkloadItem,
    generate_workload,
    validate_workload_distribution,
)


@dataclass
class MasterBenchmarkReport:
    """Master report containing results from all executed benchmark suites."""

    timestamp_utc: str
    backend_mode: str
    database_url_configured: bool
    num_txns: int
    concurrency_workers: int
    baseline_metrics: dict[str, BaselineMetrics] = field(default_factory=dict)
    concurrency_stress: ConcurrencyStressReport | None = None
    fault_recovery: FaultRecoveryReport | None = None
    deadlock_analysis: dict[str, DeadlockAnalysisReport] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "backend_mode": self.backend_mode,
            "database_url_configured": self.database_url_configured,
            "num_txns": self.num_txns,
            "concurrency_workers": self.concurrency_workers,
            "baseline_metrics": {k: v.to_dict() for k, v in self.baseline_metrics.items()},
            "concurrency_stress": self.concurrency_stress.to_dict() if self.concurrency_stress else None,
            "fault_recovery": self.fault_recovery.to_dict() if self.fault_recovery else None,
            "deadlock_analysis": {k: v.to_dict() for k, v in self.deadlock_analysis.items()} if self.deadlock_analysis else None,
        }


def format_ascii_baseline_table(metrics_dict: dict[str, BaselineMetrics]) -> str:
    """Renders a formatted ASCII table comparing all baseline paradigms."""
    header = (
        f"{'Paradigm':<38} | {'TPS':>8} | {'p50(ms)':>8} | {'p95(ms)':>8} | "
        f"{'Unsafe%':>8} | {'TOCTOU':>7} | {'DDI Leak':>8} | {'FalseStale%':>12}"
    )
    separator = "-" * len(header)
    lines = [separator, header, separator]

    for _name, m in metrics_dict.items():
        unsafe_pct = f"{m.unsafe_commit_rate * 100:.1f}%"
        false_stale_pct = f"{m.false_stale_rate * 100:.1f}%"
        line = (
            f"{m.paradigm[:37]:<38} | {m.throughput_tps:>8.1f} | {m.p50_latency_ms:>8.2f} | "
            f"{m.p95_latency_ms:>8.2f} | {unsafe_pct:>8} | {m.toctou_violations:>7} | "
            f"{m.ddi_leaks:>8} | {false_stale_pct:>12}"
        )
        lines.append(line)

    lines.append(separator)
    return "\n".join(lines)


def run_baseline_suite(
    workload: list[ClinicalWorkloadItem],
    workers: int = 16,
    db_url: str | None = None,
) -> dict[str, BaselineMetrics]:
    """Runs the standardized 5-scenario workload across all 6 baseline paradigms."""
    engines: list[BaselineEngine] = [
        GLHSSS2PLEngine(db_url=db_url),
        PostgresSSIEngine(db_url=db_url),
        Standard2PLEngine(db_url=db_url),
        StandardOCCEngine(db_url=db_url),
        FHIRBundleAdapterEngine(db_url=db_url),
        ZanzibarModelEngine(db_url=db_url),
    ]

    metrics_results: dict[str, BaselineMetrics] = {}

    for current_engine in engines:
        current_engine.setup(num_patients=20, num_partitions=64)

        def _task(tx: ClinicalWorkloadItem, target_engine: BaselineEngine = current_engine) -> TxnResult:
            return target_engine.execute_transaction(tx)

        t_start = time.perf_counter()
        results: list[TxnResult] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_task, tx) for tx in workload]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        t_end = time.perf_counter()
        elapsed = max(1e-6, t_end - t_start)
        metrics = compute_metrics(current_engine.name, results, elapsed)
        metrics_results[current_engine.name] = metrics

    return metrics_results


def export_csv_report(report: MasterBenchmarkReport, filepath: str | Path) -> None:
    """Exports benchmark metrics to CSV format."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Paradigm",
            "Total_Tx",
            "Valid_Commits",
            "Safe_Aborts",
            "Unsafe_Commits",
            "Throughput_TPS",
            "Mean_Latency_ms",
            "p50_Latency_ms",
            "p95_Latency_ms",
            "p99_Latency_ms",
            "TOCTOU_Violations",
            "DDI_Leaks",
            "Deadlocks",
            "False_Stale_Aborts",
            "Unsafe_Commit_Rate",
            "False_Stale_Rate",
        ])

        for m in report.baseline_metrics.values():
            writer.writerow([
                m.paradigm,
                m.total_tx,
                m.valid_commits,
                m.safe_aborts,
                m.unsafe_commits,
                round(m.throughput_tps, 2),
                round(m.mean_latency_ms, 3),
                round(m.p50_latency_ms, 3),
                round(m.p95_latency_ms, 3),
                round(m.p99_latency_ms, 3),
                m.toctou_violations,
                m.ddi_leaks,
                m.deadlocks,
                m.false_stale_aborts,
                round(m.unsafe_commit_rate, 4),
                round(m.false_stale_rate, 4),
            ])


def main(args: list[str] | None = None) -> int:
    """Master benchmark CLI runner."""
    parser = argparse.ArgumentParser(
        description="GLHS Real Systems Concurrency & Governance Benchmark Harness"
    )
    parser.add_argument(
        "--suite",
        choices=["all", "baselines", "concurrency", "fault", "deadlock"],
        default="all",
        help="Benchmark suite to execute (default: all)",
    )
    parser.add_argument(
        "--num-txns",
        "--txns",
        dest="num_txns",
        type=int,
        default=500,
        help="Number of transactions for baseline workload (default: 500)",
    )
    parser.add_argument(
        "--workers",
        type=str,
        default="16",
        help="Comma-separated worker counts (default: 16)",
    )
    parser.add_argument(
        "--alphas",
        type=str,
        default="0.0,0.5,0.9,1.2",
        help="Comma-separated Zipfian skew alphas (default: 0.0,0.5,0.9,1.2)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL database connection URL (defaults to in-memory SQLite / simulator)",
    )
    parser.add_argument(
        "--output-json",
        "--output",
        "-o",
        dest="output_json",
        type=str,
        default=None,
        help="Path to export structured JSON report",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=None,
        help="Path to export CSV summary table",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )

    parsed_args = parser.parse_args(args)

    db_url = parsed_args.database_url
    is_postgres = bool(db_url and ("postgresql" in db_url or "postgres" in db_url))
    backend_mode = "PostgreSQL (Live Instance)" if is_postgres else "In-Memory SQLite / Simulated Coordinator"

    workers_list = [int(w.strip()) for w in parsed_args.workers.split(",") if w.strip()]
    primary_workers = workers_list[0] if workers_list else 16
    alphas_list = [float(a.strip()) for a in parsed_args.alphas.split(",") if a.strip()]

    report = MasterBenchmarkReport(
        timestamp_utc=datetime.now(UTC).isoformat(),
        backend_mode=backend_mode,
        database_url_configured=bool(db_url),
        num_txns=parsed_args.num_txns,
        concurrency_workers=primary_workers,
    )

    print("=" * 80)
    print("GLHS Systems Concurrency & Governance Benchmark Harness")
    print(f"Backend: {backend_mode}")
    print(f"Timestamp: {report.timestamp_utc}")
    print(f"Workload Size: {parsed_args.num_txns} transactions | Primary Concurrency: {primary_workers} workers")
    print("=" * 80)

    # 1. Baseline Suite
    if parsed_args.suite in ("all", "baselines"):
        print("\n[1/4] Executing Baseline Comparative Suite (5 Scenario Families)...")
        workload = generate_workload(count=parsed_args.num_txns, seed=parsed_args.seed)
        dist = validate_workload_distribution(workload)
        print(f"  Generated Workload Distribution: {dist}")

        metrics = run_baseline_suite(workload=workload, workers=primary_workers, db_url=db_url)
        report.baseline_metrics = metrics
        print("\n" + format_ascii_baseline_table(metrics))

    # 2. Concurrency Stress Suite
    if parsed_args.suite in ("all", "concurrency"):
        print("\n[2/4] Executing Multi-Threaded Concurrency & Zipfian Skew Grid...")
        stress_workers = workers_list if len(workers_list) > 1 else [1, 2, 4, 8, 16, 32, 64, 128]
        stress_alphas = alphas_list
        stress_report = run_concurrency_stress_grid(
            workers_list=stress_workers,
            alphas_list=stress_alphas,
            paradigms=["glhs_ss2pl", "standard_2pl", "standard_occ", "postgres_ssi"],
            tx_per_worker=30,
            db_url=db_url,
            seed=parsed_args.seed,
        )
        report.concurrency_stress = stress_report
        print(f"  Completed {stress_report.total_experiments} grid evaluations across W={stress_workers}, alpha={stress_alphas}")

    # 3. Fault & Recovery Suite
    if parsed_args.suite in ("all", "fault"):
        print("\n[3/4] Executing Fault Injection, Crash Abort & Ledger Audit Suite...")
        fault_suite = FaultInjectionSuite(db_url=db_url)
        fault_report = fault_suite.run_all_fault_tests()
        report.fault_recovery = fault_report
        print(f"  Fault Tests: {fault_report.passed_tests}/{fault_report.total_tests} passed | Ledger Audit: {fault_report.ledger_audit.verification_message}")

    # 4. Deadlock Analysis Suite
    if parsed_args.suite in ("all", "deadlock"):
        print("\n[4/4] Executing Wait-For Graph (WFG) Deadlock Verification Suite...")
        deadlock_res = run_deadlock_analysis(num_threads=primary_workers, num_txns=200, seed=parsed_args.seed)
        report.deadlock_analysis = deadlock_res
        for _k, d_rep in deadlock_res.items():
            print(f"  [{d_rep.paradigm}] Deadlocks Detected: {d_rep.deadlocks_detected} (Zero Deadlock Invariant Satisfied: {d_rep.zero_deadlock_invariant_satisfied})")

    # Output exports
    if parsed_args.output_json:
        json_path = Path(parsed_args.output_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\n[Artifact] Structured JSON report saved to: {json_path}")

    if parsed_args.output_csv:
        csv_path = Path(parsed_args.output_csv)
        export_csv_report(report, csv_path)
        print(f"[Artifact] CSV summary saved to: {csv_path}")

    print("\nBenchmark harness execution completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
