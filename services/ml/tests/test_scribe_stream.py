"""SSE contract tests for the Scribe streaming endpoint helper (task 1.1)."""

from __future__ import annotations

import json

from clara_ml.scribe.asr.base import AsrResult, AsrSegment
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.streaming.scribe_stream import stream_scribe_sse


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
