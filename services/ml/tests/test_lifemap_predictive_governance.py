import pytest

from clara_ml.lifemap.predictive_governance import (
    CandidatePredictions,
    PredictiveGovernanceError,
    PredictiveUseCase,
    evaluate_bakeoff,
    validate_predictive_use_case,
)


def _use_case(**overrides: object) -> PredictiveUseCase:
    values = {
        "use_case_id": "wellness-planning-v1",
        "target_key": "weekly_planning_load",
        "task_kind": "regression",
        "permitted_output": "organizational_forecast",
        "minimum_samples": 30,
        "minimum_events_per_person": 4,
        "horizon_days": 7,
        "evaluation_split": "person_household_site_source_device_time",
        "risk_class": "low",
        "approval_id": "approval-17-1",
    }
    values.update(overrides)
    return PredictiveUseCase(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "target",
    (
        "disease_onset",
        "hospital_deterioration",
        "medication_effect",
        "emergency_triage",
    ),
)
def test_registry_hard_rejects_health_decision_targets(target: str) -> None:
    with pytest.raises(PredictiveGovernanceError, match="research_only"):
        validate_predictive_use_case(_use_case(target_key=target))


def test_dataset_creation_requires_recorded_target_approval() -> None:
    with pytest.raises(PredictiveGovernanceError, match="approval_required"):
        validate_predictive_use_case(_use_case(approval_id=None))


def test_deterministic_champion_stays_when_complexity_is_not_materially_better() -> None:
    truth = tuple(float(index % 5) for index in range(30))
    report = evaluate_bakeoff(
        use_case=_use_case(),
        y_true=truth,
        slice_keys=tuple("a" if index < 15 else "b" for index in range(30)),
        candidates=(
            CandidatePredictions(
                "robust-v1",
                "deterministic_robust",
                tuple(value + 0.1 for value in truth),
                latency_ms=1,
                cost_units=0,
            ),
            CandidatePredictions(
                "tree-v1",
                "tree",
                tuple(value + 0.098 for value in truth),
                latency_ms=20,
                cost_units=0.1,
            ),
        ),
    )
    assert report.champion_id == "robust-v1"
    assert report.selected_challenger_id is None
    assert report.decision == "retain_deterministic_champion"


def test_challenger_only_becomes_eligible_after_all_material_gates() -> None:
    truth = tuple(float(index % 5) for index in range(30))
    report = evaluate_bakeoff(
        use_case=_use_case(),
        y_true=truth,
        slice_keys=tuple("a" if index < 15 else "b" for index in range(30)),
        candidates=(
            CandidatePredictions(
                "robust-v1",
                "deterministic_robust",
                tuple(value + 1 for value in truth),
                latency_ms=1,
                cost_units=0,
            ),
            CandidatePredictions(
                "linear-v1",
                "regularized_linear",
                tuple(value + 0.1 for value in truth),
                latency_ms=5,
                cost_units=0.1,
            ),
        ),
    )
    assert report.selected_challenger_id == "linear-v1"
    assert report.decision == "eligible_for_offline_review"


def test_unjustified_neural_candidate_is_rejected() -> None:
    truth = tuple(float(index % 5) for index in range(30))
    with pytest.raises(PredictiveGovernanceError, match="not_justified"):
        evaluate_bakeoff(
            use_case=_use_case(),
            y_true=truth,
            slice_keys=tuple("a" for _ in truth),
            candidates=(
                CandidatePredictions(
                    "robust-v1", "deterministic_robust", truth, 1, 0
                ),
                CandidatePredictions("neural-v1", "neural_sequence", truth, 5, 0.1),
            ),
        )
