"""Execution runner for E02 Minimal Alternative Binding Baseline.

Executes the frozen schedule corpus (352 schedules x 4 arms = 1,408 executions)
across GLHS_B111, MIN_READSET_TOKEN, HMAC_READSET_TOKEN, and B000, recording every
execution into an append-only, tamper-evident hash-chained stream (runs.jsonl).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from evaluation.comparator_studies.minimal_readset_token.analyze import (
    analyze_minimal_token_results,
)
from evaluation.comparator_studies.minimal_readset_token.postgres_adapter import (
    DEFAULT_HMAC_SECRET,
    E02_ARMS,
    MinReadsetTokenPostgresAdapter,
    ScheduleExecutionOutcome,
)
from evaluation.glhs_binding_component_ablation.observer import ExecutionRecord, Observer

TOTAL_SCHEDULES_E02 = 352
TOTAL_EXECUTIONS_E02 = 1408


def _git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return res.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def run_minimal_token_experiment(
    *,
    protocol_path: Path,
    schedules_path: Path,
    output_dir: Path,
    backend: str = "sqlite",
    run_id: str = "GLHS-Q2-R2-20260928-R01",
) -> dict[str, Any]:
    """Execute the full 352-schedule E02 experiment and output artifacts."""
    output_dir = output_dir.resolve()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    runs_file = raw_dir / "runs.jsonl"

    schedules_data = json.loads(schedules_path.read_text(encoding="utf-8"))
    schedules = schedules_data.get("schedules", [])

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    adapter = MinReadsetTokenPostgresAdapter(engine, secret_key=DEFAULT_HMAC_SECRET)
    adapter.setup_schema()

    if runs_file.exists():
        runs_file.unlink()

    observer = Observer(runs_file)
    records: list[dict[str, Any]] = []
    sequence = 0

    for sched in schedules:
        for arm in E02_ARMS:
            sequence += 1
            outcome: ScheduleExecutionOutcome = adapter.execute_schedule(sched, arm=arm)

            rec = ExecutionRecord(
                run_id=run_id,
                schedule_id=sched["schedule_id"],
                arm=arm,
                sequence=sequence,
                admitted=outcome.admitted,
                rejection_reason_code=outcome.reason_code,
                snapshot_coordinates={
                    "source_snapshot_id": sched.get("snapshot_fields", {}).get("source_snapshot_id", "SNAP-ORIG-001"),
                    "metadata_bytes": outcome.metadata_bytes,
                },
                governance_coordinates={
                    "purpose": sched.get("context", {}).get("purpose", "self_care"),
                    "task": sched.get("context", {}).get("task", "monitoring_repeat"),
                    "actor_role": sched.get("context", {}).get("actor_role", "owner"),
                    "duration_ns": outcome.duration_ns,
                    "db_reads": outcome.db_reads,
                    "db_writes": outcome.db_writes,
                },
                binding_check_applied=arm != "B000",
                expected_admissibility=sched["expected_admissibility"],
            )
            observer.append(rec)
            records.append({
                "schedule_id": rec.schedule_id,
                "family_name": sched.get("family_name", "CLEAN"),
                "arm": rec.arm,
                "sequence": rec.sequence,
                "admitted": rec.admitted,
                "rejection_reason_code": rec.rejection_reason_code,
                "is_clean_control": sched.get("family_name") == "CLEAN",
                "is_adversarial": sched.get("family_name") != "CLEAN",
                "metadata_bytes": outcome.metadata_bytes,
                "duration_ns": outcome.duration_ns,
                "expected_admissibility": rec.expected_admissibility,
                "snapshot_coordinates": rec.snapshot_coordinates,
                "governance_coordinates": rec.governance_coordinates,
            })

    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8")) if protocol_path.exists() else {}
    summary = analyze_minimal_token_results(records)
    summary["protocol"] = protocol_data
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


run_experiment = run_minimal_token_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E02_minimal_baseline/protocol.json"),
    )
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("protocols/E01_binding_components/schedules.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E02_minimal_baseline"),
    )
    args = parser.parse_args()

    summary = run_minimal_token_experiment(
        protocol_path=args.protocol,
        schedules_path=args.schedules,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
