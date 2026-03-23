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

    assert str(captured["url"]).endswith("/v1/chat/routed")
    assert captured["json"] == {"query": "metformin la gi", "role": "researcher"}
    assert float(captured["timeout"]) > 0


def test_chat_returns_502_when_ml_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "test"},
    )

    assert response.status_code == 502
    assert "ML service unavailable" in response.json()["detail"]
