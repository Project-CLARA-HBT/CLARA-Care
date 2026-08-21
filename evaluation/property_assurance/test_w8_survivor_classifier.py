"""Tests for the W8 survivor classifier (GMT-06 category assignment)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.property_assurance import w8_survivor_classifier

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "research" / "assurance_soict" / "results" / "final-analysis.json"


def test_classifier_covers_exactly_the_sealed_all_survive_set() -> None:
    result = w8_survivor_classifier.validate_classification(analysis_path=ANALYSIS)
    assert result["classified_count"] == 25
    assert result["all_survive_count"] == 25
    assert sum(result["category_counts"].values()) == 25


def test_each_mutant_has_exactly_one_prespecified_category() -> None:
    result = w8_survivor_classifier.validate_classification(analysis_path=ANALYSIS)
    expected_categories = {
        "generator_reach",
        "missing_oracle",
        "missing_path_test_target",
        "budget_exhaustion",
        "replay_reconstruction_blind_spot",
        "api_layer_absence",
        "possible_weak_mutant",
        "other_with_rationale",
    }
    assert set(result["categories"]) == expected_categories
    for category in result["category_counts"]:
        assert category in expected_categories


def test_distribution_matches_documented_counts() -> None:
    result = w8_survivor_classifier.validate_classification(analysis_path=ANALYSIS)
    counts = result["category_counts"]
    assert counts["missing_oracle"] == 17
    assert counts["possible_weak_mutant"] == 2
    assert counts["missing_path_test_target"] == 3
    assert counts["replay_reconstruction_blind_spot"] == 3
    assert counts["generator_reach"] == 0
    assert counts["budget_exhaustion"] == 0
    assert counts["api_layer_absence"] == 0
    assert counts["other_with_rationale"] == 0


def test_known_mutants_map_to_documented_categories() -> None:
    assert w8_survivor_classifier.classify("M01-C")[0] == "missing_oracle"
    assert w8_survivor_classifier.classify("M02-C")[0] == "possible_weak_mutant"
    assert w8_survivor_classifier.classify("M05-C")[0] == "missing_path_test_target"
    assert w8_survivor_classifier.classify("M08-B")[0] == "replay_reconstruction_blind_spot"


def test_unknown_mutant_raises() -> None:
    with pytest.raises(KeyError):
        w8_survivor_classifier.classify("M01-A")


def test_rationales_are_present_and_are_not_equivalence_claims() -> None:
    result = w8_survivor_classifier.validate_classification(analysis_path=ANALYSIS)
    for mutant_id in w8_survivor_classifier.CLASSIFICATION:
        category, rationale = w8_survivor_classifier.CLASSIFICATION[mutant_id]
        assert category in result["categories"]
        assert len(rationale) > 40
        assert "equivalent" not in category
