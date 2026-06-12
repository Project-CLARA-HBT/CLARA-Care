"""Cross-component ML integration tests for the Scribe pipeline (task 3.4, _Verification_).

These tests wire the THREE real Scribe ML components together end-to-end —
``CompositeAsr`` (ASR seam, primary→fallback + degraded handling) →
``NoteGenerator`` (template note) → ``CodingAssistant`` (ICD + RxCUI + DDI) —
and assert the data flows correctly across the seams. The per-component unit
tests (``test_scribe_asr.py``, ``test_scribe_generator.py``,
``test_scribe_coding.py``, ``test_scribe_stream.py``) cover each piece in
isolation; this file fills the cross-component gap by running them as one
pipeline with NO behaviour mocked — only an in-memory ASR backend stands in for
the network transcription provider.
"""

from __future__ import annotations

import json

import clara_ml.rag.store  # noqa: F401 - import-order guard for the known cycle
from clara_ml.scribe.asr import CompositeAsr, WhisperDeepSeekAsr
from clara_ml.scribe.asr.base import AsrEvent, AsrResult, AsrSegment
from clara_ml.scribe.coding import CodingAssistant
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.streaming.scribe_stream import stream_scribe_sse


class _BackendAsr:
    """In-memory stand-in for a network ASR backend (the only non-real piece).

    Implements the ``AsrProvider`` seam so the REAL ``CompositeAsr`` fallback
    logic runs over it. ``raises``/empty segments drive the degraded + fallback
    branches we want to exercise across the pipeline.
    """

    def __init__(self, name: str, segments: list[AsrSegment] | None = None, *, raises: bool = False):
        self.name = name
        self._segments = segments or []
        self._raises = raises
        self.calls = 0

    def transcribe(self, audio, *, language, content_type):  # noqa: ANN001
        self.calls += 1
        if self._raises:
            raise RuntimeError("backend unavailable")
        return AsrResult(
            segments=list(self._segments),
            language=language,
            provider=self.name,
            degraded_count=sum(1 for s in self._segments if s.degraded),
        )

    def stream(self, audio_iter, *, language):  # noqa: ANN001
        for seg in self._segments:
            yield AsrEvent(type="segment", segment=seg, text=seg.text)


def _no_sleep(_s: float) -> None:
    return None


def _kinds(frames):  # noqa: ANN001
    return [f.split("\n", 1)[0].removeprefix("event: ") for f in frames]


def _data(frame: str) -> dict:
    line = [ln for ln in frame.splitlines() if ln.startswith("data: ")][0]
    return json.loads(line[len("data: ") :])


# --- 1. Happy path: ASR fallback -> note -> coding flow end-to-end -----------


def test_asr_fallback_feeds_note_generation_and_coding() -> None:
    """A VN code-switching encounter flows ASR(primary→fallback) → note → coding.

    The primary backend is empty so the REAL CompositeAsr falls back; the
    recovered transcript drives a complete SOAP note, and coding surfaces the
    diagnosis ICD + normalized meds (RxCUI) + the warfarin/aspirin DDI advisory.
    """

    primary = _BackendAsr("primary", [])  # empty -> triggers fallback
    fallback = _BackendAsr(
        "vn",
        [
            AsrSegment(text="Bệnh nhân tăng huyết áp nhiều năm.", speaker="patient"),
            AsrSegment(text="Đang dùng warfarin và aspirin.", speaker="clinician"),
        ],
    )
    asr = CompositeAsr(primary, fallback)

    # Seam 1: ASR seam produces the transcript via the fallback provider.
    result = asr.transcribe(b"audio", language="vi", content_type="audio/webm")
    assert result.provider == "vn"
    assert fallback.calls == 1
    transcript = result.text
    assert "tăng huyết áp" in transcript
    assert "warfarin" in transcript and "aspirin" in transcript

    # Seam 2: the recovered transcript drives a structurally-complete note.
    note = NoteGenerator().generate(transcript, "soap")
    assert list(note.sections.keys()) == ["Subjective", "Objective", "Assessment", "Plan"]
    assert note.insufficient_input is False

    # Seam 3: coding runs over the generated note text (additive, advisory).
    note_text = " ".join(note.sections.values())
    coding = CodingAssistant().suggest(note_text)
    assert "I10" in {c.code for c in coding.icd}  # hypertension diagnosis code
    rxcuis = {m.rxcui for m in coding.medications}
    assert "11289" in rxcuis  # warfarin
    assert "1191" in rxcuis  # aspirin
    assert coding.interactions  # warfarin + aspirin DDI advisory surfaced
    assert coding.advisory is True


# --- 2. Degraded/empty ASR: no fabrication propagates across components -------


def test_degraded_asr_yields_insufficient_note_and_empty_coding() -> None:
    """When both ASR backends fail, the pipeline fabricates nothing downstream."""

    primary = _BackendAsr("primary", raises=True)
    fallback = _BackendAsr("fallback", raises=True)
    asr = CompositeAsr(primary, fallback)

    result = asr.transcribe(b"audio", language="vi", content_type="audio/webm")
    assert result.segments == []  # totality: empty, never raises

    note = NoteGenerator().generate(result.text, "soap")
    # Empty transcript -> insufficient_input + all sections empty (no fabrication).
    assert note.insufficient_input is True
    assert all(v == "" for v in note.sections.values())

    coding = CodingAssistant().suggest(" ".join(note.sections.values()))
    # Nothing to code -> no ICD / meds / interactions invented.
    assert coding.icd == [] and coding.medications == [] and coding.interactions == []


def test_degraded_segment_text_never_reaches_note_or_coding() -> None:
    """A degraded chunk contributes no text, so nothing fabricated flows downstream."""

    primary = _BackendAsr(
        "primary",
        [
            AsrSegment(text="Bệnh nhân viêm họng.", speaker="patient"),
            AsrSegment(text="", speaker="unknown", degraded=True),  # degraded -> no text
        ],
    )
    asr = CompositeAsr(primary, None)
    result = asr.transcribe(b"audio", language="vi", content_type="audio/webm")
    # Degraded segment present but contributes no text to the transcript.
    assert result.degraded_count == 1
    assert result.text == "Bệnh nhân viêm họng."

    note = NoteGenerator().generate(result.text, "soap")
    coding = CodingAssistant().suggest(" ".join(note.sections.values()))
    # The real diagnosis still codes; the degraded (empty) chunk adds nothing.
    assert "J02.9" in {c.code for c in coding.icd}  # acute pharyngitis


# --- 3. Streaming pipeline + coding: SSE note text agrees with coding input ---


def test_stream_pipeline_then_coding_is_additive_and_consistent() -> None:
    """stream_scribe_sse (ASR seam + generator) → coding on the streamed note.

    Confirms the streamed terminal note text is exactly what coding consumes and
    that coding is additive metadata (the streamed note text is unchanged after
    coding runs over it).
    """

    backend = _BackendAsr(
        "vn",
        [
            AsrSegment(text="Bệnh nhân tăng huyết áp.", speaker="patient"),
            AsrSegment(text="Đang dùng warfarin và aspirin.", speaker="clinician"),
        ],
    )
    asr = CompositeAsr(backend, None)

    frames = list(
        stream_scribe_sse(
            b"audio",
            language="vi",
            asr=asr,
            generator=NoteGenerator(),
            template_id="soap",
            diarization_enabled=True,
            segment_delay=0,
            token_delay=0,
            sleep=_no_sleep,
        )
    )
    assert _kinds(frames)[0] == "start" and _kinds(frames)[-1] == "done"
    done = _data(frames[-1])
    assert done["transcript"] == "Bệnh nhân tăng huyết áp. Đang dùng warfarin và aspirin."

    streamed_sections = done["note"]["sections"]
    note_text = " ".join(streamed_sections.values())
    before = dict(streamed_sections)

    coding = CodingAssistant().suggest(note_text)
    assert "I10" in {c.code for c in coding.icd}
    assert {"11289", "1191"} <= {m.rxcui for m in coding.medications}
    assert coding.interactions  # DDI advisory from the streamed note's meds

    # Additive: running coding never mutated the streamed note text (Req 7.4).
    assert streamed_sections == before


def test_real_whisper_backend_degrades_then_fallback_recovers() -> None:
    """The REAL WhisperDeepSeekAsr (empty audio = no network) drives the fallback.

    Exercises the production composite shape — a real primary provider returning
    an empty result, recovered by the fallback — feeding a real note + coding.
    """

    primary = WhisperDeepSeekAsr()  # empty audio -> empty result, no socket
    fallback = _BackendAsr("vn", [AsrSegment(text="Bệnh nhân hen phế quản.", speaker="patient")])
    asr = CompositeAsr(primary, fallback)

    result = asr.transcribe(b"", language="vi", content_type="audio/webm")
    assert result.provider == "vn"  # fell back past the empty whisper result

    note = NoteGenerator().generate(result.text, "soap")
    coding = CodingAssistant().suggest(" ".join(note.sections.values()))
    assert "J45.909" in {c.code for c in coding.icd}  # asthma / hen
