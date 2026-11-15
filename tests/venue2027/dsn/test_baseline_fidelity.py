"""Baseline fidelity vectors for DSN-baseline_tests (Task DSN-baseline_tests).

Purpose
-------
Fidelity suite for the DSN 2027 strong-baseline arms implemented in
``evaluation/venue2027/dsn/baselines.py`` (the REAL baseline module, imported
directly — no reimplementation, no fork, no stub). For EACH implemented arm
(B0-single-write, B1-outbox-idempotent, B3-fsync, B4-candidate-journal,
B5-monotonic-journal) this module records, as upstream-style vectors:

- one POSITIVE vector: the arm behaves exactly as its documented guarantee
  says on a valid case (B1 dedups duplicate deliveries on the idempotency
  key; B4/B5 reconcile exactly-once across the crash window via the
  write-ahead journal; B0/B3 commit a clean window);

- one ADVERSARIAL NEGATIVE vector into the arm's DOCUMENTED WEAK SPOT: the
  observable misbehaviour the blueprint keeps the baseline for is asserted
  verbatim, because that weakness is definitional to the study's comparison
  (B0 loses the operation on a pre-commit crash and leaves an orphaned side
  effect whose blind retry re-applies it — duplicate; B3 loses the side
  effect in its pre-WAL window and reports it honestly; B1's idempotency
  key re-acks a retry without re-applying — the observable exactly-once
  cap; B4 dedups a journaled replay to a no-op; B5 rejects a stale journal
  entry behind the monotonic watermark, non-retriably).

Plus the pinned external arm B2-durable-workflow: it MUST report
``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` — never counted as success,
never retriable, never silently treated as a passing comparison arm
(EXECUTION_CONTRACT rule 8: never replace an unavailable baseline by a toy
under the same name).

Allowed input
-------------
Only synthetic crash-window cases (``case_id``, ``operation_id``,
``crash_point``, ``delivery_schedule``, ``consent_epoch``) accepted by
``baselines.run_baseline`` with injected fresh ``BaselineContext`` stores;
no network, no database, no clock, no randomness, no live provider, no
real PHI/PII. All timestamps are caller-supplied logical integers.

Failure semantics
-----------------
A vector fails the suite when the real module deviates from its declared
semantics (a weak arm wrongly surviving its documented weak spot, a strong
arm losing exactly-once, or the external pinned arm masquerading as a
counted outcome). Errors surface as normal assertion failures with the
structured harness ``Outcome``; wiring errors surface as
``BaselineError`` with stable reason codes and are never counted as safe
rejections.

Version
-------
``BASELINE_FIDELITY_VECTORS_VERSION = "1.0.0"`` over
``BASELINES_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import typing

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dsn import baselines
from evaluation.venue2027.dsn.baselines import BASELINES_VERSION

BASELINE_FIDELITY_VECTORS_VERSION = "1.0.0"

B0 = baselines.BASELINE_B0
B1 = baselines.BASELINE_B1
B2_EXTERNAL = baselines.BASELINE_B2_WORKFLOW
B3 = baselines.BASELINE_B3
B4 = baselines.BASELINE_B4
B5 = baselines.BASELINE_B5

IN_PROCESS_ARMS = (B0, B1, B3, B4, B5)

CRASH_NONE = baselines.CRASH_NONE
CRASH_PRE_COMMIT = baselines.CRASH_PRE_COMMIT
CRASH_POST_COMMIT_PRE_RESPONSE = baselines.CRASH_POST_COMMIT_PRE_RESPONSE
CRASH_PRE_OUTBOX_DELIVERY = baselines.CRASH_PRE_OUTBOX_DELIVERY

_RC_LOST = baselines.RC_OP_LOST_SIDE_EFFECT
_RC_NOT_DURABLE = baselines.RC_OP_NOT_DURABLE
_RC_COMMITTED = baselines.RC_OP_COMMITTED
_RC_IDEM_RETRY = baselines.RC_OP_COMMITTED_IDEMPOTENT_RETRY
_RC_JOURNAL_DEDUP = baselines.RC_JOURNAL_REPLAY_DEDUP
_RC_JOURNAL_STALE = baselines.RC_JOURNAL_STALE_ENTRY
_RC_UNAVAILABLE = baselines.RC_BASELINE_UNAVAILABLE

_row_key = baselines._row_key
_outbox_key = baselines._outbox_key
_idem_key = baselines._idem_key
_journal_key = baselines._journal_key
_seq_key = baselines._seq_key


def _case(
    case_id: str,
    operation_id: str,
    crash_point: str = CRASH_NONE,
    delivery_schedule: tuple[int, ...] = (1,),
    consent_epoch: int = 3,
) -> dict[str, typing.Any]:
    return {
        "case_id": case_id,
        "operation_id": operation_id,
        "crash_point": crash_point,
        "delivery_schedule": list(delivery_schedule),
        "consent_epoch": consent_epoch,
    }


def _run(baseline_id: str, case: dict[str, typing.Any]) -> Outcome:
    """Drive the REAL module through its public dispatcher; fresh store per call."""
    return baselines.run_baseline(baseline_id, case, baselines.BaselineContext(store={}))


def _replay(
    baseline_id: str,
    case: dict[str, typing.Any],
    store: dict[str, typing.Any],
) -> Outcome:
    """Recovery replay through the SAME store (post-crash retry under one op id)."""
    return baselines.run_baseline(
        baseline_id, dict(case, crash_point=CRASH_NONE), baselines.BaselineContext(store=store)
    )


# ---------------------------------------------------------------------------
# Module pin: the REAL baseline module, version-asserted (no fork).
# ---------------------------------------------------------------------------


def test_real_module_pinned_version() -> None:
    assert BASELINES_VERSION == "1.0.0"
    assert baselines.BASELINE_REGISTRY[B2_EXTERNAL].runnable_in_process is False
    for arm in IN_PROCESS_ARMS:
        assert baselines.BASELINE_REGISTRY[arm].runnable_in_process is True


# ---------------------------------------------------------------------------
# B0-single-write — weak control; weak spot = lost / duplicated side effects.
# ---------------------------------------------------------------------------


def test_b0_positive_clean_window_commits() -> None:
    """POSITIVE: on a clean window with one delivery, B0 commits the row and
    applies the side effect (its documented happy path)."""
    store: dict[str, typing.Any] = {}
    outcome = baselines.run_baseline(
        B0, _case("fidelity/B0/pos", "op:b0-pos"), baselines.BaselineContext(store=store)
    )
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    assert outcome.retriable is False
    assert outcome.detail == _RC_COMMITTED
    # Observable: one durable write + exactly one delivery landed.
    assert store[_row_key("op:b0-pos")] == 2


def test_b0_negative_pre_commit_crash_loses_operation() -> None:
    """ADVERSARIAL NEGATIVE (documented weak spot 1): a crash before the
    durable write loses the operation entirely — B0 has no journal, so the
    loss is a silent REJECT/retry with nothing durable anywhere."""
    store: dict[str, typing.Any] = {}
    outcome = baselines.run_baseline(
        B0,
        _case("fidelity/B0/neg-lost", "op:b0-lost", crash_point=CRASH_PRE_COMMIT),
        baselines.BaselineContext(store=store),
    )
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail == _RC_NOT_DURABLE
    # Nothing durable: the write was lost, not safely rejected.
    assert store == {}


def test_b0_negative_post_commit_crash_orphans_side_effect_and_retry_duplicates() -> None:
    """ADVERSARIAL NEGATIVE (documented weak spot 2): after a
    post-commit crash the row is durable but the fire-and-forget side
    effect is orphaned; a blind retry re-applies the write — the duplicate
    the blueprint keeps B0 around to measure."""
    store: dict[str, typing.Any] = {}
    lost = baselines.run_baseline(
        B0,
        _case(
            "fidelity/B0/neg-dup",
            "op:b0-dup",
            crash_point=CRASH_POST_COMMIT_PRE_RESPONSE,
        ),
        baselines.BaselineContext(store=store),
    )
    assert lost.observed_outcome == "REJECT"
    assert lost.counted_as_success is False
    assert lost.detail == _RC_LOST
    # The orphan row persisted even though the caller never got an ack...
    assert _row_key("op:b0-dup") in store
    # ...and the blind recovery retry re-applies the write on top (duplicate).
    blind = _replay(B0, _case("fidelity/B0/neg-dup", "op:b0-dup"), store)
    assert blind.observed_outcome == "ADMIT"
    assert store[_row_key("op:b0-dup")] >= 2  # duplicate side effect observed


# ---------------------------------------------------------------------------
# B1-outbox-idempotent — strong practical baseline; idempotency-key dedup.
# ---------------------------------------------------------------------------


def test_b1_positive_duplicate_deliveries_dedup_by_idempotency_key() -> None:
    """POSITIVE: under at-least-once replay B1 re-acks the original outcome
    without re-applying the effect — the documented idempotent-consumer cap."""
    store: dict[str, typing.Any] = {}
    ctx = baselines.BaselineContext(store=store)
    first = baselines.run_baseline(
        B1, _case("fidelity/B1/pos", "op:b1-pos", delivery_schedule=(1, 2, 3)), ctx
    )
    assert first.observed_outcome == "ADMIT"
    assert first.counted_as_success is True
    assert first.detail == _RC_COMMITTED
    assert store[_idem_key("op:b1-pos")] == 1
    # Duplicate deliveries replay through the same store: deduped, no re-apply.
    replay = baselines.run_baseline(
        B1,
        _case("fidelity/B1/pos-retry", "op:b1-pos", delivery_schedule=(4, 5)),
        baselines.BaselineContext(store=store),
    )
    assert replay.observed_outcome == "ADMIT"
    assert replay.counted_as_success is True
    assert replay.detail == _RC_IDEM_RETRY
    assert store[_idem_key("op:b1-pos")] == 1  # key never re-recorded


def test_b1_negative_post_commit_crash_reacks_without_reapplying() -> None:
    """ADVERSARIAL NEGATIVE (fidelity of the dedup boundary): after a
    post-commit crash the ack is lost, but the durable idempotency key makes
    the recovery replay a re-ack — never a second effect application. A B1
    that re-applied here would falsify the strong baseline; a B1 that stayed
    INDETERMINATE would understate it. Assert the exact documented behaviour."""
    store: dict[str, typing.Any] = {}
    ctx = baselines.BaselineContext(store=store)
    first = baselines.run_baseline(
        B1,
        _case("fidelity/B1/neg", "op:b1-crash", crash_point=CRASH_POST_COMMIT_PRE_RESPONSE),
        ctx,
    )
    # Row + outbox + idem key are durable even though the ack was lost.
    assert store[_row_key("op:b1-crash")] == 1
    assert _outbox_key("op:b1-crash") in store
    assert store[_idem_key("op:b1-crash")] == 1
    assert first.observed_outcome == "ADMIT"
    assert first.counted_as_success is True
    # Recovery replay re-acks the ORIGINAL outcome; the row is never bumped.
    recovery = _replay(B1, _case("fidelity/B1/neg", "op:b1-crash"), store)
    assert recovery.observed_outcome == "ADMIT"
    assert recovery.detail == _RC_IDEM_RETRY
    assert store[_row_key("op:b1-crash")] == 1  # exactly-once observed


def test_b1_negative_pre_commit_crash_is_retriable_reject() -> None:
    """ADVERSARIAL NEGATIVE: with nothing durable B1 must not fake a commit;
    the operation is REJECTed as not durable and retriable for recovery."""
    outcome = baselines.run_baseline(
        B1, _case("fidelity/B1/neg-precommit", "op:b1-precommit", crash_point=CRASH_PRE_COMMIT),
        baselines.BaselineContext(store={}),
    )
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail == _RC_NOT_DURABLE


# ---------------------------------------------------------------------------
# B3-fsync — durability posture control; weak spot = pre-WAL side-effect loss.
# ---------------------------------------------------------------------------


def test_b3_positive_clean_window_commits_with_fsync_delivery() -> None:
    """POSITIVE: on a clean window B3 fsyncs every acknowledged write and
    commits the row with its delivery schedule applied."""
    store: dict[str, typing.Any] = {}
    outcome = baselines.run_baseline(
        B3,
        _case("fidelity/B3/pos", "op:b3-pos", delivery_schedule=(1, 2)),
        baselines.BaselineContext(store=store),
    )
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    assert outcome.detail == _RC_COMMITTED
    # One fsync'd row write + both scheduled deliveries.
    assert store[_row_key("op:b3-pos")] == 3


def test_b3_negative_pre_wal_crash_loses_side_effect() -> None:
    """ADVERSARIAL NEGATIVE (documented weak spot): fsync closes per-channel
    torn writes but cannot close the cross-channel window — a crash between
    the acknowledged row fsync and the side-effect record's durable surface
    loses the side effect. The arm reports it honestly as a LOST side effect
    (REJECT), never a phantom success."""
    store: dict[str, typing.Any] = {}
    lost = baselines.run_baseline(
        B3,
        _case("fidelity/B3/neg", "op:b3-lost", crash_point=CRASH_POST_COMMIT_PRE_RESPONSE),
        baselines.BaselineContext(store=store),
    )
    assert lost.observed_outcome == "REJECT"
    assert lost.counted_as_success is False
    assert lost.detail == _RC_LOST
    # The fsync'd row is durable (the exposed window), the side effect is not.
    assert store[_row_key("op:b3-lost")] == 1
    # And the paired no-crash run on a fresh store does NOT lose it (the
    # weakness is the crash window, not the arm's clean behaviour).
    clean = baselines.run_baseline(
        B3, _case("fidelity/B3/neg-clean", "op:b3-lost"), baselines.BaselineContext(store={})
    )
    assert clean.observed_outcome == "ADMIT"
    assert clean.detail == _RC_COMMITTED


def test_b3_negative_pre_commit_crash_has_no_durable_evidence() -> None:
    """ADVERSARIAL NEGATIVE: fsync of nothing — a pre-commit crash leaves no
    durable evidence on any channel and is a retriable REJECT, never a count."""
    store: dict[str, typing.Any] = {}
    outcome = baselines.run_baseline(
        B3, _case("fidelity/B3/neg-precommit", "op:b3-precommit", crash_point=CRASH_PRE_COMMIT),
        baselines.BaselineContext(store=store),
    )
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail == _RC_NOT_DURABLE
    assert store == {}


# ---------------------------------------------------------------------------
# B4-candidate-journal — write-ahead journal; exactly-once across the crash.
# ---------------------------------------------------------------------------


def test_b4_positive_journal_replay_after_crash_is_exactly_once() -> None:
    """POSITIVE: the write-ahead journal survives the crash window, so the
    recovery replay dedups to a no-op re-ack — exactly-once where B0 loses /
    duplicates and B3 leaves the side effect exposed."""
    store: dict[str, typing.Any] = {}
    ctx = baselines.BaselineContext(store=store)
    first = baselines.run_baseline(
        B4,
        _case("fidelity/B4/pos", "op:b4-pos", crash_point=CRASH_POST_COMMIT_PRE_RESPONSE),
        ctx,
    )
    assert first.observed_outcome == "ADMIT"
    assert first.counted_as_success is True
    assert first.detail == _RC_COMMITTED
    # Journal was made durable BEFORE the channel writes and is applied.
    assert store[_journal_key("op:b4-pos")]["applied"] is True
    recovery = _replay(B4, _case("fidelity/B4/pos", "op:b4-pos"), store)
    assert recovery.observed_outcome == "ADMIT"
    assert recovery.counted_as_success is True
    assert recovery.detail == _RC_JOURNAL_DEDUP


def test_b4_positive_clean_window_caps_delivery_replay_at_once() -> None:
    """POSITIVE: journal dedup caps at-least-once delivery replays: the
    applied_count records the attempts while the effect stays exactly-once."""
    store: dict[str, typing.Any] = {}
    ctx = baselines.BaselineContext(store=store)
    outcome = baselines.run_baseline(
        B4, _case("fidelity/B4/pos-sched", "op:b4-sched", delivery_schedule=(1, 2, 3)), ctx
    )
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.detail == _RC_COMMITTED
    journal = store[_journal_key("op:b4-sched")]
    assert journal["applied"] is True
    assert journal["applied_count"] == 3  # attempts recorded...
    # ...but a further recovery replay is still deduped to a no-op.
    replay = _replay(B4, _case("fidelity/B4/pos-sched", "op:b4-sched"), store)
    assert replay.detail == _RC_JOURNAL_DEDUP


def test_b4_negative_pre_commit_journal_loss_is_retriable_reject() -> None:
    """ADVERSARIAL NEGATIVE (documented weak spot): if the journal write
    itself is lost to a pre-commit crash, the candidate has NO durable
    evidence either — it must fail closed as a retriable REJECT, never
    coerce the loss into a commit."""
    store: dict[str, typing.Any] = {}
    outcome = baselines.run_baseline(
        B4, _case("fidelity/B4/neg", "op:b4-lost", crash_point=CRASH_PRE_COMMIT),
        baselines.BaselineContext(store=store),
    )
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail == _RC_NOT_DURABLE
    assert store == {}


# ---------------------------------------------------------------------------
# B5-monotonic-journal — B4 plus the stale-entry guard.
# ---------------------------------------------------------------------------


def test_b5_positive_fresh_write_advances_watermark_and_replay_dedups() -> None:
    """POSITIVE: a fresh write takes the next sequence above the watermark
    (the guard never blocks legitimate forward progress) and its recovery
    replay dedups like B4."""
    store: dict[str, typing.Any] = {}
    ctx = baselines.BaselineContext(store=store)
    first = baselines.run_baseline(
        B5, _case("fidelity/B5/pos", "op:b5-pos"), ctx
    )
    assert first.observed_outcome == "ADMIT"
    assert first.counted_as_success is True
    assert first.detail == _RC_COMMITTED
    assert store[_seq_key()] == 1
    assert store[_journal_key("op:b5-pos")]["seq"] == 1
    replay = _replay(B5, _case("fidelity/B5/pos", "op:b5-pos"), store)
    assert replay.observed_outcome == "ADMIT"
    assert replay.detail == _RC_JOURNAL_DEDUP


def test_b5_negative_stale_journal_entry_rejected_non_retriably() -> None:
    """ADVERSARIAL NEGATIVE (documented weak spot of B5's predecessor,
    guarded here): a journal entry whose sequence is behind the committed
    monotonic watermark cannot resurrect a superseded state — recovery
    rejects it non-retriably, and the watermark is untouched."""
    store: dict[str, typing.Any] = {}
    ctx = baselines.BaselineContext(store=store)
    # Advance the watermark with a legitimate op first.
    assert baselines.run_baseline(B5, _case("fidelity/B5/advance", "op:b5-seq1"), ctx).observed_outcome == "ADMIT"
    # Forge a stale applied entry behind the watermark and attempt recovery.
    store[_journal_key("op:b5-stale")] = {"applied": True, "seq": 0}
    stale = baselines.run_baseline(
        B5, _case("fidelity/B5/neg-stale", "op:b5-stale"), ctx
    )
    assert stale.observed_outcome == "REJECT"
    assert stale.counted_as_success is False
    assert stale.retriable is False  # stale evidence is final, not a retry
    assert stale.detail == _RC_JOURNAL_STALE
    assert store[_seq_key()] == 1  # watermark not advanced by the stale entry


def test_b5_negative_pre_commit_crash_is_retriable_reject() -> None:
    """ADVERSARIAL NEGATIVE: a pre-commit crash leaves B5 with nothing
    durable — retriable REJECT, never a counted outcome."""
    store: dict[str, typing.Any] = {}
    outcome = baselines.run_baseline(
        B5, _case("fidelity/B5/neg-precommit", "op:b5-precommit", crash_point=CRASH_PRE_COMMIT),
        baselines.BaselineContext(store=store),
    )
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail == _RC_NOT_DURABLE
    assert store == {}


# ---------------------------------------------------------------------------
# Pinned external arm B2-durable-workflow: NOT_RUN_EXTERNAL, never a toy.
# ---------------------------------------------------------------------------


def test_b2_external_pinned_reports_not_run_external_and_never_counts() -> None:
    """The pinned durable-workflow engine is absent from this worktree, so
    the arm reports NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE: never counted as
    success, never retriable, never silently treated as a passing arm — and
    a crash window must not change that (no toy substitution, rule 8)."""
    spec = baselines.BASELINE_REGISTRY[B2_EXTERNAL]
    assert spec.runnable_in_process is False
    assert spec.upstream_revision == "UNAVAILABLE"
    for crash_point in (CRASH_NONE, CRASH_PRE_COMMIT, CRASH_POST_COMMIT_PRE_RESPONSE):
        outcome = baselines.run_baseline(
            B2_EXTERNAL,
            _case("fidelity/B2/ext", "op:b2-ext", crash_point=crash_point),
            baselines.BaselineContext(store={}),
        )
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.retriable is False
        assert outcome.detail == _RC_UNAVAILABLE


# ---------------------------------------------------------------------------
# Cross-arm fidelity: the blueprint's core separation on identical cases.
# ---------------------------------------------------------------------------


def test_cross_arm_separation_b4_exactly_once_b0_duplicates_b3_loses() -> None:
    """The same post-commit crash window replayed through recovery: B4
    reconciles exactly-once (journal dedup), B0's blind retry re-applies the
    orphaned effect (duplicate), B3 reports the lost side effect. The
    three-way divergence is the study's RQ1 witness, as observable behaviour."""
    op = "op:contrast"
    case = _case("fidelity/contrast", op, crash_point=CRASH_POST_COMMIT_PRE_RESPONSE)

    b4_store: dict[str, typing.Any] = {}
    baselines.run_baseline(B4, case, baselines.BaselineContext(store=b4_store))
    b4_recovery = _replay(B4, case, b4_store)
    assert b4_recovery.detail == _RC_JOURNAL_DEDUP

    b0_store: dict[str, typing.Any] = {}
    baselines.run_baseline(B0, case, baselines.BaselineContext(store=b0_store))
    b0_blind = _replay(B0, case, b0_store)
    assert b0_blind.observed_outcome == "ADMIT"
    assert b0_store[_row_key(op)] >= 2  # duplicated effect

    b3_store: dict[str, typing.Any] = {}
    b3_lost = baselines.run_baseline(B3, case, baselines.BaselineContext(store=b3_store))
    assert b3_lost.detail == _RC_LOST

    # The candidate never duplicates on the identical window.
    assert b4_recovery.observed_outcome == "ADMIT"
    assert b4_store[_journal_key(op)]["applied"] is True


def test_refuse_constant_stub_refuses_crash_insensitive_candidate() -> None:
    """Rule-8 hygiene: a candidate that ignores the crash point is refused."""
    def constant_stub(_probe: object) -> Outcome:
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=_RC_COMMITTED,
        )

    with pytest.raises(baselines.BaselineError) as excinfo:
        baselines.refuse_constant_stub(constant_stub)
    assert excinfo.value.reason_code == baselines.RC_STUB_CONSTANT


def test_wiring_errors_fail_closed_not_counted() -> None:
    """Unknown baseline ids and malformed cases raise BaselineError — wiring
    errors, never silent outcomes that could be counted as rejections."""
    with pytest.raises(baselines.BaselineError) as unknown:
        baselines.run_baseline("B9-nonexistent", _case("fidelity/fc/1", "op:fc"), _run.__defaults__ or baselines.BaselineContext(store={}))  # type: ignore[arg-type]
    assert unknown.value.reason_code == baselines.RC_BASELINE_UNKNOWN_ID
    with pytest.raises(baselines.BaselineError) as malformed:
        baselines.run_baseline(B0, 42, baselines.BaselineContext(store={}))  # type: ignore[arg-type]
    assert malformed.value.reason_code == baselines.RC_CASE_NOT_AN_OBJECT
