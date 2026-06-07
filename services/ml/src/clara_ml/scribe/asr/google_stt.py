"""Google Cloud Speech-to-Text V2 (Chirp-3) ASR provider — placeholder (Requirement 2, 3).

Chirp-3 supports Vietnamese, speaker diarization, streaming, and automatic language
detection, which makes it a strong fit for Vietnamese clinical encounters. Vietnamese
medical speech frequently *code-switches* (embeds English drug/procedure names); this
provider is configured to keep those English tokens verbatim rather than transliterating
them, and a downstream pass aligns drug tokens to the RAG drug lexicon WITHOUT rewriting
transcript text (Requirement 2.2, 7.2).

This is a wiring placeholder: until credentials/config are present it returns an empty,
degraded :class:`AsrResult` so the :class:`CompositeAsr` falls back to Whisper. It never
raises (Requirement 2.4). Real client wiring (and the ``google-cloud-speech`` dependency)
lands in a later wave so no heavy dependency is introduced now.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

from clara_ml.scribe.asr.base import AsrEvent, AsrResult

logger = logging.getLogger(__name__)

__all__ = ["GoogleSttV2Asr"]


class GoogleSttV2Asr:
    """Vietnamese-capable ASR provider (Chirp-3). Placeholder until wired."""

    name = "google_stt_v2"

    def __init__(self, *, credentials: object | None = None) -> None:
        # No client built at construction — import-safe.
        self._credentials = credentials

    def _available(self) -> bool:
        return self._credentials is not None

    def transcribe(self, audio: bytes, *, language: str, content_type: str) -> AsrResult:
        if not self._available():
            logger.info("google_stt_v2 not configured; degrading (composite will fall back)")
            return AsrResult(segments=[], language=language, provider=self.name, degraded_count=0)
        # Real Chirp-3 call lands in a later wave.
        return AsrResult(segments=[], language=language, provider=self.name, degraded_count=0)

    def stream(self, audio_iter: Iterable[bytes], *, language: str) -> Iterator[AsrEvent]:
        # Streaming Chirp-3 wiring lands in a later wave; degrade to no events.
        del audio_iter, language
        return iter(())
