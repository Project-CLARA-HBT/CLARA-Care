"""ASR provider seam for Clara Scribe (task 0.2/0.3, Requirement 2).

Decouples the scribe note pipeline from the transcription backend behind a small,
import-safe, total (never-raises) :class:`AsrProvider` protocol. Implementations:

* :class:`WhisperDeepSeekAsr` — wraps the existing DeepSeek/Whisper audio client
  (the only fully-wired provider today).
* :class:`PhoWhisperAsr` — Vietnamese-capable HTTP provider for a self-hosted PhoWhisper
  (OpenAI-compatible) endpoint, with code-switching (keep English tokens verbatim) and
  optional per-segment diarization; degrades to empty when unconfigured.
* :class:`GoogleSttV2Asr` — credentialed Google Cloud Speech-to-Text V2
  Chirp-3 provider with Vietnamese/English code-switching.  It is usable only
  when the deployment supplies a project plus ADC/workload credentials; absent
  configuration or an upstream failure yields no text so ``CompositeAsr`` can
  use its configured independent fallback.
* :class:`CompositeAsr` — tries a primary provider then a fallback.

Importing this package opens no socket and constructs no HTTP client.
"""

from __future__ import annotations

from clara_ml.scribe.asr.base import (
    AsrEvent,
    AsrProvider,
    AsrResult,
    AsrSegment,
    relabel_speakers,
)
from clara_ml.scribe.asr.composite import CompositeAsr, build_asr_provider
from clara_ml.scribe.asr.google_stt import GoogleSttV2Asr
from clara_ml.scribe.asr.phowhisper import PhoWhisperAsr
from clara_ml.scribe.asr.whisper import WhisperDeepSeekAsr

__all__ = [
    "AsrEvent",
    "AsrProvider",
    "AsrResult",
    "AsrSegment",
    "CompositeAsr",
    "GoogleSttV2Asr",
    "PhoWhisperAsr",
    "WhisperDeepSeekAsr",
    "build_asr_provider",
    "relabel_speakers",
]
