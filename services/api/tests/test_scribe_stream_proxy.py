"""API tests for the Scribe streaming SSE proxy (Task 1.2 / Requirement 1.6).

`POST /api/v1/scribe/sessions/{id}/stream` mirrors `/api/v1/chat/stream`:
clinician RBAC + owner-scoping + internal-key relay to the ML
`/v1/scribe/stream` SSE endpoint, gated by `RAG_SCRIBE_STREAMING_ENABLED`.

Covers: flag-off 404, RBAC rejection (non-clinician), owner-scoping (non-owner),
and successful SSE relay framing with a mocked ML upstream.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)


def _login(email: str = "dr@doctor.clara") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    status = client.get("/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"})
    version = status.json()["required_version"]
    client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": version, "accepted": True},
    )
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(token: str, transcript: str = "patient has cough") -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _audio() -> dict[str, Any]:
    return {"audio_file": ("session.webm", b"audio-bytes", "audio/webm")}


class _MockStream:
    """Mimics the httpx streaming-response context manager used in the relay."""

    def __init__(self, status_code: int, chunks: list[bytes]):
        self.status_code = status_code
        self._chunks = chunks

    def __enter__(self) -> _MockStream:
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def read(self) -> bytes:
        return b""

    def iter_raw(self):  # noqa: ANN202 - generator of byte chunks
        yield from self._chunks


class _MockClient:
    """Captures the stream() kwargs so header/URL forwarding can be asserted."""

    last_kwargs: dict[str, Any] = {}
    last_url: str = ""
    status_code: int = 200
    chunks: list[bytes] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def __enter__(self) -> _MockClient:
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def stream(self, _method: str, url: str, **kwargs: Any) -> _MockStream:
        _MockClient.last_url = url
        _MockClient.last_kwargs = kwargs
        return _MockStream(_MockClient.status_code, _MockClient.chunks)


def test_stream_returns_404_when_flag_off() -> None:
    # Default: RAG_SCRIBE_STREAMING_ENABLED is off -> legacy behavior (no route).
    token = _login("dr.streamoff@doctor.clara")
    sid = _create_session(token)
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/stream",
        headers=_auth(token),
        files=_audio(),
    )
    assert r.status_code == 404
    assert "disabled" in r.json()["detail"].lower()


def test_stream_rejects_non_clinician(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", True, raising=False)
    # A plain (non-doctor) account is "normal" and must be rejected by RBAC.
    token = _login("normal.user@example.com")
    r = client.post(
        "/api/v1/scribe/sessions/1/stream",
        headers=_auth(token),
        files=_audio(),
    )
    assert r.status_code == 403


def test_stream_rejects_non_owner(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", True, raising=False)
    token_a = _login("dr.owner@doctor.clara")
    sid = _create_session(token_a)
    # A different clinician cannot stream another clinician's session (owner-scoped).
    token_b = _login("dr.intruder@doctor.clara")
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/stream",
        headers=_auth(token_b),
        files=_audio(),
    )
    assert r.status_code == 404


def test_stream_relays_sse_framing_and_internal_key(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", True, raising=False)
    monkeypatch.setattr(settings, "ml_internal_api_key", "test-internal-key", raising=False)

    _MockClient.status_code = 200
    _MockClient.chunks = [
        b'event: start\ndata: {}\n\n',
        b'event: segment\ndata: {"text":"hello","degraded":false}\n\n',
        b'event: done\ndata: {}\n\n',
    ]
    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.httpx.Client", _MockClient)

    token = _login("dr.relay@doctor.clara")
    sid = _create_session(token)
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/stream",
        headers=_auth(token),
        files=_audio(),
        params={"language": "vi"},
    )

    assert r.status_code == 200
    # SSE content type + event framing preserved during relay.
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.content.decode()
    assert "event: start" in body
    assert "event: segment" in body
    assert "event: done" in body
    assert '"text":"hello"' in body

    # Relays to the ML scribe stream endpoint with the internal-key header.
    assert _MockClient.last_url.endswith("/v1/scribe/stream")
    fwd_headers = _MockClient.last_kwargs.get("headers") or {}
    assert fwd_headers.get("X-ML-Internal-Key") == "test-internal-key"
    assert fwd_headers.get("Accept") == "text/event-stream"


def test_stream_emits_terminal_error_frame_on_upstream_failure(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", True, raising=False)

    _MockClient.status_code = 502
    _MockClient.chunks = []
    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.httpx.Client", _MockClient)

    token = _login("dr.err@doctor.clara")
    sid = _create_session(token)
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/stream",
        headers=_auth(token),
        files=_audio(),
    )
    # The relay still returns 200 (stream opened) but emits a terminal error frame
    # naming the failure class — no raw provider internals leak.
    assert r.status_code == 200
    body = r.content.decode()
    assert "event: error" in body
    assert "upstream error" in body
