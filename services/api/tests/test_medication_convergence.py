"""Medication provenance, course history, and hypothetical DDI contracts."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.api.v1.endpoints import medication_safety
from clara_api.db.models import GlhsAssertion, MedicationCourse, MedicationCourseChange
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account(label: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"med-v2-{label}-{uuid4().hex}@example.com",
            "password": "secret123",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Medication V2"},
        ).status_code
        == 200
    )
    status = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert (
        client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": status["required_version"]},
        ).status_code
        == 200
    )
    return headers


def test_course_commands_are_opaque_idempotent_and_append_only() -> None:
    headers = _account("history")
    key = uuid4().hex
    created = client.post(
        "/api/v1/medication-courses",
        headers={**headers, "Idempotency-Key": key},
        json={
            "medication_name": "Metformin 500 mg",
            "drugbank_id": "DB00331",
            "dose_text": "500 mg",
            "route_text": "oral",
            "form_text": "tablet",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    UUID(body["id"])
    assert body["reconciliation_status"] == "unknown"
    assert body["normalized_name"] == ""
    assert body["version"] == 1
    replay = client.post(
        "/api/v1/medication-courses",
        headers={**headers, "Idempotency-Key": key},
        json={
            "medication_name": "Metformin 500 mg",
            "drugbank_id": "DB00331",
            "dose_text": "500 mg",
            "route_text": "oral",
            "form_text": "tablet",
        },
    )
    assert replay.json()["id"] == body["id"]
    assert replay.json()["idempotent_replay"] is True

    correction_key = uuid4().hex
    correction_payload = {
        "medication_name": "Metformin",
        "dose_text": "500 mg",
        "schedule_text": "buổi tối",
        "route_text": "oral",
        "form_text": "tablet",
        "reason": "Sửa theo nhãn",
    }
    corrected = client.post(
        f"/api/v1/medication-courses/{body['id']}/correct",
        headers={
            **headers,
            "Idempotency-Key": correction_key,
            "If-Match": "1",
        },
        json=correction_payload,
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["version"] == 2
    corrected_replay = client.post(
        f"/api/v1/medication-courses/{body['id']}/correct",
        headers={
            **headers,
            "Idempotency-Key": correction_key,
            "If-Match": "1",
        },
        json=correction_payload,
    )
    assert corrected_replay.status_code == 200
    assert corrected_replay.json()["idempotent_replay"] is True
    assert corrected_replay.json()["version"] == 2
    ended = client.post(
        f"/api/v1/medication-courses/{body['id']}/end",
        headers={
            **headers,
            "Idempotency-Key": uuid4().hex,
            "If-Match": "2",
        },
        json={"reason": "Người dùng ghi nhận đã kết thúc"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    assert ended.json()["version"] == 3

    history = client.get(
        f"/api/v1/medication-courses/{body['id']}/history",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert history.json()["course_id"] == body["id"]
    assert history.json()["current_version"] == 3
    assert [(item["version"], item["action"]) for item in history.json()["changes"]] == [
        (1, "confirmed_create"),
        (2, "correct"),
        (3, "end"),
    ]
    other_headers = _account("history-other")
    assert (
        client.get(
            f"/api/v1/medication-courses/{body['id']}/history",
            headers=other_headers,
        ).status_code
        == 404
    )

    with SessionLocal() as db:
        course = db.execute(
            select(MedicationCourse).where(MedicationCourse.public_id == body["id"])
        ).scalar_one()
        changes = list(
            db.execute(
                select(MedicationCourseChange)
                .where(MedicationCourseChange.course_id == course.id)
                .order_by(MedicationCourseChange.version_no)
            ).scalars()
        )
        assert [(row.version_no, row.action) for row in changes] == [
            (1, "confirmed_create"),
            (2, "correct"),
            (3, "end"),
        ]
        assertions = list(
            db.execute(
                select(GlhsAssertion)
                .where(GlhsAssertion.profile_id == course.profile_id)
                .order_by(GlhsAssertion.id)
            ).scalars()
        )
        assert len(assertions) == 3
        assert [item.lifecycle_status for item in assertions] == [
            "superseded",
            "rejected",
            "superseded",
        ]
        assert [item.value_json["dose_text"] for item in assertions] == [
            "500 mg",
            "500 mg",
            "500 mg",
        ]


def test_hypothetical_ddi_is_separate_and_explicit(monkeypatch) -> None:
    headers = _account("hypothetical")
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_get",
        lambda *_args, **_kwargs: {
            "drugbank": {
                "state": "ready",
                "version": "test-drugbank",
                "manifest_matches_index": True,
                "integrity_verified": True,
            }
        },
    )
    monkeypatch.setattr(
        medication_safety,
        "proxy_ml_post",
        lambda *_args, **_kwargs: {
            "ddi_alerts": [],
            "metadata": {
                "source_used": ["drugbank"],
                "fallback_used": False,
                "drugbank": {"state": "ready", "version": "test-drugbank"},
            },
        },
    )
    response = client.post(
        "/api/v1/medication-courses/safety/ddi",
        headers=headers,
        json={"hypothetical_medications": ["Medicine A", "Medicine B"]},
    )
    assert response.status_code == 200
    assert response.json()["hypothetical"] is True
    assert response.json()["input_mode"] == "hypothetical"
    assert response.json()["courses"] == []
    mixed = client.post(
        "/api/v1/medication-courses/safety/ddi",
        headers=headers,
        json={
            "course_ids": ["not-a-course"],
            "hypothetical_medications": ["A", "B"],
        },
    )
    assert mixed.status_code == 422
    assert mixed.json()["detail"]["code"] == "mixed_real_and_hypothetical_inputs"
