"""Emit the DSN-X05_workflow_reference task proof report via agent_protocol.build_report."""

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
    "evaluation/venue2027/dsn/workflow_reference.py",
    "tests/venue2027/dsn/test_workflow_reference.py",
    "research/venue2027/proof/DSN-X05_workflow_reference.json",
    "research/venue2027/proof/logs/DSN-X05_workflow_reference.pytest.log",
    "research/venue2027/proof/logs/DSN-X05_workflow_reference.ruff.log",
    "research/venue2027/proof/logs/DSN-X05_workflow_reference.suite.log",
    "research/venue2027/proof/logs/DSN-X05_workflow_reference.testsdir.log",
    "research/venue2027/proof/logs/DSN-X05_workflow_reference.selfcheck.log",
    "research/venue2027/proof/logs/DSN-X05_workflow_reference.validator.log",
]

#: Artifacts hashed inside the report: the report itself and the validator log
#: are excluded (self-reference; the validator re-verifies them by existence).
ARTIFACTS = [p for p in CHANGED if not p.endswith("DSN-X05_workflow_reference.json")]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DSN-X05_workflow_reference",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q tests/venue2027/dsn/test_workflow_reference.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X05_workflow_reference.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dsn/workflow_reference.py "
                    "tests/venue2027/dsn/test_workflow_reference.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X05_workflow_reference.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X05_workflow_reference.suite.log",
            },
            {
                "argv": "python3 -m pytest -q tests/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X05_workflow_reference.testsdir.log",
            },
        ],
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_RUN_EXTERNAL",
        unresolved=[],
        notes=(
            "P03 task DSN-X05_workflow_reference (RQ3) for DSN 2027 (Recoverable Safety "
            "Journals for Crash-Consistent AI-Mediated Health-State Mutations): durable "
            "workflow/saga strong-baseline arm B2. Engine pinning: temporalio 1.19.0 "
            "(tag 1.19.0 -> commit 11e8650c7c8b89af45fab328e400d2fd5a9af16c via git "
            "ls-remote; PyPI License-Expression MIT verified 2026-11-15; matches "
            "research/venue2027/_shared/baselines/registry.yaml arm "
            "durable-workflow-saga-compensation) with unit runs on the Temporal "
            "test-server harness only (never a live service) and durability "
            "configuration WorkflowIDReusePolicy=REJECT_DUPLICATE keyed on the stable "
            "logical operation_id. TRUTHFUL ENGINE STATUS: the pinned SDK is NOT "
            "importable in this environment (probe_engine() -> installed=false, "
            "reason=WORKFLOW_ENGINE_UNAVAILABLE), so the engine arm was NOT executed; "
            "run_workflow(case, ctx) returns the first-class harness outcome "
            "NOT_RUN_EXTERNAL / WORKFLOW_ENGINE_UNAVAILABLE (counted_as_success=False, "
            "harness-invariant FALSE_ZERO_OUTCOME forbids counting it as success). NO "
            "real engine ran and NO result in this report is presented as an engine "
            "run; no comparative claim versus the engine is derivable. In-memory saga "
            "reference (run_saga_reference, dependency-free, deterministic, injected "
            "store, labelled IN_MEMORY_SAGA_REFERENCE in every detail string): three "
            "forward steps with declared compensations (reserve_slot/release_slot, "
            "apply_state/revert_state, emit_receipt/retract_receipt); forward failure "
            "compensates completed steps in strict reverse order "
            "(SAGA_COMPENSATED_ON_STEP_FAILURE); a failing compensation is an explicit "
            "non-retriable INDETERMINATE (SAGA_COMPENSATION_INDETERMINATE), never a "
            "silent success; pre_outbox_delivery interrupts before the delivery step "
            "and reports retriable INDETERMINATE (SAGA_INTERRUPTED_PENDING_RECOVERY); "
            "recovery replay under the same operation id resumes at the first "
            "not-applied step and dedups applied ones exactly-once "
            "(SAGA_RECOVERY_RESUMED / SAGA_RECOVERY_DEDUPED); pre_commit loses the "
            "journal write and reports a retriable REJECT with an empty store "
            "(SAGA_NOT_DURABLE_CRASH_BEFORE_WRITE). Fail-closed reason codes: "
            "SAGA_COMPENSATION_STEP_MISSING (incomplete definition refused BEFORE any "
            "journal write; missing-compensation + empty-catalog guards), "
            "CONTEXT_MALFORMED for bad ctx; malformed cases raise BaselineError via "
            "the shared baselines._validate_case schema (exact 5-key case contract, "
            "shared crash vocabulary). Tests tests/venue2027/dsn/test_workflow_reference"
            ".py: 20 tests (stdlib pytest only, no third-party deps, no DB/network) -- "
            "positive: engine identity pinned to the registry arm, truthful JSON-"
            "serializable probe, reverse-order compensation on step failure, first-step "
            "failure compensates nothing, clean commit, recovery resumption after "
            "interruption with exactly-once dedup, replay dedup over committed/running "
            "journals, IN_MEMORY_SAGA_REFERENCE label present on every saga outcome -- "
            "adversarial: missing compensation step detected before any execution "
            "(store untouched), empty saga catalog refused, engine-absent path returns "
            "NOT_RUN_EXTERNAL (never a fake success; FALSE_ZERO_OUTCOME harness "
            "invariant asserted), engine-absent outcome never conflated with the saga "
            "reference, failing compensation stays INDETERMINATE on replay, "
            "crash-before-write leaves nothing durable, malformed case/ctx wiring "
            "errors with stable codes. 20 passed in ~0.3s; full evaluation/venue2027 "
            "suite 1661 passed; full tests/venue2027 suite 148 passed; uvx ruff@0.7.1 "
            "check clean on both files; selfcheck log records probe installed=false "
            "and the engine-absent NOT_RUN_EXTERNAL outcome verbatim. "
            "source_sha_after records the base commit 5f97bc36 per sibling convention "
            "(DSN-X01/X02/X03/X06); the single task commit SHA is created immediately "
            "after this report and reported in the handoff. Baseline parity "
            "NOT_RUN_EXTERNAL: the pinned engine itself did not run in this "
            "environment (transparent status permitted by the blueprint; prevents any "
            "unsupported comparative claim). Dependencies: DSN-baselines PASS verified "
            "in research/venue2027/STATE/completion.json before start. Next ready "
            "tasks: none blocked by this task; DSN-X04_outbox_reference (sibling "
            "P03) remains open in its own worktree."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DSN-X05_workflow_reference.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-X05_workflow_reference",
    )
    log_path = REPO / "research/venue2027/proof/logs/DSN-X05_workflow_reference.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
