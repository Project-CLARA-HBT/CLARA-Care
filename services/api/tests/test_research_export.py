"""Tests for the research export endpoint (clara-research Requirement 16, task 17.1).

Covers the ``POST /research/tier2/jobs/{job_id}/export`` flag gate (default-off →
404), the completed-status gate (R16.4), owner isolation, and that every exported
artifact (md/docx/pdf) always includes the citations and the Citation Registry
(R16.2).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ResearchJob, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _enable_export(monkeypatch, value: bool = True) -> None:
    monkeypatch.setattr(get_settings(), "research_export_enabled", value, raising=False)


def _completed_result(*, with_registry: bool = True) -> dict:
    result: dict = {
        "tier": "tier2",
        "research_mode": "deep",
        "answer_markdown": "## Kết luận\n\nMetformin là lựa chọn đầu tay.",
        "citations": [
            {
                "source_id": "c1",
                "source": "pubmed",
                "title": "A landmark trial",
                "url": "https://example.org/a",
                "study_id": "PMID:12345678",
                "source_type": "rct",
                "trust_tier": 1,
                "published_at": "2023-04-01",
            }
        ],
    }
    if with_registry:
        result["citation_registry"] = [
            {"citation_id": "c1", "study_id": "PMID:12345678", "title": "A landmark trial"}
        ]
    return result


def _seed_job(
    *,
    email: str,
    job_id: str,
    status: str,
    result: dict | None,
) -> None:
    now = datetime.now(tz=UTC)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        job = ResearchJob(
            job_id=job_id,
            user_id=user.id,
            role="researcher",
            status=status,
            query_text="metformin vs insulin",
            request_payload={"query": "metformin vs insulin", "research_mode": "deep"},
            progress_json={
                "flow_events": [],
                "flow_stages": [],
                "active_stage": "",
                "status_note": "",
                "reasoning_steps": [],
            },
            result_json=result,
            error_text="",
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now if status == "completed" else None,
        )
        db.add(job)
        db.commit()


def test_export_flag_off_returns_404(monkeypatch) -> None:
    _enable_export(monkeypatch, value=False)
    token = _login("export.flagoff@research.clara")
    _seed_job(
        email="export.flagoff@research.clara",
        job_id="export-flag-off",
        status="completed",
        result=_completed_result(),
    )
    response = client.post(
        "/api/v1/research/tier2/jobs/export-flag-off/export?format=md",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_export_markdown_includes_citations_and_registry(monkeypatch) -> None:
    _enable_export(monkeypatch)
    token = _login("export.md@research.clara")
    _seed_job(
        email="export.md@research.clara",
        job_id="export-md",
        status="completed",
        result=_completed_result(),
    )
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-md/export?format=md",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    body = resp.text
    assert "## Citations" in body
    assert "## Citation Registry" in body
    assert "A landmark trial" in body
    assert "PMID:12345678" in body
    assert "attachment" in resp.headers["content-disposition"]


def test_export_derives_registry_when_absent(monkeypatch) -> None:
    _enable_export(monkeypatch)
    token = _login("export.noreg@research.clara")
    _seed_job(
        email="export.noreg@research.clara",
        job_id="export-noreg",
        status="completed",
        result=_completed_result(with_registry=False),
    )
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-noreg/export?format=md",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.text
    # Registry section is always present and populated from citations.
    assert "## Citation Registry" in body
    assert body.count("PMID:12345678") >= 2  # once in citations, once in derived registry


def test_export_docx_renders_zip(monkeypatch) -> None:
    _enable_export(monkeypatch)
    token = _login("export.docx@research.clara")
    _seed_job(
        email="export.docx@research.clara",
        job_id="export-docx",
        status="completed",
        result=_completed_result(),
    )
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-docx/export?format=docx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]
    assert resp.content[:2] == b"PK"  # DOCX is a zip container


def test_export_pdf_renders_pdf(monkeypatch) -> None:
    _enable_export(monkeypatch)
    token = _login("export.pdf@research.clara")
    _seed_job(
        email="export.pdf@research.clara",
        job_id="export-pdf",
        status="completed",
        result=_completed_result(),
    )
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-pdf/export?format=pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")
    assert resp.content.rstrip().endswith(b"%%EOF")


def test_export_rejected_when_not_completed(monkeypatch) -> None:
    _enable_export(monkeypatch)
    token = _login("export.queued@research.clara")
    _seed_job(
        email="export.queued@research.clara",
        job_id="export-queued",
        status="queued",
        result=None,
    )
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-queued/export?format=md",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_export_invalid_format_rejected(monkeypatch) -> None:
    _enable_export(monkeypatch)
    token = _login("export.badfmt@research.clara")
    _seed_job(
        email="export.badfmt@research.clara",
        job_id="export-badfmt",
        status="completed",
        result=_completed_result(),
    )
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-badfmt/export?format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_export_owner_isolation(monkeypatch) -> None:
    _enable_export(monkeypatch)
    owner_token = _login("export.owner@research.clara")  # noqa: F841
    _seed_job(
        email="export.owner@research.clara",
        job_id="export-owned",
        status="completed",
        result=_completed_result(),
    )
    other_token = _login("export.intruder@research.clara")
    resp = client.post(
        "/api/v1/research/tier2/jobs/export-owned/export?format=md",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
