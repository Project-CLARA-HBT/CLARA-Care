"""SSE streaming for Clara Scribe transcription + note draft (task 1.1, Requirement 1).

Reuses the chat-stream SSE frame helper (:func:`sse_event`). Given an uploaded audio
blob it drives the injected ASR seam and emits, using the established chat-stream SSE
contract (``event: <type>`` + ``data: <json>``):

1. ``start``   — ``{}`` (client opens the live transcript panel).
2. ``partial`` — interim text for a chunk before it is finalized (Requirement 1.3).
3. ``segment`` — one finalized :class:`AsrSegment` (with speaker + ``degraded`` flag).
4. ``token``   — chunks of the generated note's first section (typing effect),
   only when a template/generator is provided.
5. ``done``    — ``{transcript, segments, note, asr_meta, flow_events}`` (terminal
   success), or ``error`` (terminal failure) whose payload names the failure class.

The terminal ``done`` frame additively carries a ``flow_events`` array (Requirement
10.3) describing the scribe pipeline stages that ran — ``transcribe``, ``diarize``,
and ``generate`` — using the *same* flow-event shape chat/research emit. This makes
the streamed pipeline observable in the existing UI process panel without a new
contract. The events are PII-free (Requirement 10.1): only stage/status/coarse
counts/timestamps, never transcript text or patient identifiers.

Streaming path (Requirement 1.2/1.3): when the ASR provider exposes ``stream(...)``
the helper drives it, mapping each :class:`AsrEvent` to a ``partial``/``segment`` SSE
frame. When the streaming provider is unavailable (it raises or yields a terminal
``error`` event with no usable segments) the helper FALLS BACK to the batch
``transcribe(...)`` path; if batch also yields nothing it emits a terminal ``error``
naming the failure class (Requirement 1.5).

A degraded ASR chunk is forwarded with ``degraded=true`` and its text is NEVER replaced
by fabricated text (Requirement 1.4). Import-safe; the ASR + generator are injected so
the module is unit-testable with fakes.
"""

from __future__ import annotations

import logging
from queue import Empty, Queue
from threading import Thread
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from typing import Any

from clara_ml.streaming.chat_stream import iter_answer_chunks, sse_event

logger = logging.getLogger(__name__)

__all__ = ["stream_scribe_sse"]

_DEFAULT_SEGMENT_DELAY = 0.02
_DEFAULT_TOKEN_DELAY = 0.018
_DEFAULT_HEARTBEAT_SECONDS = 10.0


def _stream_events_with_heartbeats(
    stream_fn: Callable[..., Any],
    audio: bytes,
    *,
    language: str,
    heartbeat_seconds: float,
) -> Iterator[tuple[str, Any]]:
    """Run blocking ASR off-generator and keep the SSE connection observable."""

    queue: Queue[tuple[str, Any]] = Queue()

    def produce() -> None:
        try:
            for event in stream_fn([audio], language=language):
                queue.put(("event", event))
        except Exception as exc:  # noqa: BLE001 - re-raised in relay thread
            queue.put(("error", exc))
        finally:
            queue.put(("done", None))

    Thread(target=produce, name="scribe-asr-stream", daemon=True).start()
    interval = max(float(heartbeat_seconds), 0.05)
    while True:
        try:
            kind, value = queue.get(timeout=interval)
        except Empty:
            yield "heartbeat", None
            continue
        if kind == "done":
            return
        if kind == "error":
            raise value
        yield kind, value


def _flow_event(*, stage: str, status: str, source_count: int, note: str) -> dict[str, Any]:
    """Build one scribe pipeline flow/telemetry event (Requirement 10.3).

    Reuses the established flow-event shape (``{stage, timestamp, status,
    source_count, note}``) that chat/research already emit and the web process
    panel/LogicFlow already render, so scribe pipeline stages are observable in
    the UI via the *same* mechanism — no new contract is introduced.

    PII-free by construction (Requirement 10.1): callers pass only the coarse
    ``stage``/``status``, a non-negative ``source_count``, and a ``note`` derived
    from stage metadata (provider/template/counts) — never transcript text or any
    patient identifier.
    """

    return {
        "stage": stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_count": max(int(source_count), 0),
        "note": note,
    }


def _serialize_segment(
    index: int, seg: Any, *, diarization_enabled: bool = True
) -> dict[str, Any]:
    """Project an :class:`AsrSegment` to its SSE/JSON payload (additive metadata).

    The ``speaker`` label is surfaced from the provider only when diarization is
    enabled (Requirement 3.1); when diarization is unavailable/disabled the label
    defaults to ``"unknown"`` (Requirement 3.2) without altering the segment text
    or order — diarization is additive metadata only (Requirement 3.4). The flag
    never changes which segments are emitted or their text.
    """

    speaker = getattr(seg, "speaker", "unknown") if diarization_enabled else "unknown"
    return {
        "index": index,
        "text": getattr(seg, "text", ""),
        "speaker": speaker or "unknown",
        "start_ms": getattr(seg, "start_ms", 0),
        "end_ms": getattr(seg, "end_ms", 0),
        "confidence": getattr(seg, "confidence", 0.0),
        "degraded": bool(getattr(seg, "degraded", False)),
    }


def stream_scribe_sse(
    audio: bytes,
    *,
    language: str,
    content_type: str = "application/octet-stream",
    template_id: str | None = None,
    asr: Any,
    generator: Any | None = None,
    correction_fn: Callable[[str, str], dict[str, Any]] | None = None,
    diarization_enabled: bool = True,
    segment_delay: float = _DEFAULT_SEGMENT_DELAY,
    token_delay: float = _DEFAULT_TOKEN_DELAY,
    heartbeat_seconds: float = _DEFAULT_HEARTBEAT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str]:
    """Yield the SSE frames for one streamed scribe transcription (+ optional note).

    ``diarization_enabled`` gates surfacing provider speaker labels (Requirement 3):
    when ``False`` every segment's ``speaker`` defaults to ``"unknown"`` (legacy
    behavior, note generation unaffected); when ``True`` the provider's diarization
    label is surfaced. Either way the segment text and ordering are unchanged.
    """

    yield sse_event("start", {})

    serialized_segments: list[dict[str, Any]] = []
    asr_meta: dict[str, Any] = {"provider": "", "language": language, "degraded_count": 0}
    stream_failure: str | None = None
    batch_already_attempted = False
    produced = False

    # (1) Streaming path — drive the provider's stream(...) when available
    # (Requirement 1.2/1.3). For each finalized segment we emit an interim
    # ``partial`` frame then the finalized ``segment`` frame.
    stream_fn = getattr(asr, "stream", None)
    if callable(stream_fn):
        try:
            for item_type, event in _stream_events_with_heartbeats(
                stream_fn,
                audio,
                language=language,
                heartbeat_seconds=heartbeat_seconds,
            ):
                if item_type == "heartbeat":
                    yield sse_event(
                        "heartbeat",
                        {"stage": "transcribe", "status": "running"},
                    )
                    continue
                etype = getattr(event, "type", "")
                detail = getattr(event, "detail", {}) or {}
                if detail.get("provider"):
                    asr_meta["provider"] = detail["provider"]
                if detail.get("language"):
                    asr_meta["language"] = detail["language"]

                if etype == "error":
                    stream_failure = str(detail.get("reason") or "asr_stream_error")
                    batch_already_attempted = bool(detail.get("batch_attempted"))
                    break
                if etype == "partial":
                    yield sse_event(
                        "partial",
                        {"index": len(serialized_segments), "text": getattr(event, "text", "")},
                    )
                    continue
                if etype == "segment":
                    seg = getattr(event, "segment", None)
                    if seg is None:
                        continue
                    index = len(serialized_segments)
                    payload = _serialize_segment(
                        index, seg, diarization_enabled=diarization_enabled
                    )
                    # Interim view first (never fabricated — mirrors the finalized
                    # text, empty for a degraded chunk), then the finalized segment.
                    yield sse_event(
                        "partial",
                        {"index": index, "text": payload["text"], "degraded": payload["degraded"]},
                    )
                    serialized_segments.append(payload)
                    if payload["degraded"]:
                        asr_meta["degraded_count"] += 1
                    yield sse_event("segment", payload)
                    produced = True
                    if segment_delay > 0:
                        sleep(segment_delay)
        except Exception as exc:  # noqa: BLE001 - streaming provider is total; degrade to batch
            logger.warning("scribe_stream_provider_failed err=%s", exc.__class__.__name__)
            stream_failure = exc.__class__.__name__

    # (2) Batch fallback — used for the legacy (no stream(...)) path and when the
    # streaming provider produced no usable segments (Requirement 1.5).
    if not produced and batch_already_attempted:
        yield sse_event(
            "error",
            {"message": "scribe streaming unavailable", "error": stream_failure},
        )
        return
    if not produced:
        try:
            result = asr.transcribe(audio, language=language, content_type=content_type)
        except Exception as exc:  # noqa: BLE001 - terminal error frame, never raise
            logger.warning("scribe_stream_asr_failed err=%s", exc.__class__.__name__)
            yield sse_event(
                "error",
                {"message": "scribe transcription failed", "error": exc.__class__.__name__},
            )
            return

        batch_segments = list(getattr(result, "segments", []) or [])
        for seg in batch_segments:
            index = len(serialized_segments)
            payload = _serialize_segment(
                index, seg, diarization_enabled=diarization_enabled
            )
            serialized_segments.append(payload)
            if payload["degraded"]:
                asr_meta["degraded_count"] += 1
            yield sse_event("segment", payload)
            if segment_delay > 0:
                sleep(segment_delay)

        asr_meta["provider"] = getattr(result, "provider", "") or asr_meta["provider"]
        asr_meta["language"] = getattr(result, "language", language) or language
        if getattr(result, "degraded_count", 0):
            asr_meta["degraded_count"] = result.degraded_count

        # Streaming was attempted and failed AND batch could not transcribe either:
        # surface a terminal error naming the failure class (Requirement 1.5).
        if not batch_segments and stream_failure is not None:
            yield sse_event(
                "error",
                {"message": "scribe streaming unavailable", "error": stream_failure},
            )
            return

    transcript = " ".join(s["text"] for s in serialized_segments if s["text"]).strip()

    # (3) Optional note draft — typewriter the first non-empty section.
    note_payload: dict[str, Any] | None = None
    if generator is not None:
        try:
            note = generator.generate(transcript, template_id)
            note_payload = {
                "template_id": getattr(note, "template_id", template_id or "soap"),
                "sections": dict(getattr(note, "sections", {})),
                "insufficient_input": bool(getattr(note, "insufficient_input", False)),
            }
            first_text = next((v for v in note_payload["sections"].values() if v), "")
            for chunk in iter_answer_chunks(first_text):
                yield sse_event("token", {"text": chunk})
                if token_delay > 0:
                    sleep(token_delay)
        except Exception as exc:  # noqa: BLE001 - note is best-effort
            logger.warning("scribe_stream_note_failed err=%s", exc.__class__.__name__)
            note_payload = None

    # (4) Optional medical-ASR correction proposals. The callback is injected by
    # the governed ML route, returns review-only source-spanned candidates, and
    # never changes ``transcript`` or the streamed note.
    medical_correction: dict[str, Any] | None = None
    if correction_fn is not None:
        try:
            medical_correction = correction_fn(transcript, language)
        except Exception:  # noqa: BLE001 - correction must not fail transcription
            medical_correction = {"status": "unavailable", "suggestions": [], "applied": False}

    # (5) Pipeline flow/telemetry events (Requirement 10.3) — surface the stages
    # that actually ran (transcribe, diarize, generate) using the established
    # flow-event shape, so the streamed pipeline is observable in the UI process
    # panel via the same mechanism as chat/research. PII-free: notes carry only
    # provider/template/coarse counts (Requirement 10.1).
    flow_events: list[dict[str, Any]] = []

    transcribe_status = "completed"
    if not serialized_segments or asr_meta["degraded_count"] >= len(serialized_segments):
        transcribe_status = "degraded"
    flow_events.append(
        _flow_event(
            stage="transcribe",
            status=transcribe_status,
            source_count=len(serialized_segments),
            note=(
                f"provider={asr_meta['provider'] or 'unknown'} "
                f"language={asr_meta['language']} degraded={asr_meta['degraded_count']}"
            ),
        )
    )

    if diarization_enabled:
        labeled = sum(
            1 for s in serialized_segments if s.get("speaker", "unknown") != "unknown"
        )
        flow_events.append(
            _flow_event(
                stage="diarize",
                status="completed" if labeled else "unknown",
                source_count=labeled,
                note=f"labeled={labeled}/{len(serialized_segments)}",
            )
        )
    else:
        flow_events.append(
            _flow_event(
                stage="diarize", status="skipped", source_count=0, note="diarization disabled"
            )
        )

    if generator is None:
        flow_events.append(
            _flow_event(
                stage="generate", status="skipped", source_count=0, note="no generator"
            )
        )
    elif note_payload is None:
        flow_events.append(
            _flow_event(
                stage="generate", status="error", source_count=0, note="note generation failed"
            )
        )
    else:
        filled = sum(1 for v in note_payload["sections"].values() if v)
        flow_events.append(
            _flow_event(
                stage="generate",
                status=(
                    "insufficient_input"
                    if note_payload.get("insufficient_input")
                    else "completed"
                ),
                source_count=filled,
                note=(
                    f"template={note_payload['template_id']} "
                    f"sections={len(note_payload['sections'])}"
                ),
            )
        )

    # (6) Terminal success frame with the full structured result.
    yield sse_event(
        "done",
        {
            "transcript": transcript,
            "segments": serialized_segments,
            "note": note_payload,
            "medical_correction": medical_correction,
            "asr_meta": asr_meta,
            "flow_events": flow_events,
        },
    )
