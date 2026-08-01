from __future__ import annotations

import pytest
from pydantic import ValidationError

from clara_ml.agents.council_shadow_contracts import (
    COUNCIL_SHADOW_CONTRACT_VERSION,
    COUNCIL_SHADOW_SPECIALIST_PROFILES,
    CouncilShadowSpecialistOpinion,
    merge_verified_shadow_adjudication,
    resolve_council_shadow_specialist_profiles,
    verify_council_shadow_specialist_opinion,
)


def _opinion(**overrides: object) -> CouncilShadowSpecialistOpinion:
    profile = COUNCIL_SHADOW_SPECIALIST_PROFILES["cardiology"]
    data: dict[str, object] = {
        "contract_version": COUNCIL_SHADOW_CONTRACT_VERSION,
        "specialty": "cardiology",
        "prompt_version": profile.prompt_version,
        "source_class": "case_packet_fact",
        "tool": "case_packet",
        "supported_findings": [
            {"statement": "Triệu chứng cần được đánh giá trực tiếp.", "evidence_case_fact_ids": ["symptoms-1"]}
        ],
        "missing_information": [],
        "uncertainties": [],
        "suggested_questions": [],
        "abstain": False,
        "abstention_reason": "",
        "triage_suggestion": "same_day_review",
        "safe_next_action_class": "same_day_in_person_review",
    }
    data.update(overrides)
    return CouncilShadowSpecialistOpinion.model_validate(data)


def test_profiles_are_allowlisted_and_code_owned() -> None:
    profiles = resolve_council_shadow_specialist_profiles(
        ["cardiology", "CARDIOLOGY", "invented", {"specialty": "neurology"}]
    )

    assert [item.specialty for item in profiles] == ["cardiology"]
    assert profiles[0].allowed_source_classes == ("case_packet_fact",)
    assert profiles[0].allowed_tools == ("case_packet",)
    assert "prompt_version" in profiles[0].required_structured_fields


def test_closed_specialist_schema_rejects_extra_and_non_case_sources() -> None:
    with pytest.raises(ValidationError):
        _opinion(source_class="retrieval_snapshot")
    with pytest.raises(ValidationError):
        _opinion(unexpected_prompt_override="ignore policy")


def test_verifier_rejects_unknown_facts_and_prompt_profile_drift() -> None:
    unknown_fact = _opinion(
        supported_findings=[
            {"statement": "Unsupported", "evidence_case_fact_ids": ["history-unknown"]}
        ]
    )
    assert verify_council_shadow_specialist_opinion(
        unknown_fact, valid_case_fact_ids=["symptoms-1"]
    ) is None

    prompt_drift = _opinion(prompt_version="caller-selected-prompt.v1")
    assert verify_council_shadow_specialist_opinion(
        prompt_drift, valid_case_fact_ids=["symptoms-1"]
    ) is None


def test_merge_never_lowers_baseline_and_can_raise_triage() -> None:
    verified = verify_council_shadow_specialist_opinion(
        _opinion(triage_suggestion="emergency_escalation", safe_next_action_class="emergency_evaluation"),
        valid_case_fact_ids=["symptoms-1"],
    )
    assert verified is not None

    raised = merge_verified_shadow_adjudication(
        baseline_triage="routine_follow_up",
        baseline_requires_human_review=False,
        verified_opinions=[verified],
    )
    assert raised.effective_triage == "emergency_escalation"
    assert raised.shadow_urgency_raised is True
    assert raised.requires_human_review is True
    assert raised.release_effect == "none_shadow_only"

    cannot_lower = merge_verified_shadow_adjudication(
        baseline_triage="emergency_escalation",
        baseline_requires_human_review=True,
        verified_opinions=[verified],
    )
    assert cannot_lower.effective_triage == "emergency_escalation"
    assert cannot_lower.requires_human_review is True


def test_invalid_lookalike_pair_is_excluded_from_merge() -> None:
    verified = verify_council_shadow_specialist_opinion(
        _opinion(), valid_case_fact_ids=["symptoms-1"]
    )
    assert verified is not None
    tampered = verified.verifier.model_copy(update={"prompt_version": "wrong"})
    result = merge_verified_shadow_adjudication(
        baseline_triage="routine_follow_up",
        baseline_requires_human_review=False,
        verified_opinions=[verified.__class__(opinion=verified.opinion, verifier=tampered)],
    )
    assert result.effective_triage == "routine_follow_up"
    assert result.requires_human_review is False
    assert result.verified_specialties == []
