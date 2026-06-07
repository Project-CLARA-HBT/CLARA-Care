"""Unit tests for the Clara Scribe ASR provider seam (Wave 0 / Requirement 2)."""

from __future__ import annotations

from clara_ml.config import settings
from clara_ml.scribe.asr import (
    AsrResult,
    AsrSegment,
    CompositeAsr,
    WhisperDeepSeekAsr,
    build_asr_provider,
)


class _FakeProvider:
    def __init__(self, name: str, segments: list[AsrSegment] | None = None, raises: bool = False):
        self.name = name
        self._segments = segments or []
        self._raises = raises
        self.calls = 0

    def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
        self.calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return AsrResult(segments=list(self._segments), language=language, provider=self.name)

    def stream(self, audio_iter, *, language):  # noqa: ANN001
        return iter(())


def test_composite_uses_primary_when_it_has_segments() -> None:
    primary = _FakeProvider("p", [AsrSegment(text="hello")])
    fallback = _FakeProvider("f", [AsrSegment(text="other")])
    out = CompositeAsr(primary, fallback).transcribe(b"x", language="vi", content_type="audio/webm")
    assert out.provider == "p"
    assert out.text == "hello"
    assert fallback.calls == 0


def test_composite_falls_back_when_primary_empty() -> None:
    primary = _FakeProvider("p", [])
    fallback = _FakeProvider("f", [AsrSegment(text="rescued")])
    out = CompositeAsr(primary, fallback).transcribe(b"x", language="vi", content_type="audio/webm")
    assert out.provider == "f"
    assert out.text == "rescued"
    assert fallback.calls == 1


def test_composite_never_raises_when_primary_raises() -> None:
    primary = _FakeProvider("p", raises=True)
    fallback = _FakeProvider("f", [AsrSegment(text="safe")])
    out = CompositeAsr(primary, fallback).transcribe(b"x", language="vi", content_type="audio/webm")
    assert out.text == "safe"


def test_composite_total_when_both_fail() -> None:
    primary = _FakeProvider("p", raises=True)
    fallback = _FakeProvider("f", raises=True)
    out = CompositeAsr(primary, fallback).transcribe(b"x", language="vi", content_type="audio/webm")
    assert out.segments == []  # empty, but no exception


def test_whisper_provider_import_safe_and_total_on_empty_audio() -> None:
    # Constructing builds no client; empty audio returns an empty result (no network).
    provider = WhisperDeepSeekAsr()
    out = provider.transcribe(b"", language="vi", content_type="audio/webm")
    assert out.provider == "whisper"
    assert out.segments == []


def test_build_asr_provider_resolves_whisper_and_unknown(monkeypatch) -> None:
    monkeypatch.setattr(settings, "scribe_asr_primary", "whisper", raising=False)
    monkeypatch.setattr(settings, "scribe_asr_fallback", "whisper", raising=False)
    comp = build_asr_provider(settings)
    assert isinstance(comp, CompositeAsr)

    monkeypatch.setattr(settings, "scribe_asr_primary", "totally-unknown", raising=False)
    comp2 = build_asr_provider(settings)
    # Unknown primary degrades to a working whisper-backed composite (no raise).
    assert isinstance(comp2, CompositeAsr)
    out = comp2.transcribe(b"", language="vi", content_type="audio/webm")
    assert out.segments == []
