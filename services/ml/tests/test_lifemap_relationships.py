import pytest

from clara_ml.lifemap.relationships import (
    PairedSignal,
    RelationshipDiscoveryError,
    discover_relationship,
)


def _pairs(reverse_confirmation: bool = False) -> tuple[PairedSignal, ...]:
    discovery = tuple(
        PairedSignal(float(index), float(index) + 0.1, "discovery")
        for index in range(10)
    )
    confirmation = tuple(
        PairedSignal(
            float(index),
            float(-index if reverse_confirmation else index) + 0.2,
            "confirmation",
        )
        for index in range(10, 20)
    )
    return discovery + confirmation


def test_relationship_requires_coverage_and_separate_confirmation() -> None:
    result = discover_relationship(
        signal_x="sleep_duration",
        signal_y="self_reported_energy",
        pairs=_pairs(),
        expected_pairs=20,
        lag=1,
        tested_hypotheses=4,
        minimum_coverage=0.8,
        minimum_absolute_effect=0.3,
        alpha=0.05,
        known_confounders=("work_schedule", "device_change"),
    )
    assert result.confirmed is True
    assert result.multiplicity_method.startswith("bonferroni")
    assert result.known_confounders == ("work_schedule", "device_change")
    assert "không chứng minh nguyên nhân" in result.explanation_vi
    assert "does not establish causation" in result.explanation_en


def test_direction_failure_does_not_confirm_discovery_candidate() -> None:
    result = discover_relationship(
        signal_x="a",
        signal_y="b",
        pairs=_pairs(reverse_confirmation=True),
        expected_pairs=20,
        lag=0,
        tested_hypotheses=1,
        minimum_coverage=0.8,
        minimum_absolute_effect=0.3,
        alpha=0.05,
        known_confounders=(),
    )
    assert result.confirmed is False


def test_missing_paired_coverage_fails_closed() -> None:
    with pytest.raises(RelationshipDiscoveryError, match="coverage"):
        discover_relationship(
            signal_x="a",
            signal_y="b",
            pairs=_pairs()[:4],
            expected_pairs=20,
            lag=0,
            tested_hypotheses=1,
            minimum_coverage=0.8,
            minimum_absolute_effect=0.3,
            alpha=0.05,
            known_confounders=(),
        )
