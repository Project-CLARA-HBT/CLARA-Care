from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
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


def test_scribe_transcribe_accepts_webm_with_codec_param(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {"text": "transcribed text"}

    class _MockAsyncClient:
        def __init__(self, timeout: float):
            self.timeout = timeout
            assert timeout == get_settings().ml_scribe_timeout_seconds

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

        async def post(self, _url: str, **kwargs: Any):
            files = kwargs.get("files") or {}
            uploaded = files.get("audio_file")
            assert isinstance(uploaded, tuple)
            assert uploaded[2] == "audio/webm"
            return _MockResponse()

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.scribe.httpx.AsyncClient",
        _MockAsyncClient,
    )

    response = client.post(
        "/api/v1/scribe/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio_file": ("session.webm", b"audio-bytes", "audio/webm;codecs=opus")},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "transcribed text"


def test_scribe_transcribe_rejects_unsupported_mime_with_param() -> None:
    token = _login("dr@doctor.clara")
    response = client.post(
        "/api/v1/scribe/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio_file": ("session.ogg", b"audio-bytes", "audio/ogg;codecs=opus")},
    )
    assert response.status_code == 415
    assert "Unsupported audio content type" in response.json()["detail"]
