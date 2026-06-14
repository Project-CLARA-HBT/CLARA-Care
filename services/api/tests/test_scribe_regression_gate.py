"""Flags-off regression gate for the API scribe surface (task 3.5, Req 11.2).

This is the standing regression gate that pins the core backward-compatibility
contract of the whole Clara Scribe enterprise feature: *with every wave-1 scribe
flag OFF, the observable API behavior is byte-for-byte the current batch
transcribe + SOAP + CRUD behavior* (Requirement 11.2). Concretely it asserts:

* the legacy ``POST /scribe/soap`` proxy returns the upstream ML payload verbatim
  (no enterprise wrapping / extra envelope);
* session CRUD response payloads carry EXACTLY the legacy field set — no enterprise
  metadata fields (grounding/extraction/coding/wer/quality/...) leak into the shape;
* ``GET /scribe/analytics/summary`` returns exactly the legacy summary fields;
* none of the flag-gated enterprise routes are exposed (notes/sign/amend/segment
  relabel/export/stream all 404), so the enterprise surface is fully retracted;
* the legacy ``POST /scribe/transcribe`` route stays mounted and is NOT consent-gated
  (consent-required defaults off), so the legacy ASR entry point is unchanged.

The flags are forced OFF explicitly (not relying on process env) so the gate is
deterministic regardless of how the suite is invoked.

Task 10.1 (_Req 11.2, 12.1, 13.1, 14.1, 15.1, 16.1, 17.1, 18.1, 19.1, 20.1_) folds
the wave-2 (R12–R20) flags into this same gate: with EVERY scribe flag off — all
wave-1 flags AND all wave-2 flags — the observable behavior is byte-for-byte the
current batch transcribe + SOAP + CRUD behavior. Concretely the wave-2 extension
additionally pins that:

* the additive ``ScribeNoteVersion`` metadata columns
  (``grounding_json`` / ``extraction_json`` / ``wer_json`` / ``quality_json``) are
  never present/populated — the legacy flow creates no note-version rows at all;
* the new addendum endpoints (attach + list) are inactive (404);
* the ``/scribe/analytics/quality`` endpoint is inactive (404);
* the ``fhir_composition`` export format is unavailable (404);
* the grounding/extraction read endpoints are retracted (404).

Uses the doctor auto-provision login (``*@doctor.clara``) + a mocked ML SOAP proxy;
no real ML calls.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeAudit, ScribeNoteVersion, ScribeSession
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


# The frozen legacy contracts. Adding an enterprise field to either of these
# response shapes (e.g. surfacing grounding/extraction on a session) would break
# byte-for-byte compatibility and MUST trip this gate.
_LEGACY_SESSION_FIELDS = {
    "id",
    "title",
    "status",
    "transcript",
    "soap",
    "insights",
    "metadata",
    "last_processed_at",
    "created_at",
    "updated_at",
}
_LEGACY_SUMMARY_FIELDS = {
    "total_sessions",
    "completed_sessions",
    "draft_sessions",
    "sessions_today",
    "avg_transcript_chars",
}

# Every wave-1 scribe flag. The gate forces all of these OFF.
_WAVE1_FLAGS = (
    "rag_scribe_streaming_enabled",
    "rag_scribe_diarization_enabled",
    "rag_scribe_consent_required",
    "rag_scribe_templates_enabled",
    "rag_scribe_coding_enabled",
    "rag_scribe_sign_workflow_enabled",
    "rag_scribe_export_enabled",
    "rag_scribe_fhir_export_enabled",
)

# Every wave-2 (R12–R20) scribe flag (task 10.1). The gate forces all of these OFF
# too, so the full enterprise surface — grounding, structured extraction, E/M+CPT
# coding, quality metrics, WER reporting, FHIR Composition, addendum, specialty
# templates, eval gate — is retracted alongside the wave-1 surface.
_WAVE2_FLAGS = (
    "rag_scribe_grounding_enabled",
    "rag_scribe_structured_extraction_enabled",
    "rag_scribe_em_cpt_coding_enabled",
    "rag_scribe_quality_metrics_enabled",
    "rag_scribe_wer_reporting_enabled",
    "rag_scribe_fhir_composition_enabled",
    "rag_scribe_addendum_enabled",
    "rag_scribe_specialty_templates_enabled",
    "rag_scribe_eval_gate_enabled",
)

# The full set the gate pins OFF: byte-for-byte current behavior holds only when
# EVERY scribe flag (wave-1 + wave-2) is off (Req 11.2).
_ALL_SCRIBE_FLAGS = _WAVE1_FLAGS + _WAVE2_FLAGS

# The legacy ML SOAP payload the proxy should pass through verbatim.
_FAKE_SOAP = {
    "subjective": {"chief_complaint": "cough"},
    "objective": {"vitals": {}, "findings": []},
    "assessment": {"problems": ["Persistent cough"], "acuity": "moderate"},
    "plan": {"next_steps": ["follow up"], "follow_up": "24-72h"},
    "metadata": {"pipeline": "p2-scribe-soap-v2", "fallback_used": True},
}


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
        return dict(_FAKE_SOAP)

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _all_flags_off(monkeypatch) -> None:
    settings = get_settings()
    for flag in _ALL_SCRIBE_FLAGS:
        monkeypatch.setattr(settings, flag, False, raising=False)


def _create_session(token: str, *, auto: bool = False) -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": "patient has cough", "auto_generate_soap": auto},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_legacy_soap_proxy_passthrough_unchanged(monkeypatch) -> None:
    """Req 11.2: ``/scribe/soap`` returns the ML payload verbatim, no enterprise envelope."""

    _all_flags_off(monkeypatch)
    _mock_soap(monkeypatch)
    token = _login("dr.gate.soap@doctor.clara")

    r = client.post(
        "/api/v1/scribe/soap", headers=_auth(token), json={"transcript": "cough"}
    )
    assert r.status_code == 200, r.text
    # Byte-for-byte: the proxy response equals the upstream ML payload exactly.
    assert r.json() == _FAKE_SOAP


def test_session_crud_payload_has_only_legacy_fields(monkeypatch) -> None:
    """Req 11.2: session create/get/list responses carry exactly the legacy field set.

    No enterprise metadata (grounding/extraction/coding/wer/quality/encounter/...)
    leaks into the observable session shape when the flags are off.
    """

    _all_flags_off(monkeypatch)
    _mock_soap(monkeypatch)
    token = _login("dr.gate.crud@doctor.clara")

    created = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": "patient has cough", "auto_generate_soap": True},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["id"]
    assert set(created.json().keys()) == _LEGACY_SESSION_FIELDS

    got = client.get(f"/api/v1/scribe/sessions/{sid}", headers=_auth(token))
    assert got.status_code == 200, got.text
    assert set(got.json().keys()) == _LEGACY_SESSION_FIELDS
    # Auto-generated SOAP is persisted via the legacy normalize path (S/O/A/P +
    # long-form keys); the upstream content is carried through unchanged. We assert
    # the legacy normalized key set + content passthrough, not an enterprise shape.
    soap = got.json()["soap"]
    assert set(soap.keys()) == {
        "subjective", "objective", "assessment", "plan", "S", "O", "A", "P"
    }
    assert soap["subjective"] == _FAKE_SOAP["subjective"]
    assert soap["assessment"] == _FAKE_SOAP["assessment"]

    listed = client.get("/api/v1/scribe/sessions", headers=_auth(token))
    assert listed.status_code == 200, listed.text
    assert set(listed.json().keys()) == {"items", "total"}
    for item in listed.json()["items"]:
        assert set(item.keys()) == _LEGACY_SESSION_FIELDS


def test_analytics_summary_payload_unchanged(monkeypatch) -> None:
    """Req 11.2: ``/scribe/analytics/summary`` returns exactly the legacy summary fields."""

    _all_flags_off(monkeypatch)
    _mock_soap(monkeypatch)
    token = _login("dr.gate.analytics@doctor.clara")
    _create_session(token)

    r = client.get("/api/v1/scribe/analytics/summary", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert set(r.json().keys()) == _LEGACY_SUMMARY_FIELDS


def test_enterprise_routes_not_exposed_with_flags_off(monkeypatch) -> None:
    """Req 11.1/11.2: every flag-gated enterprise route is retracted (404) with flags off.

    The owner is a legitimate clinician, so a 404 here is flag-gating (the enterprise
    surface does not exist), not RBAC/owner-scoping. This is the "none of the
    enterprise routes exposed" half of the byte-for-byte contract.
    """

    _all_flags_off(monkeypatch)
    _mock_soap(monkeypatch)
    token = _login("dr.gate.routes@doctor.clara")
    sid = _create_session(token)

    audio = {"audio_file": ("s.webm", b"audio-bytes", "audio/webm")}
    gated = [
        ("notes", client.post(
            f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(token),
            json={"template_id": "soap"})),
        ("sign", client.post(
            f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))),
        ("amend", client.post(
            f"/api/v1/scribe/sessions/{sid}/amend", headers=_auth(token),
            json={"template_id": "soap"})),
        ("segment_relabel", client.patch(
            f"/api/v1/scribe/sessions/{sid}/segments/0", headers=_auth(token),
            json={"speaker": "patient"})),
        ("export", client.get(
            f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))),
        ("stream", client.post(
            f"/api/v1/scribe/sessions/{sid}/stream", headers=_auth(token), files=audio)),
        # --- wave-2 (R12–R20) enterprise routes (task 10.1) ---
        ("grounding_read", client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/grounding", headers=_auth(token))),
        ("extraction_read", client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/extraction", headers=_auth(token))),
        ("addendum_attach", client.post(
            f"/api/v1/scribe/sessions/{sid}/notes/1/addendum", headers=_auth(token),
            json={"text": "late finding"})),
        ("addenda_list", client.get(
            f"/api/v1/scribe/sessions/{sid}/notes/1/addenda", headers=_auth(token))),
        ("analytics_quality", client.get(
            "/api/v1/scribe/analytics/quality", headers=_auth(token))),
        ("export_fhir_composition", client.get(
            f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition",
            headers=_auth(token))),
    ]
    for label, resp in gated:
        assert resp.status_code == 404, f"{label}: expected flag-off 404, got {resp.status_code}"


def test_legacy_transcribe_route_mounted_and_not_consent_gated(monkeypatch) -> None:
    """Req 11.2: the legacy ``/scribe/transcribe`` entry point is unchanged.

    With consent-required OFF the consent guard never engages, and the route stays
    mounted: a malformed request reaches request validation (422), proving the route
    is exposed (a flag-retracted route would 404 before validation). This pins that
    the legacy ASR entry point is neither removed nor newly consent-gated.
    """

    _all_flags_off(monkeypatch)
    token = _login("dr.gate.transcribe@doctor.clara")

    # No audio_file part => FastAPI request validation rejects with 422, NOT 404.
    r = client.post("/api/v1/scribe/transcribe", headers=_auth(token), data={"language": "vi"})
    assert r.status_code == 422, r.text
    assert get_settings().rag_scribe_consent_required is False


def test_legacy_crud_writes_no_enterprise_audit_rows(monkeypatch) -> None:
    """Req 11.2: the legacy create+regenerate flow writes no enterprise audit trail.

    The append-only ``ScribeAudit`` table is an enterprise (wave-1) addition; with the
    flags off the legacy CRUD path must not emit any audit rows for a session, so the
    persisted side effects are byte-for-byte the legacy set.
    """

    _all_flags_off(monkeypatch)
    _mock_soap(monkeypatch)
    token = _login("dr.gate.audit@doctor.clara")
    sid = _create_session(token, auto=True)

    regen = client.post(
        f"/api/v1/scribe/sessions/{sid}/regenerate", headers=_auth(token), json={}
    )
    assert regen.status_code == 200, regen.text

    with SessionLocal() as db:
        session_row = db.get(ScribeSession, sid)
        assert session_row is not None
        audit_rows = db.execute(
            select(ScribeAudit).where(ScribeAudit.session_id == sid)
        ).scalars().all()
        assert audit_rows == [], "legacy CRUD must not write enterprise audit rows"


def test_legacy_flow_creates_no_note_version_rows_or_additive_columns(monkeypatch) -> None:
    """Req 11.2/12.1/13.1/15.1/16.1: the additive note-version metadata is never present.

    The wave-2 additive metadata (``grounding_json`` / ``extraction_json`` /
    ``wer_json`` / ``quality_json``) lives on ``ScribeNoteVersion`` rows, which are
    created only by the flag-gated sign/note workflow. With every flag off the legacy
    create+regenerate flow persists SOAP onto the session itself and creates NO
    ``ScribeNoteVersion`` rows — so none of the additive columns are ever present or
    populated (they cannot leak into the byte-for-byte legacy behavior).
    """

    _all_flags_off(monkeypatch)
    _mock_soap(monkeypatch)
    token = _login("dr.gate.versions@doctor.clara")
    sid = _create_session(token, auto=True)

    regen = client.post(
        f"/api/v1/scribe/sessions/{sid}/regenerate", headers=_auth(token), json={}
    )
    assert regen.status_code == 200, regen.text

    with SessionLocal() as db:
        version_rows = db.execute(
            select(ScribeNoteVersion).where(ScribeNoteVersion.session_id == sid)
        ).scalars().all()
        assert version_rows == [], "legacy flow must not create enterprise note-version rows"
        # Defensive: even if a row somehow existed, every additive column must be null.
        for row in version_rows:
            assert row.grounding_json is None
            assert row.extraction_json is None
            assert row.wer_json is None
            assert row.quality_json is None


def test_quality_analytics_endpoint_inactive_with_flags_off(monkeypatch) -> None:
    """Req 15.1/11.2: the enterprise ``/analytics/quality`` surface is retracted (404).

    The legacy ``/analytics/summary`` stays available and unchanged (asserted in
    ``test_analytics_summary_payload_unchanged``); the wave-7 quality surface is
    fully retracted with the flags off.
    """

    _all_flags_off(monkeypatch)
    token = _login("dr.gate.quality@doctor.clara")

    resp = client.get("/api/v1/scribe/analytics/quality", headers=_auth(token))
    assert resp.status_code == 404, resp.text
