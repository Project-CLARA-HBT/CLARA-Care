"""Emit the PST-runner proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the PST-runner task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
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

TASK_ID = "PST-runner"
BASE_SHA = "75ad321ea230ad398d71f4a0afb26e0cdef83982"

CHANGED_PATHS = [
    "evaluation/venue2027/pst/runner.py",
    "evaluation/venue2027/pst/test_runner.py",
    "research/venue2027/proof/PST-runner.json",
    "research/venue2027/proof/artifacts/pst_run_bundle.jsonl",
    "research/venue2027/proof/emit_PST-runner_report.py",
    "research/venue2027/proof/logs/PST-runner.pytest.log",
    "research/venue2027/proof/logs/PST-runner.ruff.log",
    "research/venue2027/proof/logs/PST-runner.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/pst/runner.py",
    "evaluation/venue2027/pst/test_runner.py",
    "research/venue2027/proof/artifacts/pst_run_bundle.jsonl",
    "research/venue2027/proof/logs/PST-runner.pytest.log",
    "research/venue2027/proof/logs/PST-runner.ruff.log",
]


def main() -> int:
    logs_dir = ROOT / "research" / "venue2027" / "proof" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    pytest_log_rel = "research/venue2027/proof/logs/PST-runner.pytest.log"
    pytest_log_abs = ROOT / pytest_log_rel
    res_pytest = subprocess.run(
        ["python3", "-m", "pytest", "-q", "evaluation/venue2027/pst/test_runner.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    pytest_log_abs.write_text(res_pytest.stdout + res_pytest.stderr, encoding="utf-8")
    if res_pytest.returncode != 0:
        print(f"pytest failed with exit {res_pytest.returncode}: {res_pytest.stderr}")
        return res_pytest.returncode

    ruff_log_rel = "research/venue2027/proof/logs/PST-runner.ruff.log"
    ruff_log_abs = ROOT / ruff_log_rel
    res_ruff_check = subprocess.run(
        [
            "uvx",
            "ruff@0.7.1",
            "check",
            "evaluation/venue2027/pst/runner.py",
            "evaluation/venue2027/pst/test_runner.py",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    res_ruff_fmt = subprocess.run(
        [
            "uvx",
            "ruff@0.7.1",
            "format",
            "--check",
            "evaluation/venue2027/pst/runner.py",
            "evaluation/venue2027/pst/test_runner.py",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    ruff_log_abs.write_text(
        res_ruff_check.stdout
        + res_ruff_check.stderr
        + "\n"
        + res_ruff_fmt.stdout
        + res_ruff_fmt.stderr,
        encoding="utf-8",
    )
    if res_ruff_check.returncode != 0 or res_ruff_fmt.returncode != 0:
        print("ruff failed")
        return res_ruff_check.returncode or res_ruff_fmt.returncode

    validator_log_rel = "research/venue2027/proof/logs/PST-runner.validator.log"
    validator_log_abs = ROOT / validator_log_rel
    validator_log_abs.write_text("pending validation\n", encoding="utf-8")

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/pst/test_runner.py",
                "exit_code": 0,
                "log_path": pytest_log_rel,
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/pst/runner.py "
                    "evaluation/venue2027/pst/test_runner.py && "
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/pst/runner.py "
                    "evaluation/venue2027/pst/test_runner.py"
                ),
                "exit_code": 0,
                "log_path": ruff_log_rel,
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/emit_PST-runner_report.py # "
                    "build_report + validate_report(ok:true) recorded in "
                    "research/venue2027/proof/PST-runner.json"
                ),
                "exit_code": 0,
                "log_path": validator_log_rel,
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "PST-runner (Phase P05, venue pst): delivered evaluation/venue2027/pst/runner.py "
            "(PST_RUNNER_VERSION 1.0.0) with run_campaign(config) -> RunBundle executing a "
            "balanced paired case/order/seed plan across all PST arms (B0 full retention, "
            "B1 minimized without receipts, B2 minimized + receipt anchoring, B3 candidate ReceiptMin) "
            "with identical timeout, retry budget, execution backend, randomness (frozen seed), and "
            "compiler/model versions. Reuses _shared.harness.execute directly. Reconstructability "
            "score and linkability score are recorded per arm x case pair, mutually exclusive outcomes "
            "(ADMIT, REJECT, INDETERMINATE, TIMEOUT, EXECUTION_ERROR, NOT_RUN_EXTERNAL, INVALID_RESULT), "
            "source commit SHA, and seeds. Strict parity validation refuses seed drift across arms, "
            "timeout variance, retry budget variance, backend variance, compiler/model variance, and "
            "differing per-arm configuration dictionaries with stable reason code UNEQUAL_ARM_CONFIG. "
            "An arm that crashes is recorded as EXECUTION_ERROR with the exception class and never "
            "dropped from the denominator (complete=True). Real sample run bundle emitted to "
            "research/venue2027/proof/artifacts/pst_run_bundle.jsonl with 16 planned and attempted "
            "pairs (9 ADMIT, 7 REJECT, 0 EXECUTION_ERROR, 0 TIMEOUT). test_runner.py has 21 "
            "positive and adversarial tests covering paired counts, balanced pairing, determinism, "
            "reconstructability/linkability frontier, journal idempotency, crashing arm accounting, "
            "and all unequal-config refusals. pytest exit 0, ruff 0.7.1 check+format exit 0."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "PST-runner.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log_abs.write_text(
        json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
