"""Unit tests for wave-7 note-quality + efficiency metric derivation (Requirement 15).

Covers the pure helpers added to ``clara_api.core.scribe_analytics``:
- ``compute_scribe_metrics`` derives edit-rate / time-saved / degraded-rate (reused
  from wave-1) plus grounded-claim rate and a PDQI-9-style structural proxy, from
  non-PII session metadata only (Req 15.2),
- each metric is OMITTED when its input is unavailable (omit-on-missing, Req 15.6) —
  never fabricated/zero-filled,
- grounded-claim rate is read from the finalized note's ``grounding_json`` and
  omitted when grounding is off / had no significant claims (Req 15.6),
- the structural proxy is a bounded structural-completeness signal only (Req 15.5),
- all emitted values are bounded numbers (PII-free by construction, Req 15.3).
"""

from __future__ import annotations

from clara_api.core.scribe_analytics import (
    compute_scribe_metrics,
    compute_structural_completeness,
    extract_grounded_claim_rate,
)

# --- grounded-claim rate -----------------------------------------------------


def test_grounded_claim_rate_read_from_grounding_json() -> None:
    grounding = {"enabled": True, "grounded_claim_rate": 0.75, "total_significant": 4}
    assert extract_grounded_claim_rate(grounding) == 0.75


def test_grounded_claim_rate_clamped_to_unit_interval() -> None:
    assert extract_grounded_claim_rate(
        {"enabled": True, "grounded_claim_rate": 1.5, "total_significant": 2}
    ) == 1.0
    assert extract_grounded_claim_rate(
        {"enabled": True, "grounded_claim_rate": -0.2, "total_significant": 2}
    ) == 0.0


def test_grounded_claim_rate_omitted_when_grounding_disabled() -> None:
    # Omit-on-missing (Req 15.6): grounding off -> no metric, not a fabricated 0.
    assert extract_grounded_claim_rate(
        {"enabled": False, "grounded_claim_rate": 0.0, "total_significant": 0}
    ) is None
    assert extract_grounded_claim_rate(None) is None
    assert extract_grounded_claim_rate({}) is None


def test_grounded_claim_rate_omitted_when_no_significant_claims() -> None:
    # rate is a meaningless 0.0 when there were no significant claims -> omit.
    assert extract_grounded_claim_rate(
        {"enabled": True, "grounded_claim_rate": 0.0, "total_significant": 0}
    ) is None


# --- PDQI-9 structural proxy -------------------------------------------------


def test_structural_proxy_full_when_all_sections_populated() -> None:
    sections = {"subjective": "cough", "objective": "afebrile", "assessment": "URI", "plan": "rest"}
    assert compute_structural_completeness(sections) == 1.0


def test_structural_proxy_fraction_of_nonempty_sections() -> None:
    # 2 of 4 sections populated -> 0.5.
    sections = {"subjective": "cough", "objective": "", "assessment": "URI", "plan": "   "}
    assert compute_structural_completeness(sections) == 0.5


def test_structural_proxy_zero_when_all_sections_empty() -> None:
    sections = {"subjective": "", "objective": None, "assessment": "  ", "plan": {}}
    assert compute_structural_completeness(sections) == 0.0


def test_structural_proxy_omitted_when_no_sections() -> None:
    # Omit-on-missing (Req 15.6): nothing to measure -> None, never a fabricated 0.
    assert compute_structural_completeness(None) is None
    assert compute_structural_completeness({}) is None
    assert compute_structural_completeness([]) is None


def test_structural_proxy_supports_list_sections() -> None:
    assert compute_structural_completeness(["a", "", "c"]) == round(2 / 3, 4)


# --- compute_scribe_metrics: full derivation --------------------------------


def test_compute_scribe_metrics_all_metrics_present_and_bounded() -> None:
    session_meta = {
        "note_versions": [
            {
                "sections": {"subjective": "patient reports a cough", "plan": "rest"},
            },
            {
                "sections": {"subjective": "patient reports a dry cough", "plan": "rest, fluids"},
                "grounding": {
                    "enabled": True,
                    "grounded_claim_rate": 0.8,
                    "total_significant": 5,
                },
            },
        ],
        "asr_meta": {
            "segments": [
                {"degraded": True},
                {"degraded": False},
                {"degraded": False},
                {"degraded": False},
            ]
        },
    }
    metrics = compute_scribe_metrics(session_meta)
    assert set(metrics) == {
        "edit_rate",
        "time_saved_minutes",
        "degraded_rate",
        "grounded_claim_rate",
        "pdqi9_structural_proxy",
    }
    assert 0.0 < metrics["edit_rate"] <= 1.0
    assert metrics["time_saved_minutes"] >= 0.0
    assert metrics["degraded_rate"] == 0.25
    assert metrics["grounded_claim_rate"] == 0.8
    assert metrics["pdqi9_structural_proxy"] == 1.0
    # Every emitted value is a bounded number (PII-free by construction, Req 15.3).
    assert all(isinstance(v, (int, float)) for v in metrics.values())


def test_compute_scribe_metrics_omits_grounded_rate_when_grounding_absent() -> None:
    # Finalized note has no grounding metadata -> grounded_claim_rate omitted, but
    # the structural proxy and edit/time metrics are still derived.
    session_meta = {
        "note_versions": [
            {"sections": {"subjective": "generated"}},
            {"sections": {"subjective": "generated edited", "plan": "rest"}},
        ],
        "asr_meta": None,
    }
    metrics = compute_scribe_metrics(session_meta)
    assert "grounded_claim_rate" not in metrics
    assert "degraded_rate" not in metrics
    assert "edit_rate" in metrics
    assert "time_saved_minutes" in metrics
    assert "pdqi9_structural_proxy" in metrics


def test_compute_scribe_metrics_omits_structural_proxy_without_note_versions() -> None:
    # No note versions -> no sections -> structural proxy + edit/time omitted; only
    # ASR-derived degraded_rate survives (omit-on-missing, Req 15.6).
    session_meta = {
        "note_versions": [],
        "asr_meta": {"segments": [{"degraded": True}, {"degraded": False}]},
    }
    metrics = compute_scribe_metrics(session_meta)
    assert metrics == {"degraded_rate": 0.5}


def test_compute_scribe_metrics_empty_for_no_signal() -> None:
    assert compute_scribe_metrics({"note_versions": [], "asr_meta": None}) == {}
    assert compute_scribe_metrics({}) == {}
    assert compute_scribe_metrics(None) == {}  # type: ignore[arg-type]


def test_compute_scribe_metrics_grounded_rate_from_finalized_version_only() -> None:
    # Grounding only on the first (generated) version, not the finalized one ->
    # omitted, because the finalized note carries no grounding metadata.
    session_meta = {
        "note_versions": [
            {
                "sections": {"subjective": "a"},
                "grounding": {"enabled": True, "grounded_claim_rate": 0.9, "total_significant": 3},
            },
            {"sections": {"subjective": "a edited"}},
        ],
        "asr_meta": None,
    }
    metrics = compute_scribe_metrics(session_meta)
    assert "grounded_claim_rate" not in metrics
