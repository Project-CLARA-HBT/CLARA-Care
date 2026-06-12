"""Property 3 (degraded path): a degraded ASR chunk never yields fabricated text.

Property 3 has two halves. The empty/unusable-transcript half (all sections empty
+ ``insufficient_input``) is covered by ``test_scribe_generator_properties.py``.
This module covers the *streaming* half (Requirement 1.4): for ANY sequence of ASR
segments — including degraded chunks with arbitrary/empty text — the SSE pipeline
forwards each segment's text byte-for-byte and never substitutes fabricated text
for a degraded chunk, and the assembled transcript is exactly the concatenation of
the non-empty segment texts in order.

Validates: Requirements 1.4, 6.4
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.scribe.asr.base import SPEAKERS, AsrResult, AsrSegment
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.streaming.scribe_stream import stream_scribe_sse


def _no_sleep(_s: float) -> None:
    return None


def _kinds(frames: list[str]) -> list[str]:
    return [f.split("\n", 1)[0].removeprefix("event: ") for f in frames]


def _data(frame: str) -> dict:
    # Frame is "event: <type>\ndata: <json>\n\n". Split on the LITERAL "\ndata: "
    # delimiter (never str.splitlines(), which also breaks on unicode separators
    # like NEL/U+0085 that can legitimately appear inside the JSON payload).
    body = frame.split("\ndata: ", 1)[1]
    return json.loads(body.rstrip("\n"))


class _FakeAsr:
    """Batch-only provider returning a fixed :class:`AsrResult` (no fabrication)."""

    def __init__(self, result: AsrResult) -> None:
        self._result = result

    def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
        return self._result


# A degraded chunk may carry empty OR non-empty text; either way the pipeline
# must forward it verbatim and never invent replacement text.
_segment = st.builds(
    AsrSegment,
    text=st.text(max_size=40),
    speaker=st.sampled_from(SPEAKERS),
    degraded=st.booleans(),
)
_segments = st.lists(_segment, min_size=1, max_size=8)


# Feature: clara-scribe-enterprise, Property 3 (degraded streaming): no fabrication
# Validates: Requirements 1.4, 6.4
@settings(max_examples=200, deadline=None)
@given(segments=_segments)
def test_p3_degraded_chunk_text_is_never_fabricated(segments: list[AsrSegment]) -> None:
    result = AsrResult(
        segments=segments,
        language="vi",
        provider="whisper",
        degraded_count=sum(1 for s in segments if s.degraded),
    )
    frames = list(
        stream_scribe_sse(
            b"audio",
            language="vi",
            asr=_FakeAsr(result),
            generator=None,  # isolate transcript fidelity from note generation
            segment_delay=0,
            token_delay=0,
            sleep=_no_sleep,
        )
    )

    seg_frames = [_data(f) for f, k in zip(frames, _kinds(frames)) if k == "segment"]
    # Every input segment is emitted, in order, with byte-identical text — a
    # degraded chunk is forwarded as-is (often empty), never replaced.
    assert len(seg_frames) == len(segments)
    for emitted, original in zip(seg_frames, segments):
        assert emitted["text"] == original.text
        assert emitted["degraded"] is bool(original.degraded)
        # A degraded chunk is never given fabricated (non-original) text.
        if original.degraded:
            assert emitted["text"] == original.text

    done = _data(frames[-1])
    # The transcript is exactly the ordered concatenation of non-empty texts —
    # nothing fabricated is injected for degraded/empty chunks.
    expected = " ".join(s.text for s in segments if s.text).strip()
    assert done["transcript"] == expected


# Feature: clara-scribe-enterprise, Property 3 (degraded + note): generator adds nothing
# Validates: Requirements 1.4, 6.4
@settings(max_examples=150, deadline=None)
@given(segments=_segments)
def test_p3_note_from_degraded_stream_only_uses_transcript_tokens(
    segments: list[AsrSegment],
) -> None:
    result = AsrResult(segments=segments, language="vi", provider="whisper")
    frames = list(
        stream_scribe_sse(
            b"audio",
            language="vi",
            asr=_FakeAsr(result),
            generator=NoteGenerator(llm_complete=None),  # deterministic, no LLM
            template_id="soap",
            segment_delay=0,
            token_delay=0,
            sleep=_no_sleep,
        )
    )
    done = _data(frames[-1])
    transcript = done["transcript"]
    note = done["note"]
    assert note is not None
    transcript_tokens = set(transcript.split())
    # The deterministic note never introduces a token absent from the transcript
    # (no fabricated meds/allergies/findings), even after a degraded stream.
    for value in note["sections"].values():
        for token in value.split():
            assert token in transcript_tokens
