from __future__ import annotations

from datetime import UTC, datetime

import pytest

from evaluation.governance_adversarial.govred_repetition_protocol import (
    REPETITIONS_PER_SCENARIO,
    SCENARIO_COUNT,
    TOTAL_REPETITIONS,
    CommitOrderEvidence,
    aggregate_at_logical_schedule,
    build_repeat_manifest,
    classify_commit_order,
    ordering_to_state,
    run_repetition,
    scenario_ids,
    validate_repeat_manifest,
)


def test_scenario_ids_and_repetition_totals() -> None:
    ids = scenario_ids()
    assert len(ids) == SCENARIO_COUNT == 30
    assert ids[0] == "concurrent_stale_state_write-001"
    assert TOTAL_REPETITIONS == 30 * REPETITIONS_PER_SCENARIO == 1500


def test_manifest_build_and_validate() -> None:
    manifest = build_repeat_manifest()
    result = validate_repeat_manifest(manifest)
    assert result["status"] == "VALIDATED_FROZEN_NOT_EXECUTED"
    assert result["scenario_count"] == 30
    assert result["repetitions_per_logical_schedule"] == 50
    assert result["total_repetitions"] == 1500
    assert manifest["db"]["track_commit_timestamp_available"] is True
    assert manifest["logical_unit"].startswith("scenario")


def test_manifest_requires_track_commit_timestamp() -> None:
    manifest = build_repeat_manifest()
    manifest["db"]["track_commit_timestamp_available"] = False
    with pytest.raises(ValueError, match="requires_track_commit_timestamp"):
        validate_repeat_manifest(manifest)


def test_manifest_rejects_non_frozen() -> None:
    manifest = build_repeat_manifest()
    manifest["status"] = "draft"
    with pytest.raises(ValueError, match="not_frozen"):
        validate_repeat_manifest(manifest)


def test_manifest_rejects_altered_scenario_set() -> None:
    manifest = build_repeat_manifest()
    manifest["scenario_ids"] = ["concurrent_stale_state_write-001"]
    with pytest.raises(ValueError, match="scenario_ids_invalid"):
        validate_repeat_manifest(manifest)


def _evidence(
    *,
    gov_ts: datetime | None,
    prop_ts: datetime | None,
    outcome: str = "transition_committed",
) -> CommitOrderEvidence:
    return CommitOrderEvidence(
        governance_txid=1,
        proposal_txid=2,
        governance_commit_ts=gov_ts,
        proposal_commit_ts=prop_ts,
        track_commit_timestamp=True,
        outcome=outcome,
    )


def test_commit_order_never_inferred_from_txid() -> None:
    evidence = _evidence(gov_ts=None, prop_ts=None)
    ordering, confidence, reason = classify_commit_order(evidence)
    assert ordering == "unknowable"
    assert confidence == "none"
    assert "commit timestamp unavailable" in reason
    # Even with txids present, no timestamp means no ordering.
    assert ordering_to_state("transition_committed", ordering) == "INDETERMINATE"


def test_governance_first_is_confirmed_invalid_when_committed() -> None:
    base = datetime(2026, 8, 19, tzinfo=UTC)
    evidence = _evidence(gov_ts=base, prop_ts=base.replace(second=1))
    ordering, confidence, _ = classify_commit_order(evidence)
    assert ordering == "governance_committed_before_proposal"
    assert confidence == "high"
    assert ordering_to_state("transition_committed", ordering) == "CONFIRMED_INVALID"


def test_proposal_first_is_not_a_violation() -> None:
    base = datetime(2026, 8, 19, tzinfo=UTC)
    evidence = _evidence(gov_ts=base.replace(second=1), prop_ts=base)
    ordering, _, _ = classify_commit_order(evidence)
    assert ordering == "proposal_committed_before_governance"
    assert ordering_to_state("transition_committed", ordering) == "INDETERMINATE"


def test_same_timestamp_is_indeterminate() -> None:
    base = datetime(2026, 8, 19, tzinfo=UTC)
    evidence = _evidence(gov_ts=base, prop_ts=base)
    ordering, confidence, _ = classify_commit_order(evidence)
    assert ordering == "same_commit_timestamp"
    assert confidence == "none"
    assert ordering_to_state("transition_committed", ordering) == "INDETERMINATE"


def test_monotonic_fallback_resolves_conclusive_windows() -> None:
    evidence = CommitOrderEvidence(
        governance_txid=1,
        proposal_txid=2,
        governance_commit_ts=None,
        proposal_commit_ts=None,
        track_commit_timestamp=True,
        outcome="transition_committed",
        monotonic_evidence={
            "governance_commit_ns": 1000,
            "proposal_start_ns": 2000,
            "proposal_complete_ns": 3000,
        },
    )
    ordering, confidence, _ = classify_commit_order(evidence)
    assert ordering == "governance_committed_before_proposal"
    assert confidence == "medium"
    assert ordering_to_state("transition_committed", ordering) == "CONFIRMED_INVALID"


def test_monotonic_overlap_stays_indeterminate() -> None:
    evidence = CommitOrderEvidence(
        governance_txid=1,
        proposal_txid=2,
        governance_commit_ts=None,
        proposal_commit_ts=None,
        track_commit_timestamp=True,
        outcome="transition_committed",
        monotonic_evidence={"governance_commit_ns": 2000, "proposal_start_ns": 1000},
    )
    ordering, confidence, _ = classify_commit_order(evidence)
    assert ordering == "unknowable"
    assert confidence == "none"


def test_rejected_outcome_is_safe_regardless_of_order() -> None:
    evidence = _evidence(gov_ts=None, prop_ts=None, outcome="rejected")
    ordering, _, _ = classify_commit_order(evidence)
    assert ordering_to_state("rejected", ordering) == "CONFIRMED_SAFE_OR_REJECTED"


def test_aggregation_robust_only_if_all_valid_repetitions_satisfy() -> None:
    base = datetime(2026, 8, 19, tzinfo=UTC)
    records = [
        run_repetition(
            "concurrent_stale_state_write-001",
            repeat_id=index,
            evidence=_evidence(
                gov_ts=base,
                prop_ts=base.replace(second=1),
                outcome="rejected",
            ),
        )
        for index in range(5)
    ]
    result = aggregate_at_logical_schedule(records)
    assert result["robust"] is True
    assert result["verdict"] == "robust"


def test_mixed_classifications_are_not_majority_voted() -> None:
    base = datetime(2026, 8, 19, tzinfo=UTC)
    records = [
        run_repetition(
            "concurrent_stale_state_write-001",
            repeat_id=0,
            evidence=_evidence(gov_ts=base, prop_ts=base.replace(second=1)),
        ),
        run_repetition(
            "concurrent_stale_state_write-001",
            repeat_id=1,
            evidence=_evidence(
                gov_ts=base.replace(second=1),
                prop_ts=base.replace(second=2),
                outcome="rejected",
            ),
        ),
    ]
    result = aggregate_at_logical_schedule(records)
    assert result["robust"] is False
    assert result["verdict"] == "not_robust"
    # State counts report the mix; nothing is majority-voted into safety.
    assert result["state_counts"]["CONFIRMED_INVALID"] == 1
    assert result["state_counts"]["CONFIRMED_SAFE_OR_REJECTED"] == 1


def test_indeterminate_repetition_blocks_robust_verdict() -> None:
    records = [
        run_repetition(
            "concurrent_stale_state_write-001",
            repeat_id=index,
            evidence=_evidence(gov_ts=None, prop_ts=None),
        )
        for index in range(3)
    ]
    result = aggregate_at_logical_schedule(records)
    assert result["robust"] is False
    assert result["state_counts"]["INDETERMINATE"] == 3


def test_aggregation_rejects_mixed_scenarios() -> None:
    with pytest.raises(ValueError, match="mixed_scenarios"):
        aggregate_at_logical_schedule(
            [
                run_repetition(
                    "concurrent_stale_state_write-001", 0, _evidence(gov_ts=None, prop_ts=None)
                ),
                run_repetition(
                    "concurrent_stale_state_write-002", 0, _evidence(gov_ts=None, prop_ts=None)
                ),
            ]
        )
