"""Frozen domain policies for versioned Clinical Commitments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from clara_api.glhs.domain import GlhsInvariantError

COMMITMENT_SCHEMA_VERSION = "commitloop.commitment.v1"


@dataclass(frozen=True)
class CommitmentDomainPolicy:
    domain: str
    actions: frozenset[str]
    required_target_fields: frozenset[str]
    authority_classes: frozenset[str]
    actor_roles: frozenset[str]
    allowed_transitions: Mapping[str, frozenset[str]]
    default_grace: timedelta
    conflict_rule: str
    abstention_rule: str
    partial_satisfaction: bool
    minimum_evidence: int


_COMMON_TRANSITIONS = {
    "NONE": frozenset({"OPEN"}),
    "OPEN": frozenset(
        {"OPEN", "PARTIALLY_SATISFIED", "SATISFIED", "SUPERSEDED", "CANCELLED"}
    ),
    "PARTIALLY_SATISFIED": frozenset(
        {"OPEN", "PARTIALLY_SATISFIED", "SATISFIED", "SUPERSEDED", "CANCELLED"}
    ),
    "SATISFIED": frozenset({"SATISFIED", "SUPERSEDED"}),
    "SUPERSEDED": frozenset({"SUPERSEDED"}),
    "CANCELLED": frozenset({"CANCELLED", "OPEN"}),
}

DOMAIN_POLICIES: Mapping[str, CommitmentDomainPolicy] = {
    "medications": CommitmentDomainPolicy(
        domain="medications",
        actions=frozenset(
            {"take_medication", "refill_medication", "medication_review"}
        ),
        required_target_fields=frozenset({"system", "code"}),
        authority_classes=frozenset(
            {"patient_report", "clinician_order", "pharmacist_verified"}
        ),
        actor_roles=frozenset({"owner", "clinician", "caregiver"}),
        allowed_transitions=_COMMON_TRANSITIONS,
        default_grace=timedelta(days=1),
        conflict_rule="comparable_authority_conflict_requires_medication_review",
        abstention_rule="abstain_on_dose_or_active_order_conflict",
        partial_satisfaction=True,
        minimum_evidence=1,
    ),
    "allergies": CommitmentDomainPolicy(
        domain="allergies",
        actions=frozenset({"avoid_substance", "verify_allergy", "update_allergy_status"}),
        required_target_fields=frozenset({"system", "code"}),
        authority_classes=frozenset({"patient_report", "clinician_confirmed"}),
        actor_roles=frozenset({"owner", "clinician", "caregiver"}),
        allowed_transitions=_COMMON_TRANSITIONS,
        default_grace=timedelta(0),
        conflict_rule="confirmed_allergy_conflict_requires_clinician_resolution",
        abstention_rule="abstain_on_active_allergy_conflict",
        partial_satisfaction=False,
        minimum_evidence=1,
    ),
    "conditions": CommitmentDomainPolicy(
        domain="conditions",
        actions=frozenset({"follow_up_condition", "monitor_condition", "review_condition"}),
        required_target_fields=frozenset({"system", "code"}),
        authority_classes=frozenset({"patient_report", "clinician_diagnosis"}),
        actor_roles=frozenset({"owner", "clinician", "caregiver"}),
        allowed_transitions=_COMMON_TRANSITIONS,
        default_grace=timedelta(days=7),
        conflict_rule="diagnostic_conflict_requires_clinician_resolution",
        abstention_rule="abstain_on_unresolved_diagnostic_conflict",
        partial_satisfaction=True,
        minimum_evidence=1,
    ),
    "observations": CommitmentDomainPolicy(
        domain="observations",
        actions=frozenset(
            {"repeat_measurement", "complete_service_request", "monitor_observation"}
        ),
        required_target_fields=frozenset({"system", "code"}),
        authority_classes=frozenset(
            {"patient_report", "device_measurement", "lab_verified", "clinician_order"}
        ),
        actor_roles=frozenset({"owner", "clinician", "caregiver"}),
        allowed_transitions=_COMMON_TRANSITIONS,
        default_grace=timedelta(days=7),
        conflict_rule="comparable_measurements_remain_conflicted",
        abstention_rule="abstain_when_measurement_evidence_is_insufficient_or_conflicted",
        partial_satisfaction=True,
        minimum_evidence=1,
    ),
}


def policy_for(domain: str) -> CommitmentDomainPolicy:
    try:
        return DOMAIN_POLICIES[domain]
    except KeyError as exc:
        raise GlhsInvariantError("commitment_domain_forbidden") from exc


# Frozen action -> FHIR resource_type mapping used to derive lifecycle
# predicates from the domain policy (P4).  Code-owned; an unmapped action
# simply cannot derive a predicate and keeps today's required-predicate error.
_ACTION_RESOURCE_TYPES: Mapping[str, Mapping[str, str]] = {
    "medications": {
        "take_medication": "MedicationStatement",
        "refill_medication": "MedicationRequest",
        "medication_review": "MedicationStatement",
    },
    "allergies": {
        "avoid_substance": "AllergyIntolerance",
        "verify_allergy": "AllergyIntolerance",
        "update_allergy_status": "AllergyIntolerance",
    },
    "conditions": {
        "follow_up_condition": "Condition",
        "monitor_condition": "Observation",
        "review_condition": "Condition",
    },
    "observations": {
        "repeat_measurement": "Observation",
        "complete_service_request": "ServiceRequest",
        "monitor_observation": "Observation",
    },
}


def derive_lifecycle_predicates(
    policy: CommitmentDomainPolicy,
    *,
    action: str,
    target: dict[str, object],
    due_time: datetime | None,
) -> dict[str, dict[str, object]]:
    """Derive lifecycle predicates from the frozen domain policy (P4).

    Returns a mapping of predicate name to a bounded ``event`` predicate whose
    ``equals`` fields are taken from the action/domain mapping and the target
    (``system``/``code``) where sensible, stamped with the provenance marker
    ``{"derived_from_policy": <domain>}``.  The marker is preserved by the
    predicate DSL validator and never participates in evaluation.

    ``due_time`` is reserved for policy-bounded time windows; current policies
    derive none.  When no derivation is possible for a lifecycle, callers keep
    today's ``commitment_<predicate>_predicate_required`` invariant.
    """

    resource_type = _ACTION_RESOURCE_TYPES.get(policy.domain, {}).get(action)
    if resource_type is None:
        return {}
    equals: dict[str, object] = {"resource_type": resource_type}
    for field in ("system", "code"):
        value = target.get(field) if isinstance(target, Mapping) else None
        if isinstance(value, str) and value:
            equals[field] = value
    marker: dict[str, object] = {"derived_from_policy": policy.domain}
    return {
        "fulfillment": {"op": "event", "equals": dict(equals), **marker},
        "partial": {
            "op": "event",
            "equals": {**equals, "status": "preliminary"},
            **marker,
        },
        "cancellation": {
            "op": "event",
            "equals": {**equals, "status": "cancelled"},
            **marker,
        },
        "supersession": {
            "op": "event",
            "equals": {**equals, "status": "superseded"},
            **marker,
        },
    }


def validate_domain_version(
    *,
    policy: CommitmentDomainPolicy,
    action: str,
    target: dict[str, object],
    authority_class: str,
    actor_role: str,
    prior_lifecycle: str | None,
    lifecycle_state: str,
    due_time: datetime | None,
    grace_end: datetime | None,
    has_fulfillment_predicate: bool,
    has_cancellation_predicate: bool,
    has_supersession_predicate: bool,
    has_partial_predicate: bool,
) -> None:
    if action not in policy.actions:
        raise GlhsInvariantError("commitment_domain_action_invalid")
    if not policy.required_target_fields.issubset(target) or any(
        not isinstance(target[field], str) or not target[field]
        for field in policy.required_target_fields
    ):
        raise GlhsInvariantError("commitment_target_invalid")
    if authority_class not in policy.authority_classes:
        raise GlhsInvariantError("commitment_authority_invalid")
    if actor_role not in policy.actor_roles:
        raise GlhsInvariantError("commitment_review_authority_required")
    prior = prior_lifecycle or "NONE"
    if lifecycle_state not in policy.allowed_transitions.get(prior, frozenset()):
        raise GlhsInvariantError("commitment_transition_invalid")
    if lifecycle_state in {"OPEN", "PARTIALLY_SATISFIED"} and not has_fulfillment_predicate:
        raise GlhsInvariantError("commitment_fulfillment_predicate_required")
    if lifecycle_state == "PARTIALLY_SATISFIED" and (
        not policy.partial_satisfaction or not has_partial_predicate
    ):
        raise GlhsInvariantError("commitment_partial_predicate_required")
    if lifecycle_state == "CANCELLED" and not has_cancellation_predicate:
        raise GlhsInvariantError("commitment_cancellation_predicate_required")
    if lifecycle_state == "SUPERSEDED" and not has_supersession_predicate:
        raise GlhsInvariantError("commitment_supersession_predicate_required")
    if grace_end is not None and due_time is None:
        raise GlhsInvariantError("commitment_grace_requires_due_time")
