"""Unit tests for the shared transcript-span / provenance model (task 4.1, Req 12, 13.6).

Covers deterministic derivation from persisted ASR segments, ``resolve(span_id)``
correctness, span-id stability across rebuilds, and the invariant that the
registry never mutates transcript text.
"""

from __future__ import annotations

import copy

from clara_ml.scribe.asr.base import AsrSegment
from clara_ml.scribe.provenance import (
    Provenance,
    SpanRegistry,
    TranscriptSpan,
    build_span_registry,
    segment_id_for,
)


def _segments() -> list[AsrSegment]:
    return [
        AsrSegment(text="Patient reports headache.", speaker="patient"),
        AsrSegment(text="BP 120/80 today.", speaker="clinician"),
        AsrSegment(text="", speaker="unknown", degraded=True),
        AsrSegment(text="Start lisinopril 10mg.", speaker="clinician"),
    ]


# --- data models ----------------------------------------------------------


def test_segment_id_for_is_zero_padded_and_positional() -> None:
    assert segment_id_for(0) == "seg-0000"
    assert segment_id_for(7) == "seg-0007"
    assert segment_id_for(1234) == "seg-1234"


def test_transcript_span_and_provenance_are_frozen_pure_data() -> None:
    span = TranscriptSpan(span_id="seg-0000", segment_id="seg-0000", end_char=5, text="hello")
    prov = Provenance(span_ids=["seg-0000"], method="lexicon")
    assert span.span_id == "seg-0000"
    assert prov.span_ids == ["seg-0000"]
    assert prov.method == "lexicon"
    # Provenance default is an empty list + empty method.
    empty = Provenance()
    assert empty.span_ids == []
    assert empty.method == ""


# --- deterministic derivation ---------------------------------------------


def test_full_segment_spans_derived_in_order() -> None:
    registry = build_span_registry(_segments())
    spans = registry.spans()
    assert [s.span_id for s in spans] == ["seg-0000", "seg-0001", "seg-0002", "seg-0003"]
    assert spans[0].text == "Patient reports headache."
    assert spans[0].start_char == 0
    assert spans[0].end_char == len("Patient reports headache.")
    # Degraded/empty segment still yields a (empty) resolvable span.
    assert spans[2].text == ""
    assert spans[2].end_char == 0


def test_derivation_is_deterministic_for_same_segments() -> None:
    a = build_span_registry(_segments()).spans()
    b = build_span_registry(_segments()).spans()
    assert a == b


def test_span_ids_stable_across_rebuilds() -> None:
    seg = _segments()
    first = SpanRegistry.from_segments(seg)
    second = SpanRegistry.from_segments(seg)
    for index in range(len(seg)):
        sid = segment_id_for(index)
        assert first.resolve(sid) == second.resolve(sid)
    # Sub-span ids are also stable across independent registries.
    s1 = first.make_span("seg-0001", 0, 2)
    s2 = second.make_span("seg-0001", 0, 2)
    assert s1 is not None and s2 is not None
    assert s1.span_id == s2.span_id == "seg-0001:0-2"
    assert s1 == s2


# --- resolve(span_id) ------------------------------------------------------


def test_resolve_full_segment_span() -> None:
    registry = build_span_registry(_segments())
    span = registry.resolve("seg-0003")
    assert span is not None
    assert span.segment_id == "seg-0003"
    assert span.text == "Start lisinopril 10mg."


def test_resolve_unknown_span_returns_none() -> None:
    registry = build_span_registry(_segments())
    assert registry.resolve("seg-9999") is None
    assert registry.resolve("not-a-span") is None
    assert registry.resolve("seg-0000:bad-range") is None
    assert registry.resolve("seg-9999:0-3") is None


def test_resolve_rederives_canonical_sub_span_without_prior_make_span() -> None:
    # A sub-span id that was never explicitly created still resolves consistently,
    # so grounding (4.2) and extraction (4.3) provenance always resolve.
    registry = build_span_registry(_segments())
    span = registry.resolve("seg-0000:0-7")
    assert span is not None
    assert span.segment_id == "seg-0000"
    assert span.start_char == 0
    assert span.end_char == 7
    assert span.text == "Patient"


def test_make_span_clamps_offsets_and_is_resolvable() -> None:
    registry = build_span_registry(_segments())
    span = registry.make_span("seg-0001", 3, 999)
    assert span is not None
    assert span.start_char == 3
    assert span.end_char == len("BP 120/80 today.")
    assert span.text == "120/80 today."
    # The derived span is now resolvable by its id.
    assert registry.resolve(span.span_id) == span


def test_make_span_full_range_collapses_to_segment_span() -> None:
    registry = build_span_registry(_segments())
    full = registry.make_span("seg-0000", 0, None)
    assert full is not None
    assert full.span_id == "seg-0000"  # not "seg-0000:0-25"


def test_make_span_unknown_segment_returns_none() -> None:
    registry = build_span_registry(_segments())
    assert registry.make_span("seg-9999", 0, 3) is None


def test_segment_text_lookup() -> None:
    registry = build_span_registry(_segments())
    assert registry.segment_text("seg-0001") == "BP 120/80 today."
    assert registry.segment_text("seg-9999") is None


def test_shared_span_ids_resolve_to_same_span_for_grounding_and_extraction() -> None:
    # Req 13.6: an extracted item and its grounding reference the SAME span ids.
    registry = build_span_registry(_segments())
    extraction_prov = Provenance(span_ids=["seg-0003:6-16"], method="lexicon")
    grounding_prov = Provenance(span_ids=["seg-0003:6-16"], method="nli")
    resolved_extraction = registry.resolve(extraction_prov.span_ids[0])
    resolved_grounding = registry.resolve(grounding_prov.span_ids[0])
    assert resolved_extraction is not None
    assert resolved_extraction == resolved_grounding
    assert resolved_extraction.text == "lisinopril"


# --- never mutates transcript text ----------------------------------------


def test_registry_never_mutates_segment_text() -> None:
    segments = _segments()
    snapshot = copy.deepcopy(segments)
    registry = build_span_registry(segments)
    # Exercise every read path.
    registry.spans()
    registry.make_span("seg-0000", 1, 4)
    registry.resolve("seg-0001:0-2")
    registry.resolve("seg-0003")
    # Original segments (text + order) are byte-for-byte unchanged.
    assert segments == snapshot
    assert [s.text for s in segments] == [s.text for s in snapshot]


def test_registry_snapshot_independent_of_caller_list() -> None:
    segments = _segments()
    registry = build_span_registry(segments)
    # Mutating the caller's list after construction must not change the registry.
    segments.append(AsrSegment(text="appended later"))
    assert registry.resolve("seg-0004") is None
    assert len(registry.spans()) == 4
