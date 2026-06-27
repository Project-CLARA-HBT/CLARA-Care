"""Regression tests locking Council input validation across the upgrade (task 5.3).

Requirement 5.4 mandates that the upgrade preserve the *existing* input-validation
behavior of the Council surface:

* a run with no symptoms, labs, medications, or history is rejected with **400**;
* audio uploads keep the existing **15MB** size limit (**413** when exceeded);
* audio uploads keep the existing content-type allow-list (**415** when violated).

These checks live in ``services/api/.../endpoints/council.py``:
``_call_council_intake_ml`` raises 400/413/415 (used by both ``POST /council/intake``
and ``POST /council/cases/{id}/intake``), and ``run_council_case`` raises 400 on an
empty run payload. This module locks all four behaviors so the upgrade — which is
additive and feature-flagged (all ``COUNCIL_*`` flags default OFF) — cannot
silently regress them.

The validation in every case runs *before* any upstream ML call, so the ML
proxy / ML intake network path is stubbed to raise if it is ever reached. That
both keeps the suite free of any live-ML dependency and strengthens the
regression: it proves validation short-circuits before the network.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)

# The audio size limit and content-type allow-list mirrored from the endpoint
# under test; if the production constants change, these expectations should be
# revisited deliberately rather than drift silently.
_MAX_AUDIO_BYTES = 15 * 1024 * 1024
_ALLOWED_AUDIO_TYPE = "audio/wav"
_DISALLOWED_AUDIO_TYPE = "audio/ogg"


def _login(email: str = "dr@doctor.clara") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_empty_case(token: str) -> int:
    """Create a case with no run payload (so a run has no input data)."""

    response = client.post(
        "/api/v1/council/cases",
        headers=_auth(token),
        json={"title": "empty case"},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


@pytest.fixture
def fail_if_ml_called(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any upstream Council ML call explode.

    Validation (400/413/415) must short-circuit before the ML proxy or the ML
    intake HTTP client is touched. Wiring both to raise turns a regression that
    reorders validation after the network call into a hard test failure, and
    guarantees no live ML service is needed.
    """

    def _boom_proxy(_path: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("proxy_ml_post must not be called before validation passes")

    class _BoomAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("ML intake HTTP client must not be opened before validation")

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        _boom_proxy,
    )
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.httpx.AsyncClient",
        _BoomAsyncClient,
    )


# ---------------------------------------------------------------------------
# 400 — empty input
# ---------------------------------------------------------------------------


def test_intake_rejects_empty_input_with_400(fail_if_ml_called) -> None:
    """No transcript and no audio on intake → 400 (Req 5.4)."""

    token = _login()
    response = client.post(
        "/api/v1/council/intake",
        headers=_auth(token),
        data={"transcript": ""},
    )
    assert response.status_code == 400, response.text
    assert "transcript or audio_file is required" in response.json()["detail"]


def test_case_run_rejects_empty_payload_with_400(fail_if_ml_called) -> None:
    """Running a case with no symptoms/labs/medications/history → 400 (Req 5.4)."""

    token = _login()
    case_id = _create_empty_case(token)
    response = client.post(
        f"/api/v1/council/cases/{case_id}/run",
        headers=_auth(token),
        json={},
    )
    assert response.status_code == 400, response.text
    assert "dữ liệu đầu vào" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 413 — audio over 15MB
# ---------------------------------------------------------------------------


def test_intake_rejects_oversized_audio_with_413(fail_if_ml_called) -> None:
    """Audio over the 15MB limit → 413 (Req 5.4)."""

    token = _login()
    oversized = b"\x00" * (_MAX_AUDIO_BYTES + 1)
    response = client.post(
        "/api/v1/council/intake",
        headers=_auth(token),
        files={"audio_file": ("big.wav", oversized, _ALLOWED_AUDIO_TYPE)},
    )
    assert response.status_code == 413, response.text
    assert "too large" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 415 — audio content-type not in the allow-list
# ---------------------------------------------------------------------------


def test_intake_rejects_unsupported_content_type_with_415(fail_if_ml_called) -> None:
    """Audio with a content-type outside the allow-list → 415 (Req 5.4)."""

    token = _login()
    response = client.post(
        "/api/v1/council/intake",
        headers=_auth(token),
        files={"audio_file": ("clip.ogg", b"audio-bytes", _DISALLOWED_AUDIO_TYPE)},
    )
    assert response.status_code == 415, response.text
    assert "Unsupported audio content type" in response.json()["detail"]
