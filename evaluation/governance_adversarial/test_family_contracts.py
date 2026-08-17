from __future__ import annotations

import pytest

from evaluation.governance_adversarial.cache_observer import CACHE_OBSERVATION_FIELDS
from evaluation.governance_adversarial.family_contracts import (
    AUDIT_REQUIRED_FAMILIES,
    BASE_OBSERVATION_FIELDS,
    CACHE_FAMILIES,
    STAGE_NAMES,
    VALID_CONTROL_NAMES,
    contracts,
    family_contract,
    is_cache_family,
    validate_coverage,
)
from evaluation.governance_adversarial.protocol import FAMILIES


def test_every_protocol_family_has_a_typed_contract() -> None:
    validate_coverage()
    registered = {contract.family for contract in contracts()}
    assert registered == set(FAMILIES)


def test_every_family_requires_http_and_postgres() -> None:
    for family in FAMILIES:
        required = family_contract(family).required_stages()
        assert {"http", "postgres"} <= required
        assert required <= set(STAGE_NAMES)


def test_non_cache_family_must_not_claim_cache_traversal() -> None:
    for family in FAMILIES:
        contract = family_contract(family)
        if family in CACHE_FAMILIES:
            assert is_cache_family(family)
            continue
        assert "cache" not in contract.required_stages()
        assert "cache" not in contract.permitted_stages()
        assert not is_cache_family(family)


def test_cache_family_requires_concrete_cache_observation() -> None:
    assert CACHE_FAMILIES == {
        "revoked_consent_cache_index_reuse",
        "derived_cache_persistence_after_revocation",
    }
    for family in CACHE_FAMILIES:
        contract = family_contract(family)
        assert "cache" in contract.required_stages()
        assert "cache" in contract.permitted_stages()
        for field in CACHE_OBSERVATION_FIELDS:
            assert field in contract.required_observation_fields
        assert "cache_index_revocation_failure" in contract.required_observation_fields


def test_audit_required_only_for_audit_reconstruction_family() -> None:
    for family in FAMILIES:
        contract = family_contract(family)
        if family in AUDIT_REQUIRED_FAMILIES:
            assert "audit" in contract.required_stages()
            assert "audit_reconstruction_complete" in contract.required_observation_fields
        else:
            assert "audit" not in contract.required_stages()


def test_base_observation_fields_required_for_every_family() -> None:
    for family in FAMILIES:
        for field in BASE_OBSERVATION_FIELDS:
            assert field in family_contract(family).required_observation_fields


def test_stage_contract_flags_are_consistent() -> None:
    for contract in contracts():
        for stage in contract.stages:
            assert stage.name in STAGE_NAMES
            if stage.required:
                assert stage.permitted
                assert stage.observed
                assert stage.artifact_sha256
            if stage.observed:
                assert stage.permitted


def test_valid_controls_within_prespecified_set() -> None:
    for family in FAMILIES:
        contract = family_contract(family)
        assert contract.valid_controls
        assert set(contract.valid_controls) <= set(VALID_CONTROL_NAMES)


def test_governance_writer_type_and_invalid_control_declared() -> None:
    for family in FAMILIES:
        contract = family_contract(family)
        assert contract.governance_writer_type
        assert contract.invalid_control


def test_unknown_family_contract_rejected() -> None:
    with pytest.raises(ValueError, match="govred_unknown_family"):
        family_contract("not_a_real_family")
