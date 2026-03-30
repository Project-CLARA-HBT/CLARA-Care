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

    response = client.post(
        api_path,
        headers={"Authorization": f"Bearer {token}"},
        json=request_payload,
    )

    assert response.status_code == 200
    assert response.json() == upstream_payload
    assert str(captured["url"]).endswith(ml_path)
    expected_payload = dict(request_payload)
    if api_path == "/api/v1/research/tier2":
        expected_payload["role"] = "researcher"
    assert captured["json"] == expected_payload
    assert float(captured["timeout"]) > 0


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
    assert response.json() == {"ok": True}
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
    assert payload["metadata"] == {}
    assert payload["citations"] == []
    assert payload["fallback_reason"] == "ConnectError"
    assert call_count["count"] == 2
