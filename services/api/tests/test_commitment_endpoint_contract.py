from __future__ import annotations

import pytest
from pydantic import ValidationError

from clara_api.api.v1.endpoints.commitments import (
    ProposalRequest,
    SnapshotRequest,
    TransitionRequest,
    router,
)


def test_commitment_routes_expose_human_governance_not_model_or_gold_routes() -> None:
    paths = {route.path for route in router.routes}
    assert "/proposals" in paths
    assert "/{commitment_id}/transitions" in paths
    assert "/snapshots" in paths
    assert not any("model" in path or "gold" in path for path in paths)


def test_commitment_request_contract_rejects_model_origin_and_untyped_fields() -> None:
    with pytest.raises(ValidationError):
        ProposalRequest(
            domain="observations",
            semantic_key="observation:synthetic",
            supersession_key="observation:synthetic",
            observed_evidence_ids=["evidence"],
            proposed_transition="OPEN",
            origin="model",
        )
    with pytest.raises(ValidationError):
        TransitionRequest(
            domain="observations",
            proposal_id="proposal",
            evidence_ids=["evidence"],
            expected_state_version=0,
            action="repeat_measurement",
            target={"system": "s", "code": "c"},
            anchor_valid_time="2026-01-01T00:00:00Z",
            anchor_known_time="2026-01-01T00:00:00Z",
            authority_class="patient_report",
            transition_kind="commitment_opened",
            reason_code="source_grounded",
            construction_gold="forbidden",
        )


def test_commitment_request_contract_requires_timezone_aware_bitemporal_values() -> None:
    with pytest.raises(ValidationError, match="timezone_required"):
        SnapshotRequest(
            domains=["observations"],
            task="reconcile",
            valid_at="2026-01-01T00:00:00",
            known_at="2026-01-01T00:00:00Z",
        )
    request = SnapshotRequest(
        domains=["observations"],
        task="reconcile",
        valid_at="2026-01-01T07:00:00+07:00",
        known_at="2026-01-01T00:00:00Z",
    )
    assert request.valid_at.isoformat() == "2026-01-01T00:00:00+00:00"


def test_snapshot_contract_rejects_unknown_or_duplicate_domains() -> None:
    common = {
        "task": "reconcile",
        "valid_at": "2026-01-01T00:00:00Z",
        "known_at": "2026-01-01T00:00:00Z",
    }
    with pytest.raises(ValidationError, match="commitment_domain_invalid"):
        SnapshotRequest(domains=["observations", "unknown"], **common)
    with pytest.raises(ValidationError, match="commitment_domain_invalid"):
        SnapshotRequest(domains=["observations", "observations"], **common)
