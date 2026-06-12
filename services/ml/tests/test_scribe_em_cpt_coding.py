"""Unit tests for the Scribe CodingAssistant E/M + CPT extension (task 5.1, Req 14).

Covers: defensible E/M level across documentation richness; the anti-upcoding
guarantee (suggested level never exceeds the defensible ceiling, including a case
where a naive breadth heuristic would over-code); every suggestion carries a
justifying span and is advisory/`selected=False`; Vietnamese localization; the
flag-off inert path; no note-text mutation; and `as_dict` serialization.
"""

from __future__ import annotations

import clara_ml.rag.store  # noqa: F401 - import-order guard for the known cycle
from clara_ml.scribe.coding import CodingAssistant, EmCptSuggestion
from clara_ml.scribe.generator import NoteGenerator

# --- representative note texts ---------------------------------------------

# Rich BREADTH (lots of history/exam language, long) but THIN medical
# decision-making: a single self-limited problem, no prescription, no data, no
# risk. A naive "more words = higher level" heuristic would over-code this.
_BREADTH_ONLY_NOTE = (
    "History of present illness: patient presents with a mild headache for one "
    "day. Review of systems is otherwise negative. Past medical history is "
    "noncontributory. Family history reviewed and unremarkable. Social history "
    "obtained, non-smoker. Physical exam: general appearance well, comprehensive "
    "exam performed, HEENT normal, lungs clear, abdomen soft and non-tender. "
    "Detailed examination shows no acute distress and stable vital signs today."
)

# Full moderate-complexity MDM: two chronic problems + prescription management +
# data reviewed (no high-risk markers).
_MODERATE_MDM_NOTE = (
    "Patient with hypertension and type 2 diabetes for follow-up. "
    "Prescribed lisinopril and adjusted the dose. Ordered a CBC and an ECG, "
    "results reviewed."
)

# High-complexity MDM: chronic problems + prescription + data + high-risk.
_HIGH_MDM_NOTE = (
    "Patient with heart failure and chronic kidney disease, now with severe "
    "shortness of breath. Prescribed IV diuretics. Ordered labs and chest x-ray. "
    "Decision to admit to hospital for intensive monitoring."
)

# Vietnamese-first moderate note (code-switching English drug name preserved).
_VN_MODERATE_NOTE = (
    "Bệnh nhân tăng huyết áp và đái tháo đường tái khám. Kê đơn thuốc metformin "
    "và chỉnh liều. Chỉ định xét nghiệm công thức máu, đánh giá kết quả."
)


def _enabled() -> CodingAssistant:
    """A CodingAssistant with the R14 pass force-enabled (flag-independent)."""

    return CodingAssistant(em_cpt_enabled=True)


# --- defensible level across documentation richness ------------------------


def test_defensible_level_grows_with_documentation_richness() -> None:
    a = _enabled()
    minimal = a.defensible_em_level("")
    breadth_only = a.defensible_em_level(_BREADTH_ONLY_NOTE)
    moderate = a.defensible_em_level(_MODERATE_MDM_NOTE)
    high = a.defensible_em_level(_HIGH_MDM_NOTE)

    assert minimal == 1  # nothing documented
    assert breadth_only == 2  # one self-limited problem, no real MDM
    assert moderate == 4  # 2 chronic + Rx management + data
    assert high == 5  # + high-risk admit decision
    assert minimal < breadth_only < moderate < high


def test_defensible_level_is_bounded_1_to_5() -> None:
    a = _enabled()
    for note in ("", _BREADTH_ONLY_NOTE, _MODERATE_MDM_NOTE, _HIGH_MDM_NOTE, _VN_MODERATE_NOTE):
        level = a.defensible_em_level(note)
        assert 1 <= level <= 5


# --- anti-upcoding: suggested level never exceeds the defensible ceiling ----


def test_suggested_em_level_never_exceeds_defensible_level() -> None:
    a = _enabled()
    for note in (_BREADTH_ONLY_NOTE, _MODERATE_MDM_NOTE, _HIGH_MDM_NOTE, _VN_MODERATE_NOTE):
        defensible = a.defensible_em_level(note)
        em = [s for s in a.suggest_em_cpt(note) if s.kind == "E/M"]
        assert em, f"expected an E/M suggestion for: {note[:40]!r}"
        assert em[0].level is not None
        assert em[0].level <= defensible


def test_breadth_heavy_note_is_not_upcoded() -> None:
    # The breadth-only note reads "comprehensive/detailed" with lots of history
    # and exam language, but the documented MDM only defensibly supports level 2.
    # The suggestion must stay at the defensible ceiling, not the inflated breadth.
    a = _enabled()
    defensible = a.defensible_em_level(_BREADTH_ONLY_NOTE)
    em = next(s for s in a.suggest_em_cpt(_BREADTH_ONLY_NOTE) if s.kind == "E/M")

    assert defensible == 2
    assert em.level == 2
    assert em.code == "99212"
    # The rationale explains the anti-upcoding clamp happened.
    assert "anti-upcoding" in em.rationale.lower()


# --- every suggestion carries a span and is advisory / not selected ---------


def test_every_suggestion_has_a_justifying_span_and_is_advisory() -> None:
    a = _enabled()
    suggestions = a.suggest_em_cpt(_HIGH_MDM_NOTE)
    assert suggestions
    for s in suggestions:
        assert isinstance(s, EmCptSuggestion)
        assert s.spans and all(span.strip() for span in s.spans)  # justifying span(s)
        assert s.selected is False  # never auto-selected (Req 14.3/14.5)
        assert s.status == "advisory"
        assert s.code  # a concrete code is attached


def test_em_suggestion_carries_em_metadata() -> None:
    em = next(s for s in _enabled().suggest_em_cpt(_MODERATE_MDM_NOTE) if s.kind == "E/M")
    assert em.system == "E/M"
    assert em.level == 4
    assert em.code == "99214"


# --- CPT / procedure detection ---------------------------------------------


def test_cpt_procedure_detected_with_span() -> None:
    note = "Performed an ECG in clinic and administered a nebulizer treatment."
    cpts = [s for s in _enabled().suggest_em_cpt(note) if s.kind == "CPT"]
    codes = {c.code for c in cpts}
    assert "93000" in codes  # ECG
    assert "94640" in codes  # nebulizer
    for c in cpts:
        assert c.level is None
        assert c.spans and c.selected is False


def test_no_procedure_means_no_cpt_suggestion() -> None:
    cpts = [s for s in _enabled().suggest_em_cpt(_BREADTH_ONLY_NOTE) if s.kind == "CPT"]
    assert cpts == []  # nothing fabricated


# --- Vietnamese localization (Req 14.6) ------------------------------------


def test_vietnamese_localized_displays() -> None:
    a = _enabled()
    suggestions = a.suggest_em_cpt(_VN_MODERATE_NOTE)
    assert suggestions
    em = next(s for s in suggestions if s.kind == "E/M")
    # Bilingual: English display plus a Vietnamese-first localized label.
    assert em.display  # English present
    assert "Khám và quản lý" in em.display_vi
    # The VN note still yields the moderate defensible level.
    assert em.level == 4


def test_vietnamese_cpt_localization() -> None:
    note = "Đo điện tâm đồ cho bệnh nhân và lấy máu tĩnh mạch xét nghiệm."
    cpts = [s for s in _enabled().suggest_em_cpt(note) if s.kind == "CPT"]
    codes = {c.code for c in cpts}
    assert "93000" in codes  # điện tâm đồ -> ECG
    assert "36415" in codes  # lấy máu tĩnh mạch -> venipuncture
    ecg = next(c for c in cpts if c.code == "93000")
    assert "Điện tâm đồ" in ecg.display_vi


# --- flag-off inertness (Req 14.1) -----------------------------------------


def test_flag_off_em_cpt_is_inert() -> None:
    disabled = CodingAssistant(em_cpt_enabled=False)
    assert disabled.em_cpt_enabled is False
    assert disabled.suggest_em_cpt(_HIGH_MDM_NOTE) == []

    res = disabled.suggest(_HIGH_MDM_NOTE, lang="en")
    assert res.em_cpt == []
    # Legacy serialization is byte-for-byte: no "em_cpt" key when off.
    assert "em_cpt" not in res.as_dict()


def test_flag_on_populates_em_cpt_in_suggest_and_as_dict() -> None:
    res = CodingAssistant(em_cpt_enabled=True).suggest(_MODERATE_MDM_NOTE, lang="en")
    assert res.em_cpt  # populated when enabled
    payload = res.as_dict()
    assert "em_cpt" in payload
    assert isinstance(payload["em_cpt"], list) and payload["em_cpt"]


def test_empty_text_yields_no_suggestions_even_when_enabled() -> None:
    a = _enabled()
    assert a.suggest_em_cpt("") == []
    assert a.suggest_em_cpt("   ") == []


# --- additive: never mutates note text (Req 14.7) --------------------------


def test_em_cpt_is_additive_and_never_mutates_note_text() -> None:
    note = NoteGenerator().generate(
        "Patient with hypertension and diabetes. Prescribed lisinopril. Ordered an ECG.",
        "soap",
    )
    before = dict(note.sections)
    combined = " ".join(note.sections.values())

    suggestions = _enabled().suggest_em_cpt(combined)

    assert note.sections == before  # note text untouched
    assert suggestions  # suggestions are separate metadata


# --- serialization ----------------------------------------------------------


def test_as_dict_serialization_shape() -> None:
    suggestions = _enabled().suggest_em_cpt(_HIGH_MDM_NOTE)
    assert suggestions
    for s in suggestions:
        d = s.as_dict()
        assert set(d) == {
            "code",
            "kind",
            "system",
            "display",
            "display_vi",
            "level",
            "spans",
            "rationale",
            "selected",
            "status",
        }
        assert d["kind"] in {"E/M", "CPT"}
        assert d["selected"] is False
        assert d["status"] == "advisory"
        assert isinstance(d["spans"], list)


def test_structured_extraction_strengthens_defensible_level() -> None:
    # Providing structured-extraction problems/medications (Req 13 provenance)
    # raises the defensible MDM evidence even when the raw text is terse.
    class _Item:
        def __init__(self, surface: str) -> None:
            self.surface = surface

    class _Extraction:
        problems = [_Item("hypertension"), _Item("type 2 diabetes")]
        medications = [_Item("lisinopril")]

    a = _enabled()
    terse = "Follow-up visit, results reviewed."
    without = a.defensible_em_level(terse)
    with_extraction = a.defensible_em_level(terse, extraction=_Extraction())
    assert with_extraction > without
    assert with_extraction == 4  # 2 problems + medication (Rx) management
