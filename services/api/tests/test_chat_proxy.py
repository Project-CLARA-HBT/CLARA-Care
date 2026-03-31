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
    assert body["attribution"]["mode"] == "evidence_rag"
    assert body["attribution"]["citation_count"] == 0
    assert body["attribution"]["source_count"] >= 4
    assert isinstance(body["attribution"]["source_used"], list)
    assert body["attribution"]["source_errors"] == {}
    assert body["attribution"]["fallback_used"] is False
    assert isinstance(body["attributions"], list)
    assert body["attributions"][0]["channel"] == "chat"

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
    assert "không kết nối được nguồn RAG" in body["reply"]
    assert body["ml"]["fallback_reason"].startswith("ml_unavailable:")
    assert body["attribution"]["channel"] == "chat"
    assert body["attribution"]["mode"] == "safe_mode"
    assert body["attribution"]["citation_count"] == 0
    assert body["attribution"]["fallback_used"] is True
    assert isinstance(body["attributions"], list)
    assert body["attributions"][0]["channel"] == "chat"


def test_chat_returns_smalltalk_safe_fallback_for_greeting(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "hi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "doctor"
    assert body["model_used"] == "api-safe-smalltalk-v1"
    assert "chào" in body["reply"].lower()
    assert body["ml"]["fallback_reason"].startswith("ml_unavailable:")


def test_chat_recovers_with_safe_mode_retry_when_primary_5xx(monkeypatch) -> None:
    token = _login("dr@doctor.clara")
    captured_payloads: list[dict[str, object]] = []
    call_count = {"count": 0}

    class _FailingResponse:
        status_code = 503
        request = httpx.Request("POST", "http://ml/v1/chat/routed")

        @staticmethod
        def json() -> dict[str, object]:
            return {"detail": "upstream overloaded"}

    class _SafeModeRecoveredResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "answer": "safe-mode-answer",
                "role": "doctor",
                "intent": "general_guidance",
                "confidence": 0.7,
                "emergency": False,
                "model_used": "deepseek-v3.2",
                "retrieved_ids": ["local-1"],
            }

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> object:
        call_count["count"] += 1
        captured_payloads.append(json)
        if call_count["count"] == 1:
            return _FailingResponse()
        return _SafeModeRecoveredResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "toi dang uong warfarin va bi dau da day"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"].startswith("Hệ thống truy xuất chuyên sâu đang bận")
    assert body["model_used"] == "deepseek-v3.2"
    assert body["ml"]["safe_mode_used"] is True
    assert body["ml"]["fallback_reason"].startswith("ml_upstream_5xx:")
    assert call_count["count"] == 2
    assert len(captured_payloads) == 2

    second_payload = captured_payloads[1]
    second_flow = second_payload["rag_flow"]
    assert second_flow["verification_enabled"] is False
    assert second_flow["scientific_retrieval_enabled"] is False
    assert second_flow["web_retrieval_enabled"] is False
    assert second_flow["file_retrieval_enabled"] is True


def test_chat_uses_safe_mode_when_primary_ml_path_times_out(monkeypatch) -> None:
    token = _login("ops@admin.clara")
    calls: list[dict[str, object]] = []

    class _MockResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload
            self.request = httpx.Request("POST", "http://ml.test/v1/chat/routed")

        def json(self) -> dict[str, object]:
            return self._payload

    def _fake_post(url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        call_index = len(calls)
        if call_index == 1:
            raise httpx.TimeoutException("primary path timeout")
        return _MockResponse(
            200,
            {
                "answer": "Nên theo dõi triệu chứng và trao đổi bác sĩ nếu bệnh nền phức tạp.",
                "role": "admin",
                "intent": "general_guidance",
                "confidence": 0.74,
                "emergency": False,
                "model_used": "deepseek-v3.2",
                "retrieved_ids": [],
            },
        )

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "warfarin và aspirin có rủi ro gì"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_used"] == "deepseek-v3.2"
    assert "truy xuất chuyên sâu đang bận" in body["reply"].lower()
    assert "safe_mode_recovered" in str(body["ml"].get("fallback_reason", ""))
    assert body["ml"].get("safe_mode_used") is True

    assert len(calls) == 2
    safe_mode_payload = calls[1]["json"]
    assert isinstance(safe_mode_payload, dict)
    rag_flow = safe_mode_payload["rag_flow"]
    assert isinstance(rag_flow, dict)
    assert rag_flow["verification_enabled"] is False
    assert rag_flow["scientific_retrieval_enabled"] is False
    assert rag_flow["web_retrieval_enabled"] is False
    assert rag_flow["file_retrieval_enabled"] is True
