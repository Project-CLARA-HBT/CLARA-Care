"""Emit the SACMAT-X03_cedar_runner task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"

CHANGED = [
    "evaluation/venue2027/sacmat/cedar_runner.py",
    "research/venue2027/sacmat/tests/test_cedar_runner.py",
    "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.live_engine.log",
    "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.validator.log",
    "research/venue2027/proof/SACMAT-X03_cedar_runner.json",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="SACMAT-X03_cedar_runner",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/test_cedar_runner.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/cedar_runner.py "
                    "research/venue2027/sacmat/tests/test_cedar_runner.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.ruff.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/sacmat/cedar_runner.py "
                    "research/venue2027/sacmat/tests/test_cedar_runner.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.ruff.log",
            },
            {
                "argv": (
                    "python3 scripts/ops/eval_sacmat_x03_live_engine.py "
                    "(live upstream cedar-policy-cli 4.14.1 probe; log records "
                    "'cedar --version' output and the runner's "
                    "engine=cedar-upstream-cli verdicts on the synthetic corpus)"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.live_engine.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/sacmat/cedar_runner.py",
            "research/venue2027/sacmat/tests/test_cedar_runner.py",
            "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.ruff.log",
            "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.live_engine.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 task SACMAT-X03_cedar_runner (RQ3): real-engine Cedar runner for "
            "PolicyTrace. evaluation/venue2027/sacmat/cedar_runner.py implements "
            "the task signature evaluate_cedar(policy, trace, query) with honest "
            "engine detection: when a genuine upstream 'cedar' CLI is detected "
            "(pinned cedar-policy-cli 4.14.1 per the baselines.py registry row) "
            "the REAL binary decides via 'cedar authorize' (fixed argv, 0600-mode "
            "temp files, no shell, --request-validation false for the schema-free "
            "synthetic corpus) and the verdict is normalized to the portable "
            "four-valued oracle vocabulary; when no engine is detected the runner "
            "returns the first-class harness outcome NOT_RUN_EXTERNAL / "
            "BASELINE_UNAVAILABLE (counted_as_success=False) and NEVER substitutes "
            "a fabricated verdict. Engine spawn failure, unparseable engine output "
            "and policy parse errors all fail closed to INDETERMINATE with stable "
            "reason codes (ENGINE_EXECUTION_ERROR / ENGINE_MALFORMED_OUTPUT / "
            "CEDAR_POLICY_PARSE_ERROR) — never reinterpreted as safe-looking "
            "rejections. The faithful in-process adapter CedarPolicyPort is a "
            "clearly-labelled PORT over baselines.CedarPolicyEngine: every result "
            "carries engine='cedar-port' (upstream runs carry "
            "engine='cedar-upstream-cli'), backend and detail strings stating it "
            "is a port of the pinned v4.14.1 documented semantics and NOT an "
            "upstream execution, so a port result can never be reported as a "
            "genuine engine run. HONEST ENGINE STATUS: the REAL upstream Cedar "
            "engine (cedar-policy-cli v4.14.1, 'cedar --version' verified in "
            "live_engine.log) WAS installed via cargo during this task and the "
            "live probe ran the true binary end-to-end (PERMIT on an active "
            "delegation, DENY under forbid precedence after revocation); on "
            "engine-free environments the same code path returns NOT_RUN_EXTERNAL "
            "and the pytest live-engine control degrades to skip, never a faked "
            "pass. test_cedar_runner.py: 7 positive controls (port evaluates a "
            "policy set and returns a PERMIT verdict labelled cedar-port; port "
            "DENY after revocation; missing-entity NOT_APPLICABLE/DENY; injected "
            "upstream CLI PERMIT and DENY with upstream label; deterministic "
            "Cedar-shaped translation; live-engine control) and 10 adversarial "
            "controls (engine unavailable -> NOT_RUN_EXTERNAL with "
            "counted_as_success=False on both injected-None and emptied-PATH "
            "probes; unavailability never silently substituted by the port; spawn "
            "failure -> INDETERMINATE; garbage output -> INDETERMINATE; parse "
            "error -> INDETERMINATE; port vs upstream labels provably distinct on "
            "engine/backend/detail; malformed policy input and malformed query "
            "override raise CedarRunnerError with stable reason codes; version/"
            "label provenance declared). 17 passed in 0.33s with the real engine "
            "present (0 skipped); uvx ruff@0.7.1 check + format --check clean. "
            "source_sha_after records the task base commit 5f97bc36 per sibling "
            "convention; the single task commit SHA is created immediately after "
            "this report and reported in the handoff. Baseline parity "
            "NOT_APPLICABLE (adapter layer; the port reuses the independently "
            "tested baselines.CedarPolicyEngine semantics from SACMAT-baselines "
            "PASS). Dependency SACMAT-baselines PASS verified in "
            "STATE/completion.json before start. Next ready tasks: SACMAT-X04/"
            "X05 (OpenFGA/OPA real-engine adapters) per taskctl ready."
        ),
    )

    out_path = REPO / "research/venue2027/proof/SACMAT-X03_cedar_runner.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="SACMAT-X03_cedar_runner",
    )
    log_path = REPO / "research/venue2027/proof/logs/SACMAT-X03_cedar_runner.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
