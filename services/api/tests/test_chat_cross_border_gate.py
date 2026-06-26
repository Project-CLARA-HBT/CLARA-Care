"""Cross-border transfer gate wiring on the chat ML proxy (task 5.2).

Verifies that ``outbound_guard`` is consulted before the outbound (offshore)
ML call: when ``COMPLIANCE_CROSS_BORDER_GATING_ENABLED`` is on and the user has
not granted ``cross_border_processing`` consent, the chat turn degrades to a
local deterministic answer labeled degraded and the offshore model is never
called. With the flag off, or with consent present, behavior is unchanged.

**Validates: Requirements 4.2 / Correctness Property P2**
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.compliance import consent as consent_ledger
from clara_api.core.config import get_settings
from clara_api.db.models import User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return int(db.execute(select(User.id).where(User.email == email)).scalar_one())


def _normal_ml_response() -> object:
    class _MockResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "answer": "mocked-answer",
                "role": "doctor",
                "intent": "evidence_review",
                "confidence": 0.9,
                "emergency": False,
                "model_used": "deepseek-v3.2",
                "retrieved_ids": ["doc-1"],
            }

    return _MockResponse()


def test_chat_degrades_when_cross_border_consent_absent(monkeypatch) -> None:
    """Gating on + no consent ⇒ degrade locally, never call the offshore ML."""
    token = _login("blockme@doctor.clara")

    def _fake_post(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("offshore ML must NOT be called when cross-border is gated")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)
    monkeypatch.setenv("COMPLIANCE_CROSS_BORDER_GATING_ENABLED", "true")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "warfarin và aspirin có rủi ro gì"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["model_used"] == "local-synth-degraded-v1"
    assert body["fallback"] is True
    assert body["fallback_reason"].startswith("cross_border_gated:")
    assert "xuyên biên giới" in body["reply"]


def test_chat_proxies_when_gating_flag_off(monkeypatch) -> None:
    """Flag off (default) ⇒ proxies to the ML service exactly as before."""
    token = _login("legacy@doctor.clara")
    calls = {"n": 0}

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        calls["n"] += 1
        _ = (json, timeout)
        return _normal_ml_response()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)

    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "metformin la gi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert calls["n"] == 1
    assert body["model_used"] == "deepseek-v3.2"
    assert body["reply"] == "mocked-answer"
    assert body["fallback"] is False


def test_chat_proxies_when_cross_border_consent_present(monkeypatch) -> None:
    """Gating on + consent present ⇒ offshore call proceeds normally."""
    token = _login("okcross@doctor.clara")
    user_id = _user_id("okcross@doctor.clara")
    with SessionLocal() as db:
        consent_ledger.grant(
            db, user_id=user_id, purpose=consent_ledger.PURPOSE_CROSS_BORDER, version="v1"
        )
        db.commit()

    calls = {"n": 0}

    def _fake_post(_url: str, *, json: dict[str, object], timeout: float) -> object:
        calls["n"] += 1
        _ = (json, timeout)
        return _normal_ml_response()

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.post", _fake_post)
    monkeypatch.setenv("COMPLIANCE_CROSS_BORDER_GATING_ENABLED", "true")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "metformin la gi"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert calls["n"] == 1
    assert body["model_used"] == "deepseek-v3.2"
    assert body["reply"] == "mocked-answer"


def test_chat_stream_degrades_without_opening_upstream(monkeypatch) -> None:
    """Gating on + no consent ⇒ stream emits a terminal degraded frame only."""
    token = _login("blockstream@doctor.clara")

    def _fail_client(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("offshore stream must NOT be opened when gated")

    monkeypatch.setattr("clara_api.api.v1.endpoints.chat.httpx.Client", _fail_client)
    monkeypatch.setenv("COMPLIANCE_CROSS_BORDER_GATING_ENABLED", "true")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "warfarin và aspirin có rủi ro gì"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert "cross_border_consent_required" in response.text
