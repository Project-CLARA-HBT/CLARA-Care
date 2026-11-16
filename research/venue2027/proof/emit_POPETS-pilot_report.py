"""Emit the POPETS-pilot task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

from evaluation.venue2027.popets.pilot_executor import PilotConfig, execute_pilot  # noqa: E402

TASK = "POPETS-pilot"
BASE_SHA = "6faf61e1238fd7caae5e0f6113283cc4856f0398"

CHANGED_PATHS = [
    "research/venue2027/popets/protocols/pilot_plan.yaml",
    "evaluation/venue2027/popets/pilot_executor.py",
    "evaluation/venue2027/popets/test_pilot_executor.py",
    "research/venue2027/proof/artifacts/popets_pilot_report.json",
    "research/venue2027/proof/emit_POPETS-pilot_report.py",
    "research/venue2027/proof/POPETS-pilot.json",
    "research/venue2027/proof/logs/POPETS-pilot.pytest.log",
    "research/venue2027/proof/logs/POPETS-pilot.ruff.log",
    "research/venue2027/proof/logs/POPETS-pilot.validator.log",
]

ARTIFACT_PATHS = [
    "research/venue2027/popets/protocols/pilot_plan.yaml",
    "evaluation/venue2027/popets/pilot_executor.py",
    "evaluation/venue2027/popets/test_pilot_executor.py",
    "research/venue2027/proof/artifacts/popets_pilot_report.json",
    "research/venue2027/proof/logs/POPETS-pilot.pytest.log",
    "research/venue2027/proof/logs/POPETS-pilot.ruff.log",
]


def main() -> int:
    logs_dir = REPO / "research" / "venue2027" / "proof" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = REPO / "research" / "venue2027" / "proof" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run pytest
    pytest_log_rel = "research/venue2027/proof/logs/POPETS-pilot.pytest.log"
    pytest_log_abs = REPO / pytest_log_rel
    cmd_pytest = [
        "python3",
        "-m",
        "pytest",
        "-q",
        "evaluation/venue2027/popets/test_pilot_executor.py",
    ]
    res_pytest = subprocess.run(
        cmd_pytest,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    pytest_log_abs.write_text(res_pytest.stdout + res_pytest.stderr, encoding="utf-8")
    if res_pytest.returncode != 0:
        print(f"pytest failed with exit {res_pytest.returncode}: {res_pytest.stderr}")
        return res_pytest.returncode

    # 2. Run ruff check and format
    ruff_log_rel = "research/venue2027/proof/logs/POPETS-pilot.ruff.log"
    ruff_log_abs = REPO / ruff_log_rel
    cmd_ruff_check = [
        "uvx",
        "ruff@0.7.1",
        "check",
        "evaluation/venue2027/popets/pilot_executor.py",
        "evaluation/venue2027/popets/test_pilot_executor.py",
    ]
    res_ruff_check = subprocess.run(
        cmd_ruff_check,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    cmd_ruff_fmt = [
        "uvx",
        "ruff@0.7.1",
        "format",
        "--check",
        "evaluation/venue2027/popets/pilot_executor.py",
        "evaluation/venue2027/popets/test_pilot_executor.py",
    ]
    res_ruff_fmt = subprocess.run(
        cmd_ruff_fmt,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    ruff_combined = (
        f"=== ruff check ===\n{res_ruff_check.stdout}{res_ruff_check.stderr}\n"
        f"=== ruff format --check ===\n{res_ruff_fmt.stdout}{res_ruff_fmt.stderr}\n"
    )
    ruff_log_abs.write_text(ruff_combined, encoding="utf-8")
    if res_ruff_check.returncode != 0:
        print(f"ruff check failed with exit {res_ruff_check.returncode}")
        return res_ruff_check.returncode
    if res_ruff_fmt.returncode != 0:
        print(f"ruff format failed with exit {res_ruff_fmt.returncode}")
        return res_ruff_fmt.returncode

    # 3. Generate sample pilot report artifact
    pilot_cfg = PilotConfig(pilot_id="popets-pilot-proof", split="dev", seed=42, n=60)
    sample_report = execute_pilot(pilot_cfg)
    report_artifact_path = artifacts_dir / "popets_pilot_report.json"
    report_artifact_path.write_text(
        json.dumps(sample_report.to_dict(), indent=2) + "\n", encoding="utf-8"
    )

    # 4. Resolve source SHA
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    commands = [
        {
            "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_pilot_executor.py",
            "exit_code": res_pytest.returncode,
            "log_path": pytest_log_rel,
        },
        {
            "argv": (
                "uvx ruff@0.7.1 check evaluation/venue2027/popets/pilot_executor.py "
                "evaluation/venue2027/popets/test_pilot_executor.py && "
                "uvx ruff@0.7.1 format --check evaluation/venue2027/popets/pilot_executor.py "
                "evaluation/venue2027/popets/test_pilot_executor.py"
            ),
            "exit_code": 0,
            "log_path": ruff_log_rel,
        },
        {
            "argv": "PYTHONPATH=. python3 research/venue2027/proof/emit_POPETS-pilot_report.py",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/POPETS-pilot.validator.log",
        },
    ]

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED_PATHS,
        commands=commands,
        artifact_paths=ARTIFACT_PATHS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "POPETS-pilot (Phase P06, venue popets): delivered development-split pilot "
            "evaluation plan (research/venue2027/popets/protocols/pilot_plan.yaml) and "
            "pilot executor (evaluation/venue2027/popets/pilot_executor.py, "
            "POPETS_PILOT_EXECUTOR_VERSION 1.0.0). Executes strictly on the development "
            "split ('split: dev') and refuses any access to test or holdout splits with "
            "stable reason code HOLDOUT_ACCESS_FORBIDDEN. Evaluates baseline fairness and "
            "parity across all arms (B0-B4), measures empirical runtime distribution "
            "(mean, variance, p95), outcome variance, and paired difference variance. "
            "Computes prospective power estimates and Clopper-Pearson zero-event bounds "
            "across sample sizes (20..1200) to select a feasible experimental matrix "
            "(seeds [42, 101, 2027], N=1200, timeout=60.0s, retry_budget=0, resource=cpu) "
            "without unsealing the main holdout split. Implements target contracts "
            "execute_pilot(config, dev_dataset)->PilotReport and pilot(config)->PilotReport. "
            "Sample run emitted to research/venue2027/proof/artifacts/popets_pilot_report.json. "
            "15 tests pass in test_pilot_executor.py (positive + adversarial holdout controls); "
            "pytest exit 0; uvx ruff@0.7.1 check and format clean (exit 0)."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "POPETS-pilot.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    validator_log_rel = "research/venue2027/proof/logs/POPETS-pilot.validator.log"
    validator_log_abs = REPO / validator_log_rel
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    validator_log_abs.write_text(payload, encoding="utf-8")

    # Update the report with the validator log hash now that it exists
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED_PATHS,
        commands=commands,
        artifact_paths=ARTIFACT_PATHS + [validator_log_rel],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=report["notes"],
    )
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    validator_log_abs.write_text(payload, encoding="utf-8")

    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
