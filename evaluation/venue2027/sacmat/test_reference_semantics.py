"""Tests for SACMAT-X02_reference_semantics — reference decision procedure.

Positive controls exercise the four semantic axes independently coded:
conformant ALLOW (grant ordering + obligation satisfaction), expiry
divergence DENY (authority established after the decision time), revocation
dominance DENY, delegation transitivity ALLOW. Adversarial controls fail
closed with stable reason codes: revoke-before-grant DENY, delegation cycle
UNKNOWN (never a hung walk or a false permit), missing logical time
INDETERMINATE (never a safe-looking denial), revoked-actor transitive DENY.
The module imports only the reference semantics under test — no candidate
policy engine, no baseline arm, no DB, no model, no live provider, no clock.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.sacmat.reference_semantics import (
    DECISION_ALLOW,
    DECISION_DENY,
    DECISION_INDETERMINATE,
    DECISION_UNKNOWN,
    DETAIL_NO_AUTHORITY,
    DETAIL_OBLIGATION_FAULT,
    DETAIL_REVOKED_CHAIN,
    REASON_EMPTY_TRACE,
    REASON_MALFORMED_EVENT,
    REASON_MISSING_LOGICAL_TIME,
    REASON_UNKNOWN_PURPOSE,
    REFERENCE_SEMANTICS_VERSION,
    ReferenceEvent,
    ReferenceQuery,
    ReferenceTrace,
    ReferenceVerdict,
    reference_decide,
    reference_decide_json,
)

TENANT = "synthetic-tenant"
RESOURCE = "medication_record"
PURPOSE = "self_care"
STATE = "consent-epoch-7"


def event(
    kind: str,
    principal: str,
    t: int,
    *,
    policy_state: str = STATE,
    purpose: str = PURPOSE,
) -> ReferenceEvent:
    return ReferenceEvent(
        principal=principal,
        tenant=TENANT,
        resource=RESOURCE,
        purpose=purpose,
        policy_state=policy_state,
        logical_time=t,
        kind=kind,
    )


def trace_of(*events: ReferenceEvent, trace_id: str = "trace-ref") -> ReferenceTrace:
    return ReferenceTrace(trace_id=trace_id, events=events)


def query(
    principal: str = "dr.yen",
    t: int = 10,
    *,
    purpose: str = PURPOSE,
    obligations: dict[str, bool] | None = None,
) -> ReferenceQuery:
    return ReferenceQuery(
        principal=principal,
        tenant=TENANT,
        resource=RESOURCE,
        purpose=purpose,
        decision_time=t,
        policy_state=STATE,
        obligations=obligations or {},
    )


# ---------------------------------------------------------------------------
# Positive controls — each operator independently coded
# ---------------------------------------------------------------------------


def test_positive_conformant_grant_then_access_allows() -> None:
    verdict = reference_decide(
        trace_of(event("GRANT", "dr.yen", 1), event("ACCESS", "dr.yen", 2)), query(t=10)
    )
    assert verdict.decision == DECISION_ALLOW
    assert verdict.reason_code == "OK"
    assert verdict.reference_version == REFERENCE_SEMANTICS_VERSION


def test_positive_delegation_transitivity_allows_delegate() -> None:
    verdict = reference_decide(
        trace_of(
            event("GRANT", "dr.yen", 1),
            event("DELEGATE", "nurse.pham", 2, policy_state="dr.yen"),
            event("ACCESS", "nurse.pham", 3),
        ),
        query(principal="nurse.pham", t=10),
    )
    assert verdict.decision == DECISION_ALLOW


def test_positive_expiry_divergence_denies_lapsed_grant() -> None:
    # Authority established only AFTER the decision time: at t=5 the grant
    # has not yet come into force — temporal expiry divergence is DENY.
    verdict = reference_decide(trace_of(event("GRANT", "dr.yen", 20)), query(t=5))
    assert verdict.decision == DECISION_DENY
    assert verdict.detail == DETAIL_NO_AUTHORITY


def test_positive_revocation_dominance_denies_after_revoke() -> None:
    verdict = reference_decide(
        trace_of(
            event("GRANT", "dr.yen", 1),
            event("REVOKE", "dr.yen", 5),
            event("ACCESS", "dr.yen", 6),
        ),
        query(t=10),
    )
    assert verdict.decision == DECISION_DENY
    assert verdict.detail == DETAIL_NO_AUTHORITY


def test_positive_regrant_after_revocation_restores_direct_authority() -> None:
    verdict = reference_decide(
        trace_of(
            event("GRANT", "dr.yen", 1),
            event("REVOKE", "dr.yen", 2),
            event("GRANT", "dr.yen", 3),
            event("ACCESS", "dr.yen", 4),
        ),
        query(t=10),
    )
    assert verdict.decision == DECISION_ALLOW


def test_positive_obligations_satisfied_allow() -> None:
    verdict = reference_decide(
        trace_of(event("GRANT", "dr.yen", 1)),
        query(t=10, obligations={"audit_log": True, "minimize_phi": True}),
    )
    assert verdict.decision == DECISION_ALLOW


def test_positive_json_round_trip_is_stable() -> None:
    trace = trace_of(event("GRANT", "dr.yen", 1), event("ACCESS", "dr.yen", 2))
    payload = reference_decide_json(trace.to_dict(), query(t=10).to_dict())
    assert payload["decision"] == DECISION_ALLOW
    assert payload == reference_decide_json(trace.to_dict(), query(t=10).to_dict())
    assert json.loads(json.dumps(payload))["trace_sha256"] == trace.trace_sha256


# ---------------------------------------------------------------------------
# Adversarial controls — fail closed with stable reason codes
# ---------------------------------------------------------------------------


def test_adversarial_revoke_before_grant_denies() -> None:
    verdict = reference_decide(trace_of(event("REVOKE", "dr.yen", 1)), query(t=10))
    assert verdict.decision == DECISION_DENY
    assert verdict.detail == DETAIL_NO_AUTHORITY


def test_adversarial_delegation_cycle_denies_never_permits() -> None:
    # A delegates to B, B delegates back to A: the cycle must not mint
    # authority for anyone; the walk is bounded and resolves deny/unknown.
    verdict = reference_decide(
        trace_of(
            event("GRANT", "dr.a", 1),
            event("DELEGATE", "dr.b", 2, policy_state="dr.a"),
            event("DELEGATE", "dr.a", 3, policy_state="dr.b"),
        ),
        query(principal="dr.b", t=10),
    )
    assert verdict.decision in (DECISION_DENY, DECISION_UNKNOWN)


def test_adversarial_missing_logical_time_is_indeterminate() -> None:
    raw = event("GRANT", "dr.yen", 1).to_dict()
    raw["logical_time"] = None
    verdict = reference_decide({"trace_id": "t", "events": [raw]}, query(t=10))
    assert verdict.decision == DECISION_INDETERMINATE
    assert verdict.reason_code == REASON_MISSING_LOGICAL_TIME


def test_adversarial_missing_decision_time_is_indeterminate() -> None:
    payload = query(t=10).to_dict()
    payload["decision_time"] = None
    verdict = reference_decide(trace_of(event("GRANT", "dr.yen", 1)), payload)
    assert verdict.decision == DECISION_INDETERMINATE
    assert verdict.reason_code == REASON_MISSING_LOGICAL_TIME


def test_adversarial_revoked_actor_transitive_denies() -> None:
    # dr.yen delegates to nurse.pham, then dr.yen is revoked: nurse.pham's
    # inherited authority chain still reaches the revoked actor -> DENY.
    verdict = reference_decide(
        trace_of(
            event("GRANT", "dr.yen", 1),
            event("DELEGATE", "nurse.pham", 2, policy_state="dr.yen"),
            event("REVOKE", "dr.yen", 3),
            event("ACCESS", "nurse.pham", 4),
        ),
        query(principal="nurse.pham", t=10),
    )
    assert verdict.decision == DECISION_DENY
    assert verdict.detail == DETAIL_REVOKED_CHAIN


def test_adversarial_redelegation_chain_to_revoked_root_denies() -> None:
    verdict = reference_decide(
        trace_of(
            event("GRANT", "dr.yen", 1),
            event("DELEGATE", "nurse.pham", 2, policy_state="dr.yen"),
            event("DELEGATE", "aide.truc", 3, policy_state="nurse.pham"),
            event("REVOKE", "dr.yen", 4),
            event("ACCESS", "aide.truc", 5),
        ),
        query(principal="aide.truc", t=10),
    )
    assert verdict.decision == DECISION_DENY


def test_adversarial_unknown_purpose_denies() -> None:
    verdict = reference_decide(trace_of(event("GRANT", "dr.yen", 1)), query(t=10, purpose=""))
    assert verdict.decision == DECISION_DENY
    assert verdict.reason_code == REASON_UNKNOWN_PURPOSE


def test_adversarial_purpose_mismatch_denies() -> None:
    verdict = reference_decide(
        trace_of(event("GRANT", "dr.yen", 1, purpose="self_care")),
        query(t=10, purpose="research"),
    )
    assert verdict.decision == DECISION_DENY
    assert verdict.detail == DETAIL_NO_AUTHORITY


def test_adversarial_obligation_fault_denies() -> None:
    verdict = reference_decide(
        trace_of(event("GRANT", "dr.yen", 1)),
        query(t=10, obligations={"audit_log": False}),
    )
    assert verdict.decision == DECISION_DENY
    assert verdict.detail == DETAIL_OBLIGATION_FAULT


def test_adversarial_empty_trace_denies() -> None:
    verdict = reference_decide(ReferenceTrace(trace_id="t", events=()), query(t=10))
    assert verdict.decision == DECISION_DENY
    assert verdict.reason_code == REASON_EMPTY_TRACE


def test_adversarial_unsupported_event_kind_is_unknown() -> None:
    verdict = reference_decide(
        trace_of(event("GRANT", "dr.yen", 1), event("IMPOUNDS", "dr.yen", 2)), query(t=10)
    )
    assert verdict.decision == DECISION_UNKNOWN
    assert verdict.reason_code == "UNSUPPORTED_CONSTRUCT"


def test_adversarial_unresolvable_delegation_is_unknown() -> None:
    verdict = reference_decide(
        trace_of(event("DELEGATE", "nurse.pham", 1, policy_state="dr.nobody")),
        query(principal="nurse.pham", t=10),
    )
    assert verdict.decision == DECISION_UNKNOWN
    assert verdict.reason_code == "UNRESOLVABLE_DELEGATION"


def test_adversarial_malformed_event_is_indeterminate() -> None:
    verdict = reference_decide(
        ReferenceTrace(trace_id="t", events=(event("GRANT", "", 1),)), query(t=10)
    )
    assert verdict.decision == DECISION_INDETERMINATE
    assert verdict.reason_code == REASON_MALFORMED_EVENT


def test_adversarial_query_missing_principal_is_indeterminate() -> None:
    verdict = reference_decide(trace_of(event("GRANT", "dr.yen", 1)), query(principal="", t=10))
    assert verdict.decision == DECISION_INDETERMINATE


def test_verdict_is_json_serializable() -> None:
    verdict = reference_decide(trace_of(event("GRANT", "dr.yen", 1)), query(t=10))
    assert isinstance(verdict, ReferenceVerdict)
    payload = json.loads(json.dumps(verdict.to_dict()))
    assert payload["decision"] == DECISION_ALLOW


def test_policy_trace_shaped_object_is_accepted() -> None:
    class _Shaped:
        events = (
            event("GRANT", "dr.yen", 1),
            event("ACCESS", "dr.yen", 2),
        )

    verdict = reference_decide(_Shaped(), query(t=10))
    assert verdict.decision == DECISION_ALLOW


@pytest.mark.parametrize(
    ("decision", "allowed"),
    [
        (DECISION_ALLOW, True),
        (DECISION_DENY, True),
        (DECISION_INDETERMINATE, True),
        (DECISION_UNKNOWN, True),
    ],
)
def test_verdict_values_are_portable(decision: str, allowed: bool) -> None:
    assert allowed and decision in {"ALLOW", "DENY", "INDETERMINATE", "UNKNOWN"}
