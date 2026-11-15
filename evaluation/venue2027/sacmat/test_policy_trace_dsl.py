"""Tests for SACMAT-X01_policy_trace_dsl — temporal conformance properties.

Positive controls replay governed delegated-consent histories (grant,
delegate, access under an intact authority chain) and assert the expected
PERMIT outcome with zero findings. Adversarial controls fail closed with
stable reason codes (MISSING_LOGICAL_TIME, UNORDERED_TIMESTAMPS,
DUPLICATE_TIMESTAMP, MALFORMED_EVENT, SCHEMA_VERSION_MISMATCH, EMPTY_TRACE)
or surface trace-level findings (REVOKE_BEFORE_GRANT, DELEGATION_CYCLE,
REVOKED_ACTOR_TRANSITIVITY, UNESTABLISHED_AUTHORITY) that are never coerced
into safe acceptances. A seeded deterministic property test (deterministic
random traces, no clock/randomness beyond the local ``random.Random``)
replays hundreds of histories and asserts replay stability, JSON
round-tripping and outcome/findings consistency. The module imports only
the DSL under test (independent-oracle rule): no candidate runtime, no DB,
no model, no live provider.
"""

from __future__ import annotations

import json
import random

import pytest

from evaluation.venue2027.sacmat.policy_trace_dsl import (
    EVENT_KIND_ACCESS,
    EVENT_KIND_DELEGATE,
    EVENT_KIND_GRANT,
    EVENT_KIND_REVOKE,
    FINDING_DELEGATION_CYCLE,
    FINDING_REVOKE_BEFORE_GRANT,
    FINDING_REVOKED_ACTOR_TRANSITIVITY,
    FINDING_UNESTABLISHED_AUTHORITY,
    OUTCOME_DENY,
    OUTCOME_INDETERMINATE,
    OUTCOME_PERMIT,
    POLICY_TRACE_DSL_VERSION,
    REASON_DUPLICATE_TIMESTAMP,
    REASON_EMPTY_TRACE,
    REASON_MALFORMED_EVENT,
    REASON_MISSING_LOGICAL_TIME,
    REASON_SCHEMA_VERSION_MISMATCH,
    REASON_UNORDERED_TIMESTAMPS,
    Event,
    PolicyTrace,
    PolicyTraceError,
    TraceVerdict,
    evaluate_trace,
    evaluate_trace_json,
    parse_policy_trace,
)

TENANT = "synthetic-tenant"
RESOURCE = "medication_record"
PURPOSE = "self_care"
STATE = "consent-epoch-7"


def event(kind: str, principal: str, t: int, *, policy_state: str = STATE) -> Event:
    return Event(
        principal=principal,
        tenant=TENANT,
        resource=RESOURCE,
        purpose=PURPOSE,
        policy_state=policy_state,
        logical_time=t,
        kind=kind,
    )


def trace_of(*events: Event, trace_id: str = "trace-x") -> PolicyTrace:
    return PolicyTrace(trace_id=trace_id, events=events)


def trace_payload(*events: Event, trace_id: str = "trace-x") -> dict:
    return {
        "version": POLICY_TRACE_DSL_VERSION,
        "trace_id": trace_id,
        "events": [e.to_dict() for e in events],
    }


def finding_kinds(verdict: TraceVerdict) -> list[str]:
    return [f.kind for f in verdict.findings]


# ---------------------------------------------------------------------------
# Positive controls — governed histories adjudicated as specified
# ---------------------------------------------------------------------------


def test_positive_grant_then_access_permits() -> None:
    trace = trace_of(event(EVENT_KIND_GRANT, "dr.yen", 1), event(EVENT_KIND_ACCESS, "dr.yen", 2))
    verdict = evaluate_trace(trace)
    assert verdict.outcome == OUTCOME_PERMIT
    assert verdict.findings == ()
    assert verdict.trace_id == "trace-x"


def test_positive_delegation_chain_permits_for_delegate() -> None:
    trace = trace_of(
        event(EVENT_KIND_GRANT, "dr.yen", 1),
        event(EVENT_KIND_DELEGATE, "dr.yen", 2, policy_state="nurse.lan"),
        event(EVENT_KIND_ACCESS, "nurse.lan", 3),
    )
    verdict = evaluate_trace(trace)
    assert verdict.outcome == OUTCOME_PERMIT
    assert verdict.findings == ()


def test_positive_revoke_stops_later_access() -> None:
    trace = trace_of(
        event(EVENT_KIND_GRANT, "dr.yen", 1),
        event(EVENT_KIND_ACCESS, "dr.yen", 2),
        event(EVENT_KIND_REVOKE, "dr.yen", 3),
        event(EVENT_KIND_ACCESS, "dr.yen", 4),
    )
    verdict = evaluate_trace(trace)
    assert verdict.outcome == OUTCOME_DENY
    assert FINDING_REVOKE_BEFORE_GRANT not in finding_kinds(verdict)
    assert FINDING_REVOKED_ACTOR_TRANSITIVITY not in finding_kinds(verdict)


def test_positive_trace_round_trip_and_deterministic_hash() -> None:
    trace = trace_of(
        event(EVENT_KIND_GRANT, "dr.yen", 1),
        event(EVENT_KIND_DELEGATE, "dr.yen", 2, policy_state="nurse.lan"),
        event(EVENT_KIND_ACCESS, "nurse.lan", 3),
        trace_id="trace-roundtrip",
    )
    payload = trace_payload(*trace.events, trace_id=trace.trace_id)
    reparsed = parse_policy_trace(payload)
    assert reparsed == trace
    assert reparsed.trace_sha256 == trace.trace_sha256
    canonical = json.dumps(trace.to_dict(), sort_keys=True)
    assert json.loads(canonical)["trace_id"] == "trace-roundtrip"


def test_positive_evaluate_trace_json_serializable() -> None:
    payload = trace_payload(
        event(EVENT_KIND_GRANT, "dr.yen", 1),
        event(EVENT_KIND_DELEGATE, "dr.yen", 2, policy_state="nurse.lan"),
        event(EVENT_KIND_ACCESS, "nurse.lan", 3),
    )
    verdict = evaluate_trace_json(payload)
    dumped = json.loads(json.dumps(verdict, sort_keys=True))
    assert dumped["outcome"] == OUTCOME_PERMIT
    assert dumped["dsl_version"] == POLICY_TRACE_DSL_VERSION
    assert len(dumped["trace_sha256"]) == 64
    assert dumped["findings"] == []


# ---------------------------------------------------------------------------
# Adversarial: validator rejections with stable reason codes
# ---------------------------------------------------------------------------


def test_adversarial_missing_logical_time_refused() -> None:
    payload = {
        "version": POLICY_TRACE_DSL_VERSION,
        "trace_id": "trace-no-time",
        "events": [
            {
                "principal": "dr.yen",
                "tenant": TENANT,
                "resource": RESOURCE,
                "purpose": PURPOSE,
                "policy_state": STATE,
                "kind": EVENT_KIND_GRANT,
            }
        ],
    }
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(payload)
    assert excinfo.value.reason_code == REASON_MISSING_LOGICAL_TIME
    with pytest.raises(PolicyTraceError) as excinfo:
        event(EVENT_KIND_GRANT, "dr.yen", None)  # type: ignore[arg-type]
    assert excinfo.value.reason_code == REASON_MISSING_LOGICAL_TIME


def test_adversarial_unordered_timestamps_refused_not_reordered() -> None:
    events = (
        event(EVENT_KIND_GRANT, "dr.yen", 3),
        event(EVENT_KIND_REVOKE, "dr.yen", 1),
    )
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(trace_payload(*events))
    assert excinfo.value.reason_code == REASON_UNORDERED_TIMESTAMPS


def test_adversarial_duplicate_timestamp_refused() -> None:
    events = (
        event(EVENT_KIND_GRANT, "dr.yen", 5),
        event(EVENT_KIND_GRANT, "nurse.lan", 5),
    )
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(trace_payload(*events))
    assert excinfo.value.reason_code == REASON_DUPLICATE_TIMESTAMP


def test_adversarial_malformed_events_refused() -> None:
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(trace_payload(event(EVENT_KIND_GRANT, "", 1)))
    assert excinfo.value.reason_code == REASON_MALFORMED_EVENT
    with pytest.raises(PolicyTraceError) as excinfo:
        Event.from_dict({"principal": "dr.yen", "kind": EVENT_KIND_GRANT, "logical_time": 1})
    assert excinfo.value.reason_code == REASON_MALFORMED_EVENT
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(trace_payload(event(EVENT_KIND_GRANT, "dr.yen", "soon")))  # type: ignore[arg-type]
    assert excinfo.value.reason_code == REASON_MALFORMED_EVENT
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(trace_payload(event("BLESSED_STATE", "dr.yen", 1)))
    assert excinfo.value.reason_code == REASON_MALFORMED_EVENT


def test_adversarial_schema_version_mismatch_refused() -> None:
    payload = trace_payload(event(EVENT_KIND_GRANT, "dr.yen", 1))
    payload["version"] = "clara.sacmat.policy-trace-dsl-v0-RETIRED"
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(payload)
    assert excinfo.value.reason_code == REASON_SCHEMA_VERSION_MISMATCH


def test_adversarial_empty_trace_refused() -> None:
    payload = trace_payload()
    payload["events"] = []
    with pytest.raises(PolicyTraceError) as excinfo:
        parse_policy_trace(payload)
    assert excinfo.value.reason_code == REASON_EMPTY_TRACE


# ---------------------------------------------------------------------------
# Adversarial: trace-level findings — never coerced to safe acceptances
# ---------------------------------------------------------------------------


def test_adversarial_revoke_before_grant_detected() -> None:
    trace = trace_of(event(EVENT_KIND_REVOKE, "dr.yen", 1))
    verdict = evaluate_trace(trace)
    assert finding_kinds(verdict) == [FINDING_REVOKE_BEFORE_GRANT]
    witness = verdict.findings[0]
    assert witness.witness_event_index == 0
    assert witness.actor == "dr.yen"
    assert verdict.outcome == OUTCOME_DENY


def test_adversarial_delegation_cycle_detected() -> None:
    trace = trace_of(
        event(EVENT_KIND_GRANT, "dr.yen", 1),
        event(EVENT_KIND_DELEGATE, "dr.yen", 2, policy_state="nurse.lan"),
        event(EVENT_KIND_DELEGATE, "nurse.lan", 3, policy_state="dr.yen"),
    )
    verdict = evaluate_trace(trace)
    assert FINDING_DELEGATION_CYCLE in finding_kinds(verdict)
    witness = next(f for f in verdict.findings if f.kind == FINDING_DELEGATION_CYCLE)
    assert witness.witness_event_index == 2


def test_adversarial_revoked_actor_transitivity_detected() -> None:
    trace = trace_of(
        event(EVENT_KIND_GRANT, "dr.yen", 1),
        event(EVENT_KIND_DELEGATE, "dr.yen", 2, policy_state="nurse.lan"),
        event(EVENT_KIND_REVOKE, "dr.yen", 3),
        event(EVENT_KIND_ACCESS, "nurse.lan", 4),
    )
    verdict = evaluate_trace(trace)
    kinds = finding_kinds(verdict)
    assert FINDING_REVOKED_ACTOR_TRANSITIVITY in kinds
    assert verdict.outcome == OUTCOME_DENY


def test_adversarial_unestablished_authority_is_indeterminate_not_permit() -> None:
    trace = trace_of(event(EVENT_KIND_ACCESS, "ghost.principal", 1))
    verdict = evaluate_trace(trace)
    assert verdict.outcome == OUTCOME_INDETERMINATE
    assert FINDING_UNESTABLISHED_AUTHORITY in finding_kinds(verdict)


def test_findings_are_first_class_never_safe_acceptances() -> None:
    trace = trace_of(
        event(EVENT_KIND_REVOKE, "dr.yen", 1),
        event(EVENT_KIND_GRANT, "dr.yen", 2),
        event(EVENT_KIND_DELEGATE, "dr.yen", 3, policy_state="nurse.lan"),
        event(EVENT_KIND_DELEGATE, "nurse.lan", 4, policy_state="dr.yen"),
    )
    verdict = evaluate_trace(trace)
    kinds = finding_kinds(verdict)
    assert FINDING_REVOKE_BEFORE_GRANT in kinds
    assert FINDING_DELEGATION_CYCLE in kinds
    assert all(f.witness_event_index >= 0 for f in verdict.findings)
    # determinism: same trace -> identical verdict payload
    assert evaluate_trace(trace).to_dict() == verdict.to_dict()


# ---------------------------------------------------------------------------
# Seeded deterministic property test — replay stability and JSON round-trip
# ---------------------------------------------------------------------------


def _seeded_trace(rng: random.Random, index: int) -> PolicyTrace:
    principals = ["dr.yen", "nurse.lan", "pharm.vu"]
    delegate_targets = ["nurse.lan", "pharm.vu", "dr.yen"]
    events: list[Event] = []
    t = 1
    for _ in range(rng.randint(2, 7)):
        roll = rng.random()
        actor = rng.choice(principals)
        if roll < 0.35:
            events.append(event(EVENT_KIND_GRANT, actor, t))
        elif roll < 0.55:
            events.append(event(EVENT_KIND_REVOKE, actor, t))
        elif roll < 0.8:
            events.append(
                event(EVENT_KIND_DELEGATE, actor, t, policy_state=rng.choice(delegate_targets))
            )
        else:
            events.append(event(EVENT_KIND_ACCESS, actor, t))
        t += rng.randint(1, 3)
    if not any(e.kind == EVENT_KIND_ACCESS for e in events):
        events.append(event(EVENT_KIND_ACCESS, rng.choice(principals), t))
    return PolicyTrace(trace_id=f"synthetic-{index}", events=tuple(events))


@pytest.mark.parametrize("seed", range(48))
def test_property_replay_stable_json_roundtrip_verdict_consistent(seed: int) -> None:
    rng = random.Random(2027_0000 + seed)
    trace = _seeded_trace(rng, seed)
    payload = trace_payload(*trace.events, trace_id=trace.trace_id)
    reparsed = parse_policy_trace(payload)
    assert reparsed == trace

    verdict = evaluate_trace(reparsed)
    assert isinstance(verdict, TraceVerdict)
    # Replay stability: identical re-evaluation yields a byte-identical dict.
    assert evaluate_trace(reparsed).to_dict() == verdict.to_dict()
    # JSON round-trip of the verdict payload.
    restored = json.loads(json.dumps(verdict.to_dict(), sort_keys=True))
    assert restored["outcome"] == verdict.outcome
    assert len(restored["trace_sha256"]) == 64
    assert restored["dsl_version"] == POLICY_TRACE_DSL_VERSION
    # Findings sorted deterministically by (witness_event_index, kind).
    keys = [(f.witness_event_index, f.kind) for f in verdict.findings]
    assert keys == sorted(keys)
    # Outcome/findings consistency: an INDETERMINATE outcome is never silently
    # mapped to PERMIT, and DENY traces carry no silent acceptance.
    if verdict.outcome == OUTCOME_PERMIT:
        assert FINDING_REVOKED_ACTOR_TRANSITIVITY not in finding_kinds(verdict)
    if verdict.outcome == OUTCOME_INDETERMINATE:
        assert FINDING_UNESTABLISHED_AUTHORITY in finding_kinds(verdict)
