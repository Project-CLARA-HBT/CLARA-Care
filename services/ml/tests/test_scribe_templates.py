"""Unit tests for the Clara Scribe templates registry (Wave 0 / Requirement 6)."""

from __future__ import annotations

import dataclasses

import pytest

from clara_ml.scribe.templates import (
    DEFAULT_TEMPLATE_ID,
    TEMPLATES,
    Template,
    get_template,
    list_templates,
)


def test_default_template_resolves_to_soap() -> None:
    assert DEFAULT_TEMPLATE_ID == "soap"
    soap = get_template(DEFAULT_TEMPLATE_ID)
    assert soap is not None
    assert soap.section_keys == ["Subjective", "Objective", "Assessment", "Plan"]


def test_every_template_has_nonempty_ordered_unique_sections() -> None:
    templates = list_templates()
    assert len(templates) >= 5
    for tpl in templates:
        assert tpl.id and tpl.display_name
        assert tpl.section_keys, f"{tpl.id} has no sections"
        assert all(isinstance(k, str) and k.strip() for k in tpl.section_keys)
        # Section keys are unique within a template (deterministic structure).
        assert len(set(tpl.section_keys)) == len(tpl.section_keys)


def test_get_template_unknown_returns_none() -> None:
    assert get_template("does-not-exist") is None
    assert get_template("") is None
    assert get_template(None) is None


def test_registry_keys_match_template_ids() -> None:
    for key, tpl in TEMPLATES.items():
        assert key == tpl.id


def test_vietnamese_template_present() -> None:
    vn = get_template("vn_benh_an")
    assert vn is not None and vn.language == "vi"
    assert "Chẩn đoán" in vn.section_keys


def test_all_five_expected_templates_present() -> None:
    expected = {"soap", "h_and_p", "progress_note", "referral_letter", "vn_benh_an"}
    assert expected.issubset(set(TEMPLATES))
    for tid in expected:
        assert get_template(tid) is not None


def test_list_templates_is_order_preserving_and_returns_a_copy() -> None:
    first = list_templates()
    second = list_templates()
    # Order is stable across calls.
    assert [t.id for t in first] == [t.id for t in second]
    # soap is registered first (it is the default).
    assert first[0].id == DEFAULT_TEMPLATE_ID
    # Returned list is a copy: mutating it does not corrupt the registry.
    first.append(Template(id="bogus", display_name="x", section_keys=["A"]))
    assert [t.id for t in list_templates()] != [t.id for t in first]
    assert get_template("bogus") is None


def test_template_instances_are_frozen_immutable() -> None:
    tpl = get_template("soap")
    assert tpl is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        tpl.id = "mutated"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        tpl.section_keys = []  # type: ignore[misc]


def test_non_default_templates_use_english_except_vietnamese() -> None:
    for tpl in list_templates():
        expected_lang = "vi" if tpl.id == "vn_benh_an" else "en"
        assert tpl.language == expected_lang
