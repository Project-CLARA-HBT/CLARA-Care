from __future__ import annotations

import pytest

from clara_ml.agents import research_tier2 as tier2
from clara_ml.agents.research_tier2 import PicoFrame, PicoIncompleteError


@pytest.fixture
def _enable_pico(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tier2.settings, "research_pico_enabled", True)


# --- Clinical-query detection (R7.1) -------------------------------------------------------


def test_is_clinical_query_true_for_treatment_question():
    assert tier2._is_clinical_query(
        "Hiệu quả điều trị warfarin so với aspirin ở bệnh nhân cao tuổi nguy cơ xuất huyết"
    )


def test_is_clinical_query_true_for_recognized_medication():
    assert tier2._is_clinical_query("warfarin ibuprofen")


def test_is_clinical_query_false_for_non_clinical_text():
    assert not tier2._is_clinical_query("Thời tiết Hà Nội hôm nay thế nào")


def test_is_clinical_query_false_for_empty_query():
    assert not tier2._is_clinical_query("   ")


# --- PICO extraction: completeness or named rejection (R7.2, R7.3) -------------------------


def test_extract_pico_frame_complete_clinical_query():
    frame = tier2._extract_pico_frame(
        "Ở bệnh nhân cao tuổi, điều trị warfarin so với ibuprofen "
        "làm giảm nguy cơ xuất huyết và tỷ lệ tử vong không?"
    )
    assert isinstance(frame, PicoFrame)
    # All four elements determined and non-empty (never fabricated, never blank).
    payload = frame.as_payload()
    assert set(payload) == {"population", "intervention", "comparison", "outcome"}
    assert all(value.strip() for value in payload.values())


def test_extract_pico_frame_element_values_are_derived_from_query():
    query = "Ở phụ nữ mang thai, điều trị paracetamol so với placebo giảm nguy cơ sốt"
    frame = tier2._extract_pico_frame(query)
    # Each element value is composed of tokens detected in the query (no fabrication).
    folded_query = tier2._ascii_fold(query)
    for element in frame.as_payload().values():
        for part in element.split(", "):
            assert part in folded_query


def test_extract_pico_frame_raises_named_rejection_when_comparison_missing():
    # Single-arm clinical question with no comparator.
    with pytest.raises(PicoIncompleteError) as exc:
        tier2._extract_pico_frame(
            "Điều trị warfarin ở bệnh nhân cao tuổi có làm giảm nguy cơ đột quỵ không?"
        )
    assert exc.value.element == "comparison"


def test_extract_pico_frame_raises_named_rejection_when_population_missing():
    with pytest.raises(PicoIncompleteError) as exc:
        tier2._extract_pico_frame("warfarin")
    assert exc.value.element in {"population", "intervention", "comparison", "outcome"}
    # The first undetermined element for a bare drug token is the population.
    assert exc.value.element == "population"


# --- Flag gating (R7.4) --------------------------------------------------------------------


def test_maybe_build_pico_frame_returns_none_when_flag_disabled(monkeypatch):
    monkeypatch.setattr(tier2.settings, "research_pico_enabled", False)
    assert (
        tier2._maybe_build_pico_frame(
            "điều trị warfarin so với ibuprofen ở bệnh nhân cao tuổi giảm nguy cơ xuất huyết"
        )
        is None
    )


def test_maybe_build_pico_frame_returns_none_for_non_clinical_query(_enable_pico):
    assert tier2._maybe_build_pico_frame("Thời tiết Hà Nội hôm nay") is None


def test_maybe_build_pico_frame_returns_frame_for_clinical_query(_enable_pico):
    frame = tier2._maybe_build_pico_frame(
        "Ở bệnh nhân cao tuổi, điều trị warfarin so với ibuprofen giảm nguy cơ xuất huyết và tử vong"
    )
    assert isinstance(frame, PicoFrame)


def test_maybe_build_pico_frame_propagates_incomplete_error(_enable_pico):
    with pytest.raises(PicoIncompleteError):
        tier2._maybe_build_pico_frame(
            "Điều trị warfarin ở bệnh nhân cao tuổi có giảm nguy cơ đột quỵ không?"
        )


# --- PicoIncompleteError shape -------------------------------------------------------------


def test_pico_incomplete_error_names_element():
    err = PicoIncompleteError("outcome")
    assert err.element == "outcome"
    assert "outcome" in str(err)
