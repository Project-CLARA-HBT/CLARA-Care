"""ASR provider seam for Clara Scribe (task 0.2/0.3, Requirement 2).

Decouples the scribe note pipeline from the transcription backend behind a small,
import-safe, total (never-raises) :class:`AsrProvider` protocol. Implementations:

* :class:`WhisperDeepSeekAsr` — wraps the existing DeepSeek/Whisper audio client
  (the only fully-wired provider today).
* :class:`GoogleSttV2Asr` — placeholder Vietnamese-capable provider (Chirp-3 +
  diarization + code-switching); returns an empty/degraded result until wired.
* :class:`CompositeAsr` — tries a primary provider then a fallback.

Importing this package opens no socket and constructs no HTTP client.
"""

from __future__ import annotations

from clara_ml.scribe.asr.base import (
    AsrEvent,
    AsrProvider,
    AsrResult,
    AsrSegment,
)
from clara_ml.scribe.asr.composite import CompositeAsr, build_asr_provider
from clara_ml.scribe.asr.google_stt import GoogleSttV2Asr
from clara_ml.scribe.asr.whisper import WhisperDeepSeekAsr

__all__ = [
    "AsrEvent",
    "AsrProvider",
    "AsrResult",
    "AsrSegment",
    "CompositeAsr",
    "GoogleSttV2Asr",
    "WhisperDeepSeekAsr",
    "build_asr_provider",
]
