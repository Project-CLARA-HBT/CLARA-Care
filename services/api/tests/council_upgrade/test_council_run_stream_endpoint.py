"""Tests for the Council streaming run proxy (task 2.2).

``POST /api/v1/council/cases/{id}/run/stream`` is the SSE sibling of the
blocking ``/run``. It is gated by ``COUNCIL_STREAMING_ENABLED`` (flag off ⇒ the
project's standard feature-disabled HTTP 404), and when on it enforces the same
``doctor`` RBAC, owner isolation, and empty-input validation as ``/run`` before
proxying the ML ``POST /v1/council/run/stream`` SSE through to the client
(Requirements 1.3, 1.6).

These tests stub ``httpx.Client`` so no live ML service is needed.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)

_RUN_PAYLOAD: dict[str, Any] = {
    "symptoms": ["polypharmacy", "fatigue"],
    "labs": {"creatinine": 1.2},
    "medications": ["warfarin"],
    "history": "htn",
    "specialist_count": 2,
    "specialists": ["pharmacology", "nephrology"],
}


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_case(token: str, request: dict[str, Any] | None = None) -> int:
    response = client.post(
        "/api/v1/council/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "stream case", "request": request or _RUN_PAYLOAD},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


class _FakeStreamCtx:
    """Mimics the ``client.stream(...)`` context manager from httpx."""

    def __init__(self, *, status_code: int, chunks: list[bytes]) -> None:
        self.status_code = status_code
        self._chunks = chunks

    def __enter__(self) -> _FakeStreamCtx:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b""

    def iter_raw(self):
        yield from self._chunks


class _FakeClient:
    def __init__(self, *, status_code: int, chunks: list[bytes], captured: dict[str, Any]) -> None:
        self._status_code = status_code
        self._chunks = chunks
        self._captured = captured

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def stream(self, method: str, url: str, *, json: dict[str, Any], headers: dict[str, str]):
        self._captured["method"] = method
        self._captured["url"] = url
        self._captured["json"] = json
        self._captured["headers"] = headers
        return _FakeStreamCtx(status_code=self._status_code, chunks=self._chunks)


def _install_fake_client(
    monkeypatch, *, status_code: int, chunks: list[bytes], captured: dict[str, Any]
) -> None:
    def _factory(*_args: Any, **_kwargs: Any) -> _FakeClient:
        return _FakeClient(status_code=status_code, chunks=chunks, captured=captured)

    monkeypatch.setattr("clara_api.api.v1.endpoints.council.httpx.Client", _factory)


def test_stream_returns_404_when_flag_off() -> None:
    """Flag off ⇒ feature-disabled 404; blocking /run remains the only path (Req 1.3)."""
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 404


def test_stream_relays_upstream_sse_when_flag_on(set_flags, monkeypatch) -> None:
    """Flag on ⇒ relay the ML SSE chunks untouched to the client (Req 1.1, 1.2)."""
    set_flags(council_streaming_enabled=True)
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    captured: dict[str, Any] = {}
    chunks = [
        b'event: stage\ndata: {"sequence":0,"step":"intake_normalized"}\n\n',
        b'event: result\ndata: {"final_recommendation":"review with a clinician"}\n\n',
    ]
    _install_fake_client(monkeypatch, status_code=200, chunks=chunks, captured=captured)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.content
    assert b"event: stage" in body
    assert b"event: result" in body
    # Proxies to the ML streaming endpoint with the normalized run payload.
    assert str(captured["url"]).endswith("/v1/council/run/stream")
    assert captured["json"]["symptoms"] == ["polypharmacy", "fatigue"]


def test_stream_emits_terminal_error_on_upstream_4xx(set_flags, monkeypatch) -> None:
    """Upstream error ⇒ terminal SSE error frame, never a partial success (Req 1.4)."""
    set_flags(council_streaming_enabled=True)
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    captured: dict[str, Any] = {}
    _install_fake_client(monkeypatch, status_code=503, chunks=[], captured=captured)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200
    assert b"event: error" in response.content


def test_stream_rejects_empty_input_with_400(set_flags) -> None:
    """Same empty-input validation as /run (Req 1.6 / 5.4)."""
    set_flags(council_streaming_enabled=True)
    token = _login("dr@doctor.clara")
    case_id = _create_case(
        token,
        request={"symptoms": [], "labs": {}, "medications": [], "history": ""},
    )

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 400


def test_stream_forbidden_for_non_doctor(set_flags) -> None:
    """Same doctor RBAC as /run (Req 1.6)."""
    set_flags(council_streaming_enabled=True)
    token = _login("alice@research.clara")

    response = client.post(
        "/api/v1/council/cases/1/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 403


def test_stream_owner_isolation_returns_404(set_flags) -> None:
    """A doctor cannot stream another doctor's case (Req 1.6 owner isolation)."""
    set_flags(council_streaming_enabled=True)
    owner_token = _login("dr@doctor.clara")
    case_id = _create_case(owner_token)

    other_token = _login("doctor2@doctor.clara")
    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream",
        headers={"Authorization": f"Bearer {other_token}"},
        json={},
    )

    assert response.status_code == 404
