import httpx
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_chat_success_proxies_request_and_role(monkeypatch) -> None:
    token = _login("alice@research.clara")
    captured: dict[str, object] = {}

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "answer": "mocked-answer",
                "role": "researcher",
                "intent": "evidence_review",
                "confidence": 0.91,
                "emergency": False,
                "model_used": "deepseek-v3.2",
                "retrieved_ids": ["doc-1"],
            }

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "metformin la gi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "mocked-answer"
    assert body["role"] == "researcher"
    assert body["intent"] == "evidence_review"
    assert body["emergency"] is False
    assert body["model_used"] == "deepseek-v3.2"
    assert body["ml"]["retrieved_ids"] == ["doc-1"]
    assert body["attribution"]["channel"] == "chat"
    assert body["attribution"]["citation_count"] == 0
    assert body["attribution"]["source_count"] >= 4

    assert str(captured["url"]).endswith("/v1/chat/routed")
    forwarded = captured["json"]
    assert isinstance(forwarded, dict)
    assert forwarded["query"] == "metformin la gi"
    assert forwarded["role"] == "researcher"
    assert forwarded["rag_flow"] == {
        "role_router_enabled": True,
        "intent_router_enabled": True,
        "verification_enabled": True,
        "deepseek_fallback_enabled": True,
        "low_context_threshold": 0.2,
        "scientific_retrieval_enabled": True,
        "web_retrieval_enabled": True,
        "file_retrieval_enabled": True,
    }
    rag_sources = forwarded["rag_sources"]
    assert isinstance(rag_sources, list)
    source_ids = {
        source["id"] for source in rag_sources if isinstance(source, dict) and "id" in source
    }
    assert {"pubmed", "rxnorm", "openfda", "davidrug"}.issubset(source_ids)
    timeout = captured["timeout"]
    assert isinstance(timeout, (int, float))  # noqa: UP038
    assert timeout > 0


def test_chat_returns_safe_fallback_when_ml_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "test"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "doctor"
    assert body["model_used"] == "api-safe-fallback-v1"
    assert "quá tải tạm thời" in body["reply"]
    assert body["ml"]["fallback_reason"].startswith("ml_unavailable:")
    assert body["attribution"]["channel"] == "chat"
    assert body["attribution"]["citation_count"] == 0
