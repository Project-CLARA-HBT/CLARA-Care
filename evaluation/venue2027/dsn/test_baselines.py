"""Tests for DSN-baselines — baseline fidelity adapters (phase P03).

Positive controls:
- Registry coverage: every in-process arm runs end to end and returns a
  counted ADMIT on a clean window; the pinned external arm is transparently
  NOT_RUN_EXTERNAL.
- Core P03 contrast: after a crash the candidate journal (B4) reconciles the
  operation exactly-once (dedup on the journal), while B0 either loses the
  operation (pre-commit) or leaves an orphaned side effect that a blind
  retry re-applies — B0 never gives exactly-once.
- B1 idempotent consumer: duplicate deliveries under at-least-once replay
  re-ack without re-applying the effect.
- B3 fsync honesty: the acknowledged-row / lost-side-effect window is
  reported as a lost side effect, never as a phantom success.
- B5 monotonic guard: a stale journal entry behind the watermark is
  rejected; a fresh write above the watermark proceeds.
- Determinism: identical (case, fresh store) pairs yield identical outcomes.

Adversarial controls (must fail closed):
- Crash-before-WAL (pre_commit) is never counted as success on any arm: the
  outcome is REJECT, retriable, counted_as_success=False.
- refuse_constant_stub refuses a constant stub (same outcome for the clean
  and crashed probes) and admits a crash-sensitive adapter.
- The pinned external arm returns NOT_RUN_EXTERNAL, never counted.
- Unknown baseline id, non-mapping case, missing/unknown/badly-typed case
  fields, malformed context and bad delivery schedules raise BaselineError
  with stable reason codes (wiring errors, not silent outcomes).
"""

from __future__ import annotations

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dsn.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2_WORKFLOW,
    BASELINE_B3,
    BASELINE_B4,
    BASELINE_B5,
    BASELINE_REGISTRY,
    CRASH_NONE,
    CRASH_POST_COMMIT_PRE_RESPONSE,
    CRASH_PRE_COMMIT,
    CRASH_PRE_OUTBOX_DELIVERY,
    RC_BASELINE_UNAVAILABLE,
    RC_CASE_BAD_TYPE,
    RC_CASE_EMPTY_OP_ID,
    RC_CASE_MISSING_FIELD,
    RC_CASE_NOT_AN_OBJECT,
    RC_CASE_UNKNOWN_FIELD,
    RC_CONTEXT_MALFORMED,
    RC_CRASH_POINT_UNKNOWN,
    RC_DELIVERY_SCHEDULE_BAD,
    RC_JOURNAL_REPLAY_DEDUP,
    RC_JOURNAL_STALE_ENTRY,
    RC_OP_COMMITTED,
    RC_OP_COMMITTED_IDEMPOTENT_RETRY,
    RC_OP_LOST_SIDE_EFFECT,
    RC_OP_NOT_DURABLE,
    RC_STUB_CONSTANT,
    RC_STUB_SEPARATION_OK,
    BaselineContext,
    BaselineError,
    _idem_key,
    _journal_key,
    _row_key,
    _seq_key,
    refuse_constant_stub,
    run_baseline,
)

IN_PROCESS_ARMS = (BASELINE_B0, BASELINE_B1, BASELINE_B3, BASELINE_B4, BASELINE_B5)


def make_case(
    case_id: str = "case-0001",
    operation_id: str = "op:0001",
    crash_point: str = CRASH_NONE,
    delivery_schedule: tuple[int, ...] | list[int] = (1,),
    consent_epoch: int = 3,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "operation_id": operation_id,
        "crash_point": crash_point,
        "delivery_schedule": list(delivery_schedule),
        "consent_epoch": consent_epoch,
    }


def fresh_ctx() -> BaselineContext:
    return BaselineContext(store={}, recovery_retries=2)


# ---------------------------------------------------------------------------
# Positive controls.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", IN_PROCESS_ARMS)
def test_registry_covers_arm_and_clean_run_commits(baseline_id: str) -> None:
    """Every in-process arm is registered, runnable, and commits cleanly."""
    assert baseline_id in BASELINE_REGISTRY
    spec = BASELINE_REGISTRY[baseline_id]
    assert spec.runnable_in_process is True
    outcome = run_baseline(baseline_id, make_case(), fresh_ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    assert outcome.retriable is False


def test_external_pinned_arm_is_not_run_external() -> None:
    """The durable-workflow arm stays transparently NOT_RUN_EXTERNAL."""
    spec = BASELINE_REGISTRY[BASELINE_B2_WORKFLOW]
    assert spec.runnable_in_process is False
    outcome = run_baseline(BASELINE_B2_WORKFLOW, make_case(), fresh_ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is False
    assert outcome.detail == RC_BASELINE_UNAVAILABLE


def test_b0_clean_window_applies_effect_once() -> None:
    """On a clean window with one delivery B0 applies the effect exactly once."""
    ctx = fresh_ctx()
    outcome = run_baseline(BASELINE_B0, make_case(delivery_schedule=(1,)), ctx)
    assert outcome.observed_outcome == "ADMIT"
    # Initial durable write + exactly one delivery.
    assert ctx.store[_row_key("op:0001")] == 2


def test_b1_duplicate_deliveries_dedup_by_idempotency_key() -> None:
    """B1 under at-least-once replay re-acks without re-applying the effect."""
    ctx = fresh_ctx()
    outcome = run_baseline(
        BASELINE_B1, make_case(delivery_schedule=(1, 2, 3)), ctx
    )
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.detail == RC_OP_COMMITTED
    # Outbox row records deliveries; the idempotency key is durable.
    assert ctx.store[_idem_key("op:0001")] == 1
    # Retry after the fact: dedup, never a second effect application.
    replay = run_baseline(BASELINE_B1, make_case(delivery_schedule=(4,)), ctx)
    assert replay.observed_outcome == "ADMIT"
    assert replay.detail == RC_OP_COMMITTED_IDEMPOTENT_RETRY


def test_core_contrast_b4_exactly_once_after_crash_b0_not() -> None:
    """The P03 core separation.

    Same post-commit crash window replayed through recovery: B4's journal
    dedup reconciles exactly-once, while B0 leaves an orphaned side effect
    whose blind retry re-applies (duplicate) and B3 loses the side effect.
    """
    op = "op:contrast"
    case = make_case(case_id="contrast", operation_id=op, crash_point=CRASH_POST_COMMIT_PRE_RESPONSE)

    # B4: journal is durable before the crash; recovery replay dedups.
    b4_ctx = fresh_ctx()
    first = run_baseline(BASELINE_B4, case, b4_ctx)
    assert first.observed_outcome == "ADMIT"
    recovery = run_baseline(
        BASELINE_B4,
        make_case(case_id="contrast", operation_id=op, crash_point=CRASH_NONE),
        b4_ctx,
    )
    assert recovery.observed_outcome == "ADMIT"
    assert recovery.detail == RC_JOURNAL_REPLAY_DEDUP
    # Exactly one journaled operation; the replay was a deduped no-op.
    assert b4_ctx.store[_journal_key(op)]["applied"] is True

    # B0: the side effect is orphaned; a blind retry re-applies the write.
    b0_ctx = fresh_ctx()
    lost = run_baseline(BASELINE_B0, case, b0_ctx)
    assert lost.observed_outcome == "REJECT"
    assert lost.counted_as_success is False
    blind_retry = run_baseline(
        BASELINE_B0,
        make_case(case_id="contrast", operation_id=op, crash_point=CRASH_NONE),
        b0_ctx,
    )
    assert blind_retry.observed_outcome == "ADMIT"
    # The row was re-applied on top of the orphan (duplicate effect).
    assert b0_ctx.store[_row_key(op)] >= 2

    # B3: fsync cannot close the pre-WAL window; the side effect stays lost.
    b3_ctx = fresh_ctx()
    b3_lost = run_baseline(BASELINE_B3, case, b3_ctx)
    assert b3_lost.observed_outcome == "REJECT"
    assert b3_lost.detail == RC_OP_LOST_SIDE_EFFECT
    assert b3_lost.counted_as_success is False


def test_b4_pre_outbox_delivery_replay_is_deduped() -> None:
    """B4 crash at pre-outbox-delivery: recovery replay completes exactly-once."""
    ctx = fresh_ctx()
    case = make_case(crash_point=CRASH_PRE_OUTBOX_DELIVERY, delivery_schedule=(1, 2))
    first = run_baseline(BASELINE_B4, case, ctx)
    assert first.observed_outcome == "ADMIT"
    replay = run_baseline(
        BASELINE_B4,
        make_case(crash_point=CRASH_NONE, delivery_schedule=(1, 2)),
        ctx,
    )
    assert replay.observed_outcome == "ADMIT"
    assert replay.detail == RC_JOURNAL_REPLAY_DEDUP


def test_b5_monotonic_guard_rejects_stale_entry() -> None:
    """A journal entry behind the monotonic watermark is rejected on replay."""
    ctx = fresh_ctx()
    # Fresh write commits at sequence 1 and advances the watermark.
    outcome = run_baseline(BASELINE_B5, make_case(operation_id="op:seq-a"), ctx)
    assert outcome.observed_outcome == "ADMIT"
    assert ctx.store[_seq_key()] == 1
    # Forge a stale journal entry for another op (behind the watermark) and
    # attempt recovery: the monotonic guard rejects it, non-retriably.
    ctx.store[_journal_key("op:stale")] = {"applied": True, "seq": 0}
    stale = run_baseline(BASELINE_B5, make_case(operation_id="op:stale"), ctx)
    assert stale.observed_outcome == "REJECT"
    assert stale.detail == RC_JOURNAL_STALE_ENTRY
    assert stale.counted_as_success is False
    assert stale.retriable is False


def test_determinism_same_case_fresh_store() -> None:
    """Identical (case, fresh store) pairs yield identical outcomes."""
    for baseline_id in IN_PROCESS_ARMS:
        results = [
            run_baseline(baseline_id, make_case(delivery_schedule=(1, 2)), fresh_ctx())
            for _ in range(3)
        ]
        first = results[0]
        for other in results[1:]:
            assert other.to_dict() == first.to_dict()


# ---------------------------------------------------------------------------
# Adversarial controls.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", IN_PROCESS_ARMS)
def test_crash_before_wal_never_counts_as_success(baseline_id: str) -> None:
    """Crash-before-WAL is REJECT + retriable, never a phantom success."""
    ctx = fresh_ctx()
    case = make_case(crash_point=CRASH_PRE_COMMIT)
    outcome = run_baseline(baseline_id, case, ctx)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail == RC_OP_NOT_DURABLE
    # Nothing durable anywhere for this operation.
    assert _row_key("op:0001") not in ctx.store
    assert _idem_key("op:0001") not in ctx.store
    assert _journal_key("op:0001") not in ctx.store


def test_refuse_constant_stub_rejects_constant_adapter() -> None:
    """A stub that ignores the crash point is refused (rule 8)."""

    def constant_stub(probe: object) -> Outcome:
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=RC_OP_COMMITTED,
        )

    with pytest.raises(BaselineError) as excinfo:
        refuse_constant_stub(constant_stub)
    assert excinfo.value.reason_code == RC_STUB_CONSTANT


def test_refuse_constant_stub_admits_crash_sensitive_adapter() -> None:
    """An adapter that distinguishes clean vs crashed probes is admitted."""

    def faithful_adapter(probe: object) -> Outcome:
        crash_point = probe["crash_point"] if isinstance(probe, dict) else CRASH_NONE  # type: ignore[union-attr]
        if crash_point == CRASH_PRE_COMMIT:
            return Outcome(
                observed_outcome="REJECT",
                counted_as_success=False,
                retriable=True,
                detail=RC_OP_NOT_DURABLE,
            )
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=RC_OP_COMMITTED,
        )

    result = refuse_constant_stub(faithful_adapter)
    assert result.observed_outcome == "ADMIT"
    assert result.detail == RC_STUB_SEPARATION_OK
    assert result.counted_as_success is True


def test_unavailable_upstream_returns_not_run_external() -> None:
    """An unavailable upstream arm is NOT_RUN_EXTERNAL, never counted, never a toy."""
    outcome = run_baseline(BASELINE_B2_WORKFLOW, make_case(), fresh_ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is False
    assert outcome.detail == RC_BASELINE_UNAVAILABLE


def test_unknown_baseline_id_raises_wiring_error() -> None:
    with pytest.raises(BaselineError) as excinfo:
        run_baseline("B9-nonexistent", make_case(), fresh_ctx())
    assert excinfo.value.reason_code == "BASELINE_UNKNOWN_ID"


def test_non_mapping_case_raises_wiring_error() -> None:
    with pytest.raises(BaselineError) as excinfo:
        run_baseline(BASELINE_B0, ["not", "a", "mapping"], fresh_ctx())  # type: ignore[arg-type]
    assert excinfo.value.reason_code == RC_CASE_NOT_AN_OBJECT


def test_missing_case_field_raises_wiring_error() -> None:
    case = make_case()
    del case["crash_point"]
    with pytest.raises(BaselineError) as excinfo:
        run_baseline(BASELINE_B0, case, fresh_ctx())
    assert excinfo.value.reason_code == RC_CASE_MISSING_FIELD


def test_unknown_case_field_raises_wiring_error() -> None:
    case = make_case()
    case["reason_code"] = "LEAK_ATTEMPT"  # type: ignore[index]
    with pytest.raises(BaselineError) as excinfo:
        run_baseline(BASELINE_B0, case, fresh_ctx())
    assert excinfo.value.reason_code == RC_CASE_UNKNOWN_FIELD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", ""),
        ("operation_id", None),
        ("consent_epoch", -1),
        ("crash_point", "mid_wal"),
        ("delivery_schedule", [0]),
        ("delivery_schedule", "1,2"),
    ],
)
def test_badly_typed_case_fields_raise_wiring_error(field: str, value: object) -> None:
    case = make_case()
    case[field] = value  # type: ignore[literal-required]
    with pytest.raises(BaselineError) as excinfo:
        run_baseline(BASELINE_B4, case, fresh_ctx())
    assert excinfo.value.reason_code in (
        RC_CASE_BAD_TYPE,
        RC_CASE_EMPTY_OP_ID,
        RC_CRASH_POINT_UNKNOWN,
        RC_DELIVERY_SCHEDULE_BAD,
    )


def test_malformed_context_raises_wiring_error() -> None:
    with pytest.raises(BaselineError) as excinfo:
        run_baseline(BASELINE_B0, make_case(), {"store": {}})  # type: ignore[arg-type]
    assert excinfo.value.reason_code == RC_CONTEXT_MALFORMED
    with pytest.raises(BaselineError) as excinfo:
        run_baseline(BASELINE_B0, make_case(), BaselineContext(store={}, recovery_retries=0))
    assert excinfo.value.reason_code == RC_CONTEXT_MALFORMED
