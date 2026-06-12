"""Scribe pipeline flow/telemetry events via the audit trail (task 3.1, Req 10.3).

The audit endpoint additively surfaces a ``flow_events`` projection that reuses
the existing flow-event shape (``{stage, timestamp, status, source_count, note}``)
so the API-side pipeline stages — consent, transcribe, diarize, generate, sign —
are observable in the UI process panel via the same mechanism as chat/research.

Asserts: events are emitted for the relevant stages; events are PII-free (no
transcript text / patient identifier appears in any event, Req 10.1); and event
shapes match the established flow-event contract. Flag-consistent: with the
enterprise flags off no audit rows exist, so the projection is empty (legacy
behavior unchanged).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)

_FLOW_KEYS = {"stage", "timestamp", "status", "source_count", "note"}
_SECRET = "Nguyen Van Patient 0901234567 warfarin secret-history-text"


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200
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


def _mock_soap(monkeypatch) -> None:
    def fake_proxy(_path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        return {"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"}

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _enable_sign_workflow(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "rag_scribe_sign_workflow_enabled", True, raising=False)


def _create_session(token: str, transcript: str = _SECRET) -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_audit_flow_events_cover_consent_generate_sign(monkeypatch) -> None:
    """Req 10.3: consent/generate/sign stages surface as flow events."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.flow@doctor.clara")
    sid = _create_session(token)

    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))

    audit = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token))
    assert audit.status_code == 200
    body = audit.json()
    assert "flow_events" in body
    stages = [e["stage"] for e in body["flow_events"]]
    # Consent -> generate -> sign pipeline stages are all observable, in order.
    assert stages == ["consent", "generate", "sign"]


def test_audit_flow_events_match_contract_shape(monkeypatch) -> None:
    """Every projected flow event matches the established flow-event contract."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.flowshape@doctor.clara")
    sid = _create_session(token)
    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    client.post(
        f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token), json={"template_id": "soap"}
    )

    events = client.get(
        f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token)
    ).json()["flow_events"]
    assert events
    for event in events:
        assert set(event.keys()) == _FLOW_KEYS
        assert isinstance(event["stage"], str) and event["stage"]
        assert isinstance(event["status"], str) and event["status"]
        assert isinstance(event["source_count"], int) and event["source_count"] >= 0
        assert isinstance(event["note"], str)
        assert isinstance(event["timestamp"], str) and event["timestamp"]


def test_audit_flow_events_are_pii_free(monkeypatch) -> None:
    """Req 10.1: no transcript text / patient identifier leaks into any flow event."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.flowpii@doctor.clara")
    sid = _create_session(token, transcript=_SECRET)

    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    client.post(
        f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token), json={"template_id": "soap"}
    )
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))

    events = client.get(
        f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token)
    ).json()["flow_events"]
    serialized = json.dumps(events, ensure_ascii=False)
    for pii in ("Nguyen", "0901234567", "warfarin", "secret-history-text"):
        assert pii not in serialized


def test_flow_events_empty_without_audit_rows(monkeypatch) -> None:
    """Flag-consistent: a session with no enterprise audit rows yields no flow events."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.flowempty@doctor.clara")
    sid = _create_session(token)
    body = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token)).json()
    assert body["flow_events"] == []
