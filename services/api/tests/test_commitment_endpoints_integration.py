from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.consent import MEDICAL_CONSENT_TYPE, required_medical_disclaimer_version
from clara_api.db.models import HealthSourceReference, PhrProfile, UserConsent
from clara_api.db.session import SessionLocal
from clara_api.glhs.gateway import EvidenceInput, record_evidence
from clara_api.main import app

client = TestClient(app)


def _account(
    label: str, *, request_client: TestClient = client, accept_consent: bool = True
) -> dict[str, str]:
    response = request_client.post(
        "/api/v1/auth/login",
        json={"email": f"commitment-{label}-{uuid4().hex}@example.com", "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert (
        request_client.put(
            "/api/v1/phr/record", headers=headers, json={"full_name": "Commitment Test"}
        ).status_code
        == 200
    )
    if accept_consent:
        consent = request_client.get("/api/v1/auth/consent-status", headers=headers).json()
        assert (
            request_client.post(
                "/api/v1/auth/consent",
                headers=headers,
                json={"accepted": True, "consent_version": consent["required_version"]},
            ).status_code
            == 200
        )
    return headers


def _evidence(headers: dict[str, str], *, request_client: TestClient = client) -> str:
    consent_status = request_client.get("/api/v1/auth/consent-status", headers=headers)
    assert consent_status.status_code == 200, consent_status.text
    user_id = int(consent_status.json()["user_id"])
    with SessionLocal() as db:
        profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == user_id)).scalar_one()
        source = HealthSourceReference(
            profile_id=profile.id,
            source_kind="integration_fixture",
            source_identity=f"commitment-source:{uuid4()}",
            checksum="sha256:integration-fixture",
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        db.add(source)
        db.flush()
        evidence = record_evidence(
            db,
            profile_id=profile.id,
            data=EvidenceInput(
                source_reference_id=source.id,
                evidence_kind="source_event",
                artifact_type="fhir_resource",
                artifact_public_id="Observation/integration",
                fingerprint=f"commitment-evidence:{uuid4()}",
                valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        )
        db.commit()
        return evidence.public_id


def _proposal_payload(
    evidence_id: str, snapshot: dict[str, object] | None = None
) -> dict[str, object]:
    snapshot = snapshot or {
        "snapshot_id": "untrusted-snapshot",
        "manifest_digest": "0" * 64,
        "state_version": 0,
    }
    return {
        "domain": "observations",
        "semantic_key": "observation:integration:repeat",
        "supersession_key": "observation:integration",
        "observed_evidence_ids": [evidence_id],
        "proposed_transition": "OPEN",
        "observed_base_state_version": snapshot["state_version"],
        "task": "commitment_proposal",
        "source_snapshot_id": snapshot["snapshot_id"],
        "source_snapshot_digest": snapshot["manifest_digest"],
    }


def _proposal_snapshot(headers: dict[str, str], evidence_id: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/commitments/snapshots",
        headers=headers,
        json={
            "domains": ["observations"],
            "task": "commitment_proposal",
            "valid_at": "2026-01-02T00:00:00Z",
            "known_at": "2026-01-02T00:00:00Z",
            "strict": True,
            "evidence_ids": [evidence_id],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_owner_commitment_route_is_consent_scoped_and_append_only() -> None:
    headers = _account("owner")
    evidence_id = _evidence(headers)
    proposal_snapshot = _proposal_snapshot(headers, evidence_id)
    proposal = client.post(
        "/api/v1/commitments/proposals",
        headers=headers,
        json=_proposal_payload(evidence_id, proposal_snapshot),
    )
    assert proposal.status_code == 201, proposal.text
    assert proposal.json()["source_snapshot_id"] == proposal_snapshot["snapshot_id"]
    assert proposal.json()["source_snapshot_digest"] == proposal_snapshot["manifest_digest"]
    transition_payload = {
        "domain": "observations",
        "proposal_id": proposal.json()["proposal_id"],
        "evidence_ids": [evidence_id],
        "expected_state_version": 0,
        "action": "repeat_measurement",
        "target": {"system": "http://loinc.org", "code": "integration"},
        "anchor_valid_time": "2026-01-01T00:00:00Z",
        "anchor_known_time": "2026-01-01T00:00:00Z",
        "authority_class": "patient_report",
        "fulfillment_predicate": {
            "op": "event",
            "equals": {
                "resource_type": "Observation",
                "system": "http://loinc.org",
                "code": "integration",
                "status": "final",
            },
        },
        "transition_kind": "commitment_opened",
        "reason_code": "source_grounded_intent",
    }
    transition = client.post(
        f"/api/v1/commitments/{proposal.json()['commitment_id']}/transitions",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json=transition_payload,
    )
    assert transition.status_code == 201, transition.text
    stale = client.post(
        f"/api/v1/commitments/{proposal.json()['commitment_id']}/transitions",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json=transition_payload,
    )
    assert stale.status_code == 409, stale.text
    snapshot = client.post(
        "/api/v1/commitments/snapshots",
        headers=headers,
        json={
            "domains": ["observations"],
            "task": "reconcile_commitments",
            "valid_at": "2026-01-02T00:00:00Z",
            "known_at": "2026-01-02T00:00:00Z",
            "strict": True,
        },
    )
    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.json()["state_version"] == transition.json()["resulting_state_version"]
    assert snapshot.json()["consent_version"].startswith(
        f"{MEDICAL_CONSENT_TYPE}:{required_medical_disclaimer_version()}:"
    )
    decision = client.get(
        f"/api/v1/commitments/{proposal.json()['commitment_id']}/decisions/"
        f"{transition.json()['decision_id']}?domain=observations",
        headers=headers,
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["result_product_state"]["lifecycle_state"] == "OPEN"

    other = _account("other")
    denied = client.get(
        f"/api/v1/commitments/{proposal.json()['commitment_id']}/decisions/"
        f"{transition.json()['decision_id']}?domain=observations",
        headers=other,
    )
    assert denied.status_code == 404


def test_commitment_route_requires_current_medical_consent() -> None:
    headers = _account("unconsented", accept_consent=False)
    evidence_id = _evidence(headers)
    response = client.post(
        "/api/v1/commitments/proposals",
        headers=headers,
        json=_proposal_payload(evidence_id),
    )
    assert response.status_code == 428, response.text


def test_commitment_route_requires_authentication() -> None:
    anonymous_client = TestClient(app)
    response = anonymous_client.post(
        "/api/v1/commitments/proposals",
        json=_proposal_payload("glhs-evidence-untrusted"),
    )
    assert response.status_code == 401


def test_commitment_proposal_api_never_admits_an_unbound_thss_input() -> None:
    """The public proposal API has no base-version-only fallback for THSS work."""

    headers = _account("thss-binding")
    evidence_id = _evidence(headers)
    payload = _proposal_payload(evidence_id)
    payload.pop("source_snapshot_id")
    payload.pop("source_snapshot_digest")
    response = client.post("/api/v1/commitments/proposals", headers=headers, json=payload)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert {error["loc"][-1] for error in errors} == {
        "source_snapshot_id",
        "source_snapshot_digest",
    }


def test_commitment_proposal_api_rejects_foreign_profile_snapshot() -> None:
    """The HTTP path must not turn another profile's THSS into local authority."""

    owner_headers = _account("foreign-snapshot-owner")
    owner_evidence = _evidence(owner_headers)
    foreign_snapshot = _proposal_snapshot(owner_headers, owner_evidence)

    target_headers = _account("foreign-snapshot-target")
    target_evidence = _evidence(target_headers)
    response = client.post(
        "/api/v1/commitments/proposals",
        headers=target_headers,
        json=_proposal_payload(target_evidence, foreign_snapshot),
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"detail": {"code": "proposal_snapshot_scope_forbidden"}}


def test_revoked_medical_consent_blocks_commitment_and_can_be_reaccepted() -> None:
    headers = _account("revoked")
    status_response = client.get("/api/v1/auth/consent-status", headers=headers)
    user_id = int(status_response.json()["user_id"])
    with SessionLocal() as db:
        db.add(
            UserConsent(
                user_id=user_id,
                consent_type=MEDICAL_CONSENT_TYPE,
                consent_version=required_medical_disclaimer_version(),
                revoked_at=datetime.now(UTC),
            )
        )
        db.commit()
    evidence_id = _evidence(headers)
    assert client.get("/api/v1/auth/consent-status", headers=headers).json()["accepted"] is False
    blocked = client.post(
        "/api/v1/commitments/proposals",
        headers=headers,
        json=_proposal_payload(evidence_id),
    )
    assert blocked.status_code == 428, blocked.text

    reaccepted = client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={
            "accepted": True,
            "consent_version": required_medical_disclaimer_version(),
        },
    )
    assert reaccepted.status_code == 200, reaccepted.text
    allowed = client.post(
        "/api/v1/commitments/proposals",
        headers=headers,
        json=_proposal_payload(evidence_id, _proposal_snapshot(headers, evidence_id)),
    )
    assert allowed.status_code == 201, allowed.text


def test_cookie_authenticated_commitment_mutation_requires_csrf_header() -> None:
    cookie_client = TestClient(app)
    headers = _account("csrf", request_client=cookie_client)
    evidence_id = _evidence(headers, request_client=cookie_client)
    response = cookie_client.post(
        "/api/v1/commitments/proposals",
        json=_proposal_payload(evidence_id),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}


def test_lease_acquire_and_renew_endpoints() -> None:
    headers = _account("lease-test")
    # Acquire lease
    acquire_resp = client.post(
        "/api/v1/leases/acquire",
        headers=headers,
        json={
            "domain": "medications",
            "partitions": ["medications:rx-test-1", "medications:rx-test-2"],
            "timeout_seconds": 5.0,
            "epoch": 1,
        },
    )
    assert acquire_resp.status_code == 201, acquire_resp.text
    lease_data = acquire_resp.json()
    assert "lease_id" in lease_data
    assert lease_data["epoch"] == 1
    assert lease_data["state"] == "active"
    assert len(lease_data["held_coordinates"]) == 2
    lease_id = lease_data["lease_id"]

    # Renew lease
    renew_resp = client.post(
        f"/api/v1/leases/{lease_id}/renew",
        headers=headers,
        json={"epoch": 2, "validate_snapshots": True},
    )
    assert renew_resp.status_code == 200, renew_resp.text
    renew_data = renew_resp.json()
    assert renew_data["lease_id"] == lease_id
    assert renew_data["epoch"] == 2
    assert renew_data["state"] == "active"


def test_lease_renew_wounded_fails_closed() -> None:
    from clara_api.glhs.commitment_gateway import get_dag_lock_manager
    headers = _account("lease-wounded")
    acquire_resp = client.post(
        "/api/v1/leases/acquire",
        headers=headers,
        json={"domain": "medications", "partitions": ["medications:rx-wounded-1"]},
    )
    assert acquire_resp.status_code == 201, acquire_resp.text
    lease_id = acquire_resp.json()["lease_id"]

    # Mark wounded
    lock_mgr = get_dag_lock_manager()
    txn = lock_mgr.get_transaction(lease_id)
    assert txn is not None
    txn.mark_wounded("preempted_by_higher_priority")

    renew_resp = client.post(
        f"/api/v1/leases/{lease_id}/renew",
        headers=headers,
        json={"validate_snapshots": False},
    )
    assert renew_resp.status_code == 409, renew_resp.text
    assert "wound_wait_preempted" in renew_resp.json()["detail"]["code"]


def test_commitment_cancel_endpoint() -> None:
    headers = _account("cancel-test")
    evidence_id = _evidence(headers)
    proposal_snapshot = _proposal_snapshot(headers, evidence_id)
    proposal = client.post(
        "/api/v1/commitments/proposals",
        headers=headers,
        json=_proposal_payload(evidence_id, proposal_snapshot),
    )
    assert proposal.status_code == 201, proposal.text
    commitment_id = proposal.json()["commitment_id"]

    transition_payload = {
        "domain": "observations",
        "proposal_id": proposal.json()["proposal_id"],
        "evidence_ids": [evidence_id],
        "expected_state_version": 0,
        "action": "repeat_measurement",
        "target": {"system": "http://loinc.org", "code": "integration"},
        "anchor_valid_time": "2026-01-01T00:00:00Z",
        "anchor_known_time": "2026-01-01T00:00:00Z",
        "authority_class": "patient_report",
        "fulfillment_predicate": {
            "op": "event",
            "equals": {
                "resource_type": "Observation",
                "system": "http://loinc.org",
                "code": "integration",
                "status": "final",
            },
        },
        "transition_kind": "commitment_opened",
        "reason_code": "source_grounded_intent",
    }
    transition = client.post(
        f"/api/v1/commitments/{commitment_id}/transitions",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json=transition_payload,
    )
    assert transition.status_code == 201, transition.text

    # Cancel commitment
    cancel_resp = client.post(
        f"/api/v1/commitments/{commitment_id}/cancel",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={
            "domain": "observations",
            "reason_code": "patient_requested_cancellation",
            "evidence_ids": [evidence_id],
        },
    )
    assert cancel_resp.status_code == 201, cancel_resp.text
    cancel_data = cancel_resp.json()
    assert cancel_data["commitment_id"] == commitment_id
    assert cancel_data["lifecycle_state"] == "CANCELLED"
    assert cancel_data["resulting_state_version"] == transition.json()["resulting_state_version"] + 1

    # Cancelling again fails with 409
    cancel_again = client.post(
        f"/api/v1/commitments/{commitment_id}/cancel",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"domain": "observations", "reason_code": "retry"},
    )
    assert cancel_again.status_code == 409, cancel_again.text
