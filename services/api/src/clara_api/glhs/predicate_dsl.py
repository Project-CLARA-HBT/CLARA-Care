"""Bounded, deterministic JSON predicates for CommitLoop evidence matching.

This deliberately interprets a closed data structure.  It never evaluates
Python, SQL, JSONPath, regexes, or model-provided executable content.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

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
            }
        ),
    )
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
    return result


def evaluate_predicate(predicate: object, events: list[dict[str, Any]]) -> bool:
    """Evaluate only validated event dictionaries; input ordering is irrelevant."""

    value = validate_predicate(predicate)
    unique_events = []
    seen_ids = set()
    for event in events:
        evidence_id = event.get("evidence_id")
        if isinstance(evidence_id, str):
            if evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)
        unique_events.append(event)

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

    def evaluate(node: dict[str, Any]) -> bool:
        if node["op"] == "all":
            return all(evaluate(child) for child in node["children"])
        if node["op"] == "any":
            return any(evaluate(child) for child in node["children"])
        if node["op"] == "not":
            return not evaluate(node["child"])
        if node["op"] == "count":
            count = sum(matches(node["where"], event) for event in unique_events)
            return count >= node["min"] and ("max" not in node or count <= node["max"])
        return any(matches(node, event) for event in unique_events)

    return evaluate(value)
