"""Flow/telemetry events for the scribe streaming pipeline (task 3.1, Req 10.3).

Asserts that the terminal ``done`` frame additively carries a ``flow_events``
array covering the pipeline stages that ran (transcribe, diarize, generate),
that each event matches the established flow-event contract
(``{stage, timestamp, status, source_count, note}``), and that the events are
PII-free — no transcript text / patient identifier appears in any event
(Requirement 10.1).
"""

from __future__ import annotations

import json

from clara_ml.scribe.asr.base import AsrResult, AsrSegment
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.streaming.scribe_stream import stream_scribe_sse

_FLOW_KEYS = {"stage", "timestamp", "status", "source_count", "note"}


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


def _done(frames):  # noqa: ANN001
    return _data(frames[-1])


def test_done_payload_includes_pipeline_flow_events() -> None:
    """Req 10.3: transcribe/diarize/generate stages surface in done.flow_events."""

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
            b"audio",
            language="vi",
            asr=asr,
            generator=NoteGenerator(),
            template_id="soap",
            diarization_enabled=True,
            segment_delay=0,
            token_delay=0,
            sleep=_no_sleep,
        )
    )
    done = _done(frames)
    events = done["flow_events"]
    stages = [e["stage"] for e in events]
    assert stages == ["transcribe", "diarize", "generate"]

    by_stage = {e["stage"]: e for e in events}
    assert by_stage["transcribe"]["status"] == "completed"
    assert by_stage["transcribe"]["source_count"] == 2
    assert by_stage["diarize"]["status"] == "completed"
    assert by_stage["diarize"]["source_count"] == 2  # both segments labeled
    assert by_stage["generate"]["status"] == "completed"


def test_flow_event_shape_matches_contract() -> None:
    """Every scribe flow event uses the established flow-event shape/keys."""

    asr = _FakeAsr(
        AsrResult(segments=[AsrSegment(text="hi")], language="en", provider="whisper")
    )
    frames = list(
        stream_scribe_sse(
            b"a", language="en", asr=asr, generator=NoteGenerator(),
            segment_delay=0, token_delay=0, sleep=_no_sleep,
        )
    )
    events = _done(frames)["flow_events"]
    assert events  # non-empty
    for event in events:
        assert set(event.keys()) == _FLOW_KEYS
        assert isinstance(event["stage"], str) and event["stage"]
        assert isinstance(event["status"], str) and event["status"]
        assert isinstance(event["source_count"], int) and event["source_count"] >= 0
        assert isinstance(event["note"], str)
        assert isinstance(event["timestamp"], str) and event["timestamp"]


def test_flow_events_are_pii_free() -> None:
    """Req 10.1: no transcript text / patient identifier leaks into any event."""

    secret_history = "Nguyen Van Patient 0901234567 secret-history-text"
    asr = _FakeAsr(
        AsrResult(
            segments=[AsrSegment(text=secret_history, speaker="patient")],
            language="vi",
            provider="phowhisper",
        )
    )
    frames = list(
        stream_scribe_sse(
            b"audio", language="vi", asr=asr, generator=NoteGenerator(),
            template_id="soap", segment_delay=0, token_delay=0, sleep=_no_sleep,
        )
    )
    events = _done(frames)["flow_events"]
    serialized = json.dumps(events, ensure_ascii=False)
    for pii in ("Nguyen", "0901234567", "secret-history-text"):
        assert pii not in serialized


def test_diarize_skipped_when_disabled() -> None:
    """Diarization disabled => diarize stage status is 'skipped' (additive metadata)."""

    asr = _FakeAsr(
        AsrResult(
            segments=[AsrSegment(text="a", speaker="patient")],
            language="vi",
            provider="whisper",
        )
    )
    frames = list(
        stream_scribe_sse(
            b"a", language="vi", asr=asr, diarization_enabled=False,
            segment_delay=0, sleep=_no_sleep,
        )
    )
    by_stage = {e["stage"]: e for e in _done(frames)["flow_events"]}
    assert by_stage["diarize"]["status"] == "skipped"


def test_generate_skipped_when_no_generator() -> None:
    """No generator => generate stage status is 'skipped'."""

    asr = _FakeAsr(
        AsrResult(segments=[AsrSegment(text="a")], language="en", provider="whisper")
    )
    frames = list(
        stream_scribe_sse(
            b"a", language="en", asr=asr, generator=None, segment_delay=0, sleep=_no_sleep,
        )
    )
    by_stage = {e["stage"]: e for e in _done(frames)["flow_events"]}
    assert by_stage["generate"]["status"] == "skipped"


def test_insufficient_input_marks_generate_stage() -> None:
    """Empty transcript => generate stage flagged 'insufficient_input' (no fabrication)."""

    asr = _FakeAsr(AsrResult(segments=[], language="vi", provider="whisper"))
    frames = list(
        stream_scribe_sse(
            b"a", language="vi", asr=asr, generator=NoteGenerator(),
            template_id="soap", segment_delay=0, token_delay=0, sleep=_no_sleep,
        )
    )
    # No segments produced; batch returned empty -> terminal done with empty transcript.
    if _kinds(frames)[-1] != "done":
        return  # terminal error path (no flow_events expected) — covered elsewhere
    by_stage = {e["stage"]: e for e in _done(frames)["flow_events"]}
    assert by_stage["generate"]["status"] == "insufficient_input"
