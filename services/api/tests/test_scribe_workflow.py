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


def _enable_sign_workflow(monkeypatch) -> None:
    """Enable the flag-gated enterprise sign workflow (Requirement 11.1)."""

    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_sign_workflow_enabled", True, raising=False)


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
    _enable_sign_workflow(monkeypatch)
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
    _enable_sign_workflow(monkeypatch)
    token = _login()
    sid = _create_session(token)
    # No note generated yet -> still draft -> sign must be rejected (illegal transition).
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 409


def test_consent_required_blocks_note_when_flag_on(monkeypatch) -> None:
    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
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
    _enable_sign_workflow(monkeypatch)
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


def test_generate_note_honors_template_when_templates_enabled(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_templates_enabled", True, raising=False)
    _enable_sign_workflow(monkeypatch)

    def path_aware_proxy(path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        if path == "/v1/scribe/note":
            return {
                "template_id": "vn_benh_an",
                "sections": {"Lý do khám": "ho", "Chẩn đoán": "viêm họng"},
                "insufficient_input": False,
            }
        return {"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"}

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", path_aware_proxy)
    token = _login("dr.tpl@doctor.clara")
    sid = _create_session(token)
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "vn_benh_an"},
    )
    assert g.status_code == 200
    body = g.json()
    # The persisted note used the VN template's sections (not SOAP).
    assert body["soap"] is not None
    assert "Chẩn đoán" in body["soap"]


def test_generate_note_defaults_to_soap_when_templates_disabled(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_templates_enabled", False, raising=False)
    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.soap@doctor.clara")
    sid = _create_session(token)
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "vn_benh_an"},
    )
    assert g.status_code == 200
    # Flag off -> SOAP shape regardless of requested template.
    assert set(g.json()["soap"].keys()) >= {"subjective", "objective", "assessment", "plan"}


# ---------------------------------------------------------------------------
# Task 2.2 focused coverage: version_no increments, signed-row immutability,
# from/to audit on every transition, prior-version queryability, flag gating.
# ---------------------------------------------------------------------------


def _versions_for(sid: int) -> list[Any]:
    """Read all persisted note versions for a session, oldest first."""

    from sqlalchemy import select

    from clara_api.db.models import ScribeNoteVersion
    from clara_api.db.session import SessionLocal

    with SessionLocal() as db:
        return list(
            db.execute(
                select(ScribeNoteVersion)
                .where(ScribeNoteVersion.session_id == sid)
                .order_by(ScribeNoteVersion.version_no.asc())
            ).scalars().all()
        )


def test_signed_version_is_immutable_after_amend(monkeypatch) -> None:
    """Req 8.2/8.5: amend preserves the signed version byte-for-byte + bumps version_no."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.imm@doctor.clara")
    sid = _create_session(token)

    client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                json={"template_id": "soap"})
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))

    # Snapshot the signed (v1) row before amend.
    before = _versions_for(sid)
    assert len(before) == 1
    v1 = before[0]
    assert v1.version_no == 1
    assert v1.signed is True and v1.signed_at is not None and v1.signed_by is not None
    v1_sections = dict(v1.sections_json or {})
    v1_signed_at = v1.signed_at
    v1_signed_by = v1.signed_by

    # Amend -> new version, signed one preserved.
    a = client.post(f"/api/v1/scribe/sessions/{sid}/amend", headers=_auth(token),
                    json={"template_id": "soap", "transcript": "updated transcript"})
    assert a.status_code == 200 and a.json()["status"] == "amended"

    after = _versions_for(sid)
    assert [v.version_no for v in after] == [1, 2]  # version_no incremented, v1 still present
    v1_after = after[0]
    # The signed v1 row is byte-for-byte unchanged (immutable).
    assert v1_after.signed is True
    assert v1_after.sections_json == v1_sections
    assert v1_after.signed_at == v1_signed_at
    assert v1_after.signed_by == v1_signed_by
    # The new amended v2 row is unsigned.
    assert after[1].signed is False


def test_every_transition_writes_from_to_audit(monkeypatch) -> None:
    """Req 8.3: each status transition records actor + from_status/to_status."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    monkeypatch.setattr(get_settings(), "rag_scribe_export_enabled", True, raising=False)
    token = _login("dr.audit@doctor.clara")
    sid = _create_session(token)

    client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                json={"template_id": "soap"})
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    client.post(f"/api/v1/scribe/sessions/{sid}/amend", headers=_auth(token),
                json={"template_id": "soap"})
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))  # re-sign amendment
    client.get(f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))

    entries = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token)).json()[
        "entries"
    ]
    # The note_signed action appears twice (initial sign + re-sign of the amendment),
    # so assert on the full (action, from, to) tuple set rather than keying by action.
    transitions = {(e["action"], e["from_status"], e["to_status"]) for e in entries}
    assert ("note_generated", "draft", "in_review") in transitions
    assert ("note_signed", "in_review", "signed") in transitions
    assert ("note_amended", "signed", "amended") in transitions
    assert ("note_signed", "amended", "signed") in transitions
    assert ("note_exported", "signed", "exported") in transitions
    # Every transition carries an actor.
    assert all(e["actor"] is not None for e in entries)


def test_amend_from_draft_rejected(monkeypatch) -> None:
    """Req 8.1: amend is only legal from 'signed'."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.amenddraft@doctor.clara")
    sid = _create_session(token)
    a = client.post(f"/api/v1/scribe/sessions/{sid}/amend", headers=_auth(token),
                    json={"template_id": "soap"})
    assert a.status_code == 409


def test_resign_signed_version_rejected(monkeypatch) -> None:
    """Req 8.2: a signed version cannot be re-signed in place."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.resign@doctor.clara")
    sid = _create_session(token)
    client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                json={"template_id": "soap"})
    sign_resp = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert sign_resp.status_code == 200
    # Status is now 'signed'; signing again is an illegal transition (409).
    resign_resp = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert resign_resp.status_code == 409


def test_regenerate_in_review_versions_and_audits_without_transition(monkeypatch) -> None:
    """Req 8.3/8.5: regenerating while in_review keeps prior versions + audits the edit."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.regen@doctor.clara")
    sid = _create_session(token)

    client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                json={"template_id": "soap"})
    second = client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                         json={"template_id": "soap"})
    assert second.status_code == 200 and second.json()["status"] == "in_review"

    # Both versions persisted (prior content recoverable, Req 8.5).
    assert [v.version_no for v in _versions_for(sid)] == [1, 2]

    # Two note_generated audit entries; the second is an edit with no transition.
    entries = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token)).json()[
        "entries"
    ]
    gens = [e for e in entries if e["action"] == "note_generated"]
    assert len(gens) == 2
    assert gens[0]["from_status"] == "draft" and gens[0]["to_status"] == "in_review"
    assert gens[1]["from_status"] == "in_review" and gens[1]["to_status"] == "in_review"


def test_generate_on_signed_rejected_use_amend(monkeypatch) -> None:
    """Req 8.2: once signed, in-place note regeneration is rejected (use amend)."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.gensigned@doctor.clara")
    sid = _create_session(token)
    client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                json={"template_id": "soap"})
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    g = client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                    json={"template_id": "soap"})
    assert g.status_code == 409


def test_sign_workflow_disabled_returns_404(monkeypatch) -> None:
    """Req 11.1/11.2: flag off ⇒ enterprise note lifecycle endpoints not exposed."""

    _mock_soap(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_sign_workflow_enabled", False, raising=False)
    token = _login("dr.flagoff@doctor.clara")
    sid = _create_session(token)
    assert client.post(f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
                       json={"template_id": "soap"}).status_code == 404
    assert client.post(f"/api/v1/scribe/sessions/{sid}/sign",
                       headers=_auth(token)).status_code == 404
    assert client.post(f"/api/v1/scribe/sessions/{sid}/amend", headers=_auth(token),
                       json={"template_id": "soap"}).status_code == 404
