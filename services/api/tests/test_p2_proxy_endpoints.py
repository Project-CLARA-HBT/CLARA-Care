import json
import threading
import time
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from clara_api.db.models import ResearchJob, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5'\xd4\xa2"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _minimal_progress(now: datetime) -> dict[str, object]:
    return {
        "flow_events": [
            {
                "id": "evt-1",
                "stage": "final_response",
                "status": "completed",
                "note": "done",
                "timestamp": now.isoformat(),
            }
        ],
        "flow_stages": [
            {
                "id": "final_response",
                "label": "Final Response",
                "status": "completed",
                "detail": "done",
                "source": "flow_events",
            }
        ],
        "active_stage": "final_response",
        "status_note": "done",
        "reasoning_steps": [],
    }


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


@pytest.mark.parametrize(
    ("email", "api_path", "ml_path"),
    [
        ("alice@research.clara", "/api/v1/research/tier2", "/v1/research/tier2"),
        ("bob@example.com", "/api/v1/careguard/analyze", "/v1/careguard/analyze"),
        ("dr@doctor.clara", "/api/v1/scribe/soap", "/v1/scribe/soap"),
    ],
)
def test_new_proxy_endpoints_success(
    monkeypatch: pytest.MonkeyPatch,
    email: str,
    api_path: str,
    ml_path: str,
) -> None:
    token = _login(email)
    captured: dict[str, object] = {}
    request_payload: dict[str, object] = {"sample": "value"}
    upstream_payload = {"ok": True, "endpoint": ml_path}

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return upstream_payload

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        api_path,
        headers={"Authorization": f"Bearer {token}"},
        json=request_payload,
    )

    assert response.status_code == 200
    response_payload = response.json()
    if api_path == "/api/v1/careguard/analyze":
        assert response_payload["ok"] is True
        assert response_payload["endpoint"] == ml_path
        assert response_payload["attribution"]["channel"] == "careguard"
        assert response_payload["attribution"]["mode"] == "local_only"
        assert isinstance(response_payload["attributions"], list)
        assert response_payload["attributions"][0]["channel"] == "careguard"
    elif api_path == "/api/v1/research/tier2":
        assert response_payload["ok"] is True
        assert response_payload["attribution"]["channel"] == "research"
        assert response_payload["attribution"]["mode"] == "fast"
        assert response_payload["attribution"]["citation_count"] == 0
        assert isinstance(response_payload["attribution"]["source_used"], list)
        assert response_payload["attribution"]["source_errors"] == {}
        assert response_payload["attribution"]["fallback_used"] is False
        assert isinstance(response_payload["attributions"], list)
        assert response_payload["attributions"][0]["channel"] == "research"
    else:
        assert response_payload == upstream_payload
    assert str(captured["url"]).endswith(ml_path)
    expected_payload = dict(request_payload)
    if api_path == "/api/v1/research/tier2":
        expected_payload["role"] = "researcher"
        expected_payload["answer_format"] = "markdown"
        expected_payload["response_format"] = "markdown"
        expected_payload["render_hints"] = {
            "markdown": True,
            "tables": True,
            "mermaid": True,
            "chart_spec_fences": [
                "chart-spec",
                "vega-lite",
                "echarts-option",
                "json",
                "yaml",
            ],
        }
    if api_path == "/api/v1/careguard/analyze":
        expected_payload["external_ddi_enabled"] = False
    forwarded_payload = captured["json"]
    assert isinstance(forwarded_payload, dict)
    for key, value in expected_payload.items():
        assert forwarded_payload.get(key) == value
    if api_path == "/api/v1/research/tier2":
        assert isinstance(forwarded_payload.get("rag_flow"), dict)
        assert isinstance(forwarded_payload.get("rag_sources"), list)
        assert len(forwarded_payload["rag_sources"]) >= 1
    timeout = captured["timeout"]
    assert isinstance(timeout, (int, float))  # noqa: UP038
    assert timeout > 0


@pytest.mark.parametrize(
    ("email", "api_path"),
    [
        ("bob@example.com", "/api/v1/careguard/analyze"),
        ("dr@doctor.clara", "/api/v1/scribe/soap"),
    ],
)
def test_non_research_proxy_endpoints_return_502_when_ml_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    email: str,
    api_path: str,
) -> None:
    token = _login(email)

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        api_path,
        headers={"Authorization": f"Bearer {token}"},
        json={"sample": "value"},
    )

    assert response.status_code == 502
    assert "ML service unavailable" in response.json()["detail"]


def test_research_upload_file_returns_file_id_and_preview() -> None:
    token = _login("alice@research.clara")

    response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("note.txt", b"metformin and lisinopril", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("file_id"), str)
    assert payload["metadata"]["filename"] == "note.txt"
    assert payload["metadata"]["size"] == len(b"metformin and lisinopril")
    assert "metformin" in payload["preview"]
    assert payload["token_count"] > 0


def test_research_attribution_respects_canonical_fallback_used(monkeypatch) -> None:
    token = _login("alice@research.clara")

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "tier": "tier2",
                "answer": "fallback answer",
                "fallback_used": True,
                "source_used": "pubmed,openfda",
                "source_errors": {"openfda": ["timeout"]},
                "metadata": {},
            }

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        _ = (json, timeout)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "test fallback attribution"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attribution"]["fallback_used"] is True
    assert body["attribution"]["source_used"] == ["pubmed", "openfda"]
    assert body["attribution"]["source_errors"] == {"openfda": ["timeout"]}
    assert isinstance(body["attributions"], list)
    assert body["attributions"][0] == body["attribution"]


def test_research_upload_file_json_is_parsed_as_text() -> None:
    token = _login("alice@research.clara")

    response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "medication.json",
                b'{"drug":"metformin","dose":"500mg","with_food":true}',
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert '"drug": "metformin"' in payload["preview"]
    assert payload["token_count"] > 0


def test_research_upload_file_image_returns_soft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _login("alice@research.clara")
    monkeypatch.setenv("RESEARCH_UPLOAD_IMAGE_OCR", "1")

    def _fake_scan_with_tgc_ocr(
        *,
        file_bytes: bytes,
        file_name: str,
        content_type: str,
    ) -> tuple[str, str, str]:
        _ = (file_bytes, file_name, content_type)
        raise HTTPException(status_code=502, detail="Không kết nối được OCR service")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard._scan_with_tgc_ocr",
        _fake_scan_with_tgc_ocr,
    )

    response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("scan.png", _TINY_PNG, "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "ocr" in payload["preview"].lower()
    assert payload["token_count"] == 0


def test_research_upload_file_image_uses_internal_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _login("alice@research.clara")
    monkeypatch.setenv("RESEARCH_UPLOAD_IMAGE_OCR", "1")

    def _fake_scan_with_tgc_ocr(
        *,
        file_bytes: bytes,
        file_name: str,
        content_type: str,
    ) -> tuple[str, str, str]:
        _ = (file_bytes, file_name, content_type)
        return "Aspirin 81mg", "/ocr", "tgc-transhub"

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.careguard._scan_with_tgc_ocr",
        _fake_scan_with_tgc_ocr,
    )

    response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("scan.png", _TINY_PNG, "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "aspirin 81mg" in payload["preview"].lower()
    assert payload["token_count"] > 0


def test_research_upload_file_pdf_uses_parsed_text(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _login("alice@research.clara")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._extract_pdf_text",
        lambda _file_bytes: ("Clinical summary: metformin maintenance.", ""),
    )

    response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("clinical-note.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "metformin" in payload["preview"].lower()
    assert payload["token_count"] > 0


def test_research_tier2_forwards_uploaded_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _login("alice@research.clara")

    upload_response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("clinical-note.txt", b"Patient uses metformin", "text/plain")},
    )
    assert upload_response.status_code == 200
    file_id = upload_response.json()["file_id"]

    captured: dict[str, object] = {}

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"ok": True}

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    request_payload = {
        "question": "drug interactions",
        "source_mode": "uploaded_files",
        "uploaded_file_ids": [file_id],
    }
    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json=request_payload,
    )

    assert response.status_code == 200
    response_payload = response.json()
    assert response_payload["ok"] is True
    assert response_payload["attribution"]["channel"] == "research"
    assert isinstance(response_payload["attributions"], list)
    assert isinstance(response_payload["attribution"]["source_used"], list)
    assert str(captured["url"]).endswith("/v1/research/tier2")

    forwarded_payload = captured["json"]
    assert isinstance(forwarded_payload, dict)
    assert forwarded_payload["source_mode"] == "uploaded_files"
    assert isinstance(forwarded_payload.get("uploaded_documents"), list)
    assert len(forwarded_payload["uploaded_documents"]) == 1
    uploaded_document = forwarded_payload["uploaded_documents"][0]
    assert uploaded_document["file_id"] == file_id
    assert uploaded_document["filename"] == "clinical-note.txt"
    assert "metformin" in uploaded_document["text"]


def test_research_tier2_job_create_and_get(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _login("alice@research.clara")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._queue_research_job",
        lambda _job_id: None,
    )

    create_response = client.post(
        "/api/v1/research/tier2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Tương tác Warfarin với thuốc giảm đau phổ biến",
            "research_mode": "deep",
            "source_hub_sources": ["pubmed", "europepmc"],
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert isinstance(payload.get("job_id"), str)
    assert payload.get("status") in {"queued", "running", "completed"}
    assert payload.get("query") == "Tương tác Warfarin với thuốc giảm đau phổ biến"
    assert isinstance(payload.get("progress"), dict)

    job_id = payload["job_id"]
    get_response = client.get(
        f"/api/v1/research/tier2/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["job_id"] == job_id
    assert fetched["query"] == payload["query"]


def test_research_tier2_job_create_accepts_deep_beta_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._queue_research_job",
        lambda _job_id: None,
    )

    create_response = client.post(
        "/api/v1/research/tier2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Deep beta mode persistence",
            "research_mode": "deep_beta",
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    job_id = payload["job_id"]

    with SessionLocal() as db:
        row = db.query(ResearchJob).filter(ResearchJob.job_id == job_id).first()
        assert row is not None
        assert isinstance(row.request_payload, dict)
        assert row.request_payload["research_mode"] == "deep_beta"


def test_research_tier2_job_create_forwards_full_retrieval_stack_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._queue_research_job",
        lambda _job_id: None,
    )

    create_response = client.post(
        "/api/v1/research/tier2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Persist retrieval full mode",
            "stack_mode": "full",
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    job_id = payload["job_id"]

    with SessionLocal() as db:
        row = db.query(ResearchJob).filter(ResearchJob.job_id == job_id).first()
        assert row is not None
        assert isinstance(row.request_payload, dict)
        assert row.request_payload["retrieval_stack_mode"] == "full"
        assert "stack_mode" not in row.request_payload


def test_research_tier2_job_get_404_for_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    token_a = _login("alice@research.clara")
    token_b = _login("bob@example.com")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._queue_research_job",
        lambda _job_id: None,
    )

    create_response = client.post(
        "/api/v1/research/tier2/jobs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"query": "test isolation"},
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["job_id"]

    other_user_response = client.get(
        f"/api/v1/research/tier2/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_user_response.status_code == 404


def test_research_tier2_job_stream_returns_progress_and_done() -> None:
    token = _login("alice@research.clara")
    now = datetime.now(tz=UTC)

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "alice@research.clara").first()
        assert user is not None
        job = ResearchJob(
            job_id="stream-test-job-1",
            user_id=user.id,
            role="researcher",
            status="completed",
            query_text="stream test",
            request_payload={"query": "stream test"},
            progress_json={
                "flow_events": [
                    {
                        "id": "evt-1",
                        "stage": "collect_evidence",
                        "status": "in_progress",
                        "note": "Đang truy xuất nguồn.",
                        "timestamp": now.isoformat(),
                    }
                ],
                "flow_stages": [
                    {
                        "id": "collect_evidence",
                        "label": "Collect Evidence",
                        "status": "in_progress",
                        "detail": "Đang truy xuất nguồn.",
                        "source": "flow_events",
                    }
                ],
                "active_stage": "collect_evidence",
                "status_note": "Đang truy xuất nguồn.",
                "reasoning_steps": [],
            },
            result_json={"answer": "ok", "metadata": {"research_mode": "fast"}},
            error_text="",
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
        )
        db.add(job)
        db.commit()

    with client.stream(
        "GET",
        "/api/v1/research/tier2/jobs/stream-test-job-1/stream",
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        assert response.status_code == 200
        body = ""
        for chunk in response.iter_text():
            body += chunk

    assert "event: progress" in body
    assert "event: done" in body
    data_lines = [
        line[len("data: ") :]
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert data_lines
    parsed_payloads = []
    for raw in data_lines:
        parsed_payloads.append(json.loads(raw))
    assert any(payload.get("job_id") == "stream-test-job-1" for payload in parsed_payloads)


def test_research_tier2_job_stream_reflects_external_job_updates() -> None:
    token = _login("alice@research.clara")
    now = datetime.now(tz=UTC)
    job_id = "stream-test-job-live-update"

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "alice@research.clara").first()
        assert user is not None
        job = ResearchJob(
            job_id=job_id,
            user_id=user.id,
            role="researcher",
            status="running",
            query_text="stream update test",
            request_payload={"query": "stream update test"},
            progress_json={
                "flow_events": [
                    {
                        "id": "evt-init",
                        "stage": "dispatch_ml",
                        "status": "in_progress",
                        "note": "Đã gửi yêu cầu lên ML service.",
                        "timestamp": now.isoformat(),
                    }
                ],
                "flow_stages": [
                    {
                        "id": "dispatch_ml",
                        "label": "Dispatch Ml",
                        "status": "in_progress",
                        "detail": "Đã gửi yêu cầu lên ML service.",
                        "source": "flow_events",
                    }
                ],
                "active_stage": "dispatch_ml",
                "status_note": "Đã gửi yêu cầu lên ML service.",
                "reasoning_steps": [],
            },
            result_json=None,
            error_text="",
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=None,
        )
        db.add(job)
        db.commit()

    def _complete_job_later() -> None:
        time.sleep(0.8)
        with SessionLocal() as db:
            row = db.query(ResearchJob).filter(ResearchJob.job_id == job_id).first()
            assert row is not None
            row.status = "completed"
            row.completed_at = datetime.now(tz=UTC)
            row.updated_at = datetime.now(tz=UTC)
            row.result_json = {"answer": "done", "metadata": {"research_mode": "fast"}}
            row.progress_json = {
                "flow_events": [
                    {
                        "id": "evt-init",
                        "stage": "dispatch_ml",
                        "status": "in_progress",
                        "note": "Đã gửi yêu cầu lên ML service.",
                        "timestamp": now.isoformat(),
                    },
                    {
                        "id": "evt-done",
                        "stage": "final_response",
                        "status": "completed",
                        "note": "Đã hoàn tất trả lời.",
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    },
                ],
                "flow_stages": [
                    {
                        "id": "dispatch_ml",
                        "label": "Dispatch Ml",
                        "status": "completed",
                        "detail": "Đã gửi yêu cầu lên ML service.",
                        "source": "flow_events",
                    },
                    {
                        "id": "final_response",
                        "label": "Final Response",
                        "status": "completed",
                        "detail": "Đã hoàn tất trả lời.",
                        "source": "flow_events",
                    },
                ],
                "active_stage": "final_response",
                "status_note": "Đã hoàn tất trả lời.",
                "reasoning_steps": [],
            }
            db.add(row)
            db.commit()

    worker = threading.Thread(target=_complete_job_later, daemon=True)
    worker.start()

    with client.stream(
        "GET",
        f"/api/v1/research/tier2/jobs/{job_id}/stream?poll_interval_seconds=0.3&heartbeat_seconds=5",
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        assert response.status_code == 200
        body = ""
        for chunk in response.iter_text():
            body += chunk
            if "event: done" in body:
                break

    worker.join(timeout=3.0)
    assert "event: progress" in body
    assert "event: done" in body
    assert '"status": "completed"' in body or '"status":"completed"' in body


def test_research_tier2_job_stream_surfaces_deep_beta_result_mode() -> None:
    token = _login("alice@research.clara")
    now = datetime.now(tz=UTC)

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "alice@research.clara").first()
        assert user is not None
        job = ResearchJob(
            job_id="stream-test-job-deep-beta",
            user_id=user.id,
            role="researcher",
            status="completed",
            query_text="stream deep beta",
            request_payload={"query": "stream deep beta", "research_mode": "deep_beta"},
            progress_json=_minimal_progress(now),
            result_json={"answer": "ok", "metadata": {"research_mode": "deep_beta"}},
            error_text="",
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
        )
        db.add(job)
        db.commit()

    with client.stream(
        "GET",
        "/api/v1/research/tier2/jobs/stream-test-job-deep-beta/stream",
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        assert response.status_code == 200
        body = ""
        for chunk in response.iter_text():
            body += chunk

    data_lines = [line[len("data: ") :] for line in body.splitlines() if line.startswith("data: ")]
    assert data_lines
    payloads = [json.loads(raw) for raw in data_lines]
    done_payload = payloads[-1]
    result_payload = done_payload.get("result") or {}
    metadata_payload = result_payload.get("metadata") if isinstance(result_payload, dict) else {}
    assert metadata_payload["research_mode"] == "deep_beta"


def test_research_tier2_returns_fail_soft_payload_with_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")
    call_count = {"count": 0}

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        call_count["count"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "summary", "source_mode": "uploaded_files", "uploaded_file_ids": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] is True
    assert payload["metadata"]["research_mode"] == "fast"
    assert payload["metadata"]["deep_pass_count"] == 0
    assert payload["citations"] == []
    assert payload["fallback_reason"] == "ConnectError"
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["fallback_used"] is True
    assert payload["attribution"]["mode"] == "fast"
    assert call_count["count"] == 2


def test_research_tier2_fail_soft_keeps_deep_mode_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")
    call_count = {"count": 0}

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        call_count["count"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "deep mode fail soft",
            "research_mode": "deep",
            "retrieval_stack_mode": "full",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] is True
    assert payload["research_mode"] == "deep"
    assert payload["retrieval_stack_mode"] == "full"
    assert payload["deep_pass_count"] == 0
    assert payload["metadata"]["research_mode"] == "deep"
    assert payload["metadata"]["retrieval_stack_mode"] == "full"
    assert payload["metadata"]["deep_pass_count"] == 0
    assert payload["fallback_reason"] == "ConnectError"
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["fallback_used"] is True
    assert payload["attribution"]["mode"] == "deep"
    assert call_count["count"] == 2


def test_research_tier2_fail_soft_keeps_deep_beta_mode_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")
    call_count = {"count": 0}

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        call_count["count"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "deep beta fail soft", "research_mode": "deep_beta"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] is True
    assert payload["research_mode"] == "deep_beta"
    assert payload["deep_pass_count"] == 0
    assert payload["metadata"]["research_mode"] == "deep_beta"
    assert payload["metadata"]["deep_pass_count"] == 0
    assert payload["fallback_reason"] == "ConnectError"
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["fallback_used"] is True
    assert payload["attribution"]["mode"] == "deep_beta"
    assert call_count["count"] == 2


def test_research_tier2_forwards_research_mode_to_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")
    captured: dict[str, object] = {}

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"answer": "ok", "metadata": {"research_mode": "deep", "deep_pass_count": 2}}

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "deep reasoning test", "research_mode": "deep"},
    )

    assert response.status_code == 200
    assert str(captured["url"]).endswith("/v1/research/tier2")
    forwarded = captured["json"]
    assert isinstance(forwarded, dict)
    assert forwarded["research_mode"] == "deep"
    assert forwarded["role"] == "researcher"
    assert forwarded["strict_deepseek_required"] is False
    assert isinstance(forwarded.get("rag_flow"), dict)
    assert isinstance(forwarded.get("rag_sources"), list)


def test_research_tier2_forwards_deep_beta_mode_to_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")
    captured: dict[str, object] = {}

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"answer": "ok", "metadata": {"research_mode": "deep_beta", "deep_pass_count": 1}}

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "deep beta reasoning test", "research_mode": "deep_beta"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["research_mode"] == "deep_beta"
    assert payload["attribution"]["mode"] == "deep_beta"
    assert str(captured["url"]).endswith("/v1/research/tier2")
    forwarded = captured["json"]
    assert isinstance(forwarded, dict)
    assert forwarded["research_mode"] == "deep_beta"
    assert forwarded["role"] == "researcher"


def test_research_tier2_forwards_full_retrieval_stack_mode_to_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")
    captured: dict[str, object] = {}

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"answer": "ok", "metadata": {"research_mode": "fast"}}

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "stack mode full test", "stack_mode": "full"},
    )

    assert response.status_code == 200
    assert str(captured["url"]).endswith("/v1/research/tier2")
    forwarded = captured["json"]
    assert isinstance(forwarded, dict)
    assert forwarded["retrieval_stack_mode"] == "full"
    assert "stack_mode" not in forwarded


def test_research_tier2_normalize_preserves_new_telemetry_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")

    upstream_payload = {
        "answer": "ok",
        "metadata": {
            "research_mode": "deep",
            "deep_pass_count": 2,
            "flow_events": [
                {
                    "stage": "deep_retrieval_pass",
                    "status": "completed",
                    "payload": {"docs_found": ["doc-a"], "source_errors": {"openfda": ["timeout"]}},
                },
                {"stage": "answer_synthesis", "status": "completed"},
            ],
            "telemetry": {
                "research_mode": "deep",
                "search_plan": {
                    "query": "normalize telemetry contract",
                    "query_terms": ["normalize", "telemetry", "contract"],
                    "top_k": 5,
                },
                "source_attempts": [
                    {"source": "pubmed", "status": "completed", "attempt": 1},
                    {"source": "openfda", "status": "timeout", "attempt": 1},
                ],
                "index_summary": {
                    "indexed_docs": 14,
                    "selected_docs": 5,
                    "selected_sources": {"pubmed": 3, "dailymed": 2},
                },
                "custom_field": {"keep": True},
                "crawl_summary": {"pages_requested": 3, "pages_crawled": 2, "domains": ["nih.gov"]},
            },
            "context_debug": {
                "retrieval_trace": {"retrieved_count": 5},
                "source_errors": {"openfda": ["timeout"]},
            },
        },
    }

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return upstream_payload

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "normalize telemetry contract", "research_mode": "deep"},
    )

    assert response.status_code == 200
    payload = response.json()
    telemetry = payload["telemetry"]
    assert telemetry["research_mode"] == "deep"
    assert telemetry["search_plan"]["query_terms"] == ["normalize", "telemetry", "contract"]
    assert telemetry["query_plan"]["query_terms"] == ["normalize", "telemetry", "contract"]
    assert telemetry["source_attempts"][1]["source"] == "openfda"
    assert telemetry["index_summary"]["indexed_docs"] == 14
    assert telemetry["index_summary"]["selected_docs"] == 5
    assert telemetry["crawl_summary"]["pages_crawled"] == 2
    assert telemetry["custom_field"] == {"keep": True}
    assert payload["query_plan"]["query_terms"] == ["normalize", "telemetry", "contract"]
    assert payload["search_plan"]["query_terms"] == ["normalize", "telemetry", "contract"]
    assert payload["source_attempts"][1]["source"] == "openfda"
    assert payload["source_errors"] == {"openfda": ["timeout"]}
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["mode"] == "deep"
    assert payload["attribution"]["source_errors"] == {"openfda": ["timeout"]}
    assert set(payload["attribution"]["source_used"]) >= {"pubmed", "openfda"}
    assert isinstance(payload["attributions"], list)
    assert payload["attributions"][0] == payload["attribution"]
    assert isinstance(payload.get("flow_events"), list)
    assert payload["flow_events"][0]["stage"] == "deep_retrieval_pass"


def test_research_tier2_exposes_telemetry_details_from_context_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")

    upstream_payload = {
        "answer": "ok",
        "metadata": {
            "context_debug": {
                "query_keywords": ["warfarin", "ibuprofen"],
                "retrieved_context": [
                    {
                        "id": "doc-1",
                        "source": "pubmed",
                        "score": 0.91,
                        "reasoning": "Matched DDI keyword overlap",
                    }
                ],
                "score_breakdown": {
                    "relevance": 0.91,
                    "coverage": 0.73,
                },
                "source_reasoning": [
                    {
                        "source": "pubmed",
                        "reasoning": "High confidence RCT source",
                        "score": 0.91,
                    }
                ],
                "source_errors": {"openfda": ["timeout"]},
            }
        },
    }

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return upstream_payload

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "warfarin ibuprofen ddi"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["context_debug"]["query_keywords"] == ["warfarin", "ibuprofen"]
    assert payload["source_errors"] == {"openfda": ["timeout"]}

    telemetry = payload["telemetry"]
    assert telemetry["keywords"] == ["warfarin", "ibuprofen"]
    assert telemetry["docs"][0]["id"] == "doc-1"
    assert telemetry["scores"]["relevance"] == 0.91
    assert telemetry["source_reasoning"][0]["source"] == "pubmed"
    assert telemetry["errors"] == {"openfda": ["timeout"]}
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["source_errors"] == {"openfda": ["timeout"]}


def test_research_tier2_promotes_verification_matrix_and_trace_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")

    upstream_payload = {
        "answer": "ok",
        "metadata": {
            "telemetry": {
                "query_plan": {
                    "query": "warfarin ibuprofen bleeding risk",
                    "top_k": 5,
                },
                "source_attempts": [
                    {"source": "pubmed", "status": "completed"},
                    {"source": "openfda", "status": "timeout"},
                ],
                "source_errors": {"openfda": ["timeout"]},
                "verification_matrix": [
                    {
                        "claim": "Warfarin + ibuprofen increases bleeding risk.",
                        "verdict": "supported",
                        "confidence": 0.96,
                        "evidence": ["pubmed:123456"],
                    }
                ],
                "contradiction_summary": {
                    "has_contradiction": True,
                    "count": 1,
                    "summary": "Risk magnitude differs by dose and duration.",
                },
                "trace_metadata": {
                    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                    "span_id": "00f067aa0ba902b7",
                    "traceparent": (
                        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
                    ),
                },
            },
            "context_debug": {
                "retrieval_trace": {
                    "otel_trace_context": {
                        "trace_flags": "01",
                        "sampled": True,
                    }
                }
            },
        },
    }

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return upstream_payload

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        _ = (json, timeout)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "warfarin ibuprofen bleeding risk", "research_mode": "deep"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["query_plan"]["query"] == "warfarin ibuprofen bleeding risk"
    assert payload["source_attempts"][0]["source"] == "pubmed"
    assert payload["source_errors"] == {"openfda": ["timeout"]}

    assert payload["verification_matrix"][0]["verdict"] == "supported"
    assert payload["contradiction_summary"]["count"] == 1
    assert payload["trace_metadata"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert payload["trace_metadata"]["span_id"] == "00f067aa0ba902b7"
    assert payload["trace_metadata"]["trace_flags"] == "01"
    assert payload["trace_metadata"]["sampled"] is True

    telemetry = payload["telemetry"]
    assert telemetry["verification_matrix"][0]["claim"].startswith("Warfarin + ibuprofen")
    assert telemetry["contradiction_summary"]["has_contradiction"] is True
    assert telemetry["trace_metadata"]["traceparent"].startswith("00-4bf92f3577b34da6")


def test_research_tier2_promotes_new_metadata_contract_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _login("alice@research.clara")

    upstream_payload = {
        "answer": "ok",
        "metadata": {
            "research_mode": "deep",
            "query_plan": {
                "query": "warfarin ibuprofen",
                "query_terms": ["warfarin", "ibuprofen"],
                "top_k": 6,
            },
            "source_attempts": [
                {"source": "pubmed", "status": "completed", "attempt": 1},
                {"provider": "openfda", "status": "timeout", "attempt": 1},
            ],
            "source_errors": {"openfda": "timeout"},
            "fallback_reason": "upstream_timeout",
        },
    }

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return upstream_payload

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        _ = (json, timeout)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/research/tier2",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "warfarin ibuprofen", "research_mode": "deep"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_reason"] == "upstream_timeout"
    assert payload["query_plan"]["query_terms"] == ["warfarin", "ibuprofen"]
    assert payload["search_plan"]["query_terms"] == ["warfarin", "ibuprofen"]
    assert payload["source_attempts"][1]["provider"] == "openfda"
    assert payload["source_errors"] == {"openfda": ["timeout"]}
    assert payload["fallback"] is True

    telemetry = payload["telemetry"]
    assert telemetry["query_plan"]["query_terms"] == ["warfarin", "ibuprofen"]
    assert telemetry["search_plan"]["query_terms"] == ["warfarin", "ibuprofen"]
    assert telemetry["source_attempts"][0]["source"] == "pubmed"

    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["mode"] == "deep"
    assert payload["attribution"]["fallback_used"] is True
    assert payload["attribution"]["source_errors"] == {"openfda": ["timeout"]}
    assert set(payload["attribution"]["source_used"]) >= {"pubmed", "openfda"}
    assert isinstance(payload["attributions"], list)
    assert payload["attributions"][0] == payload["attribution"]
