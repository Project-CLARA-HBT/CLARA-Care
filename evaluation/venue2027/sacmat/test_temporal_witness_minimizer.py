"""Tests for SACMAT-X09_minimizer — Delta-debugging witness minimizer.

Validates the delta-debugging reduction of fault-revealing temporal policy traces
under the audited DSL semantics (:mod:`evaluation.venue2027.sacmat.policy_trace_dsl`).

Covers:
- Positive controls:
  - 10-event trace reduced to 3 essential events (DELEGATION_CYCLE preserving granting context).
  - 10-event trace reduced to 2 essential events (DELEGATION_CYCLE between two ungranted delegates).
  - 10-event trace reduced to 2 essential events under a custom predicate (unauthorized revoke + access).
  - 10-event trace reduced to 4 essential events (REVOKED_ACTOR_TRANSITIVITY).
  - Length invariant: len(minimized) <= len(original).
  - 1-minimality guarantee: removing any further event eliminates the fault.
  - JSON serialization of MinimizedTrace records.
  - Convenience contract minimize(trace, predicate) -> PolicyTrace.
  - Idempotence and determinism across repeat runs.
- Adversarial controls:
  - Trace without fault raises MinimizerError with NO_FAULT_DETECTED.
  - Oracle predicate returning False raises NO_FAULT_DETECTED.
  - Non-monotonic timestamps (unordered) refused with NON_MONOTONIC_TIMESTAMPS.
  - Non-monotonic timestamps (duplicates) refused with NON_MONOTONIC_TIMESTAMPS.
  - Non-monotonic timestamps in dict payloads refused with NON_MONOTONIC_TIMESTAMPS.
  - Empty trace refused with EMPTY_TRACE.
  - Non-matching target_fault raises TARGET_FAULT_NOT_FOUND.
  - Malformed trace / event structures refused with MALFORMED_TRACE.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from evaluation.venue2027.sacmat.policy_trace_dsl import (
    EVENT_KIND_ACCESS,
    EVENT_KIND_DELEGATE,
    EVENT_KIND_GRANT,
    EVENT_KIND_REVOKE,
    FINDING_DELEGATION_CYCLE,
    FINDING_REVOKE_BEFORE_GRANT,
    FINDING_REVOKED_ACTOR_TRANSITIVITY,
    OUTCOME_DENY,
    OUTCOME_PERMIT,
    POLICY_TRACE_DSL_VERSION,
    Event,
    PolicyTrace,
    evaluate_trace,
)
from evaluation.venue2027.sacmat.temporal_witness_minimizer import (
    REASON_EMPTY_TRACE_CODE,
    REASON_MALFORMED_TRACE,
    REASON_NO_FAULT_DETECTED,
    REASON_NON_MONOTONIC_TIMESTAMPS,
    REASON_TARGET_FAULT_NOT_FOUND,
    TEMPORAL_WITNESS_MINIMIZER_VERSION,
    MinimizedTrace,
    MinimizerError,
    is_1_minimal,
    minimize,
    minimize_witness,
)

TENANT = "tenant-minimizer"
RESOURCE = "patient_vitals"
PURPOSE = "emergency_access"
STATE = "epoch-01"


def make_event(
    kind: str,
    principal: str,
    logical_time: int,
    *,
    policy_state: str = STATE,
) -> Event:
    return Event(
        principal=principal,
        tenant=TENANT,
        resource=RESOURCE,
        purpose=PURPOSE,
        policy_state=policy_state,
        logical_time=logical_time,
        kind=kind,
    )


def make_trace(events: Sequence[Event], trace_id: str = "trace-test") -> PolicyTrace:
    return PolicyTrace(trace_id=trace_id, events=tuple(events))


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_10_events_minimized_to_3_essential_events_with_granting_context() -> None:
    """10 events with 7 extraneous events minimized to exactly 3 essential events.

    Essential events:
    1. GRANT to alice at t=10 (granting context required so no spurious REVOKE_BEFORE_GRANT appears)
    2. DELEGATE alice -> bob at t=30
    3. DELEGATE bob -> alice at t=70 (closes delegation cycle)
    Extraneous events: grants and accesses for other principals (carol, dave, etc.).
    """
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_GRANT, "carol", 20),
        make_event(EVENT_KIND_DELEGATE, "alice", 30, policy_state="bob"),
        make_event(EVENT_KIND_ACCESS, "carol", 40),
        make_event(EVENT_KIND_GRANT, "dave", 50),
        make_event(EVENT_KIND_ACCESS, "dave", 60),
        make_event(EVENT_KIND_DELEGATE, "bob", 70, policy_state="alice"),
        make_event(EVENT_KIND_ACCESS, "carol", 80),
        make_event(EVENT_KIND_GRANT, "eve", 90),
        make_event(EVENT_KIND_ACCESS, "eve", 100),
    )
    trace = make_trace(events, trace_id="trace-cycle-10")
    assert len(trace.events) == 10

    # Initial evaluation should expose DELEGATION_CYCLE without spurious findings
    initial_verdict = evaluate_trace(trace)
    assert any(f.kind == FINDING_DELEGATION_CYCLE for f in initial_verdict.findings)

    minimized: MinimizedTrace = minimize_witness(trace, oracle=evaluate_trace)

    # 1. Length guarantees
    assert minimized.original_event_count == 10
    assert minimized.minimized_event_count == 3
    assert len(minimized) == 3
    assert len(minimized.events) <= len(trace.events)
    assert minimized.reduction_ratio == 0.7

    # 2. Semantic fault preserved on oracle
    verdict = evaluate_trace(minimized.trace)
    kinds = [f.kind for f in verdict.findings]
    assert kinds == [FINDING_DELEGATION_CYCLE]
    assert FINDING_REVOKE_BEFORE_GRANT not in kinds
    assert minimized.fault == FINDING_DELEGATION_CYCLE

    # 3. Granting context preserved: alice's grant is still in the witness
    principals_and_kinds = [(e.principal, e.kind) for e in minimized.events]
    assert principals_and_kinds == [
        ("alice", EVENT_KIND_GRANT),
        ("alice", EVENT_KIND_DELEGATE),
        ("bob", EVENT_KIND_DELEGATE),
    ]

    # 4. 1-minimality verified
    assert minimized.is_1_minimal is True
    assert is_1_minimal(minimized.trace, evaluate_trace) is True

    # 5. Removing any of the 3 events eliminates the fault or corrupts context
    for i in range(3):
        cand = minimized.events[:i] + minimized.events[i + 1 :]
        cand_trace = PolicyTrace(trace_id="test-sub", events=cand)
        cand_verdict = evaluate_trace(cand_trace)
        # Either DELEGATION_CYCLE disappears, or new findings (REVOKE_BEFORE_GRANT) appear
        cand_kinds = [f.kind for f in cand_verdict.findings]
        assert cand_kinds != [FINDING_DELEGATION_CYCLE]


def test_positive_10_events_minimized_to_2_essential_events_cycle() -> None:
    """10 events minimized to 2 essential events for an ungranted delegation cycle."""
    events = (
        make_event(EVENT_KIND_GRANT, "carol", 10),
        make_event(EVENT_KIND_ACCESS, "carol", 20),
        make_event(EVENT_KIND_DELEGATE, "actor_a", 25, policy_state="actor_b"),
        make_event(EVENT_KIND_ACCESS, "carol", 30),
        make_event(EVENT_KIND_GRANT, "dave", 40),
        make_event(EVENT_KIND_ACCESS, "dave", 50),
        make_event(EVENT_KIND_ACCESS, "carol", 60),
        make_event(EVENT_KIND_DELEGATE, "actor_b", 75, policy_state="actor_a"),
        make_event(EVENT_KIND_GRANT, "eve", 85),
        make_event(EVENT_KIND_ACCESS, "eve", 95),
    )
    trace = make_trace(events, trace_id="trace-cycle-ungranted-10")
    minimized = minimize_witness(
        trace,
        oracle=evaluate_trace,
        target_fault=FINDING_DELEGATION_CYCLE,
    )

    assert minimized.original_event_count == 10
    assert minimized.minimized_event_count == 2
    assert len(minimized.events) == 2
    assert minimized.is_1_minimal is True
    assert (
        is_1_minimal(minimized.trace, evaluate_trace, target_fault=FINDING_DELEGATION_CYCLE) is True
    )

    # Check the 2 events are the cyclic delegations
    expected_pairs = [("actor_a", "actor_b"), ("actor_b", "actor_a")]
    actual_pairs = [(e.principal, e.policy_state) for e in minimized.events]
    assert actual_pairs == expected_pairs


def test_positive_10_events_minimized_to_2_essential_events_custom_predicate() -> None:
    """10 events minimized to 2 essential events using a custom predicate."""

    def intruder_predicate(trace: PolicyTrace) -> bool:
        has_revoke = any(
            e.kind == EVENT_KIND_REVOKE and e.principal == "intruder" for e in trace.events
        )
        has_access = any(
            e.kind == EVENT_KIND_ACCESS and e.principal == "intruder" for e in trace.events
        )
        return has_revoke and has_access

    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_ACCESS, "alice", 20),
        make_event(EVENT_KIND_REVOKE, "intruder", 25),
        make_event(EVENT_KIND_ACCESS, "alice", 30),
        make_event(EVENT_KIND_GRANT, "carol", 40),
        make_event(EVENT_KIND_ACCESS, "carol", 50),
        make_event(EVENT_KIND_GRANT, "dave", 60),
        make_event(EVENT_KIND_ACCESS, "dave", 70),
        make_event(EVENT_KIND_ACCESS, "alice", 80),
        make_event(EVENT_KIND_ACCESS, "intruder", 90),
    )
    trace = make_trace(events, trace_id="trace-pred-10")

    minimized = minimize_witness(trace, oracle=intruder_predicate)

    assert minimized.original_event_count == 10
    assert minimized.minimized_event_count == 2
    assert len(minimized) == 2
    assert minimized.is_1_minimal is True

    events_summary = [(e.principal, e.kind) for e in minimized.events]
    assert events_summary == [
        ("intruder", EVENT_KIND_REVOKE),
        ("intruder", EVENT_KIND_ACCESS),
    ]

    # Verify 1-minimality: removing either event makes intruder_predicate False
    assert not intruder_predicate(PolicyTrace(trace_id="sub1", events=(minimized.events[0],)))
    assert not intruder_predicate(PolicyTrace(trace_id="sub2", events=(minimized.events[1],)))


def test_positive_10_events_minimized_to_4_events_revoked_transitivity() -> None:
    """10 events with revoked transitivity minimized to 4 essential events.

    Essential: GRANT root -> DELEGATE root->delegatee -> REVOKE root -> ACCESS delegatee.
    Granting context is strictly required because if GRANT root is deleted,
    delegatee never gains authority and REVOKED_ACTOR_TRANSITIVITY cannot fire.
    """
    events = (
        make_event(EVENT_KIND_GRANT, "root_doc", 10),
        make_event(EVENT_KIND_GRANT, "other_user", 20),
        make_event(EVENT_KIND_DELEGATE, "root_doc", 30, policy_state="nurse_joy"),
        make_event(EVENT_KIND_ACCESS, "other_user", 40),
        make_event(EVENT_KIND_GRANT, "third_user", 50),
        make_event(EVENT_KIND_REVOKE, "root_doc", 60),
        make_event(EVENT_KIND_ACCESS, "third_user", 70),
        make_event(EVENT_KIND_ACCESS, "other_user", 80),
        make_event(EVENT_KIND_ACCESS, "nurse_joy", 90),
        make_event(EVENT_KIND_ACCESS, "other_user", 100),
    )
    trace = make_trace(events, trace_id="trace-transitivity-10")

    minimized = minimize_witness(
        trace,
        oracle=evaluate_trace,
        target_fault=FINDING_REVOKED_ACTOR_TRANSITIVITY,
    )

    assert minimized.original_event_count == 10
    assert minimized.minimized_event_count == 4
    assert len(minimized) == 4
    assert minimized.is_1_minimal is True
    assert minimized.fault == FINDING_REVOKED_ACTOR_TRANSITIVITY

    verdict = evaluate_trace(minimized.trace)
    assert any(f.kind == FINDING_REVOKED_ACTOR_TRANSITIVITY for f in verdict.findings)
    assert verdict.outcome == OUTCOME_DENY


def test_positive_convenience_contract_minimize() -> None:
    """Convenience function minimize(trace, predicate) -> PolicyTrace directly."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_DELEGATE, "alice", 20, policy_state="bob"),
        make_event(EVENT_KIND_DELEGATE, "bob", 30, policy_state="alice"),
        make_event(EVENT_KIND_GRANT, "carol", 40),
    )
    trace = make_trace(events, trace_id="trace-convenience")
    min_trace = minimize(trace)

    assert isinstance(min_trace, PolicyTrace)
    assert len(min_trace.events) == 3
    verdict = evaluate_trace(min_trace)
    assert any(f.kind == FINDING_DELEGATION_CYCLE for f in verdict.findings)


def test_positive_minimized_trace_json_serializable() -> None:
    """MinimizedTrace to_dict produces valid JSON."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_DELEGATE, "alice", 20, policy_state="bob"),
        make_event(EVENT_KIND_DELEGATE, "bob", 30, policy_state="alice"),
    )
    trace = make_trace(events, trace_id="trace-json-test")
    minimized = minimize_witness(trace)

    payload = minimized.to_dict()
    dumped = json.dumps(payload, indent=2)
    loaded = json.loads(dumped)

    assert loaded["version"] == TEMPORAL_WITNESS_MINIMIZER_VERSION
    assert loaded["dsl_version"] == POLICY_TRACE_DSL_VERSION
    assert loaded["fault"] == FINDING_DELEGATION_CYCLE
    assert loaded["minimized_event_count"] == 3
    assert loaded["is_1_minimal"] is True
    assert "trace" in loaded
    assert len(loaded["minimized_trace_sha256"]) == 64


def test_positive_already_minimal_trace_is_unchanged() -> None:
    """An already 1-minimal trace is preserved with identical events."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_DELEGATE, "alice", 20, policy_state="bob"),
        make_event(EVENT_KIND_DELEGATE, "bob", 30, policy_state="alice"),
    )
    trace = make_trace(events, trace_id="trace-already-minimal")
    minimized = minimize_witness(trace)

    assert minimized.original_event_count == 3
    assert minimized.minimized_event_count == 3
    assert minimized.trace.events == trace.events
    assert minimized.reduction_ratio == 0.0


def test_positive_determinism_and_idempotence() -> None:
    """Repeated minimizations on identical inputs produce identical outputs."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_GRANT, "carol", 20),
        make_event(EVENT_KIND_DELEGATE, "alice", 30, policy_state="bob"),
        make_event(EVENT_KIND_ACCESS, "carol", 40),
        make_event(EVENT_KIND_DELEGATE, "bob", 70, policy_state="alice"),
    )
    trace = make_trace(events, trace_id="trace-det")
    res1 = minimize_witness(trace)
    res2 = minimize_witness(trace)
    res3 = minimize_witness(res1.trace)

    assert res1.trace.to_dict() == res2.trace.to_dict()
    assert res1.trace.to_dict() == res3.trace.to_dict()
    assert res1.trace.trace_sha256 == res2.trace.trace_sha256


def test_positive_accepts_dict_mapping_payload() -> None:
    """minimize_witness directly accepts a raw dict payload adhering to DSL schema."""
    payload = {
        "version": POLICY_TRACE_DSL_VERSION,
        "trace_id": "trace-dict-input",
        "events": [
            make_event(EVENT_KIND_GRANT, "alice", 10).to_dict(),
            make_event(EVENT_KIND_GRANT, "carol", 20).to_dict(),
            make_event(EVENT_KIND_DELEGATE, "alice", 30, policy_state="bob").to_dict(),
            make_event(EVENT_KIND_DELEGATE, "bob", 40, policy_state="alice").to_dict(),
        ],
    }
    minimized = minimize_witness(payload)
    assert minimized.minimized_event_count == 3
    assert minimized.is_1_minimal is True


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_trace_without_fault_raises_error() -> None:
    """Trace without fault (PERMIT with zero findings) raises NO_FAULT_DETECTED."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_ACCESS, "alice", 20),
    )
    trace = make_trace(events, trace_id="trace-benign")
    initial_verdict = evaluate_trace(trace)
    assert initial_verdict.outcome == OUTCOME_PERMIT
    assert initial_verdict.findings == ()

    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(trace)
    assert exc_info.value.reason_code == REASON_NO_FAULT_DETECTED


def test_adversarial_predicate_returning_false_raises_error() -> None:
    """Predicate returning False raises NO_FAULT_DETECTED."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_ACCESS, "alice", 20),
    )
    trace = make_trace(events, trace_id="trace-pred-false")
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(trace, oracle=lambda t: False)
    assert exc_info.value.reason_code == REASON_NO_FAULT_DETECTED


def test_adversarial_target_fault_not_found_raises_error() -> None:
    """Requesting a target_fault not present in the trace raises TARGET_FAULT_NOT_FOUND."""
    events = (
        make_event(EVENT_KIND_REVOKE, "alice", 10),  # REVOKE_BEFORE_GRANT
    )
    trace = make_trace(events, trace_id="trace-wrong-fault")
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(trace, target_fault=FINDING_DELEGATION_CYCLE)
    assert exc_info.value.reason_code == REASON_TARGET_FAULT_NOT_FOUND


def test_adversarial_non_monotonic_timestamps_unordered_refused() -> None:
    """Trace with decreasing logical times is refused with NON_MONOTONIC_TIMESTAMPS."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 30),
        make_event(EVENT_KIND_ACCESS, "alice", 10),
    )
    trace = make_trace(events, trace_id="trace-bad-order")
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(trace)
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_TIMESTAMPS


def test_adversarial_non_monotonic_timestamps_duplicate_refused() -> None:
    """Trace with duplicate logical times is refused with NON_MONOTONIC_TIMESTAMPS."""
    events = (
        make_event(EVENT_KIND_GRANT, "alice", 10),
        make_event(EVENT_KIND_ACCESS, "alice", 10),
    )
    trace = make_trace(events, trace_id="trace-dup-time")
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(trace)
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_TIMESTAMPS


def test_adversarial_non_monotonic_dict_payload_refused() -> None:
    """Dict payload with unordered events is refused with NON_MONOTONIC_TIMESTAMPS."""
    payload = {
        "version": POLICY_TRACE_DSL_VERSION,
        "trace_id": "trace-dict-unordered",
        "events": [
            make_event(EVENT_KIND_GRANT, "alice", 50).to_dict(),
            make_event(EVENT_KIND_ACCESS, "alice", 20).to_dict(),
        ],
    }
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(payload)
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_TIMESTAMPS


def test_adversarial_empty_trace_refused() -> None:
    """Trace with zero events is refused with EMPTY_TRACE."""
    trace = make_trace((), trace_id="trace-empty")
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(trace)
    assert exc_info.value.reason_code == REASON_EMPTY_TRACE_CODE


def test_adversarial_malformed_trace_type_refused() -> None:
    """Passing invalid object type raises MALFORMED_TRACE."""
    with pytest.raises(MinimizerError) as exc_info:
        minimize_witness(12345)  # type: ignore[arg-type]
    assert exc_info.value.reason_code == REASON_MALFORMED_TRACE
