"""Bounded, deterministic JSON predicates for CommitLoop evidence matching.

This deliberately interprets a closed data structure.  It never evaluates
Python, SQL, JSONPath, regexes, or model-provided executable content.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.domain import GlhsInvariantError

DSL_VERSION = "commitloop-predicate.v1"
_MAX_DEPTH = 8
_MAX_CHILDREN = 32
_OPS = frozenset({"all", "any", "not", "event", "count"})
_EVENT_FIELDS = frozenset(
    {
        "resource_type",
        "code",
        "system",
        "status",
        "authority",
        "encounter_reference",
        "reference",
        "semantic_key",
    }
)
# Additive provenance metadata: ``derive_lifecycle_predicates`` stamps event
# predicates with {"derived_from_policy": domain}.  It never participates in
# evaluation; it is preserved so stored derived predicates remain re-validatable
# and auditable.  Behavior for every pre-existing predicate is unchanged.
_METADATA_FIELDS = frozenset({"derived_from_policy"})
_NUMERIC_FIELDS = frozenset({"numeric_value", "quantity_value"})
_COMPARATORS = frozenset({"lt", "lte", "eq", "gte", "gt"})
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


def _keys(predicate: dict[str, Any], allowed: frozenset[str]) -> None:
    if set(predicate) - allowed:
        raise GlhsInvariantError("invalid_predicate_fields")


def _scalar(value: object) -> bool:
    return isinstance(value, (str, int, float, bool)) and not (
        isinstance(value, float) and not math.isfinite(value)
    )


def _at(value: object) -> datetime:
    if not isinstance(value, str):
        raise GlhsInvariantError("invalid_predicate_time")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise GlhsInvariantError("invalid_predicate_time") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def validate_predicate(predicate: object, *, depth: int = 0) -> dict[str, Any]:
    if depth > _MAX_DEPTH or not isinstance(predicate, dict):
        raise GlhsInvariantError("invalid_predicate")
    op = predicate.get("op")
    if op not in _OPS:
        raise GlhsInvariantError("invalid_predicate_operator")
    if op in {"all", "any"}:
        _keys(predicate, frozenset({"op", "children"}))
        children = predicate.get("children")
        if not isinstance(children, list) or not children or len(children) > _MAX_CHILDREN:
            raise GlhsInvariantError("invalid_predicate_children")
        return {
            "op": op,
            "children": [validate_predicate(item, depth=depth + 1) for item in children],
        }
    if op == "not":
        _keys(predicate, frozenset({"op", "child"}))
        return {"op": op, "child": validate_predicate(predicate.get("child"), depth=depth + 1)}
    if op == "count":
        _keys(predicate, frozenset({"op", "where", "min", "max"}))
        child = validate_predicate(predicate.get("where"), depth=depth + 1)
        if child["op"] != "event":
            raise GlhsInvariantError("invalid_predicate_count_where")
        minimum = predicate.get("min")
        if not isinstance(minimum, int) or not 0 <= minimum <= 1000:
            raise GlhsInvariantError("invalid_predicate_count")
        maximum = predicate.get("max")
        if maximum is not None and (
            not isinstance(maximum, int) or not minimum <= maximum <= 1000
        ):
            raise GlhsInvariantError("invalid_predicate_count")
        count_result = {"op": op, "where": child, "min": minimum}
        if maximum is not None:
            count_result["max"] = maximum
        return count_result
    _keys(
        predicate,
        frozenset(
            {
                "op",
                "equals",
                "in",
                "compare",
                "authority_at_least",
                "not_before",
                "not_after",
                "known_before",
                *_METADATA_FIELDS,
            }
        ),
    )
    marker = predicate.get("derived_from_policy")
    if marker is not None and (not isinstance(marker, str) or not marker):
        raise GlhsInvariantError("invalid_predicate_fields")
    fields = predicate.get("equals", {})
    if not isinstance(fields, dict) or set(fields) - _EVENT_FIELDS:
        raise GlhsInvariantError("invalid_predicate_event_fields")
    if any(not _scalar(value) for value in fields.values()):
        raise GlhsInvariantError("invalid_predicate_event_value")
    membership = predicate.get("in", {})
    if not isinstance(membership, dict) or set(membership) - _EVENT_FIELDS:
        raise GlhsInvariantError("invalid_predicate_event_fields")
    canonical_membership = {}
    for field, choices in membership.items():
        if (
            not isinstance(choices, list)
            or not choices
            or len(choices) > _MAX_CHILDREN
            or any(not _scalar(value) for value in choices)
        ):
            raise GlhsInvariantError("invalid_predicate_membership")
        canonical_membership[field] = sorted(
            set(choices), key=lambda item: (type(item).__name__, str(item))
        )
    compare = predicate.get("compare")
    canonical_compare = None
    if compare is not None:
        if not isinstance(compare, dict):
            raise GlhsInvariantError("invalid_predicate_comparison")
        _keys(compare, frozenset({"field", "operator", "value"}))
        field, operator, threshold = (
            compare.get("field"),
            compare.get("operator"),
            compare.get("value"),
        )
        if (
            field not in _NUMERIC_FIELDS
            or operator not in _COMPARATORS
            or isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(float(threshold))
            or abs(float(threshold)) > 1e12
        ):
            raise GlhsInvariantError("invalid_predicate_comparison")
        canonical_compare = {"field": field, "operator": operator, "value": threshold}
    authority = predicate.get("authority_at_least")
    if authority is not None and authority not in _AUTHORITY_RANK:
        raise GlhsInvariantError("invalid_predicate_authority")
    if not fields and not canonical_membership and canonical_compare is None and authority is None:
        raise GlhsInvariantError("invalid_predicate_event_fields")
    result: dict[str, Any] = {"op": "event"}
    if fields:
        result["equals"] = dict(sorted(fields.items()))
    if canonical_membership:
        result["in"] = dict(sorted(canonical_membership.items()))
    if canonical_compare is not None:
        result["compare"] = canonical_compare
    if authority is not None:
        result["authority_at_least"] = authority
    for key in ("not_before", "not_after", "known_before"):
        if key in predicate:
            result[key] = _at(predicate[key]).isoformat()
    if "not_before" in result and "not_after" in result:
        if _at(result["not_before"]) > _at(result["not_after"]):
            raise GlhsInvariantError("invalid_predicate_time_window")
    if marker is not None:
        result["derived_from_policy"] = marker
    return result


def _sortable_time(value: object) -> datetime | None:
    """Normalize a valid_at for deterministic scan ordering."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def match_predicate(predicate: object, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Match a validated predicate and report the decisive evidence, bounded.

    Returns ``{"matched", "matched_event_ids", "decisive_event",
    "predicate_digest"}``:

    * ``matched`` - whether the predicate holds over ``events``.
    * ``matched_event_ids`` - the evidence ids the predicate consumed, in
      deterministic ``(valid_at, evidence_id)`` scan order.
    * ``decisive_event`` - ``{"evidence_id", "valid_at", "known_at"}`` of the
      event at which the predicate first becomes satisfied when events are
      scanned in ``(valid_at, evidence_id)`` order; ``None`` when the predicate
      holds with no event (e.g. ``not``).
    * ``predicate_digest`` - sha-256 hex of the canonical validated predicate.

    Evaluation semantics are identical to ``evaluate_predicate`` (order
    invariant; duplicates by ``evidence_id`` are idempotent); only the
    matched/decisive reporting is new.
    """

    validated = validate_predicate(predicate)
    unique = []
    seen: set[str] = set()
    for event in sorted(
        events,
        key=lambda item: (
            _sortable_time(item.get("valid_at")) or datetime.max.replace(tzinfo=UTC),
            str(item.get("evidence_id", "")),
        ),
    ):
        evidence_id = event.get("evidence_id")
        if isinstance(evidence_id, str):
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
        unique.append(event)

    def scan_index(event: dict[str, Any]) -> tuple[datetime, str]:
        return (
            _sortable_time(event.get("valid_at")) or datetime.max.replace(tzinfo=UTC),
            str(event.get("evidence_id", "")),
        )

    def matches(node: dict[str, Any], event: dict[str, Any]) -> bool:
        if not all(
            event.get(field) == expected for field, expected in node.get("equals", {}).items()
        ):
            return False
        if not all(event.get(field) in choices for field, choices in node.get("in", {}).items()):
            return False
        comparison = node.get("compare")
        if comparison is not None:
            actual = event.get(comparison["field"])
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                return False
            expected = comparison["value"]
            operators = {
                "lt": actual < expected,
                "lte": actual <= expected,
                "eq": actual == expected,
                "gte": actual >= expected,
                "gt": actual > expected,
            }
            if not operators[comparison["operator"]]:
                return False
        authority = node.get("authority_at_least")
        actual_authority = event.get("authority")
        if authority is not None and (
            not isinstance(actual_authority, str)
            or _AUTHORITY_RANK.get(actual_authority, -1) < _AUTHORITY_RANK[authority]
        ):
            return False
        valid_at = event.get("valid_at")
        known_at = event.get("known_at")
        if "not_before" in node and (
            not isinstance(valid_at, str) or _at(valid_at) < _at(node["not_before"])
        ):
            return False
        if "not_after" in node and (
            not isinstance(valid_at, str) or _at(valid_at) > _at(node["not_after"])
        ):
            return False
        return "known_before" not in node or (
            isinstance(known_at, str) and _at(known_at) <= _at(node["known_before"])
        )

    def consume(node: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], dict[str, Any] | None]:
        """Return (matched, consumed events in scan order, decisive event)."""
        if node["op"] in {"all", "any"}:
            results = [consume(child) for child in node["children"]]
            matched = all(item[0] for item in results) if node["op"] == "all" else any(
                item[0] for item in results
            )
            matched_results = [item for item in results if item[0]]
            consumed = [
                event
                for event in unique
                if any(event in item[1] for item in matched_results)
            ]
            decisive = None
            if consumed:
                if node["op"] == "any" and any(item[2] is None for item in matched_results):
                    decisive = None
                elif node["op"] == "all":
                    decisive = max(consumed, key=scan_index)
                else:
                    decisive = min(consumed, key=scan_index)
            return matched, consumed, decisive
        if node["op"] == "not":
            return not consume(node["child"])[0], [], None
        if node["op"] == "count":
            matching = [event for event in unique if matches(node["where"], event)]
            minimum = node["min"]
            maximum = node.get("max")
            matched = len(matching) >= minimum and (
                maximum is None or len(matching) <= maximum
            )
            if not matched:
                return False, [], None
            consumed = matching[:minimum]
            return True, consumed, consumed[-1]
        for event in unique:
            if matches(node, event):
                return True, [event], event
        return False, [], None

    matched, consumed, decisive = consume(validated)
    decisive_event = None
    if decisive is not None:
        decisive_event = {
            "evidence_id": str(decisive.get("evidence_id", "")),
            "valid_at": decisive.get("valid_at"),
            "known_at": decisive.get("known_at"),
        }
    return {
        "matched": matched,
        "matched_event_ids": [str(event.get("evidence_id")) for event in consumed],
        "decisive_event": decisive_event,
        "predicate_digest": consistency_fingerprint(validated),
    }


def evaluate_predicate(predicate: object, events: list[dict[str, Any]]) -> bool:
    """Evaluate only validated event dictionaries; input ordering is irrelevant."""

    return match_predicate(predicate, events)["matched"]
