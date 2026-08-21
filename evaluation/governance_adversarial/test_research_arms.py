from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.research_arms import (
    CommitCoordinates,
    evaluate_commit_admission,
)


def test_arms_have_distinct_prespecified_revalidation_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    stale_governance = CommitCoordinates(True, True, True, False)
    stale_state = CommitCoordinates(True, True, False, True)
    invalid_snapshot = CommitCoordinates(True, False, True, True)

    assert evaluate_commit_admission(arm_name="UNBOUND", coordinates=stale_state).accepted
    assert evaluate_commit_admission(
        arm_name="STATE_VERSION_ONLY", coordinates=stale_governance
    ).accepted
    assert not evaluate_commit_admission(
        arm_name="STATE_VERSION_ONLY", coordinates=stale_state
    ).accepted
    assert evaluate_commit_admission(
        arm_name="SNAPSHOT_BOUND_STATE_ONLY", coordinates=stale_governance
    ).accepted
    assert not evaluate_commit_admission(
        arm_name="SNAPSHOT_BOUND_STATE_ONLY", coordinates=invalid_snapshot
    ).accepted
    strict = evaluate_commit_admission(arm_name="GLHS_STRICT", coordinates=stale_governance)
    assert not strict.accepted and strict.reason_code == "governance_coordinate_stale"


def test_arm_admission_refuses_without_isolated_research_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLARA_GOVRED_ISOLATED_RESEARCH", raising=False)
    with pytest.raises(FreezeError, match="govred_research_arm_requires_isolated_environment"):
        evaluate_commit_admission(
            arm_name="GLHS_STRICT",
            coordinates=CommitCoordinates(True, True, True, True),
        )


def test_production_services_do_not_import_research_arm_implementation() -> None:
    root = Path(__file__).resolve().parents[2]
    production_roots = (root / "services/api/src", root / "services/ml/src")
    forbidden = ("evaluation.governance_adversarial", "research_arms")
    for source_root in production_roots:
        for source in source_root.rglob("*.py"):
            contents = source.read_text(encoding="utf-8")
            assert not any(marker in contents for marker in forbidden), source
