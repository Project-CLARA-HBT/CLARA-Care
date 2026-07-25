"""End-to-end integration tests for the wave-2 scribe endpoints *together* (task 10.2).

The per-endpoint suites already pin each wave-2 surface in isolation:

* ``test_scribe_grounding_extraction.py`` — grounding/extraction reads;
* ``test_scribe_em_cpt_coding.py`` — E/M+CPT coding read;
* ``test_scribe_addendum.py`` — addendum attach + listing + export demarcation;
* ``test_scribe_export.py`` — ``fhir_composition`` Composition/Encounter export;
* ``test_scribe_analytics_quality.py`` / ``test_scribe_wer_persist.py`` — quality + WER.

What none of them exercise — and what task 10.2 asks for — is the **new endpoints
working together end-to-end in one session lifecycle with every wave-2 flag enabled
simultaneously**, proving the additive passes cooperate (grounding + extraction +
E/M/CPT + WER all populate on the same note without interfering), the read endpoints
surface each report, and the signed-note → addendum → ``fhir_composition`` → quality
analytics chain holds across components. This file fills that gap and also closes the
cross-route RBAC / owner-scoping / flags-off matrix for the wave-2 read + quality
surfaces (``test_scribe_rbac_integration.py`` covers consent/notes/sign/amend/audit/
relabel/export/stream but not grounding/extraction/coding/addenda reads or
``/analytics/quality``).

The ML proxy is mocked through the shared ``proxy_ml_post`` seam (no real ML calls).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeAddendum, ScribeAudit, ScribeNoteVersion, ScribeSession
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

# Distinctive PII tokens seeded into transcript / segments; they must never leak
# into the additive metadata or the quality-analytics payload.
_PII = ("NguyenVanWave2", "0900112233", "secret-wave2-transcript")

_FAKE_SOAP = {"subjective": "s-text", "objective": "o-text", "assessment": "a-text",
              "plan": "p-text"}

# Every additive pass result returned together for a single note-gen call, so the
# combined flow proves the passes cooperate (none clobbers another's column).
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
        }
    ],
}
_FAKE_WER = {
    "version": "scribe-wer-v1",
    "enabled": True,
    "by_language": [
        {"dimension": "language", "label": "vi", "method": "confidence_proxy",
         "value": 0.72, "segment_count": 2, "word_count": 6}
    ],
    "by_accent": [],
    "by_speaker": [
        {"dimension": "speaker", "label": "clinician", "method": "confidence_proxy",
         "value": 0.8, "segment_count": 1, "word_count": 3}
    ],
}

# The wave-2 feature flags (all default off ⇒ legacy). The combined flow flips them
# all on at once so the endpoints are exercised together.
_WAVE2_FLAGS = (
    "rag_scribe_grounding_enabled",
    "rag_scribe_structured_extraction_enabled",
    "rag_scribe_em_cpt_coding_enabled",
    "rag_scribe_wer_reporting_enabled",
    "rag_scribe_fhir_composition_enabled",
    "rag_scribe_addendum_enabled",
    "rag_scribe_quality_metrics_enabled",
)


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


def _mock_ml(monkeypatch, *, capture: dict[str, Any] | None = None) -> None:
    """Mock the ML proxy: SOAP for note-gen, ALL passes for the additive pass call."""

    def fake_proxy(path: str, payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        if path == "/v1/scribe/passes":
            if capture is not None:
                capture["payload"] = payload
            return {
                "grounding": dict(_FAKE_GROUNDING),
                "extraction": dict(_FAKE_EXTRACTION),
                "coding": dict(_FAKE_CODING),
                "wer": dict(_FAKE_WER),
            }
        return dict(_FAKE_SOAP)

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _enable_wave2(monkeypatch, value: bool = True) -> None:
    """Flip every wave-2 flag (+ sign/export workflow) to ``value`` at once."""

    settings = get_settings()
    for flag in (
        "rag_scribe_sign_workflow_enabled",
        "rag_scribe_export_enabled",
        *_WAVE2_FLAGS,
    ):
        monkeypatch.setattr(settings, flag, value, raising=False)


def _create_session(token: str) -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={
            "title": "Wave2 Visit",
            "transcript": f"{_PII[0]} {_PII[1]} {_PII[2]}",
            "auto_generate_soap": False,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _seed_encounter_and_segments(sid: int) -> None:
    """Stamp opaque encounter context + PII-bearing ASR segments onto the session."""

    with SessionLocal() as db:
        item = db.get(ScribeSession, sid)
        assert item is not None
        item.encounter_json = {
            "visit_type": "follow-up",
            "encounter_at": "2026-04-10T09:30:00+00:00",
            "patient_ref": "opaque-patient-123",
        }
        item.asr_meta_json = {
            "provider": "whisper",
            "language": "vi",
            "degraded_count": 1,
            "segments": [
                {"text": _PII[2], "speaker": "clinician", "confidence": 0.8, "degraded": True},
                {"text": _PII[0], "speaker": "patient", "confidence": 0.6, "degraded": False},
            ],
        }
        db.add(item)
        db.commit()


def _generate_note(token: str, sid: int) -> None:
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    assert g.status_code == 200, g.text


def _sign(token: str, sid: int) -> None:
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 200, s.text
    assert s.json()["status"] == "signed"


def _version_row(sid: int) -> ScribeNoteVersion | None:
    with SessionLocal() as db:
        return db.execute(
            select(ScribeNoteVersion)
            .where(ScribeNoteVersion.session_id == sid)
            .order_by(ScribeNoteVersion.version_no.asc())
        ).scalars().first()


# ---------------------------------------------------------------------------
# 1. The full wave-2 lifecycle with every flag on, exercising the new endpoints
#    together: generate (all passes) → read grounding/extraction/coding → sign →
#    addendum → fhir_composition export (incl. addendum) → quality analytics.
# ---------------------------------------------------------------------------


def test_wave2_endpoints_cooperate_end_to_end(monkeypatch) -> None:
    capture: dict[str, Any] = {}
    _mock_ml(monkeypatch, capture=capture)
    _enable_wave2(monkeypatch)
    token = _login("dr.w2.flow@doctor.clara")
    sid = _create_session(token)
    _seed_encounter_and_segments(sid)

    # --- generate: every additive pass populates its own column, none clobbered ---
    _generate_note(token, sid)
    row = _version_row(sid)
    assert row is not None
    # Additive: the note section text carries the generated SOAP content verbatim
    # and no pass folded its payload into the clinical text.
    assert isinstance(row.sections_json, dict)
    for key, value in _FAKE_SOAP.items():
        assert row.sections_json[key] == value
    for leaked in ("grounding", "extraction", "em_cpt", "wer"):
        assert leaked not in row.sections_json
    assert row.grounding_json == _FAKE_GROUNDING
    assert row.extraction_json == _FAKE_EXTRACTION
    assert row.coding_json == _FAKE_CODING
    assert row.wer_json == _FAKE_WER
    # The single passes call carried every pass flag + the session ASR metadata.
    payload = capture["payload"]
    assert payload["grounding_enabled"] is True
    assert payload["extraction_enabled"] is True
    assert payload["coding_enabled"] is True
    assert payload["wer_enabled"] is True
    assert payload["language"] == "vi"
    assert len(payload["segments_meta"]) == 2

    # --- grounding read ---
    g = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(token)
    )
    assert g.status_code == 200, g.text
    gbody = g.json()
    assert gbody["session_id"] == sid and gbody["version_no"] == 1
    assert gbody["grounding"]["grounded_claim_rate"] == 1.0
    assert gbody["grounding"]["statements"][0]["status"] == "grounded"

    # --- extraction read ---
    e = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(token)
    )
    assert e.status_code == 200, e.text
    assert e.json()["extraction"]["medications"][0]["rxcui"] == "29046"

    # --- coding read (advisory, unselected) ---
    c = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(token)
    )
    assert c.status_code == 200, c.text
    suggestion = c.json()["coding"]["em_cpt"][0]
    assert suggestion["code"] == "99214"
    assert suggestion["selected"] is False and suggestion["status"] == "advisory"

    # --- sign → addendum (no new version, one audit, signed bytes unchanged) ---
    signed_bytes = json.dumps(row.sections_json, sort_keys=True, ensure_ascii=False)
    _sign(token, sid)
    with SessionLocal() as db:
        before_versions = db.query(ScribeNoteVersion).filter(
            ScribeNoteVersion.session_id == sid
        ).count()
        before_audit = db.query(ScribeAudit).filter(
            ScribeAudit.session_id == sid
        ).count()

    addtext = "Patient called back: symptoms improved overnight."
    a = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/1/addendum",
        headers=_auth(token), json={"text": addtext},
    )
    assert a.status_code == 200, a.text

    with SessionLocal() as db:
        after_versions = db.query(ScribeNoteVersion).filter(
            ScribeNoteVersion.session_id == sid
        ).count()
        after_audit = db.query(ScribeAudit).filter(
            ScribeAudit.session_id == sid
        ).count()
        addenda = db.query(ScribeAddendum).filter(
            ScribeAddendum.session_id == sid
        ).count()
        signed_row = db.query(ScribeNoteVersion).filter(
            ScribeNoteVersion.session_id == sid,
            ScribeNoteVersion.signed.is_(True),
        ).one()
        after_bytes = json.dumps(
            signed_row.sections_json, sort_keys=True, ensure_ascii=False
        )
    assert after_versions == before_versions, "addendum creates no new note version"
    assert after_audit == before_audit + 1, "exactly one audit entry for the addendum"
    assert addenda == 1
    assert after_bytes == signed_bytes, "signed sections byte-for-byte unchanged"

    # --- addenda listing ---
    lst = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/addenda", headers=_auth(token)
    )
    assert lst.status_code == 200, lst.text
    assert [x["text"] for x in lst.json()["addenda"]] == [addtext]

    # --- fhir_composition export: Composition + Encounter + DocumentReference,
    #     with the addendum as a demarcated section after the signed content ---
    ex = client.get(
        f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition",
        headers=_auth(token),
    )
    assert ex.status_code == 200, ex.text
    body = ex.json()
    assert body["format"] == "fhir_composition"
    comp = body["composition"]
    assert comp["resourceType"] == "Composition"
    titles = [s["title"] for s in comp["section"]]
    assert titles[:4] == ["subjective", "objective", "assessment", "plan"]
    # The signed template sections round-trip the note content.
    assert "s-text" in comp["section"][0]["text"]["div"]
    # The addendum rides along as exactly one demarcated section.
    addendum_titles = [t for t in titles if t.startswith("Addendum")]
    assert len(addendum_titles) == 1
    addendum_section = next(s for s in comp["section"] if s["title"].startswith("Addendum"))
    assert addtext in addendum_section["text"]["div"]
    # Encounter derived from the opaque, non-PII encounter context.
    enc = body["encounter"]
    assert enc["resourceType"] == "Encounter"
    assert enc["class"]["code"] == "follow-up"
    assert enc["subject"]["reference"] == "opaque-patient-123"
    # DocumentReference still emitted alongside, carrying the addendum.
    doc_md = body["document_reference"]["content"][0]["attachment"]["data"]
    assert "## Addenda" in doc_md and addtext in doc_md

    # --- quality analytics: the same session surfaces grounded-claim rate + the
    #     structural proxy, derived from the persisted (non-PII) metadata ---
    q = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert q.status_code == 200, q.text
    qbody = q.json()
    encounters = [e for e in qbody["encounters"] if e["session_id"] == sid]
    assert len(encounters) == 1
    qenc = encounters[0]
    # Grounded-claim rate sourced from this note's grounding_json.
    assert qenc["grounded_claim_rate"] == 1.0
    # The canonical SOAP template has four populated sections. Alias keys are
    # only part of the legacy session CRUD projection, not persisted note
    # template sections, so completeness is measured against these four.
    assert qenc["pdqi9_structural_proxy"] == 1.0
    assert qenc["degraded_rate"] == 0.5  # one of two segments degraded
    # PII-free: no seeded transcript/patient token survives anywhere in the payload.
    serialized = json.dumps(qbody)
    for pii in _PII:
        assert pii not in serialized, f"PII leaked into quality payload: {pii!r}"


# ---------------------------------------------------------------------------
# 2. Combined flags-off retraction: every NEW wave-2 surface is gone at once.
# ---------------------------------------------------------------------------


def test_wave2_new_endpoints_all_retracted_when_flags_off(monkeypatch) -> None:
    """All wave-2 flags off ⇒ each new endpoint 404s; the legacy note-gen still works.

    Generating a note with the flags off leaves every additive column null, so the
    read endpoints have nothing to surface and the gated routes are not exposed —
    the observable shape is the legacy one (complements task 10.1's byte-for-byte gate).
    """

    _mock_ml(monkeypatch)
    # Keep sign workflow on (so a note can be generated) but every wave-2 flag off.
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_sign_workflow_enabled", True, raising=False)
    monkeypatch.setattr(settings, "rag_scribe_export_enabled", True, raising=False)
    for flag in _WAVE2_FLAGS:
        monkeypatch.setattr(settings, flag, False, raising=False)

    token = _login("dr.w2.off@doctor.clara")
    sid = _create_session(token)
    _seed_encounter_and_segments(sid)
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    # No additive column populated with the flags off.
    assert row.grounding_json is None
    assert row.extraction_json is None
    assert row.coding_json is None
    assert row.wer_json is None

    _sign(token, sid)

    # Every new wave-2 surface retracted (404).
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(token)
    ).status_code == 404
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(token)
    ).status_code == 404
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(token)
    ).status_code == 404
    assert client.post(
        f"/api/v1/scribe/sessions/{sid}/notes/1/addendum",
        headers=_auth(token), json={"text": "x"},
    ).status_code == 404
    assert client.get(
        f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition",
        headers=_auth(token),
    ).status_code == 404
    assert client.get(
        "/api/v1/scribe/analytics/quality", headers=_auth(token)
    ).status_code == 404


# ---------------------------------------------------------------------------
# 3. Cross-route RBAC + owner-scoping for the NEW wave-2 read + quality surfaces
#    (the gap in test_scribe_rbac_integration.py, which omits these endpoints).
# ---------------------------------------------------------------------------


def _wave2_read_routes(sid: int) -> list[tuple[str, Callable[[str], Any]]]:
    return [
        ("grounding", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(t))),
        ("extraction", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(t))),
        ("coding", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/coding", headers=_auth(t))),
        ("addendum", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/notes/1/addendum", headers=_auth(t),
            json={"text": "x"})),
        ("addenda", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/addenda", headers=_auth(t))),
        ("fhir_composition", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition",
            headers=_auth(t))),
    ]


def test_wave2_read_surfaces_reject_non_doctor_403(monkeypatch) -> None:
    """RBAC: a non-doctor is rejected (403) on every wave-2 read + quality surface.

    RBAC runs as a route dependency before any flag/ownership check, so the 403
    holds even with every wave-2 flag enabled.
    """

    _mock_ml(monkeypatch)
    _enable_wave2(monkeypatch)
    owner = _login("dr.w2.rbac.owner@doctor.clara")
    sid = _create_session(owner)
    _seed_encounter_and_segments(sid)
    _generate_note(owner, sid)
    _sign(owner, sid)

    intruder = _login("plain.w2.user@example.com")  # non-doctor
    for label, call in _wave2_read_routes(sid):
        assert call(intruder).status_code == 403, f"{label}: expected 403"
    # The session-independent quality analytics surface is also doctor-gated.
    assert client.get(
        "/api/v1/scribe/analytics/quality", headers=_auth(intruder)
    ).status_code == 403


def test_wave2_read_surfaces_owner_scoped_404(monkeypatch) -> None:
    """Owner-scoping: a clinician cannot reach another clinician's wave-2 metadata.

    Flags are ON so the 404 reflects owner-scoping, not flag-gating.
    """

    _mock_ml(monkeypatch)
    _enable_wave2(monkeypatch)
    owner = _login("dr.w2.scope.owner@doctor.clara")
    sid = _create_session(owner)
    _seed_encounter_and_segments(sid)
    _generate_note(owner, sid)
    _sign(owner, sid)

    other = _login("dr.w2.scope.intruder@doctor.clara")  # a doctor, but not the owner
    for label, call in _wave2_read_routes(sid):
        assert call(other).status_code == 404, f"{label}: expected 404"
