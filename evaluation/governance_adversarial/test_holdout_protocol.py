from __future__ import annotations

import pytest

from evaluation.governance_adversarial.holdout_protocol import (
    AUTHORSHIP_MODE,
    MAX_SCHEDULES,
    MIN_SCHEDULES,
    build_holdout_freeze,
    build_holdout_schedules,
    validate_holdout_freeze,
)


def test_skeleton_is_within_30_60_and_balanced() -> None:
    schedules = build_holdout_schedules()
    assert MIN_SCHEDULES <= len(schedules) <= MAX_SCHEDULES
    families = {s["family"] for s in schedules}
    assert "gst_bypass_prompt" not in families
    assert "patient_evidence_prompt_injection" not in families
    # No oracle expectations or authorship in the skeleton.
    assert all(s.get("authorship") is None for s in schedules)
    assert all("expected_outcome" not in s for s in schedules)


def test_skeleton_respects_explicit_count() -> None:
    schedules = build_holdout_schedules(30)
    assert len(schedules) == 30


def test_skeleton_rejects_out_of_range_count() -> None:
    with pytest.raises(ValueError, match="out_of_range"):
        build_holdout_schedules(29)
    with pytest.raises(ValueError, match="out_of_range"):
        build_holdout_schedules(61)


def test_freeze_requires_independent_human_authors() -> None:
    schedules = build_holdout_schedules(30)
    authors = {s["schedule_id"]: "human-author:ana" for s in schedules}
    freeze = build_holdout_freeze(schedules, authors=authors)
    assert freeze["status"] == "FROZEN_UNEXECUTED_MANUAL_AUTHORSHIP_GATE"
    assert freeze["execution_status"] == "NOT_EXECUTED"
    assert freeze["reporting"] == "separate from final-003; never merged"
    for schedule in freeze["schedules"]:
        assert schedule["authorship"]["mode"] == AUTHORSHIP_MODE
        assert schedule["authorship"]["author_id"].startswith("human-author:")


def test_llm_simulated_authorship_is_rejected() -> None:
    schedules = build_holdout_schedules(30)
    authors = {s["schedule_id"]: "llm-assistant:model-x" for s in schedules}
    with pytest.raises(ValueError, match="independent_human"):
        build_holdout_freeze(schedules, authors=authors)


def test_missing_author_is_rejected() -> None:
    schedules = build_holdout_schedules(30)
    with pytest.raises(ValueError, match="missing_independent_human_author"):
        build_holdout_freeze(schedules, authors={})


def test_validate_fails_closed_on_execution() -> None:
    schedules = build_holdout_schedules(30)
    authors = {s["schedule_id"]: "human-author:ana" for s in schedules}
    freeze = build_holdout_freeze(schedules, authors=authors)
    freeze["execution_status"] = "EXECUTED"
    with pytest.raises(ValueError, match="must_not_be_executed"):
        validate_holdout_freeze(freeze)


def test_validate_accepts_frozen_unexecuted() -> None:
    schedules = build_holdout_schedules(30)
    authors = {s["schedule_id"]: "human-author:ana" for s in schedules}
    freeze = build_holdout_freeze(schedules, authors=authors)
    result = validate_holdout_freeze(freeze)
    assert result["status"] == "VALIDATED_FROZEN_HOLDOUT_NOT_EXECUTED"
    assert result["database_executed"] is False
    assert result["result_emitted"] is False