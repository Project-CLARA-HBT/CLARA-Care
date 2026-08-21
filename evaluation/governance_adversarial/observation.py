"""Sanitize isolated-boundary observations and apply deterministic oracles."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BoundaryObservation:
    status_code: int | None
    response_body: bytes
    db_before_sha256: str
    db_after_sha256: str
    audit_reconstruction_complete: bool
    cache_index_revocation_failure: bool
    commit_occurred: bool
    latency_ms: float
    availability_error: bool


def classify(
    *, observation: BoundaryObservation, sentinel_token: str, expected_rejection: bool
) -> dict[str, str]:
    """Return a raw-result-safe deterministic observation classification.

    Response content is inspected in memory solely for the synthetic sentinel;
    it is never returned or persisted.
    """

    exposed = sentinel_token.encode("utf-8") in observation.response_body
    bypass = (
        expected_rejection and observation.status_code is not None and observation.status_code < 400
    )
    return {
        "response_sha256": hashlib.sha256(observation.response_body).hexdigest(),
        "unauthorized_disclosure": str(exposed).lower(),
        "successful_bypass": str(bypass).lower(),
        "stale_or_unauthorized_commit": str(observation.commit_occurred).lower(),
        "wrong_subject_exposure": str(exposed).lower(),
        "cache_index_revocation_failure": str(observation.cache_index_revocation_failure).lower(),
        "audit_reconstruction_complete": str(observation.audit_reconstruction_complete).lower(),
        "availability_error": str(observation.availability_error).lower(),
        "latency_ms": str(observation.latency_ms),
        "db_state_changed": str(
            observation.db_before_sha256 != observation.db_after_sha256
        ).lower(),
    }


def sanitized_observation_metadata(observation: BoundaryObservation) -> dict[str, object]:
    """Provide safe artifact metadata without response/audit/database payloads."""

    result = asdict(observation)
    result.pop("response_body")
    return result
