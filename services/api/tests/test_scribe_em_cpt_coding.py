"""Integration tests for the additive E/M + CPT coding pass + read endpoint.

Task 5.2 (_Req 14.3, 14.5_). ``POST /scribe/sessions/{id}/notes`` runs the E/M+CPT
coding pass (R14) as an additive pass when ``RAG_SCRIBE_EM_CPT_CODING_ENABLED`` is on,
persisting the result into the ``coding_json`` column of the created
``ScribeNoteVersion`` without touching the note's section text. A read endpoint
surfaces the persisted metadata under clinician RBAC + owner-scoping:

* ``GET /scribe/sessions/{id}/notes/{ver}/coding``

These tests pin:

* flags-on note generation populates ``coding_json`` + the read returns it, and the
  note ``sections_json`` text is byte-for-byte the generated note (additive, Req 14.7);
* every suggestion is advisory and ``selected=False`` from the server (Req 14.3/14.5);
* flags-off ⇒ the column stays null AND the read endpoint 404s (surface retracted);
* RBAC 403 for a non-doctor + owner-scope 404 for a non-owner clinician on the read.

The ML pass endpoint is mocked through the shared ``proxy_ml_post`` seam (no real ML).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeNoteVersion
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


# Canned ML pass result the mocked proxy returns for "/v1/scribe/passes". The
# coding payload mirrors the ML CodingResult.as_dict() shape: legacy Req 7 fields
# plus the additive em_cpt list (advisory, selected=False).
_FAKE_CODING = {
    "icd": [],
    "medications": [],
    "interactions": [],
    "advisory": True,
    "em_cpt": [
        {
            "code": "99214",
            "kind": "E/M",
            "system": "E/M",
            "display": "Office visit, level 4",
            "display_vi": "Khám phòng khám, mức 4",
            "level": 4,
            "spans": ["seg-0001"],
            "rationale": "moderate MDM",
            "selected": False,
            "status": "advisory",
        },
        {
            "code": "93000",
            "kind": "CPT",
            "system": "CPT",
            "display": "Electrocardiogram",
            "display_vi": "Điện tâm đồ",
            "level": None,
            "spans": ["seg-0002"],
            "rationale": "ECG performed",
            "selected": False,
            "status": "advisory",
        },
    ],
}
_FAKE_SOAP = {"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"}


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


def _mock_ml(monkeypatch) -> None:
    """Mock the ML proxy: SOAP for note-gen, coding for the additive pass call."""

    def fake_proxy(path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        if path == "/v1/scribe/passes":
            return {"grounding": None, "extraction": None, "coding": dict(_FAKE_CODING)}
        return dict(_FAKE_SOAP)

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _enable(monkeypatch, **flags: bool) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_sign_workflow_enabled", True, raising=False)
    for name, value in flags.items():
        monkeypatch.setattr(settings, name, value, raising=False)


def _create_session(token: str, transcript: str = "patient has cough") -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _generate_note(token: str, sid: int) -> None:
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    assert g.status_code == 200, g.text


def _version_row(sid: int):
    with SessionLocal() as db:
        return db.execute(
            select(ScribeNoteVersion)
            .where(ScribeNoteVersion.session_id == sid)
            .order_by(ScribeNoteVersion.version_no.asc())
        ).scalars().first()


def test_flag_on_populates_coding_and_read_returns_advisory_unselected(monkeypatch) -> None:
    """Req 14.3/14.5: flag on ⇒ coding_json populated + read returns it; text additive."""

    _mock_ml(monkeypatch)
    _enable(monkeypatch, rag_scribe_em_cpt_coding_enabled=True)
    token = _login("dr.emcpt.on@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    # The note section text is the generated SOAP content (additive, Req 14.7).
    assert isinstance(row.sections_json, dict)
    assert row.sections_json["subjective"] == _FAKE_SOAP["subjective"]
    assert "em_cpt" not in row.sections_json  # coding never folds into note text
    assert row.coding_json == _FAKE_CODING

    coding = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(token)
    )
    assert coding.status_code == 200, coding.text
    body = coding.json()
    assert body["session_id"] == sid and body["version_no"] == 1
    suggestions = body["coding"]["em_cpt"]
    assert {s["code"] for s in suggestions} == {"99214", "93000"}
    # Every suggestion is advisory and NOT auto-selected (Req 14.3/14.5).
    for s in suggestions:
        assert s["selected"] is False
        assert s["status"] == "advisory"
        assert s["spans"]  # justifying span(s) present (Req 14.2)


def test_flag_off_no_coding_persisted_and_read_404(monkeypatch) -> None:
    """Req 14.1: coding flag off ⇒ column null + read endpoint 404 (surface retracted)."""

    _mock_ml(monkeypatch)
    _enable(monkeypatch, rag_scribe_em_cpt_coding_enabled=False)
    token = _login("dr.emcpt.off@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    assert row.coding_json is None

    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(token)
    ).status_code == 404


def test_read_404_when_version_missing(monkeypatch) -> None:
    """Flag on but unknown version ⇒ 404 (no data), never a fabricated suggestion set."""

    _mock_ml(monkeypatch)
    _enable(monkeypatch, rag_scribe_em_cpt_coding_enabled=True)
    token = _login("dr.emcpt.missing@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/99/coding", headers=_auth(token)
    ).status_code == 404


def test_read_rbac_non_doctor_403(monkeypatch) -> None:
    """RBAC: a non-doctor account is rejected (403) on the coding read endpoint."""

    _mock_ml(monkeypatch)
    _enable(monkeypatch, rag_scribe_em_cpt_coding_enabled=True)
    owner = _login("dr.emcpt.owner@doctor.clara")
    sid = _create_session(owner)
    _generate_note(owner, sid)

    intruder = _login("plain.emcpt.user@example.com")  # non-doctor
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(intruder)
    ).status_code == 403


def test_read_owner_scoped_404_for_non_owner(monkeypatch) -> None:
    """Owner-scoping: a clinician cannot read another clinician's coding metadata."""

    _mock_ml(monkeypatch)
    _enable(monkeypatch, rag_scribe_em_cpt_coding_enabled=True)
    owner = _login("dr.emcpt.owner2@doctor.clara")
    sid = _create_session(owner)
    _generate_note(owner, sid)

    other = _login("dr.emcpt.intruder@doctor.clara")  # a doctor, but not the owner
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(other)
    ).status_code == 404
