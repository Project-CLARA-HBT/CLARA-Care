"""Property 6: scribe analytics/telemetry is PII-free (Requirement 10.1).

The analytics summary must expose only coarse counts/durations — never the raw
transcript or patient identifiers.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)

_SECRET = "Nguyen Van Patient 0901234567 warfarin secret-history-text"


def _login(email: str = "dr.pii@doctor.clara") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    token = r.json()["access_token"]
    status = client.get("/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"})
    version = status.json()["required_version"]
    client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": version, "accepted": True},
    )
    return token


def test_analytics_summary_contains_no_transcript_pii() -> None:
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}
    # Create a session whose transcript carries (fake) PII + clinical text.
    created = client.post(
        "/api/v1/scribe/sessions",
        headers=headers,
        json={"title": "visit", "transcript": _SECRET, "auto_generate_soap": False},
    )
    assert created.status_code == 200

    summary = client.get("/api/v1/scribe/analytics/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()

    # Only coarse numeric signals; no transcript/PII tokens leak into telemetry.
    serialized = json.dumps(body)
    for token_text in ("Nguyen", "0901234567", "warfarin", "secret-history-text"):
        assert token_text not in serialized
    assert set(body.keys()) == {
        "total_sessions",
        "completed_sessions",
        "draft_sessions",
        "sessions_today",
        "avg_transcript_chars",
    }
    assert all(isinstance(v, (int, float)) for v in body.values())
