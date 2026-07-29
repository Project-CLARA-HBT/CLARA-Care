from dataclasses import dataclass

import pytest

from clara_ml.lifemap.adaptive import (
    AdaptivePolicyError,
    BanditPilotProtocol,
    EligibleQuestion,
    FrictionFeatures,
    LoggedAction,
    RankContext,
    UtilityLabel,
    assess_friction,
    choose_friction_action,
    compare_shadow_rankings,
    evaluate_logged_policy,
    rank_eligible_questions,
    utility_value,
    validate_bandit_protocol,
)


@dataclass
class _Scorer:
    values: dict[str, float]
    model_id: str = "signed-ranker-v1"
    artifact_verified: bool = True

    def score(
        self, *, context: tuple[float, ...], eligible_question_ids: tuple[str, ...]
    ) -> dict[str, float]:
        del context, eligible_question_ids
        return self.values


def _context(**overrides: object) -> RankContext:
    values = {
        "stable_features": (0.2, 0.4),
        "burden_today": 0.0,
        "cooldown_active": False,
        "do_not_ask": False,
        "consent_active": True,
        "emergency_detected": False,
    }
    values.update(overrides)
    return RankContext(**values)  # type: ignore[arg-type]


def test_utility_uses_information_safety_usefulness_and_burden_not_clicks() -> None:
    base = UtilityLabel(0.8, 0.9, 0.7, 0.2, False, False, "review-v1")
    clicked = UtilityLabel(0.8, 0.9, 0.7, 0.2, False, True, "review-v1")
    dismissed = UtilityLabel(0.8, 0.9, 0.7, 0.2, True, True, "review-v1")
    assert utility_value(base) == utility_value(clicked)
    assert utility_value(dismissed) < utility_value(base)


def test_ranker_can_only_reorder_verified_deterministic_eligible_set() -> None:
    eligible = (EligibleQuestion("q1", 1, 0.1), EligibleQuestion("q2", 2, 0.1))
    ranked = rank_eligible_questions(
        eligible=eligible,
        context=_context(),
        scorer=_Scorer({"q1": 0.1, "q2": 0.9}),
        policy_version="policy-v1",
        shadow_only=True,
    )
    assert [item.question_id for item in ranked] == ["q2", "q1"]
    assert ranked[0].shadow_only is True
    deterministic = rank_eligible_questions(
        eligible=eligible,
        context=_context(),
        scorer=None,
        policy_version="policy-v1",
        shadow_only=True,
    )
    comparison = compare_shadow_rankings(deterministic, ranked)
    assert comparison.top_one_changed is True
    assert comparison.eligible_set_preserved is True
    with pytest.raises(AdaptivePolicyError, match="modified_eligible"):
        rank_eligible_questions(
            eligible=eligible,
            context=_context(),
            scorer=_Scorer({"q1": 0.1, "invented": 0.9}),
            policy_version="policy-v1",
            shadow_only=True,
        )


def test_emergency_consent_and_do_not_ask_precede_learned_ranking() -> None:
    eligible = (EligibleQuestion("q1", 1, 0.1),)
    assert (
        rank_eligible_questions(
            eligible=eligible,
            context=_context(emergency_detected=True),
            scorer=_Scorer({"q1": 1}),
            policy_version="policy-v1",
            shadow_only=True,
        )
        == ()
    )
    assert (
        rank_eligible_questions(
            eligible=eligible,
            context=_context(consent_active=False),
            scorer=_Scorer({"q1": 1}),
            policy_version="policy-v1",
            shadow_only=True,
        )
        == ()
    )


def test_offline_policy_evaluation_reports_support_and_effective_sample() -> None:
    estimate = evaluate_logged_policy(
        (
            LoggedAction(1.0, 0.5, 0.5),
            LoggedAction(0.0, 0.5, 0.5),
            LoggedAction(1.0, 0.0, 0.5),
        ),
        minimum_effective_sample_size=2,
    )
    assert estimate.inverse_propensity_value == 0.5
    assert estimate.support_violations == 1
    assert estimate.eligible_for_shadow_review is False


def test_bandit_protocol_is_specified_but_has_no_activation_authority() -> None:
    protocol = BanditPilotProtocol(
        protocol_id="question-bandit-protocol-v1",
        safe_action_ids=("q1", "q2"),
        probability_floor=0.1,
        probability_ceiling=0.9,
        daily_burden_ceiling=1,
        weekly_burden_ceiling=3,
        cohort_definition="consenting adult allowlist",
        minimum_sample_size=200,
        monitoring_metrics=("burden", "dismissal", "safety"),
        stop_criteria=("safety_event", "burden_ceiling"),
        consent_version="medical-v1",
        approval_id=None,
    )
    validate_bandit_protocol(protocol)
    assert protocol.approval_id is None


def test_friction_actions_cannot_increase_pressure_or_escape_allowlist() -> None:
    result = choose_friction_action(
        friction_score=0.9,
        proposed_actions=("reduce_reminders", "offer_pause"),
        notification_pressure=3,
        pressure_ceiling=3,
        model_id="friction-shadow-v1",
    )
    assert result.action == "reduce_reminders"
    assert result.notification_pressure == 3
    with pytest.raises(AdaptivePolicyError, match="forbidden"):
        choose_friction_action(
            friction_score=0.9,
            proposed_actions=("increase_reminders",),
            notification_pressure=0,
            pressure_ceiling=3,
            model_id="friction-shadow-v1",
        )


def test_friction_model_receives_only_bounded_non_content_features() -> None:
    @dataclass
    class _FrictionScorer:
        model_id: str = "signed-friction-v1"
        artifact_verified: bool = True

        def score(self, features: tuple[float, ...]) -> float:
            assert features == (2.0, 1.0, 1.0, 3.0, 20.0)
            return 0.8

    result = assess_friction(
        features=FrictionFeatures(2, 1, 1, 3, 20),
        scorer=_FrictionScorer(),
        proposed_actions=("offer_smaller_user_step",),
        notification_pressure=1,
        pressure_ceiling=3,
    )
    assert result.action == "offer_smaller_user_step"
