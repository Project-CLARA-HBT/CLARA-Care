"""Integration tests for the additive grounding/extraction passes + read endpoints.

Task 4.5 (_Req 12.7, 13_). ``POST /scribe/sessions/{id}/notes`` runs the grounding
(R12) + structured-extraction (R13) passes as additive passes when the flags are on,
persisting the results into the ``grounding_json`` / ``extraction_json`` columns of
the created ``ScribeNoteVersion`` without touching the note's section text. Two read
endpoints surface the persisted metadata under clinician RBAC + owner-scoping:

* ``GET /scribe/sessions/{id}/notes/{ver}/grounding``
* ``GET /scribe/sessions/{id}/notes/{ver}/extraction``

These tests pin:

* flags-on note generation populates both columns + the read endpoints return them,
  and the note ``sections_json`` text is byte-for-byte the generated note (additive);
* flags-off ⇒ the columns stay null AND the read endpoints 404 (surface retracted);
* RBAC 403 for a non-doctor + owner-scope 404 for a non-owner clinician on the reads.

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


# Canned ML pass result the mocked proxy returns for "/v1/scribe/passes".
_FAKE_GROUNDING = {
    "version": "scribe-grounding-v1",
    "enabled": True,
    "statements": [
        {
            "statement": "Start lisinopril 10mg once daily",
            "section": "plan",
            "significant": True,
            "critical_safety": True,
            "grounded": True,
            "supporting_span_ids": ["seg-0002"],
            "method": "nli",
            "status": "grounded",
            "asserted": True,
            "fact_check": "pass",
        }
    ],
    "grounded_claim_rate": 1.0,
    "unverified_candidates": [],
    "total_significant": 1,
    "grounded_significant": 1,
}
_FAKE_EXTRACTION = {
    "version": "scribe-extraction-v1",
    "enabled": True,
    "problems": [],
    "medications": [
        {
            "surface": "lisinopril",
            "rxcui": "29046",
            "span_ids": ["seg-0002:6-16"],
            "method": "lexicon",
        }
    ],
    "allergies": [],
    "vitals": [],
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
    """Mock the ML proxy: SOAP for note-gen, passes for the additive pass call."""

    def fake_proxy(path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        if path == "/v1/scribe/passes":
            return {"grounding": dict(_FAKE_GROUNDING), "extraction": dict(_FAKE_EXTRACTION)}
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


def test_flags_on_populate_columns_and_reads_return_metadata(monkeypatch) -> None:
    """Req 12.7/13: flags on ⇒ columns populated + read endpoints return them; text additive."""

    _mock_ml(monkeypatch)
    _enable(
        monkeypatch,
        rag_scribe_grounding_enabled=True,
        rag_scribe_structured_extraction_enabled=True,
    )
    token = _login("dr.ge.on@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    # The note section text is the generated SOAP content, with the additive
    # metadata living in dedicated columns (the passes never fold into sections).
    row = _version_row(sid)
    assert row is not None
    assert isinstance(row.sections_json, dict)
    assert row.sections_json["subjective"] == _FAKE_SOAP["subjective"]
    assert row.sections_json["plan"] == _FAKE_SOAP["plan"]
    # No grounding/extraction keys leaked into the note's section text.
    assert "grounding" not in row.sections_json
    assert "extraction" not in row.sections_json
    assert row.grounding_json == _FAKE_GROUNDING
    assert row.extraction_json == _FAKE_EXTRACTION

    grounding = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(token)
    )
    assert grounding.status_code == 200, grounding.text
    body = grounding.json()
    assert body["session_id"] == sid and body["version_no"] == 1
    assert body["grounding"]["grounded_claim_rate"] == 1.0
    assert body["grounding"]["statements"][0]["status"] == "grounded"

    extraction = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(token)
    )
    assert extraction.status_code == 200, extraction.text
    ebody = extraction.json()
    assert ebody["session_id"] == sid and ebody["version_no"] == 1
    assert ebody["extraction"]["medications"][0]["rxcui"] == "29046"


def test_only_grounding_flag_on_populates_only_grounding(monkeypatch) -> None:
    """Req 13.1: extraction flag off ⇒ extraction column null + extraction read 404."""

    _mock_ml(monkeypatch)
    _enable(
        monkeypatch,
        rag_scribe_grounding_enabled=True,
        rag_scribe_structured_extraction_enabled=False,
    )
    token = _login("dr.ge.gonly@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    assert row.grounding_json == _FAKE_GROUNDING
    assert row.extraction_json is None

    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(token)
    ).status_code == 200
    # Extraction flag off ⇒ the read endpoint is retracted (404), not empty data.
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(token)
    ).status_code == 404


def test_flags_off_no_metadata_persisted_and_reads_404(monkeypatch) -> None:
    """Req 12.1/13.1: both flags off ⇒ columns null + both read endpoints 404."""

    _mock_ml(monkeypatch)
    _enable(
        monkeypatch,
        rag_scribe_grounding_enabled=False,
        rag_scribe_structured_extraction_enabled=False,
    )
    token = _login("dr.ge.off@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    assert row.grounding_json is None
    assert row.extraction_json is None

    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(token)
    ).status_code == 404
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(token)
    ).status_code == 404


def test_read_404_when_version_missing_or_no_data(monkeypatch) -> None:
    """Flag on but unknown version ⇒ 404 (no data), never a fabricated report."""

    _mock_ml(monkeypatch)
    _enable(
        monkeypatch,
        rag_scribe_grounding_enabled=True,
        rag_scribe_structured_extraction_enabled=True,
    )
    token = _login("dr.ge.missing@doctor.clara")
    sid = _create_session(token)
    _generate_note(token, sid)

    # Version 99 does not exist.
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/99/grounding", headers=_auth(token)
    ).status_code == 404
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/99/extraction", headers=_auth(token)
    ).status_code == 404


def test_reads_rbac_non_doctor_403(monkeypatch) -> None:
    """RBAC: a non-doctor account is rejected (403) on both read endpoints."""

    _mock_ml(monkeypatch)
    _enable(
        monkeypatch,
        rag_scribe_grounding_enabled=True,
        rag_scribe_structured_extraction_enabled=True,
    )
    owner = _login("dr.ge.owner@doctor.clara")
    sid = _create_session(owner)
    _generate_note(owner, sid)

    intruder = _login("plain.ge.user@example.com")  # non-doctor
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(intruder)
    ).status_code == 403
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(intruder)
    ).status_code == 403


def test_reads_owner_scoped_404_for_non_owner(monkeypatch) -> None:
    """Owner-scoping: a clinician cannot read another clinician's note metadata."""

    _mock_ml(monkeypatch)
    _enable(
        monkeypatch,
        rag_scribe_grounding_enabled=True,
        rag_scribe_structured_extraction_enabled=True,
    )
    owner = _login("dr.ge.owner2@doctor.clara")
    sid = _create_session(owner)
    _generate_note(owner, sid)

    other = _login("dr.ge.intruder@doctor.clara")  # a doctor, but not the owner
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(other)
    ).status_code == 404
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(other)
    ).status_code == 404
