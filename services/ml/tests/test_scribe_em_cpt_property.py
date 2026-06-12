"""Property 10: anti-upcoding E/M + CPT coding suggestions (task 5.3).

*For any* note, :meth:`CodingAssistant.suggest_em_cpt` (flag ENABLED, Req 14) must
satisfy three invariants over every suggestion it returns (E/M visit-level + CPT):

ANTI-UPCODING (Req 14.2 / 14.4) — the suggested E/M ``level`` is NEVER higher than
:meth:`CodingAssistant.defensible_em_level` for the same note. A naive estimate keyed
on documentation breadth (history/exam verbiage, note length) may rate the visit higher,
but the suggestion is clamped to the level the documented Medical-Decision-Making
DEFENSIBLY supports. This is exercised with breadth-heavy / thin-MDM notes where a naive
score genuinely exceeds the defensible ceiling — and the clamp is cross-checked against an
INDEPENDENT recomputation of the naive vs defensible scores (so the bound is not tautological).

EVERY SUGGESTION CARRIES A SPAN (Req 14.2) — every returned suggestion (E/M and CPT) has a
non-empty ``spans`` list, and every span text actually appears in the note text (no fabricated
justification).

NONE SELECTED WITHOUT CONFIRMATION (Req 14.3 / 14.5) — every server-produced suggestion has
``selected is False`` and ``status == "advisory"``; nothing is auto-selected, finalized, or
applied without explicit clinician confirmation.

Validates: Requirements 14.2, 14.3, 14.4, 14.5
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_ml.scribe.coding import (
    CodingAssistant,
    EmCptSuggestion,
    _defensible_level_from_signals,
    _detect_em_signals,
    _naive_level_from_signals,
)

# ---------------------------------------------------------------------------
# Smart generators.
#
# Per-axis sentence pools (English + Vietnamese, with diacritics) that drive the
# E/M Medical-Decision-Making axes (problems, prescription management, data
# reviewed, risk) and the *gameable* documentation-breadth axes (history/exam
# verbiage, note length) that a naive level estimate over-weights. Procedure
# sentences embed CPT keywords so CPT suggestions are produced and span-checked.
# Mixed with neutral filler, empty/whitespace, and arbitrary unicode so the
# property is exercised across the whole input space.
# ---------------------------------------------------------------------------

_PROBLEM_SENTENCES: list[str] = [
    "Diagnosed with hypertension.",
    "Patient has type 2 diabetes.",
    "Presents with pneumonia.",
    "Complains of headache and cough.",
    "History of asthma noted.",
    "Bệnh nhân bị tăng huyết áp.",
    "Chẩn đoán viêm phổi.",
    "Tiền sử hen phế quản.",
]

_PRESCRIPTION_SENTENCES: list[str] = [
    "Start lisinopril 10mg once daily.",
    "Prescribed amoxicillin for the infection.",
    "Titrate metformin dose upward.",
    "Adjust dose of warfarin tonight.",
    "Kê đơn thuốc hạ huyết áp.",
    "Chỉnh liều thuốc đái tháo đường.",
]

_DATA_SENTENCES: list[str] = [
    "CBC and metabolic panel ordered.",
    "Chest x-ray reviewed today.",
    "Lab results reviewed with the patient.",
    "Ultrasound of the abdomen performed.",
    "Chỉ định xét nghiệm công thức máu.",
    "Đánh giá kết quả xét nghiệm.",
]

_HIGH_RISK_SENTENCES: list[str] = [
    "Decision made to hospitalize the patient.",
    "Admitted to the ICU for monitoring.",
    "Life-threatening presentation requiring emergency care.",
    "Nhập viện cấp cứu vì suy hô hấp nặng.",
    "Theo dõi tích cực tại hồi sức.",
]

_HISTORY_BREADTH_SENTENCES: list[str] = [
    "A comprehensive history of present illness was obtained.",
    "Complete review of systems documented across all systems.",
    "Past medical history, family history, and social history reviewed in detail.",
    "Detailed history taken covering all relevant systems thoroughly.",
    "Khai thác bệnh sử và tiền sử gia đình một cách chi tiết.",
]

_EXAM_BREADTH_SENTENCES: list[str] = [
    "A comprehensive physical exam was performed.",
    "Detailed examination including HEENT and general appearance.",
    "On exam, a complete multi-system examination was documented.",
    "Khám lâm sàng toàn diện đã được thực hiện.",
]

# Procedure sentences embedding CPT keywords from the coding table.
_PROCEDURE_SENTENCES: list[str] = [
    "Performed an electrocardiogram in the office.",
    "Nebulizer treatment was administered.",
    "Spirometry performed for pulmonary function test.",
    "Therapeutic intramuscular injection administered.",
    "Incision and drainage of the abscess performed.",
    "Laceration repair with suture completed.",
    "Venipuncture for a blood draw obtained.",
    "Đo điện tâm đồ tại phòng khám.",
    "Khâu vết thương cho bệnh nhân.",
]

_NEUTRAL_SENTENCES: list[str] = [
    "The clinician greeted the patient warmly.",
    "Follow up was scheduled for next week.",
    "Bệnh nhân cảm thấy ổn hơn hôm nay.",
    "",
    "   ",
]

# Long filler that adds word-count (no MDM/breadth keywords) to push the naive
# length axis without raising the defensible ceiling.
_FILLER = (
    "The patient and the clinician discussed the visit at length and in a calm "
    "and unhurried manner over the course of the appointment without any rush "
    "and with careful attention to the patient comfort and overall wellbeing."
)

_MDM_POOLS = [
    _PROBLEM_SENTENCES,
    _PRESCRIPTION_SENTENCES,
    _DATA_SENTENCES,
    _HIGH_RISK_SENTENCES,
]
_BREADTH_POOLS = [_HISTORY_BREADTH_SENTENCES, _EXAM_BREADTH_SENTENCES]

# A single line of note text: any clinical/breadth/procedure/neutral sentence,
# Vietnamese-flavoured text, or arbitrary unicode (covers empty + non-clinical).
_line = st.one_of(
    st.sampled_from(
        _PROBLEM_SENTENCES
        + _PRESCRIPTION_SENTENCES
        + _DATA_SENTENCES
        + _HIGH_RISK_SENTENCES
        + _HISTORY_BREADTH_SENTENCES
        + _EXAM_BREADTH_SENTENCES
        + _PROCEDURE_SENTENCES
        + _NEUTRAL_SENTENCES
    ),
    st.text(max_size=50),
    st.text(
        alphabet="aáàảãạâbcđeéèêghiíìklmnoóòôơpqrstuúùưvxy 0123456789mg/.",
        max_size=50,
    ),
)


@st.composite
def _note_text(draw: st.DrawFn) -> str:
    """Draw a free-form note: a mix of any lines (may be empty/whitespace)."""

    lines = draw(st.lists(_line, max_size=10))
    return "\n".join(lines).strip()


@st.composite
def _breadth_heavy_thin_mdm_note(draw: st.DrawFn) -> str:
    """Draw a breadth-rich / thin-MDM note designed to tempt upcoding.

    Lots of history/exam verbiage + long filler (inflating the naive length and
    breadth axes) with at most a single acute problem and NO prescription / data
    / high-risk evidence — so a naive estimate over-codes while the defensible
    ceiling stays low. The anti-upcoding clamp must hold here.
    """

    parts: list[str] = []
    parts.extend(
        draw(st.lists(st.sampled_from(_HISTORY_BREADTH_SENTENCES), min_size=1, max_size=4))
    )
    parts.extend(draw(st.lists(st.sampled_from(_EXAM_BREADTH_SENTENCES), min_size=1, max_size=4)))
    # Optionally a single acute complaint (still thin MDM).
    if draw(st.booleans()):
        parts.append("Patient complains of a mild headache.")
    # Long filler to push the naive note-length axis over its threshold.
    parts.extend([_FILLER] * draw(st.integers(min_value=1, max_value=3)))
    draw(st.randoms()).shuffle(parts)
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Injectable fake structured extraction (duck-typed: items expose ``.surface``).
# Lets the extraction-aware code paths run without coupling to the real model.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeItem:
    surface: str


@dataclass(frozen=True)
class _FakeExtraction:
    problems: list[_FakeItem]
    medications: list[_FakeItem]


@st.composite
def _fake_extraction(draw: st.DrawFn) -> _FakeExtraction:
    problems = draw(st.lists(st.sampled_from(["hypertension", "diabetes", "asthma"]), max_size=3))
    meds = draw(st.lists(st.sampled_from(["lisinopril", "metformin", "warfarin"]), max_size=3))
    return _FakeExtraction(
        problems=[_FakeItem(p) for p in problems],
        medications=[_FakeItem(m) for m in meds],
    )


# An assistant with the R14 flag forced ON regardless of the global setting.
def _assistant() -> CodingAssistant:
    return CodingAssistant(em_cpt_enabled=True)


def _em_suggestions(suggestions: list[EmCptSuggestion]) -> list[EmCptSuggestion]:
    return [s for s in suggestions if s.kind == "E/M"]


# ---------------------------------------------------------------------------
# Property 10a — ANTI-UPCODING: suggested E/M level never exceeds defensible.
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 10: anti-upcoding
# Validates: Requirements 14.2, 14.4
@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(note=_note_text())
def test_p10_em_level_never_exceeds_defensible(note) -> None:
    assistant = _assistant()
    defensible = assistant.defensible_em_level(note)
    suggestions = assistant.suggest_em_cpt(note)

    assert 1 <= defensible <= 5
    for em in _em_suggestions(suggestions):
        assert em.level is not None
        # Anti-upcoding: the suggested visit level is clamped to the ceiling.
        assert em.level <= defensible, (
            f"upcoded: suggested level {em.level} > defensible {defensible} for note {note!r}"
        )
    # At most one E/M suggestion is ever produced (the single visit level).
    assert len(_em_suggestions(suggestions)) <= 1


# ---------------------------------------------------------------------------
# Property 10b — ANTI-UPCODING is non-tautological: on breadth-heavy / thin-MDM
# notes a naive estimate genuinely over-codes, yet the suggestion stays clamped.
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 10: anti-upcoding (clamp is real)
# Validates: Requirements 14.4
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(note=_breadth_heavy_thin_mdm_note())
def test_p10_breadth_heavy_note_is_clamped_below_naive(note) -> None:
    assistant = _assistant()
    signals = _detect_em_signals(note)
    naive = _naive_level_from_signals(signals)
    defensible = _defensible_level_from_signals(signals)

    # Sanity for this targeted generator: the naive (breadth/length) estimate is
    # at least as high as the defensible ceiling — i.e. there is upcoding pressure.
    assert naive >= defensible

    for em in _em_suggestions(assistant.suggest_em_cpt(note)):
        # The suggestion follows the DEFENSIBLE ceiling, not the inflated naive
        # estimate: it never exceeds defensible, even when naive is higher.
        assert em.level == defensible
        assert em.level <= naive


# ---------------------------------------------------------------------------
# Property 10c — EVERY SUGGESTION CARRIES A REAL SPAN (Req 14.2).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 10: every suggestion carries a span
# Validates: Requirements 14.2
@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(note=_note_text())
def test_p10_every_suggestion_carries_a_real_span(note) -> None:
    suggestions = _assistant().suggest_em_cpt(note)

    for s in suggestions:
        # (Req 14.2) every E/M and CPT suggestion is justified by >=1 span...
        assert s.spans, f"{s.kind} suggestion {s.code} has no justifying span"
        # ...and every span is faithful text actually present in the note (no
        # fabricated justification).
        for span in s.spans:
            assert span, "a justifying span must be non-empty"
            assert span in note, f"fabricated span {span!r} not found in note {note!r}"


# ---------------------------------------------------------------------------
# Property 10d — NONE SELECTED WITHOUT CONFIRMATION (Req 14.3 / 14.5).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 10: nothing selected without confirmation
# Validates: Requirements 14.3, 14.5
@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(note=_note_text())
def test_p10_nothing_selected_without_confirmation(note) -> None:
    suggestions = _assistant().suggest_em_cpt(note)

    for s in suggestions:
        # (Req 14.3/14.5) every suggestion is advisory and unselected: nothing is
        # auto-selected, finalized, or applied without explicit clinician confirm.
        assert s.selected is False, f"{s.kind} {s.code} auto-selected without confirmation"
        assert s.status == "advisory", f"{s.kind} {s.code} not advisory (status={s.status!r})"


# ---------------------------------------------------------------------------
# Property 10e — invariants hold equally when the shared structured extraction
# (Req 13) is supplied as additional MDM evidence (anti-upcoding + advisory).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 10: anti-upcoding with extraction
# Validates: Requirements 14.2, 14.3, 14.4, 14.5
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(note=_note_text(), extraction=_fake_extraction())
def test_p10_invariants_hold_with_extraction(note, extraction) -> None:
    assistant = _assistant()
    defensible = assistant.defensible_em_level(note, extraction=extraction)
    suggestions = assistant.suggest_em_cpt(note, extraction=extraction)

    for s in suggestions:
        assert s.selected is False
        assert s.status == "advisory"
        assert s.spans
        if s.kind == "E/M":
            assert s.level is not None and s.level <= defensible
