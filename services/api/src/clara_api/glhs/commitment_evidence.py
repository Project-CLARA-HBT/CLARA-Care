"""Minimal evidence selection for Clinical Commitment THSS (P8).

``select_minimal_evidence`` replaces the compiler's blind union of every
included commitment's evidence with the caller's disclosed evidence.  An
evidence id may enter the disclosed snapshot only when it earns an explicit
role:

* ``anchor`` - named by the target/anchor commitment, or disclosed as the
  declared anchor of a target commitment that is not yet visible (opening
  flow), or (legacy domain-scoped mode) evidence of the relevant set.
* ``target_supporting`` - named by a relevant commitment whose target
  system/code matches the declared task target.
* ``predicate_supporting`` - matched by any lifecycle predicate of a relevant
  commitment, evaluated deterministically with ``predicate_dsl``.
* ``conflict`` - named by a *blocking* conflicted commitment.
* ``dependency`` - named by a commitment inside the resolved dependency
  closure.

Caller-supplied disclosed evidence that earns no role is excluded and
recorded in ``excluded_caller_evidence`` with the reason
``no_supported_evidence_role``; it never auto-enters.

Predicate event views
---------------------
The compiler holds only evidence pointers (ids), so predicate matching builds
a deterministic event view per candidate id from the attributes that exist:

* commitment-derived: the naming commitment's target ``system``/``code``,
  ``authority_class``, ``semantic_key`` and anchor times;
* evidence-derived (disclosed pointers only): ``artifact_type`` ->
  ``resource_type``, ``artifact_public_id`` -> ``code``, ``evidence_kind`` ->
  ``status``, ``valid_from`` -> ``valid_at`` and ``recorded_at`` ->
  ``known_at``.

A lifecycle predicate matches an id when ``evaluate_predicate`` returns true
over that id's single event view (conservative: ``count`` predicates never
match a single id, which only ever *excludes* evidence - the safe direction).
Predicates that fail DSL validation are ignored.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.predicate_dsl import evaluate_predicate

ANCHOR_ROLE = "anchor"
TARGET_SUPPORTING_ROLE = "target_supporting"
PREDICATE_SUPPORTING_ROLE = "predicate_supporting"
CONFLICT_ROLE = "conflict"
DEPENDENCY_ROLE = "dependency"
EVIDENCE_ROLES = frozenset(
    {ANCHOR_ROLE, TARGET_SUPPORTING_ROLE, PREDICATE_SUPPORTING_ROLE, CONFLICT_ROLE, DEPENDENCY_ROLE}
)
EXCLUDED_EVIDENCE_REASON = "no_supported_evidence_role"

LIFECYCLE_PREDICATE_FIELDS = (
    "fulfillment_predicate",
    "cancellation_predicate",
    "supersession_predicate",
    "partial_predicate",
    "conditional_trigger",
)


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return normalized.isoformat()
    if isinstance(value, str) and value:
        return value
    return None


def _commitment_evidence_ids(commitment: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(evidence_id) for evidence_id in commitment.get("evidence_ids") or ())


def commitment_evidence_event_view(
    commitment: dict[str, Any], evidence_id: str
) -> dict[str, Any]:
    """Deterministic event view for a commitment-named evidence id."""

    target = commitment.get("target")
    if not isinstance(target, dict):
        target = {}
    return {
        "evidence_id": str(evidence_id),
        "semantic_key": str(commitment.get("semantic_key") or ""),
        "code": str(target.get("code") or ""),
        "system": str(target.get("system") or ""),
        "authority": str(commitment.get("authority_class") or ""),
        "valid_at": _iso(commitment.get("anchor_valid_time")) or "",
        "known_at": _iso(commitment.get("anchor_known_time")) or "",
    }


def evidence_event_view(evidence: Any) -> dict[str, Any]:
    """Deterministic event view for a disclosed evidence pointer."""

    return {
        "evidence_id": str(getattr(evidence, "public_id", "")),
        "resource_type": str(getattr(evidence, "artifact_type", "") or ""),
        "code": str(getattr(evidence, "artifact_public_id", "") or ""),
        "status": str(getattr(evidence, "evidence_kind", "") or ""),
        "valid_at": _iso(getattr(evidence, "valid_from", None)) or "",
        "known_at": _iso(getattr(evidence, "recorded_at", None)) or "",
    }


def _lifecycle_predicates(commitment: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    predicates: list[dict[str, Any]] = []
    for field in LIFECYCLE_PREDICATE_FIELDS:
        predicate = commitment.get(field)
        if isinstance(predicate, dict):
            predicates.append(predicate)
    return tuple(predicates)


def classify_evidence_role(
    evidence_id: str,
    *,
    anchor_ids: frozenset[str] = frozenset(),
    dependency_ids: frozenset[str] = frozenset(),
    target_ids: frozenset[str] = frozenset(),
    conflict_ids: frozenset[str] = frozenset(),
    predicate_ids: frozenset[str] = frozenset(),
) -> str | None:
    """Return the single deterministic role for one evidence id.

    Priority order is fixed: conflict, anchor, dependency, target-supporting,
    predicate-supporting.  ``None`` means the id earns no role and must not be
    disclosed (caller-disclosed ids are then excluded and recorded).
    """

    if evidence_id in conflict_ids:
        return CONFLICT_ROLE
    if evidence_id in anchor_ids:
        return ANCHOR_ROLE
    if evidence_id in dependency_ids:
        return DEPENDENCY_ROLE
    if evidence_id in target_ids:
        return TARGET_SUPPORTING_ROLE
    if evidence_id in predicate_ids:
        return PREDICATE_SUPPORTING_ROLE
    return None


def select_minimal_evidence(
    *,
    relevant: tuple[dict[str, Any], ...],
    target_semantic_key: str | None = None,
    target: dict[str, Any] | None = None,
    anchor_commitment: dict[str, Any] | None = None,
    dependency_ids: frozenset[str] = frozenset(),
    blocking: tuple[dict[str, Any], ...] = (),
    disclosed_evidence: tuple[Any, ...] = (),
) -> dict[str, Any]:
    """Select the minimal evidence ids that earn a supported disclosure role."""

    disclosed_by_id = {str(item.public_id): item for item in disclosed_evidence}
    disclosed_ids = frozenset(disclosed_by_id)

    anchor_ids: set[str] = set()
    if anchor_commitment is not None:
        anchor_ids.update(_commitment_evidence_ids(anchor_commitment))
    elif target_semantic_key is not None or target is not None:
        # Opening flow: the caller declares the anchor evidence of a target
        # commitment that is not yet visible.
        anchor_ids.update(disclosed_ids)
    else:
        # Legacy domain-scoped mode: the relevant set is the task scope and
        # its evidence (plus caller disclosure) is the disclosure boundary.
        for item in relevant:
            anchor_ids.update(_commitment_evidence_ids(item))
        anchor_ids.update(disclosed_ids)

    dependency_evidence_ids: set[str] = set()
    for item in relevant:
        if str(item.get("semantic_key")) in dependency_ids:
            dependency_evidence_ids.update(_commitment_evidence_ids(item))

    target_supporting_ids: set[str] = set()
    if target is not None:
        for item in relevant:
            if item is anchor_commitment:
                continue
            item_target = item.get("target")
            if (
                isinstance(item_target, dict)
                and item_target.get("system") == target.get("system")
                and item_target.get("code") == target.get("code")
            ):
                target_supporting_ids.update(_commitment_evidence_ids(item))

    conflict_ids: set[str] = set()
    for item in blocking:
        if item.get("evidence_state") == "CONFLICTED":
            conflict_ids.update(_commitment_evidence_ids(item))

    candidate_ids = sorted(
        {
            *(
                evidence_id
                for item in relevant
                for evidence_id in _commitment_evidence_ids(item)
            ),
            *disclosed_ids,
        }
    )
    events: dict[str, dict[str, Any]] = {}
    for evidence_id in candidate_ids:
        view: dict[str, Any] = {}
        for item in relevant:
            if evidence_id in set(_commitment_evidence_ids(item)):
                view.update(commitment_evidence_event_view(item, evidence_id))
                break
        if evidence_id in disclosed_ids:
            # Commitment-derived fields win; evidence-derived fields fill only
            # the slots the commitment view does not provide.
            for field, value in evidence_event_view(disclosed_by_id[evidence_id]).items():
                if field != "evidence_id" and not view.get(field):
                    view[field] = value
        events[evidence_id] = view

    predicate_ids: set[str] = set()
    for item in relevant:
        for predicate in _lifecycle_predicates(item):
            for evidence_id in {*_commitment_evidence_ids(item), *disclosed_ids}:
                if evidence_id in predicate_ids:
                    continue
                try:
                    if evaluate_predicate(predicate, [events[evidence_id]]):
                        predicate_ids.add(evidence_id)
                except GlhsInvariantError:
                    continue

    roles: dict[str, str] = {}
    evidence_ids: set[str] = set()
    for evidence_id in candidate_ids:
        role = classify_evidence_role(
            evidence_id,
            anchor_ids=frozenset(anchor_ids),
            dependency_ids=frozenset(dependency_evidence_ids),
            target_ids=frozenset(target_supporting_ids),
            conflict_ids=frozenset(conflict_ids),
            predicate_ids=frozenset(predicate_ids),
        )
        if role is None:
            continue
        roles[evidence_id] = role
        evidence_ids.add(evidence_id)

    excluded_caller_evidence = tuple(
        {
            "evidence_id": evidence_id,
            "reason": EXCLUDED_EVIDENCE_REASON,
        }
        for evidence_id in sorted(disclosed_ids - evidence_ids)
    )
    return {
        "evidence_ids": sorted(evidence_ids),
        "roles": dict(sorted(roles.items())),
        "predicate_matched_ids": sorted(predicate_ids),
        "excluded_caller_evidence": excluded_caller_evidence,
    }
