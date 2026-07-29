"""Whisper/DeepSeek ASR provider (Requirement 2).

Wraps the existing :class:`clara_ml.llm.deepseek_client.DeepSeekClient.transcribe_audio`
(the audio/Whisper endpoint already used by ``/v1/scribe/transcribe``) behind the
:class:`~clara_ml.scribe.asr.base.AsrProvider` seam. Import-safe (no client built at
construction) and total (never raises — returns an empty/degraded result on failure).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

from clara_ml.config import settings
from clara_ml.llm.model_registry import ModelTask, build_task_client
from clara_ml.scribe.asr.base import AsrEvent, AsrResult, AsrSegment

logger = logging.getLogger(__name__)

__all__ = ["WhisperDeepSeekAsr"]


class WhisperDeepSeekAsr:
    """ASR provider backed by the DeepSeek/Whisper audio transcription endpoint."""

    name = "whisper"

    def __init__(self, client_factory=None) -> None:
        # The client is built lazily so importing/constructing opens no socket.
        self._client_factory = client_factory

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        # Local CPU Whisper can legitimately take longer than a text LLM
        # request. Give it one bounded attempt; retrying the same audio while
        # the first decode still consumes CPU creates a timeout storm.
        client, _ = build_task_client(
            ModelTask.SCRIBE_TRANSCRIPTION,
            settings,
            timeout_seconds=max(
                float(settings.deepseek_timeout_seconds),
                float(settings.scribe_asr_timeout_seconds),
            ),
            retries_per_base=0,
            audio=True,
        )
        return client

    def transcribe(self, audio: bytes, *, language: str, content_type: str) -> AsrResult:
        """Transcribe a whole audio blob into a single (speaker-unknown) segment."""

        lang = (language or settings.scribe_asr_language or "vi").strip()
        if not audio:
            return AsrResult(segments=[], language=lang, provider=self.name, degraded_count=0)
        try:
            text = self._build_client().transcribe_audio(
                audio_bytes=audio,
                filename="scribe-audio.webm",
                content_type=content_type or "application/octet-stream",
                model=settings.deepseek_audio_model,
                language=lang or None,
                prompt=(
                    "Medical consultation audio in Vietnamese. Keep English drug/procedure "
                    "names verbatim. Return complete transcript text only."
                ),
            )
        except Exception as exc:  # noqa: BLE001 - total: never raise from the seam
            logger.warning("whisper_asr_failed err=%s", exc.__class__.__name__)
            return AsrResult(segments=[], language=lang, provider=self.name, degraded_count=0)

        clean = (text or "").strip()
        if not clean:
            return AsrResult(segments=[], language=lang, provider=self.name, degraded_count=0)
        segment = AsrSegment(text=clean, speaker="unknown")
        return AsrResult(segments=[segment], language=lang, provider=self.name, degraded_count=0)

    def stream(self, audio_iter: Iterable[bytes], *, language: str) -> Iterator[AsrEvent]:
        """Batch-backed streaming: transcribe the joined chunks, emit one segment.

        A genuinely incremental streaming backend lands in a later wave; for now
        this adapts the batch transcription into a single terminal segment event
        so the SSE endpoint contract holds.
        """

        audio = b"".join(audio_iter)
        result = self.transcribe(audio, language=language, content_type="application/octet-stream")
        for seg in result.segments:
            yield AsrEvent(type="segment", segment=seg, text=seg.text)
