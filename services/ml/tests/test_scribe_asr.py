"""Unit tests for the Clara Scribe ASR provider seam (Wave 0 / Requirement 2)."""

from __future__ import annotations

from clara_ml.config import settings
from clara_ml.scribe.asr import (
    AsrEvent,
    AsrResult,
    AsrSegment,
    CompositeAsr,
    PhoWhisperAsr,
    WhisperDeepSeekAsr,
    build_asr_provider,
    relabel_speakers,
)
from clara_ml.scribe.asr.base import SPEAKERS


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


def test_google_chirp_provider_uses_real_response_without_inventing_roles() -> None:
    from types import SimpleNamespace

    from clara_ml.scribe.asr.google_stt import GoogleSttV2Asr

    class Client:
        def __init__(self) -> None:
            self.request = None

        def recognize(self, *, request):
            self.request = request
            alternative = SimpleNamespace(
                transcript="Bệnh nhân đau ngực",
                confidence=0.91,
            )
            result = SimpleNamespace(
                alternatives=[alternative],
                result_end_offset=SimpleNamespace(seconds=2, nanos=500_000_000),
                language_code="vi-VN",
            )
            return SimpleNamespace(results=[result])

    client = Client()
    provider = GoogleSttV2Asr(project_id="clinical-project", client=client)
    output = provider.transcribe(b"real-audio", language="vi-VN", content_type="audio/webm")

    assert output.text == "Bệnh nhân đau ngực"
    assert output.segments[0].speaker == "unknown"
    assert output.segments[0].end_ms == 2500
    assert client.request["config"]["model"] == "chirp_3"


class _FakeResponse:
    def __init__(self, *, json_data=None, status_code: int = 200, raise_exc=None):
        self._json = json_data
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc

    def json(self):
        return self._json


class _FakeHttpClient:
    """Minimal httpx.Client stand-in (context manager + .post)."""

    def __init__(self, response=None, post_exc=None):
        self._response = response
        self._post_exc = post_exc
        self.posts: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, *, headers=None, data=None, files=None):  # noqa: ANN001
        self.posts.append({"url": url, "headers": headers, "data": data, "files": files})
        if self._post_exc is not None:
            raise self._post_exc
        return self._response


def test_phowhisper_import_safe_and_degrades_when_unconfigured() -> None:
    # No base url -> import-safe construction + degraded empty result (no network).
    provider = PhoWhisperAsr(base_url="")
    out = provider.transcribe(b"audio", language="vi", content_type="audio/webm")
    assert out.provider == "phowhisper"
    assert out.segments == []
    assert out.language == "vi"


def test_phowhisper_transcribes_flat_text_payload() -> None:
    client = _FakeHttpClient(_FakeResponse(json_data={"text": "Bệnh nhân dùng Paracetamol"}))
    provider = PhoWhisperAsr(base_url="http://pho.local", client_factory=lambda: client)
    out = provider.transcribe(b"audio", language="vi", content_type="audio/webm")
    assert out.provider == "phowhisper"
    assert out.text == "Bệnh nhân dùng Paracetamol"
    assert out.segments[0].speaker == "unknown"
    # Code-switching prompt sent + multipart hits the OpenAI-compatible path.
    assert client.posts[0]["url"] == "http://pho.local/v1/audio/transcriptions"
    assert client.posts[0]["data"]["language"] == "vi"
    assert "prompt" in client.posts[0]["data"]


def test_phowhisper_parses_diarized_segments() -> None:
    payload = {
        "segments": [
            {"text": "Chào bác sĩ", "speaker": "patient", "start": 0.0, "end": 1.5},
            {"text": "Anh dùng Aspirin chưa", "speaker": "clinician", "start": 1.5, "end": 3.0},
        ]
    }
    client = _FakeHttpClient(_FakeResponse(json_data=payload))
    provider = PhoWhisperAsr(base_url="http://pho.local/v1", client_factory=lambda: client)
    out = provider.transcribe(b"audio", language="vi", content_type="audio/webm")
    assert [s.speaker for s in out.segments] == ["patient", "clinician"]
    assert out.segments[1].text == "Anh dùng Aspirin chưa"
    # base already ends with /v1 -> not doubled.
    assert client.posts[0]["url"] == "http://pho.local/v1/audio/transcriptions"


def test_phowhisper_never_raises_on_http_error() -> None:
    client = _FakeHttpClient(post_exc=RuntimeError("connection reset"))
    provider = PhoWhisperAsr(
        base_url="http://pho.local",
        retries=0,
        retry_backoff_seconds=0.0,
        client_factory=lambda: client,
    )
    out = provider.transcribe(b"audio", language="vi", content_type="audio/webm")
    assert out.segments == []
    assert out.degraded_count == 1  # degraded, not an exception


def test_phowhisper_empty_audio_returns_empty() -> None:
    provider = PhoWhisperAsr(base_url="http://pho.local")
    out = provider.transcribe(b"", language="vi", content_type="audio/webm")
    assert out.segments == []


def test_build_asr_provider_resolves_phowhisper(monkeypatch) -> None:
    monkeypatch.setattr(settings, "scribe_asr_primary", "phowhisper", raising=False)
    monkeypatch.setattr(settings, "scribe_asr_fallback", "whisper", raising=False)
    monkeypatch.setattr(settings, "scribe_phowhisper_base_url", "", raising=False)
    comp = build_asr_provider(settings)
    assert isinstance(comp, CompositeAsr)
    # Unconfigured phowhisper primary degrades; composite falls back without raising.
    out = comp.transcribe(b"", language="vi", content_type="audio/webm")
    assert out.segments == []


# --- Core seam types: defaults, derived text, degraded count (Requirement 1.4/2/3) ---


def test_asr_segment_defaults_are_safe() -> None:
    seg = AsrSegment(text="hello")
    assert seg.speaker == "unknown"  # diarization unavailable -> unknown (Req 3.2)
    assert seg.start_ms == 0
    assert seg.end_ms == 0
    assert seg.confidence == 0.0
    assert seg.degraded is False


def test_asr_result_defaults_and_text_preserves_order_and_skips_blanks() -> None:
    empty = AsrResult()
    assert empty.segments == []
    assert empty.language == ""
    assert empty.provider == ""
    assert empty.degraded_count == 0
    assert empty.text == ""

    result = AsrResult(
        segments=[
            AsrSegment(text="first"),
            AsrSegment(text="", degraded=True),  # degraded/blank chunk contributes no text
            AsrSegment(text="second"),
        ]
    )
    # Order preserved; blank/degraded segment never fabricates text (Req 1.4).
    assert result.text == "first second"


def test_asr_result_degraded_count_is_carried_verbatim() -> None:
    result = AsrResult(segments=[AsrSegment(text="ok")], degraded_count=2)
    assert result.degraded_count == 2


def test_asr_event_shapes_partial_segment_error() -> None:
    partial = AsrEvent(type="partial", text="hel")
    assert partial.type == "partial"
    assert partial.segment is None
    assert partial.detail == {}

    seg = AsrSegment(text="hello")
    segment_evt = AsrEvent(type="segment", segment=seg, text=seg.text)
    assert segment_evt.type == "segment"
    assert segment_evt.segment is seg
    assert segment_evt.text == "hello"

    error_evt = AsrEvent(type="error", detail={"reason": "asr_unavailable"})
    assert error_evt.type == "error"
    assert error_evt.segment is None
    assert error_evt.detail["reason"] == "asr_unavailable"


# --- relabel_speakers: additive metadata only, text + order preserved (Req 3.4 / Property 2) ---


def test_relabel_speakers_preserves_text_and_order() -> None:
    segments = [
        AsrSegment(text="Chào bác sĩ", speaker="unknown"),
        AsrSegment(text="Anh dùng Aspirin chưa", speaker="unknown"),
    ]
    relabeled = relabel_speakers(segments, {0: "patient", 1: "clinician"})
    assert [s.text for s in relabeled] == [s.text for s in segments]
    assert [s.speaker for s in relabeled] == ["patient", "clinician"]
    # Input list not mutated (pure).
    assert [s.speaker for s in segments] == ["unknown", "unknown"]


def test_relabel_speakers_ignores_unknown_labels() -> None:
    segments = [AsrSegment(text="x", speaker="clinician")]
    # A label outside SPEAKERS leaves the original speaker untouched.
    relabeled = relabel_speakers(segments, {0: "doctor"})
    assert relabeled[0].speaker == "clinician"
    assert relabeled[0].text == "x"


def test_relabel_speakers_only_valid_labels_assigned() -> None:
    segments = [AsrSegment(text=str(i)) for i in range(len(SPEAKERS))]
    labels = dict(enumerate(SPEAKERS))
    relabeled = relabel_speakers(segments, labels)
    assert [s.speaker for s in relabeled] == list(SPEAKERS)
    assert [s.text for s in relabeled] == [s.text for s in segments]


# --- Composite streaming: never raises, degraded -> terminal error, else segment events ---


def test_composite_stream_yields_error_event_when_no_segments() -> None:
    primary = _FakeProvider("p", [])
    fallback = _FakeProvider("f", [])
    events = list(CompositeAsr(primary, fallback).stream([b"x"], language="vi"))
    assert len(events) == 1
    assert events[0].type == "error"
    assert events[0].detail.get("reason") == "asr_unavailable"


def test_composite_stream_yields_segment_events_in_order() -> None:
    primary = _FakeProvider("p", [AsrSegment(text="one"), AsrSegment(text="two")])
    events = list(CompositeAsr(primary, None).stream([b"a", b"b"], language="vi"))
    assert [e.type for e in events] == ["segment", "segment"]
    assert [e.text for e in events] == ["one", "two"]


def test_composite_total_with_no_fallback_returns_empty_shape() -> None:
    primary = _FakeProvider("p", [])
    out = CompositeAsr(primary).transcribe(b"x", language="vi", content_type="audio/webm")
    assert out.segments == []  # totality holds even without a fallback


# --- Import safety: constructing providers opens no socket ---


def test_constructing_providers_opens_no_socket(monkeypatch) -> None:
    import socket

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("provider construction must not open a socket")

    monkeypatch.setattr(socket.socket, "connect", _boom, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _boom, raising=True)

    # All seam providers + the composite factory construct without any network I/O.
    WhisperDeepSeekAsr()
    PhoWhisperAsr(base_url="http://pho.local")
    build_asr_provider(settings)
