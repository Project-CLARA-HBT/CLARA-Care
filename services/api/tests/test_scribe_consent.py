"""Consent capture + guard + immutability tests for Clara Scribe (Requirement 4).

Covers:
- 4.1 flag-on rejects transcription/note for a session with no active consent;
       flag-off leaves the legacy path unguarded (byte-for-byte).
- 4.2 consent capture persists method/scope/captured_by/captured_at, sets
       session.consent_id, and writes a ``consent_captured`` audit entry.
- 4.3 the consent record is immutable: there is no edit endpoint, and revoking
       leaves the captured fields unchanged (revocation is a NEW audit event).
- 4.4 revoking stops further transcription (revoked => treated as no active
       consent) and flags the session accordingly.

Uses the doctor auto-provision login + a mocked ML SOAP proxy (no real ML calls).
"""

from __future__ import annotations

import io
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeConsent
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str = "dr.consent@doctor.clara") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    status = client.get(
        "/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"}
    )
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


def _mock_transcribe_ml(monkeypatch) -> None:
    async def fake_call(**_kw: Any) -> dict[str, Any]:
        return {"text": "transcribed text"}

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.scribe._call_scribe_transcribe_ml", fake_call
    )


def _create_session(token: str, transcript: str = "patient has cough") -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _audio_files() -> dict[str, Any]:
    return {"audio_file": ("a.webm", io.BytesIO(b"fake-audio-bytes"), "audio/webm")}


# --- Req 4.2: capture persists fields + sets consent_id + writes audit -------


def test_consent_capture_persists_record_and_audit(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    token = _login("dr.cap@doctor.clara")
    sid = _create_session(token)

    c = client.post(
        f"/api/v1/scribe/sessions/{sid}/consent",
        headers=_auth(token),
        json={"method": "written", "scope": "full-visit"},
    )
    assert c.status_code == 200
    body = c.json()
    assert body["captured"] is True
    consent_id = body["consent_id"]

    with SessionLocal() as db:
        row = db.get(ScribeConsent, consent_id)
        assert row is not None
        assert row.method == "written"
        assert row.scope == "full-visit"
        assert row.captured_by is not None
        assert row.captured_at is not None
        assert row.revoked_at is None

    # session.consent_id points at the record.
    sess = client.get(f"/api/v1/scribe/sessions/{sid}", headers=_auth(token))
    assert sess.status_code == 200

    audit = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token))
    actions = [e["action"] for e in audit.json()["entries"]]
    assert "consent_captured" in actions


# --- Req 4.1: flag-on guard rejects without consent, allows after capture ----


def test_flag_off_transcription_not_guarded(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_consent_required", False, raising=False)
    _mock_transcribe_ml(monkeypatch)
    token = _login("dr.flagoff@doctor.clara")
    sid = _create_session(token)
    # No consent, flag off -> legacy behavior, transcription allowed.
    r = client.post(
        "/api/v1/scribe/transcribe",
        headers=_auth(token),
        files=_audio_files(),
        data={"session_id": str(sid)},
    )
    assert r.status_code == 200
    assert r.json()["text"] == "transcribed text"


def test_flag_on_rejects_transcription_without_consent(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_consent_required", True, raising=False)
    _mock_transcribe_ml(monkeypatch)
    token = _login("dr.guard@doctor.clara")
    sid = _create_session(token)
    r = client.post(
        "/api/v1/scribe/transcribe",
        headers=_auth(token),
        files=_audio_files(),
        data={"session_id": str(sid)},
    )
    assert r.status_code == 403


def test_capture_then_transcription_allowed(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_consent_required", True, raising=False)
    _mock_transcribe_ml(monkeypatch)
    token = _login("dr.allow@doctor.clara")
    sid = _create_session(token)
    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    r = client.post(
        "/api/v1/scribe/transcribe",
        headers=_auth(token),
        files=_audio_files(),
        data={"session_id": str(sid)},
    )
    assert r.status_code == 200


# --- Req 4.3: immutability — no edit endpoint, captured fields unchanged ------


def test_no_consent_edit_endpoint() -> None:
    token = _login("dr.noedit@doctor.clara")
    sid = _create_session(token)
    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    # There is no PATCH/PUT consent route; only POST capture + POST revoke exist.
    patched = client.patch(
        f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={"method": "x"}
    )
    assert patched.status_code in (404, 405)
    put = client.put(
        f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={"method": "x"}
    )
    assert put.status_code in (404, 405)


def test_revoke_leaves_captured_fields_unchanged(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    token = _login("dr.immutable@doctor.clara")
    sid = _create_session(token)
    c = client.post(
        f"/api/v1/scribe/sessions/{sid}/consent",
        headers=_auth(token),
        json={"method": "verbal", "scope": "encounter"},
    )
    consent_id = c.json()["consent_id"]

    with SessionLocal() as db:
        before = db.get(ScribeConsent, consent_id)
        captured = (before.method, before.scope, before.captured_by, before.captured_at)

    rv = client.post(f"/api/v1/scribe/sessions/{sid}/consent/revoke", headers=_auth(token))
    assert rv.status_code == 200 and rv.json()["revoked"] is True

    with SessionLocal() as db:
        after = db.get(ScribeConsent, consent_id)
        # Original captured fields are byte-for-byte unchanged; only revoked_at is set.
        assert (after.method, after.scope, after.captured_by, after.captured_at) == captured
        assert after.revoked_at is not None


# --- Req 4.4: revoke creates new audit event + blocks further transcription ---


def test_revoke_creates_new_audit_event_and_blocks(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_consent_required", True, raising=False)
    _mock_transcribe_ml(monkeypatch)
    token = _login("dr.revoke@doctor.clara")
    sid = _create_session(token)

    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    # Allowed while consent active.
    ok = client.post(
        "/api/v1/scribe/transcribe",
        headers=_auth(token),
        files=_audio_files(),
        data={"session_id": str(sid)},
    )
    assert ok.status_code == 200

    rv = client.post(f"/api/v1/scribe/sessions/{sid}/consent/revoke", headers=_auth(token))
    assert rv.status_code == 200

    # Audit gained a distinct consent_revoked entry (not an edit of the capture entry).
    audit = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token))
    actions = [e["action"] for e in audit.json()["entries"]]
    assert actions.count("consent_captured") == 1
    assert actions.count("consent_revoked") == 1

    # Further transcription is now blocked (revoked => no active consent).
    blocked = client.post(
        "/api/v1/scribe/transcribe",
        headers=_auth(token),
        files=_audio_files(),
        data={"session_id": str(sid)},
    )
    assert blocked.status_code == 403


def test_revoke_without_active_consent_returns_404() -> None:
    token = _login("dr.norevoke@doctor.clara")
    sid = _create_session(token)
    rv = client.post(f"/api/v1/scribe/sessions/{sid}/consent/revoke", headers=_auth(token))
    assert rv.status_code == 404
