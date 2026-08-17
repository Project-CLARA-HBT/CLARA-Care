from __future__ import annotations

from evaluation.governance_adversarial.controls_schema import (
    POSITIVE_CONTROLS,
    positive_control_schema,
)


def test_schema_defines_all_seven_matched_positive_controls() -> None:
    schema = positive_control_schema()
    expected = {
        "consent_revoke_invalid",
        "policy_change_invalid",
        "actor_change_invalid",
        "state_advance_invalid",
        "digest_corrupt_invalid",
        "expired_invalid",
        "cross_subject_invalid",
    }
    assert set(schema["controls"].keys()) == expected


def test_each_control_has_a_distinct_matched_valid_control() -> None:
    for invalid, spec in POSITIVE_CONTROLS.items():
        assert spec["valid_control"]
        assert spec["valid_control"] != invalid
        assert spec["family"]
        assert spec["mutation_class"]
        assert spec["expected_invalid_outcome"] == "rejected"
        assert spec["expected_valid_outcome"] == "committed"


def test_valid_control_names_follow_authority_preserving_semantics() -> None:
    schema = positive_control_schema()
    valid_names = [spec["valid_control"] for spec in schema["controls"].values()]
    assert "consent_unchanged_valid" in valid_names
    assert "policy_unchanged_valid" in valid_names
    assert "actor_stable_valid" in valid_names
    assert "same_state_valid" in valid_names
    assert "digest_intact_valid" in valid_names
    assert "unexpired_valid" in valid_names
    assert "same_subject_valid" in valid_names


def test_schema_is_json_serializable_and_preserves_coordinates() -> None:
    import json

    schema = positive_control_schema()
    json.dumps(schema)
    assert schema["schema_version"] == "govred-positive-control-schema-v1"
    assert "consent_granted" in schema["preserved_coordinates"]
    assert "state_version_current" in schema["preserved_coordinates"]
