"""Focused tests for the Scribe note export endpoint (Task 2.6 / Requirement 9).

Covers:
- DOCX export for a signed note reuses the workspace DOCX render path and returns
  a binary .docx attachment (Req 9.1).
- Markdown and FHIR exports include the encounter context, the signing clinician +
  sign timestamp, and the required source/medical attribution (Req 9.2/9.3).
- Exporting a draft is rejected with 409 (Req 9.4).
- Export flag off ⇒ 404; FHIR flag off ⇒ 404 (Req 11.1).

Uses the doctor auto-provision login + a mocked ML SOAP proxy (no real ML calls).
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeSession
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _login(email: str = "dr.export@doctor.clara") -> str:
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
    """Stamp an opaque, non-PII encounter context onto the session."""

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


def _progress_to_signed(token: str, sid: int) -> None:
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
        json={"template_id": "soap"},
    )
    assert g.status_code == 200, g.text
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 200, s.text
    assert s.json()["status"] == "signed"


def test_docx_export_returns_docx_attachment(monkeypatch) -> None:
    """Req 9.1: DOCX export reuses the workspace render path and returns a .docx file."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.docx@doctor.clara")
    sid = _create_session(token)
    _set_encounter(sid)
    _progress_to_signed(token, sid)

    r = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=docx", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert _DOCX_MEDIA_TYPE in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    assert len(r.content) > 200

    # It is a real DOCX (zip with word/document.xml) carrying the note + attribution.
    with zipfile.ZipFile(io.BytesIO(r.content), mode="r") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Visit Note" in document_xml
    assert "follow-up" in document_xml
    assert "Signed by" in document_xml
    assert "attribution" in document_xml.lower()


def test_markdown_export_includes_attribution(monkeypatch) -> None:
    """Req 9.2: markdown export includes encounter, signer + timestamp, attribution."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch)
    token = _login("dr.md@doctor.clara")
    sid = _create_session(token)
    _set_encounter(sid)
    _progress_to_signed(token, sid)

    r = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "md"
    md = body["markdown"]
    # Template sections.
    assert "s-text" in md and "p-text" in md
    # Encounter context.
    assert "follow-up" in md
    assert "opaque-patient-123" in md
    assert "2026-04-10T09:30:00" in md
    # Signing clinician + sign timestamp.
    assert "Signed by:" in md
    assert "Signed at:" in md
    # Required source/medical attribution.
    assert "attribution" in md.lower()
    assert "disclaimer" in md.lower()


def test_fhir_export_includes_attribution(monkeypatch) -> None:
    """Req 9.3: FHIR DocumentReference carries encounter, signer, and attribution."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch, rag_scribe_fhir_export_enabled=True)
    token = _login("dr.fhir@doctor.clara")
    sid = _create_session(token)
    _set_encounter(sid)
    _progress_to_signed(token, sid)

    r = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=fhir", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["format"] == "fhir"
    doc = body["document_reference"]
    assert doc["resourceType"] == "DocumentReference"
    # Signing clinician + sign timestamp.
    assert doc["author"] and doc["author"][0]["display"]
    assert doc["date"] is not None
    # Encounter context (opaque, non-PII).
    assert doc["context"]["encounter_context"]["visit_type"] == "follow-up"
    assert doc["context"]["encounter_context"]["patient_ref"] == "opaque-patient-123"
    # Required source/medical attribution travels with the resource.
    assert "attribution" in doc["meta"]
    # Embedded markdown attachment also carries the attribution.
    assert "disclaimer" in doc["content"][0]["attachment"]["data"].lower()


def test_draft_export_rejected_all_formats(monkeypatch) -> None:
    """Req 9.4: exporting a draft is rejected (409) for every format."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch, rag_scribe_fhir_export_enabled=True)
    token = _login("dr.draft@doctor.clara")
    sid = _create_session(token)
    for fmt in ("md", "docx", "fhir"):
        r = client.get(f"/api/v1/scribe/sessions/{sid}/export?format={fmt}", headers=_auth(token))
        assert r.status_code == 409, f"{fmt}: {r.text}"


def test_export_flag_off_returns_404(monkeypatch) -> None:
    """Req 11.1: export disabled ⇒ endpoint not exposed (404)."""

    _mock_soap(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_export_enabled", False, raising=False)
    token = _login("dr.flagoff.export@doctor.clara")
    sid = _create_session(token)
    r = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=docx", headers=_auth(token))
    assert r.status_code == 404


def test_fhir_flag_off_returns_404_even_when_signed(monkeypatch) -> None:
    """Req 11.1: FHIR export gated independently; off ⇒ 404 (md/docx still work)."""

    _mock_soap(monkeypatch)
    _enable(monkeypatch, rag_scribe_fhir_export_enabled=False)
    token = _login("dr.fhiroff@doctor.clara")
    sid = _create_session(token)
    _progress_to_signed(token, sid)
    r = client.get(f"/api/v1/scribe/sessions/{sid}/export?format=fhir", headers=_auth(token))
    assert r.status_code == 404
