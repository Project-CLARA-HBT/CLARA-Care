"""Tests for the request body-size limit middleware (Requirement 4.1, 4.2).

These build an isolated app around ``RequestBodyLimitMiddleware`` and stub the
settings the middleware reads, so the body-size behavior can be exercised
without the full application startup.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import clara_api.core.request_limits as request_limits
from clara_api.core.request_limits import RequestBodyLimitMiddleware


@dataclass
class _StubSettings:
    hardening_request_body_limit_enabled: bool
    hardening_request_body_max_bytes: int


def _build_client(monkeypatch: pytest.MonkeyPatch, settings: _StubSettings) -> TestClient:
    monkeypatch.setattr(request_limits, "get_settings", lambda: settings)

    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"received": len(body)}

    @app.post("/scribe/transcribe")
    async def scribe(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"received": len(body)}

    @app.post("/council/audio")
    async def council(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"received": len(body)}

    return TestClient(app)


def test_flag_off_allows_oversized_body(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _StubSettings(
        hardening_request_body_limit_enabled=False,
        hardening_request_body_max_bytes=10,
    )
    client = _build_client(monkeypatch, settings)

    response = client.post("/echo", content=b"x" * 1000)

    assert response.status_code == 200
    assert response.json() == {"received": 1000}


def test_body_at_limit_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _StubSettings(
        hardening_request_body_limit_enabled=True,
        hardening_request_body_max_bytes=100,
    )
    client = _build_client(monkeypatch, settings)

    response = client.post("/echo", content=b"x" * 100)

    assert response.status_code == 200
    assert response.json() == {"received": 100}


def test_body_over_limit_is_rejected_413(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _StubSettings(
        hardening_request_body_limit_enabled=True,
        hardening_request_body_max_bytes=100,
    )
    client = _build_client(monkeypatch, settings)

    response = client.post("/echo", content=b"x" * 101)

    assert response.status_code == 413
    payload = response.json()
    assert payload["detail"] == "Request body too large."
    assert payload["max_bytes"] == 100


def test_413_response_is_pii_free(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _StubSettings(
        hardening_request_body_limit_enabled=True,
        hardening_request_body_max_bytes=16,
    )
    client = _build_client(monkeypatch, settings)

    secret = b"patient-name=Nguyen-Van-A-secret-overflow"
    response = client.post("/echo", content=secret)

    assert response.status_code == 413
    # The rejection must not echo any request content back to the client.
    assert "Nguyen" not in response.text
    assert "patient" not in response.text


def test_audio_upload_prefixes_are_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _StubSettings(
        hardening_request_body_limit_enabled=True,
        hardening_request_body_max_bytes=10,
    )
    client = _build_client(monkeypatch, settings)

    # Both audio-upload prefixes preserve their own _MAX_AUDIO_BYTES handling and
    # are not throttled by the generic body-size middleware.
    scribe_response = client.post("/scribe/transcribe", content=b"x" * 5000)
    assert scribe_response.status_code == 200
    assert scribe_response.json() == {"received": 5000}

    council_response = client.post("/council/audio", content=b"x" * 5000)
    assert council_response.status_code == 200
    assert council_response.json() == {"received": 5000}
