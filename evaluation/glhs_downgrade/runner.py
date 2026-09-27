"""Execution runner for E03 Downgrade and Lineage Anti-Laundering Assurance.

Executes the frozen schedule corpus (300 schedules) across all 10 negative laundering
patterns and clean controls, recording every execution into an append-only,
tamper-evident hash-chained JSONL stream (`runs.jsonl`).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from evaluation.glhs_binding_component_ablation.observer import ExecutionRecord, Observer
from evaluation.glhs_downgrade.adapter import DowngradeAssuranceAdapter, ScheduleExecutionOutcome
from evaluation.glhs_downgrade.analyze import analyze_downgrade_results
from evaluation.glhs_downgrade.schedules import build_schedules_document

TOTAL_SCHEDULES_E03 = 300
TOTAL_EXECUTIONS_E03 = 300


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


def run_downgrade_experiment(
    *,
    protocol_path: Path,
    schedules_path: Path,
    output_dir: Path,
    backend: str = "isolated_sqlite",
    run_id: str = "GLHS-Q2-R2-20260928-R01",
) -> dict[str, Any]:
    """Execute the full 300-schedule E03 experiment and output raw/runs.jsonl."""
    output_dir = output_dir.resolve()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    runs_file = raw_dir / "runs.jsonl"

    if schedules_path.exists():
        schedules_data = json.loads(schedules_path.read_text(encoding="utf-8"))
        schedules = schedules_data.get("schedules", [])
    else:
        schedules_doc = build_schedules_document()
        schedules = schedules_doc["schedules"]

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    adapter = DowngradeAssuranceAdapter(engine)
    adapter.setup_schema()

    if runs_file.exists():
        runs_file.unlink()

    observer = Observer(runs_file)
    records: list[dict[str, Any]] = []

    for idx, sched in enumerate(schedules, start=1):
        outcome: ScheduleExecutionOutcome = adapter.execute_schedule(sched)

        rec = ExecutionRecord(
            run_id=run_id,
            schedule_id=sched["schedule_id"],
            arm=sched["pattern_code"],
            sequence=idx,
            admitted=outcome.admitted,
            rejection_reason_code=outcome.reason_code,
            snapshot_coordinates={
                "pattern_id": sched["pattern_id"],
                "pattern_code": sched["pattern_code"],
                "downgrade_success": outcome.downgrade_success,
                "domain": sched.get("domain", "medications"),
            },
            governance_coordinates={
                "purpose": sched.get("purpose", "self_care"),
                "task": sched.get("task", "medication_review"),
                "actor_role": sched.get("actor_role", "owner"),
                "duration_ns": outcome.duration_ns,
                "db_reads": outcome.db_reads,
                "db_writes": outcome.db_writes,
            },
            binding_check_applied=True,
            expected_admissibility=sched["expected_outcome"],
        )
        observer.append(rec)
        records.append({
            "schedule_id": rec.schedule_id,
            "pattern_id": sched["pattern_id"],
            "pattern_code": sched["pattern_code"],
            "sequence": rec.sequence,
            "admitted": rec.admitted,
            "downgrade_success": outcome.downgrade_success,
            "rejection_reason_code": rec.rejection_reason_code,
            "is_clean_control": sched.get("is_clean_control", False),
            "is_adversarial": sched.get("is_adversarial", True),
            "duration_ns": outcome.duration_ns,
            "expected_outcome": sched["expected_outcome"],
            "snapshot_coordinates": rec.snapshot_coordinates,
            "governance_coordinates": rec.governance_coordinates,
        })

    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8")) if protocol_path.exists() else {}
    summary = analyze_downgrade_results(records, protocol_data=protocol_data)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E03_downgrade/protocol.json"),
    )
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("protocols/E03_downgrade/schedules.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E03_downgrade"),
    )
    args = parser.parse_args()

    summary = run_downgrade_experiment(
        protocol_path=args.protocol,
        schedules_path=args.schedules,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
