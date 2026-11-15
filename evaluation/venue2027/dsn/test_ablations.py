"""Tests for DSN-ablation — causal mechanism ablation variants (phase P04).

Positive controls:
- Registry declarations: every registered variant declares exactly ONE ablated
  mechanism axis, title, description, expected failure window, expected effect,
  and reuses candidate/baseline components.
- run_ablation execution: every registered variant runs through the task-manifest
  signature run_ablation(name, case) -> Outcome and returns an Outcome.
- Causal mechanism isolation:
  * without_journal (no recovery): after a post-commit crash, outcome is unadjudicable
    (lost recovery/effect) and broker replays apply duplicate effects.
  * without_idempotency_key: broker replays and post-crash retries apply duplicate effects.
  * without_wal_pre_write: mid_effect crash uniquely causes duplicate effect on recovery.
  * common_safety_gate: correctly aborts consent revocation, but fails crash recovery.
  * full_fat_baseline: survives normal crash recovery and dedups replays, but fails
    mid_effect crash and fails to detect corrupted journals.
- Mechanistic inference matrix: verify_mechanistic_inference_matrix executes all 48 cells
  (6 variants/reference x 8 windows) and verifies all_cells_match is True.
- Single-factor isolation: each ablation causes failure ONLY on its expected mechanisms/windows.

Adversarial controls (fail closed):
- refuse_unregistered_variant refuses unknown variant IDs with UNKNOWN_ABLATION_VARIANT.
- refuse_unregistered_variant refuses nothing-removing identities (full_candidate, candidate ID)
  with VARIANT_REMOVES_NOTHING.
- VariantSpec refuses empty/blank ablated_mechanism.
- Malformed cases (non-mapping, missing fields, unknown fields, bad types, malformed schedules)
  return Outcome("EXECUTION_ERROR") with stable reason codes.
- Determinism: repeating runs yields byte-identical results.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dsn import ablations as abl
from evaluation.venue2027.dsn import candidate as cand


@pytest.fixture(scope="module")
def matrix_result() -> dict[str, object]:
    return abl.verify_mechanistic_inference_matrix()


# ---------------------------------------------------------------------------
# Registry Shape & Declarations
# ---------------------------------------------------------------------------


def test_registry_variants_registered() -> None:
    expected = {
        abl.VARIANT_WITHOUT_JOURNAL,
        abl.VARIANT_WITHOUT_IDEMPOTENCY_KEY,
        abl.VARIANT_WITHOUT_WAL_PRE_WRITE,
        abl.VARIANT_COMMON_SAFETY_GATE,
        abl.VARIANT_FULL_FAT_BASELINE,
    }
    assert set(abl.ABLATION_REGISTRY.keys()) == expected
    assert set(abl.variant_ids()) == expected


def test_registry_every_variant_declares_exactly_one_mechanism() -> None:
    mechanisms = set()
    for vid, spec in abl.ABLATION_REGISTRY.items():
        assert isinstance(spec.ablated_mechanism, str)
        assert len(spec.ablated_mechanism.strip()) > 0
        assert spec.ablated_mechanism not in mechanisms
        mechanisms.add(spec.ablated_mechanism)
        assert len(spec.reuses) > 0
        assert len(spec.expected_failure_window) > 0
        assert len(spec.expected_effect) > 0
        spec_dict = spec.to_dict()
        assert spec_dict["variant_id"] == vid


def test_describe_ablations_smoke() -> None:
    desc = abl.describe_ablations()
    assert desc["task_id"] == abl.ABLATION_TASK_ID
    assert desc["version"] == abl.ABLATIONS_VERSION
    assert len(desc["registered_variants"]) == 5
    assert len(desc["guarantees"]) >= 5


# ---------------------------------------------------------------------------
# Adversarial: Unregistered & Nothing-Removing Refusals
# ---------------------------------------------------------------------------


def test_refuse_unregistered_variant_unknown() -> None:
    with pytest.raises(abl.AblationError) as exc:
        abl.refuse_unregistered_variant("warp_speed_variant")
    assert exc.value.reason_code == abl.RC_UNKNOWN_ABLATION_VARIANT

    # Via run_ablation
    outcome = abl.run_ablation(
        "warp_speed_variant", {"case_id": "c1", "operation_id": "op1", "delivery_schedule": [1]}
    )
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert abl.RC_UNKNOWN_ABLATION_VARIANT in outcome.detail


def test_refuse_unregistered_variant_removes_nothing() -> None:
    for identity in (
        abl.REFERENCE_VARIANT_ID,
        cand.CANDIDATE_ID,
        "candidate",
        "full_fat_candidate",
    ):
        with pytest.raises(abl.AblationError) as exc:
            abl.refuse_unregistered_variant(identity)
        assert exc.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING

        outcome = abl.run_ablation(
            identity, {"case_id": "c1", "operation_id": "op1", "delivery_schedule": [1]}
        )
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert abl.RC_VARIANT_REMOVES_NOTHING in outcome.detail


def test_variant_spec_refuses_empty_mechanism() -> None:
    with pytest.raises(abl.AblationError) as exc:
        abl.VariantSpec(
            variant_id="bad_spec",
            title="bad",
            ablated_mechanism="",
            description="none",
            expected_failure_window="none",
            expected_effect="none",
            reuses=("candidate",),
            applied_by="harness",
            runner=lambda case: Outcome("ADMIT"),
        )
    assert exc.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING


# ---------------------------------------------------------------------------
# Adversarial: Malformed Cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_case, expected_code",
    [
        ("not_a_dict", abl.RC_CASE_NOT_AN_OBJECT),
        ({}, abl.RC_CASE_MISSING_FIELD),
        ({"case_id": "c1"}, abl.RC_CASE_MISSING_FIELD),
        ({"case_id": "c1", "operation_id": "op1"}, abl.RC_CASE_MISSING_FIELD),
        (
            {"case_id": "c1", "operation_id": "op1", "delivery_schedule": [1], "extra_key": True},
            abl.RC_CASE_UNKNOWN_FIELD,
        ),
        ({"case_id": "", "operation_id": "op1", "delivery_schedule": [1]}, abl.RC_CASE_BAD_FIELD),
        ({"case_id": "c1", "operation_id": "", "delivery_schedule": [1]}, abl.RC_CASE_BAD_FIELD),
        (
            {"case_id": "c1", "operation_id": "op1", "delivery_schedule": "not_a_list"},
            abl.RC_CASE_BAD_FIELD,
        ),
        ({"case_id": "c1", "operation_id": "op1", "delivery_schedule": [0]}, abl.RC_CASE_BAD_FIELD),
        (
            {
                "case_id": "c1",
                "operation_id": "op1",
                "delivery_schedule": [1],
                "authorized_consent_epoch": -1,
            },
            abl.RC_CASE_BAD_FIELD,
        ),
        (
            {
                "case_id": "c1",
                "operation_id": "op1",
                "delivery_schedule": [1],
                "crash_point": "bad_crash",
            },
            abl.RC_CASE_BAD_FIELD,
        ),
    ],
)
def test_run_ablation_malformed_case(bad_case: object, expected_code: str) -> None:
    outcome = abl.run_ablation(abl.VARIANT_WITHOUT_JOURNAL, bad_case)  # type: ignore[arg-type]
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert expected_code in outcome.detail


# ---------------------------------------------------------------------------
# Positive: Demonstrated Failure Modes for Each Ablation
# ---------------------------------------------------------------------------


def test_ablation_without_journal_demonstrated_loss_and_duplicates() -> None:
    # 1. Post-commit crash causes lost recovery / unadjudicable outcome:
    crashed_case = abl.make_window_case(cand.CRASH_POST_COMMIT_PRE_RESPONSE)
    crashed_outcome = abl.run_ablation(abl.VARIANT_WITHOUT_JOURNAL, crashed_case)
    assert crashed_outcome.observed_outcome == "INDETERMINATE"
    assert crashed_outcome.counted_as_success is False
    assert abl.RC_LOST_EFFECT in crashed_outcome.detail

    # 2. Broker replay causes demonstrated duplicate effects:
    replay_case = abl.make_window_case(abl.WINDOW_BROKER_REPLAY)
    replay_outcome = abl.run_ablation(abl.VARIANT_WITHOUT_JOURNAL, replay_case)
    assert replay_outcome.observed_outcome == "ADMIT"
    assert replay_outcome.counted_as_success is False
    assert abl.RC_DUPLICATE_EFFECT in replay_outcome.detail


def test_ablation_without_idempotency_key_demonstrated_duplicate_effects() -> None:
    # Broker replay causes duplicate effects:
    case = abl.make_window_case(abl.WINDOW_BROKER_REPLAY)
    outcome = abl.run_ablation(abl.VARIANT_WITHOUT_IDEMPOTENCY_KEY, case)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is False
    assert abl.RC_DUPLICATE_EFFECT in outcome.detail
    detail = json.loads(outcome.detail)
    assert detail["effect_applications"] == 3


def test_ablation_without_wal_demonstrated_duplicate_effect_on_mid_effect_crash() -> None:
    # Crash at mid_effect causes duplicate effect on recovery:
    case = abl.make_window_case(cand.CRASH_MID_EFFECT)
    outcome = abl.run_ablation(abl.VARIANT_WITHOUT_WAL_PRE_WRITE, case)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is False
    assert abl.RC_WAL_LOST in outcome.detail
    detail = json.loads(outcome.detail)
    assert detail["effect_applications"] >= 2


def test_ablation_common_safety_gate_passes_revocation_fails_recovery() -> None:
    # Consent revocation is caught:
    revoked_case = abl.make_window_case(abl.WINDOW_CONSENT_REVOKED)
    revoked_outcome = abl.run_ablation(abl.VARIANT_COMMON_SAFETY_GATE, revoked_case)
    assert revoked_outcome.observed_outcome == "REJECT"
    assert revoked_outcome.counted_as_success is True

    # Crash recovery fails:
    crashed_case = abl.make_window_case(cand.CRASH_POST_COMMIT_PRE_RESPONSE)
    crashed_outcome = abl.run_ablation(abl.VARIANT_COMMON_SAFETY_GATE, crashed_case)
    assert crashed_outcome.observed_outcome == "INDETERMINATE"
    assert crashed_outcome.counted_as_success is False


def test_ablation_full_fat_baseline_fails_tampering_and_mid_effect() -> None:
    # Mid-effect crash fails (no WAL):
    mid_case = abl.make_window_case(cand.CRASH_MID_EFFECT)
    mid_outcome = abl.run_ablation(abl.VARIANT_FULL_FAT_BASELINE, mid_case)
    assert mid_outcome.counted_as_success is False

    # Tampered journal is not detected:
    tamper_case = abl.make_window_case(abl.WINDOW_CORRUPT_JOURNAL)
    tamper_outcome = abl.run_ablation(abl.VARIANT_FULL_FAT_BASELINE, tamper_case)
    assert tamper_outcome.counted_as_success is False
    assert abl.RC_TAMPERING_NOT_DETECTED in tamper_outcome.detail


# ---------------------------------------------------------------------------
# Mechanistic Inference Matrix Verification
# ---------------------------------------------------------------------------


def test_mechanistic_inference_matrix_shape() -> None:
    matrix = abl.mechanistic_inference_matrix()
    assert matrix["ablations_version"] == abl.ABLATIONS_VERSION
    assert matrix["reference_variant"] == abl.REFERENCE_VARIANT_ID
    assert set(matrix["crash_windows"]) == set(abl.MATRIX_WINDOWS)
    assert set(matrix["variants"].keys()) == set(abl.ABLATION_REGISTRY.keys())
    # 6 rows (reference + 5 variants) x 8 windows = 48 cells:
    predicted = matrix["predicted_verdicts"]
    assert len(predicted) == 6
    for v in predicted.values():
        assert len(v) == 8


def test_verify_mechanistic_inference_matrix_all_cells_match(
    matrix_result: dict[str, object],
) -> None:
    assert matrix_result["all_cells_match"] is True
    assert matrix_result["total_cells"] == 48
    assert matrix_result["matching_cells"] == 48


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_determinism() -> None:
    for vid in abl.variant_ids():
        case = abl.make_window_case(abl.WINDOW_MID_EFFECT, case_id=f"det-{vid}")
        out1 = abl.run_ablation(vid, case)
        out2 = abl.run_ablation(vid, case)
        assert out1.observed_outcome == out2.observed_outcome
        assert out1.counted_as_success == out2.counted_as_success
        assert out1.retriable == out2.retriable
        assert out1.detail == out2.detail
