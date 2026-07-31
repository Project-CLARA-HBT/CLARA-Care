"""End-to-end boundary tests for Council's opaque Research snapshot attachment.

The browser selects only a completed own Research job ID.  The API then derives
and persists a bounded identifier/category packet, and adds it to the internal
Council request only.  No research prose, query, URL, citation title, score, or
client-provided packet is accepted at this boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import ResearchJob, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_RUN_REQUEST = {
    "symptoms": ["fatigue"],
    "labs": {"creatinine": 1.2},
    "medications": ["warfarin"],
    "history": "hypertension",
    "specialists": ["pharmacology", "nephrology"],
}


def _login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_case(headers: dict[str, str]) -> int:
    response = client.post(
        "/api/v1/council/cases",
        headers=headers,
        json={"title": "attachment case", "request": _RUN_REQUEST},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _insert_completed_snapshot(email: str, *, usable: bool = True) -> str:
    job_id = f"research-{uuid4()}"
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        now = datetime.now(tz=UTC)
        snapshot = {
            "schema_version": "1.0",
            "run_id": job_id,
            "captured_at": now.isoformat(),
            "evidence_sha256": "a" * 64,
            "citation_registry": (
                [
                    {
                        "citation_id": "PMID:123456",
                        "source_type": "guideline",
                        "title": "must never cross into Council",
                        "url": "https://example.invalid/private",
                    },
                    {
                        "citation_id": "DOI:10.1000/example",
                        "source_type": "systematic_review",
                    },
                ]
                if usable
                else [{"citation_id": "opaque-1", "source_type": "unknown"}]
            ),
            "citations": [{"title": "not exposed", "url": "https://example.invalid"}],
        }
        db.add(
            ResearchJob(
                job_id=job_id,
                user_id=user.id,
                role="doctor",
                status="completed",
                query_text="sensitive research query must not cross boundary",
                request_payload={"query": "sensitive research query must not cross boundary"},
                result_json={"answer": "not exposed"},
                evidence_snapshot_json=snapshot,
                progress_json={},
                error_text="",
                started_at=now,
                completed_at=now,
            )
        )
        db.commit()
    return job_id


def test_attach_is_owner_scoped_opaque_and_append_only(set_flags) -> None:
    set_flags(council_evidence_packet_shadow_enabled=True)
    owner_email = "snapshot-owner@doctor.clara"
    owner = _login(owner_email)
    other = _login("snapshot-other@doctor.clara")
    case_id = _create_case(owner)
    job_id = _insert_completed_snapshot(owner_email)

    options = client.get(f"/api/v1/council/cases/{case_id}/evidence-snapshots", headers=owner)
    assert options.status_code == 200, options.text
    listed = next(item for item in options.json()["items"] if item["job_id"] == job_id)
    assert listed == {
        "job_id": job_id,
        "captured_at": listed["captured_at"],
        "evidence_count": 2,
        "categories": ["clinical_guideline", "systematic_review"],
    }
    assert "query" not in listed
    assert "title" not in listed
    assert "url" not in listed

    attached = client.post(
        f"/api/v1/council/cases/{case_id}/evidence-snapshots/{job_id}/attach",
        headers=owner,
    )
    assert attached.status_code == 201, attached.text
    body = attached.json()
    assert body["research_job_id"] == job_id
    assert body["evidence_count"] == 2
    assert body["categories"] == ["clinical_guideline", "systematic_review"]
    assert "evidence_packet" not in body
    assert "query" not in body
    assert "title" not in body
    assert "url" not in body

    second = client.post(
        f"/api/v1/council/cases/{case_id}/evidence-snapshots/{job_id}/attach",
        headers=owner,
    )
    assert second.status_code == 201, second.text
    attachments = client.get(f"/api/v1/council/cases/{case_id}/evidence-attachments", headers=owner)
    assert attachments.status_code == 200, attachments.text
    assert len(attachments.json()["items"]) == 2

    # The same endpoints must not reveal whether this case/job exists to another doctor.
    assert (
        client.get(f"/api/v1/council/cases/{case_id}/evidence-snapshots", headers=other).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/council/cases/{case_id}/evidence-attachments", headers=other).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/council/cases/{case_id}/evidence-snapshots/{job_id}/attach",
            headers=other,
        ).status_code
        == 404
    )


def test_only_completed_traceable_snapshot_is_attachable(set_flags) -> None:
    set_flags(council_evidence_packet_shadow_enabled=True)
    email = "snapshot-unusable@doctor.clara"
    headers = _login(email)
    case_id = _create_case(headers)
    unusable_job_id = _insert_completed_snapshot(email, usable=False)

    options = client.get(f"/api/v1/council/cases/{case_id}/evidence-snapshots", headers=headers)
    assert options.status_code == 200, options.text
    assert all(item["job_id"] != unusable_job_id for item in options.json()["items"])
    response = client.post(
        f"/api/v1/council/cases/{case_id}/evidence-snapshots/{unusable_job_id}/attach",
        headers=headers,
    )
    assert response.status_code == 409, response.text


def test_run_injects_only_server_built_packet_and_preserves_case_payload(set_flags, monkeypatch) -> None:
    set_flags(council_evidence_packet_shadow_enabled=True)
    email = "snapshot-run@doctor.clara"
    headers = _login(email)
    case_id = _create_case(headers)
    job_id = _insert_completed_snapshot(email)
    assert (
        client.post(
            f"/api/v1/council/cases/{case_id}/evidence-snapshots/{job_id}/attach",
            headers=headers,
        ).status_code
        == 201
    )

    captured: dict[str, object] = {}

    def fake_proxy(_path: str, payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {
            "final_recommendation": "review with clinician",
            "emergency_escalation": {"triggered": False},
        }

    monkeypatch.setattr("clara_api.api.v1.endpoints.council.proxy_ml_post", fake_proxy)
    run = client.post(f"/api/v1/council/cases/{case_id}/run", headers=headers, json={})
    assert run.status_code == 200, run.text
    packet = captured["council_evidence_packet"]
    assert packet == {
        "tool": "retrieval_snapshot",
        "retrieval_snapshot_id": "a" * 64,
        "evidence": [
            {"evidence_id": "PMID:123456", "category": "clinical_guideline"},
            {"evidence_id": "DOI:10.1000/example", "category": "systematic_review"},
        ],
    }
    assert "sensitive research query" not in str(captured)
    assert "example.invalid" not in str(captured)

    # The persisted case request remains clinical input only, so a later read or
    # run-history snapshot does not become an alternate retrieval-content store.
    persisted_request = run.json()["request"]
    assert "council_evidence_packet" not in persisted_request
    assert set(persisted_request) == {
        "symptoms",
        "labs",
        "medications",
        "history",
        "specialist_count",
        "specialists",
    }


def test_flag_off_hides_selector_rejects_write_and_preserves_run_payload(set_flags, monkeypatch) -> None:
    set_flags(council_evidence_packet_shadow_enabled=False)
    email = "snapshot-flag-off@doctor.clara"
    headers = _login(email)
    case_id = _create_case(headers)
    job_id = _insert_completed_snapshot(email)

    assert (
        client.get(f"/api/v1/council/cases/{case_id}/evidence-snapshots", headers=headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/council/cases/{case_id}/evidence-attachments", headers=headers).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/council/cases/{case_id}/evidence-snapshots/{job_id}/attach",
            headers=headers,
        ).status_code
        == 404
    )

    captured: dict[str, object] = {}

    def fake_proxy(_path: str, payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {"final_recommendation": "review", "emergency_escalation": {"triggered": False}}

    monkeypatch.setattr("clara_api.api.v1.endpoints.council.proxy_ml_post", fake_proxy)
    response = client.post(f"/api/v1/council/cases/{case_id}/run", headers=headers, json={})
    assert response.status_code == 200, response.text
    assert "council_evidence_packet" not in captured
