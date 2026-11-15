"""Emit the DSN-baselines proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the DSN-baselines task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "DSN-baselines"

BASE_SHA = "6fe5fe193a5a55f456f163a853c1b2c41c0c869f"

CHANGED = [
    "evaluation/venue2027/dsn/baselines.py",
    "evaluation/venue2027/dsn/test_baselines.py",
    "research/venue2027/proof/DSN-baselines.json",
    "research/venue2027/proof/emit_dsn_baselines_report.py",
    "research/venue2027/proof/logs/DSN-baselines.pytest.log",
    "research/venue2027/proof/logs/DSN-baselines.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_baselines.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-baselines.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/dsn/baselines.py "
        "evaluation/venue2027/dsn/test_baselines.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-baselines.ruff.log",
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
            "evaluation/venue2027/dsn/baselines.py",
            "evaluation/venue2027/dsn/test_baselines.py",
        ],
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 baseline fidelity adapters for DSN 2027 (Recoverable Safety Journals "
            "for Crash-Consistent AI-Mediated Health-State Mutations). "
            "evaluation/venue2027/dsn/baselines.py implements run_baseline(baseline_id, "
            "case, ctx) -> Outcome (harness Outcome: observed_outcome in "
            "ADMIT/REJECT/INDETERMINATE/NOT_RUN_EXTERNAL, retriable flag) plus "
            "BASELINE_REGISTRY (typed BaselineSpec rows: provenance, registry name, "
            "runnability, notes) and refuse_constant_stub, over SYNTHETIC crash-window "
            "cases ({case_id, operation_id, crash_point, delivery_schedule, "
            "consent_epoch}; deterministic logical time, no hidden clock, no "
            "randomness, no network, no live provider, no real PHI/PII; injected "
            "BaselineContext.store dict as the in-process durable store, fresh per "
            "case so arms never share state). Arms: B0-single-write (bare durable "
            "write + fire-and-forget side effect, no journal — crash before the "
            "write loses the operation, crash after the commit orphans the side "
            "effect and a blind retry re-applies it: duplicate); B1-outbox-idempotent "
            "(row + transactional outbox + idempotency key in one durable "
            "transaction; retries and duplicate deliveries dedup on the key and "
            "re-ack without re-applying); B3-fsync (per-channel fsync discipline "
            "without an atomic multi-channel commit — the acknowledged-row/"
            "side-effect-pre-WAL window still loses the side effect and the arm "
            "reports it honestly as a lost side effect, never a phantom success); "
            "B4-candidate-journal (write-ahead journal entry durable BEFORE any "
            "channel write; recovery replays the journal and dedups by immutable "
            "operation id = exactly-once across the crash window); "
            "B5-monotonic-journal (B4 plus a monotonic sequence watermark; recovery "
            "rejects stale journal entries behind the watermark, non-retriably). "
            "Pinned external arm B2-durable-workflow (durable workflow/saga engine, "
            "registry ORIGINAL_UPSTREAM row durable-workflow-saga) is NOT_RUN_EXTERNAL "
            "with BASELINE_UNAVAILABLE: the pinned engine version and its parity "
            "fixture are absent from this worktree, so no toy substitution under the "
            "pinned name (EXECUTION_CONTRACT rule 8). Fail-closed contract: malformed "
            "cases/contexts and unknown baseline ids raise BaselineError with stable "
            "reason codes (wiring errors, never silently counted outcomes); "
            "crash-before-WAL yields REJECT + retriable + counted_as_success=False on "
            "every in-process arm (never a phantom success); extra case keys "
            "(including reason_code-like leak attempts) are refused. Core P03 "
            "separation asserted in tests: after the post-commit crash window, B4 "
            "recovery replay dedups to exactly-once (RC_JOURNAL_REPLAY_DEDUP) while "
            "B0's blind retry re-applies the orphaned write (duplicate) and B3 "
            "reports the lost side effect. refuse_constant_stub replays paired "
            "clean/crashed probe cases differing only in crash point and refuses a "
            "candidate whose (outcome, reason) signature is identical across the "
            "pair (CONSTANT_STUB_REFUSED) while admitting a crash-sensitive adapter "
            "(STUB_SEPARATION_OK). Machine-checked: 31 new tests pass (positive: "
            "registry coverage, clean-run commit per arm, B1 idempotent-consumer "
            "replay dedup, B4-vs-B0/B3 exactly-once contrast, B4 pre-outbox-crash "
            "replay dedup, B5 stale-entry guard, determinism; adversarial: "
            "crash-before-WAL never counted as success on any arm, constant-stub "
            "refusal, crash-sensitive admission, NOT_RUN_EXTERNAL arm, unknown "
            "baseline id / non-mapping case / missing-unknown-badly-typed fields / "
            "malformed context wiring errors); full evaluation/venue2027/dsn suite "
            "113 passed; ruff@0.7.1 check clean on touched files. source_sha_after = "
            "base SHA per established repo convention (proof report committed "
            "together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "DSN-baselines.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
