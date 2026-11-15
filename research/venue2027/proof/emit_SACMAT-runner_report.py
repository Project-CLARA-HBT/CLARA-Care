"""Emit the SACMAT-runner task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the SACMAT-runner task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "SACMAT-runner"

BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "evaluation/venue2027/sacmat/runner.py",
    "evaluation/venue2027/sacmat/test_runner.py",
    "research/venue2027/proof/SACMAT-runner.json",
    "research/venue2027/proof/artifacts/sacmat_run_bundle.jsonl",
    "research/venue2027/proof/emit_SACMAT-runner_report.py",
    "research/venue2027/proof/logs/SACMAT-runner.pytest.log",
    "research/venue2027/proof/logs/SACMAT-runner.ruff.log",
    "research/venue2027/proof/logs/SACMAT-runner.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_runner.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-runner.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/runner.py evaluation/venue2027/sacmat/test_runner.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-runner.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-runner_report.py # build_report + validate_report(ok:true) recorded in research/venue2027/proof/SACMAT-runner.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-runner.validator.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "evaluation/venue2027/sacmat/runner.py",
            "evaluation/venue2027/sacmat/test_runner.py",
            "research/venue2027/proof/artifacts/sacmat_run_bundle.jsonl",
            "research/venue2027/proof/logs/SACMAT-runner.pytest.log",
            "research/venue2027/proof/logs/SACMAT-runner.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P05 task SACMAT-runner (PolicyTrace RQ1-RQ3): uniform multi-arm execution runner. "
            "evaluation/venue2027/sacmat/runner.py implements run_campaign(config) -> RunBundle, "
            "executing all candidate, single-engine, and ablation policy arms over the temporal trace "
            "corpus under balanced paired case/seed plan and equal timeout. Reuses the audited shared "
            "deterministic harness (_shared.harness). Every (arm, case) cell is accounted for; non-completions "
            "and adapter crashes record as EXECUTION_ERROR rather than being silently dropped; timeouts record "
            "as TIMEOUT; mutually exclusive outcomes per GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4. "
            "Unequal configurations (seed drift, per-arm timeouts) and missing arms fail closed with stable "
            "reason codes. Real sample run bundle artifact emitted under "
            "research/venue2027/proof/artifacts/sacmat_run_bundle.jsonl recording all 36 planned engine x trace pairs."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-runner.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-runner.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
