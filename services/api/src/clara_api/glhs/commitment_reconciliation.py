"""Deterministic bitemporal Commitment Reconciliation Engine (P1/P2).

This engine derives a full commitment product state from a frozen, version-like
object (duck-typed via ``getattr``; any ORM row, ``SimpleNamespace``, or
attribute-bearing value works) plus a list of evidence event dicts, at explicit
``valid_at``/``known_at`` bitemporal cutoffs.

Purity and determinism (P12)
---------------------------
The engine is a pure function of its input: it never reads or writes a database
session and never mutates the version-like value or the events it inspects.
Identical inputs yield an identical ``algorithm_digest`` (concurrent writers
cannot disagree).  Canonical health state is written only by
``clara_api.glhs.commitment_gateway.apply_commitment_transition``.

Bitemporal visibility (P1)
--------------------------
An event is *visible* when its ``valid_at`` is not after the valid-time cutoff
and its ``known_at`` is not after the knowledge-time cutoff; late-arriving,
backdated evidence (``known_at`` after the cutoff) is excluded until knowledge
time catches up.  Cross-subject evidence (an event ``profile_id`` that differs
from the version ``profile_id``) is always excluded.  Evidence before the
version ``earliest_valid_time`` is ineligible for predicate matching.

Anchor vs effective time (P2)
-----------------------------
``anchor_valid_time``/``anchor_known_time`` are the creation anchor of the
version.  ``state_effective_at``/``state_known_at`` are reported separately:
``state_effective_at`` defaults to the anchor valid time when the version does
not carry an explicit effective time (``commitment_gateway`` stores the column
when present; older rows reconstruct to the anchor).

Timeliness clocks (P9)
----------------------
Timeliness is computed with the freshness-clock precedence from
``clara_api.glhs.freshness``: for a terminal decisive event, the source
observation clock (``observed_at``) governs, then the clinical validity anchor
(``valid_at``).  The knowledge clock is deliberately NOT used as the timeliness
point: it records ingestion, and using it would make timeliness depend on
ingestion latency.  For an OPEN version the cutoff itself is the point.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.predicate_dsl import match_predicate

RECONCILIATION_ALGORITHM = "commitment-reconciliation.v1"

_AUTHORITY_RANK = {
    "unverified": 0,
    "patient_report": 1,
    "device_measurement": 2,
    "clinician_order": 3,
    "lab_verified": 3,
    "pharmacist_verified": 4,
    "clinician_confirmed": 4,
    "clinician_diagnosis": 4,
}

# Predicate names and the version attribute carrying each predicate.
_PREDICATE_NAMES = (
    "conditional_trigger",
    "cancellation",
    "supersession",
    "fulfillment",
    "partial",
)
_PREDICATE_ATTRS = {
    "conditional_trigger": "conditional_trigger_json",
    "cancellation": "cancellation_predicate_json",
    "supersession": "supersession_predicate_json",
    "fulfillment": "fulfillment_predicate_json",
    "partial": "partial_predicate_json",
}
# Predicates each lifecycle requires for coverage.predicate_inputs.
_REQUIRED_PREDICATES = {
    "OPEN": ("fulfillment",),
    "PARTIALLY_SATISFIED": ("fulfillment", "partial"),
    "CANCELLED": ("cancellation",),
    "SUPERSEDED": ("supersession",),
    "SATISFIED": (),
}

_LIFECYCLE_REASONS = {
    "conditional_trigger_not_satisfied": "OPEN",
    "cancellation_predicate_satisfied": "CANCELLED",
    "supersession_predicate_satisfied": "SUPERSEDED",
    "fulfillment_predicate_satisfied": "SATISFIED",
    "partial_predicate_satisfied": "PARTIALLY_SATISFIED",
    "no_terminal_predicate_satisfied": "OPEN",
}


@dataclass(frozen=True)
class CommitmentProductState:
    """Full deterministic product state of one reconciled commitment version."""

    lifecycle_state: str
    evidence_state: str
    timeliness_state: str
    matched_evidence_ids: tuple[str, ...]
    excluded_evidence: tuple[dict[str, str], ...]
    reason_codes: tuple[str, ...]
    decisive_valid_time: datetime | None
    escalation_reasons: tuple[dict[str, str], ...]
    predicate_matches: Mapping[str, Mapping[str, Any]]
    coverage: Mapping[str, bool]
    algorithm_digest: str
    timeliness: str
    anchor_valid_time: datetime | None
    anchor_known_time: datetime | None
    state_effective_at: datetime | None
    state_known_at: datetime | None


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _field(version: object, name: str, default: object = None) -> object:
    return getattr(version, name, default)


def _freshness_point(event: dict[str, Any]) -> datetime | None:
    """Resolve the timeliness clock of a decisive event.

    Mirrors ``clara_api.glhs.freshness`` precedence for the source observation
    clock and the clinical validity anchor; the knowledge clock is excluded
    because it records ingestion latency, not clinical timing.
    """

    observed = _time(event.get("observed_at"))
    if observed is not None:
        return observed
    return _time(event.get("valid_at"))


def _timeliness(
    *,
    due_time: datetime | None,
    grace_end: datetime | None,
    point: datetime | None,
) -> str:
    if due_time is None:
        return "NOT_APPLICABLE"
    due = _utc(due_time)
    assert due is not None
    grace = _utc(grace_end)
    if point is None:
        return "UNKNOWN"
    if point < due:
        return "BEFORE_DUE"
    if grace is not None and point <= grace:
        return "IN_GRACE"
    return "OVERDUE"


def _comparable_contradictions(
    events: list[dict[str, Any]], *, authority_class: str
) -> list[dict[str, Any]]:
    threshold = _AUTHORITY_RANK.get(authority_class, 0)
    return [
        item
        for item in events
        if item.get("relation") == "contradicts"
        and (
            not isinstance(item.get("authority"), str)
            or _AUTHORITY_RANK.get(item["authority"], 0) >= threshold
        )
    ]


def _predicate_matches(
    version: object, eligible: list[dict[str, Any]]
) -> dict[str, Mapping[str, Any]]:
    matches: dict[str, Mapping[str, Any]] = {}
    for name in _PREDICATE_NAMES:
        predicate = _field(version, _PREDICATE_ATTRS[name])
        if predicate is None:
            matches[name] = MappingProxyType(
                {
                    "matched": True if name == "conditional_trigger" else False,
                    "matched_event_ids": (),
                    "decisive_event": None,
                    "predicate_digest": None,
                }
            )
            continue
        result = match_predicate(predicate, eligible)
        matches[name] = MappingProxyType(
            {
                "matched": bool(result["matched"]),
                "matched_event_ids": tuple(result["matched_event_ids"]),
                "decisive_event": result["decisive_event"],
                "predicate_digest": result["predicate_digest"],
            }
        )
    return matches


def _coverage(
    version: object,
    *,
    lifecycle_state: str,
    eligible_count: int,
    anchor: tuple[datetime | None, datetime | None],
) -> Mapping[str, bool]:
    anchor_valid, anchor_known = anchor
    target = _field(version, "target_json")
    dependencies = _field(version, "dependencies_json")
    authority = _field(version, "authority_class")
    minimum = _field(version, "minimum_evidence", 1)
    predicate_inputs = all(
        _field(version, _PREDICATE_ATTRS[name]) is not None
        for name in _REQUIRED_PREDICATES.get(lifecycle_state, ())
    )
    return MappingProxyType(
        {
            "anchor": anchor_valid is not None and anchor_known is not None,
            "target": isinstance(target, dict) and bool(target),
            "predicate_inputs": predicate_inputs,
            "dependencies": dependencies is not None,
            "authority": isinstance(authority, str) and authority in _AUTHORITY_RANK,
            "minimum_evidence": eligible_count >= int(minimum if isinstance(minimum, int) else 1),
        }
    )


def reconcile_commitment(
    version: object,
    events: list[dict[str, Any]],
    *,
    valid_at: datetime,
    known_at: datetime,
) -> CommitmentProductState:
    """Reconcile one frozen version against its evidence at bitemporal cutoffs.

    ``version`` is duck-typed: version fields are read with ``getattr``, so any
    ORM row or attribute-bearing object works.  ``events`` are dicts carrying
    ``evidence_id``/``valid_at``/``known_at`` (and optionally ``observed_at``,
    ``authority``, ``relation``, ``profile_id``, and predicate fields).
    """

    valid_cutoff = _utc(valid_at)
    known_cutoff = _utc(known_at)
    if valid_cutoff is None or known_cutoff is None:
        raise ValueError("commitment_reconciliation_timezone_required")

    version_profile = _field(version, "profile_id", None)
    visible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for event in events:
        event_valid = _time(event.get("valid_at"))
        event_known = _time(event.get("known_at"))
        identifier = str(event.get("evidence_id", "unknown"))
        if event_valid is None or event_known is None:
            excluded.append({"evidence_id": identifier, "reason": "missing_bitemporal_time"})
        elif event_valid > valid_cutoff:
            excluded.append({"evidence_id": identifier, "reason": "future_valid_time"})
        elif event_known > known_cutoff:
            excluded.append({"evidence_id": identifier, "reason": "not_yet_known"})
        elif version_profile is not None and event.get("profile_id") is not None and str(
            event["profile_id"]
        ) != str(version_profile):
            excluded.append({"evidence_id": identifier, "reason": "cross_subject_evidence"})
        else:
            visible.append(event)
    visible.sort(
        key=lambda item: (
            _time(item["valid_at"]) or datetime.min.replace(tzinfo=UTC),
            str(item.get("evidence_id", "")),
        )
    )

    earliest = _utc(_time(_field(version, "earliest_valid_time")))
    eligible: list[dict[str, Any]] = []
    for item in visible:
        event_time = _time(item.get("valid_at"))
        if earliest is not None and (event_time is None or event_time < earliest):
            excluded.append(
                {
                    "evidence_id": str(item.get("evidence_id", "unknown")),
                    "reason": "before_earliest_valid_time",
                }
            )
        else:
            eligible.append(item)

    contradictions = _comparable_contradictions(
        visible, authority_class=str(_field(version, "authority_class", ""))
    )
    if contradictions:
        evidence_state = "CONFLICTED"
    elif not visible:
        evidence_state = "INSUFFICIENT_EVIDENCE"
    else:
        evidence_state = "CLEAR"

    predicate_matches = _predicate_matches(version, eligible)
    triggered = bool(predicate_matches["conditional_trigger"]["matched"])

    lifecycle_reason: str
    decisive_event: dict[str, Any] | None
    if not triggered:
        lifecycle_reason = "conditional_trigger_not_satisfied"
        decisive_event = None
    elif predicate_matches["cancellation"]["matched"]:
        lifecycle_reason = "cancellation_predicate_satisfied"
        decisive_event = predicate_matches["cancellation"]["decisive_event"]
    elif predicate_matches["supersession"]["matched"]:
        lifecycle_reason = "supersession_predicate_satisfied"
        decisive_event = predicate_matches["supersession"]["decisive_event"]
    elif predicate_matches["fulfillment"]["matched"]:
        lifecycle_reason = "fulfillment_predicate_satisfied"
        decisive_event = predicate_matches["fulfillment"]["decisive_event"]
    elif predicate_matches["partial"]["matched"]:
        lifecycle_reason = "partial_predicate_satisfied"
        decisive_event = predicate_matches["partial"]["decisive_event"]
    else:
        lifecycle_reason = "no_terminal_predicate_satisfied"
        decisive_event = None

    lifecycle_state = _LIFECYCLE_REASONS[lifecycle_reason]
    decisive_valid_time = (
        _time(decisive_event.get("valid_at")) if decisive_event is not None else None
    )
    full_decisive_event = None
    if decisive_event is not None:
        decisive_id = str(decisive_event.get("evidence_id", ""))
        full_decisive_event = next(
            (item for item in eligible if str(item.get("evidence_id", "")) == decisive_id),
            None,
        )
    decisive_freshness = (
        _freshness_point(full_decisive_event) if full_decisive_event is not None else None
    )
    due_time = _time(_field(version, "due_time"))
    grace_end = _time(_field(version, "grace_end"))
    if lifecycle_state == "OPEN" and decisive_valid_time is None:
        point = valid_cutoff
    else:
        point = decisive_freshness if decisive_freshness is not None else valid_cutoff
    timeliness = _timeliness(due_time=due_time, grace_end=grace_end, point=point)

    matched_ids = tuple(
        str(item["evidence_id"])
        for item in visible
        if isinstance(item.get("evidence_id"), str)
    )
    reasons = [lifecycle_reason]
    if contradictions:
        reasons.append("comparable_evidence_conflict")
    if not visible:
        reasons.append("no_visible_evidence")

    commitment_id = _field(version, "commitment_id", None)
    escalation: list[dict[str, str]] = []
    if timeliness == "OVERDUE":
        escalation.append(
            {"code": "commitment_overdue", "commitment_id": str(commitment_id)}
            if commitment_id is not None
            else {"code": "commitment_overdue"}
        )
    if evidence_state == "CONFLICTED":
        escalation.append(
            {"code": "commitment_conflict", "commitment_id": str(commitment_id)}
            if commitment_id is not None
            else {"code": "commitment_conflict"}
        )
    if evidence_state == "INSUFFICIENT_EVIDENCE":
        escalation.append(
            {
                "code": "commitment_insufficient_evidence",
                "commitment_id": str(commitment_id),
            }
            if commitment_id is not None
            else {"code": "commitment_insufficient_evidence"}
        )
    escalation.sort(key=lambda item: (item["code"], item.get("commitment_id", "")))

    anchor_valid_time = _utc(_time(_field(version, "anchor_valid_time")))
    anchor_known_time = _utc(_time(_field(version, "anchor_known_time")))
    state_effective_at = _utc(_time(_field(version, "state_effective_at"))) or anchor_valid_time
    state_known_at = _utc(_time(_field(version, "state_known_at"))) or anchor_known_time

    coverage = _coverage(
        version,
        lifecycle_state=str(_field(version, "lifecycle_state", lifecycle_state)),
        eligible_count=len(eligible),
        anchor=(anchor_valid_time, anchor_known_time),
    )

    digest_payload = {
        "algorithm": RECONCILIATION_ALGORITHM,
        "lifecycle_state": lifecycle_state,
        "evidence_state": evidence_state,
        "timeliness": timeliness,
        "reason_codes": reasons,
        "matched_evidence_ids": list(matched_ids),
        "excluded_evidence": [
            {key: item[key] for key in sorted(item)} for item in excluded
        ],
        "decisive_valid_time": decisive_valid_time.isoformat() if decisive_valid_time else None,
        "escalation_reasons": [
            {key: item[key] for key in sorted(item)} for item in escalation
        ],
        "predicate_matches": {
            name: {
                "matched": bool(item["matched"]),
                "matched_event_ids": list(item["matched_event_ids"]),
                "decisive_event": item["decisive_event"],
                "predicate_digest": item["predicate_digest"],
            }
            for name, item in predicate_matches.items()
        },
        "coverage": dict(coverage),
        "anchor_valid_time": anchor_valid_time.isoformat() if anchor_valid_time else None,
        "anchor_known_time": anchor_known_time.isoformat() if anchor_known_time else None,
        "state_effective_at": state_effective_at.isoformat() if state_effective_at else None,
        "state_known_at": state_known_at.isoformat() if state_known_at else None,
        "valid_at_cutoff": valid_cutoff.isoformat(),
        "known_at_cutoff": known_cutoff.isoformat(),
    }
    algorithm_digest = consistency_fingerprint(digest_payload)

    return CommitmentProductState(
        lifecycle_state=lifecycle_state,
        evidence_state=evidence_state,
        timeliness_state=timeliness,
        matched_evidence_ids=matched_ids,
        excluded_evidence=tuple(excluded),
        reason_codes=tuple(reasons),
        decisive_valid_time=decisive_valid_time,
        escalation_reasons=tuple(escalation),
        predicate_matches=MappingProxyType(predicate_matches),
        coverage=coverage,
        algorithm_digest=algorithm_digest,
        timeliness=timeliness,
        anchor_valid_time=anchor_valid_time,
        anchor_known_time=anchor_known_time,
        state_effective_at=state_effective_at,
        state_known_at=state_known_at,
    )
