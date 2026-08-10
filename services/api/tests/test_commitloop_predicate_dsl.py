from __future__ import annotations

import itertools

import pytest

from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.predicate_dsl import evaluate_predicate, validate_predicate


def test_dsl_is_deterministic_and_respects_known_time() -> None:
    predicate = {
        "op": "event",
        "equals": {"resource_type": "Observation", "code": "x", "status": "final"},
        "known_before": "2026-01-02T00:00:00+00:00",
    }
    visible = {
        "resource_type": "Observation",
        "code": "x",
        "status": "final",
        "known_at": "2026-01-01T00:00:00+00:00",
    }
    late = {**visible, "known_at": "2026-01-03T00:00:00+00:00"}
    assert evaluate_predicate(predicate, [visible]) is True
    assert evaluate_predicate(predicate, [late]) is False
    assert validate_predicate(predicate) == validate_predicate(predicate)


def test_dsl_rejects_executable_or_unbounded_constructs() -> None:
    with pytest.raises(GlhsInvariantError, match="invalid_predicate_operator"):
        validate_predicate({"op": "python", "code": "__import__('os')"})
    with pytest.raises(GlhsInvariantError, match="invalid_predicate_event_fields"):
        validate_predicate({"op": "event", "equals": {"jsonpath": "$.x"}})
    with pytest.raises(GlhsInvariantError, match="invalid_predicate_fields"):
        validate_predicate(
            {"op": "event", "equals": {"code": "x"}, "python": "print('unsafe')"}
        )


def test_membership_numeric_authority_and_encounter_are_closed_and_typed() -> None:
    predicate = {
        "op": "all",
        "children": [
            {
                "op": "event",
                "equals": {
                    "resource_type": "Observation",
                    "encounter_reference": "Encounter/synthetic",
                },
                "in": {"status": ["amended", "final"]},
                "authority_at_least": "lab_verified",
            },
            {
                "op": "event",
                "equals": {"code": "synthetic"},
                "compare": {"field": "numeric_value", "operator": "gte", "value": 10},
            },
        ],
    }
    events = [
        {
            "evidence_id": "e1",
            "resource_type": "Observation",
            "encounter_reference": "Encounter/synthetic",
            "status": "final",
            "authority": "clinician_confirmed",
        },
        {"evidence_id": "e2", "code": "synthetic", "numeric_value": 10.5},
    ]
    assert evaluate_predicate(predicate, events)
    assert validate_predicate(predicate)["children"][0]["in"]["status"] == [
        "amended",
        "final",
    ]


def test_count_is_order_invariant_and_duplicate_evidence_is_idempotent() -> None:
    predicate = {
        "op": "count",
        "where": {"op": "event", "equals": {"code": "synthetic"}},
        "min": 2,
        "max": 2,
    }
    events = [
        {"evidence_id": "a", "code": "synthetic"},
        {"evidence_id": "b", "code": "synthetic"},
        {"evidence_id": "a", "code": "synthetic"},
    ]
    for permutation in itertools.permutations(events):
        assert evaluate_predicate(predicate, list(permutation))


@pytest.mark.parametrize(
    "predicate",
    [
        {
            "op": "event",
            "compare": {"field": "unbounded", "operator": "gte", "value": 1},
        },
        {
            "op": "event",
            "compare": {"field": "numeric_value", "operator": "gte", "value": 10**13},
        },
        {"op": "event", "authority_at_least": "model_guess"},
        {
            "op": "event",
            "equals": {"code": "x"},
            "not_before": "2026-02-01T00:00:00Z",
            "not_after": "2026-01-01T00:00:00Z",
        },
    ],
)
def test_dsl_rejects_unbounded_or_invalid_typed_constraints(predicate: dict) -> None:
    with pytest.raises(GlhsInvariantError):
        validate_predicate(predicate)
