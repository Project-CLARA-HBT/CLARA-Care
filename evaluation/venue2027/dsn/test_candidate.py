"""Tests for DSN-candidate — recoverable safety journal (arm B3).

Positive controls (mechanism works, commit exactly once across crash windows):
- Nominal episode: one journal COMMIT, one row write, one effect, verdict
  COMMITTED (CASE_MATRIX DSN-CASE-01).
- Every crash window (pre_commit, post_commit_pre_response,
  pre_outbox_delivery, mid_effect) followed by resume on the surviving journal
  converges to COMMITTED with exactly one durable row write and one durable
  effect application (DSN-CASE-02/03/04/07 semantics).
- Broker replay (three deliveries of the same message) dedupes against the
  journaled write-ahead effect record: one effect, all deliveries recorded.
- Revocation interleaving: consent epoch moves before the commit -> durable
  ABORT -> REJECTED, no row write, no effect, and a resumed episode stays
  stably rejected (DSN-CASE-05).

Adversarial controls (fail closed):
- Every interior corruption mode (payload flip, forged digest, dropped
  interior entry, unknown kind) yields INDETERMINATE with JOURNAL_CORRUPT —
  never COMMITTED, never a coerced safe rejection (DSN-CASE-06).
- A dropped LAST entry (legal prefix / crash window) still resumes to
  COMMITTED, distinguishing truncation from tampering.
- Cross-channel semantic contradictions (effect-without-commit, abort+commit,
  duplicate commits, divergent effect digests, foreign shard entries,
  mismatched intent binding) are INDETERMINATE.
- Recovery on a corrupted journal is refused by the executor without mutating
  durable stores (JOURNAL_CORRUPT), and run_candidate maps it to
  INDETERMINATE / never counted.
- Ablation (journal removed) cannot adjudicate and applies one effect per
  delivery (duplicate side effects under replay).
- Determinism: identical cases produce byte-identical detail JSON; malformed
  cases fail closed with EXECUTION_ERROR and stable reason codes.

Independence assertion: candidate.py statically imports neither the oracle
module, the reference state machine, the reconciler, nor any held-out label
file (AST scan over the module source), and imports cleanly in a fresh
interpreter process.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation.venue2027.dsn import candidate as cand
from evaluation.venue2027.dsn.candidate import (
    ABLATION_ID,
    ABORT,
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    COMMIT,
    EFFECT_APPLIED,
    INTENT,
    OUTBOX_RECORD,
    CandidateError,
    DurableStores,
    SafetyJournal,
    WriteIntent,
    ablation_no_journal_execute,
    corrupt_journal,
    describe_mechanism,
    execute_operation,
    recoverable_outcome,
    run_candidate,
    verify_journal,
)

OP_ID = "op:w12-dsn-candidate-0001"
OTHER_OP_ID = "op:w12-dsn-candidate-other"
PAYLOAD = "a" * 64
OTHER_PAYLOAD = "b" * 64
EPOCH = 3
ISSUED_AT = 10

FORBIDDEN_IMPORT_FRAGMENTS: tuple[str, ...] = (
    "independent_oracle",
    "state_machine",
    "reconcile_journal",
    "oracle_kernel",
    "outbox_reference",
    "workflow_reference",
    "baselines",
)

_FORBIDDEN_LABEL_FILES: tuple[str, ...] = (
    "truth.json",
    "case.json",
    "observed.json",
    "labels",
    "holdout",
)


def _intent(
    operation_id: str = OP_ID,
    epoch: int = EPOCH,
    payload: str = PAYLOAD,
    issued: int = ISSUED_AT,
) -> WriteIntent:
    return WriteIntent(
        operation_id=operation_id,
        tenant_id="synthetic-tenant",
        principal_id="synthetic-actor",
        purpose="self_care",
        authorized_consent_epoch=epoch,
        payload_digest_sha256=payload,
        issued_logical_time=issued,
    )


def _case(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "case_id": "DSN-CASE-01",
        "operation_id": OP_ID,
        "authorized_consent_epoch": EPOCH,
        "delivery_schedule": [1],
    }
    base.update(overrides)
    return base


def _run_full_episode(
    intent: WriteIntent,
    crash_point: str,
    schedule: tuple[int, ...] = (1,),
    epoch_at_commit: int | None = None,
) -> tuple[cand.ExecutionReport, cand.ExecutionReport, DurableStores]:
    """Crash mid-episode, then resume on the surviving journal + stores."""

    stores = DurableStores()
    first = execute_operation(
        intent,
        crash_point=crash_point,
        delivery_schedule=schedule,
        stores=stores,
        consent_epoch_at_commit=epoch_at_commit,
    )
    resumed = execute_operation(
        intent, delivery_schedule=schedule, journal=first.journal, stores=stores
    )
    return first, resumed, stores


# ---------------------------------------------------------------------------
# Independence: no oracle / held-out label imports in the candidate module
# ---------------------------------------------------------------------------


def test_candidate_does_not_import_oracle_or_label_files() -> None:
    source = Path(cand.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=cand.__file__)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                    assert fragment not in alias.name, f"candidate imports {alias.name}"
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                assert fragment not in module, f"candidate imports from {module}"
    # No held-out label file is read anywhere in the module source.
    for fragment in _FORBIDDEN_LABEL_FILES:
        assert fragment not in source, f"candidate references label file {fragment}"


def test_candidate_module_imports_clean_in_fresh_interpreter() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import evaluation.venue2027.dsn.candidate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_module_identity_and_version() -> None:
    assert CANDIDATE_ID == "dsn-recoverable-safety-journal"
    assert CANDIDATE_VERSION == "1.0.0"
    description = describe_mechanism()
    assert description["candidate_id"] == CANDIDATE_ID
    assert description["ablation_id"] == ABLATION_ID
    assert description["enforcement"]["write_ahead_effect_record"] is True
    assert description["guarantees"] and description["non_guarantees"]
    json.dumps(description)  # JSON-serializable


# ---------------------------------------------------------------------------
# Positive: nominal commit, exactly once
# ---------------------------------------------------------------------------


def test_nominal_episode_commits_exactly_once() -> None:
    stores = DurableStores()
    report = execute_operation(_intent(), delivery_schedule=(1,), stores=stores)
    assert report.stopped_at == "completed"
    verdict = recoverable_outcome(report.journal, _intent())
    assert verdict.outcome == "COMMITTED"
    assert verdict.reason_code == "COMMITTED_EFFECT_APPLIED"
    kinds = [entry.kind for entry in report.journal.entries]
    assert kinds == [INTENT, COMMIT, OUTBOX_RECORD, EFFECT_APPLIED]
    assert report.row_writes == 1
    assert report.effect_applications == 1
    assert stores.row_write_count == 1
    assert stores.effect_apply_count == 1


def test_resume_idempotent_second_pass_changes_nothing() -> None:
    stores = DurableStores()
    first = execute_operation(_intent(), delivery_schedule=(1,), stores=stores)
    second = execute_operation(
        _intent(), delivery_schedule=(1, 2), journal=first.journal, stores=stores
    )
    assert second.resumed is True
    assert second.row_writes == 0
    assert second.effect_applications == 0
    assert second.deliveries_observed == 2
    assert second.deliveries_deduped == 2
    verdict = recoverable_outcome(second.journal, _intent())
    assert verdict.outcome == "COMMITTED"
    assert stores.row_write_count == 1
    assert stores.effect_apply_count == 1


# ---------------------------------------------------------------------------
# Positive: every crash window, then recovery resumes exactly once
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("crash_point", "expected_kinds_at_crash"),
    [
        ("pre_commit", [INTENT]),
        ("post_commit_pre_response", [INTENT, COMMIT]),
        ("pre_outbox_delivery", [INTENT, COMMIT, OUTBOX_RECORD]),
        ("mid_effect", [INTENT, COMMIT, OUTBOX_RECORD, EFFECT_APPLIED]),
    ],
)
def test_crash_then_recovery_commits_exactly_once(
    crash_point: str, expected_kinds_at_crash: list[str]
) -> None:
    first, resumed, stores = _run_full_episode(_intent(), crash_point, schedule=(1, 2, 3))
    assert first.crash_point == crash_point
    assert [entry.kind for entry in first.journal.entries] == expected_kinds_at_crash
    assert first.stopped_at == f"crash:{crash_point}"
    assert resumed.stopped_at == "completed"
    verdict = recoverable_outcome(resumed.journal, _intent())
    assert verdict.outcome == "COMMITTED"
    # Exactly once across the crash window: one durable row, one durable effect.
    assert stores.row_write_count == 1
    assert stores.effect_apply_count == 1
    assert len([e for e in resumed.journal.entries if e.kind == COMMIT]) == 1


def test_pre_commit_crash_leaves_no_positive_evidence() -> None:
    stores = DurableStores()
    first = execute_operation(_intent(), crash_point="pre_commit", stores=stores)
    assert stores.row_write_count == 0
    assert stores.effect_apply_count == 0
    verdict = recoverable_outcome(first.journal, _intent())
    assert verdict.outcome == "REJECTED"
    assert verdict.reason_code == "NOT_COMMITTED_NO_DURABLE_EVIDENCE"
    assert verdict.retriable is True


def test_mid_effect_crash_never_marks_effect_applied() -> None:
    """The write-ahead record exists but the store effect never landed."""

    stores = DurableStores()
    first = execute_operation(
        _intent(), crash_point="mid_effect", delivery_schedule=(1,), stores=stores
    )
    assert stores.effect_apply_count == 0
    assert first.effect_applications == 0
    # Journal is a legal prefix; recovery completes the interrupted effect.
    resumed = execute_operation(
        _intent(), delivery_schedule=(2,), journal=first.journal, stores=stores
    )
    assert resumed.effect_applications == 1
    assert stores.effect_apply_count == 1
    verdict = recoverable_outcome(resumed.journal, _intent())
    assert verdict.outcome == "COMMITTED"


# ---------------------------------------------------------------------------
# Positive: broker replay dedupe (DSN-CASE-04)
# ---------------------------------------------------------------------------


def test_broker_replay_applies_effect_once() -> None:
    stores = DurableStores()
    report = execute_operation(_intent(), delivery_schedule=(1, 1, 1), stores=stores)
    assert report.deliveries_observed == 3
    assert report.deliveries_deduped == 2
    assert report.effect_applications == 1
    assert stores.effect_apply_count == 1
    applied = [e for e in report.journal.entries if e.kind == EFFECT_APPLIED]
    assert len(applied) == 1
    verdict = recoverable_outcome(report.journal, _intent())
    assert verdict.outcome == "COMMITTED"
    assert verdict.reason_code == "COMMITTED_EFFECT_APPLIED"


# ---------------------------------------------------------------------------
# Positive: revocation interleaving (DSN-CASE-05)
# ---------------------------------------------------------------------------


def test_revocation_before_commit_aborts_and_stays_rejected() -> None:
    stores = DurableStores()
    first = execute_operation(_intent(), stores=stores, consent_epoch_at_commit=EPOCH + 1)
    assert stores.row_write_count == 0
    assert stores.effect_apply_count == 0
    kinds = [entry.kind for entry in first.journal.entries]
    assert kinds == [INTENT, ABORT]
    verdict = recoverable_outcome(first.journal, _intent())
    assert verdict.outcome == "REJECTED"
    assert verdict.reason_code == "CONSENT_REVOKED_BEFORE_COMMIT"
    assert verdict.retriable is False
    # Resume: the rejection is durable and stable; no new mutations occur.
    resumed = execute_operation(
        _intent(), delivery_schedule=(1,), journal=first.journal, stores=stores
    )
    assert resumed.stopped_at == "rejected_stable"
    assert stores.row_write_count == 0
    assert stores.effect_apply_count == 0


def test_commit_stamped_with_post_revocation_epoch_rejected() -> None:
    journal = SafetyJournal().append(
        INTENT, OP_ID, {"payload_digest_sha256": PAYLOAD, "authorized_consent_epoch": EPOCH}, 0
    )
    journal = journal.append(
        COMMIT,
        OP_ID,
        {"row_version": 1, "consent_epoch_at_commit": EPOCH + 1, "payload_digest_sha256": PAYLOAD},
        1,
    )
    verdict = recoverable_outcome(journal, _intent())
    assert verdict.outcome == "REJECTED"
    assert verdict.reason_code == "FORBIDDEN_WRITE_POST_REVOCATION"


# ---------------------------------------------------------------------------
# Adversarial: corrupt journal -> INDETERMINATE, never coerced (DSN-CASE-06)
# ---------------------------------------------------------------------------


def _verified_journal() -> SafetyJournal:
    report = execute_operation(_intent(), delivery_schedule=(1,))
    assert recoverable_outcome(report.journal, _intent()).outcome == "COMMITTED"
    return report.journal


@pytest.mark.parametrize(
    "mode", ["flip_payload", "flip_digest", "drop_interior_entry", "unknown_kind"]
)
def test_interior_corruption_is_indeterminate(mode: str) -> None:
    journal = corrupt_journal(_verified_journal(), mode, 1)
    verdict = recoverable_outcome(journal, _intent())
    assert verdict.outcome == "INDETERMINATE"
    assert verdict.reason_code == "JOURNAL_CORRUPT"
    assert verdict.retriable is False
    assert verdict.details["defects"]


def test_tail_truncation_is_legal_prefix_not_corruption() -> None:
    journal = _verified_journal()
    truncated = SafetyJournal(journal.entries[:-1])  # crash cut the tail
    assert verify_journal(truncated, OP_ID) == ()
    verdict = recoverable_outcome(truncated, _intent())
    assert verdict.outcome == "COMMITTED"
    assert verdict.reason_code == "COMMITTED_PENDING_DELIVERY"


def test_recovery_on_corrupted_journal_refuses_without_mutating_stores() -> None:
    stores = DurableStores()
    first = execute_operation(_intent(), delivery_schedule=(1,), stores=stores)
    corrupted = corrupt_journal(first.journal, "flip_payload", 1)
    with pytest.raises(CandidateError) as excinfo:
        execute_operation(_intent(), delivery_schedule=(1,), journal=corrupted, stores=stores)
    assert excinfo.value.reason_code == "JOURNAL_CORRUPT"
    assert stores.row_write_count == 1  # untouched by the refused episode
    assert stores.effect_apply_count == 1


def test_foreign_shard_entry_is_indeterminate() -> None:
    journal = _verified_journal()
    foreign = journal.append(OUTBOX_RECORD, OTHER_OP_ID, {}, 99)
    verdict = recoverable_outcome(foreign, _intent())
    assert verdict.outcome == "INDETERMINATE"
    assert verdict.reason_code == "JOURNAL_CORRUPT"


def test_intent_binding_mismatch_is_indeterminate() -> None:
    journal = _verified_journal()
    verdict = recoverable_outcome(journal, _intent(payload=OTHER_PAYLOAD))
    assert verdict.outcome == "INDETERMINATE"
    assert verdict.reason_code == "JOURNAL_INTENT_MISMATCH"
    verdict_epoch = recoverable_outcome(journal, _intent(epoch=EPOCH + 1))
    assert verdict_epoch.outcome == "INDETERMINATE"


def test_semantic_contradictions_are_indeterminate() -> None:
    def _entry(kind: str, payload: dict[str, object], seq: int) -> object:
        return (kind, payload, seq)

    commit_payload: dict[str, object] = {
        "row_version": 1,
        "consent_epoch_at_commit": EPOCH,
        "payload_digest_sha256": PAYLOAD,
    }
    effect_payload: dict[str, object] = {"attempt": 1, "effect_receipt_digest": "c" * 64}

    # Effect without commit.
    j1 = SafetyJournal().append(
        INTENT, OP_ID, {"payload_digest_sha256": PAYLOAD, "authorized_consent_epoch": EPOCH}, 0
    )
    j1 = j1.append(EFFECT_APPLIED, OP_ID, effect_payload, 1)
    v1 = recoverable_outcome(j1, _intent())
    assert (v1.outcome, v1.reason_code) == ("INDETERMINATE", "EFFECT_WITHOUT_COMMIT")

    # Abort then commit.
    j2 = SafetyJournal().append(
        INTENT, OP_ID, {"payload_digest_sha256": PAYLOAD, "authorized_consent_epoch": EPOCH}, 0
    )
    j2 = j2.append(ABORT, OP_ID, {"reason": "CONSENT_REVOKED_BEFORE_COMMIT"}, 1)
    j2 = j2.append(COMMIT, OP_ID, commit_payload, 2)
    v2 = recoverable_outcome(j2, _intent())
    assert (v2.outcome, v2.reason_code) == ("INDETERMINATE", "ABORT_COMMIT_CONTRADICTION")

    # Duplicate commits.
    j3 = SafetyJournal().append(
        INTENT, OP_ID, {"payload_digest_sha256": PAYLOAD, "authorized_consent_epoch": EPOCH}, 0
    )
    j3 = j3.append(COMMIT, OP_ID, commit_payload, 1)
    j3 = j3.append(COMMIT, OP_ID, commit_payload, 2)
    v3 = recoverable_outcome(j3, _intent())
    assert (v3.outcome, v3.reason_code) == ("INDETERMINATE", "DUPLICATE_COMMIT_RECORD")

    # Outbox record without commit.
    j4 = SafetyJournal().append(
        INTENT, OP_ID, {"payload_digest_sha256": PAYLOAD, "authorized_consent_epoch": EPOCH}, 0
    )
    j4 = j4.append(OUTBOX_RECORD, OP_ID, {}, 1)
    v4 = recoverable_outcome(j4, _intent())
    assert (v4.outcome, v4.reason_code) == ("INDETERMINATE", "OUTBOX_WITHOUT_COMMIT")

    # Divergent effect digests across duplicates.
    j5 = SafetyJournal().append(
        INTENT, OP_ID, {"payload_digest_sha256": PAYLOAD, "authorized_consent_epoch": EPOCH}, 0
    )
    j5 = j5.append(COMMIT, OP_ID, commit_payload, 1)
    j5 = j5.append(EFFECT_APPLIED, OP_ID, effect_payload, 2)
    j5 = j5.append(EFFECT_APPLIED, OP_ID, {"attempt": 2, "effect_receipt_digest": "d" * 64}, 3)
    v5 = recoverable_outcome(j5, _intent())
    assert (v5.outcome, v5.reason_code) == ("INDETERMINATE", "DUPLICATE_EFFECT_DIVERGENCE")
    assert _entry  # silence unused-helper lint if any


def test_malformed_inputs_fail_closed_indeterminate() -> None:
    bad_intent = WriteIntent(
        operation_id=OP_ID,
        tenant_id="synthetic-tenant",
        principal_id="synthetic-actor",
        purpose="self_care",
        authorized_consent_epoch=-1,
        payload_digest_sha256=PAYLOAD,
        issued_logical_time=0,
    )
    verdict = recoverable_outcome(SafetyJournal(), bad_intent)
    assert (verdict.outcome, verdict.reason_code) == ("INDETERMINATE", "MALFORMED_WRITE_INTENT")
    # Empty journal is a retriable non-commit, not an error and not a success.
    empty = recoverable_outcome(SafetyJournal(), _intent())
    assert (empty.outcome, empty.reason_code, empty.retriable) == (
        "REJECTED",
        "NOT_COMMITTED_NO_DURABLE_EVIDENCE",
        True,
    )


def test_from_dict_roundtrip_and_malformed_refusals() -> None:
    report = execute_operation(_intent(), delivery_schedule=(1,))
    revived = SafetyJournal.from_dict(json.loads(json.dumps(report.journal.to_dict())))
    assert verify_journal(revived, OP_ID) == ()
    assert recoverable_outcome(revived, _intent()).outcome == "COMMITTED"
    with pytest.raises(CandidateError) as excinfo:
        SafetyJournal.from_dict({"entries": [{"seq": 0}]})
    assert excinfo.value.reason_code == "MALFORMED_JOURNAL"
    with pytest.raises(CandidateError) as excinfo_intent:
        WriteIntent.from_dict({"operation_id": OP_ID})
    assert excinfo_intent.value.reason_code == "MALFORMED_WRITE_INTENT"
    with pytest.raises(CandidateError) as excinfo_corrupt:
        corrupt_journal(_verified_journal(), "shred", 0)
    assert excinfo_corrupt.value.reason_code == "CORRUPTION_SPEC_MALFORMED"
    with pytest.raises(CandidateError) as excinfo_crash:
        execute_operation(_intent(), crash_point="inside_the_sun")
    assert excinfo_crash.value.reason_code == "CRASH_POINT_UNKNOWN"


# ---------------------------------------------------------------------------
# Ablation: journal removed -> no adjudication, duplicate effects under replay
# ---------------------------------------------------------------------------


def test_ablation_cannot_adjudicate_and_duplicates_effects() -> None:
    stores = DurableStores()
    report = ablation_no_journal_execute(_intent(), delivery_schedule=(1, 1, 1), stores=stores)
    assert report["ablation_id"] == ABLATION_ID
    assert report["recoverable_outcome_available"] is False
    # Fire-and-forget consumer: one effect per delivery, no dedupe.
    assert report["effect_applications"] == 3
    assert stores.effect_apply_count == 3
    # After the post-commit crash the journal-less arm has no verdict at all.
    crashed = ablation_no_journal_execute(
        _intent(), crash_point="post_commit_pre_response", delivery_schedule=(1,)
    )
    assert crashed["row_write_attempts"] == 1
    assert crashed["recoverable_outcome_available"] is False


def test_ablation_refuses_malformed_inputs() -> None:
    with pytest.raises(CandidateError) as excinfo:
        ablation_no_journal_execute(_intent(epoch=-1))
    assert excinfo.value.reason_code == "MALFORMED_WRITE_INTENT"
    with pytest.raises(CandidateError) as excinfo_schedule:
        ablation_no_journal_execute(_intent(), delivery_schedule=(0,))
    assert excinfo_schedule.value.reason_code == "DELIVERY_SCHEDULE_MALFORMED"


# ---------------------------------------------------------------------------
# run_candidate adapter: harness mapping, determinism, fail-closed wiring
# ---------------------------------------------------------------------------


def test_run_candidate_clean_case_admits_committed() -> None:
    outcome = run_candidate(_case(), None)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    detail = json.loads(outcome.detail)
    assert detail["verdict"]["outcome"] == "COMMITTED"
    assert detail["verdict"]["reason_code"] == "COMMITTED_EFFECT_APPLIED"
    assert detail["resume"]["stopped_at"] == "completed"


def test_run_candidate_every_crash_window_still_admits_exactly_once() -> None:
    for crash_point in (
        "pre_commit",
        "post_commit_pre_response",
        "pre_outbox_delivery",
        "mid_effect",
    ):
        outcome = run_candidate(
            _case(case_id=f"DSN-CASE-{crash_point}", crash_point=crash_point), None
        )
        assert outcome.observed_outcome == "ADMIT", crash_point
        detail = json.loads(outcome.detail)
        assert detail["verdict"]["outcome"] == "COMMITTED"
        assert detail["resume"]["row_writes"] <= 1
        assert detail["resume"]["effect_applications"] <= 1


def test_run_candidate_revocation_rejects() -> None:
    outcome = run_candidate(_case(case_id="DSN-CASE-05", consent_epoch_at_commit=EPOCH + 1), None)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is True
    detail = json.loads(outcome.detail)
    assert detail["verdict"]["outcome"] == "REJECTED"
    assert detail["verdict"]["retriable"] is False


def test_run_candidate_corrupt_journal_is_indeterminate_never_counted() -> None:
    outcome = run_candidate(
        _case(
            case_id="DSN-CASE-06",
            corrupt_journal={"mode": "flip_payload", "entry_index": 1},
        ),
        None,
    )
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    detail = json.loads(outcome.detail)
    assert detail["verdict"]["reason_code"] == "JOURNAL_CORRUPT"


def test_run_candidate_broker_replay_admits_with_dedup() -> None:
    outcome = run_candidate(_case(case_id="DSN-CASE-04", delivery_schedule=[1, 1, 1]), None)
    assert outcome.observed_outcome == "ADMIT"
    detail = json.loads(outcome.detail)
    assert detail["resume"]["deliveries_observed"] == 3
    assert detail["resume"]["deliveries_deduped"] >= 2
    assert detail["resume"]["effect_applications"] <= 1


def test_run_candidate_deterministic() -> None:
    case = _case(case_id="determinism", crash_point="mid_effect", delivery_schedule=[1, 2])
    one = run_candidate(case, None)
    two = run_candidate(case, None)
    assert one.observed_outcome == two.observed_outcome == "ADMIT"
    assert one.detail == two.detail


def test_run_candidate_fail_closed_on_malformed_case() -> None:
    for bad, code in (
        ("not-an-object", "CASE_NOT_AN_OBJECT"),
        ({"case_id": "x"}, "CASE_MISSING_FIELD"),
        (
            {
                "case_id": "x",
                "operation_id": OP_ID,
                "authorized_consent_epoch": EPOCH,
                "delivery_schedule": [],
                "warp_drive": True,
            },
            "CASE_UNKNOWN_FIELD",
        ),
        (
            {
                "case_id": "x",
                "operation_id": OP_ID,
                "authorized_consent_epoch": EPOCH,
                "delivery_schedule": [0],
            },
            "CASE_BAD_FIELD",
        ),
        (
            {
                "case_id": "x",
                "operation_id": OP_ID,
                "authorized_consent_epoch": EPOCH,
                "delivery_schedule": [1],
                "crash_point": "photon_torpedo",
            },
            "CASE_BAD_FIELD",
        ),
        (
            {
                "case_id": "x",
                "operation_id": OP_ID,
                "authorized_consent_epoch": EPOCH,
                "delivery_schedule": [1],
                "corrupt_journal": {"mode": "shred", "entry_index": 0},
            },
            "CORRUPTION_SPEC_MALFORMED",
        ),
    ):
        outcome = run_candidate(bad, None)  # type: ignore[arg-type]
        assert outcome.observed_outcome == "EXECUTION_ERROR", bad
        assert outcome.counted_as_success is False
        assert code in outcome.detail
