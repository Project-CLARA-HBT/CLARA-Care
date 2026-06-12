"""Tests for streamed diarization-segment persistence (Task 2.5 / Req 3).

The streaming SSE relay (``POST /scribe/sessions/{id}/stream``) is a byte
passthrough; to make streamed segments relabelable (Req 3.3/3.4) the relay
additively captures the terminal ``done`` frame and persists its segments under
``asr_meta_json['segments']`` — the same key the relabel endpoint (task 2.4) reads.

These tests pin:
- the ``done`` SSE frame is parsed into its JSON payload,
- streamed segments (with speaker) are persisted under ``asr_meta_json['segments']``,
- default ``unknown`` speaker survives persistence (Req 3.2),
- persistence is additive: the session transcript text is NOT overwritten (Req 3.4),
- a ``segments_persisted`` audit entry is appended.
"""

from __future__ import annotations

from datetime import UTC, datetime

from clara_api.api.v1.endpoints.scribe import (
    _parse_sse_done_payload,
    _persist_stream_segments,
)
from clara_api.db.models import ScribeAudit, ScribeSession, User
from clara_api.db.session import SessionLocal


def _done_frames() -> str:
    return (
        "event: start\ndata: {}\n\n"
        'event: segment\ndata: {"index":0,"text":"bệnh nhân ho","speaker":"patient"}\n\n'
        'event: segment\ndata: {"index":1,"text":"khám phổi","speaker":"unknown"}\n\n'
        'event: done\ndata: {"transcript":"bệnh nhân ho khám phổi",'
        '"segments":[{"index":0,"text":"bệnh nhân ho","speaker":"patient"},'
        '{"index":1,"text":"khám phổi","speaker":"unknown"}],'
        '"note":null,"asr_meta":{"provider":"phowhisper","language":"vi","degraded_count":0}}\n\n'
    )


def test_parse_sse_done_payload_extracts_segments() -> None:
    payload = _parse_sse_done_payload(_done_frames())
    assert payload is not None
    assert payload["asr_meta"]["provider"] == "phowhisper"
    assert [s["speaker"] for s in payload["segments"]] == ["patient", "unknown"]


def test_parse_sse_done_payload_none_when_absent() -> None:
    buffer = "event: start\ndata: {}\n\nevent: segment\ndata: {\"index\":0}\n\n"
    assert _parse_sse_done_payload(buffer) is None


def _make_session() -> int:
    with SessionLocal() as db:
        user = User(
            email="dr.streampersist@doctor.clara",
            hashed_password="x",
            role="doctor",
            full_name="Dr Stream",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        now = datetime.now(tz=UTC)
        item = ScribeSession(
            user_id=user.id,
            title="t",
            status="draft",
            transcript="ORIGINAL TRANSCRIPT",
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id


def test_persist_stream_segments_writes_under_asr_meta_json() -> None:
    sid = _make_session()
    payload = _parse_sse_done_payload(_done_frames())
    assert payload is not None

    _persist_stream_segments(session_id=sid, actor_id=None, done_payload=payload)

    with SessionLocal() as db:
        item = db.get(ScribeSession, sid)
        assert item is not None
        meta = item.asr_meta_json
        assert isinstance(meta, dict)
        # Segments persisted under the same key the relabel endpoint reads (Req 3.3).
        assert [s["speaker"] for s in meta["segments"]] == ["patient", "unknown"]
        assert [s["text"] for s in meta["segments"]] == ["bệnh nhân ho", "khám phổi"]
        # asr_meta provider/language/degraded_count carried through (Req 2.5).
        assert meta["provider"] == "phowhisper"
        assert meta["language"] == "vi"
        assert meta["degraded_count"] == 0
        # Additive only: canonical transcript text is NOT overwritten (Req 3.4).
        assert item.transcript == "ORIGINAL TRANSCRIPT"

        actions = [
            r.action
            for r in db.query(ScribeAudit).filter(ScribeAudit.session_id == sid).all()
        ]
        assert "segments_persisted" in actions


def test_persist_default_unknown_speaker_preserved() -> None:
    """Req 3.2: a segment with no diarization (speaker unknown) persists as unknown."""

    sid = _make_session()
    payload = {
        "segments": [{"index": 0, "text": "hello", "speaker": "unknown"}],
        "asr_meta": {"provider": "whisper", "language": "en", "degraded_count": 0},
    }
    _persist_stream_segments(session_id=sid, actor_id=None, done_payload=payload)
    with SessionLocal() as db:
        item = db.get(ScribeSession, sid)
        assert item is not None
        assert item.asr_meta_json["segments"][0]["speaker"] == "unknown"


def test_persist_noop_when_no_segments() -> None:
    """No segments in the done frame ⇒ nothing persisted (legacy behavior unaffected)."""

    sid = _make_session()
    _persist_stream_segments(
        session_id=sid, actor_id=None, done_payload={"segments": [], "asr_meta": {}}
    )
    with SessionLocal() as db:
        item = db.get(ScribeSession, sid)
        assert item is not None
        assert item.asr_meta_json is None
