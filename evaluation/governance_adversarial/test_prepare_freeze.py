from __future__ import annotations

from evaluation.governance_adversarial.prepare_freeze import prepare
from evaluation.governance_adversarial.protocol import FAMILIES


def test_prepare_creates_nonexecutable_locked_test_candidates() -> None:
    artifacts = prepare(
        seed=20260817,
        repetitions=1,
        statistics_plan={"schema_version": "govred-statistics-plan-v1", "status": "draft"},
    )

    candidate = artifacts["locked_test_candidate.json"]
    final = artifacts["final_locked_manifest_template.json"]
    receipt = artifacts["freeze_preparation_receipt.json"]
    assert candidate["partition"] == "locked_test_candidate"
    assert candidate["freeze_state"] == "candidate_pending_independent_review"
    assert {case["family"] for case in candidate["cases"]} == set(FAMILIES)
    assert final["partition"] == "locked_test"
    assert final["status"] == "draft"
    assert final["independent_curator_attestation"] is False
    assert receipt["status"] == "candidate_and_template_only_not_frozen_not_executed"
