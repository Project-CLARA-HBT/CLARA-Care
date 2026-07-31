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

from clara_ml.llm.model_registry import AsrProviderRoute, resolve_asr_provider_selection
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
            yield AsrEvent(
                type="error",
                detail={"reason": "asr_unavailable", "batch_attempted": True},
            )
            return
        # Carry provider/language on each event so the SSE layer can record
        # accurate ASR metadata (provider, language, degraded count — Req 2.5).
        meta = {"provider": result.provider, "language": result.language}
        for seg in result.segments:
            yield AsrEvent(type="segment", segment=seg, text=seg.text, detail=dict(meta))


def _provider_for_route(route: AsrProviderRoute, settings: Any | None = None) -> AsrProvider:
    """Build an ASR provider from an already allowlisted registry route."""

    if route.provider == "google_stt_v2_chirp3":
        return GoogleSttV2Asr(
            project_id=str(getattr(settings, "scribe_google_project_id", "") or ""),
            location=str(getattr(settings, "scribe_google_location", "us") or "us"),
            recognizer=str(getattr(settings, "scribe_google_recognizer", "_") or "_"),
        )
    if route.provider == "phowhisper":
        return PhoWhisperAsr(model=route.model)
    # The registry normalizes unknown routes to Whisper before this point.
    return WhisperDeepSeekAsr()


def build_asr_provider(settings: Any) -> CompositeAsr:
    """Build the configured composite ASR provider from settings (import-safe)."""

    selection = resolve_asr_provider_selection(settings)
    primary = _provider_for_route(selection.primary, settings)
    fallback = (
        _provider_for_route(selection.fallback, settings)
        if selection.fallback is not None
        else None
    )
    return CompositeAsr(primary, fallback)
