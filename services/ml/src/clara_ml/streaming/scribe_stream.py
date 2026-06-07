"""SSE streaming for Clara Scribe transcription + note draft (task 1.1, Requirement 1).

Reuses the chat-stream SSE frame helper (`sse_event`). Given an uploaded audio
blob it transcribes via the injected ASR seam and emits:

1. ``start``   — ``{}`` (client opens the live transcript panel).
2. ``segment`` — one per :class:`AsrSegment` (with speaker + degraded flag).
3. ``token``   — chunks of the generated note's first section (typing effect),
   only when a template/generator is provided.
4. ``done``    — ``{transcript, segments, note, asr_meta}`` / ``error`` on failure.

A degraded ASR segment is forwarded with ``degraded=true`` and NEVER replaced by
fabricated text (Requirement 1.4). Import-safe; ASR + generator are injected so
the module is unit-testable with fakes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

from clara_ml.streaming.chat_stream import iter_answer_chunks, sse_event

logger = logging.getLogger(__name__)

__all__ = ["stream_scribe_sse"]

_DEFAULT_SEGMENT_DELAY = 0.02
_DEFAULT_TOKEN_DELAY = 0.018


def stream_scribe_sse(
    audio: bytes,
    *,
    language: str,
    content_type: str = "application/octet-stream",
    template_id: str | None = None,
    asr: Any,
    generator: Any | None = None,
    segment_delay: float = _DEFAULT_SEGMENT_DELAY,
    token_delay: float = _DEFAULT_TOKEN_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str]:
    """Yield the SSE frames for one streamed scribe transcription (+ optional note)."""

    yield sse_event("start", {})
    try:
        result = asr.transcribe(audio, language=language, content_type=content_type)
    except Exception as exc:  # noqa: BLE001 - terminal error frame, never raise
        logger.warning("scribe_stream_asr_failed err=%s", exc.__class__.__name__)
        yield sse_event("error", {"message": "scribe transcription failed", "error": exc.__class__.__name__})
        return

    segments = list(getattr(result, "segments", []) or [])
    serialized_segments: list[dict[str, Any]] = []
    for index, seg in enumerate(segments):
        payload = {
            "index": index,
            "text": getattr(seg, "text", ""),
            "speaker": getattr(seg, "speaker", "unknown"),
            "start_ms": getattr(seg, "start_ms", 0),
            "end_ms": getattr(seg, "end_ms", 0),
            "degraded": bool(getattr(seg, "degraded", False)),
        }
        serialized_segments.append(payload)
        yield sse_event("segment", payload)
        if segment_delay > 0:
            sleep(segment_delay)

    transcript = " ".join(s["text"] for s in serialized_segments if s["text"]).strip()

    note_payload: dict[str, Any] | None = None
    if generator is not None:
        try:
            note = generator.generate(transcript, template_id)
            note_payload = {
                "template_id": getattr(note, "template_id", template_id or "soap"),
                "sections": dict(getattr(note, "sections", {})),
                "insufficient_input": bool(getattr(note, "insufficient_input", False)),
            }
            # Typewriter the first non-empty section for the live note draft.
            first_text = next((v for v in note_payload["sections"].values() if v), "")
            for chunk in iter_answer_chunks(first_text):
                yield sse_event("token", {"text": chunk})
                if token_delay > 0:
                    sleep(token_delay)
        except Exception as exc:  # noqa: BLE001 - note is best-effort
            logger.warning("scribe_stream_note_failed err=%s", exc.__class__.__name__)
            note_payload = None

    yield sse_event(
        "done",
        {
            "transcript": transcript,
            "segments": serialized_segments,
            "note": note_payload,
            "asr_meta": {
                "provider": getattr(result, "provider", ""),
                "language": getattr(result, "language", language),
                "degraded_count": getattr(result, "degraded_count", 0),
            },
        },
    )
