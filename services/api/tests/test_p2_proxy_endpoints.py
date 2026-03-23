import httpx
import pytest
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


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
    request_payload = {"sample": "value"}
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

    response = client.post(api_path, headers={"Authorization": f"Bearer {token}"}, json=request_payload)

    assert response.status_code == 200
    assert response.json() == upstream_payload
    assert str(captured["url"]).endswith(ml_path)
    assert captured["json"] == request_payload
    assert float(captured["timeout"]) > 0


@pytest.mark.parametrize(
    ("email", "api_path"),
    [
        ("alice@research.clara", "/api/v1/research/tier2"),
        ("bob@example.com", "/api/v1/careguard/analyze"),
        ("dr@doctor.clara", "/api/v1/scribe/soap"),
    ],
)
def test_new_proxy_endpoints_return_502_when_ml_unavailable(
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
