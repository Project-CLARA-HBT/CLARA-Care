"""Property test P14 — template/macro addition isolation (task 8.2, Requirement 19.5).

Design Property 14 (Validates: Requirements 19.5):

    *For any* existing template and any newly added specialty template or
    macro/snippet in the registry, the generated output of every pre-existing
    template is unchanged (adding a template or macro never alters the structure
    or output of existing templates).

The Requirement 6 base templates are always resolvable, while specialty templates
and clinician macros only enter the registry when
``RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED`` is on. Isolation therefore means: for
ANY base template and ANY transcript, generating the note yields byte-for-byte
identical output whether the specialty-templates/macros flag is OFF or ON.

This module also *reuses Property 1* (design: "the specialty-template completeness
criteria (19.2/19.4) reuse Property 1 rather than duplicating it"): for ANY
specialty template and ANY transcript, ``generate(...)`` returns exactly that
template's declared section keys, in order (completeness — Req 19.2/19.4 == 6.2/6.3).

The crafted-example coverage lives in ``test_scribe_specialty_templates.py``; this
module strengthens Property 14 with randomized Hypothesis strategies over diverse
transcripts (empty, code-switched VN/EN, short, and long).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.config import settings as ml_settings
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.scribe.templates import (
    MACROS,
    SPECIALTY_TEMPLATES,
    TEMPLATES,
    expand_macros,
    get_template,
    insert_macro,
)

_BASE_IDS = sorted(TEMPLATES)
_SPECIALTY_IDS = sorted(SPECIALTY_TEMPLATES)
_MACRO_TRIGGERS = [m.trigger for m in MACROS.values()]


@contextmanager
def _specialty_flag(value: bool) -> Iterator[None]:
    """Temporarily force the Req 19 gate, restoring the prior value afterwards.

    Toggling the global flag (rather than the ``include_specialty`` override)
    exercises the real, unchanged generation call site, which resolves templates
    through ``get_template`` keyed off this setting.
    """

    original = ml_settings.rag_scribe_specialty_templates_enabled
    ml_settings.rag_scribe_specialty_templates_enabled = value
    try:
        yield
    finally:
        ml_settings.rag_scribe_specialty_templates_enabled = original


# Diverse transcripts: empty, free-form unicode text, code-switched VN/EN clinical
# fragments (some embedding macro trigger tokens), and long inputs.
_vn_en_fragment = st.sampled_from(
    [
        "bệnh nhân nam 60 tuổi",
        "đau ngực 2 giờ",
        "ho sốt 2 ngày",
        "patient reports cough",
        "fever for three days",
        "BP 140/90 mmHg",
        "SpO2 98% on room air",
        "metformin 500mg",
        "không dị ứng thuốc",
        "no known drug allergies",
        "khám tim phổi bình thường",
        *_MACRO_TRIGGERS,
    ]
)
_code_switched = st.lists(_vn_en_fragment, min_size=1, max_size=30).map(", ".join)
_long_text = st.text(min_size=200, max_size=1200)
_transcripts = st.one_of(
    st.just(""),
    st.sampled_from(["", "   ", "\n\t", "ab"]),
    st.text(max_size=400),
    _code_switched,
    _long_text,
)

_base_template_id = st.sampled_from(_BASE_IDS)
_specialty_template_id = st.sampled_from(_SPECIALTY_IDS)


def _note_tuple(note) -> tuple:
    """Byte-for-byte comparable projection of a generated note."""

    return (
        note.template_id,
        note.insufficient_input,
        tuple(note.sections.items()),  # ordered keys + exact values
    )


# Feature: clara-scribe-enterprise, Property 14: Template/macro addition isolation
# Validates: Requirements 19.5
@settings(max_examples=200, deadline=None)
@given(transcript=_transcripts, tid=_base_template_id)
def test_property14_existing_template_output_unchanged_by_extension(
    transcript: str, tid: str
) -> None:
    """Adding specialty templates/macros never alters an existing template's output.

    For ANY base (Requirement 6) template and ANY transcript, generating the note
    with the specialty-templates/macros flag OFF is byte-for-byte identical to
    generating it with the flag ON (Req 19.5 isolation).
    """

    with _specialty_flag(False):
        off = NoteGenerator().generate(transcript, tid)
    with _specialty_flag(True):
        on = NoteGenerator().generate(transcript, tid)

    # Same template resolved and byte-for-byte identical structure + content.
    assert on.template_id == off.template_id == tid
    assert list(on.sections.keys()) == list(off.sections.keys())
    assert _note_tuple(on) == _note_tuple(off)


# Feature: clara-scribe-enterprise, Property 14 (Property 1 reuse): specialty completeness
# Validates: Requirements 19.5, 19.2, 19.4
@settings(max_examples=200, deadline=None)
@given(transcript=_transcripts, sid=_specialty_template_id)
def test_property1_reuse_specialty_template_completeness(transcript: str, sid: str) -> None:
    """Specialty templates reuse Property 1: exactly the declared section keys.

    For ANY specialty template and ANY transcript, ``generate(...)`` returns
    exactly that template's declared section keys, in order (completeness —
    Req 19.2/19.4 == 6.2/6.3).
    """

    with _specialty_flag(True):
        tpl = get_template(sid)
        assert tpl is not None
        note = NoteGenerator().generate(transcript, sid)

    assert note.template_id == sid
    assert list(note.sections.keys()) == list(tpl.section_keys)
    assert all(isinstance(v, str) for v in note.sections.values())


# Feature: clara-scribe-enterprise, Property 14: macro insertion/expansion isolation
# Validates: Requirements 19.5
@settings(max_examples=200, deadline=None)
@given(transcript=_transcripts, tid=_base_template_id)
def test_property14_macro_ops_never_mutate_existing_template_output(
    transcript: str, tid: str
) -> None:
    """Macro insertion/expansion never mutates an already-generated note's output.

    Macro operations are pure string transforms over a clinician's working text;
    they produce new strings and must never reach back and alter the sections of a
    note generated from an existing template (Req 19.5 isolation).
    """

    with _specialty_flag(True):
        note = NoteGenerator().generate(transcript, tid)
        before = _note_tuple(note)

        # Exercise macro expansion + insertion over each section's text.
        for macro in MACROS.values():
            for value in list(note.sections.values()):
                expanded = expand_macros(value)
                assert isinstance(expanded, str)
                inserted = insert_macro(value, macro)
                assert macro.body in inserted

        # The generated note is untouched by those pure transforms.
        assert _note_tuple(note) == before


@pytest.mark.parametrize("tid", _BASE_IDS)
def test_base_template_isolation_crafted_examples(tid: str) -> None:
    """Anchor example: a representative VN/EN transcript is flag-invariant per base id."""

    transcript = "BN nam 60 tuổi, đau ngực 2 giờ; patient reports cough, BP 140/90."
    with _specialty_flag(False):
        off = NoteGenerator().generate(transcript, tid)
    with _specialty_flag(True):
        on = NoteGenerator().generate(transcript, tid)
    assert _note_tuple(on) == _note_tuple(off)
