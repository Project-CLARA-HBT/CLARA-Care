"""Universal Capture safety, review, and isolation contracts."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from clara_api.api.v1.endpoints import lifemap_capture as capture_endpoint
from clara_api.core.config import get_settings
from clara_api.db.models import (
    LifeMapCaptureCandidate,
    LifeMapCaptureReviewAction,
    LifeMapCaptureSession,
    LifeMapEvent,
    MedicationCourse,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.capture_artifacts import StoredCaptureArtifact
from clara_api.lifemap.capture_domain import (
    emergency_fast_path,
    validate_candidate,
)
from clara_api.main import app
from clara_api.phr.normalizer import NormalizedMedication

client = TestClient(app)


class ArtifactStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        *,
        profile_public_id: str,
        artifact_public_id: str,
        data: bytes,
        declared_type: str,
    ) -> StoredCaptureArtifact:
        key = f"capture/{profile_public_id}/{artifact_public_id}"
        self.objects[key] = data
        return StoredCaptureArtifact(
            storage_key=key,
            media_type=declared_type,
            byte_size=len(data),
            checksum="test-checksum",
            malware_status="clean",
        )

    def get(self, *, storage_key: str) -> bytes:
        return self.objects[storage_key]

    def delete(self, *, storage_key: str) -> None:
        self.objects.pop(storage_key, None)


def _account(label: str) -> tuple[dict[str, str], str]:
    email = f"capture-{label}-{uuid4().hex}@normal.clara"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": f"Capture {label}"},
    ).status_code == 200
    consent_status = client.get("/api/v1/auth/consent-status", headers=headers)
    assert consent_status.status_code == 200
    required = consent_status.json()["required_version"]
    accepted = client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"accepted": True, "consent_version": required},
    )
    assert accepted.status_code == 200
    profiles = client.get("/api/v1/profiles", headers=headers).json()
    return headers, profiles[0]["id"]


def test_capture_domain_has_conservative_bilingual_emergency_fast_path() -> None:
    assert emergency_fast_path("Tôi đau ngực và không thở được")
    assert emergency_fast_path("severe chest pain and cannot breathe")
    assert not emergency_fast_path("Tôi muốn ghi lại giấc ngủ hôm qua")
    validation = validate_candidate(
        "medication_label", {"medication_name": "Medicine A"}
    )
    assert validation.valid
    assert validation.missing_critical == ("strength", "route")


def test_emergency_capture_short_circuits_before_any_persistence(monkeypatch) -> None:
    headers, _profile_id = _account("emergency")
    monkeypatch.setattr(get_settings(), "lifemap_capture_enabled", True)
    with SessionLocal() as db:
        before = db.execute(
            select(func.count(LifeMapCaptureSession.id))
        ).scalar_one()
    response = client.post(
        "/api/v1/lifemap/capture/sessions",
        headers=headers,
        json={"text": "Tôi đau ngực và không thở được", "locale": "vi"},
    )
    assert response.status_code == 201
    assert response.json()["emergency"] is True
    assert response.json()["persisted"] is False
    with SessionLocal() as db:
        after = db.execute(select(func.count(LifeMapCaptureSession.id))).scalar_one()
    assert after == before


def test_capture_review_is_resumable_profile_scoped_and_idempotent(monkeypatch) -> None:
    owner, owner_profile = _account("owner")
    stranger, _stranger_profile = _account("stranger")
    monkeypatch.setattr(get_settings(), "lifemap_capture_enabled", True)
    created = client.post(
        "/api/v1/lifemap/capture/sessions",
        headers=owner,
        json={"text": "Tôi ngủ 7 giờ tối qua", "locale": "vi"},
    )
    assert created.status_code == 201, created.text
    session = created.json()
    assert session["emergency"] is False
    candidate = session["candidates"][0]
    assert candidate["status"] == "draft"
    assert candidate["source_span"] == {
        "start": 0,
        "end": len("Tôi ngủ 7 giờ tối qua"),
    }

    resumed = client.get(
        f"/api/v1/lifemap/capture/sessions/{session['id']}", headers=owner
    )
    assert resumed.status_code == 200
    denied = client.get(
        f"/api/v1/lifemap/capture/sessions/{session['id']}",
        headers={**stranger, "X-CLARA-Profile-Context": owner_profile},
    )
    assert denied.status_code == 404

    key = f"capture-confirm-{uuid4().hex}"
    confirmed = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate['id']}/review",
        headers={**owner, "Idempotency-Key": key},
        json={"action": "confirm", "reason": "Người dùng đã kiểm tra"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["idempotent_replay"] is False
    assert confirmed.json()["event_id"]
    duplicates = client.get(
        f"/api/v1/lifemap/capture/candidates/{candidate['id']}/duplicates",
        headers=owner,
    )
    assert duplicates.status_code == 200
    assert duplicates.json() == {
        "candidate_id": candidate["id"],
        "suggestions": [
            {
                "event_id": confirmed.json()["event_id"],
                "reason_code": "exact_source_checksum",
            }
        ],
        "auto_merged": False,
    }

    replay = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate['id']}/review",
        headers={**owner, "Idempotency-Key": key},
        json={"action": "confirm", "reason": "Người dùng đã kiểm tra"},
    )
    assert replay.status_code == 200
    assert replay.json()["event_id"] == confirmed.json()["event_id"]
    assert replay.json()["idempotent_replay"] is True

    with SessionLocal() as db:
        event = db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.public_id == confirmed.json()["event_id"]
            )
        ).scalar_one()
        assert event.truth_state == "confirmed"
        assert event.profile_id
        assert db.execute(
            select(func.count(LifeMapCaptureReviewAction.id)).where(
                LifeMapCaptureReviewAction.candidate_id.is_not(None)
            )
        ).scalar_one() == 1


def test_capture_artifact_access_is_short_lived_scoped_and_deleted_on_abandon(
    monkeypatch,
) -> None:
    owner, _profile_id = _account("artifact")
    stranger, _stranger_profile = _account("artifact-stranger")
    monkeypatch.setattr(get_settings(), "lifemap_capture_enabled", True)
    store = ArtifactStore()
    monkeypatch.setattr(capture_endpoint, "_artifact_store", lambda: store)
    session = client.post(
        "/api/v1/lifemap/capture/artifact-sessions",
        headers=owner,
        json={"input_kind": "visit_document", "locale": "vi"},
    ).json()
    uploaded = client.post(
        f"/api/v1/lifemap/capture/sessions/{session['id']}/artifacts",
        headers=owner,
        files={"artifact": ("note.txt", b"bounded artifact", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    artifact = uploaded.json()
    assert artifact["malware_status"] == "clean"
    assert artifact["job"]["status"] == "queued"
    job = client.get(
        f"/api/v1/lifemap/capture/jobs/{artifact['job']['id']}",
        headers=owner,
    )
    assert job.status_code == 200
    assert job.json()["status"] == "queued"
    assert job.json()["candidates"] == []
    content = client.get(
        f"/api/v1/lifemap/capture/artifacts/{artifact['id']}/content",
        headers={
            **owner,
            "X-Capture-Artifact-Token": artifact["access_token"],
        },
    )
    assert content.status_code == 200
    assert content.content == b"bounded artifact"
    assert content.headers["cache-control"] == "no-store, private"
    assert client.get(
        f"/api/v1/lifemap/capture/artifacts/{artifact['id']}/content",
        headers={
            **stranger,
            "X-Capture-Artifact-Token": artifact["access_token"],
        },
    ).status_code == 404
    assert client.get(
        f"/api/v1/lifemap/capture/artifacts/{artifact['id']}/content",
        headers={**owner, "X-Capture-Artifact-Token": "0.invalid"},
    ).status_code == 403

    abandoned = client.post(
        f"/api/v1/lifemap/capture/sessions/{session['id']}/abandon",
        headers=owner,
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["status"] == "abandoned"
    assert store.objects == {}


def test_medication_capture_requires_critical_review_then_creates_confirmed_course(
    monkeypatch,
) -> None:
    owner, _profile_id = _account("medication-review")
    monkeypatch.setattr(get_settings(), "lifemap_capture_enabled", True)
    monkeypatch.setattr(
        capture_endpoint,
        "normalize_medication_name",
        lambda name, db=None: NormalizedMedication(
            display_name="Paracetamol",
            normalized_name="paracetamol",
            rx_cui="161",
            normalization_source="db",
            confidence=1.0,
            is_normalized=True,
        ),
    )
    created = client.post(
        "/api/v1/lifemap/capture/artifact-sessions",
        headers=owner,
        json={"input_kind": "medication_label", "locale": "vi"},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]
    with SessionLocal() as db:
        session = db.execute(
            select(LifeMapCaptureSession).where(
                LifeMapCaptureSession.public_id == session_id
            )
        ).scalar_one()
        candidate = LifeMapCaptureCandidate(
            session_id=session.id,
            profile_id=session.profile_id,
            candidate_type="medication_label",
            field_path="medication_label",
            value_json={"medication_name": "Paracetamol"},
            confidence=0.62,
            field_confidence_json={"medication_name": 0.62},
            source_span_json={
                "kind": "text_fields",
                "fields": {"medication_name": {"start": 0, "end": 11}},
            },
            missing_critical_fields_json=["strength", "route"],
            extraction_schema_version="lifemap.capture.v1",
            extractor_version="grounded-ocr-baseline-v1",
        )
        db.add(candidate)
        db.commit()
        candidate_id = candidate.public_id

    blocked = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate_id}/review",
        headers={**owner, "Idempotency-Key": f"missing-{uuid4().hex}"},
        json={"action": "confirm"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "critical_fields_missing"

    edited_value = {
        "medication_name": "Paracetamol",
        "strength": "500 mg",
        "route": "oral",
    }
    edited = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate_id}/review",
        headers={**owner, "Idempotency-Key": f"edit-{uuid4().hex}"},
        json={"action": "edit", "value": edited_value},
    )
    assert edited.status_code == 200, edited.text
    proposal = client.get(
        f"/api/v1/lifemap/capture/candidates/{candidate_id}/normalization",
        headers=owner,
    )
    assert proposal.status_code == 200, proposal.text
    assert proposal.json() == {
        "candidate_id": candidate_id,
        "original_text": "Paracetamol",
        "status": "candidate",
        "proposal": {
            "display_name": "Paracetamol",
            "normalized_name": "paracetamol",
            "system": "rxnorm",
            "code": "161",
            "source": "db",
            "confidence": 1.0,
        },
        "auto_confirmable": False,
        "requires_explicit_acceptance": True,
        "mapping_policy_version": "lifemap-medication-normalization-v1",
    }
    confirmed = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate_id}/review",
        headers={**owner, "Idempotency-Key": f"confirm-{uuid4().hex}"},
        json={"action": "confirm", "accept_normalization": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["medication_course_id"]
    assert confirmed.json()["normalization"]["accepted"] is True
    with SessionLocal() as db:
        course = db.execute(
            select(MedicationCourse).where(
                MedicationCourse.public_id
                == confirmed.json()["medication_course_id"]
            )
        ).scalar_one()
        assert course.medication_name == "Paracetamol"
        assert course.dose_text == "500 mg"
        assert course.route_text == "oral"
        assert course.truth_state == "confirmed"
        assert course.normalized_name == "paracetamol"
        assert course.normalization_system == "rxnorm"
        assert course.normalization_code == "161"
        assert course.provenance_json["normalization"]["decision"] == "accepted"


def test_medication_capture_never_accepts_an_unmapped_normalization(
    monkeypatch,
) -> None:
    owner, _profile_id = _account("medication-unmapped")
    monkeypatch.setattr(get_settings(), "lifemap_capture_enabled", True)
    monkeypatch.setattr(
        capture_endpoint,
        "normalize_medication_name",
        lambda name, db=None: NormalizedMedication(
            display_name=name,
            normalized_name=name.casefold(),
            rx_cui="",
            normalization_source="fallback",
            confidence=0.0,
            is_normalized=False,
        ),
    )
    created = client.post(
        "/api/v1/lifemap/capture/artifact-sessions",
        headers=owner,
        json={"input_kind": "medication_label", "locale": "vi"},
    )
    session_id = created.json()["id"]
    with SessionLocal() as db:
        session = db.execute(
            select(LifeMapCaptureSession).where(
                LifeMapCaptureSession.public_id == session_id
            )
        ).scalar_one()
        candidate = LifeMapCaptureCandidate(
            session_id=session.id,
            profile_id=session.profile_id,
            candidate_type="medication_label",
            field_path="medication_label",
            value_json={
                "medication_name": "Unknown medicine",
                "strength": "1 tablet",
                "route": "oral",
            },
            missing_critical_fields_json=[],
            extraction_schema_version="lifemap.capture.v1",
            extractor_version="test",
        )
        db.add(candidate)
        db.commit()
        candidate_id = candidate.public_id

    proposal = client.get(
        f"/api/v1/lifemap/capture/candidates/{candidate_id}/normalization",
        headers=owner,
    )
    assert proposal.status_code == 200
    assert proposal.json()["status"] == "unmapped"
    assert proposal.json()["proposal"] is None
    blocked = client.post(
        f"/api/v1/lifemap/capture/candidates/{candidate_id}/review",
        headers={**owner, "Idempotency-Key": f"unmapped-{uuid4().hex}"},
        json={"action": "confirm", "accept_normalization": True},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "normalization_not_available"
