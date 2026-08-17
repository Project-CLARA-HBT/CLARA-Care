from __future__ import annotations

from types import SimpleNamespace

import pytest

from evaluation.glhs_postgres_toctou.schedule_primitives import (
    TransactionTrace,
    classify_concurrent_commit_order,
    classify_proposal_order,
    elapsed_ms,
    new_idempotency_key,
    sha256_hex,
    snapshot_binding_digest,
)


def test_binding_digest_refuses_pre_binding_snapshot_contract() -> None:
    with pytest.raises(ValueError, match="snapshot_manifest_digest_contract_unavailable"):
        snapshot_binding_digest(SimpleNamespace(snapshot_id="legacy"))


def test_binding_digest_accepts_only_manifest_digest() -> None:
    assert snapshot_binding_digest(SimpleNamespace(manifest_digest="a" * 64)) == (
        "a" * 64,
        "manifest_digest",
    )


def test_concurrent_commit_classifier_does_not_hide_post_revoke_commit() -> None:
    assert classify_concurrent_commit_order(
        outcome="transition_committed",
        revoke_commit_ns=10,
        commit_start_ns=11,
        commit_complete_ns=12,
    ) == ("forbidden_transition_committed_after_observed_revoke", True)


def test_concurrent_commit_classifier_keeps_overlapping_commit_indeterminate() -> None:
    assert classify_concurrent_commit_order(
        outcome="transition_committed",
        revoke_commit_ns=12,
        commit_start_ns=10,
        commit_complete_ns=13,
    ) == ("indeterminate_ordering_transition_committed", None)


def test_concurrent_commit_classifier_accepts_commit_before_revoke() -> None:
    assert classify_concurrent_commit_order(
        outcome="transition_committed",
        revoke_commit_ns=15,
        commit_start_ns=10,
        commit_complete_ns=12,
    ) == ("transition_committed_before_observed_revoke_commit", False)


def test_concurrent_commit_classifier_rejection_is_not_forbidden() -> None:
    assert classify_concurrent_commit_order(
        outcome="assertion_consent_mismatch",
        revoke_commit_ns=5,
        commit_start_ns=11,
        commit_complete_ns=12,
    ) == ("rejected_after_observed_revoke_commit", False)


def test_proposal_classifier_keeps_unproven_order_indeterminate() -> None:
    assert classify_proposal_order(
        outcome="proposal_committed",
        revoke_commit_ns=12,
        proposal_complete_ns=13,
    ) == ("indeterminate_ordering_proposal_committed", None)


def test_proposal_classifier_accepts_proven_commit_before_revoke() -> None:
    assert classify_proposal_order(
        outcome="proposal_committed",
        revoke_commit_ns=15,
        proposal_complete_ns=12,
    ) == ("proposal_committed_before_observed_revoke_commit", False)


def test_idempotency_keys_are_unique_with_stable_prefix() -> None:
    first = new_idempotency_key("w4-schedule")
    second = new_idempotency_key("w4-schedule")
    assert first.startswith("w4-schedule:")
    assert first != second


def test_sha256_hex_is_deterministic() -> None:
    assert sha256_hex("canonical") == sha256_hex("canonical")
    assert len(sha256_hex("x")) == 64


def test_elapsed_ms_is_positive_and_rounded() -> None:
    started = elapsed_ms.__globals__["now_monotonic_ns"]()
    duration = elapsed_ms(started)
    assert duration >= 0.0
    assert isinstance(duration, float)


class _TracedSession:
    backend_pid = 4242
    txid = 99


def test_transaction_trace_records_boundaries_with_pid_and_txid() -> None:
    trace = TransactionTrace()
    session = _TracedSession()
    trace.begin(session)
    trace.commit(session)

    events = trace.events
    assert [e.event for e in events] == ["begin", "commit"]
    assert events[0].backend_pid == 4242
    assert events[0].txid == 99
    assert events[0].monotonic_ns <= events[1].monotonic_ns


def test_transaction_trace_captures_missing_session_metadata_as_none() -> None:
    trace = TransactionTrace()
    trace.begin()
    assert trace.events[0].backend_pid is None
    assert trace.events[0].txid is None


def test_transaction_trace_records_rollback_and_lock_wait() -> None:
    trace = TransactionTrace()
    trace.begin()
    trace.lock_wait(lock="profile:1", waited_ns=42, acquired=False)
    trace.rollback()

    assert [e.event for e in trace.events] == ["begin", "rollback"]
    assert trace.lock_waits[0].lock == "profile:1"
    assert trace.lock_waits[0].waited_ns == 42
    assert trace.lock_waits[0].acquired is False

    serialized = trace.to_dict()
    assert serialized["events"][-1]["event"] == "rollback"
    assert serialized["lock_waits"][0]["lock"] == "profile:1"
