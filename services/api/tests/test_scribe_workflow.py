"""Integration tests for the Clara Scribe enterprise workflow.

Covers consent capture (R4), note generation + sign/amend lifecycle with audit
(R8 / Property 4 — signed immutability + audit append-only), and export gating
(R9). Uses the doctor auto-provision login + a mocked ML SOAP proxy.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)


def _login(email: str = "dr@doctor.clara") -> str:
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


def _create_session(token: str, transcript: str = "patient has cough") -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_full_sign_amend_audit_workflow(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    token = _login()
    sid = _create_session(token)

    # consent
    c = client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    assert c.status_code == 200 and c.json()["captured"] is True

    # generate note -> status in_review
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    assert g.status_code == 200
    assert g.json()["status"] == "in_review"

    # sign -> status signed
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 200
    assert s.json()["status"] == "signed"

    # amend -> status amended (new version, signed one preserved)
    a = client.post(
        f"/api/v1/scribe/sessions/{sid}/amend",
        headers=_auth(token),
        json={"template_id": "soap", "transcript": "updated"},
    )
    assert a.status_code == 200
    assert a.json()["status"] == "amended"

    # audit trail is append-only + ordered (consent, note_generated, signed, amended)
    audit = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token))
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()["entries"]]
    assert actions == ["consent_captured", "note_generated", "note_signed", "note_amended"]


def test_cannot_sign_from_draft(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    token = _login()
    sid = _create_session(token)
    # No note generated yet -> still draft -> sign must be rejected (illegal transition).
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 409


def test_consent_required_blocks_note_when_flag_on(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_consent_required", True, raising=False)
    token = _login()
    sid = _create_session(token)
    # No consent captured -> note generation blocked.
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token), json={"template_id": "soap"}
    )
    assert g.status_code == 403


def test_export_requires_signed_and_flag(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_export_enabled", True, raising=False)
    token = _login()
    sid = _create_session(token)

    # draft export rejected
    e0 = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))
    assert e0.status_code == 409

    # progress to signed
    client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))

    e1 = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))
    assert e1.status_code == 200
    assert e1.json()["format"] == "md" and "markdown" in e1.json()


def test_owner_scoping_blocks_other_users(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    token_a = _login("dra@doctor.clara")
    sid = _create_session(token_a)
    token_b = _login("drb@doctor.clara")
    r = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token_b))
    assert r.status_code == 404
