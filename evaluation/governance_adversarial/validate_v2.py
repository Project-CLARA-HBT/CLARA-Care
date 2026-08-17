"""W2 per-family boundary validator replacing the all-stage boolean check.

``execute.py`` hard-codes ``_REQUIRED_BOUNDARY_STAGES = {http, postgres, cache,
audit}`` and requires every ``EXECUTED`` row to attest all four stages.  That is
wrong for W2: a family that never traverses a cache must not claim one, and a
cache family must carry a concrete cache observation.  This module validates
ONLY the stages each family's contract requires and rejects unsupported
attestation (for example, a non-cache family claiming ``cache``).  It is the W2
replacement for the hard-coded boolean requirement; ``execute.py`` is
intentionally left unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.cache_observer import (
    CACHE_OBSERVATION_FIELDS,
    CacheObservation,
)
from evaluation.governance_adversarial.family_contracts import (
    STAGE_NAMES,
    family_contract,
)


def validate_boundary_attestation(*, family: str, attestation: object) -> None:
    """Check only the family's required stages; reject unsupported attestation.

    * every required stage must be present and ``True``;
    * a stage claimed as ``True`` must be within the family's permitted stages
      (a non-cache family claiming ``cache`` is rejected as unsupported).
    """

    contract = family_contract(family)
    if not isinstance(attestation, dict):
        raise FreezeError("govred_v2_boundary_path_attestation_missing")
    claimed = {stage for stage, value in attestation.items() if value is True}
    if unknown := claimed - set(STAGE_NAMES):
        raise FreezeError("govred_v2_attestation_unknown_stage:" + ",".join(sorted(unknown)))
    if missing := contract.required_stages() - claimed:
        raise FreezeError("govred_v2_boundary_stage_missing:" + ",".join(sorted(missing)))
    if unsupported := claimed - contract.permitted_stages():
        raise FreezeError("govred_v2_unsupported_attestation:" + ",".join(sorted(unsupported)))


def validate_observation_fields(*, family: str, observation_metadata: Mapping[str, object]) -> None:
    """Require the family's required observation fields in sanitized metadata.

    ``observation_metadata`` is the combined sanitized boundary observation
    (``BoundaryObservation`` minus the raw response body) plus, for cache
    families, the concrete cache-observation fields.
    """

    contract = family_contract(family)
    missing = [
        field for field in contract.required_observation_fields if field not in observation_metadata
    ]
    if missing:
        raise FreezeError("govred_v2_observation_field_missing:" + ",".join(sorted(missing)))


def validate_cache_observation(*, family: str, cache_observation: CacheObservation | None) -> None:
    """Enforce the concrete cache observation for cache families.

    A cache family must carry a :class:`CacheObservation` with every W2 field.
    A non-cache family must not carry a cache observation that claims any stale
    cache result (an all-neutral observation is permitted as a no-claim).
    """

    contract = family_contract(family)
    if not contract.cache_required:
        if cache_observation is not None and any(cache_observation.asdict().values()):
            raise FreezeError("govred_v2_unsupported_cache_observation")
        return
    if cache_observation is None:
        raise FreezeError("govred_v2_cache_observation_missing")
    if missing := set(CACHE_OBSERVATION_FIELDS) - set(cache_observation.asdict()):
        raise FreezeError("govred_v2_cache_observation_field_missing:" + ",".join(sorted(missing)))


def validate_family_result(
    *,
    family: str,
    attestation: object,
    observation_metadata: Mapping[str, object],
    cache_observation: CacheObservation | None = None,
) -> None:
    """Validate one family's complete W2 boundary evidence.

    This is the entry point adapters/executors should call for each executed
    logical case in place of the blanket all-stage boolean check.
    """

    validate_boundary_attestation(family=family, attestation=attestation)
    validate_observation_fields(family=family, observation_metadata=observation_metadata)
    validate_cache_observation(family=family, cache_observation=cache_observation)


def required_stages(family: str) -> frozenset[str]:
    """Return the stages a family's contract requires (adapter-facing)."""

    return family_contract(family).required_stages()


def permitted_stages(family: str) -> frozenset[str]:
    """Return the stages a family's contract permits (adapter-facing)."""

    return family_contract(family).permitted_stages()
