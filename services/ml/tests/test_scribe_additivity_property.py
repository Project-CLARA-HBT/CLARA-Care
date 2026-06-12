"""Property 7: additive metadata never mutates note text or transcript (task 4.7).

*For any* generated note version and transcript, running any combination of the
grounding pass (``GroundingVerifier.verify``, Req 12), the structured-extraction
pass (``StructuredExtractor.extract``, Req 13), and the coding pass
(``CodingAssistant.suggest``, Req 14/7) — combined and in any order, with their
flags ENABLED so the passes actually execute — leaves the note's ``sections_json``
clinical text and the transcript (ASR segments + derived span registry) byte-for-byte
unchanged. The only outputs are the additive ``grounding_json`` / ``extraction_json``
/ ``coding_json`` metadata.

Validates: Requirements 12.6, 13.5, 14.7
"""

from __future__ import annotations

import copy
import itertools
from collections.abc import Callable

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_ml.scribe.asr.base import SPEAKERS, AsrSegment
from clara_ml.scribe.coding import CodingAssistant
from clara_ml.scribe.extraction import StructuredExtractor
from clara_ml.scribe.generator import Note, NoteGenerator
from clara_ml.scribe.grounding import GroundingVerifier
from clara_ml.scribe.provenance import SpanRegistry, build_span_registry
from clara_ml.scribe.templates import list_templates

# ---------------------------------------------------------------------------
# Smart generators: clinical-ish transcript/note content that actually drives
# the grounding/extraction/coding passes down their real (non-inert) paths —
# meds + doses, vitals, allergies, problems, ICD-mappable diagnoses — mixed with
# Vietnamese, empty, and arbitrary-unicode text so the property is exercised
# across the whole input space (not just happy-path English).
# ---------------------------------------------------------------------------

_CLINICAL_SENTENCES: list[str] = [
    # English: meds + doses (extraction/coding hooks) and grounded statements.
    "Patient reports a headache for three days.",
    "Start lisinopril 10mg once daily.",
    "Administer warfarin 5mg nightly.",
    "Continue metformin 500mg twice daily.",
    "Blood pressure is 120/80 today.",
    "Heart rate 72 bpm, temperature 37.0 C.",
    "SpO2 98% on room air.",
    "Patient is allergic to penicillin.",
    "No known drug allergies.",
    "Diagnosed with type 2 diabetes and hypertension.",
    "Past medical history of asthma.",
    "Patient complains of chest pain and shortness of breath.",
    # Vietnamese (code-switching, diacritics): meds/vitals/problems.
    "Bệnh nhân bị tăng huyết áp.",
    "Kê metformin 500mg hai lần mỗi ngày.",
    "Nhiệt độ 38 C, mạch 90 bpm.",
    "Tiền sử hen phế quản.",
    "Chẩn đoán viêm phổi.",
    "Dị ứng với penicillin.",
    # Degenerate / boundary content.
    "",
    "   ",
    "\n\t",
]

# A single segment's text: clinical phrase, arbitrary unicode, or VN-ish text.
_segment_text = st.one_of(
    st.sampled_from(_CLINICAL_SENTENCES),
    st.text(max_size=60),
    st.text(alphabet="aáàảãạâbcđeéèêghiíìklmnoóòôơpqrstuúùưvxy 0123456789mg/", max_size=60),
)

_segment = st.builds(
    AsrSegment,
    text=_segment_text,
    speaker=st.sampled_from(SPEAKERS),
    degraded=st.booleans(),
)

# A transcript: an ordered list of ASR segments (may be empty).
_segments = st.lists(_segment, max_size=8)

_TEMPLATE_IDS = [t.id for t in list_templates()]


@st.composite
def _note_and_segments(draw: st.DrawFn) -> tuple[Note, list[AsrSegment]]:
    """Draw a (note, segments) pair with clinically meaningful section content.

    The note is built directly into a randomly chosen template's section keys,
    each section filled with 0..3 sampled clinical sentences (so critical-safety
    statements, meds, vitals, and ungrounded claims all appear), guaranteeing the
    passes traverse their real logic rather than the empty/no-op path.
    """

    segments = draw(_segments)
    template = draw(st.sampled_from(list_templates()))
    sections: dict[str, str] = {}
    for key in template.section_keys:
        parts = draw(st.lists(st.sampled_from(_CLINICAL_SENTENCES), max_size=3))
        sections[key] = " ".join(parts).strip()
    note = Note(template_id=template.id, sections=sections)
    return note, segments


# ---------------------------------------------------------------------------
# Pass runners (each ENABLED so it actually executes) keyed by name. Every
# runner only READS the note + registry and returns additive metadata.
# ---------------------------------------------------------------------------

PassRunner = Callable[[Note, SpanRegistry], object]


def _run_grounding(note: Note, registry: SpanRegistry) -> object:
    return GroundingVerifier(enabled=True).verify(note, registry)


def _run_extraction(note: Note, registry: SpanRegistry) -> object:
    return StructuredExtractor(enabled=True, lexicon_lookup=lambda _s: None).extract(registry)


def _run_coding(note: Note, registry: SpanRegistry) -> object:
    note_text = "\n".join(note.sections.values())
    return CodingAssistant().suggest(note_text)


_RUNNERS: dict[str, PassRunner] = {
    "grounding": _run_grounding,
    "extraction": _run_extraction,
    "coding": _run_coding,
}


def _snapshot(note: Note, segments: list[AsrSegment], registry: SpanRegistry):
    """Deep-copy snapshots of everything the passes must never mutate."""

    return (
        copy.deepcopy(note.sections),
        copy.deepcopy(note.template_id),
        copy.deepcopy(segments),
        [s.text for s in segments],
        [(s.span_id, s.text) for s in registry.spans()],
    )


def _assert_unchanged(note, segments, registry, snap) -> None:
    sections_snap, template_snap, segments_snap, seg_text_snap, spans_snap = snap
    # Note clinical text byte-for-byte unchanged (additive metadata only).
    assert note.sections == sections_snap
    assert note.template_id == template_snap
    # Transcript segments (text + order + all fields) byte-for-byte unchanged.
    assert segments == segments_snap
    assert [s.text for s in segments] == seg_text_snap
    # Derived transcript span registry unchanged (ids + read-only snippet text).
    assert [(s.span_id, s.text) for s in registry.spans()] == spans_snap


# ---------------------------------------------------------------------------
# Property 7 — combined application: running ALL three passes leaves the note
# sections text and the transcript byte-for-byte unchanged.
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 7: Additive metadata never mutates
# Validates: Requirements 12.6, 13.5, 14.7
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_note_and_segments())
def test_p7_combined_passes_never_mutate(data) -> None:
    note, segments = data
    registry = build_span_registry(segments)
    snap = _snapshot(note, segments, registry)

    # Run grounding + extraction + coding combined (all flags enabled).
    _run_grounding(note, registry)
    _run_extraction(note, registry)
    _run_coding(note, registry)

    _assert_unchanged(note, segments, registry, snap)


# ---------------------------------------------------------------------------
# Property 7 — order independence: the mutation-freedom invariant holds for
# EVERY ordering of the three passes (additivity must not depend on sequence).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 7: Additive metadata never mutates
# Validates: Requirements 12.6, 13.5, 14.7
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    data=_note_and_segments(),
    order=st.permutations(["grounding", "extraction", "coding"]),
)
def test_p7_mutation_freedom_is_order_independent(data, order) -> None:
    note, segments = data
    registry = build_span_registry(segments)
    snap = _snapshot(note, segments, registry)

    for name in order:
        _RUNNERS[name](note, registry)
        # The invariant holds after EACH step, not only at the end.
        _assert_unchanged(note, segments, registry, snap)


# ---------------------------------------------------------------------------
# Property 7 — generated-note path: a note produced by the real NoteGenerator
# (deterministic, no-LLM) is equally immune to mutation by the combined passes.
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 7: Additive metadata never mutates
# Validates: Requirements 12.6, 13.5, 14.7
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(segments=_segments, template_id=st.sampled_from(_TEMPLATE_IDS))
def test_p7_generated_note_path_never_mutates(segments, template_id) -> None:
    transcript = "\n".join(s.text for s in segments)
    note = NoteGenerator(llm_complete=None).generate(transcript, template_id)
    registry = build_span_registry(segments)
    snap = _snapshot(note, segments, registry)
    transcript_snap = transcript

    # Apply every combination (non-empty subsets) of the three passes.
    names = ["grounding", "extraction", "coding"]
    for r in range(1, len(names) + 1):
        for combo in itertools.combinations(names, r):
            for name in combo:
                _RUNNERS[name](note, registry)
            _assert_unchanged(note, segments, registry, snap)
            assert transcript == transcript_snap
