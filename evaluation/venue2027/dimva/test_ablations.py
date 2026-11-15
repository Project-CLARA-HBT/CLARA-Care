"""Tests for DIMVA-ablation — causal mechanism ablation variants for GovernanceTrace.

Positive controls:
- Every registered variant in ABLATION_REGISTRY runs through run_ablation(name, case)
  and detect_variant(name, events).
- The full candidate (full_candidate) DETECTs the crafted low-and-slow cross-tool
  campaign (9 denials over 9 distinct tools across 8h logical time).
- Removing campaign linkage (without_campaign_linkage) causes the detector to
  MISS the low-and-slow campaign that full_candidate catches (core P04 causal requirement).
- Removing cross-tool feature (without_cross_tool_feature) causes the detector to
  MISS the low-and-slow campaign because tool diversity collapses.
- Removing pacing feature (without_pacing_feature) causes the detector to MISS
  the low-and-slow campaign because evades_fixed_window is unsatisfied.
- Static per-window counting (with_only_per_window_counts) misses the low-and-slow
  campaign AND false-flags the benign burst (B0 falsification arm).
- All variants admit legitimate benign controls (single retry, care-team handoff).
- Mechanistic inference matrix: every variant x family prediction matches observed
  executions (all_cells_match is True).
- Determinism: repeated evaluations produce byte-identical results.

Adversarial controls:
- Unregistered variant ids are refused by refuse_unregistered_variant and run_ablation
  with UNKNOWN_ABLATION_VARIANT (fail closed, never run as full candidate).
- Known identities that remove no mechanism (CANDIDATE_ID, "candidate", "DIMVA-candidate")
  are refused with VARIANT_REMOVES_NOTHING.
- VariantSpec construction with an empty ablated mechanism or an impostor 'none'
  is refused with VARIANT_REMOVES_NOTHING.
- Malformed cases (non-mapping, missing events, events not a list) fail closed
  to INDETERMINATE, never counted as success.
- Malformed minimal events (reason-code leakage, unknown fields, bad types,
  non-monotonic timestamps, mixed actors) fail closed to INDETERMINATE with
  stable candidate reason codes.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027.dimva import ablations as abl
from evaluation.venue2027.dimva import candidate as cand

# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


class TestAblationRegistryAndSpecs:
    def test_registry_contains_expected_variants(self) -> None:
        expected = {
            abl.VARIANT_WITHOUT_CAMPAIGN_LINKAGE,
            abl.VARIANT_WITHOUT_CROSS_TOOL_FEATURE,
            abl.VARIANT_WITHOUT_PACING_FEATURE,
            abl.VARIANT_WITH_ONLY_PER_WINDOW_COUNTS,
            abl.VARIANT_FULL_CANDIDATE,
        }
        assert set(abl.ABLATION_REGISTRY) == expected
        assert abl.variant_ids() == tuple(abl.ABLATION_REGISTRY)

    def test_each_spec_declares_exact_mechanism_and_provenance(self) -> None:
        for variant_id, spec in abl.ABLATION_REGISTRY.items():
            assert spec.variant_id == variant_id
            assert spec.title
            assert spec.ablated_mechanism
            assert spec.description
            assert spec.expected_effect
            assert spec.reuses
            assert spec.applied_by
            data = spec.to_dict()
            assert data["variant_id"] == variant_id
            assert data["ablated_mechanism"] == spec.ablated_mechanism


class TestPositiveAblationBehaviors:
    @pytest.mark.parametrize("variant_id", sorted(abl.ABLATION_REGISTRY))
    def test_each_registered_variant_runs(self, variant_id: str) -> None:
        case = abl.fixture_benign_retry()
        outcome = abl.run_ablation(variant_id, case)
        assert outcome.observed_outcome in (abl.VERDICT_ADMIT, abl.VERDICT_REJECT)
        assert outcome.counted_as_success is True

        detection = abl.detect_variant(variant_id, case["events"])
        assert detection.decision in (cand.DETECT, cand.NO_DETECT)
        assert 0.0 <= detection.score <= 1.0

    def test_full_candidate_catches_low_and_slow_campaign(self) -> None:
        case = abl.fixture_low_and_slow_cross_tool()
        outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case)
        assert outcome.observed_outcome == abl.VERDICT_REJECT
        assert outcome.counted_as_success is True

        detection = abl.detect_full_candidate(case["events"])
        assert detection.decision == cand.DETECT
        assert detection.reason == cand.RC_CAMPAIGN_STRUCTURE_DETECTED
        assert detection.score >= cand.DEFAULT_PARAMS.detect_threshold

    def test_removing_campaign_linkage_misses_low_and_slow(self) -> None:
        """Core P04 test: without campaign linkage, low-and-slow is missed."""
        case = abl.fixture_low_and_slow_cross_tool()

        # Full candidate catches it
        full_outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case)
        assert full_outcome.observed_outcome == abl.VERDICT_REJECT

        # Without campaign linkage misses it
        abl_outcome = abl.run_ablation(abl.VARIANT_WITHOUT_CAMPAIGN_LINKAGE, case)
        assert abl_outcome.observed_outcome == abl.VERDICT_ADMIT
        assert abl_outcome.counted_as_success is True

        det = abl.detect_without_campaign_linkage(case["events"])
        assert det.decision == cand.NO_DETECT
        assert det.reason == cand.RC_NO_ALARM

    def test_removing_cross_tool_feature_misses_low_and_slow(self) -> None:
        case = abl.fixture_low_and_slow_cross_tool()
        outcome = abl.run_ablation(abl.VARIANT_WITHOUT_CROSS_TOOL_FEATURE, case)
        assert outcome.observed_outcome == abl.VERDICT_ADMIT
        assert outcome.counted_as_success is True

        det = abl.detect_without_cross_tool_feature(case["events"])
        assert det.decision == cand.NO_DETECT

    def test_removing_pacing_feature_misses_low_and_slow(self) -> None:
        case = abl.fixture_low_and_slow_cross_tool()
        outcome = abl.run_ablation(abl.VARIANT_WITHOUT_PACING_FEATURE, case)
        assert outcome.observed_outcome == abl.VERDICT_ADMIT
        assert outcome.counted_as_success is True

        det = abl.detect_without_pacing_feature(case["events"])
        assert det.decision == cand.NO_DETECT

    def test_per_window_counts_misses_low_and_slow_and_false_alarms_on_burst(
        self,
    ) -> None:
        # Misses low and slow
        case_attack = abl.fixture_low_and_slow_cross_tool()
        outcome_attack = abl.run_ablation(abl.VARIANT_WITH_ONLY_PER_WINDOW_COUNTS, case_attack)
        assert outcome_attack.observed_outcome == abl.VERDICT_ADMIT

        # False-alarms on benign burst
        case_burst = abl.fixture_benign_burst()
        outcome_burst = abl.run_ablation(abl.VARIANT_WITH_ONLY_PER_WINDOW_COUNTS, case_burst)
        assert outcome_burst.observed_outcome == abl.VERDICT_REJECT
        assert abl.RC_WINDOW_COUNT_THRESHOLD_REACHED in outcome_burst.detail

        # Full candidate admits benign burst
        full_burst = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case_burst)
        assert full_burst.observed_outcome == abl.VERDICT_ADMIT

    def test_benign_controls_admitted_by_all_variants(self) -> None:
        for variant_id in abl.ABLATION_REGISTRY:
            retry_res = abl.run_ablation(variant_id, abl.fixture_benign_retry())
            assert retry_res.observed_outcome == abl.VERDICT_ADMIT

            handoff_res = abl.run_ablation(variant_id, abl.fixture_benign_handoff())
            assert handoff_res.observed_outcome == abl.VERDICT_ADMIT


class TestMechanisticInferenceMatrix:
    def test_verify_mechanistic_inference_matrix_all_cells_match(self) -> None:
        report = abl.verify_mechanistic_inference_matrix()
        assert report["all_cells_match"] is True
        assert report["cell_count"] == len(abl.ABLATION_REGISTRY) * len(abl.FAULT_FAMILY_IDS)
        for cell in report["cells"]:
            assert cell["match"] is True
            assert cell["predicted"] == cell["observed"]

    def test_mechanistic_inference_matrix_structure(self) -> None:
        matrix = abl.mechanistic_inference_matrix()
        assert matrix["ablations_version"] == abl.ABLATIONS_VERSION
        assert matrix["reference_variant"] == abl.REFERENCE_VARIANT_ID
        assert set(matrix["fault_families"]) == set(abl.FAULT_FAMILY_IDS)
        assert set(matrix["variants"]) == set(abl.ABLATION_REGISTRY)
        assert "degradation_axes" in matrix
        # Check that reference variant is not degraded vs itself
        assert matrix["degradation_axes"][abl.REFERENCE_VARIANT_ID]["measurably_degraded"] is False
        # Check that ablations are measurably degraded
        for vid in (
            abl.VARIANT_WITHOUT_CAMPAIGN_LINKAGE,
            abl.VARIANT_WITHOUT_CROSS_TOOL_FEATURE,
            abl.VARIANT_WITHOUT_PACING_FEATURE,
            abl.VARIANT_WITH_ONLY_PER_WINDOW_COUNTS,
        ):
            assert matrix["degradation_axes"][vid]["measurably_degraded"] is True

    def test_describe_ablations_design_record(self) -> None:
        desc = abl.describe_ablations()
        assert desc["ablations_version"] == abl.ABLATIONS_VERSION
        assert desc["task_id"] == abl.ABLATION_TASK_ID
        assert desc["candidate_id"] == cand.CANDIDATE_ID
        assert desc["reference_variant"] == abl.REFERENCE_VARIANT_ID
        assert set(desc["registry"]) == set(abl.ABLATION_REGISTRY)
        assert abl.RC_UNKNOWN_ABLATION_VARIANT in desc["refusal_codes"]
        assert abl.RC_VARIANT_REMOVES_NOTHING in desc["refusal_codes"]

    def test_determinism_repeated_executions_identical(self) -> None:
        rep1 = abl.verify_mechanistic_inference_matrix()
        rep2 = abl.verify_mechanistic_inference_matrix()
        assert rep1 == rep2


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


class TestAdversarialRefusals:
    @pytest.mark.parametrize(
        "bogus",
        [
            "unregistered_arm",
            "foo_bar",
            "without_everything",
            "full_candidate_v2",
            "",
            "UNKNOWN",
        ],
    )
    def test_unregistered_variant_refused_by_guard(self, bogus: str) -> None:
        with pytest.raises(abl.AblationError) as excinfo:
            abl.refuse_unregistered_variant(bogus)
        assert excinfo.value.reason_code == abl.RC_UNKNOWN_ABLATION_VARIANT

    @pytest.mark.parametrize("bogus", ["unregistered_arm", "fake_variant", ""])
    def test_unregistered_variant_refused_by_run_ablation(self, bogus: str) -> None:
        case = abl.fixture_low_and_slow_cross_tool()
        outcome = abl.run_ablation(bogus, case)
        assert outcome.observed_outcome == abl.VERDICT_EXECUTION_ERROR
        assert outcome.counted_as_success is False
        assert abl.RC_UNKNOWN_ABLATION_VARIANT in outcome.detail

    @pytest.mark.parametrize(
        "identity",
        [
            cand.CANDIDATE_ID,
            "DIMVA-candidate",
            "candidate",
            "unablated_candidate",
            "none",
            "removes_nothing",
        ],
    )
    def test_nothing_removing_identity_refused_by_guard(self, identity: str) -> None:
        with pytest.raises(abl.AblationError) as excinfo:
            abl.refuse_unregistered_variant(identity)
        assert excinfo.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING

    @pytest.mark.parametrize(
        "identity",
        [
            cand.CANDIDATE_ID,
            "DIMVA-candidate",
            "candidate",
        ],
    )
    def test_nothing_removing_identity_refused_by_run_ablation(self, identity: str) -> None:
        case = abl.fixture_low_and_slow_cross_tool()
        outcome = abl.run_ablation(identity, case)
        assert outcome.observed_outcome == abl.VERDICT_EXECUTION_ERROR
        assert outcome.counted_as_success is False
        assert abl.RC_VARIANT_REMOVES_NOTHING in outcome.detail

    def test_spec_declaring_no_mechanism_refused_at_construction(self) -> None:
        with pytest.raises(abl.AblationError) as excinfo:
            abl.VariantSpec(
                variant_id="empty_mechanism",
                title="Invalid Empty Mechanism",
                ablated_mechanism="",
                description="test",
                expected_effect="test",
                reuses=(),
                applied_by="test",
            )
        assert excinfo.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING

        with pytest.raises(abl.AblationError) as excinfo:
            abl.VariantSpec(
                variant_id="impostor_none",
                title="Impostor Reference Row",
                ablated_mechanism="none",
                description="test",
                expected_effect="test",
                reuses=(),
                applied_by="test",
            )
        assert excinfo.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING


class TestAdversarialMalformedInputs:
    def test_malformed_case_not_a_mapping(self) -> None:
        outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, "not_a_mapping")  # type: ignore[arg-type]
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == abl.RC_MALFORMED_CASE

    def test_case_missing_events_field(self) -> None:
        outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"case_id": "C-1"})
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == abl.RC_CASE_EVENTS_MISSING

    def test_case_events_not_a_list(self) -> None:
        outcome = abl.run_ablation(
            abl.VARIANT_FULL_CANDIDATE, {"case_id": "C-1", "events": "not_a_list"}
        )
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == abl.RC_CASE_EVENTS_NOT_A_LIST

    def test_empty_events_list(self) -> None:
        outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"case_id": "C-1", "events": []})
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == cand.RC_EVENT_SEQUENCE_EMPTY

    def test_reason_code_leak_rejected_fail_closed(self) -> None:
        event_with_leak = {
            "actor_id": "a",
            "tool": "t",
            "scope": "s",
            "allowed": False,
            "ts": 100,
            "reason_code": "LEAKED_SECRET",
        }
        outcome = abl.run_ablation(
            abl.VARIANT_FULL_CANDIDATE,
            {"case_id": "C-1", "events": [event_with_leak]},
        )
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == cand.RC_EVENT_REASON_CODE_FORBIDDEN

    def test_non_monotonic_ts_rejected(self) -> None:
        events = [
            {"actor_id": "a", "tool": "t", "scope": "s", "allowed": True, "ts": 200},
            {"actor_id": "a", "tool": "t", "scope": "s", "allowed": True, "ts": 100},
        ]
        outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"case_id": "C-1", "events": events})
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == cand.RC_EVENT_TS_NOT_MONOTONIC

    def test_mixed_actors_in_session_rejected(self) -> None:
        events = [
            {"actor_id": "actor-1", "tool": "t", "scope": "s", "allowed": True, "ts": 100},
            {"actor_id": "actor-2", "tool": "t", "scope": "s", "allowed": True, "ts": 200},
        ]
        outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"case_id": "C-1", "events": events})
        assert outcome.observed_outcome == abl.VERDICT_INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == cand.RC_SESSION_MIXED_ACTORS
