"""Tests for DSN-X01_state_spec — 3-way durable state machine.

Positive controls (must yield the adjudicated verdict):
- CASE-01 nominal durable transition: row + receipt + outbox with one effect
  receipt all agree -> COMMITTED.
- CASE-03 crash after SQL COMMIT before HTTP ACK: committed row + receipt +
  pending outbox (no delivery) -> COMMITTED (retry reconciles by operation ID;
  durable success never inferred from the missing ACK).
- CASE-04 broker replay: same outbox message delivered three times with an
  identical effect receipt -> COMMITTED (idempotent, all deliveries recorded).
- CASE-07 outbox delayed: committed row + receipt, outbox present, no effect
  applied yet -> COMMITTED with PENDING_DELIVERY reason (storage commit
  separated from downstream delivery).
- Determinism: identical inputs yield identical verdicts (retry idempotence by
  stable operation ID); round-trips through to_dict/from_dict are lossless.

Adversarial controls (must fail closed):
- CASE-02 crash before SQL COMMIT: all channels ABSENT -> REJECTED with
  NOT_COMMITTED_NO_DURABLE_EVIDENCE (never a phantom success).
- CASE-05 consent revoked between authorization and commit: row stamped with
  a higher consent epoch -> REJECTED (forbidden write).
- CASE-06 corrupted receipt: stored transition digest differs from the row
  digest -> INDETERMINATE (tamper flagged, never silent success).
- Stale receipt: receipt row_version behind the committed row -> INDETERMINATE.
- Orphan ledger receipt with no committed row -> INDETERMINATE (never coerced
  to a safe rejection that would license a duplicate effect).
- Committed row with missing/outbox-absent evidence -> INDETERMINATE.
- Delivery timestamp before the outbox record -> INDETERMINATE.
- Divergent effect digests across duplicate deliveries -> INDETERMINATE.
- Malformed intent / durable state / unknown channel status -> INDETERMINATE
  with stable reason codes, never exceptions escaping evaluate_durability.
- Durable outbox failure record -> REJECTED (fsync failure), never COMMITTED.
- recover(): incomplete histories (no intent / no state), unknown event kinds,
  malformed events and conflicting intents fail closed with stable codes.
"""

from __future__ import annotations

import dataclasses
import json

from evaluation.venue2027.dsn import state_machine as sm

OP_ID = "op:w8-dsn-x01-0001"
TENANT = "synthetic-tenant"
PRINCIPAL = "synthetic-actor"
PURPOSE = "self_care"
PAYLOAD_DIGEST = "a" * 64
ROW_DIGEST = "b" * 64
RECEIPT_DIGEST = "c" * 64
EFFECT_DIGEST = "d" * 64
ISSUED_AT = 10
WAL_COMMIT_AT = 20
RECEIPT_AT = 21
RECORDED_AT = 20
DELIVERED_AT = 30
RECONCILER_AT = 100


def make_intent(epoch: int = 3) -> sm.WriteIntent:
    return sm.WriteIntent(
        operation_id=OP_ID,
        tenant_id=TENANT,
        principal_id=PRINCIPAL,
        purpose=PURPOSE,
        authorized_consent_epoch=epoch,
        payload_digest_sha256=PAYLOAD_DIGEST,
        issued_logical_time=ISSUED_AT,
    )


def make_row(
    *,
    status: sm.ChannelStatus = sm.ChannelStatus.PRESENT,
    op_id: str | None = OP_ID,
    version: int | None = 1,
    commit_at: int | None = WAL_COMMIT_AT,
    epoch: int | None = 3,
    digest: str | None = ROW_DIGEST,
) -> sm.ClinicalRowState:
    if status is sm.ChannelStatus.ABSENT:
        op_id, version, commit_at, epoch, digest = None, None, None, None, None
    return sm.ClinicalRowState(
        status=status,
        operation_id=op_id,
        row_version=version,
        wal_commit_logical_time=commit_at,
        consent_epoch_at_commit=epoch,
        row_digest_sha256=digest,
    )


def make_receipt(
    *,
    status: sm.ChannelStatus = sm.ChannelStatus.PRESENT,
    op_id: str | None = OP_ID,
    version: int | None = 1,
    epoch: int | None = 3,
    decision: str | None = sm.RECEIPT_DECISION_ACCEPT,
    at: int | None = RECEIPT_AT,
    transition_digest: str | None = ROW_DIGEST,
) -> sm.DecisionReceipt:
    if status is sm.ChannelStatus.ABSENT:
        op_id, version, epoch, decision, at, transition_digest = (
            None,
            None,
            None,
            None,
            None,
            None,
        )
    return sm.DecisionReceipt(
        status=status,
        operation_id=op_id,
        row_version=version,
        consent_epoch=epoch,
        decision=decision,
        receipt_logical_time=at,
        receipt_digest_sha256=None if status is sm.ChannelStatus.ABSENT else RECEIPT_DIGEST,
        stored_transition_digest=transition_digest,
    )


def make_outbox(
    *,
    status: sm.ChannelStatus = sm.ChannelStatus.PRESENT,
    op_id: str | None = OP_ID,
    recorded_at: int | None = RECORDED_AT,
    deliveries: tuple[sm.DeliveryReceipt, ...] = (),
) -> sm.OutboxState:
    if status is sm.ChannelStatus.ABSENT:
        op_id, recorded_at, deliveries = None, None, ()
    return sm.OutboxState(
        status=status,
        operation_id=op_id,
        recorded_logical_time=recorded_at,
        deliveries=deliveries,
    )


def make_state(
    *,
    row: sm.ClinicalRowState | None = None,
    receipt: sm.DecisionReceipt | None = None,
    outbox: sm.OutboxState | None = None,
    current_epoch: int = 3,
    reconciler_at: int = RECONCILER_AT,
) -> sm.DurableState:
    return sm.DurableState(
        clinical_row=row if row is not None else make_row(),
        decision_receipt=receipt if receipt is not None else make_receipt(),
        outbox=outbox if outbox is not None else make_outbox(),
        current_consent_epoch=current_epoch,
        reconciler_logical_time=reconciler_at,
    )


def delivery(
    attempt: int,
    *,
    applied: bool = True,
    digest: str | None = EFFECT_DIGEST,
    at: int = DELIVERED_AT,
    op_id: str = OP_ID,
) -> sm.DeliveryReceipt:
    return sm.DeliveryReceipt(
        operation_id=op_id,
        attempt=attempt,
        effect_applied=applied,
        delivered_logical_time=at,
        effect_receipt_digest=digest,
    )


def evaluate(
    *, intent: sm.WriteIntent | None = None, state: sm.DurableState
) -> sm.DurabilityVerdict:
    return sm.evaluate_durability(intent if intent is not None else make_intent(), state)


# --------------------------------------------------------------------------
# Positive controls
# --------------------------------------------------------------------------


def test_case_01_nominal_transition_is_committed() -> None:
    state = make_state(outbox=make_outbox(deliveries=(delivery(1),)))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    assert verdict.reason_code == sm.REASON_COMMITTED_EFFECT_APPLIED
    assert verdict.details["deliveries_recorded"] == 1
    assert verdict.details["effects_applied"] == 1


def test_case_03_crash_after_commit_before_ack_is_committed() -> None:
    # The server committed then died before the HTTP response: the ACK is
    # absent, but the durable channels carry the truth. A retry reconciles to
    # COMMITTED — success is inferred from durable receipts, never the ACK.
    state = make_state(outbox=make_outbox(deliveries=()))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    assert verdict.reason_code == sm.REASON_COMMITTED_PENDING_DELIVERY


def test_case_04_duplicate_delivery_idempotent_committed() -> None:
    state = make_state(
        outbox=make_outbox(
            deliveries=(delivery(1), delivery(2), delivery(3)),
        )
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    assert verdict.reason_code == sm.REASON_COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT
    assert verdict.details["deliveries_recorded"] == 3
    assert verdict.details["effects_applied"] == 3
    assert verdict.details["effect_receipt_digest"] == EFFECT_DIGEST


def test_case_07_outbox_delayed_is_committed_pending_delivery() -> None:
    # Outbox message persists but the broker is unavailable: storage commit
    # status is separate from downstream delivery, both remain COMMITTED.
    state = make_state(outbox=make_outbox(deliveries=(delivery(1, applied=False),)))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    assert verdict.reason_code == sm.REASON_COMMITTED_PENDING_DELIVERY


def test_verdict_is_deterministic_for_identical_inputs() -> None:
    state = make_state(outbox=make_outbox(deliveries=(delivery(1),)))
    first = evaluate(state=state)
    for _ in range(5):
        assert evaluate(state=state).to_dict() == first.to_dict()


def test_retry_with_same_operation_id_is_idempotent() -> None:
    # Retries are keyed to the immutable operation ID: replaying the same
    # (intent, state) pair never flips the verdict or doubles the effect.
    state = make_state(outbox=make_outbox(deliveries=(delivery(1),)))
    verdicts = {sm.verdict_sha256(evaluate(state=state)) for _ in range(3)}
    assert len(verdicts) == 1


def test_serialization_round_trip_lossless() -> None:
    intent = make_intent()
    state = make_state(outbox=make_outbox(deliveries=(delivery(1),)))
    verdict = evaluate(state=state)
    assert sm.WriteIntent.from_dict(intent.to_dict()) == intent
    assert sm.DurableState.from_dict(state.to_dict()) == state
    assert sm.DurabilityVerdict.from_dict(verdict.to_dict()) == verdict


def test_json_serializable_outputs() -> None:
    state = make_state(outbox=make_outbox(deliveries=(delivery(1),)))
    payload = json.dumps(evaluate(state=state).to_dict())
    assert OP_ID in payload


def test_reason_code_registry_matches_all_emitted_codes() -> None:
    # Every state gets exactly one verdict whose reason code is registered.
    states = [
        make_state(outbox=make_outbox(deliveries=(delivery(1),))),
        make_state(
            row=make_row(status=sm.ChannelStatus.ABSENT),
            receipt=make_receipt(status=sm.ChannelStatus.ABSENT),
            outbox=make_outbox(status=sm.ChannelStatus.ABSENT),
        ),
        make_state(receipt=make_receipt(status=sm.ChannelStatus.CORRUPT)),
        make_state(outbox=make_outbox(status=sm.ChannelStatus.FAILED, op_id=OP_ID)),
    ]
    for state in states:
        verdict = evaluate(state=state)
        assert verdict.reason_code in sm.REASON_CODES
        assert verdict.outcome in (
            sm.DurabilityOutcome.COMMITTED,
            sm.DurabilityOutcome.REJECTED,
            sm.DurabilityOutcome.INDETERMINATE,
        )


# --------------------------------------------------------------------------
# Adversarial controls
# --------------------------------------------------------------------------


def test_case_02_crash_before_wal_is_rejected_not_committed() -> None:
    # SIGKILL after flushed ORM changes, before the server confirms commit:
    # nothing durable exists. The verdict must never be a phantom success.
    state = make_state(
        row=make_row(status=sm.ChannelStatus.ABSENT),
        receipt=make_receipt(status=sm.ChannelStatus.ABSENT),
        outbox=make_outbox(status=sm.ChannelStatus.ABSENT),
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.REJECTED
    assert verdict.reason_code == sm.REASON_NOT_COMMITTED_NO_DURABLE_EVIDENCE


def test_case_05_consent_revoked_before_commit_is_rejected() -> None:
    # Consent revoked between initial authorization and the actual mutation
    # commit: the row carries a post-revocation epoch -> forbidden write.
    state = make_state(row=make_row(epoch=4), current_epoch=4)
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.REJECTED
    assert verdict.reason_code == sm.REASON_FORBIDDEN_WRITE_POST_REVOCATION


def test_case_06_corrupted_receipt_is_indeterminate() -> None:
    # Signed receipt digest differs from the stored transition: flag tamper,
    # never silently succeed.
    state = make_state(receipt=make_receipt(transition_digest="e" * 64))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_RECEIPT_DIGEST_MISMATCH


def test_stale_receipt_version_is_indeterminate() -> None:
    # Receipt signed for an older row version than the committed row.
    state = make_state(row=make_row(version=2), receipt=make_receipt(version=1))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_STALE_RECEIPT_VERSION_MISMATCH


def test_orphan_receipt_without_clinical_row_is_indeterminate() -> None:
    # A ledger receipt with no committed row must never be coerced into a
    # rejection (which would license a duplicate effect) nor a success.
    state = make_state(
        row=make_row(status=sm.ChannelStatus.ABSENT),
        receipt=make_receipt(),
        outbox=make_outbox(status=sm.ChannelStatus.ABSENT),
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW


def test_committed_row_without_decision_receipt_is_indeterminate() -> None:
    # Never infer durable success without a receipt (fail closed).
    state = make_state(receipt=make_receipt(status=sm.ChannelStatus.ABSENT))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW


def test_committed_row_without_outbox_is_indeterminate() -> None:
    state = make_state(outbox=make_outbox(status=sm.ChannelStatus.ABSENT))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_OUTBOX_RECORD_MISSING


def test_outbox_orphan_without_clinical_row_is_indeterminate() -> None:
    state = make_state(
        row=make_row(status=sm.ChannelStatus.ABSENT),
        receipt=make_receipt(status=sm.ChannelStatus.ABSENT),
        outbox=make_outbox(deliveries=()),
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_OUTBOX_ORPHAN_NO_CLINICAL_ROW


def test_divergent_duplicate_effects_are_indeterminate() -> None:
    state = make_state(
        outbox=make_outbox(
            deliveries=(
                delivery(1, digest=EFFECT_DIGEST),
                delivery(2, digest="f" * 64),
            )
        )
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_DUPLICATE_EFFECT_DIVERGENCE


def test_delivery_before_outbox_record_is_indeterminate() -> None:
    state = make_state(
        outbox=make_outbox(deliveries=(delivery(1, at=5),))
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_DELIVERY_TIMESTAMP_ANOMALY


def test_receipt_timestamp_after_reconciler_is_indeterminate() -> None:
    state = make_state(receipt=make_receipt(at=RECONCILER_AT + 1))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_RECEIPT_TIMESTAMP_ANOMALY


def test_wal_commit_after_reconciler_is_indeterminate() -> None:
    state = make_state(row=make_row(commit_at=RECONCILER_AT + 1))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_WAL_COMMIT_TIMESTAMP_ANOMALY


def test_outbox_record_before_wal_commit_is_indeterminate() -> None:
    state = make_state(outbox=make_outbox(recorded_at=WAL_COMMIT_AT - 1))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_OUTBOX_TIMESTAMP_ANOMALY


def test_receipt_before_wal_commit_is_indeterminate() -> None:
    state = make_state(receipt=make_receipt(at=WAL_COMMIT_AT - 1))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_RECEIPT_TIMESTAMP_ANOMALY


def test_receipt_epoch_from_the_future_is_indeterminate() -> None:
    state = make_state(receipt=make_receipt(epoch=99), current_epoch=3)
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_CONSENT_EPOCH_ANOMALY


def test_state_operation_mismatch_is_indeterminate() -> None:
    state = make_state(
        row=make_row(op_id="op:other-1"),
        receipt=make_receipt(op_id="op:other-1"),
        outbox=make_outbox(op_id="op:other-1", deliveries=()),
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_STATE_OPERATION_MISMATCH


def test_non_accept_receipt_decision_is_rejected() -> None:
    state = make_state(receipt=make_receipt(decision="DENY"))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.REJECTED
    assert verdict.reason_code == sm.REASON_RECEIPT_DECISION_CONFLICT


def test_corrupt_clinical_row_is_indeterminate() -> None:
    state = make_state(row=make_row(status=sm.ChannelStatus.CORRUPT))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_CLINICAL_ROW_CORRUPT


def test_corrupt_ledger_receipt_is_indeterminate() -> None:
    state = make_state(receipt=make_receipt(status=sm.ChannelStatus.CORRUPT))
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_DECISION_RECEIPT_CORRUPT


def test_outbox_fsync_failure_record_is_rejected() -> None:
    state = make_state(
        outbox=sm.OutboxState(
            status=sm.ChannelStatus.FAILED,
            operation_id=OP_ID,
            failure_reason="FSYNC_ERROR",
        )
    )
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.REJECTED
    assert verdict.reason_code == sm.REASON_OUTBOX_FSYNC_FAILED


def test_malformed_intent_is_indeterminate_not_raised() -> None:
    intent = dataclasses.replace(make_intent(), operation_id="")
    verdict = evaluate(intent=intent, state=make_state())
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_MALFORMED_WRITE_INTENT


def test_malformed_state_is_indeterminate_not_raised() -> None:
    # Directly constructed malformed state: ABSENT clinical row that still
    # carries a payload must be refused structurally (fail closed).
    malformed_row = sm.ClinicalRowState(
        status=sm.ChannelStatus.ABSENT,
        operation_id=OP_ID,
        row_version=1,
        wal_commit_logical_time=WAL_COMMIT_AT,
        consent_epoch_at_commit=3,
        row_digest_sha256=ROW_DIGEST,
    )
    verdict = evaluate(state=make_state(row=malformed_row))
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_MALFORMED_DURABLE_STATE


def test_malformed_outbox_delivery_is_indeterminate() -> None:
    bad = dataclasses.replace(delivery(1), attempt=0)
    verdict = evaluate(state=make_state(outbox=make_outbox(deliveries=(bad,))))
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_MALFORMED_DURABLE_STATE


def test_internal_error_guard_yields_indeterminate() -> None:
    # A state object that passes structural typing but explodes inside the
    # reconciler must surface as INDETERMINATE, never as an escape exception.
    row = dataclasses.replace(make_row(), wal_commit_logical_time=2**64 - 1)
    receipt = make_receipt(at=2**64 - 1)
    state = make_state(row=row, receipt=receipt)
    verdict = evaluate(state=state)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE


# --------------------------------------------------------------------------
# recover(): event-history fold
# --------------------------------------------------------------------------


def committed_history_state() -> dict[str, object]:
    return {
        "clinical_row": make_row().to_dict(),
        "decision_receipt": make_receipt().to_dict(),
        "outbox": make_outbox(deliveries=(delivery(1),)).to_dict(),
        "current_consent_epoch": 3,
        "reconciler_logical_time": RECONCILER_AT,
    }


def test_recover_clean_episode_is_committed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="CRASH",
                logical_time=25,
                payload={"crash_point": sm.CrashPoint.NONE},
            ),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    assert verdict.reason_code == sm.REASON_COMMITTED_EFFECT_APPLIED
    assert verdict.crash_points == (sm.CrashPoint.NONE,)


def test_recover_pre_commit_episode_is_rejected() -> None:
    blank = {
        "clinical_row": make_row(status=sm.ChannelStatus.ABSENT).to_dict(),
        "decision_receipt": make_receipt(status=sm.ChannelStatus.ABSENT).to_dict(),
        "outbox": make_outbox(status=sm.ChannelStatus.ABSENT).to_dict(),
        "current_consent_epoch": 3,
        "reconciler_logical_time": RECONCILER_AT,
    }
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="CRASH",
                logical_time=15,
                payload={"crash_point": sm.CrashPoint.PRE_COMMIT},
            ),
            sm.HistoryEvent(kind="DURABLE_STATE", logical_time=40, payload=blank),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.REJECTED
    assert verdict.reason_code == sm.REASON_NOT_COMMITTED_NO_DURABLE_EVIDENCE


def test_recover_replays_deliver_events_into_outbox() -> None:
    base = committed_history_state()
    base["outbox"] = make_outbox(deliveries=()).to_dict()
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(kind="DURABLE_STATE", logical_time=40, payload=base),
            sm.HistoryEvent(
                kind="DELIVER", logical_time=50, payload=delivery(1).to_dict()
            ),
            sm.HistoryEvent(
                kind="DELIVER", logical_time=51, payload=delivery(2).to_dict()
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    assert verdict.reason_code == sm.REASON_COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT
    assert verdict.details["deliveries_recorded"] == 2


def test_recover_without_state_fails_closed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_HISTORY_INCOMPLETE


def test_recover_without_intent_fails_closed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_HISTORY_INCOMPLETE


def test_recover_unknown_event_kind_fails_closed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
            sm.HistoryEvent(kind="MAGIC", logical_time=45, payload={}),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_UNKNOWN_HISTORY_EVENT


def test_recover_unknown_crash_point_fails_closed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(kind="CRASH", logical_time=15, payload={"crash_point": "sigsegv"}),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_UNKNOWN_HISTORY_EVENT


def test_recover_malformed_intent_event_fails_closed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(kind="WRITE_INTENT", logical_time=ISSUED_AT, payload={}),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_MALFORMED_HISTORY_EVENT


def test_recover_malformed_state_event_fails_closed() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="DURABLE_STATE", logical_time=40, payload={"clinical_row": {}}
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_MALFORMED_HISTORY_EVENT


def test_recover_conflicting_intent_fails_closed() -> None:
    # Two different operation intents in one episode: the fold cannot know
    # which durable state to adjudicate -> fail closed, never guess.
    other = dataclasses.replace(make_intent(), operation_id="op:other-2")
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="WRITE_INTENT", logical_time=11, payload=other.to_dict()
            ),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert verdict.reason_code == sm.REASON_STATE_OPERATION_MISMATCH


def test_recover_preserves_recorded_evaluations() -> None:
    recorded = sm.DurabilityVerdict(
        outcome=sm.DurabilityOutcome.INDETERMINATE,
        reason_code=sm.REASON_RECEIPT_DIGEST_MISMATCH,
        details={"step": "mid-recovery"},
    )
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="EVALUATION", logical_time=45, payload=recorded.to_dict()
            ),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    verdict = sm.recover(history)
    assert verdict.evaluations[0]["reason_code"] == sm.REASON_RECEIPT_DIGEST_MISMATCH


def test_recover_json_round_trip() -> None:
    history = sm.EventHistory(
        events=(
            sm.HistoryEvent(
                kind="WRITE_INTENT",
                logical_time=ISSUED_AT,
                payload=make_intent().to_dict(),
            ),
            sm.HistoryEvent(
                kind="DURABLE_STATE",
                logical_time=40,
                payload=committed_history_state(),
            ),
        ),
        reconciler_logical_time=RECONCILER_AT,
    )
    restored = sm.EventHistory.from_dict(json.loads(json.dumps(history.to_dict())))
    assert restored == history
    verdict = sm.recover(restored)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED


def test_reconcile_convenience_wraps_evaluate_durability() -> None:
    state = make_state(outbox=make_outbox(deliveries=(delivery(1),)))
    verdict = sm.reconcile(OP_ID, state)
    assert verdict.outcome is sm.DurabilityOutcome.COMMITTED
    mismatch = sm.reconcile("op:elsewhere", state)
    assert mismatch.outcome is sm.DurabilityOutcome.INDETERMINATE
    assert mismatch.reason_code == sm.REASON_STATE_OPERATION_MISMATCH


# --------------------------------------------------------------------------
# Module-level contract
# --------------------------------------------------------------------------


def test_version_and_contract_surface() -> None:
    assert sm.STATE_MACHINE_VERSION == "clara.dsn.state-machine-v1"
    assert set(sm.CRASH_POINTS) == {
        sm.CrashPoint.NONE,
        sm.CrashPoint.PRE_COMMIT,
        sm.CrashPoint.POST_COMMIT_PRE_RESPONSE,
        sm.CrashPoint.PRE_OUTBOX_DELIVERY,
    }
    assert sm.DurabilityOutcome.INDETERMINATE.value == "INDETERMINATE"


def test_demo_self_check_spans_all_crash_points(tmp_path=None) -> None:
    payload = sm._demo()
    assert set(payload["results"]) == set(sm.CRASH_POINTS)
    assert payload["results"][sm.CrashPoint.NONE]["outcome"] == "COMMITTED"
    assert payload["results"][sm.CrashPoint.PRE_COMMIT]["outcome"] == "REJECTED"
