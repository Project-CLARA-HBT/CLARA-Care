"""Unit tests for the Scribe CodingAssistant (task 1.7, Requirement 7)."""

from __future__ import annotations

import clara_ml.rag.store  # noqa: F401 - import-order guard for the known cycle
from clara_ml.scribe.coding import CodingAssistant, MedSuggestion
from clara_ml.scribe.generator import NoteGenerator


def test_empty_text_yields_empty_result() -> None:
    res = CodingAssistant().suggest("")
    assert res.icd == [] and res.medications == [] and res.interactions == []


def test_icd_keyword_suggestion_with_span_is_advisory() -> None:
    res = CodingAssistant().suggest("Bệnh nhân tăng huyết áp nhiều năm.")
    codes = {c.code for c in res.icd}
    assert "I10" in codes
    hit = next(c for c in res.icd if c.code == "I10")
    assert hit.confirmed is False and hit.span and res.advisory is True


def test_medications_normalized_via_lexicon_offline() -> None:
    # Lexicon-only linker (no network) maps known drugs to rxcui.
    res = CodingAssistant().suggest("Đang dùng warfarin và aspirin.")
    rxcuis = {m.rxcui for m in res.medications}
    assert "11289" in rxcuis  # warfarin
    assert "1191" in rxcuis  # aspirin


def test_known_interaction_surfaced_advisory() -> None:
    # Reuses the CareGuard/DDI path, which surfaces localized (Vietnamese)
    # advisory text for the warfarin + aspirin bleeding interaction.
    res = CodingAssistant().suggest("warfarin and aspirin together", lang="en")
    assert res.interactions  # at least one advisory surfaced
    assert any("máu" in s.lower() for s in res.interactions)


def test_no_interaction_for_single_or_unknown_meds() -> None:
    # Fewer than two normalized meds -> no DDI advisory (nothing fabricated).
    res = CodingAssistant().suggest("Đang dùng warfarin.", lang="vi")
    assert res.interactions == []


def test_interaction_seam_is_injectable() -> None:
    called = {}

    def fake_ddi(meds):  # noqa: ANN001
        called["n"] = len(list(meds))
        return ["custom-advisory"]

    res = CodingAssistant(
        linker=_FakeLinker([("11289", "warfarin"), ("1191", "aspirin")]),
        interaction_fn=fake_ddi,
    ).suggest("warfarin aspirin", lang="en")
    assert res.interactions == ["custom-advisory"]
    assert called["n"] == 2


class _FakeEntity:
    def __init__(self, rxcui: str, name: str):
        self.rxcui = rxcui
        self.canonical_name = name
        self.cui = ""
        self.synonyms = [{"name": name, "lang": "en", "kind": "mention"}]


class _FakeLinker:
    def __init__(self, pairs):  # noqa: ANN001
        self._pairs = pairs

    def link(self, text, *, lang="en"):  # noqa: ANN001
        return [_FakeEntity(r, n) for r, n in self._pairs]


def test_unknown_drug_degrades_to_no_med() -> None:
    res = CodingAssistant().suggest("took some unknownzaxdrug today", lang="en")
    # Unknown surface not in lexicon -> no fabricated med/rxcui (graceful).
    assert all(isinstance(m, MedSuggestion) for m in res.medications)
    assert all(m.rxcui == "" for m in res.medications)


class _NamedNoRxcuiEntity:
    """A linked concept that resolved a name but no RxCUI (e.g. UMLS-only)."""

    def __init__(self, name: str):
        self.rxcui = ""
        self.canonical_name = name
        self.cui = "C123"
        self.synonyms = [{"name": name, "lang": "en", "kind": "mention"}]


def test_known_name_without_rxcui_degrades_to_surface_text() -> None:
    # Graceful degradation (Req 7.2): when RxCUI is unknown, the medication is
    # still surfaced as text with an empty rxcui rather than dropped/fabricated.
    res = CodingAssistant(linker=_FakeLinkerEntities([_NamedNoRxcuiEntity("mystery drug")])).suggest(
        "patient takes mystery drug", lang="en"
    )
    assert len(res.medications) == 1
    med = res.medications[0]
    assert med.rxcui == ""
    assert med.normalized_name == "mystery drug"
    assert med.surface == "mystery drug"


class _FakeLinkerEntities:
    def __init__(self, entities):  # noqa: ANN001
        self._entities = entities

    def link(self, text, *, lang="en"):  # noqa: ANN001
        return list(self._entities)


def test_suggestions_are_additive_and_never_mutate_note_text() -> None:
    # Coding is additive metadata: generating coding suggestions for a note's
    # text returns a separate result and leaves the note text byte-for-byte
    # unchanged (Requirement 7.4).
    note = NoteGenerator().generate("Bệnh nhân tăng huyết áp, đang dùng warfarin và aspirin.", "soap")
    before = dict(note.sections)
    combined = " ".join(note.sections.values())

    result = CodingAssistant().suggest(combined)

    assert note.sections == before  # note text untouched
    assert isinstance(result.as_dict(), dict)  # suggestions are separate metadata
    assert result.advisory is True
