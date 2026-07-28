"""Phase-5 evidence question API contracts.

The router is mounted here only until the application router owns the final
integration line.  The guard keeps the test compatible with that integration.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints import evidence_questions
from clara_api.db.models import GuidelineArtifact
from clara_api.db.session import SessionLocal
from clara_api.main import app

if not any(
    getattr(route, "path", None) == "/api/v1/episodes/{episode_id}/evidence-questions"
    for route in app.routes
):
    app.include_router(evidence_questions.router, prefix="/api/v1")

client = TestClient(app)


def _headers(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _episode(headers: dict[str, str], suffix: str) -> str:
    assert (
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": f"Evidence User {suffix}"},
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": f"episode-{suffix}"},
        json={"title": "Theo dõi huyết áp"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _verified_result() -> dict:
    return {
        "quality_gate": {"passed": True},
        "citations": [
            {
                "citation_id": "c-guideline",
                "source_id": "nice-hypertension-2025",
                "source": "nice",
                "source_type": "guideline",
                "title": "Hypertension guideline",
                "url": "https://www.nice.org.uk/guidance/ng136",
                "published_at": "2025-01-01",
            },
            {
                "citation_id": "c-rct",
                "study_id": "PMID:12345678",
                "source": "pubmed",
                "source_type": "rct",
                "title": "A randomized trial",
                "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                "pmid": "12345678",
                "excerpt": "Primary-trial abstract passage.",
            },
            {
                "citation_id": "c-editorial",
                "study_id": "PMID:23456789",
                "source": "pubmed",
                "source_type": "editorial",
                "title": "Editorial context",
                "url": "https://pubmed.ncbi.nlm.nih.gov/23456789/",
            },
        ],
        "conflicting_evidence": [
            {"claim": "The optimal target differs.", "citation_ids": ["c-guideline", "c-rct"]}
        ],
    }


def test_evidence_question_requires_confirmation_then_releases_provenance_only(monkeypatch) -> None:
    suffix = uuid4().hex
    owner = _headers(f"evidence-owner-{suffix}@normal.clara")
    stranger = _headers(f"evidence-stranger-{suffix}@normal.clara")
    episode_id = _episode(owner, suffix)

    created = client.post(
        f"/api/v1/episodes/{episode_id}/evidence-questions",
        headers=owner,
        json={"question": "Điều gì có bằng chứng về kiểm soát huyết áp?"},
    )
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]
    assert created.json()["requires_confirmation"] is True
    assert client.post(
        f"/api/v1/evidence-questions/{question_id}/run",
        headers={**owner, "Idempotency-Key": f"run-{suffix}"},
    ).status_code == 409

    corrected = client.patch(
        f"/api/v1/evidence-questions/{question_id}",
        headers=owner,
        json={
            "population_context": "Người lớn có tăng huyết áp đã được xác nhận.",
            "outcomes": ["huyết áp", "biến cố tim mạch"],
            "time_horizon": "12 tháng",
            "confirmed": True,
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["confirmed"] is True

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research.research_tier2",
        lambda *_args, **_kwargs: _verified_result(),
    )
    run = client.post(
        f"/api/v1/evidence-questions/{question_id}/run",
        headers={**owner, "Idempotency-Key": f"run-{suffix}"},
    )
    assert run.status_code == 202, run.text
    assert run.json()["status"] == "running"
    assert run.json()["release_status"] == "pending"
    assert run.json()["evidence_count"] == 0
    assert "answer" not in run.json()
    run_id = run.json()["id"]

    completed = client.get(f"/api/v1/evidence-runs/{run_id}", headers=owner)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["release_status"] == "evidence_available"
    assert completed.json()["evidence_count"] == 3
    matrix = client.get(f"/api/v1/evidence-runs/{run_id}/matrix", headers=owner)
    assert matrix.status_code == 200
    assert set(matrix.json()["source_classes"]) == {
        "guideline",
        "primary_randomized_trial",
        "editorial_commentary",
    }
    rct = matrix.json()["source_classes"]["primary_randomized_trial"][0]
    assert rct["identifiers"]["pmid"] == "12345678"
    assert client.get(f"/api/v1/evidence-runs/{run_id}/applicability", headers=owner).json()[
        "status"
    ] == "not_assessed"
    assert client.get(f"/api/v1/evidence-runs/{run_id}/contradictions", headers=owner).json()[
        "status"
    ] == "reported"
    assert client.get(f"/api/v1/evidence-runs/{run_id}", headers=stranger).status_code == 404

    subscription = client.post(
        f"/api/v1/evidence-runs/{run_id}/subscribe", headers=owner, json={}
    )
    assert subscription.status_code == 201
    subscription_id = subscription.json()["id"]
    assert client.post(
        f"/api/v1/evidence-runs/{run_id}/subscribe", headers=owner, json={}
    ).json()["idempotent_replay"] is True
    assert client.delete(
        f"/api/v1/evidence-subscriptions/{subscription_id}", headers=stranger
    ).status_code == 404
    revoked = client.delete(f"/api/v1/evidence-subscriptions/{subscription_id}", headers=owner)
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert client.post(
        f"/api/v1/evidence-runs/{run_id}/subscribe", headers=owner, json={}
    ).json()["reactivated"] is True

    replay = client.post(
        f"/api/v1/evidence-questions/{question_id}/run",
        headers={**owner, "Idempotency-Key": f"run-{suffix}"},
    )
    assert replay.status_code == 202
    assert replay.json()["idempotent_replay"] is True


def test_evidence_run_abstains_when_research_falls_back(monkeypatch) -> None:
    suffix = uuid4().hex
    headers = _headers(f"evidence-fallback-{suffix}@normal.clara")
    episode_id = _episode(headers, suffix)
    question = client.post(
        f"/api/v1/episodes/{episode_id}/evidence-questions",
        headers=headers,
        json={
            "question": "Có bằng chứng nào về điều trị đau đầu kéo dài?",
            "population_context": "Người lớn.",
            "outcomes": ["giảm triệu chứng"],
            "time_horizon": "4 tuần",
            "confirmed": True,
        },
    )
    assert question.status_code == 201
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research.research_tier2",
        lambda *_args, **_kwargs: {
            "fallback": True,
            "quality_gate": {"passed": False},
            "citations": [{"source": "system_fallback", "title": "No evidence"}],
        },
    )
    run = client.post(
        f"/api/v1/evidence-questions/{question.json()['id']}/run",
        headers={**headers, "Idempotency-Key": f"fallback-{suffix}"},
    )
    assert run.status_code == 202
    assert run.json()["release_status"] == "pending"
    assert run.json()["evidence_count"] == 0
    completed = client.get(f"/api/v1/evidence-runs/{run.json()['id']}", headers=headers)
    assert completed.json()["status"] == "completed"
    assert completed.json()["release_status"] == "evidence_unavailable"
    matrix = client.get(f"/api/v1/evidence-runs/{run.json()['id']}/matrix", headers=headers)
    assert matrix.json()["source_classes"] == {}
    assert matrix.json()["unavailable_reason"]


def test_evidence_run_enqueues_once_and_worker_uses_durable_run(monkeypatch) -> None:
    suffix = uuid4().hex
    headers = _headers(f"evidence-async-{suffix}@normal.clara")
    episode_id = _episode(headers, suffix)
    question = client.post(
        f"/api/v1/episodes/{episode_id}/evidence-questions",
        headers=headers,
        json={
            "question": "Bằng chứng kiểm soát huyết áp tại nhà là gì?",
            "population_context": "Người lớn có tăng huyết áp.",
            "outcomes": ["huyết áp"],
            "time_horizon": "12 tháng",
            "confirmed": True,
        },
    )
    assert question.status_code == 201

    enqueued: list[tuple[int, dict]] = []
    worker = evidence_questions._execute_evidence_run
    monkeypatch.setattr(
        evidence_questions,
        "_execute_evidence_run",
        lambda run_id, token_data: enqueued.append((run_id, token_data)),
    )
    request_headers = {**headers, "Idempotency-Key": f"async-{suffix}"}
    started = client.post(
        f"/api/v1/evidence-questions/{question.json()['id']}/run",
        headers=request_headers,
    )
    assert started.status_code == 202
    assert started.json()["status"] == "running"
    assert started.json()["release_status"] == "pending"
    assert len(enqueued) == 1
    run_id = int(started.json()["id"])

    observed = client.get(f"/api/v1/evidence-runs/{run_id}", headers=headers)
    assert observed.status_code == 200
    assert observed.json()["status"] == "running"

    replay = client.post(
        f"/api/v1/evidence-questions/{question.json()['id']}/run",
        headers=request_headers,
    )
    assert replay.status_code == 202
    assert replay.json()["idempotent_replay"] is True
    assert len(enqueued) == 1

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research.research_tier2",
        lambda *_args, **_kwargs: _verified_result(),
    )
    # Simulate the post-response worker using only durable ID + copied auth context.
    worker(run_id, enqueued[0][1])

    completed = client.get(f"/api/v1/evidence-runs/{run_id}", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["release_status"] == "evidence_available"
    assert completed.json()["evidence_count"] == 3


def test_evidence_background_failure_is_observable(monkeypatch) -> None:
    suffix = uuid4().hex
    headers = _headers(f"evidence-worker-failure-{suffix}@normal.clara")
    episode_id = _episode(headers, suffix)
    question = client.post(
        f"/api/v1/episodes/{episode_id}/evidence-questions",
        headers=headers,
        json={
            "question": "Bằng chứng nào phù hợp cho theo dõi triệu chứng?",
            "population_context": "Người lớn.",
            "outcomes": ["triệu chứng"],
            "time_horizon": "4 tuần",
            "confirmed": True,
        },
    )
    assert question.status_code == 201
    captured: list[tuple[int, dict]] = []
    worker = evidence_questions._execute_evidence_run
    monkeypatch.setattr(
        evidence_questions,
        "_execute_evidence_run",
        lambda run_id, token_data: captured.append((run_id, token_data)),
    )
    started = client.post(
        f"/api/v1/evidence-questions/{question.json()['id']}/run",
        headers={**headers, "Idempotency-Key": f"worker-failure-{suffix}"},
    )
    assert started.status_code == 202
    run_id = int(started.json()["id"])
    token_data = captured[0][1]

    def _fail(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research.research_tier2",
        _fail,
    )
    worker(run_id, token_data)
    failed = client.get(f"/api/v1/evidence-runs/{run_id}", headers=headers)
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["release_status"] == "evidence_unavailable"
    assert failed.json()["evidence_count"] == 0


def test_guideline_artifact_only_exposes_curator_published_rows() -> None:
    headers = _headers(f"guideline-reader-{uuid4().hex}@normal.clara")
    with SessionLocal() as db:
        draft = GuidelineArtifact(
            title="Draft guideline",
            source_provider="nice",
            source_url="https://www.nice.org.uk/guidance/ng136",
            intended_population_json={"age": "adult"},
            action_options_json={"actions": ["discuss care"]},
            content_json={"summary": "draft"},
            status="draft",
        )
        published = GuidelineArtifact(
            title="Published hypertension guideline",
            source_provider="nice",
            source_url="https://www.nice.org.uk/guidance/ng136",
            source_section="Recommendations",
            jurisdiction="UK",
            version="2025.1",
            intended_population_json={"age": "adult"},
            eligibility_logic_json={"status": "validated", "expression": "age >= 18"},
            action_options_json={"actions": ["discuss with clinician"]},
            certainty="moderate",
            content_json={"summary": "Curated source text."},
            status="published",
        )
        db.add_all([draft, published])
        db.commit()
        db.refresh(draft)
        db.refresh(published)
        draft_id, published_id = draft.id, published.id

    assert client.get(f"/api/v1/guideline-artifacts/{draft_id}", headers=headers).status_code == 404
    response = client.get(f"/api/v1/guideline-artifacts/{published_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["provenance"]["source_provider"] == "nice"
    assert response.json()["eligibility_logic"]["status"] == "validated"
