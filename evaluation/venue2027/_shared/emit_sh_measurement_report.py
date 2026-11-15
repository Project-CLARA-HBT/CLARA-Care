"""Emit research/venue2027/proof/SH-measurement.json via agent_protocol.build_report.

Assembles the SH-measurement task report with real command logs (pytest, ruff,
emitter, validator) and hashes every declared artifact, then validates it with
agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "SH-measurement"
SOURCE_SHA_BEFORE = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"

CHANGED_PATHS = [
    "evaluation/venue2027/_shared/measurement.py",
    "evaluation/venue2027/_shared/test_measurement.py",
    "evaluation/venue2027/_shared/emit_metrics_sample.py",
    "evaluation/venue2027/_shared/emit_sh_measurement_report.py",
    "research/venue2027/proof/artifacts/metrics_sample.json",
    "research/venue2027/proof/logs/SH-measurement.pytest.log",
    "research/venue2027/proof/logs/SH-measurement.ruff.log",
    "research/venue2027/proof/logs/SH-measurement.emit.log",
    "research/venue2027/proof/logs/SH-measurement.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/_shared/measurement.py",
    "evaluation/venue2027/_shared/test_measurement.py",
    "evaluation/venue2027/_shared/emit_metrics_sample.py",
    "evaluation/venue2027/_shared/emit_sh_measurement_report.py",
    "research/venue2027/proof/artifacts/metrics_sample.json",
    "research/venue2027/proof/logs/SH-measurement.pytest.log",
    "research/venue2027/proof/logs/SH-measurement.ruff.log",
    "research/venue2027/proof/logs/SH-measurement.emit.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/_shared/test_measurement.py"
                        " evaluation/venue2027/_shared/test_harness.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SH-measurement.pytest.log",
            },
            {
                "argv": "ruff check evaluation/venue2027/_shared/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SH-measurement.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 evaluation/venue2027/_shared/emit_metrics_sample.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SH-measurement.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "SH-measurement measurement standard over raw run bundles: "
            "measure(bundle, require=..., latency_unit='s') -> Metrics (v1.0.0) computing, from raw "
            "records only: mutually exclusive outcome counts (admit/reject/indeterminate/not_run/"
            "timeout/execution_error + harness invalid_result kept visible), explicit denominator "
            "(planned/attempted/missing/attempted_total), forbidden-commit rate (oracle truth vs "
            "observed ADMIT, predeclared denominator), false-stale rate (observed REJECT vs oracle "
            "ADMIT), throughput as committed ops / busy seconds (sum of per-record durations, "
            "benchmark overhead excluded), latency p50/p95/p99 via exact nearest-rank order "
            "statistics, and retry amplification from attempt_index. "
            "assert_denominator_consistency(bundle) proves counts partition the planned total "
            "(bucket sum == record count, unique pair identity, attempted+missing == planned, "
            "manifest denominator_total == recount). "
            "Metrics whose required records are missing are refused with stable reason codes "
            "(MISSING_RECORDS / ORACLE_VERDICT_MISSING / NO_DENOMINATOR / MIXED_TIME_UNITS / "
            "MALFORMED_DURATION / MALFORMED_RECORD) and listed in Metrics.unavailable — never "
            "invented as zeros; require=(...) escalates to MeasurementError. "
            "Real artifact metrics_sample.json computed from the committed 6-pair "
            "run_bundle_sample.jsonl: admit=2 reject=2 indeterminate=1 execution_error=1, "
            "denominator 6/6 planned=attempted, forbidden_commit_rate=0.0 (0/6, oracle-derived), "
            "false_stale_rate=0.0, throughput=2 admits / 8e-6 busy s, latency p50=3e-06 s "
            "p95=p99=5e-06 s (n=6, unit s); retry_amplification correctly UNAVAILABLE "
            "(MISSING_RECORDS) because the harness records no attempt fields — not defaulted to "
            "1.0. 32 positive+adversarial tests (mixed time units rejected for p99, dropped pair / "
            "lying manifest / duplicate pair refused with DENOMINATOR_MISMATCH, absent metrics "
            "never fabricated as zero, sleep benchmark plausible latency); 47 tests pass with the "
            "harness suite; ruff clean."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "SH-measurement.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log
    # OUTSIDE the report's own artifact set (a log describing the validation
    # of the report cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "SH-measurement.validator.log"
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
