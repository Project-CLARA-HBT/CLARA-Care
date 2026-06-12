"""Focused unit tests for the Scribe NoteGenerator (task 1.6, Requirement 6).

These deterministic example tests complement the property tests in
``test_scribe_generator_properties.py`` by pinning the concrete behaviours the
task calls out:

* exact section keys for EVERY registered template (Req 6.2),
* ``insufficient_input`` on empty/whitespace transcript with all sections empty
  (Req 6.4),
* structure determinism — same template id always yields the same section keys
  regardless of transcript content (Req 6.3),
* no fabrication on empty input and no invented drugs/allergies in the
  deterministic fallback (Req 6.4/6.5),
* the generation prompt carries the shared assistive guardrail (Req 10.2).
"""

from __future__ import annotations

import pytest

from clara_ml.scribe.generator import _GUARDRAIL, NoteGenerator, _build_prompt
from clara_ml.scribe.templates import (
    DEFAULT_TEMPLATE_ID,
    get_template,
    list_templates,
)

_ALL_TEMPLATE_IDS = [t.id for t in list_templates()]


# --- Req 6.2: exact section keys for every template -------------------------


@pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
def test_generate_returns_exact_template_section_keys(template_id: str) -> None:
    template = get_template(template_id)
    assert template is not None
    note = NoteGenerator().generate("BN ho, sốt 2 ngày.", template_id)
    # Keys match exactly (no missing, no extra) and order is preserved.
    assert list(note.sections.keys()) == list(template.section_keys)
    assert note.template_id == template.id
    assert all(isinstance(v, str) for v in note.sections.values())


def test_unknown_template_falls_back_to_soap_default() -> None:
    for bad in ("does-not-exist", "", None):
        note = NoteGenerator().generate("patient reports a cough", bad)  # type: ignore[arg-type]
        soap = get_template(DEFAULT_TEMPLATE_ID)
        assert soap is not None
        assert list(note.sections.keys()) == list(soap.section_keys)
        assert note.template_id == DEFAULT_TEMPLATE_ID


def test_default_template_is_soap_when_no_id_given() -> None:
    note = NoteGenerator().generate("patient reports a cough")
    assert note.template_id == "soap"
    assert list(note.sections.keys()) == ["Subjective", "Objective", "Assessment", "Plan"]


# --- Req 6.4: insufficient_input on empty/unusable transcript ---------------


@pytest.mark.parametrize("blank", ["", "   ", "\n\t ", "\u00a0", "ab"])
@pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
def test_empty_or_unusable_transcript_flags_insufficient_and_empties(
    blank: str, template_id: str
) -> None:
    note = NoteGenerator().generate(blank, template_id)
    template = get_template(template_id)
    assert template is not None
    assert note.insufficient_input is True
    # Structure is still complete, but every section is an empty string.
    assert list(note.sections.keys()) == list(template.section_keys)
    assert all(v == "" for v in note.sections.values())


def test_insufficient_input_does_not_call_llm() -> None:
    calls: list[str] = []

    def tracking_llm(prompt: str) -> str:
        calls.append(prompt)
        return '{"Subjective": "should not appear"}'

    note = NoteGenerator(llm_complete=tracking_llm).generate("   ", "soap")
    # No LLM call for unusable input -> no chance to fabricate content.
    assert calls == []
    assert note.insufficient_input is True
    assert all(v == "" for v in note.sections.values())


# --- Req 6.3: structure determinism -----------------------------------------


@pytest.mark.parametrize("template_id", _ALL_TEMPLATE_IDS)
def test_structure_is_deterministic_across_transcripts(template_id: str) -> None:
    gen = NoteGenerator()
    transcripts = [
        "Bệnh nhân đau đầu.",
        "Patient on warfarin 5mg daily, allergic to penicillin.",
        "x" * 300,
        "   leading and trailing   ",
    ]
    key_sets = [list(gen.generate(t, template_id).sections.keys()) for t in transcripts]
    # Every transcript yields identical section keys for the same template.
    assert all(ks == key_sets[0] for ks in key_sets)


def test_repeated_generation_is_structurally_stable() -> None:
    gen = NoteGenerator()
    first = gen.generate("patient has a fever", "h_and_p")
    second = gen.generate("entirely different content here", "h_and_p")
    assert list(first.sections.keys()) == list(second.sections.keys())


# --- Req 6.4/6.5: no fabrication --------------------------------------------


def test_deterministic_fallback_only_uses_transcript_tokens() -> None:
    transcript = "Bệnh nhân ổn định, không dùng thuốc."
    note = NoteGenerator(llm_complete=None).generate(transcript, "soap")
    transcript_tokens = set(transcript.split())
    for value in note.sections.values():
        for token in value.split():
            assert token in transcript_tokens


def test_fallback_invents_no_drugs_or_allergies() -> None:
    # A transcript that mentions NO medication/allergy must not produce any.
    transcript = "Patient came in for a routine wellness check and felt fine."
    note = NoteGenerator(llm_complete=None).generate(transcript, "h_and_p")
    combined = " ".join(note.sections.values()).lower()
    for invented in ("penicillin", "warfarin", "aspirin", "amoxicillin", "allergic"):
        assert invented not in combined


def test_empty_input_fabricates_nothing_for_any_template() -> None:
    for template_id in _ALL_TEMPLATE_IDS:
        note = NoteGenerator().generate("", template_id)
        assert "".join(note.sections.values()) == ""


# --- Req 10.2: prompt carries the shared assistive guardrail ----------------


def test_generation_prompt_carries_assistive_guardrail() -> None:
    template = get_template("soap")
    assert template is not None
    prompt = _build_prompt(template, "patient reports chest pain")
    assert _GUARDRAIL in prompt
    # The guardrail forbids autonomous diagnosis/prescription + fabrication.
    lowered = _GUARDRAIL.lower()
    assert "diagnose" in lowered and "prescribe" in lowered
    assert "invent" in lowered or "not present" in lowered
    # The transcript is included and the exact section keys are requested.
    assert "patient reports chest pain" in prompt
    for key in template.section_keys:
        assert key in prompt
