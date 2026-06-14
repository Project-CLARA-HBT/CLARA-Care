"""SSE contract tests for the Scribe streaming endpoint helper (task 1.1)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from clara_ml.config import settings
from clara_ml.main import app
from clara_ml.scribe.asr.base import AsrEvent, AsrResult, AsrSegment
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.streaming.scribe_stream import stream_scribe_sse

_client = TestClient(app)


def _no_sleep(_s: float) -> None:
    return None


def _kinds(frames):  # noqa: ANN001
    return [f.split("\n", 1)[0].removeprefix("event: ") for f in frames]


def _data(frame: str) -> dict:
    line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
    return json.loads(line[len("data: ") :])


class _FakeAsr:
    def __init__(self, result: AsrResult):
        self._result = result

    def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
        return self._result


def test_stream_emits_start_segments_done_with_transcript() -> None:
    asr = _FakeAsr(
        AsrResult(
            segments=[
                AsrSegment(text="bệnh nhân ho", speaker="patient"),
                AsrSegment(text="khám phổi rõ", speaker="clinician"),
            ],
            language="vi",
            provider="whisper",
        )
    )
    frames = list(
        stream_scribe_sse(b"audio", language="vi", asr=asr, generator=NoteGenerator(),
                          template_id="soap", segment_delay=0, token_delay=0, sleep=_no_sleep)
    )
    kinds = _kinds(frames)
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert kinds.count("segment") == 2
    done = _data(frames[-1])
    assert done["transcript"] == "bệnh nhân ho khám phổi rõ"
    assert done["note"]["template_id"] == "soap"
    assert set(done["note"]["sections"].keys()) == {"Subjective", "Objective", "Assessment", "Plan"}
    assert done["asr_meta"]["provider"] == "whisper"


def test_degraded_segment_forwarded_not_fabricated() -> None:
    asr = _FakeAsr(
        AsrResult(
            segments=[AsrSegment(text="", speaker="unknown", degraded=True)],
            language="vi",
            provider="whisper",
            degraded_count=1,
        )
    )
    frames = list(stream_scribe_sse(b"a", language="vi", asr=asr, segment_delay=0, sleep=_no_sleep))
    seg = next(_data(f) for f, k in zip(frames, _kinds(frames)) if k == "segment")
    assert seg["degraded"] is True
    assert seg["text"] == ""  # no fabricated text


def test_asr_failure_emits_terminal_error() -> None:
    class _BoomAsr:
        def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
            raise RuntimeError("asr down")

    frames = list(stream_scribe_sse(b"a", language="vi", asr=_BoomAsr(), sleep=_no_sleep))
    kinds = _kinds(frames)
    assert kinds[-1] == "error"
    assert _data(frames[-1])["error"] == "RuntimeError"


def test_no_generator_skips_note() -> None:
    asr = _FakeAsr(AsrResult(segments=[AsrSegment(text="hi")], language="en", provider="whisper"))
    frames = list(stream_scribe_sse(b"a", language="en", asr=asr, generator=None, segment_delay=0, sleep=_no_sleep))
    done = _data(frames[-1])
    assert done["note"] is None
    assert "token" not in _kinds(frames)


# --- Diarization gating tests (task 2.5, Requirement 3) ---


def _segments_of_done(frames) -> list[dict]:  # noqa: ANN001
    return _data(frames[-1])["segments"]


def test_diarization_enabled_surfaces_provider_speaker() -> None:
    """Req 3.1: with diarization on, provider speaker labels are surfaced."""

    asr = _FakeAsr(
        AsrResult(
            segments=[
                AsrSegment(text="bệnh nhân ho", speaker="patient"),
                AsrSegment(text="khám phổi rõ", speaker="clinician"),
            ],
            language="vi",
            provider="phowhisper",
        )
    )
    frames = list(
        stream_scribe_sse(
            b"audio", language="vi", asr=asr, diarization_enabled=True,
            segment_delay=0, sleep=_no_sleep,
        )
    )
    segs = _segments_of_done(frames)
    assert [s["speaker"] for s in segs] == ["patient", "clinician"]


def test_diarization_disabled_defaults_speaker_unknown() -> None:
    """Req 3.2: with diarization off, every speaker defaults to ``unknown``.

    Text + ordering are unchanged (Req 3.4): only the additive speaker label differs.
    """

    asr = _FakeAsr(
        AsrResult(
            segments=[
                AsrSegment(text="bệnh nhân ho", speaker="patient"),
                AsrSegment(text="khám phổi rõ", speaker="clinician"),
            ],
            language="vi",
            provider="phowhisper",
        )
    )
    frames = list(
        stream_scribe_sse(
            b"audio", language="vi", asr=asr, diarization_enabled=False,
            segment_delay=0, sleep=_no_sleep,
        )
    )
    segs = _segments_of_done(frames)
    assert [s["speaker"] for s in segs] == ["unknown", "unknown"]
    # Additive only: transcript text + segment order untouched (Req 3.4).
    assert [s["text"] for s in segs] == ["bệnh nhân ho", "khám phổi rõ"]
    assert _data(frames[-1])["transcript"] == "bệnh nhân ho khám phổi rõ"


def test_default_unknown_when_provider_returns_no_speaker() -> None:
    """Req 3.2: a provider that emits no speaker yields ``unknown`` (default)."""

    asr = _FakeAsr(
        AsrResult(segments=[AsrSegment(text="hi there")], language="en", provider="whisper")
    )
    frames = list(
        stream_scribe_sse(b"a", language="en", asr=asr, segment_delay=0, sleep=_no_sleep)
    )
    segs = _segments_of_done(frames)
    assert segs[0]["speaker"] == "unknown"


def test_diarization_disabled_streaming_path_defaults_unknown() -> None:
    """Req 3.2 on the streaming (stream(...)) path: speaker forced to unknown."""

    events = [
        AsrEvent(type="segment", segment=AsrSegment(text="a", speaker="patient"), text="a"),
        AsrEvent(type="segment", segment=AsrSegment(text="b", speaker="clinician"), text="b"),
    ]
    frames = list(
        stream_scribe_sse(
            b"audio", language="vi", asr=_StreamAsr(events), diarization_enabled=False,
            segment_delay=0, sleep=_no_sleep,
        )
    )
    segs = _segments_of_done(frames)
    assert [s["speaker"] for s in segs] == ["unknown", "unknown"]
    assert [s["text"] for s in segs] == ["a", "b"]


class _StreamAsr:
    """ASR provider exposing stream(...) that yields AsrEvents (production shape)."""

    def __init__(self, events):  # noqa: ANN001
        self._events = events

    def stream(self, audio_iter, *, language):  # noqa: ANN001
        for evt in self._events:
            yield evt

    def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
        # Should not be reached when the stream produces usable segments.
        raise AssertionError("batch path should not run when streaming succeeds")


def test_streaming_path_emits_partial_then_segment_then_done() -> None:
    events = [
        AsrEvent(type="segment", segment=AsrSegment(text="bệnh nhân ho", speaker="patient"),
                 text="bệnh nhân ho", detail={"provider": "phowhisper", "language": "vi"}),
        AsrEvent(type="segment", segment=AsrSegment(text="khám phổi rõ", speaker="clinician"),
                 text="khám phổi rõ", detail={"provider": "phowhisper", "language": "vi"}),
    ]
    frames = list(
        stream_scribe_sse(b"audio", language="vi", asr=_StreamAsr(events),
                          segment_delay=0, token_delay=0, sleep=_no_sleep)
    )
    kinds = _kinds(frames)
    assert kinds[0] == "start" and kinds[-1] == "done"
    # Requirement 1.3: both partial (interim) and segment (finalized) appear.
    assert kinds.count("partial") == 2
    assert kinds.count("segment") == 2
    # Interim partial precedes its finalized segment.
    assert kinds.index("partial") < kinds.index("segment")
    done = _data(frames[-1])
    assert done["transcript"] == "bệnh nhân ho khám phổi rõ"
    assert done["asr_meta"]["provider"] == "phowhisper"
    assert done["asr_meta"]["language"] == "vi"


def test_streaming_unavailable_falls_back_to_batch_then_done() -> None:
    """Stream yields a terminal error; batch fallback still produces a transcript."""

    class _StreamErrThenBatch:
        def stream(self, audio_iter, *, language):  # noqa: ANN001
            yield AsrEvent(type="error", detail={"reason": "asr_unavailable"})

        def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
            return AsrResult(segments=[AsrSegment(text="recovered")], language="vi", provider="whisper")

    frames = list(stream_scribe_sse(b"a", language="vi", asr=_StreamErrThenBatch(),
                                    segment_delay=0, sleep=_no_sleep))
    kinds = _kinds(frames)
    assert kinds[-1] == "done"  # batch fallback recovered the transcript
    assert kinds.count("segment") == 1
    assert _data(frames[-1])["transcript"] == "recovered"
    assert _data(frames[-1])["asr_meta"]["provider"] == "whisper"


def test_streaming_unavailable_and_batch_empty_emits_terminal_error() -> None:
    """Stream errors and batch yields nothing => terminal error names the failure class."""

    class _StreamErrEmptyBatch:
        def stream(self, audio_iter, *, language):  # noqa: ANN001
            yield AsrEvent(type="error", detail={"reason": "asr_unavailable"})

        def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
            return AsrResult(segments=[], language="vi", provider="composite")

    frames = list(stream_scribe_sse(b"a", language="vi", asr=_StreamErrEmptyBatch(),
                                    segment_delay=0, sleep=_no_sleep))
    kinds = _kinds(frames)
    assert kinds[-1] == "error"
    # Failure class is named, no raw provider internals.
    assert _data(frames[-1])["error"] == "asr_unavailable"


# --- Route-level tests for POST /v1/scribe/stream (flag gating, Requirement 1.1) ---


def test_route_returns_404_when_streaming_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag off => endpoint is inert (404) so legacy batch behavior is unchanged (Req 1.1)."""

    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", False, raising=False)
    resp = _client.post(
        "/v1/scribe/stream",
        files={"audio_file": ("encounter.webm", b"audio-bytes", "audio/webm")},
        data={"language": "vi"},
    )
    assert resp.status_code == 404
    assert "disabled" in resp.json()["detail"].lower()


def test_route_streams_sse_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag on => endpoint returns an SSE stream that starts and terminates cleanly (Req 1.2/1.3)."""

    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", True, raising=False)

    class _FakeComposite:
        def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
            return AsrResult(
                segments=[AsrSegment(text="bệnh nhân ho", speaker="patient")],
                language=language,
                provider="whisper",
            )

    monkeypatch.setattr("clara_ml.scribe.asr.build_asr_provider", lambda _s: _FakeComposite())

    resp = _client.post(
        "/v1/scribe/stream",
        files={"audio_file": ("encounter.webm", b"audio-bytes", "audio/webm")},
        data={"language": "vi"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert body.startswith("event: start")
    assert "event: segment" in body
    assert body.rstrip().endswith("\n\n".rstrip()) or "event: done" in body
    assert "event: done" in body
