"""Integration tests for the additive ASR WER reporting pass (task 7.2, Requirement 16).

``POST /scribe/sessions/{id}/notes`` runs the WER pass as an additive, non-blocking
pass when ``RAG_SCRIBE_WER_REPORTING_ENABLED`` is on, persisting the per-language
(and per-accent/speaker where available) measurement into the ``wer_json`` column of
the created ``ScribeNoteVersion`` without touching the note's section text. These
tests pin:

* flag ON ⇒ ``wer_json`` populated from the ML pass, the note ``sections_json`` text
  is byte-for-byte the generated note (additive, Req 16.5), and the ML pass is called
  with ``wer_enabled`` + the session's ``segments_meta`` + ``language`` (Req 16.2/16.3);
* flag OFF ⇒ ``wer_json`` stays null and the WER pass is not requested (Req 16.1);
* the WER pass is non-blocking — an ML pass failure leaves ``wer_json`` null while
  note generation still succeeds (Req 16.5);
* the persisted ``wer_json`` carries no transcript/patient text (PII-free, Req 16.4).

The ML pass endpoint is mocked through the shared ``proxy_ml_post`` seam (no real ML).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeNoteVersion, ScribeSession
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

# Canned PII-free ML WER report the mocked proxy returns for "/v1/scribe/passes".
_FAKE_WER = {
    "version": "scribe-wer-v1",
    "enabled": True,
    "by_language": [
        {
            "dimension": "language",
            "label": "vi",
            "method": "confidence_proxy",
            "value": 0.72,
            "segment_count": 2,
            "word_count": 6,
        }
    ],
    "by_accent": [],
    "by_speaker": [
        {
            "dimension": "speaker",
            "label": "clinician",
            "method": "confidence_proxy",
            "value": 0.8,
            "segment_count": 1,
            "word_count": 3,
        }
    ],
}
_FAKE_SOAP = {"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"}

# Distinctive PII tokens seeded into the session transcript / segments; they must
# never appear in the persisted wer_json.
_PII = ("NguyenVanWer", "0907654321", "secret-wer-transcript")


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


def _mock_ml(monkeypatch, *, capture: dict[str, Any] | None = None, fail: bool = False) -> None:
    """Mock the ML proxy: SOAP for note-gen, passes for the additive pass call."""

    from fastapi import HTTPException

    def fake_proxy(path: str, payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        if path == "/v1/scribe/passes":
            if capture is not None:
                capture["payload"] = payload
            if fail:
                raise HTTPException(status_code=502, detail="ml down")
            return {
                "grounding": {"enabled": False, "statements": []},
                "extraction": {"enabled": False, "medications": []},
                "wer": dict(_FAKE_WER),
            }
        return dict(_FAKE_SOAP)

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _enable(monkeypatch, **flags: bool) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rag_scribe_sign_workflow_enabled", True, raising=False)
    for name, value in flags.items():
        monkeypatch.setattr(settings, name, value, raising=False)


def _create_session_with_segments(token: str, email: str) -> int:
    """Create a session, then seed PII-bearing ASR segments into asr_meta_json."""

    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={
            "title": "t",
            "transcript": f"{_PII[0]} {_PII[1]} {_PII[2]}",
            "auto_generate_soap": False,
        },
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    with SessionLocal() as db:
        item = db.get(ScribeSession, sid)
        assert item is not None
        item.asr_meta_json = {
            "provider": "whisper",
            "language": "vi",
            "degraded_count": 0,
            "segments": [
                {"text": _PII[2], "speaker": "clinician", "confidence": 0.8, "degraded": False},
                {"text": _PII[0], "speaker": "patient", "confidence": 0.6, "degraded": False},
            ],
        }
        db.add(item)
        db.commit()
    return sid


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


def test_flag_on_persists_wer_json_and_passes_metadata(monkeypatch) -> None:
    """Req 16.2/16.3: flag on ⇒ wer_json populated + ML called with segments_meta/language."""

    capture: dict[str, Any] = {}
    _mock_ml(monkeypatch, capture=capture)
    _enable(monkeypatch, rag_scribe_wer_reporting_enabled=True)
    token = _login("dr.wer.on@doctor.clara")
    sid = _create_session_with_segments(token, "dr.wer.on@doctor.clara")
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    # Additive: note section text is the generated SOAP; no wer keys folded in.
    assert isinstance(row.sections_json, dict)
    assert row.sections_json["subjective"] == _FAKE_SOAP["subjective"]
    assert "wer" not in row.sections_json
    # wer_json persisted from the ML pass result.
    assert row.wer_json == _FAKE_WER

    # The ML pass was requested with the WER flag + the session's segment metadata
    # and language so the per-language / per-speaker breakdown is computable.
    payload = capture["payload"]
    assert payload["wer_enabled"] is True
    assert payload["language"] == "vi"
    assert len(payload["segments_meta"]) == 2
    assert payload["segments_meta"][0]["speaker"] == "clinician"


def test_flag_off_leaves_wer_json_null_and_skips_pass(monkeypatch) -> None:
    """Req 16.1: flag off ⇒ wer_json null and the WER pass is not requested."""

    capture: dict[str, Any] = {}
    _mock_ml(monkeypatch, capture=capture)
    _enable(monkeypatch, rag_scribe_wer_reporting_enabled=False)
    token = _login("dr.wer.off@doctor.clara")
    sid = _create_session_with_segments(token, "dr.wer.off@doctor.clara")
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    assert row.wer_json is None
    # With all additive flags off the passes endpoint is never called at all.
    assert "payload" not in capture


def test_wer_pass_is_non_blocking_on_ml_failure(monkeypatch) -> None:
    """Req 16.5: an ML pass failure never blocks note generation; wer_json stays null."""

    _mock_ml(monkeypatch, fail=True)
    _enable(monkeypatch, rag_scribe_wer_reporting_enabled=True)
    token = _login("dr.wer.fail@doctor.clara")
    sid = _create_session_with_segments(token, "dr.wer.fail@doctor.clara")
    # Note generation still succeeds even though the WER/passes call raised.
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    assert row.wer_json is None
    # The note itself was generated and persisted (workflow not blocked).
    assert row.sections_json["plan"] == _FAKE_SOAP["plan"]


def test_persisted_wer_json_is_pii_free(monkeypatch) -> None:
    """Req 16.4: the persisted wer_json carries no transcript/patient identifiers."""

    _mock_ml(monkeypatch)
    _enable(monkeypatch, rag_scribe_wer_reporting_enabled=True)
    token = _login("dr.wer.pii@doctor.clara")
    sid = _create_session_with_segments(token, "dr.wer.pii@doctor.clara")
    _generate_note(token, sid)

    row = _version_row(sid)
    assert row is not None
    serialized = json.dumps(row.wer_json, ensure_ascii=False)
    for pii in _PII:
        assert pii not in serialized, f"PII leaked into wer_json: {pii!r}"
