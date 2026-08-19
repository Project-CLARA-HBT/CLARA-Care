"""Tests for the W8 secondary-endpoint renderer (GMT-05, no W8 re-run)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance import w8_secondary_renderer

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research" / "assurance_soict"

METHODS = (
    "M0_regression",
    "M1_stateless_property",
    "M2_state_machine",
    "M3_combined",
)


def _render(tmp_path: Path) -> dict[str, object]:
    return w8_secondary_renderer.render_secondary_report(
        research_dir=RESEARCH, output_dir=tmp_path / "out"
    )


def test_renderer_is_deterministic(tmp_path: Path) -> None:
    first = _render(tmp_path / "a")
    second = _render(tmp_path / "b")
    assert first == second
    for name in (
        "w8_secondary_report.json",
        "w8_kill_matrix.md",
        "w8_seed_stability.md",
        "w8_family_layer_invariant.md",
        "w8_all_survive.md",
        "w8_runtime_efficiency.md",
        "w8_field_availability.md",
    ):
        assert (tmp_path / "a" / "out" / name).read_bytes() == (
            tmp_path / "b" / "out" / name
        ).read_bytes()


def test_renderer_matches_sealed_freeze_and_counts() -> None:
    report = _render(ROOT / "research" / "assurance_soict" / "w8_secondary_report")
    assert report["freeze_id"] == "govmut-soict-2026-final-v2"
    assert report["schema_version"] == "govmut-w8-secondary-report.v1"
    assert report["status"] == "rendered_from_sealed_analysis"
    assert len(report["kill_matrix"]) == 45
    assert len(report["seed_stability"]) == 45 * 4
    assert len(report["family_layer_invariant"]) == 45
    assert report["all_survive_count"] == 25
    assert len(report["all_survive"]) == 25
    assert report["outcome_counts"] == {"INFRASTRUCTURE_ERROR": 0, "KILLED": 161, "SURVIVED": 559}


def test_renderer_available_fields_match_sealed_analysis() -> None:
    sealed = json.loads(
        (RESEARCH / "seal" / "govmut-soict-2026-final_analysis-v2").read_text(encoding="utf-8")
    )
    report = _render(ROOT / "research" / "assurance_soict" / "w8_secondary_report")
    per_mutant = report["kill_matrix"]
    for row in per_mutant:
        assert row["mutant_id"] in sealed["per_mutant_method"]
    for method in METHODS:
        sealed_stats = sealed["runtime_stats"]["per_method"][method]
        rendered = next(
            row for row in report["efficiency"] if row["method"] == method
        )
        assert rendered["total_ms"] == round(sealed_stats["total_ms"], 3)
        assert rendered["killed"] == sealed["mutation_scores"][method]["killed"]


def test_renderer_all_survive_matches_sealed_per_mutant() -> None:
    sealed = json.loads(
        (RESEARCH / "seal" / "govmut-soict-2026-final_analysis-v2").read_text(encoding="utf-8")
    )
    report = _render(ROOT / "research" / "assurance_soict" / "w8_secondary_report")
    expected = sorted(
        mutant_id
        for mutant_id, by_method in sealed["per_mutant_method"].items()
        if all(by_method[method]["detected_any_seed"] == 0 for method in METHODS)
    )
    assert report["all_survive"] == expected


def test_renderer_never_invents_unrecorded_fields() -> None:
    report = _render(ROOT / "research" / "assurance_soict" / "w8_secondary_report")
    for row in report["seed_stability"]:
        if row["method"] == "M0_regression":
            assert row["first_killing_seed"] == "N/A"
        if row["kill_fraction"] == 0.0:
            assert row["time_to_first_kill_ms"] == "N/A"


def test_renderer_reports_available_and_na_fields(tmp_path: Path) -> None:
    report = _render(tmp_path / "report")
    availability = report["field_availability"]
    assert "runtime_stats.per_method" in availability["available"]
    assert any(
        item.startswith("seed_stability[") and item.endswith("first_killing_seed")
        for item in availability["rendered_as_na"]
    )
    assert "no values are imputed" in (
        tmp_path / "report" / "out" / "w8_field_availability.md"
    ).read_text(encoding="utf-8")


def test_renderer_refuses_seal_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = tmp_path / "seal" / "govmut-soict-2026-final_analysis-v2"
    broken.parent.mkdir(parents=True)
    broken.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        w8_secondary_renderer,
        "_read_sealed_analysis",
        lambda research_dir: (_ for _ in ()).throw(
            FreezeError("govmut_w8_secondary_seal_mismatch")
        ),
    )
    with pytest.raises(FreezeError, match="govmut_w8_secondary_seal_mismatch"):
        w8_secondary_renderer.render_secondary_report(
            research_dir=tmp_path, output_dir=tmp_path / "out"
        )


def test_renderer_derived_efficiency_flags_non_budget_normalized(tmp_path: Path) -> None:
    w8_secondary_renderer.render_secondary_report(
        research_dir=RESEARCH, output_dir=tmp_path / "out"
    )
    markdown = (tmp_path / "out" / "w8_runtime_efficiency.md").read_text(encoding="utf-8")
    assert "NOT budget-normalized" in markdown
    report = _render(tmp_path / "report")
    assert report["unique_incremental_kills"]["incremental_kills"]["M3_combined"] == []
