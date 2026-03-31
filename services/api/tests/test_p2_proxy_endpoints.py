import httpx
import pytest
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


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


def test_research_upload_file_image_returns_soft_preview() -> None:
    token = _login("alice@research.clara")

    response = client.post(
        "/api/v1/research/upload-file",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "parse sâu" in payload["preview"].lower()
    assert payload["token_count"] == 0


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
        json={"query": "deep mode fail soft", "research_mode": "deep"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] is True
    assert payload["research_mode"] == "deep"
    assert payload["deep_pass_count"] == 0
    assert payload["metadata"]["research_mode"] == "deep"
    assert payload["metadata"]["deep_pass_count"] == 0
    assert payload["fallback_reason"] == "ConnectError"
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["fallback_used"] is True
    assert payload["attribution"]["mode"] == "deep"
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
    assert isinstance(forwarded.get("rag_flow"), dict)
    assert isinstance(forwarded.get("rag_sources"), list)


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
    assert telemetry["source_attempts"][1]["source"] == "openfda"
    assert telemetry["index_summary"]["indexed_docs"] == 14
    assert telemetry["index_summary"]["selected_docs"] == 5
    assert telemetry["crawl_summary"]["pages_crawled"] == 2
    assert telemetry["custom_field"] == {"keep": True}
    assert payload["source_errors"] == {"openfda": ["timeout"]}
    assert payload["attribution"]["channel"] == "research"
    assert payload["attribution"]["mode"] == "deep"
    assert payload["attribution"]["source_errors"] == {"openfda": ["timeout"]}
    assert set(payload["attribution"]["source_used"]) >= {"pubmed", "openfda"}
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
