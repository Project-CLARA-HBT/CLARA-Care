"""Contained adaptive intelligence for LifeMap questions and workflow friction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class AdaptivePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class UtilityLabel:
    information_value: float
    safety_impact: float
    user_usefulness: float
    burden: float
    dismissed: bool
    click_observed: bool
    review_version: str


def utility_value(label: UtilityLabel) -> float:
    values = (
        label.information_value,
        label.safety_impact,
        label.user_usefulness,
        label.burden,
    )
    if (
        not label.review_version
        or any(not 0 <= value <= 1 or not math.isfinite(value) for value in values)
    ):
        raise AdaptivePolicyError("utility_label_invalid")
    # Clicks are deliberately excluded: engagement is not health benefit.
    dismissal_penalty = 1.0 if label.dismissed else 0.0
    return (
        0.35 * label.information_value
        + 0.30 * label.safety_impact
        + 0.35 * label.user_usefulness
        - 0.45 * label.burden
        - dismissal_penalty
    )


@dataclass(frozen=True)
class EligibleQuestion:
    question_id: str
    deterministic_rank: int
    burden_cost: float


@dataclass(frozen=True)
class RankContext:
    stable_features: tuple[float, ...]
    burden_today: float
    cooldown_active: bool
    do_not_ask: bool
    consent_active: bool
    emergency_detected: bool


class QuestionScorer(Protocol):
    model_id: str
    artifact_verified: bool

    def score(
        self,
        *,
        context: tuple[float, ...],
        eligible_question_ids: tuple[str, ...],
    ) -> dict[str, float]: ...


@dataclass(frozen=True)
class RankedQuestion:
    question_id: str
    score: float
    propensity: float
    policy_version: str
    model_id: str
    shadow_only: bool


@dataclass(frozen=True)
class ShadowRankingComparison:
    deterministic_top_id: str
    learned_top_id: str
    top_one_changed: bool
    rank_agreement: float
    eligible_set_preserved: bool


def compare_shadow_rankings(
    deterministic: tuple[RankedQuestion, ...],
    learned: tuple[RankedQuestion, ...],
) -> ShadowRankingComparison:
    if not deterministic or not learned:
        raise AdaptivePolicyError("shadow_comparison_requires_rankings")
    deterministic_ids = [item.question_id for item in deterministic]
    learned_ids = [item.question_id for item in learned]
    if set(deterministic_ids) != set(learned_ids):
        raise AdaptivePolicyError("shadow_eligible_set_changed")
    learned_positions = {item: index for index, item in enumerate(learned_ids)}
    agreement = 1 - (
        sum(
            abs(index - learned_positions[question_id])
            for index, question_id in enumerate(deterministic_ids)
        )
        / max(1, len(deterministic_ids) ** 2)
    )
    return ShadowRankingComparison(
        deterministic_top_id=deterministic_ids[0],
        learned_top_id=learned_ids[0],
        top_one_changed=deterministic_ids[0] != learned_ids[0],
        rank_agreement=max(0.0, min(1.0, agreement)),
        eligible_set_preserved=True,
    )


def rank_eligible_questions(
    *,
    eligible: tuple[EligibleQuestion, ...],
    context: RankContext,
    scorer: QuestionScorer | None,
    policy_version: str,
    shadow_only: bool,
) -> tuple[RankedQuestion, ...]:
    if (
        not policy_version
        or context.emergency_detected
        or context.do_not_ask
        or context.cooldown_active
        or not context.consent_active
        or not eligible
    ):
        return ()
    ids = tuple(item.question_id for item in eligible)
    if not all(ids) or len(set(ids)) != len(ids):
        raise AdaptivePolicyError("eligible_question_set_invalid")
    if scorer is None:
        ordered = sorted(eligible, key=lambda item: item.deterministic_rank)
        return tuple(
            RankedQuestion(
                question_id=item.question_id,
                score=-float(item.deterministic_rank),
                propensity=1.0 if index == 0 else 0.0,
                policy_version=policy_version,
                model_id="deterministic-fallback",
                shadow_only=shadow_only,
            )
            for index, item in enumerate(ordered)
        )
    if not scorer.artifact_verified:
        raise AdaptivePolicyError("ranker_artifact_not_verified")
    scores = scorer.score(context=context.stable_features, eligible_question_ids=ids)
    if set(scores) != set(ids):
        raise AdaptivePolicyError("ranker_modified_eligible_action_set")
    if any(not math.isfinite(value) for value in scores.values()):
        raise AdaptivePolicyError("ranker_score_invalid")
    ordered_ids = sorted(ids, key=lambda item: (-scores[item], item))
    # A deterministic greedy policy has propensity 1 only for its first action.
    return tuple(
        RankedQuestion(
            question_id=question_id,
            score=scores[question_id],
            propensity=1.0 if index == 0 else 0.0,
            policy_version=policy_version,
            model_id=scorer.model_id,
            shadow_only=shadow_only,
        )
        for index, question_id in enumerate(ordered_ids)
    )


@dataclass(frozen=True)
class LoggedAction:
    reward: float
    logging_propensity: float
    evaluation_probability: float


@dataclass(frozen=True)
class OfflinePolicyEstimate:
    inverse_propensity_value: float
    effective_sample_size: float
    support_violations: int
    eligible_for_shadow_review: bool


def evaluate_logged_policy(
    actions: tuple[LoggedAction, ...],
    *,
    minimum_effective_sample_size: float,
    maximum_weight: float = 20.0,
) -> OfflinePolicyEstimate:
    if not actions or minimum_effective_sample_size <= 0 or maximum_weight <= 0:
        raise AdaptivePolicyError("offline_policy_inputs_invalid")
    weighted_rewards = []
    weights = []
    violations = 0
    for action in actions:
        if (
            not math.isfinite(action.reward)
            or not 0 <= action.evaluation_probability <= 1
            or not 0 <= action.logging_propensity <= 1
        ):
            raise AdaptivePolicyError("logged_action_invalid")
        if action.evaluation_probability > 0 and action.logging_propensity == 0:
            violations += 1
            continue
        weight = min(
            maximum_weight,
            action.evaluation_probability / action.logging_propensity,
        )
        weights.append(weight)
        weighted_rewards.append(weight * action.reward)
    if not weights or sum(weights) == 0:
        return OfflinePolicyEstimate(0.0, 0.0, violations, False)
    effective = sum(weights) ** 2 / sum(weight**2 for weight in weights)
    value = sum(weighted_rewards) / sum(weights)
    return OfflinePolicyEstimate(
        inverse_propensity_value=value,
        effective_sample_size=effective,
        support_violations=violations,
        eligible_for_shadow_review=(
            violations == 0 and effective >= minimum_effective_sample_size
        ),
    )


@dataclass(frozen=True)
class BanditPilotProtocol:
    protocol_id: str
    safe_action_ids: tuple[str, ...]
    probability_floor: float
    probability_ceiling: float
    daily_burden_ceiling: int
    weekly_burden_ceiling: int
    cohort_definition: str
    minimum_sample_size: int
    monitoring_metrics: tuple[str, ...]
    stop_criteria: tuple[str, ...]
    consent_version: str
    approval_id: str | None = None


def validate_bandit_protocol(protocol: BanditPilotProtocol) -> None:
    if (
        not protocol.protocol_id
        or not protocol.safe_action_ids
        or len(set(protocol.safe_action_ids)) != len(protocol.safe_action_ids)
        or not 0 < protocol.probability_floor <= protocol.probability_ceiling < 1
        or protocol.daily_burden_ceiling < 1
        or protocol.weekly_burden_ceiling < protocol.daily_burden_ceiling
        or not protocol.cohort_definition
        or protocol.minimum_sample_size < 100
        or not protocol.monitoring_metrics
        or not protocol.stop_criteria
        or not protocol.consent_version
    ):
        raise AdaptivePolicyError("bandit_protocol_invalid")


ALLOWED_FRICTION_ACTIONS = frozenset(
    {
        "reduce_reminders",
        "change_time",
        "offer_pause",
        "offer_smaller_user_step",
        "offer_help",
    }
)


@dataclass(frozen=True)
class FrictionAssessment:
    action: str | None
    friction_score: float
    notification_pressure: int
    model_id: str


@dataclass(frozen=True)
class FrictionFeatures:
    reminder_attempts_7d: int
    dismissals_7d: int
    deferrals_7d: int
    task_step_count: int
    local_hour: int

    def as_vector(self) -> tuple[float, ...]:
        values = (
            self.reminder_attempts_7d,
            self.dismissals_7d,
            self.deferrals_7d,
            self.task_step_count,
        )
        if any(value < 0 for value in values) or not 0 <= self.local_hour <= 23:
            raise AdaptivePolicyError("friction_features_invalid")
        return tuple(float(value) for value in (*values, self.local_hour))


class FrictionScorer(Protocol):
    model_id: str
    artifact_verified: bool

    def score(self, features: tuple[float, ...]) -> float: ...


def assess_friction(
    *,
    features: FrictionFeatures,
    scorer: FrictionScorer,
    proposed_actions: tuple[str, ...],
    notification_pressure: int,
    pressure_ceiling: int,
) -> FrictionAssessment:
    if not scorer.artifact_verified:
        raise AdaptivePolicyError("friction_artifact_not_verified")
    return choose_friction_action(
        friction_score=scorer.score(features.as_vector()),
        proposed_actions=proposed_actions,
        notification_pressure=notification_pressure,
        pressure_ceiling=pressure_ceiling,
        model_id=scorer.model_id,
    )


def choose_friction_action(
    *,
    friction_score: float,
    proposed_actions: tuple[str, ...],
    notification_pressure: int,
    pressure_ceiling: int,
    model_id: str,
) -> FrictionAssessment:
    if (
        not math.isfinite(friction_score)
        or not 0 <= friction_score <= 1
        or pressure_ceiling < 0
        or notification_pressure < 0
        or not model_id
    ):
        raise AdaptivePolicyError("friction_inputs_invalid")
    if any(action not in ALLOWED_FRICTION_ACTIONS for action in proposed_actions):
        raise AdaptivePolicyError("friction_action_forbidden")
    if notification_pressure >= pressure_ceiling:
        action = "reduce_reminders" if "reduce_reminders" in proposed_actions else None
    elif friction_score >= 0.7 and proposed_actions:
        action = proposed_actions[0]
    else:
        action = None
    # No action in this use case can increase notification pressure.
    return FrictionAssessment(
        action=action,
        friction_score=friction_score,
        notification_pressure=min(notification_pressure, pressure_ceiling),
        model_id=model_id,
    )
