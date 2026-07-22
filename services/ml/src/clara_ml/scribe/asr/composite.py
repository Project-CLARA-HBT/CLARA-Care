"""Composite ASR (primary -> fallback) + provider factory (Requirement 2).

:class:`CompositeAsr` tries a primary provider; if it returns no usable segments
(or raises despite the total contract), it tries a fallback. Import-safe + total.
:func:`build_asr_provider` maps the configured provider names to implementations,
degrading unknown names to the Whisper provider.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from typing import Any

from clara_ml.scribe.asr.base import AsrEvent, AsrProvider, AsrResult
from clara_ml.scribe.asr.google_stt import GoogleSttV2Asr
from clara_ml.scribe.asr.phowhisper import PhoWhisperAsr
from clara_ml.scribe.asr.whisper import WhisperDeepSeekAsr

logger = logging.getLogger(__name__)

__all__ = ["CompositeAsr", "build_asr_provider"]


def _has_segments(result: AsrResult | None) -> bool:
    return bool(result is not None and result.segments)


class CompositeAsr:
    """Try ``primary`` then ``fallback``; never raise (Requirement 2.3/2.4)."""

    name = "composite"

    def __init__(self, primary: AsrProvider, fallback: AsrProvider | None = None) -> None:
        self._primary = primary
        self._fallback = fallback

    @staticmethod
    def _safe_transcribe(
        provider: AsrProvider | None, audio: bytes, language: str, content_type: str
    ) -> AsrResult | None:
        if provider is None:
            return None
        try:
            return provider.transcribe(audio, language=language, content_type=content_type)
        except Exception as exc:  # noqa: BLE001 - total seam
            logger.warning(
                "asr_provider_failed name=%s err=%s",
                getattr(provider, "name", "?"),
                exc.__class__.__name__,
            )
            return None

    def transcribe(self, audio: bytes, *, language: str, content_type: str) -> AsrResult:
        primary = self._safe_transcribe(self._primary, audio, language, content_type)
        if _has_segments(primary):
            return primary  # type: ignore[return-value]
        fallback = self._safe_transcribe(self._fallback, audio, language, content_type)
        if _has_segments(fallback):
            return fallback  # type: ignore[return-value]
        # Neither produced segments — return the primary's (empty) result shape.
        return primary or fallback or AsrResult(
            segments=[], language=language, provider=self.name, degraded_count=0
        )

    def stream(self, audio_iter: Iterable[bytes], *, language: str) -> Iterator[AsrEvent]:
        # Buffer once (streaming providers land in a later wave) and delegate to
        # the resilient batch path so fallback still applies.
        audio = b"".join(audio_iter)
        result = self.transcribe(audio, language=language, content_type="application/octet-stream")
        if not result.segments:
            yield AsrEvent(type="error", detail={"reason": "asr_unavailable"})
            return
        # Carry provider/language on each event so the SSE layer can record
        # accurate ASR metadata (provider, language, degraded count — Req 2.5).
        meta = {"provider": result.provider, "language": result.language}
        for seg in result.segments:
            yield AsrEvent(type="segment", segment=seg, text=seg.text, detail=dict(meta))


def _provider_by_name(name: str, settings: Any | None = None) -> AsrProvider:
    key = (name or "").strip().lower()
    if key in ("google", "google_stt", "google_stt_v2", "chirp", "chirp3"):
        return GoogleSttV2Asr(
            project_id=str(getattr(settings, "scribe_google_project_id", "") or ""),
            location=str(getattr(settings, "scribe_google_location", "us") or "us"),
            recognizer=str(getattr(settings, "scribe_google_recognizer", "_") or "_"),
        )
    if key in ("phowhisper", "pho_whisper", "pho-whisper", "vi_whisper"):
        return PhoWhisperAsr()
    # Default / unknown -> Whisper (the only fully-wired backend today).
    return WhisperDeepSeekAsr()


def build_asr_provider(settings: Any) -> CompositeAsr:
    """Build the configured composite ASR provider from settings (import-safe)."""

    primary_name = str(getattr(settings, "scribe_asr_primary", "whisper") or "whisper")
    fallback_name = str(getattr(settings, "scribe_asr_fallback", "whisper") or "whisper")
    primary = _provider_by_name(primary_name, settings)
    fallback = _provider_by_name(fallback_name, settings)
    return CompositeAsr(primary, fallback)
