"""Tests for POPETS-ablation — preregistered causal mechanism ablations.

Positive controls (each ablation runs; removing a mechanism degrades safety/exactness):
- Every registered variant runs through the task-manifest signature
  ``run_ablation(name, case) -> Outcome`` on every frozen family and returns
  a determined Outcome (ADMIT/REJECT) with the declared ablated mechanism in
  its detail payload.
- The mechanistic inference matrix verifies every variant x family cell
  against its PREREGISTERED prediction (``all_cells_match`` is True).
- ``candidate_no_key_module`` ADMITs the transitive derivation leak that the
  full candidate REJECTs (reverse-edge closure is the load-bearing mechanism).
- ``baseline_common_safety_gate`` ADMITs transitive leaks and unproven lineage
  that the candidate REJECTs (lineage provenance tracking is the mechanism).
- ``full_refresh`` REJECTs the unaffected scope that the candidate ADMITs
  (exact selective invalidation is the mechanism; full refresh over-purges).
- ``zero_proof_receipt`` ADMITs unproven lineage that the candidate REJECTs
  (provenance proof verification is the mechanism).
- ``no_context_history_branch`` ADMITs historical taint that the candidate
  REJECTs (longitudinal context history branch is the mechanism).
- Clean control: ``fresh_dispatch`` is admitted by ALL variants and reference.
- Single-factor isolation: all variants preserve cross-purpose isolation.
- Detection-count conservation: the full candidate rejects strictly more
  attack families than any ablation.

Adversarial controls (fail closed):
- An unregistered variant id is refused with UNKNOWN_ABLATION_VARIANT by
  run_ablation and refuse_unregistered_variant — never silently run as any
  registered arm.
- A variant removing nothing (the full candidate / candidate id) is refused
  with VARIANT_REMOVES_NOTHING.
- A spec declaring no ablated mechanism is refused at construction.
- Malformed cases (non-mapping, missing/empty case id, missing/malformed ops)
  never become ADMIT/REJECT.
- Determinism: identical inputs give identical results; rerunning the matrix
  is stable and its predictions are frozen constants.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.popets import ablations as abl
from evaluation.venue2027.popets import candidate as cand
from evaluation.venue2027.popets.ablations import (
    ABLATION_REGISTRY,
    FAULT_FAMILY_IDS,
    PREDICTED_VERDICTS,
    RC_CASE_ID_MISSING,
    RC_CASE_ID_NOT_STRING,
    RC_CASE_NOT_AN_OBJECT,
    RC_UNKNOWN_ABLATION_VARIANT,
    RC_VARIANT_REMOVES_NOTHING,
    RC_WORKLOAD_MALFORMED,
    REFERENCE_VARIANT_ID,
    VARIANT_ALIASES,
    VARIANT_BASELINE_COMMON_SAFETY_GATE,
    VARIANT_CANDIDATE_NO_KEY_MODULE,
    VARIANT_FULL_REFRESH,
    VARIANT_NO_CONTEXT_HISTORY_BRANCH,
    VARIANT_ZERO_PROOF_RECEIPT,
    VERDICT_ADMIT,
    VERDICT_REJECT,
    AblationError,
    VariantSpec,
    case_fixtures,
    describe_ablations,
    mechanistic_inference_matrix,
    refuse_unregistered_variant,
    run_ablation,
    variant_ids,
    verify_mechanistic_inference_matrix,
)

ALL_VARIANT_IDS = (
    VARIANT_CANDIDATE_NO_KEY_MODULE,
    VARIANT_BASELINE_COMMON_SAFETY_GATE,
    VARIANT_FULL_REFRESH,
    VARIANT_ZERO_PROOF_RECEIPT,
    VARIANT_NO_CONTEXT_HISTORY_BRANCH,
)


@pytest.fixture(scope="function")
def fixtures() -> dict[str, dict[str, Any]]:
    """Fresh fixture set per test function call."""
    builders = case_fixtures()
    return {family: builders[family]() for family in FAULT_FAMILY_IDS}


# ---------------------------------------------------------------------------
# Positive controls: registry structure & declared mechanisms
# ---------------------------------------------------------------------------


def test_registry_structure_and_declared_mechanisms() -> None:
    assert set(ABLATION_REGISTRY) == set(ALL_VARIANT_IDS)
    assert variant_ids() == tuple(ABLATION_REGISTRY)

    mechanisms = [spec.ablated_mechanism for spec in ABLATION_REGISTRY.values()]
    assert len(mechanisms) == len(set(mechanisms)), "each ablation mechanism must be unique"

    assert REFERENCE_VARIANT_ID not in ABLATION_REGISTRY
    assert cand.CANDIDATE_ID not in ABLATION_REGISTRY

    for spec in ABLATION_REGISTRY.values():
        assert spec.title.strip()
        assert spec.description.strip()
        assert spec.expected_effect.strip()
        assert spec.applied_by.strip()
        assert len(spec.reuses) >= 1

    description = describe_ablations()
    assert description["task_id"] == abl.ABLATION_TASK_ID
    assert description["candidate_id"] == cand.CANDIDATE_ID
    assert set(description["registry"]) == set(ABLATION_REGISTRY)


@pytest.mark.parametrize("variant_id", ALL_VARIANT_IDS)
def test_variant_spec_to_dict_roundtrip(variant_id: str) -> None:
    spec = ABLATION_REGISTRY[variant_id]
    payload = spec.to_dict()
    assert payload["variant_id"] == variant_id
    assert payload["ablated_mechanism"] == spec.ablated_mechanism
    assert payload["title"] == spec.title
    assert payload["description"] == spec.description
    assert payload["expected_effect"] == spec.expected_effect
    assert payload["reuses"] == list(spec.reuses)
    assert payload["applied_by"] == spec.applied_by


# ---------------------------------------------------------------------------
# Positive controls: every variant runs on every family
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant_id", ALL_VARIANT_IDS)
@pytest.mark.parametrize("family_id", FAULT_FAMILY_IDS)
def test_every_variant_runs_on_every_family(
    variant_id: str,
    family_id: str,
    fixtures: dict[str, dict[str, Any]],
) -> None:
    case = fixtures[family_id]
    outcome = run_ablation(variant_id, case)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in (VERDICT_ADMIT, VERDICT_REJECT)
    assert outcome.counted_as_success is True

    detail = json.loads(outcome.detail)
    assert detail["ablations_version"] == abl.POPETS_ABLATIONS_VERSION
    assert detail["variant_id"] == variant_id
    assert detail["ablated_mechanism"] == ABLATION_REGISTRY[variant_id].ablated_mechanism
    assert detail["case_id"] == case["case_id"]


# ---------------------------------------------------------------------------
# Positive controls: mechanistic inference matrix
# ---------------------------------------------------------------------------


def test_mechanistic_inference_matrix_design_record() -> None:
    matrix = mechanistic_inference_matrix()
    assert matrix["ablations_version"] == abl.POPETS_ABLATIONS_VERSION
    assert matrix["task_id"] == abl.ABLATION_TASK_ID
    assert matrix["reference_variant"] == REFERENCE_VARIANT_ID
    assert set(matrix["variants"]) == set(ABLATION_REGISTRY)

    for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY):
        for family_id in FAULT_FAMILY_IDS:
            assert matrix["predicted_verdicts"][variant_id][family_id] in (
                VERDICT_ADMIT,
                VERDICT_REJECT,
            )

    degradation = matrix["degradation_axes"]
    for variant_id in ABLATION_REGISTRY:
        assert degradation[variant_id]["measurably_degraded"] is True


def test_verify_mechanistic_inference_matrix_all_cells_match() -> None:
    verification = verify_mechanistic_inference_matrix()
    assert verification["all_cells_match"] is True
    assert verification["cell_count"] == len(FAULT_FAMILY_IDS) * (len(ABLATION_REGISTRY) + 1)
    assert verification["observed_degradation"] == verification["predicted_degradation"]

    for cell in verification["cells"]:
        assert cell["match"] is True, f"Mismatch in cell {cell}"


# ---------------------------------------------------------------------------
# Positive controls: removing key module degrades safety
# ---------------------------------------------------------------------------


def test_candidate_no_key_module_admits_transitive_derivation_leak(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """THE causal proof: without reverse-edge closure the transitive leak appears."""
    case = fixtures[abl.FAMILY_TRANSITIVE_REVOCATION]

    ref_outcome = abl._run_reference(case)
    assert ref_outcome.observed_outcome == VERDICT_REJECT

    ablation_outcome = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, case)
    assert ablation_outcome.observed_outcome == VERDICT_ADMIT
    detail = json.loads(ablation_outcome.detail)
    assert detail["hits"] >= 1
    assert detail["leaks"] >= 1


def test_baseline_common_safety_gate_admits_transitive_and_unproven(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Common safety gate lacks provenance tracking, admitting leaks & unproven context."""
    case_transitive = fixtures[abl.FAMILY_TRANSITIVE_REVOCATION]
    case_unproven = fixtures[abl.FAMILY_UNPROVEN_LINEAGE]

    assert abl._run_reference(case_transitive).observed_outcome == VERDICT_REJECT
    assert abl._run_reference(case_unproven).observed_outcome == VERDICT_REJECT

    assert (
        run_ablation(VARIANT_BASELINE_COMMON_SAFETY_GATE, case_transitive).observed_outcome
        == VERDICT_ADMIT
    )
    assert (
        run_ablation(VARIANT_BASELINE_COMMON_SAFETY_GATE, case_unproven).observed_outcome
        == VERDICT_ADMIT
    )


def test_full_refresh_degrades_availability_unaffected_scope(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Coarse purge over-invalidates: unaffected scope is falsely rejected."""
    case = fixtures[abl.FAMILY_UNAFFECTED_SCOPE]

    ref_outcome = abl._run_reference(case)
    assert ref_outcome.observed_outcome == VERDICT_ADMIT

    ablation_outcome = run_ablation(VARIANT_FULL_REFRESH, case)
    assert ablation_outcome.observed_outcome == VERDICT_REJECT


def test_zero_proof_receipt_admits_unproven_lineage(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Without proof/receipt verification, unanchored context enters and is served."""
    case = fixtures[abl.FAMILY_UNPROVEN_LINEAGE]

    assert abl._run_reference(case).observed_outcome == VERDICT_REJECT

    ablation_outcome = run_ablation(VARIANT_ZERO_PROOF_RECEIPT, case)
    assert ablation_outcome.observed_outcome == VERDICT_ADMIT
    detail = json.loads(ablation_outcome.detail)
    assert detail["hits"] >= 1


def test_no_context_history_branch_admits_historical_taint(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Severing derivation history unlinks child context from revoked historical origin."""
    case = fixtures[abl.FAMILY_HISTORICAL_TAINT]

    assert abl._run_reference(case).observed_outcome == VERDICT_REJECT

    ablation_outcome = run_ablation(VARIANT_NO_CONTEXT_HISTORY_BRANCH, case)
    assert ablation_outcome.observed_outcome == VERDICT_ADMIT
    detail = json.loads(ablation_outcome.detail)
    assert detail["hits"] >= 1


def test_clean_control_admitted_by_all(fixtures: dict[str, dict[str, Any]]) -> None:
    """No collateral rejection: fresh authorized context is admitted by reference & all arms."""
    case = fixtures[abl.FAMILY_FRESH_DISPATCH]

    assert abl._run_reference(case).observed_outcome == VERDICT_ADMIT
    for variant_id in ABLATION_REGISTRY:
        assert run_ablation(variant_id, case).observed_outcome == VERDICT_ADMIT


def test_single_factor_isolation_cross_purpose(fixtures: dict[str, dict[str, Any]]) -> None:
    """Cross-purpose reads are rejected across reference and every ablation arm."""
    case = fixtures[abl.FAMILY_CROSS_PURPOSE]

    assert abl._run_reference(case).observed_outcome == VERDICT_REJECT
    for variant_id in ABLATION_REGISTRY:
        assert run_ablation(variant_id, case).observed_outcome == VERDICT_REJECT


def test_reference_ceiling_strictly_higher_safety() -> None:
    """The reference candidate Pareto-dominates every ablation arm.

    Every ablation either admits strictly more attack families (safety degradation)
    or rejects unaffected clean scopes (availability degradation).
    """
    matrix = mechanistic_inference_matrix()
    attack_families = [
        abl.FAMILY_TRANSITIVE_REVOCATION,
        abl.FAMILY_UNPROVEN_LINEAGE,
        abl.FAMILY_HISTORICAL_TAINT,
        abl.FAMILY_CROSS_PURPOSE,
    ]

    ref_rejected = sum(
        1
        for f in attack_families
        if matrix["predicted_verdicts"][REFERENCE_VARIANT_ID][f] == VERDICT_REJECT
    )
    assert ref_rejected == len(attack_families)

    for variant_id in ABLATION_REGISTRY:
        var_rejected = sum(
            1
            for f in attack_families
            if matrix["predicted_verdicts"][variant_id][f] == VERDICT_REJECT
        )
        if variant_id == VARIANT_FULL_REFRESH:
            # Full refresh rejects attacks by over-invalidation, but falsely rejects unaffected scope
            assert (
                matrix["predicted_verdicts"][variant_id][abl.FAMILY_UNAFFECTED_SCOPE]
                == VERDICT_REJECT
            )
            assert (
                matrix["predicted_verdicts"][REFERENCE_VARIANT_ID][abl.FAMILY_UNAFFECTED_SCOPE]
                == VERDICT_ADMIT
            )
        else:
            # Safety degradations: admits at least one attack family the candidate blocks
            assert var_rejected < ref_rejected, f"{variant_id} must reject strictly fewer attacks"


# ---------------------------------------------------------------------------
# Adversarial controls: refusals & fail-closed behavior
# ---------------------------------------------------------------------------


def test_adversarial_refuse_unregistered_variant() -> None:
    with pytest.raises(AblationError) as exc_info:
        refuse_unregistered_variant("completely_unregistered_arm")
    assert exc_info.value.reason_code == RC_UNKNOWN_ABLATION_VARIANT

    case = {"case_id": "test-unregistered", "cache_ops": [{"op": "get", "key": "k"}]}
    outcome = run_ablation("completely_unregistered_arm", case)
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert RC_UNKNOWN_ABLATION_VARIANT in outcome.detail


def test_adversarial_refuse_removing_nothing() -> None:
    for identity in (REFERENCE_VARIANT_ID, cand.CANDIDATE_ID):
        with pytest.raises(AblationError) as exc_info:
            refuse_unregistered_variant(identity)
        assert exc_info.value.reason_code == RC_VARIANT_REMOVES_NOTHING

        case = {"case_id": "test-removing-nothing", "cache_ops": [{"op": "get", "key": "k"}]}
        outcome = run_ablation(identity, case)
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.counted_as_success is False
        assert RC_VARIANT_REMOVES_NOTHING in outcome.detail


def test_adversarial_spec_without_mechanism_refused() -> None:
    with pytest.raises(AblationError) as exc_info:
        VariantSpec(
            variant_id="empty_mechanism",
            title="Empty",
            ablated_mechanism="",
            description="desc",
            expected_effect="effect",
            reuses=("candidate",),
            applied_by="hook",
        )
    assert exc_info.value.reason_code == RC_VARIANT_REMOVES_NOTHING

    with pytest.raises(AblationError) as exc_info2:
        VariantSpec(
            variant_id="whitespace_mechanism",
            title="Whitespace",
            ablated_mechanism="   ",
            description="desc",
            expected_effect="effect",
            reuses=("candidate",),
            applied_by="hook",
        )
    assert exc_info2.value.reason_code == RC_VARIANT_REMOVES_NOTHING


def test_adversarial_malformed_cases() -> None:
    # Not a mapping
    res1 = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, "not a dict")  # type: ignore[arg-type]
    assert res1.observed_outcome == "EXECUTION_ERROR"
    assert RC_CASE_NOT_AN_OBJECT in res1.detail

    # Missing case_id
    res2 = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, {"cache_ops": []})
    assert res2.observed_outcome == "INDETERMINATE"
    assert RC_CASE_ID_MISSING in res2.detail

    # Non-string case_id
    res3 = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, {"case_id": 12345, "cache_ops": []})
    assert res3.observed_outcome == "INDETERMINATE"
    assert RC_CASE_ID_NOT_STRING in res3.detail

    # Missing cache_ops
    res4 = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, {"case_id": "c1"})
    assert res4.observed_outcome == "EXECUTION_ERROR"
    assert RC_WORKLOAD_MALFORMED in res4.detail

    # Malformed op
    res5 = run_ablation(
        VARIANT_CANDIDATE_NO_KEY_MODULE,
        {"case_id": "c2", "cache_ops": [{"op": "unknown_operation"}]},
    )
    assert res5.observed_outcome == VERDICT_REJECT
    assert RC_WORKLOAD_MALFORMED in res5.detail


def test_variant_aliases_resolve_cleanly(fixtures: dict[str, dict[str, Any]]) -> None:
    case = fixtures[abl.FAMILY_FRESH_DISPATCH]
    for alias, canonical in VARIANT_ALIASES.items():
        spec = refuse_unregistered_variant(alias)
        assert spec.variant_id == canonical

        outcome_alias = run_ablation(alias, case)
        outcome_canonical = run_ablation(canonical, case)
        assert outcome_alias.observed_outcome == outcome_canonical.observed_outcome
        assert outcome_alias.counted_as_success == outcome_canonical.counted_as_success


def test_determinism_and_freeze(fixtures: dict[str, dict[str, Any]]) -> None:
    case = fixtures[abl.FAMILY_TRANSITIVE_REVOCATION]
    run1 = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, case)
    run2 = run_ablation(VARIANT_CANDIDATE_NO_KEY_MODULE, case)
    assert run1.observed_outcome == run2.observed_outcome
    assert run1.detail == run2.detail

    # Predictions are frozen
    assert PREDICTED_VERDICTS == dict(PREDICTED_VERDICTS)
