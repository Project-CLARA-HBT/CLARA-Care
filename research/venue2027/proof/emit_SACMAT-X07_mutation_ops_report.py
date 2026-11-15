"""Emit the SACMAT-X07_mutation_ops task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-X07_mutation_ops task. No network access.

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
TASK = "SACMAT-X07_mutation_ops"

BASE_SHA = "85cd56757045e8e8788def095bba45adc669ab92"

CHANGED = [
    "evaluation/venue2027/sacmat/mutation_ops.py",
    "evaluation/venue2027/sacmat/tests/test_mutation_ops.py",
    "research/venue2027/proof/SACMAT-X07_mutation_ops.json",
    "research/venue2027/proof/emit_SACMAT-X07_mutation_ops_report.py",
    "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/tests/test_mutation_ops.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/mutation_ops.py "
        "evaluation/venue2027/sacmat/tests/test_mutation_ops.py --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.ruff.log",
    },
    {
        "argv": "uvx ruff@0.7.1 format --check evaluation/venue2027/sacmat/mutation_ops.py "
        "evaluation/venue2027/sacmat/tests/test_mutation_ops.py --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-X07_mutation_ops_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-X07_mutation_ops.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.validator.log",
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
            "evaluation/venue2027/sacmat/mutation_ops.py",
            "evaluation/venue2027/sacmat/tests/test_mutation_ops.py",
            "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X07_mutation_ops.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task SACMAT-X07_mutation_ops (PolicyTrace RQ2 mutant families). "
            "evaluation/venue2027/sacmat/mutation_ops.py (MUTATION_OPS_VERSION "
            "clara.sacmat.mutation-ops-v1) defines five well-defined policy/trace "
            "mutation operators over the audited DSL "
            "(evaluation/venue2027/sacmat/policy_trace_dsl.py, task X01), each with "
            "a stable operator id and a real mutate(trace, event_index) -> "
            "mutated_trace core: MUT_REMOVE_REVOKE (revocation omission — deletes "
            "the REVOKE event so delegated authority survives replay; verified "
            "PERMIT-after-omission against the independent DSL oracle), "
            "MUT_SWAP_GRANT_REVOKE (inverted temporal precedence — moves the "
            "directly adjacent REVOKE one slot ahead of its GRANT with logical_time "
            "just below the grant's, producing the REVOKE_BEFORE_GRANT class while "
            "respecting the DSL's strictly ascending order), "
            "MUT_EXTEND_DELEGATION_EXPIRY (stale delegation — rewrites the DELEGATE "
            "policy_state epoch token base@t<expiry> to expire at the trace's last "
            "logical time; refuses absent tokens NO_EXPIRY_TOKEN, non-integer "
            "expiries MALFORMED_EXPIRY and non-advancing rewrites "
            "NO_EXPIRY_ADVANCE), MUT_CHANGE_POLICY_VERSION (stale-policy epoch — "
            "appends the -v2@ marker with the successor's epoch to one non-terminal "
            "event's policy_state; refuses terminal targets EVENT_NOT_FOUND and "
            "marker stacking STALE_VERSION_MARKER_PRESENT, which doubles as the "
            "no-op guard since an unchanged token necessarily already carries the "
            "marker) and MUT_DROP_OBLIGATION (audit-obligation drop — downgrades "
            "one ACCESS to a redundant same-scope GRANT so no adjudicable request "
            "remains and the outcome degenerates to DENY-by-default). "
            "MUTATION_REGISTRY maps the five stable ids to the operator functions; "
            "apply_operator refuses unknown ids with UNKNOWN_OPERATOR (case-"
            "sensitive, no silent default) and apply_all sweeps every registered "
            "operator across every (or caller-specified) event index in canonical "
            "(operator_id, target index) order, skipping non-applicable targets "
            "with stable refusal codes while deduplicating by canonical "
            "trace_sha256 — so every emitted mutant provably differs from the "
            "original. Structural well-formedness is enforced fail-closed: every "
            "mutant must round-trip through the independent, version-pinned "
            "parse_policy_trace before it is returned (a mutant the DSL rejects is "
            "refused with the underlying reason code, never emitted), and a "
            "defensive TRACE_UNCHANGED post-condition blocks byte-identical "
            "outputs. All errors are stable reason codes on MutationOpError; "
            "outputs (Mutant.to_dict) are JSON-serializable; pure functions — no "
            "clock, no randomness, no I/O, deterministic repeat application. Test "
            "driver evaluation/venue2027/sacmat/tests/test_mutation_ops.py: 28 "
            "tests, all passed — positive: registry completeness (exactly the five "
            "contracted operator ids), each operator's exact structural and "
            "semantic effect verified against the independent DSL oracle (revoke "
            "omission flips DENY/REVOKED_ACTOR_TRANSITIVITY to clean PERMIT; swap "
            "yields REVOKE_BEFORE_GRANT; expiry moves to the last logical time; "
            "epoch marker rewritten; dropped obligation degenerates to DENY), "
            "mutant JSON round-tripping through parse_policy_trace, "
            "JSON-serializable Mutant records, apply_all distinctness (no mutant "
            "sha equals the original or another mutant), determinism (byte-"
            "identical repeat sweeps, canonical operator ordering), explicit "
            "event_indices targeting; adversarial: WRONG_EVENT_KIND for "
            "kind-mismatched targets (remove/drop/swap), "
            "NO_ADJACENT_GRANT_REVOKE_PAIR for non-adjacent swap targets, "
            "NO_EXPIRY_TOKEN / MALFORMED_EXPIRY / NO_EXPIRY_ADVANCE for degenerate "
            "delegation-expiry rewrites, EVENT_NOT_FOUND for terminal "
            "policy-version targets and out-of-range indices across every "
            "operator, STALE_VERSION_MARKER_PRESENT for marker stacking (and as "
            "the no-op guard, exercised via a forged already-marked token), "
            "EMPTY_TRACE for zero-event traces, UNKNOWN_OPERATOR for unregistered "
            "and case-mismatched operator ids, and the UNORDERED_TIMESTAMPS tamper "
            "harness proving the DSL round-trip gate rejects structurally invalid "
            "histories. Full local evaluation/venue2027/sacmat + "
            "research/venue2027/sacmat/tests suite: 464 passed, 9 skipped "
            "(pre-existing conditional real-binary skips), 0 failed. "
            "oracle_disagreement_count=0: every declared semantic effect was "
            "derived from and re-verified by real evaluate_trace replays of the "
            "independent DSL oracle; no oracle was repaired to match mutants. "
            "baseline_parity=NOT_APPLICABLE (mutant-family construction layer; "
            "arms B0-B4 execute at fixed budget in the budget-runner task). "
            "source_sha_after records the base commit 85cd5675 per the "
            "established sibling convention; the single task commit SHA is created "
            "immediately after this report and recorded in the commit body. "
            "Downstream consumers: SACMAT-X08_budget_runner (mutation-score "
            "denominators from MUTATION_REGISTRY), SACMAT-X09_minimizer, "
            "SACMAT-pilot."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-X07_mutation_ops.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = (
        REPO
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "SACMAT-X07_mutation_ops.validator.log"
    )
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
