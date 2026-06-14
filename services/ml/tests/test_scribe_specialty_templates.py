"""Unit tests for the Req 19 specialty-template + macro registry extension (task 8.1).

These cover the flag gate (19.1), specialty templates yielding exactly their
declared section keys via the unchanged generation call site (19.2/19.4), macro
insertion (19.3), Vietnamese-first/bilingual content (19.6), and — critically —
that adding specialty templates/macros never alters the structure or output of
any existing Requirement 6 template (19.5).
"""

from __future__ import annotations

import pytest

from clara_ml.config import settings
from clara_ml.scribe.generator import NoteGenerator
from clara_ml.scribe.templates import (
    MACROS,
    SPECIALTY_TEMPLATES,
    TEMPLATES,
    expand_macros,
    get_macro,
    get_template,
    insert_macro,
    list_macros,
    list_templates,
)

_BASE_IDS = {"soap", "h_and_p", "progress_note", "referral_letter", "vn_benh_an"}
_SPECIALTY_IDS = {"vn_tim_mach", "vn_nhi_khoa", "vn_tam_than", "vn_san_phu_khoa"}


@pytest.fixture
def specialty_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rag_scribe_specialty_templates_enabled", True, raising=False)


@pytest.fixture
def specialty_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rag_scribe_specialty_templates_enabled", False, raising=False)


# ---------------------------------------------------------------------------
# Req 19.1 — flag off => exactly the Requirement 6 template set.
# ---------------------------------------------------------------------------


def test_flag_off_offers_exactly_requirement6_set(specialty_off: None) -> None:
    ids = {t.id for t in list_templates()}
    assert ids == _BASE_IDS
    # Specialty ids are NOT resolvable while the gate is off.
    for sid in _SPECIALTY_IDS:
        assert get_template(sid) is None


def test_flag_off_macros_unavailable(specialty_off: None) -> None:
    assert list_macros() == []
    assert get_macro("tim_binh_thuong") is None


# ---------------------------------------------------------------------------
# Req 19.2 — flag on => specialty templates selectable through the same registry.
# ---------------------------------------------------------------------------


def test_flag_on_appends_specialty_templates_after_base(specialty_on: None) -> None:
    templates = list_templates()
    ids = [t.id for t in templates]
    # Base set comes first, in its original order, then the specialty set.
    assert ids[: len(_BASE_IDS)] == [t.id for t in list_templates(include_specialty=False)]
    assert set(ids) == _BASE_IDS | _SPECIALTY_IDS


@pytest.mark.parametrize("sid", sorted(_SPECIALTY_IDS))
def test_flag_on_specialty_templates_resolve(specialty_on: None, sid: str) -> None:
    tpl = get_template(sid)
    assert tpl is not None
    assert tpl.id == sid
    assert tpl.section_keys


# ---------------------------------------------------------------------------
# Req 19.4 — selected specialty template yields exactly its declared sections.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", sorted(_SPECIALTY_IDS))
def test_specialty_template_yields_exact_declared_sections(specialty_on: None, sid: str) -> None:
    tpl = get_template(sid)
    assert tpl is not None
    note = NoteGenerator().generate("BN nam 60 tuổi, đau ngực 2 giờ.", sid)
    # Generation call site is unchanged: it resolves the specialty template and
    # the note has EXACTLY the declared keys, in order (Req 19.4 == 6.2/6.3).
    assert list(note.sections.keys()) == list(tpl.section_keys)


def test_specialty_template_structure_is_transcript_independent(specialty_on: None) -> None:
    tpl = get_template("vn_tim_mach")
    assert tpl is not None
    keys_a = list(NoteGenerator().generate("đau ngực dữ dội", "vn_tim_mach").sections.keys())
    keys_b = list(NoteGenerator().generate("", "vn_tim_mach").sections.keys())
    assert keys_a == keys_b == list(tpl.section_keys)


def test_section_keys_unique_and_nonempty() -> None:
    for tpl in SPECIALTY_TEMPLATES.values():
        assert tpl.section_keys
        assert len(set(tpl.section_keys)) == len(tpl.section_keys)
        assert all(isinstance(k, str) and k.strip() for k in tpl.section_keys)


# ---------------------------------------------------------------------------
# Req 19.6 — specialty templates + macros are Vietnamese-first, bilingual.
# ---------------------------------------------------------------------------


def test_specialty_templates_are_vietnamese_first_and_bilingual() -> None:
    for tpl in SPECIALTY_TEMPLATES.values():
        assert tpl.language == "vi"
        # Bilingual where applicable: each section reads "<Tiếng Việt> (<English>)".
        assert all("(" in key and key.rstrip().endswith(")") for key in tpl.section_keys)


def test_macros_are_vietnamese_first() -> None:
    for macro in MACROS.values():
        assert macro.language == "vi"
        assert macro.body.strip()
        assert macro.trigger.startswith("/")


# ---------------------------------------------------------------------------
# Req 19.3 — clinician macros can be inserted into a note.
# ---------------------------------------------------------------------------


def test_get_and_list_macros_when_enabled(specialty_on: None) -> None:
    macros = list_macros()
    assert macros
    macro = get_macro("tim_binh_thuong")
    assert macro is not None
    assert macro in macros


def test_insert_macro_appends_by_default(specialty_on: None) -> None:
    macro = get_macro("phoi_binh_thuong")
    assert macro is not None
    assert insert_macro("", macro) == macro.body
    out = insert_macro("Khám:", macro)
    assert out == f"Khám: {macro.body}"
    assert out.endswith(macro.body)


def test_insert_macro_at_index(specialty_on: None) -> None:
    macro = get_macro("hen_tai_kham")
    assert macro is not None
    out = insert_macro("AB", macro, index=1)
    assert out == "A" + macro.body + "B"


def test_expand_macros_replaces_trigger_tokens(specialty_on: None) -> None:
    macro = get_macro("tim_binh_thuong")
    assert macro is not None
    expanded = expand_macros(f"Khám tim: {macro.trigger}")
    assert macro.trigger not in expanded
    assert macro.body in expanded


def test_expand_macros_is_noop_when_flag_off(specialty_off: None) -> None:
    text = "Khám tim: /timbinhthuong"
    assert expand_macros(text) == text


# ---------------------------------------------------------------------------
# Req 19.5 — adding templates/macros does NOT alter existing templates.
# ---------------------------------------------------------------------------


def test_base_registry_is_unchanged_by_extension() -> None:
    assert set(TEMPLATES) == _BASE_IDS
    # The base dict carries only Requirement 6 templates — no specialty leakage.
    assert not (_SPECIALTY_IDS & set(TEMPLATES))


@pytest.mark.parametrize("tid", sorted(_BASE_IDS))
def test_existing_template_output_identical_regardless_of_flag(
    monkeypatch: pytest.MonkeyPatch, tid: str
) -> None:
    transcript = "BN ho, sốt 2 ngày, đau họng."

    monkeypatch.setattr(settings, "rag_scribe_specialty_templates_enabled", False, raising=False)
    off = NoteGenerator().generate(transcript, tid)

    monkeypatch.setattr(settings, "rag_scribe_specialty_templates_enabled", True, raising=False)
    on = NoteGenerator().generate(transcript, tid)

    # Byte-for-byte identical structure AND output: adding specialty templates /
    # macros never alters an existing template (Req 19.5 isolation).
    assert on.template_id == off.template_id == tid
    assert on.sections == off.sections


def test_existing_template_section_keys_byte_for_byte_stable(specialty_on: None) -> None:
    # The canonical Requirement 6 section keys, frozen here as a regression guard.
    expected = {
        "soap": ["Subjective", "Objective", "Assessment", "Plan"],
        "progress_note": ["Interval History", "Examination", "Assessment", "Plan"],
        "referral_letter": [
            "Reason for Referral",
            "Clinical Summary",
            "Current Medications",
            "Request",
        ],
        "vn_benh_an": [
            "Lý do khám",
            "Bệnh sử",
            "Tiền sử",
            "Khám lâm sàng",
            "Chẩn đoán",
            "Hướng xử trí",
        ],
    }
    for tid, keys in expected.items():
        tpl = get_template(tid)
        assert tpl is not None
        assert tpl.section_keys == keys
