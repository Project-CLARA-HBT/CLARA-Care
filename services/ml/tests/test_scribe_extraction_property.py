"""Property 9: structured-extraction provenance integrity + no-fabrication + RxCUI (task 4.9).

*For any* transcript, :meth:`StructuredExtractor.extract` (flag ENABLED, Req 13) must
satisfy three invariants over the four clinical types (problems, medications, allergies,
vitals):

PROVENANCE INTEGRITY (Req 13.2 / 13.3 / 13.6) — every extracted item carries a non-empty
``span_ids`` list and an extraction ``method`` (``"lexicon"`` | ``"regex"``), and EVERY
referenced span id resolves in the SAME session :class:`SpanRegistry` the extractor read
(the shared identifier space of Req 13.6). The item's surface text actually appears in the
resolved span's transcript text — so provenance points at real evidence, not a dangling id.

NO FABRICATION (Req 13.7) — every extracted item's surface is substring-derived from a real
transcript segment (nothing invented); and when a clinical type has no supporting evidence
in the transcript its list is EMPTY. Exercised with transcripts both with and without each
category (absent categories must yield ``[]``).

RxCUI MAPPING (Req 13.4) — when a medication surface resolves in the (injected or real) drug
lexicon, its ``rxcui`` equals the lexicon's rxcui; when it does NOT resolve, ``rxcui is None``
and the surface text is preserved (graceful degradation). Validated against an INDEPENDENT
recomputation through the SAME ``lexicon_lookup`` callable — so the mapping is genuinely
tested, not tautological — using both a deterministic injected lexicon and the real
``rag.normalize.drug_lexicon.lookup``.

Validates: Requirements 13.2, 13.3, 13.4, 13.6, 13.7
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_ml.rag.normalize.drug_lexicon import lookup as real_lexicon_lookup
from clara_ml.scribe.asr.base import SPEAKERS, AsrSegment
from clara_ml.scribe.extraction import (
    METHOD_LEXICON,
    METHOD_REGEX,
    ExtractedItem,
    ExtractedMedication,
    ExtractedVital,
    StructuredExtraction,
    StructuredExtractor,
)
from clara_ml.scribe.provenance import SpanRegistry, build_span_registry

# ---------------------------------------------------------------------------
# Smart generators.
#
# Per-category sentence pools, each EMPIRICALLY verified (see task notes) to
# trigger ONLY its own clinical type under the extractor — and a neutral pool
# that triggers nothing. This lets the "absent category => []" invariant be
# asserted precisely: a category is present iff one of its sentences is drawn.
#
# Medication sentences use a "<verb> <drug> <dose>" shape so a medication is
# extracted via the dose-context path even when the surface is NOT in the
# lexicon (graceful-degradation path), and via the lexicon path when it is.
# ---------------------------------------------------------------------------

_METHODS = {METHOD_LEXICON, METHOD_REGEX}

_PROBLEM_SENTENCES: list[str] = [
    "Diagnosed with diabetes.",
    "Past medical history of asthma.",
    "Patient complains of chest pain.",
    "Presents with cough.",
    "Chẩn đoán viêm phổi.",
]

_ALLERGY_SENTENCES: list[str] = [
    "Patient is allergic to penicillin.",
    "Allergy to peanuts.",
    "Dị ứng với penicillin.",
]

_VITAL_SENTENCES: list[str] = [
    "Blood pressure is 120/80 today.",
    "Heart rate 72 bpm.",
    "Temperature 37.0 C.",
    "SpO2 98% on room air.",
]

_NEUTRAL_SENTENCES: list[str] = [
    "The clinician greeted the patient.",
    "Follow up scheduled next week.",
    "Bệnh nhân cảm thấy ổn hơn.",
    "",
    "   ",
]

_VERBS = ["Start", "Administer", "Continue", "Take", "Give", "Prescribe"]
_DOSES = ["10mg", "5mg", "500mg", "250mg", "75mg"]

# Real lexicon drugs (resolve to an RxCUI) + fictional drugs (never resolve).
_REAL_DRUGS = ["lisinopril", "metformin", "warfarin", "amoxicillin", "ibuprofen", "aspirin"]
_FICTIONAL_DRUGS = ["zelphamax", "quorbidol", "trambivex", "blorinax", "glarbnium"]

_CATEGORY_POOLS: dict[str, list[str]] = {
    "problems": _PROBLEM_SENTENCES,
    "allergies": _ALLERGY_SENTENCES,
    "vitals": _VITAL_SENTENCES,
}


def _med_sentence(verb: str, drug: str, dose: str) -> str:
    return f"{verb} {drug} {dose}."


@st.composite
def _segments_with_categories(draw: st.DrawFn) -> tuple[list[AsrSegment], set[str]]:
    """Draw transcript segments + the SET of clinical categories truly present.

    A non-empty subset of {problems, medications, allergies, vitals} is chosen;
    each chosen category contributes >=1 of its own (single-category) sentences,
    interleaved with neutral filler. Returned ``present`` is exactly the chosen
    set, so excluded categories are guaranteed absent from the transcript.
    """

    categories = ["problems", "medications", "allergies", "vitals"]
    present = set(draw(st.lists(st.sampled_from(categories), min_size=1, unique=True)))

    sentences: list[str] = []
    for cat in present:
        if cat == "medications":
            n = draw(st.integers(min_value=1, max_value=3))
            for _ in range(n):
                drug = draw(st.sampled_from(_REAL_DRUGS + _FICTIONAL_DRUGS))
                sentences.append(
                    _med_sentence(
                        draw(st.sampled_from(_VERBS)), drug, draw(st.sampled_from(_DOSES))
                    )
                )
        else:
            sentences.extend(
                draw(st.lists(st.sampled_from(_CATEGORY_POOLS[cat]), min_size=1, max_size=3))
            )

    # Neutral filler segments that trigger no category.
    sentences.extend(draw(st.lists(st.sampled_from(_NEUTRAL_SENTENCES), max_size=4)))
    draw(st.randoms()).shuffle(sentences)

    segments = [
        AsrSegment(text=text, speaker=draw(st.sampled_from(SPEAKERS))) for text in sentences
    ]
    return segments, present


@st.composite
def _neutral_segments(draw: st.DrawFn) -> list[AsrSegment]:
    """Draw a transcript of PURELY neutral filler (no clinical evidence at all)."""

    texts = draw(st.lists(st.sampled_from(_NEUTRAL_SENTENCES), max_size=8))
    return [AsrSegment(text=t, speaker=draw(st.sampled_from(SPEAKERS))) for t in texts]


# ---------------------------------------------------------------------------
# Injected deterministic lexicon (controls the RxCUI mapping for the property).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeLexEntry:
    """Minimal lexicon entry: only ``rxcui`` is read by the extractor."""

    rxcui: str


# Surface (normalized) -> rxcui. A deliberate mix of real + fictional drugs, so
# the injected lexicon resolves some surfaces the real lexicon would not, and
# vice-versa — making the "rxcui == lexicon's rxcui" check non-tautological.
_INJECTED_RXCUI: dict[str, str] = {
    "lisinopril": "29046",
    "metformin": "6809",
    "zelphamax": "900001",
    "quorbidol": "900002",
}


def _injected_lookup(surface: str) -> _FakeLexEntry | None:
    if not surface:
        return None
    key = surface.strip().casefold()
    rxcui = _INJECTED_RXCUI.get(key)
    return _FakeLexEntry(rxcui) if rxcui is not None else None


def _expected_rxcui(surface: str, lookup) -> str | None:
    """The rxcui the extractor MUST record: the lexicon's rxcui, else None."""

    entry = lookup(surface)
    if entry is None:
        return None
    rxcui = str(getattr(entry, "rxcui", "")) or None
    return rxcui


# ---------------------------------------------------------------------------
# Shared item iteration helpers.
# ---------------------------------------------------------------------------


def _all_items(extraction: StructuredExtraction) -> list[tuple[str, str, object]]:
    """Flatten every extracted item to ``(category, surface, provenance)``."""

    items: list[tuple[str, str, object]] = []
    for p in extraction.problems:
        items.append(("problems", p.surface, p.provenance))
    for m in extraction.medications:
        items.append(("medications", m.surface, m.provenance))
    for a in extraction.allergies:
        items.append(("allergies", a.surface, a.provenance))
    for v in extraction.vitals:
        items.append(("vitals", v.surface, v.provenance))
    return items


def _present_categories(extraction: StructuredExtraction) -> set[str]:
    return {cat for cat, _s, _p in _all_items(extraction)}


def _assert_provenance_integrity(extraction: StructuredExtraction, registry: SpanRegistry) -> None:
    """Every item: non-empty resolvable span_ids + valid method + real surface."""

    for category, surface, provenance in _all_items(extraction):
        # (13.3) every item carries provenance: >=1 span id + a known method.
        assert provenance.span_ids, f"{category} item {surface!r} has no span_ids"
        assert provenance.method in _METHODS, f"bad method {provenance.method!r}"

        for span_id in provenance.span_ids:
            # (13.6) the span id resolves in the SAME shared registry.
            span = registry.resolve(span_id)
            assert span is not None, f"span {span_id!r} does not resolve in the registry"
            # (13.7) no fabrication: the surface is real transcript text.
            assert surface, "an extracted item must carry a non-empty surface"
            assert surface in span.text, (
                f"surface {surface!r} not found in resolved span text {span.text!r}"
            )


# ---------------------------------------------------------------------------
# Property 9a — PROVENANCE INTEGRITY + surface no-fabrication (Req 13.2/13.3/13.6/13.7).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 9: structured-extraction provenance integrity
# Validates: Requirements 13.2, 13.3, 13.6, 13.7
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_segments_with_categories())
def test_p9_every_item_has_resolvable_span_method_and_real_surface(data) -> None:
    segments, _present = data
    registry = build_span_registry(segments)
    extraction = StructuredExtractor(enabled=True, lexicon_lookup=_injected_lookup).extract(
        registry
    )
    _assert_provenance_integrity(extraction, registry)


# ---------------------------------------------------------------------------
# Property 9b — NO FABRICATION: absent categories yield [] (Req 13.7), and the
# four named types are extracted when present (Req 13.2).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 9: no fabrication on absence
# Validates: Requirements 13.2, 13.7
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_segments_with_categories())
def test_p9_absent_categories_are_empty_and_present_categories_extracted(data) -> None:
    segments, present = data
    registry = build_span_registry(segments)
    extraction = StructuredExtractor(enabled=True, lexicon_lookup=_injected_lookup).extract(
        registry
    )
    extracted = _present_categories(extraction)

    # (13.7) every category absent from the transcript yields an empty list.
    absent = {"problems", "medications", "allergies", "vitals"} - present
    assert extracted & absent == set(), (
        f"fabricated items for absent categories: {sorted(extracted & absent)}"
    )
    # (13.2) every category that WAS spoken is actually extracted (no silent drop).
    assert present <= extracted, f"missed present categories: {sorted(present - extracted)}"


# Feature: clara-scribe-enterprise, Property 9: no fabrication on absence
# Validates: Requirements 13.7
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(segments=_neutral_segments())
def test_p9_neutral_transcript_extracts_nothing(segments) -> None:
    registry = build_span_registry(segments)
    extraction = StructuredExtractor(enabled=True, lexicon_lookup=_injected_lookup).extract(
        registry
    )
    # A transcript with zero clinical evidence fabricates nothing in any category.
    assert extraction.problems == []
    assert extraction.medications == []
    assert extraction.allergies == []
    assert extraction.vitals == []


# ---------------------------------------------------------------------------
# Property 9c — RxCUI MAPPING via an INJECTED deterministic lexicon (Req 13.4).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 9: RxCUI mapping (injected lexicon)
# Validates: Requirements 13.4
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_segments_with_categories())
def test_p9_rxcui_matches_injected_lexicon(data) -> None:
    segments, _present = data
    registry = build_span_registry(segments)
    extraction = StructuredExtractor(enabled=True, lexicon_lookup=_injected_lookup).extract(
        registry
    )

    for med in extraction.medications:
        expected = _expected_rxcui(med.surface, _injected_lookup)
        # Resolves => rxcui equals the lexicon's; otherwise None (graceful degrade).
        assert med.rxcui == expected, (
            f"med {med.surface!r}: rxcui {med.rxcui!r} != expected {expected!r}"
        )
        # Surface is always preserved regardless of resolution (Req 13.4).
        assert med.surface
        if expected is None:
            assert med.rxcui is None


# ---------------------------------------------------------------------------
# Property 9d — RxCUI MAPPING via the REAL drug lexicon (Req 13.4): genuinely
# reuses ``rag.normalize.drug_lexicon.lookup``, cross-checked independently.
# ---------------------------------------------------------------------------


@st.composite
def _medication_segments(draw: st.DrawFn) -> list[AsrSegment]:
    """Draw a transcript of medication sentences mixing real + fictional drugs."""

    n = draw(st.integers(min_value=1, max_value=6))
    texts: list[str] = []
    for _ in range(n):
        drug = draw(st.sampled_from(_REAL_DRUGS + _FICTIONAL_DRUGS))
        texts.append(
            _med_sentence(draw(st.sampled_from(_VERBS)), drug, draw(st.sampled_from(_DOSES)))
        )
    texts.extend(draw(st.lists(st.sampled_from(_NEUTRAL_SENTENCES), max_size=3)))
    return [AsrSegment(text=t) for t in texts]


# Feature: clara-scribe-enterprise, Property 9: RxCUI mapping (real lexicon)
# Validates: Requirements 13.4
@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(segments=_medication_segments())
def test_p9_rxcui_matches_real_drug_lexicon(segments) -> None:
    registry = build_span_registry(segments)
    # Default constructor uses the real rag.normalize.drug_lexicon.lookup.
    extraction = StructuredExtractor(enabled=True).extract(registry)

    for med in extraction.medications:
        expected = _expected_rxcui(med.surface, real_lexicon_lookup)
        assert med.rxcui == expected, (
            f"med {med.surface!r}: rxcui {med.rxcui!r} != real-lexicon {expected!r}"
        )
        # Known drug => lexicon method; unknown => regex (dose-context) + None.
        if expected is not None:
            assert med.provenance.method == METHOD_LEXICON
        else:
            assert med.rxcui is None
        assert med.surface  # surface preserved either way


# ---------------------------------------------------------------------------
# Property 9e — typed-item provenance (each concrete item type carries its own
# resolvable provenance), guarding the per-type dataclasses directly.
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 9: typed-item provenance integrity
# Validates: Requirements 13.3, 13.6
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_segments_with_categories())
def test_p9_typed_items_carry_resolvable_provenance(data) -> None:
    segments, _present = data
    registry = build_span_registry(segments)
    extraction = StructuredExtractor(enabled=True, lexicon_lookup=_injected_lookup).extract(
        registry
    )

    for item in [*extraction.problems, *extraction.allergies]:
        assert isinstance(item, ExtractedItem)
        assert all(registry.resolve(sid) is not None for sid in item.provenance.span_ids)
    for med in extraction.medications:
        assert isinstance(med, ExtractedMedication)
        assert all(registry.resolve(sid) is not None for sid in med.provenance.span_ids)
    for vital in extraction.vitals:
        assert isinstance(vital, ExtractedVital)
        assert vital.kind and vital.value
        assert all(registry.resolve(sid) is not None for sid in vital.provenance.span_ids)
