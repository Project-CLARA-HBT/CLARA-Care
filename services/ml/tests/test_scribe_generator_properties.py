"""Property + unit tests for the Scribe NoteGenerator (Properties 1 & 3).

Property 1 (template completeness): for any template + any transcript, the note's
sections have EXACTLY the template's section keys.
Property 3 (no fabrication on empty/degraded input): empty/unusable transcript →
all sections empty + insufficient_input; deterministic fallback never invents
content beyond the transcript.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from clara_ml.scribe.generator import NoteGenerator
from clara_ml.scribe.templates import list_templates

_TEMPLATE_IDS = [t.id for t in list_templates()]
_template_id = st.sampled_from(_TEMPLATE_IDS + ["unknown-template", "", None])  # type: ignore[list-item]


# Feature: clara-scribe-enterprise, Property 1: Template completeness
# Validates: Requirements 6.2, 6.3
@given(transcript=st.text(max_size=400), template_id=_template_id)
def test_property1_sections_have_exactly_template_keys(transcript: str, template_id) -> None:
    note = NoteGenerator().generate(transcript, template_id)
    from clara_ml.scribe.templates import get_template

    expected = get_template(template_id) or get_template("soap")
    assert expected is not None
    assert set(note.sections.keys()) == set(expected.section_keys)
    assert note.template_id == expected.id
    # Every value is a string (possibly empty).
    assert all(isinstance(v, str) for v in note.sections.values())


# Feature: clara-scribe-enterprise, Property 3: No fabrication on empty input
# Validates: Requirements 6.4, 1.4
@given(blank=st.sampled_from(["", "   ", "\n\t", "ab"]))
def test_property3_empty_input_yields_empty_sections_flagged(blank: str) -> None:
    note = NoteGenerator().generate(blank, "soap")
    assert note.insufficient_input is True
    assert all(v == "" for v in note.sections.values())


# Feature: clara-scribe-enterprise, Property 3 (cont.): deterministic fallback
# never adds content not present in the transcript.
@given(transcript=st.text(min_size=3, max_size=300))
def test_property3_fallback_only_uses_transcript_tokens(transcript: str) -> None:
    note = NoteGenerator(llm_complete=None).generate(transcript, "soap")
    combined = " ".join(note.sections.values())
    # Fallback content is a normalized substring projection of the transcript:
    # every non-space token in the note appears in the transcript token set.
    transcript_tokens = set(transcript.split())
    for token in combined.split():
        assert token in transcript_tokens


def test_llm_path_structure_enforced_even_with_extra_keys() -> None:
    # An LLM that returns extra/missing keys still yields exactly the template keys.
    def fake_llm(_prompt: str) -> str:
        return '{"Subjective": "s", "BOGUS": "x"}'

    note = NoteGenerator(llm_complete=fake_llm).generate("patient has cough", "soap")
    assert set(note.sections.keys()) == {"Subjective", "Objective", "Assessment", "Plan"}
    assert note.sections["Subjective"] == "s"
    assert note.sections["Objective"] == ""  # missing key filled empty


def test_llm_failure_degrades_to_deterministic() -> None:
    def boom(_prompt: str) -> str:
        raise RuntimeError("llm down")

    note = NoteGenerator(llm_complete=boom).generate("patient has cough", "soap")
    assert set(note.sections.keys()) == {"Subjective", "Objective", "Assessment", "Plan"}
    assert note.insufficient_input is False
