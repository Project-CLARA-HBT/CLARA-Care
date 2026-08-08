"""Opaque, grounded Visit loop and revision-aware pack contracts."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.api.v1.endpoints import visits
from clara_api.db.models import GlhsAssertion, LifeMapEvent
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account(label: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"visit-v2-{label}-{uuid4().hex}@example.com",
            "password": "secret123",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": "Visit V2"},
    ).status_code == 200
    status = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"accepted": True, "consent_version": status["required_version"]},
    ).status_code == 200
    return headers


def _visit(headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/visits",
        headers=headers,
        json={"title": "Tái khám", "goal": "Chuẩn bị câu hỏi"},
    )
    assert response.status_code == 201, response.text
    UUID(response.json()["id"])
    return response.json()["id"]


def test_grounded_instruction_requires_exact_span_and_explicit_confirmation(
    monkeypatch,
) -> None:
    headers = _account("grounded")
    visit_id = _visit(headers)
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"title": "Theo dõi sau khám", "goal": "Tái khám"},
    )
    assert episode.status_code == 201, episode.text
    episode_id = episode.json()["id"]
    linked = client.post(
        f"/api/v1/visits/{visit_id}/episodes",
        headers=headers,
        json={"episode_id": episode_id},
    )
    assert linked.status_code == 201, linked.text
    source = "Bác sĩ dặn tái khám sau 2 tuần."
    document = client.post(
        f"/api/v1/visits/{visit_id}/documents",
        headers=headers,
        json={
            "title": "Ghi chú sau khám",
            "text_content": source,
            "media_type": "text/plain",
            "metadata": {"capture": "user_selected"},
        },
    )
    assert document.status_code == 201, document.text
    document_id = document.json()["id"]
    UUID(document_id)
    # The E2E document path writes evidence availability to GLHS but must not
    # interpret free text into a medical assertion before grounded review.
    with SessionLocal() as db:
        document_assertion = db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.semantic_key == f"visit_document:{document_id}"
            )
        ).scalar_one()
        assert document_assertion.assertion_type == "evidence"
        assert document_assertion.predicate == "visit_document_available"
        assert document_assertion.value_json["contains_interpreted_clinical_facts"] is False
        assert source not in str(document_assertion.value_json)
    quote = "tái khám sau 2 tuần"
    start = source.index(quote)
    monkeypatch.setattr(
        visits,
        "get_settings",
        lambda: SimpleNamespace(lifemap_visit_extraction_enabled=True),
    )
    monkeypatch.setattr(
        visits,
        "proxy_ml_post",
        lambda *_args, **_kwargs: {
            "status": "ready_for_review",
            "schema_version": "lifemap.visit-instruction.v1",
            "extractor_version": "deepseek-test",
            "candidates": [
                {
                    "id": "candidate-1",
                    "kind": "follow_up",
                    "classification": "clinician_instruction",
                    "title": "Tái khám sau 2 tuần",
                    "confidence": 0.94,
                    "source_spans": [
                        {
                            "page": None,
                            "region": None,
                            "start": start,
                            "end": start + len(quote),
                            "text": quote,
                        }
                    ],
                    "source_document_digest": document.json()["content_digest"],
                }
            ],
        },
    )
    extracted = client.post(
        f"/api/v1/visits/{visit_id}/plan/extract",
        headers=headers,
        json={"document_id": document_id},
    )
    assert extracted.status_code == 202, extracted.text
    draft = extracted.json()
    UUID(draft["id"])
    assert draft["safe_unavailable"] is False
    assert draft["candidates"][0]["source_spans"][0]["text"] == quote

    confirmed = client.post(
        f"/api/v1/visits/{visit_id}/plan/confirm",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={
            "draft_id": draft["id"],
            "candidate_ids": ["candidate-1"],
            "task_status": "proposed",
            "episode_id": episode_id,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert len(confirmed.json()["task_ids"]) == 1
    UUID(confirmed.json()["task_ids"][0])
    assert len(confirmed.json()["episode_event_ids"]) == 1
    with SessionLocal() as db:
        event = db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.public_id == confirmed.json()["episode_event_ids"][0]
            )
        ).scalar_one()
        assertion = db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == event.profile_id,
                GlhsAssertion.semantic_key == f"lifemap_event:{event.public_id}",
            )
        ).scalar_one()
        assert assertion.epistemic_state == "documented"
        assert assertion.lifecycle_status == "active"

    options = client.get(
        f"/api/v1/visits/{visit_id}/pack-options",
        headers=headers,
    )
    assert options.status_code == 200, options.text
    instruction = options.json()["instructions"][0]
    UUID(instruction["id"])
    assert instruction["label"] == "Tái khám sau 2 tuần"
    pack = client.post(
        f"/api/v1/visits/{visit_id}/pack",
        headers=headers,
        json={
            "selection": {
                "concern_ids": [],
                "episode_ids": [],
                "event_ids": [],
                "medication_course_ids": [],
                "instruction_candidate_ids": [instruction["id"]],
                "questions": [],
            }
        },
    )
    assert pack.status_code == 201, pack.text
    assert client.post(
        f"/api/v1/visit-packs/{pack.json()['id']}/approve",
        headers=headers,
    ).status_code == 200
    shared = client.post(
        f"/api/v1/visit-packs/{pack.json()['id']}/shares",
        headers=headers,
        json={"expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    )
    assert shared.status_code == 201, shared.text
    snapshot = client.get(
        f"/api/v1/visit-packs/shared/{shared.json()['token']}"
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["confirmed_instructions"][0]["source_spans"][0][
        "text"
    ] == quote

    withdrawn = client.post(
        f"/api/v1/visits/{visit_id}/documents/{document_id}/withdraw",
        headers=headers,
        json={"reason": "owner_withdrew"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    with SessionLocal() as db:
        document_assertion = db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.semantic_key == f"visit_document:{document_id}"
            )
        ).scalar_one()
        assert document_assertion.lifecycle_status == "superseded"
    assert (
        client.get(f"/api/v1/visit-packs/shared/{shared.json()['token']}").status_code
        == 404
    )


def test_pack_selection_is_opaque_and_medication_change_revokes_stale_share() -> None:
    headers = _account("pack")
    visit_id = _visit(headers)
    concern = client.post(
        f"/api/v1/visits/{visit_id}/concerns",
        headers=headers,
        json={"text": "Tôi cần hỏi về lịch dùng thuốc", "priority": "routine"},
    )
    medication = client.post(
        "/api/v1/medication-courses",
        headers={**headers, "Idempotency-Key": uuid4().hex},
        json={"medication_name": "Metformin", "dose_text": "500 mg"},
    )
    assert concern.status_code == 201
    assert medication.status_code == 201
    options = client.get(
        f"/api/v1/visits/{visit_id}/pack-options",
        headers=headers,
    )
    assert options.status_code == 200, options.text
    assert options.json()["concerns"][0]["id"] == concern.json()["id"]
    assert options.json()["medications"][0]["id"] == medication.json()["id"]

    pack = client.post(
        f"/api/v1/visits/{visit_id}/pack",
        headers=headers,
        json={
            "selection": {
                "concern_ids": [concern.json()["id"]],
                "episode_ids": [],
                "event_ids": [],
                "medication_course_ids": [medication.json()["id"]],
                "instruction_candidate_ids": [],
                "questions": [],
            }
        },
    )
    assert pack.status_code == 201, pack.text
    UUID(pack.json()["id"])
    approved = client.post(
        f"/api/v1/visit-packs/{pack.json()['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    shared = client.post(
        f"/api/v1/visit-packs/{pack.json()['id']}/shares",
        headers=headers,
        json={"expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    )
    assert shared.status_code == 201, shared.text

    corrected = client.post(
        f"/api/v1/medication-courses/{medication.json()['id']}/correct",
        headers={
            **headers,
            "Idempotency-Key": uuid4().hex,
            "If-Match": "1",
        },
        json={
            "medication_name": "Metformin",
            "dose_text": "850 mg",
            "reason": "Sửa dữ liệu đã nhập nhầm",
        },
    )
    assert corrected.status_code == 200
    unavailable = client.get(
        f"/api/v1/visit-packs/shared/{shared.json()['token']}"
    )
    assert unavailable.status_code == 404


def test_opaque_visit_reference_does_not_cross_profiles() -> None:
    owner = _account("owner")
    other = _account("other")
    visit_id = _visit(owner)

    assert client.get(f"/api/v1/visits/{visit_id}", headers=other).status_code == 404
