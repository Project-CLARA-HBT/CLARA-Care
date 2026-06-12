"""Integration tests for the Scribe addendum endpoint (Task 6.2 / Requirement 18).

Covers:
- Attaching an addendum to a signed note inserts exactly one ``ScribeAddendum`` row +
  exactly one audit entry, creates NO new note version, and leaves the signed note
  version's ``sections_json`` byte-for-byte unchanged (Req 18.2/18.3/18.4/18.5).
- Export (md + fhir_composition) includes the addendum as a clearly demarcated,
  time-stamped section after the signed content (Req 18.6); signed sections unchanged.
- Addendum flag off ⇒ 404 (Req 18.1).
- Addendum on an unsigned note version is rejected (409) (Req 18.2).
- RBAC: non-doctor ⇒ 403; owner-scoping: non-owner clinician ⇒ 404.

Uses the doctor auto-provision login + a mocked ML SOAP proxy (no real ML calls).
"""

from __future__ import annotations

import copy
import json
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeAddendum, ScribeAudit, ScribeNoteVersion, ScribeSession
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200, r.text
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
        return {"subjective": "s-text", "objective": "o-text", "assessment": "a-text",
                "plan": "p-text"}

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _enable(monkeypatch, **flags: bool) -> None:
    settings = get_settings()
    settings_flags = {
        "rag_scribe_sign_workflow_enabled": True,
        "rag_scribe_export_enabled": True,
        "rag_scribe_addendum_enabled": True,
        **flags,
    }
    for name, value in settings_flags.items():
        monkeypatch.setattr(settings, name, value, raising=False)


def _create_session(token: str, transcript: str = "patient has cough") -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "Visit Note", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _set_encounter(session_id: int) -> None:
    with SessionLocal() as db:
        item = db.get(ScribeSession, session_id)
        assert item is not None
        item.encounter_json = {
            "visit_type": "follow-up",
            "encounter_at": "2026-04-10T09:30:00+00:00",
            "patient_ref": "opaque-patient-123",
        }
        db.add(item)
        db.commit()


def _generate(token: str, sid: int, template_id: str = "soap") -> int:
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
        json={"template_id": template_id},
    )
    assert g.status_code == 200, g.text
    # Return the latest version_no for this session.
    with SessionLocal() as db:
        rows = db.query(ScribeNoteVersion).filter(
            ScribeNoteVersion.session_id == sid
        ).order_by(ScribeNoteVersion.version_no.desc()).all()
        return rows[0].version_no


def _sign(token: str, sid: int) -> None:
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 200, s.text
    assert s.json()["status"] == "signed"


def _progress_to_signed(token: str, sid: int) -> int:
    ver = _generate(token, sid)
    _sign(token, sid)
    return ver


def _counts(sid: int) -> tuple[int, int, int]:
    """Return (addendum_count, audit_count, note_version_count) for a session."""

    with SessionLocal() as db:
        addenda = db.query(ScribeAddendum).filter(
            ScribeAddendum.session_id == sid
        ).count()
        audits = db.query(ScribeAudit).filter(ScribeAudit.session_id == sid).count()
        versions = db.query(ScribeNoteVersion).filter(
            ScribeNoteVersion.session_id == sid
        ).count()
        return addenda, audits, versions


def _signed_sections_snapshot(sid: int) -> Any:
    with SessionLocal() as db:
        row = db.query(ScribeNoteVersion).filter(
            ScribeNoteVersion.session_id == sid,
            ScribeNoteVersion.signed.is_(True),
        ).order_by(ScribeNoteVersion.version_no.desc()).first()
        assert row is not None
        # Deep copy to detach from the session so later reads compare independently.
        return copy.deepcopy(row.sections_json)


# ---------------------------------------------------------------------------


def test_addendum_appends_row_and_one_audit_no_new_version(monkeypatch) -> None:
    """Req 18.3/18.4/18.5: one addendum + one audit, no new version, signed bytes unchanged."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.add.basic@doctor.clara")
    sid = _create_session(token)
    ver = _progress_to_signed(token, sid)

    before_add, before_audit, before_versions = _counts(sid)
    before_sections = _signed_sections_snapshot(sid)
    # Serialize for a strict byte-for-byte comparison.
    before_bytes = json.dumps(before_sections, sort_keys=True, ensure_ascii=False)

    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(token),
        json={"text": "Patient called back: symptoms improved overnight."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"] == sid
    assert body["version_no"] == ver
    assert body["addendum_id"] > 0
    assert body["text"] == "Patient called back: symptoms improved overnight."
    assert body["created_at"] is not None

    after_add, after_audit, after_versions = _counts(sid)
    assert after_add == before_add + 1, "exactly one addendum row inserted"
    assert after_audit == before_audit + 1, "exactly one audit entry appended"
    assert after_versions == before_versions, "no new note version created"

    # Signed version sections_json is byte-for-byte unchanged.
    after_bytes = json.dumps(
        _signed_sections_snapshot(sid), sort_keys=True, ensure_ascii=False
    )
    assert after_bytes == before_bytes

    # The single new audit entry is the addendum action.
    with SessionLocal() as db:
        latest_audit = db.query(ScribeAudit).filter(
            ScribeAudit.session_id == sid
        ).order_by(ScribeAudit.id.desc()).first()
        assert latest_audit is not None
        assert latest_audit.action == "note_addendum_added"
        # No status transition (an addendum is not a lifecycle change).
        assert latest_audit.from_status == latest_audit.to_status == "signed"
        assert latest_audit.detail_json.get("version_no") == ver


def test_addendum_session_status_unchanged(monkeypatch) -> None:
    """Req 18.5: an addendum does not transition the session (still 'signed')."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.add.status@doctor.clara")
    sid = _create_session(token)
    ver = _progress_to_signed(token, sid)

    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(token), json={"text": "Follow-up note."},
    )
    assert r.status_code == 200, r.text

    g = client.get(f"/api/v1/scribe/sessions/{sid}", headers=_auth(token))
    assert g.status_code == 200, g.text
    assert g.json()["status"] == "signed"


def test_addendum_listed_in_append_order(monkeypatch) -> None:
    """Req 18.6: addenda are readable in append order via the read endpoint."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.add.list@doctor.clara")
    sid = _create_session(token)
    ver = _progress_to_signed(token, sid)

    for text in ("first addendum", "second addendum"):
        r = client.post(
            f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
            headers=_auth(token), json={"text": text},
        )
        assert r.status_code == 200, r.text

    lst = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addenda", headers=_auth(token)
    )
    assert lst.status_code == 200, lst.text
    addenda = lst.json()["addenda"]
    assert [a["text"] for a in addenda] == ["first addendum", "second addendum"]


def test_export_md_includes_demarcated_addendum_after_signed_content(monkeypatch) -> None:
    """Req 18.6: markdown export includes the addendum as a demarcated, time-stamped
    section AFTER the signed note content; signed sections preserved."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.add.exportmd@doctor.clara")
    sid = _create_session(token)
    _set_encounter(sid)
    ver = _progress_to_signed(token, sid)

    addtext = "Lab results received; no action required."
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(token), json={"text": addtext},
    )
    assert r.status_code == 200, r.text

    ex = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))
    assert ex.status_code == 200, ex.text
    md = ex.json()["markdown"]
    # Signed content still present.
    assert "s-text" in md and "p-text" in md
    # Demarcated, time-stamped addendum section.
    assert "## Addenda" in md
    assert "### Addendum —" in md
    assert addtext in md
    # The addendum appears AFTER the signed section content.
    assert md.index(addtext) > md.index("p-text")


def test_export_fhir_composition_includes_addendum_section(monkeypatch) -> None:
    """Req 18.6: fhir_composition export carries the addendum as a demarcated section;
    the signed template sections (1:1 correspondence) are preserved."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch, rag_scribe_fhir_composition_enabled=True)
    token = _login("dr.add.exportfhir@doctor.clara")
    sid = _create_session(token)
    _set_encounter(sid)
    ver = _progress_to_signed(token, sid)

    addtext = "Addendum body for FHIR."
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(token), json={"text": addtext},
    )
    assert r.status_code == 200, r.text

    ex = client.get(
        f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition", headers=_auth(token)
    )
    assert ex.status_code == 200, ex.text
    comp = ex.json()["composition"]
    titles = [s["title"] for s in comp["section"]]
    # The four signed template sections remain, in order, with one addendum section appended.
    assert titles[:4] == ["subjective", "objective", "assessment", "plan"]
    addendum_titles = [t for t in titles if t.startswith("Addendum")]
    assert len(addendum_titles) == 1
    addendum_section = next(s for s in comp["section"] if s["title"].startswith("Addendum"))
    assert addtext in addendum_section["text"]["div"]
    # The DocumentReference markdown attachment also carries the addendum (Req 18.6).
    doc_md = ex.json()["document_reference"]["content"][0]["attachment"]["data"]
    assert "## Addenda" in doc_md and addtext in doc_md


def test_addendum_flag_off_returns_404(monkeypatch) -> None:
    """Req 18.1: addendum disabled ⇒ endpoint not exposed (404)."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch, rag_scribe_addendum_enabled=False)
    token = _login("dr.add.flagoff@doctor.clara")
    sid = _create_session(token)
    ver = _progress_to_signed(token, sid)

    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(token), json={"text": "should not be accepted"},
    )
    assert r.status_code == 404, r.text


def test_addendum_on_unsigned_note_rejected(monkeypatch) -> None:
    """Req 18.2: an addendum attaches only to a SIGNED note version (unsigned ⇒ 409)."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.add.unsigned@doctor.clara")
    sid = _create_session(token)
    ver = _generate(token, sid)  # generated but NOT signed

    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(token), json={"text": "premature addendum"},
    )
    assert r.status_code == 409, r.text


def test_addendum_missing_version_returns_404(monkeypatch) -> None:
    """A non-existent note version ⇒ 404 (before any insert)."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.add.missingver@doctor.clara")
    sid = _create_session(token)
    _progress_to_signed(token, sid)

    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/999/addendum",
        headers=_auth(token), json={"text": "no such version"},
    )
    assert r.status_code == 404, r.text


def test_addendum_rbac_non_doctor_forbidden(monkeypatch) -> None:
    """RBAC: a non-doctor account is rejected with 403."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    owner = _login("dr.add.rbacowner@doctor.clara")
    sid = _create_session(owner)
    ver = _progress_to_signed(owner, sid)

    intruder = _login("plain.add.user@example.com")
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(intruder), json={"text": "x"},
    )
    assert r.status_code == 403, r.text


def test_addendum_owner_scope_non_owner_404(monkeypatch) -> None:
    """Owner-scoping: a clinician cannot add an addendum to another's session (404)."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    owner = _login("dr.add.scopeowner@doctor.clara")
    sid = _create_session(owner)
    ver = _progress_to_signed(owner, sid)

    other = _login("dr.add.scopeintruder@doctor.clara")
    r = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
        headers=_auth(other), json={"text": "x"},
    )
    assert r.status_code == 404, r.text
