"""Emit the DSN-candidate task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "85cd56757045e8e8788def095bba45adc669ab92"

CHANGED = [
    "evaluation/venue2027/dsn/candidate.py",
    "evaluation/venue2027/dsn/test_candidate.py",
    "research/venue2027/proof/DSN-candidate.json",
    "research/venue2027/proof/logs/DSN-candidate.pytest.log",
    "research/venue2027/proof/logs/DSN-candidate.ruff.log",
    "research/venue2027/proof/logs/DSN-candidate.suite.log",
    "research/venue2027/proof/logs/DSN-candidate.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DSN-candidate",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_candidate.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-candidate.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dsn/candidate.py "
                    "evaluation/venue2027/dsn/test_candidate.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-candidate.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-candidate.suite.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dsn/candidate.py",
            "evaluation/venue2027/dsn/test_candidate.py",
            "research/venue2027/proof/logs/DSN-candidate.pytest.log",
            "research/venue2027/proof/logs/DSN-candidate.ruff.log",
            "research/venue2027/proof/logs/DSN-candidate.suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task DSN-candidate (DSN 2027, 'Recoverable Safety Journals for "
            "Crash-Consistent AI-Mediated Health-State Mutations', blueprint arm B3). "
            "evaluation/venue2027/dsn/candidate.py implements the isolated proposed "
            "mechanism: a per-operation hash-chained recoverable safety journal that is "
            "the durable authority for the decision lineage (INTENT / COMMIT / "
            "OUTBOX_RECORD / EFFECT_APPLIED / ABORT entries; prev-digest chaining with "
            "genesis 0*64; seq contiguity + digest recomputation in verify_journal). "
            "Typed JSON-serializable inputs/outputs (WriteIntent, JournalEntry, "
            "SafetyJournal, DurableStores, ExecutionReport, RecoveryOutcome); docstring "
            "carries the EXECUTE/RESUME/RECOVERABLE_OUTCOME pseudocode mapping 1:1 to "
            "the blueprint's method architecture (reconciler over clinical row + "
            "immutable decision receipt + asynchronous side-effect record, retries "
            "keyed to the immutable operation ID). Executor: append INTENT; consent "
            "recheck at commit (post-revocation epoch -> durable ABORT, DSN-CASE-05); "
            "COMMIT then idempotent row materialization; OUTBOX_RECORD; at-least-once "
            "delivery loop with WRITE-AHEAD effect records -- the effect is journaled "
            "before it is applied, duplicate deliveries dedupe against the journal "
            "(DSN-CASE-04), and a mid_effect crash is healed on resume by WAL-style "
            "replay of the journaled record into the durable store, so every crash "
            "window (pre_commit / post_commit_pre_response / pre_outbox_delivery / "
            "mid_effect) converges to COMMITTED with exactly one durable row write and "
            "one durable effect application. recoverable_outcome() is pure and never "
            "raises: corrupt chain (payload flip / forged digest / dropped interior "
            "entry / unknown kind), foreign shard entry, intent-binding mismatch, "
            "abort+commit contradiction, duplicate commits, effect-without-commit, "
            "divergent effect digests and unexpected internal errors all yield "
            "INDETERMINATE with a stable reason code -- never a positive outcome, never "
            "a coerced safe rejection; only durable proof of non-commit yields "
            "REJECTED (retriable empty picture, revocation aborts). Tail truncation is "
            "a legal crash prefix (COMMITTED_PENDING_DELIVERY), interior tampering is "
            "corruption (DSN-CASE-06). Mechanism-isolation ablation "
            "ablation_no_journal_execute() removes the journal (arm-B0 failure mode): "
            "no adjudication possible (recoverable_outcome_available=False) and the "
            "fire-and-forget consumer applies one effect per delivery (3 deliveries -> "
            "3 effects), proving the journal is the load-bearing component. "
            "run_candidate(case, ctx) -> shared harness Outcome maps COMMITTED->ADMIT / "
            "REJECTED->REJECT (counted) and INDETERMINATE->INDETERMINATE (never "
            "counted, including corruption-refused recovery); malformed cases fail "
            "closed with EXECUTION_ERROR + stable reason codes. Independence: the "
            "candidate imports neither the oracle module, the reference state machine, "
            "the reconciler, the baseline references nor any held-out label file -- "
            "asserted by AST scan in test_candidate.py and by a fresh-interpreter "
            "import; no wall clock, randomness, network, DB or provider access; "
            "synthetic digests only. 34 tests passed (exactly-once across 4 crash "
            "windows, broker-replay dedupe, revocation stability, 4 corruption modes "
            "-> INDETERMINATE, semantic contradictions, ablation leak, determinism, "
            "fail-closed wiring); full evaluation/venue2027/ suite 1883 passed; "
            "uvx ruff@0.7.1 check clean. source_sha_after records the worktree base "
            "85cd5675 per sibling convention (DSN-X06); the single task commit SHA is "
            "created immediately after this report and reported in the handoff. "
            "Baseline parity NOT_APPLICABLE (B1/B2 comparator execution lives in "
            "DSN-X03/X04/X05). Dependencies DSN-oracle and SH-psc_interface PASS "
            "verified in research/venue2027/STATE/completion.json before start. "
            "Candidate design only: no empirical claims, no measured rates."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DSN-candidate.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-candidate",
    )
    log_path = REPO / "research/venue2027/proof/logs/DSN-candidate.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
