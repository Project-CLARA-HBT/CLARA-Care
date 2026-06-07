"""Unit tests for the Clara Scribe templates registry (Wave 0 / Requirement 6)."""

from __future__ import annotations

from clara_ml.scribe.templates import (
    DEFAULT_TEMPLATE_ID,
    TEMPLATES,
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
