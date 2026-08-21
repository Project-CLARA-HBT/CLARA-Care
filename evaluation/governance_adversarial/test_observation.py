from __future__ import annotations

from evaluation.governance_adversarial.observation import (
    BoundaryObservation,
    classify,
    sanitized_observation_metadata,
)


def test_oracle_detects_synthetic_sentinel_without_persisting_body() -> None:
    observation = BoundaryObservation(
        status_code=200,
        response_body=b"blocked? RIVF_SENTINEL_X",
        db_before_sha256="a" * 64,
        db_after_sha256="a" * 64,
        audit_reconstruction_complete=True,
        cache_index_revocation_failure=False,
        commit_occurred=False,
        latency_ms=12.3,
        availability_error=False,
    )
    classified = classify(
        observation=observation, sentinel_token="RIVF_SENTINEL_X", expected_rejection=True
    )
    assert classified["unauthorized_disclosure"] == "true"
    assert classified["successful_bypass"] == "true"
    assert "response_body" not in sanitized_observation_metadata(observation)
