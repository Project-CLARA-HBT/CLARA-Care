"""Derived per-encounter analytics endpoint tests (Requirement 10.1/10.4).

``GET /scribe/analytics/derived`` exposes coarse time-saved / edit-rate /
degraded-rate derived purely from persisted non-PII session metadata. These
tests assert:
- metrics are derived correctly from seeded note versions + ASR metadata,
- the output contains NO seeded transcript substring or patient identifier
  (PII-free, Req 10.1),
- metrics are omitted when their input is unavailable (omit-on-missing, Req 10.4),
- the legacy ``/analytics/summary`` payload is left unchanged (additive).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from clara_api.db.models import ScribeNoteVersion, ScribeSession, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

# Seeded "PII" tokens that must never leak into the analytics payload.
_PII_TOKENS = ("Nguyen", "0901234567", "warfarin", "secret-history-text")


def _login(email: str = "dr.derived@doctor.clara") -> str:
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


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        return user.id


def _seed_session(
    *,
    email: str,
    transcript: str,
    note_versions: list[dict] | None = None,
    asr_meta: dict | None = None,
) -> int:
    """Insert a ScribeSession (+ optional note versions / asr_meta) directly."""

    uid = _user_id(email)
    with SessionLocal() as db:
        item = ScribeSession(
            user_id=uid,
            title="visit",
            status="draft",
            transcript=transcript,
            asr_meta_json=asr_meta,
        )
        db.add(item)
        db.flush()
        for idx, sections in enumerate(note_versions or [], start=1):
            db.add(
                ScribeNoteVersion(
                    session_id=item.id,
                    version_no=idx,
                    template_id="soap",
                    sections_json=sections,
                    created_by=uid,
                )
            )
        db.commit()
        return item.id


def test_derived_metrics_computed_from_seeded_metadata() -> None:
    email = "dr.derived.calc@doctor.clara"
    token = _login(email)
    _seed_session(
        email=email,
        transcript=f"{_PII_TOKENS[0]} {_PII_TOKENS[1]} {_PII_TOKENS[2]}",
        note_versions=[
            {"S": "patient reports a cough", "P": "rest"},
            {"S": "patient reports a dry cough", "P": "rest and fluids"},
        ],
        asr_meta={
            "provider": "whisper",
            "language": "vi",
            "segments": [
                {"text": "seg one", "degraded": True},
                {"text": "seg two", "degraded": False},
                {"text": "seg three", "degraded": False},
                {"text": "seg four", "degraded": False},
            ],
        },
    )

    resp = client.get("/api/v1/scribe/analytics/derived", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["encounters"]) == 1
    enc = body["encounters"][0]
    # Edits happened between v1 and v2 -> edit rate strictly positive, bounded.
    assert 0.0 < enc["edit_rate"] <= 1.0
    assert enc["time_saved_minutes"] >= 0.0
    # 1 of 4 segments degraded.
    assert enc["degraded_rate"] == 0.25

    # Aggregate reflects the single encounter.
    assert body["aggregate"]["degraded_rate"] == 0.25
    assert "edit_rate" in body["aggregate"]


def test_derived_output_is_pii_free() -> None:
    email = "dr.derived.pii@doctor.clara"
    token = _login(email)
    _seed_session(
        email=email,
        transcript=" ".join(_PII_TOKENS),
        note_versions=[
            # Note text itself carries seeded PII to prove it never leaks out.
            {"S": f"{_PII_TOKENS[0]} prescribed {_PII_TOKENS[2]}", "P": _PII_TOKENS[3]},
            {"S": f"{_PII_TOKENS[0]} prescribed {_PII_TOKENS[2]} daily", "P": _PII_TOKENS[3]},
        ],
        asr_meta={"segments": [{"text": _PII_TOKENS[3], "degraded": True}]},
    )

    resp = client.get("/api/v1/scribe/analytics/derived", headers=_auth(token))
    assert resp.status_code == 200
    serialized = json.dumps(resp.json())
    for pii in _PII_TOKENS:
        assert pii not in serialized
    # Every emitted metric value is a bounded number, never text.
    for enc in resp.json()["encounters"]:
        for key, value in enc.items():
            if key == "session_id":
                continue
            assert value is None or isinstance(value, (int, float))


def test_derived_omits_metrics_when_input_unavailable() -> None:
    email = "dr.derived.omit@doctor.clara"
    token = _login(email)
    # Session A: note versions but NO asr_meta -> degraded_rate omitted (null).
    _seed_session(
        email=email,
        transcript="some transcript",
        note_versions=[{"S": "generated"}, {"S": "generated edited"}],
        asr_meta=None,
    )
    # Session B: asr_meta but NO note versions -> edit/time omitted (null).
    _seed_session(
        email=email,
        transcript="another transcript",
        note_versions=[],
        asr_meta={"segments": [{"degraded": True}, {"degraded": False}]},
    )
    # Session C: neither -> no derivable signal -> excluded entirely.
    _seed_session(email=email, transcript="bare", note_versions=[], asr_meta=None)

    resp = client.get("/api/v1/scribe/analytics/derived", headers=_auth(token))
    assert resp.status_code == 200
    encounters = resp.json()["encounters"]
    # Only A and B produce a derivable signal; C is omitted.
    assert len(encounters) == 2

    by_signal = {
        "note_only": next(e for e in encounters if e["edit_rate"] is not None),
        "asr_only": next(e for e in encounters if e["degraded_rate"] is not None),
    }
    # Note-only encounter: degraded_rate omitted.
    assert by_signal["note_only"]["degraded_rate"] is None
    # ASR-only encounter: edit/time omitted.
    assert by_signal["asr_only"]["edit_rate"] is None
    assert by_signal["asr_only"]["time_saved_minutes"] is None


def test_legacy_summary_payload_unchanged() -> None:
    # Additive guarantee: /analytics/summary keeps exactly its legacy key set.
    token = _login("dr.derived.legacy@doctor.clara")
    summary = client.get("/api/v1/scribe/analytics/summary", headers=_auth(token))
    assert summary.status_code == 200
    assert set(summary.json().keys()) == {
        "total_sessions",
        "completed_sessions",
        "draft_sessions",
        "sessions_today",
        "avg_transcript_chars",
    }
