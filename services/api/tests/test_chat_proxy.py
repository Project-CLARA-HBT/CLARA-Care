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
    assert body["fallback"] is False
    assert body.get("fallback_reason") is None
    assert isinstance(body["attributions"], list)
    assert body["attributions"][0]["channel"] == "chat"

    assert str(captured["url"]).endswith("/v1/chat/routed")
    forwarded = captured["json"]
    assert isinstance(forwarded, dict)
    assert forwarded["query"] == "metformin la gi"
    assert forwarded["role"] == "researcher"
    rag_flow = forwarded["rag_flow"]
    assert isinstance(rag_flow, dict)
    assert rag_flow["role_router_enabled"] is True
    assert rag_flow["intent_router_enabled"] is True
    assert rag_flow["rule_verification_enabled"] is True
    assert rag_flow["nli_model_enabled"] is True
    assert rag_flow["rag_reranker_enabled"] is True
    assert rag_flow["rag_nli_enabled"] is True
    assert rag_flow["rag_graphrag_enabled"] is True
    assert rag_flow["deepseek_fallback_enabled"] is False
    assert rag_flow["low_context_threshold"] == 0.2
    assert rag_flow["scientific_retrieval_enabled"] is True
    assert rag_flow["web_retrieval_enabled"] is True
    assert rag_flow["file_retrieval_enabled"] is True
    rag_sources = forwarded["rag_sources"]
    assert isinstance(rag_sources, list)
    source_ids = {
        source["id"] for source in rag_sources if isinstance(source, dict) and "id" in source
    }
    assert {"pubmed", "rxnorm", "openfda", "davidrug"}.issubset(source_ids)
    timeout = captured["timeout"]
    assert isinstance(timeout, (int, float))  # noqa: UP038
    assert timeout > 0


def test_chat_sanitizes_matrix_noise_from_reply(monkeypatch) -> None:
    token = _login("alice@research.clara")

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "answer": (
                    "## Kết luận nhanh\n"
                    "DASH và Địa Trung Hải đều hữu ích.\n\n"
                    "security\n"
                    "Ma trận quyết định an toàn\n"
                    "AI Verified\n"
                    "Claim\n"
                    "Verdict\n"
                    "Confidence\n"
                    "Hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời.\n"
                ),
                "role": "researcher",
                "intent": "evidence_review",
                "confidence": 0.88,
                "emergency": False,
                "model_used": "deepseek-v3.2",
                "retrieved_ids": ["doc-1"],
            }

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        _ = (json, timeout)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "So sánh DASH và Địa Trung Hải"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Ma trận quyết định an toàn" not in body["reply"]
    assert "AI Verified" not in body["reply"]
    assert "fallback local" not in body["reply"].lower()


def test_chat_rejects_reply_blank_after_sanitize(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "answer": "Hệ thống tạm thời dùng fallback local "
                "để đảm bảo không gián đoạn trả lời.",
                "role": "doctor",
                "intent": "general_guidance",
                "confidence": 0.7,
                "emergency": False,
                "model_used": "deepseek-v3.2",
                "retrieved_ids": [],
            }

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        _ = (json, timeout)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "help"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "deepseek_required_unavailable:blank_after_sanitize"


def test_chat_returns_503_when_ml_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "test"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "deepseek_required_unavailable:ml_unavailable:ConnectError"


def test_chat_attribution_reads_nested_retrieval_source_errors(monkeypatch) -> None:
    token = _login("alice@research.clara")

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
                "context_debug": {
                    "retrieval_trace": {
                        "search_phase": {
                            "source_errors": {"openfda": ["timeout"]},
                            "source_attempts": [{"source": "openfda"}],
                        }
                    }
                },
            }

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> _MockResponse:
        _ = (json, timeout)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "metformin la gi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attribution"]["source_errors"] == {"openfda": ["timeout"]}
    assert "openfda" in body["attribution"]["source_used"]


def test_chat_returns_503_for_greeting_when_ml_is_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "hi"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "deepseek_required_unavailable:ml_unavailable:ConnectError"


def test_chat_returns_503_when_control_tower_config_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    class _FailingControlTowerService:
        @staticmethod
        def load(_db: object) -> object:
            raise RuntimeError("db unavailable")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.chat.get_control_tower_config_service",
        lambda: _FailingControlTowerService(),
    )

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "test"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "control_tower_config_unavailable:RuntimeError"


def test_chat_does_not_retry_with_safe_mode_after_primary_5xx(monkeypatch) -> None:
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

    assert response.status_code == 503
    assert response.json()["detail"] == "deepseek_required_unavailable:ml_upstream_5xx:503"
    assert call_count["count"] == 1
    assert len(captured_payloads) == 1


def test_chat_does_not_retry_with_safe_mode_after_ml_timeout(monkeypatch) -> None:
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

    assert response.status_code == 503
    assert response.json()["detail"] == "deepseek_required_unavailable:ml_unavailable:TimeoutException"
    assert len(calls) == 1
