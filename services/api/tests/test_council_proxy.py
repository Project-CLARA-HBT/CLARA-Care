from typing import Any

import httpx
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_council_run_success(monkeypatch) -> None:
    token = _login("dr@doctor.clara")
    captured: dict[str, object] = {}
    request_payload = {
        "symptoms": ["polypharmacy", "fatigue"],
        "labs": {"creatinine": 1.2},
        "medications": ["warfarin"],
        "history": "htn",
        "specialist_count": 2,
        "specialists": ["pharmacology", "nephrology"],
    }
    upstream_payload = {"ok": True, "recommendation": "Review contraindications"}

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
        "/api/v1/council/run",
        headers={"Authorization": f"Bearer {token}"},
        json=request_payload,
    )

    assert response.status_code == 200
    assert response.json() == upstream_payload
    assert str(captured["url"]).endswith("/v1/council/run")
    assert captured["json"] == request_payload
    assert float(captured["timeout"]) > 0


def test_council_run_returns_502_when_ml_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.ml_proxy.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/council/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "symptoms": ["polypharmacy"],
            "labs": {},
            "medications": [],
            "history": "",
            "specialist_count": 2,
            "specialists": ["pharmacology", "nephrology"],
        },
    )

    assert response.status_code == 502
    assert "ML service unavailable" in response.json()["detail"]


def test_council_run_forbidden_for_non_doctor() -> None:
    token = _login("alice@research.clara")

    response = client.post(
        "/api/v1/council/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "symptoms": ["polypharmacy"],
            "labs": {},
            "medications": [],
            "history": "",
            "specialist_count": 2,
            "specialists": ["pharmacology", "nephrology"],
        },
    )

    assert response.status_code == 403


def test_council_intake_success(monkeypatch) -> None:
    token = _login("dr@doctor.clara")
    captured: dict[str, Any] = {}
    upstream_payload = {
        "transcript": "bn đau đầu",
        "normalized": {
            "symptoms": ["đau đầu"],
            "labs": {},
            "medications": [],
            "history": [],
        },
        "text_fields": {
            "symptoms_input": "đau đầu",
            "labs_input": "",
            "medications_input": "",
            "history_input": "",
        },
    }

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return upstream_payload

    class _FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            _ = (exc_type, exc, tb)

        async def post(
            self,
            url: str,
            *,
            data: dict[str, str],
            files: dict[str, tuple[str, bytes, str]] | None,
        ) -> _MockResponse:
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.council.httpx.AsyncClient", _FakeAsyncClient)

    response = client.post(
        "/api/v1/council/intake",
        headers={"Authorization": f"Bearer {token}"},
        data={"transcript": "bn đau đầu"},
    )

    assert response.status_code == 200
    assert response.json() == upstream_payload
    assert str(captured["url"]).endswith("/v1/council/intake")
    assert captured["data"] == {"transcript": "bn đau đầu"}
    assert captured["files"] is None
    assert float(captured["timeout"]) > 0


def test_council_consult_success(monkeypatch) -> None:
    token = _login("dr@doctor.clara")
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

    response = client.post(
        "/api/v1/council/consult",
        headers={"Authorization": f"Bearer {token}"},
        json={"transcript": "bn đau ngực, khó thở", "specialists": ["cardiology", "pharmacology"]},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert str(captured["url"]).endswith("/v1/council/consult")
    assert float(captured["timeout"]) > 0


def test_council_intake_missing_input_returns_400() -> None:
    token = _login("dr@doctor.clara")

    response = client.post(
        "/api/v1/council/intake",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Either transcript or audio_file is required" in response.json()["detail"]


def test_council_intake_forbidden_for_non_doctor() -> None:
    token = _login("alice@research.clara")

    response = client.post(
        "/api/v1/council/intake",
        headers={"Authorization": f"Bearer {token}"},
        data={"transcript": "bn đau đầu"},
    )

    assert response.status_code == 403


def test_council_intake_rejects_unsupported_audio_type() -> None:
    token = _login("dr@doctor.clara")

    response = client.post(
        "/api/v1/council/intake",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio_file": ("note.txt", b"abc", "text/plain")},
    )

    assert response.status_code == 415
    assert "Unsupported audio content type" in response.json()["detail"]


def test_council_intake_rejects_too_large_audio() -> None:
    token = _login("dr@doctor.clara")
    huge_bytes = b"a" * (15 * 1024 * 1024 + 1)

    response = client.post(
        "/api/v1/council/intake",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio_file": ("audio.webm", huge_bytes, "audio/webm")},
    )

    assert response.status_code == 413
    assert "Maximum size is 15MB" in response.json()["detail"]
