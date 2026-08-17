from __future__ import annotations

import pytest

from evaluation.governance_adversarial.controls import (
    _MUTATION_BY_INVALID,
    control_pair,
    invalid_control,
    valid_control,
    validate_control_names,
)
from evaluation.governance_adversarial.family_contracts import (
    VALID_CONTROL_NAMES,
    family_contract,
)
from evaluation.governance_adversarial.protocol import FAMILIES


def test_every_family_has_matched_valid_invalid_pair() -> None:
    validate_control_names()
    for family in FAMILIES:
        valid, invalid = control_pair(family)
        assert valid.family == family and valid.kind == "valid"
        assert invalid.family == family and invalid.kind == "invalid"
        assert valid.control in VALID_CONTROL_NAMES
        assert valid.dimension == _dimension(valid.control)


def test_valid_and_invalid_pair_share_boundary_shape() -> None:
    for family in FAMILIES:
        valid, invalid = control_pair(family)
        contract = family_contract(family)
        assert valid.required_stages == contract.required_stages()
        assert invalid.required_stages == contract.required_stages()


def test_valid_controls_pin_distinct_dimensions() -> None:
    expected = {
        "consent_unchanged_valid": "consent",
        "policy_unchanged_valid": "policy",
        "actor_stable_valid": "actor",
        "same_state_valid": "state",
        "digest_intact_valid": "digest",
        "unexpired_valid": "expiry",
        "same_subject_valid": "subject",
    }
    for control, dimension in expected.items():
        case = _valid_for(control)
        assert case.dimension == dimension


def test_invalid_controls_map_to_commit_mutations_or_disclosure_path() -> None:
    allowed_mutations = {
        None,
        "subject_cross_replay",
        "consent_revoke",
        "actor_switch_replay",
        "state_advance",
        "concurrent_governance_writer",
        "policy_version_change",
        "snapshot_digest_invalid",
        "none",
    }
    for family in FAMILIES:
        invalid = invalid_control(family)
        assert invalid.control in _MUTATION_BY_INVALID
        assert invalid.mutation in allowed_mutations


def test_valid_controls_never_carry_a_mutation() -> None:
    for family in FAMILIES:
        valid = valid_control(family)
        assert valid.mutation is None
        assert valid.governance_delta == "none"
        assert valid.expected_outcome == "governance_intact"


def test_digest_expiry_family_declares_secondary_valid_control() -> None:
    contract = family_contract("digest_expiry_tamper_replay")
    assert contract.valid_controls == ("digest_intact_valid", "unexpired_valid")
    assert valid_control("digest_expiry_tamper_replay", primary=False).control == "unexpired_valid"


def test_control_pair_stages_include_cache_only_for_cache_families() -> None:
    cache_family = "revoked_consent_cache_index_reuse"
    valid, invalid = control_pair(cache_family)
    assert "cache" in valid.required_stages
    assert "cache" in invalid.required_stages
    non_cache_valid, non_cache_invalid = control_pair("role_mismatch")
    assert "cache" not in non_cache_valid.required_stages
    assert "cache" not in non_cache_invalid.required_stages


def test_unknown_valid_control_name_rejected() -> None:
    with pytest.raises(ValueError, match="govred_unknown_family"):
        valid_control("not_a_real_family")


def _dimension(control: str) -> str:
    from evaluation.governance_adversarial.controls import _DIMENSION_BY_VALID

    return _DIMENSION_BY_VALID[control]


def _valid_for(control: str):
    from evaluation.governance_adversarial.controls import _VALID_BUILDERS

    return _VALID_BUILDERS[control]("role_mismatch")
