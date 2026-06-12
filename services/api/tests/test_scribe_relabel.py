"""Focused tests for the Scribe segment-relabel endpoint (Task 2.4 / Req 3.3, 3.4).

Requirement 3.3: the clinician can re-assign a segment's speaker label, and the
change persists on the session.
Requirement 3.4: diarization labels never alter, drop, or reorder the underlying
transcript text (a relabel is additive metadata only).

These tests pin:
- the relabel persists the new speaker (3.3),
- segment text + ordering are byte-for-byte unchanged after relabel (3.4),
- an invalid label is rejected (422),
- a ``segment_relabeled`` audit entry is appended (8.3),
- a non-owner clinician gets 404 (owner-scoped),
- the endpoint is flag-gated (off ⇒ 404; legacy behavior unchanged).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeAudit, ScribeSession
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


_SEGMENTS = [
    {
        "text": "Good morning, what brings you in?",
        "speaker": "unknown",
        "start_ms": 0,
        "end_ms": 1800,
    },
    {
        "text": "I have had a cough for three days.",
        "speaker": "unknown",
        "start_ms": 1800,
        "end_ms": 3600,
    },
    {"text": "Any fever?", "speaker": "unknown", "start_ms": 3600, "end_ms": 4200},
]


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


def _enable_diarization(monkeypatch) -> None:
    monkeypatch.setattr(
        get_settings(), "rag_scribe_diarization_enabled", True, raising=False
    )


def _create_session(token: str, *, with_segments: bool = True) -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": "patient has cough", "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    if with_segments:
        _seed_segments(sid)
    return sid


def _seed_segments(session_id: int) -> None:
    """Persist diarization segments directly (no public write API yet)."""

    with SessionLocal() as db:
        item = db.get(ScribeSession, session_id)
        assert item is not None
        item.asr_meta_json = {
            "provider": "whisper",
            "language": "en",
            "degraded_count": 0,
            "segments": [dict(seg) for seg in _SEGMENTS],
        }
        item.updated_at = datetime.now(tz=UTC)
        db.add(item)
        db.commit()


def _segments_of(session_id: int) -> list[dict]:
    with SessionLocal() as db:
        item = db.get(ScribeSession, session_id)
        assert item is not None
        return list(item.asr_meta_json["segments"])


def _audit_actions(session_id: int) -> list[str]:
    with SessionLocal() as db:
        rows = (
            db.query(ScribeAudit)
            .filter(ScribeAudit.session_id == session_id)
            .order_by(ScribeAudit.id.asc())
            .all()
        )
        return [r.action for r in rows]


def _url(sid: int, seg: int) -> str:
    return f"/api/v1/scribe/sessions/{sid}/segments/{seg}"


def test_relabel_persists_new_speaker(monkeypatch) -> None:
    """Req 3.3: re-assigning a segment's speaker persists on the session."""

    _enable_diarization(monkeypatch)
    token = _login("dr.relabel1@doctor.clara")
    sid = _create_session(token)

    r = client.patch(_url(sid, 1), headers=_auth(token), json={"speaker": "patient"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["from_speaker"] == "unknown"
    assert body["to_speaker"] == "patient"

    # Persisted on the session.
    segs = _segments_of(sid)
    assert segs[1]["speaker"] == "patient"


def test_relabel_preserves_text_and_ordering(monkeypatch) -> None:
    """Req 3.4: relabel is additive metadata only — text + ordering unchanged."""

    _enable_diarization(monkeypatch)
    token = _login("dr.relabel2@doctor.clara")
    sid = _create_session(token)

    before = _segments_of(sid)
    before_text = [s["text"] for s in before]

    # Relabel multiple segments to different speakers.
    r0 = client.patch(_url(sid, 0), headers=_auth(token), json={"speaker": "clinician"})
    r1 = client.patch(_url(sid, 1), headers=_auth(token), json={"speaker": "patient"})
    assert r0.status_code == 200
    assert r1.status_code == 200

    after = _segments_of(sid)
    after_text = [s["text"] for s in after]

    # Same count, same order, identical text byte-for-byte.
    assert after_text == before_text
    # Timings (all non-speaker metadata) are untouched.
    assert [s["start_ms"] for s in after] == [s["start_ms"] for s in before]
    assert [s["end_ms"] for s in after] == [s["end_ms"] for s in before]
    # Only the speaker labels changed where requested.
    assert after[0]["speaker"] == "clinician"
    assert after[1]["speaker"] == "patient"
    assert after[2]["speaker"] == "unknown"


def test_relabel_rejects_invalid_label(monkeypatch) -> None:
    """Req 3.1/3.3: a speaker outside the bounded label set is rejected (422)."""

    _enable_diarization(monkeypatch)
    token = _login("dr.relabel3@doctor.clara")
    sid = _create_session(token)

    r = client.patch(_url(sid, 0), headers=_auth(token), json={"speaker": "robot"})
    assert r.status_code == 422, r.text
    # Segment is untouched.
    assert _segments_of(sid)[0]["speaker"] == "unknown"


def test_relabel_writes_audit_entry(monkeypatch) -> None:
    """Req 8.3: relabel appends a `segment_relabeled` audit entry with detail."""

    _enable_diarization(monkeypatch)
    token = _login("dr.relabel4@doctor.clara")
    sid = _create_session(token)

    client.patch(_url(sid, 2), headers=_auth(token), json={"speaker": "clinician"})
    assert "segment_relabeled" in _audit_actions(sid)

    with SessionLocal() as db:
        row = (
            db.query(ScribeAudit)
            .filter(
                ScribeAudit.session_id == sid,
                ScribeAudit.action == "segment_relabeled",
            )
            .one()
        )
        assert row.detail_json == {
            "segment": 2,
            "from_speaker": "unknown",
            "to_speaker": "clinician",
        }


def test_relabel_missing_segment_index_404(monkeypatch) -> None:
    """Req 3.3: an out-of-range segment index returns 404."""

    _enable_diarization(monkeypatch)
    token = _login("dr.relabel5@doctor.clara")
    sid = _create_session(token)

    r = client.patch(_url(sid, 99), headers=_auth(token), json={"speaker": "patient"})
    assert r.status_code == 404
    # A session with no persisted segments at all also 404s.
    sid2 = _create_session(token, with_segments=False)
    r2 = client.patch(_url(sid2, 0), headers=_auth(token), json={"speaker": "patient"})
    assert r2.status_code == 404


def test_relabel_non_owner_gets_404(monkeypatch) -> None:
    """Owner-scoped: a non-owner clinician cannot relabel another's segment."""

    _enable_diarization(monkeypatch)
    owner = _login("dr.relabel.owner@doctor.clara")
    sid = _create_session(owner)
    other = _login("dr.relabel.intruder@doctor.clara")

    r = client.patch(_url(sid, 0), headers=_auth(other), json={"speaker": "patient"})
    assert r.status_code == 404


def test_relabel_flag_off_returns_404(monkeypatch) -> None:
    """Req 11.1: with diarization disabled the endpoint is not exposed (404)."""

    monkeypatch.setattr(
        get_settings(), "rag_scribe_diarization_enabled", False, raising=False
    )
    token = _login("dr.relabel6@doctor.clara")
    sid = _create_session(token)

    r = client.patch(_url(sid, 0), headers=_auth(token), json={"speaker": "patient"})
    assert r.status_code == 404
    # Segment is untouched (legacy behavior preserved).
    assert _segments_of(sid)[0]["speaker"] == "unknown"
