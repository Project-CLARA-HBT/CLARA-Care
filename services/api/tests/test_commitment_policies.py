from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clara_api.glhs.commitments import DOMAIN_POLICIES, policy_for, validate_domain_version
from clara_api.glhs.domain import GlhsInvariantError


def _validate(domain: str, **overrides: object) -> None:
    values = {
        "policy": policy_for(domain),
        "action": {
            "medications": "take_medication",
            "allergies": "avoid_substance",
            "conditions": "monitor_condition",
            "observations": "repeat_measurement",
        }[domain],
        "target": {"system": "http://example.test", "code": "synthetic"},
        "authority_class": "patient_report",
        "actor_role": "owner",
        "prior_lifecycle": None,
        "lifecycle_state": "OPEN",
        "due_time": datetime(2026, 2, 1, tzinfo=UTC),
        "grace_end": datetime(2026, 2, 8, tzinfo=UTC),
        "has_fulfillment_predicate": True,
        "has_cancellation_predicate": False,
        "has_supersession_predicate": False,
        "has_partial_predicate": False,
    }
    values.update(overrides)
    validate_domain_version(**values)  # type: ignore[arg-type]


def test_four_domain_policies_are_explicit_and_materially_distinct() -> None:
    assert set(DOMAIN_POLICIES) == {
        "medications",
        "allergies",
        "conditions",
        "observations",
    }
    signatures = {
        (
            policy.actions,
            policy.authority_classes,
            policy.default_grace,
            policy.conflict_rule,
            policy.abstention_rule,
            policy.partial_satisfaction,
        )
        for policy in DOMAIN_POLICIES.values()
    }
    assert len(signatures) == 4
    for domain in DOMAIN_POLICIES:
        _validate(domain)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"action": "prescribe_medication"}, "commitment_domain_action_invalid"),
        ({"target": {"code": "missing-system"}}, "commitment_target_invalid"),
        ({"authority_class": "model_inferred"}, "commitment_authority_invalid"),
        ({"actor_role": "admin"}, "commitment_review_authority_required"),
        (
            {"prior_lifecycle": "SUPERSEDED", "lifecycle_state": "OPEN"},
            "commitment_transition_invalid",
        ),
        (
            {"grace_end": datetime(2026, 2, 8, tzinfo=UTC), "due_time": None},
            "commitment_grace_requires_due_time",
        ),
    ],
)
def test_domain_policy_rejects_unsafe_or_incomplete_versions(
    overrides: dict[str, object], reason: str
) -> None:
    with pytest.raises(GlhsInvariantError, match=reason):
        _validate("medications", **overrides)


def test_allergy_policy_disallows_partial_satisfaction() -> None:
    with pytest.raises(GlhsInvariantError, match="commitment_partial_predicate_required"):
        _validate(
            "allergies",
            prior_lifecycle="OPEN",
            lifecycle_state="PARTIALLY_SATISFIED",
            has_partial_predicate=True,
        )


def test_policy_grace_windows_are_frozen_durations() -> None:
    assert DOMAIN_POLICIES["medications"].default_grace == timedelta(days=1)
    assert DOMAIN_POLICIES["allergies"].default_grace == timedelta(0)
    assert DOMAIN_POLICIES["conditions"].default_grace == timedelta(days=7)
