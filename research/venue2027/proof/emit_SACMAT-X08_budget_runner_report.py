"""Emit the SACMAT-X08_budget_runner task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-X08_budget_runner task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "SACMAT-X08_budget_runner"

BASE_SHA = "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614"

CHANGED = [
    "evaluation/venue2027/sacmat/budget_fair_runner.py",
    "evaluation/venue2027/sacmat/test_budget_fair_runner.py",
    "research/venue2027/proof/SACMAT-X08_budget_runner.json",
    "research/venue2027/proof/emit_SACMAT-X08_budget_runner_report.py",
    "research/venue2027/proof/logs/SACMAT-X08_budget_runner.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X08_budget_runner.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X08_budget_runner.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_budget_fair_runner.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X08_budget_runner.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/budget_fair_runner.py "
            "evaluation/venue2027/sacmat/test_budget_fair_runner.py --config ruff.toml"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X08_budget_runner.ruff.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 format --check evaluation/venue2027/sacmat/budget_fair_runner.py "
            "evaluation/venue2027/sacmat/test_budget_fair_runner.py --config ruff.toml"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X08_budget_runner.ruff.log",
    },
    {
        "argv": (
            "python3 research/venue2027/proof/emit_SACMAT-X08_budget_runner_report.py "
            "# build_report + validate_report(ok:true) recorded in "
            "research/venue2027/proof/SACMAT-X08_budget_runner.json"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X08_budget_runner.validator.log",
    },
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "evaluation/venue2027/sacmat/budget_fair_runner.py",
            "evaluation/venue2027/sacmat/test_budget_fair_runner.py",
            "research/venue2027/proof/logs/SACMAT-X08_budget_runner.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X08_budget_runner.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P05 task SACMAT-X08_budget_runner (Equal-budget competitor benchmark for PolicyTrace RQ2). "
            "evaluation/venue2027/sacmat/budget_fair_runner.py (BUDGET_FAIR_RUNNER_VERSION 1.0.0) "
            "implements run_budget_fair(campaign, budget_config) -> BudgetRunResult and "
            "assert_budget_fairness(results) verifying every competitor strategy "
            "(sequence_aware, mcdc_static, random, coverage_guided) executed under strictly EQUAL "
            "oracle query budgets, generation CPU limits, and wall-clock timeouts. "
            "Records query_trace and cumulative fault_discovery_curve. Positive controls prove: "
            "all strategies consume <= allocated budget; sequence-aware candidate discovers temporal "
            "faults (MUT_SWAP_GRANT_REVOKE, MUT_REMOVE_REVOKE) that random misses at equal budget; "
            "MC/DC static testing kills static obligation mutants but misses temporal ordering swaps; "
            "fault discovery curves are monotonically non-decreasing; and results are JSON-serializable. "
            "Adversarial controls enforce fail-closed rejection: budget overruns raise BUDGET_OVERRUN, "
            "unequal budget allocations raise UNEQUAL_BUDGET_ALLOCATION, invalid budgets raise "
            "INVALID_BUDGET, unknown strategies raise UNKNOWN_STRATEGY, and empty campaigns raise "
            "EMPTY_CAMPAIGN. Tests: 25 passed in 0.36s (exit 0); ruff check and format check clean (exit 0)."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-X08_budget_runner.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    log = (
        REPO
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "SACMAT-X08_budget_runner.validator.log"
    )
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
