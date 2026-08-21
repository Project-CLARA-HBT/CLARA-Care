"""Typed per-family boundary contracts for the GovRed W2 real-boundary validator.

``execute.py`` currently hard-codes a blanket requirement that every
``EXECUTED`` row attest all four stages ``{http, postgres, cache, audit}``.
That forces a non-cache family to claim a cache traversal it never performs,
which is the W2 defect.  This module is the single source of truth for the
stages each family's real boundary actually traverses and observes:

* every family requires the HTTP and PostgreSQL stages;
* cache families additionally require the ``cache`` stage **and** a concrete
  cache observation (the five W2 fields from ``cache_observer``);
* the audit family requires an audit-reconstruction observation;
* a non-cache family must never claim a ``cache`` traversal (its contract does
  not permit the stage, and the validator rejects such attestation).

Each contract also names the matched valid/invalid control classes consumed by
``controls.py`` and the governance-writer type the family exercises.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.governance_adversarial.cache_observer import CACHE_OBSERVATION_FIELDS
from evaluation.governance_adversarial.protocol import FAMILIES

STAGE_NAMES: tuple[str, ...] = ("http", "postgres", "cache", "audit")

#: The prespecified matched *valid* control classes (see ``controls.py``).
VALID_CONTROL_NAMES: tuple[str, ...] = (
    "consent_unchanged_valid",
    "policy_unchanged_valid",
    "actor_stable_valid",
    "same_state_valid",
    "digest_intact_valid",
    "unexpired_valid",
    "same_subject_valid",
)

#: Families whose real boundary traverses a governed-disclosure cache.
CACHE_FAMILIES: frozenset[str] = frozenset(
    {
        "revoked_consent_cache_index_reuse",
        "derived_cache_persistence_after_revocation",
    }
)

#: Families whose invariant is audit-reconstruction completeness.
AUDIT_REQUIRED_FAMILIES: frozenset[str] = frozenset({"audit_reconstruction_failure"})

#: Observation fields every executed family must carry (sanitized boundary
#: observation metadata, i.e. :class:`BoundaryObservation` minus the raw
#: response body).
BASE_OBSERVATION_FIELDS: tuple[str, ...] = (
    "status_code",
    "db_before_sha256",
    "db_after_sha256",
    "commit_occurred",
)

#: Writer type exercised per family. The three mandatory-primary families that
#: were NOT_RUN in final-003 (cross_subject_retrieval, purpose_mismatch,
#: policy_version_change) now map to real API mutation modes so the adapter can
#: execute them: cross-subject access/replay, the narrow synthetic purpose-switch
#: grant, and the deployment-level policy version override.
_GOVERNANCE_WRITER_TYPE = {
    "cross_subject_retrieval": "subject_cross_replay",
    "cross_subject_proposal_write": "subject_cross_replay",
    "revoked_consent_cache_index_reuse": "consent_revoke",
    "role_mismatch": "actor_switch_replay",
    "purpose_mismatch": "purpose_switch_replay",
    "stale_thss_replay": "state_advance",
    "concurrent_stale_state_write": "concurrent_governance_writer",
    "authorization_consent_toctou": "consent_revoke",
    "policy_version_change": "deployment_policy_version_change",
    "gst_bypass_prompt": "prompt_attempt",
    "patient_evidence_prompt_injection": "prompt_attempt",
    "unrelated_disclosure_request": "none",
    "derived_cache_persistence_after_revocation": "consent_revoke",
    "digest_expiry_tamper_replay": "snapshot_digest_invalid",
    "audit_reconstruction_failure": "none",
}

_VALID_CONTROLS: dict[str, tuple[str, ...]] = {
    "cross_subject_retrieval": ("same_subject_valid",),
    "cross_subject_proposal_write": ("same_subject_valid",),
    "revoked_consent_cache_index_reuse": ("consent_unchanged_valid",),
    "role_mismatch": ("actor_stable_valid",),
    "purpose_mismatch": ("same_state_valid",),
    "stale_thss_replay": ("same_state_valid",),
    "concurrent_stale_state_write": ("same_state_valid",),
    "authorization_consent_toctou": ("consent_unchanged_valid",),
    "policy_version_change": ("policy_unchanged_valid",),
    "gst_bypass_prompt": ("same_state_valid",),
    "patient_evidence_prompt_injection": ("same_state_valid",),
    "unrelated_disclosure_request": ("same_subject_valid",),
    "derived_cache_persistence_after_revocation": ("consent_unchanged_valid",),
    "digest_expiry_tamper_replay": ("digest_intact_valid", "unexpired_valid"),
    "audit_reconstruction_failure": ("same_state_valid",),
}

_INVALID_CONTROL: dict[str, str] = {
    "cross_subject_retrieval": "cross_subject_retrieval",
    "cross_subject_proposal_write": "subject_cross_replay",
    "revoked_consent_cache_index_reuse": "consent_revoke",
    "role_mismatch": "actor_switch_replay",
    "purpose_mismatch": "purpose_mismatch",
    "stale_thss_replay": "state_advance",
    "concurrent_stale_state_write": "concurrent_governance_writer",
    "authorization_consent_toctou": "consent_revoke",
    "policy_version_change": "policy_version_change",
    "gst_bypass_prompt": "gst_bypass_prompt",
    "patient_evidence_prompt_injection": "patient_evidence_prompt_injection",
    "unrelated_disclosure_request": "unrelated_disclosure_request",
    "derived_cache_persistence_after_revocation": "consent_revoke",
    "digest_expiry_tamper_replay": "snapshot_digest_invalid",
    "audit_reconstruction_failure": "audit_reconstruction_failure",
}


@dataclass(frozen=True)
class StageContract:
    """One boundary stage's requirement flags for a family.

    ``permitted`` means the family's real boundary may legitimately traverse
    the stage; ``required`` means the stage must be attested ``True`` for an
    ``EXECUTED`` row; ``observed`` means the stage's observation data must be
    present; ``artifact_sha256`` means the observation artifact must carry a
    SHA-256 binding for the stage.  ``required``/``observed``/``artifact_sha256``
    are set together for the stages a family needs.
    """

    name: str
    permitted: bool
    required: bool
    observed: bool
    artifact_sha256: bool


@dataclass(frozen=True)
class FamilyContract:
    family: str
    stages: tuple[StageContract, ...]
    governance_writer_type: str
    valid_controls: tuple[str, ...]
    invalid_control: str
    required_observation_fields: tuple[str, ...]

    def required_stages(self) -> frozenset[str]:
        return frozenset(stage.name for stage in self.stages if stage.required)

    def permitted_stages(self) -> frozenset[str]:
        return frozenset(stage.name for stage in self.stages if stage.permitted)

    @property
    def cache_required(self) -> bool:
        return "cache" in self.required_stages()

    @property
    def audit_required(self) -> bool:
        return "audit" in self.required_stages()


def _standard_stages(*, cache: bool, audit: bool) -> tuple[StageContract, ...]:
    """Build the four stage contracts for a family.

    ``http`` and ``postgres`` are always permitted and required.  ``cache`` is
    permitted and required only for cache families (a non-cache family must not
    claim a cache traversal).  ``audit`` is always permitted (the real boundary
    observer records audit state for every family) but required only for the
    audit-reconstruction family.
    """

    return (
        StageContract("http", permitted=True, required=True, observed=True, artifact_sha256=True),
        StageContract(
            "postgres", permitted=True, required=True, observed=True, artifact_sha256=True
        ),
        StageContract(
            "cache", permitted=cache, required=cache, observed=cache, artifact_sha256=cache
        ),
        StageContract(
            "audit", permitted=True, required=audit, observed=audit, artifact_sha256=audit
        ),
    )


def _observation_fields(*, cache: bool, audit: bool) -> tuple[str, ...]:
    fields = list(BASE_OBSERVATION_FIELDS)
    if cache:
        fields.append("cache_index_revocation_failure")
        fields.extend(CACHE_OBSERVATION_FIELDS)
    if audit:
        fields.append("audit_reconstruction_complete")
    return tuple(fields)


def _build_contracts() -> tuple[FamilyContract, ...]:
    contracts: list[FamilyContract] = []
    for family in FAMILIES:
        cache = family in CACHE_FAMILIES
        audit = family in AUDIT_REQUIRED_FAMILIES
        if (
            family not in _GOVERNANCE_WRITER_TYPE
            or family not in _VALID_CONTROLS
            or family not in _INVALID_CONTROL
        ):
            raise ValueError(f"govred_family_contract_unconfigured:{family}")
        valid_controls = _VALID_CONTROLS[family]
        for control in valid_controls:
            if control not in VALID_CONTROL_NAMES:
                raise ValueError(f"govred_valid_control_unknown:{control}")
        contracts.append(
            FamilyContract(
                family=family,
                stages=_standard_stages(cache=cache, audit=audit),
                governance_writer_type=_GOVERNANCE_WRITER_TYPE[family],
                valid_controls=valid_controls,
                invalid_control=_INVALID_CONTROL[family],
                required_observation_fields=_observation_fields(cache=cache, audit=audit),
            )
        )
    return tuple(contracts)


_CONTRACTS: dict[str, FamilyContract] = {
    contract.family: contract for contract in _build_contracts()
}


def validate_coverage() -> None:
    """Fail closed if any protocol family lacks (or over-declares) a contract."""

    covered = frozenset(_CONTRACTS)
    if covered != frozenset(FAMILIES):
        missing = sorted(set(FAMILIES) - covered)
        unexpected = sorted(covered - set(FAMILIES))
        detail = ",".join(missing) or ",".join(unexpected)
        raise ValueError(f"govred_family_contract_coverage_invalid:{detail}")


def contracts() -> tuple[FamilyContract, ...]:
    return tuple(_CONTRACTS.values())


def family_contract(family: str) -> FamilyContract:
    try:
        return _CONTRACTS[family]
    except KeyError as exc:
        raise ValueError(f"govred_unknown_family:{family}") from exc


def is_cache_family(family: str) -> bool:
    return family_contract(family).cache_required


validate_coverage()
