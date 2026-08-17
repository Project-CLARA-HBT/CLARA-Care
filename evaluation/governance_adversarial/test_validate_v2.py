from __future__ import annotations

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.cache_observer import (
    CacheObservation,
)
from evaluation.governance_adversarial.family_contracts import CACHE_FAMILIES
from evaluation.governance_adversarial.validate_v2 import (
    validate_boundary_attestation,
    validate_cache_observation,
    validate_family_result,
    validate_observation_fields,
)


def _observation_metadata(*, cache: bool = False) -> dict[str, object]:
    value: dict[str, object] = {
        "status_code": 403,
        "db_before_sha256": "a" * 64,
        "db_after_sha256": "a" * 64,
        "commit_occurred": False,
        "latency_ms": 1.0,
        "availability_error": False,
    }
    if cache:
        value["cache_index_revocation_failure"] = False
        value.update(CacheObservation.absent().asdict())
    return value


def _cache_observation(*, stale: bool = False) -> CacheObservation:
    return CacheObservation(
        stale_cache_entry_exists=stale,
        stale_cache_returned=False,
        governance_reevaluation_occurred=True,
        stale_cache_caused_invalid_persistent_commit=False,
        revocation_to_not_visible_latency=0.0,
    )


def test_non_cache_family_requires_only_http_postgres() -> None:
    validate_family_result(
        family="cross_subject_retrieval",
        attestation={"http": True, "postgres": True},
        observation_metadata=_observation_metadata(),
    )


def test_permitted_audit_attestation_accepted_for_non_audit_family() -> None:
    validate_family_result(
        family="cross_subject_retrieval",
        attestation={"http": True, "postgres": True, "audit": True},
        observation_metadata=_observation_metadata(),
    )


def test_missing_required_stage_rejected() -> None:
    with pytest.raises(FreezeError, match="govred_v2_boundary_stage_missing:postgres"):
        validate_boundary_attestation(
            family="cross_subject_retrieval",
            attestation={"http": True},
        )


def test_non_cache_family_claiming_cache_rejected_as_unsupported() -> None:
    with pytest.raises(FreezeError, match="govred_v2_unsupported_attestation:cache"):
        validate_boundary_attestation(
            family="cross_subject_retrieval",
            attestation={"http": True, "postgres": True, "cache": True},
        )


def test_unknown_stage_rejected() -> None:
    with pytest.raises(FreezeError, match="govred_v2_attestation_unknown_stage"):
        validate_boundary_attestation(
            family="cross_subject_retrieval",
            attestation={"http": True, "postgres": True, "sqlite": True},
        )


def test_cache_family_requires_cache_stage() -> None:
    with pytest.raises(FreezeError, match="govred_v2_boundary_stage_missing:cache"):
        validate_boundary_attestation(
            family="revoked_consent_cache_index_reuse",
            attestation={"http": True, "postgres": True},
        )


def test_cache_family_requires_concrete_cache_observation() -> None:
    for family in CACHE_FAMILIES:
        with pytest.raises(FreezeError, match="govred_v2_cache_observation_missing"):
            validate_family_result(
                family=family,
                attestation={"http": True, "postgres": True, "cache": True},
                observation_metadata=_observation_metadata(cache=True),
            )


def test_cache_family_valid_evidence_passes() -> None:
    for family in CACHE_FAMILIES:
        validate_family_result(
            family=family,
            attestation={"http": True, "postgres": True, "cache": True, "audit": True},
            observation_metadata=_observation_metadata(cache=True),
            cache_observation=_cache_observation(stale=True),
        )


def test_cache_family_missing_observation_field_rejected() -> None:
    cache_obs = CacheObservation(
        stale_cache_entry_exists=True,
        stale_cache_returned=True,
        governance_reevaluation_occurred=False,
        stale_cache_caused_invalid_persistent_commit=True,
        revocation_to_not_visible_latency=5.0,
    )
    incomplete = {k: v for k, v in cache_obs.asdict().items() if k != "stale_cache_returned"}
    observation_metadata = {**_observation_metadata(cache=True), **incomplete}
    observation_metadata.pop("stale_cache_returned")
    with pytest.raises(
        FreezeError, match="govred_v2_observation_field_missing:stale_cache_returned"
    ):
        validate_observation_fields(
            family="revoked_consent_cache_index_reuse",
            observation_metadata=observation_metadata,
        )


def test_missing_required_observation_field_rejected() -> None:
    metadata = _observation_metadata()
    metadata.pop("db_before_sha256")
    with pytest.raises(FreezeError, match="govred_v2_observation_field_missing:db_before_sha256"):
        validate_observation_fields(family="role_mismatch", observation_metadata=metadata)


def test_unsupported_cache_observation_rejected_on_non_cache_family() -> None:
    with pytest.raises(FreezeError, match="govred_v2_unsupported_cache_observation"):
        validate_cache_observation(
            family="role_mismatch",
            cache_observation=_cache_observation(stale=True),
        )


def test_neutral_cache_observation_allowed_on_non_cache_family() -> None:
    validate_cache_observation(family="role_mismatch", cache_observation=CacheObservation.absent())


def test_observation_metadata_requires_mapping() -> None:
    with pytest.raises(FreezeError, match="govred_v2_boundary_path_attestation_missing"):
        validate_boundary_attestation(family="role_mismatch", attestation=None)


def test_required_stages_match_cache_family_contract() -> None:
    from evaluation.governance_adversarial.validate_v2 import required_stages

    assert required_stages("revoked_consent_cache_index_reuse") == {"http", "postgres", "cache"}
    assert required_stages("cross_subject_retrieval") == {"http", "postgres"}
