"""Emit research/venue2027/proof/DSN-X01_state_spec.json via agent_protocol.build_report.

Records source_sha_before/after = base commit 06125d52 (sibling convention: the
report's SHAs precede the single task commit that carries the report, as in
DSN-dataset/ACNS-X01). Validates the assembled report with validate_report.
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "research" / "venue2027" / "_shared" / "tools"))

import agent_protocol  # noqa: E402

TASK_ID = "DSN-X01_state_spec"
BASE_SHA = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

REPORT_PATH = REPO / "research" / "venue2027" / "proof" / "DSN-X01_state_spec.json"
ARTIFACTS = (
    "evaluation/venue2027/dsn/state_machine.py",
    "evaluation/venue2027/dsn/test_state_machine.py",
)
COMMANDS = (
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_state_machine.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-X01_state_spec.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/dsn/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-X01_state_spec.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DSN-X01_state_spec.suite.log",
    },
)


def main() -> int:
    report = agent_protocol.build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=[
            *ARTIFACTS,
            "research/venue2027/proof/DSN-X01_state_spec.json",
            "research/venue2027/proof/logs/DSN-X01_state_spec.pytest.log",
            "research/venue2027/proof/logs/DSN-X01_state_spec.ruff.log",
            "research/venue2027/proof/logs/DSN-X01_state_spec.suite.log",
        ],
        commands=list(COMMANDS),
        artifact_paths=list(ARTIFACTS),
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 task DSN-X01_state_spec for DSN 2027 (Recoverable Safety Journals for "
            "Crash-Consistent AI-Mediated Health-State Mutations, RQ1). "
            "state_machine.py implements the recoverable outcome function over the "
            "3-way durable state (committed clinical row, versioned decision receipt "
            "ledger, transactional outbox with partial-effect delivery receipts) with "
            "logical timestamps: evaluate_durability(write_intent, durable_state) -> "
            "DurabilityVerdict returns exactly one of COMMITTED/REJECTED/INDETERMINATE "
            "with a stable reason code (33-code registry) for every (intent, state) "
            "pair. Fail-closed invariants: durable success is NEVER inferred without a "
            "decision receipt bound to the committed clinical row (row without receipt "
            "-> ORPHAN_RECEIPT_NO_CLINICAL_ROW, INDETERMINATE), an HTTP response/ACK is "
            "never durable evidence, disagreeing channels are never coerced into a safe "
            "rejection, and an unexpected internal error yields "
            "INDETERMINATE/INTERNAL_EVALUATION_ERROR via a final guard instead of "
            "raising. Windows covered per CASE_MATRIX: DSN-CASE-01 nominal "
            "all-channels-agree -> COMMITTED (EFFECT_APPLIED); DSN-CASE-02 crash before "
            "WAL commit (all channels ABSENT) -> REJECTED "
            "NOT_COMMITTED_NO_DURABLE_EVIDENCE (no phantom success); DSN-CASE-03 crash "
            "after commit before ACK -> COMMITTED PENDING_DELIVERY (retry reconciles by "
            "immutable operation ID, unknown-response reconciliation); DSN-CASE-04 "
            "broker replay x3 identical effect digests -> COMMITTED "
            "DUPLICATE_DELIVERY_IDEMPOTENT with all deliveries recorded; DSN-CASE-05 "
            "consent revoked between authorization and commit (row stamped with "
            "post-revocation epoch) -> REJECTED FORBIDDEN_WRITE_POST_REVOCATION; "
            "DSN-CASE-06 corrupted signed receipt (stored transition digest != row "
            "digest) -> INDETERMINATE RECEIPT_DIGEST_MISMATCH (tamper flagged, never "
            "silent success); DSN-CASE-07 outbox delayed (no delivery yet) -> COMMITTED "
            "PENDING_DELIVERY (storage commit separated from downstream delivery); "
            "stale receipt (row_version behind committed row) -> INDETERMINATE "
            "STALE_RECEIPT_VERSION_MISMATCH; plus outbox fsync failure record -> "
            "REJECTED, torn clinical row / corrupt ledger / corrupt outbox -> "
            "INDETERMINATE, orphan ledger receipt without row -> INDETERMINATE (never a "
            "rejection licensing a duplicate effect), orphan outbox without row -> "
            "INDETERMINATE, divergent duplicate effect digests -> INDETERMINATE "
            "DUPLICATE_EFFECT_DIVERGENCE, delivery/commit/receipt timestamp anomalies "
            "-> INDETERMINATE, receipt decision conflict -> REJECTED, epoch-from-future "
            "-> INDETERMINATE, cross-channel operation mismatch -> INDETERMINATE, "
            "malformed intent/state (incl. ABSENT-carrying-payload) -> INDETERMINATE. "
            "recover(history: EventHistory) -> RecoveryVerdict folds ordered crash "
            "episodes (WRITE_INTENT/CRASH/DURABLE_STATE/DELIVER/EVALUATION events over "
            "4 crash points mirroring CASE_MATRIX): replays at-least-once DELIVER "
            "events into the outbox channel, preserves recorded evaluations, and fails "
            "closed on incomplete histories (no intent/state), unknown event kinds, "
            "unknown crash points, malformed events and conflicting intents "
            "(HISTORY_INCOMPLETE / UNKNOWN_HISTORY_EVENT / MALFORMED_HISTORY_EVENT / "
            "STATE_OPERATION_MISMATCH). Pure functions: logical timestamps only, no "
            "clock/randomness/I/O/provider; typed dataclasses are JSON-serializable "
            "with to_dict/from_dict round-trips verified; retries keyed by stable "
            "operation ID are idempotent (identical verdict digests). Tests: 48 "
            "passed (14 positive incl. determinism/idempotence/round-trip/registry, "
            "34 adversarial+history incl. all four required crash windows, duplicate "
            "delivery, stale receipt, tamper, governance race, fail-closed fold). "
            "Shared evaluation suite regression: 679 passed. uvx ruff@0.7.1 check "
            "clean. source_sha_after records the base commit 06125d52 per sibling "
            "convention (DSN-dataset); the single task commit SHA is created "
            "immediately after this report and recorded in the commit body. Oracle "
            "independence preserved: the test module imports only the module under "
            "test; no candidate runtime, DB, model or live provider involved."
        ),
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = agent_protocol.validate_report(
        report,
        repo=REPO,
        expected_task_id=TASK_ID,
        verify_artifacts=True,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
