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


def _proposal_payload(evidence_id: str) -> dict[str, object]:
    return {
        "domain": "observations",
        "semantic_key": "observation:integration:repeat",
        "supersession_key": "observation:integration",
        "observed_evidence_ids": [evidence_id],
        "proposed_transition": "OPEN",
    }


def test_owner_commitment_route_is_consent_scoped_and_append_only() -> None:
    headers = _account("owner")
    evidence_id = _evidence(headers)
    proposal = client.post(
        "/api/v1/commitments/proposals",
        headers=headers,
        json=_proposal_payload(evidence_id),
    )
    assert proposal.status_code == 201, proposal.text
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
    assert snapshot.json()["consent_version"] == (
        f"{MEDICAL_CONSENT_TYPE}:{required_medical_disclaimer_version()}"
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
        json=_proposal_payload(evidence_id),
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
