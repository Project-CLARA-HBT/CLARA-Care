"""Tests for SACMAT-ablation — preregistered causal mechanism ablations.

Positive controls (each ablation runs; removing a mechanism measurably
degrades detection against the full-candidate reference row):
- Every registered variant runs through the task-manifest signature
  ``run_ablation(name, case) -> Outcome`` on every frozen fault family and
  returns a determined/first-class Outcome with the declared ablated
  mechanism in its detail payload.
- The mechanistic inference matrix verifies every variant x family cell
  against its PREREGISTERED prediction (``all_cells_match``).
- ``static_only`` MISSES the healed expiry divergence the full candidate
  REJECTs (temporal dimension is load-bearing).
- ``no_differential`` MISSES every divergence family (multi-engine
  differential is load-bearing).
- ``no_expiry_check`` MISSES the expiry-family divergence while STILL
  catching the revocation-family divergence (the expiry check is the single
  mechanism responsible for expiry-family detection; single-factor isolation).
- ``common_safety_gate`` MISSES the expiry family and FALSE-FLAGS the clean
  restored-authority family (removing conformance detection is doubly
  degrading).
- Detection-count conservation: the full candidate detects strictly more
  fault families than any ablation; the composed reference-vs-ablation delta
  is exactly the declared mechanism's causal contribution.

Adversarial controls (fail closed):
- An unregistered variant id is refused with UNKNOWN_ABLATION_VARIANT by
  run_ablation, run_variant_trace and refuse_unregistered_variant — never
  silently run as any registered arm.
- A variant removing nothing (the full candidate / candidate id) is refused
  with VARIANT_REMOVES_NOTHING.
- A spec declaring no ablated mechanism is refused at construction.
- Malformed cases (non-mapping, missing/empty case id, missing trace) never
  become ADMIT/REJECT.
- Determinism: identical inputs give identical results; rerunning the matrix
  is stable.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat import ablations as abl
from evaluation.venue2027.sacmat import candidate as cand
from evaluation.venue2027.sacmat.ablations import (
    ABLATION_REGISTRY,
    FAULT_FAMILY_IDS,
    PREDICTED_VERDICTS,
    RC_UNKNOWN_ABLATION_VARIANT,
    RC_VARIANT_REMOVES_NOTHING,
    REFERENCE_VARIANT_ID,
    VARIANT_COMMON_SAFETY_GATE,
    VARIANT_NO_DIFFERENTIAL,
    VARIANT_NO_EXPIRY_CHECK,
    VARIANT_STATIC_ONLY,
    VariantSpec,
    describe_ablations,
    fault_family_fixtures,
    mechanistic_inference_matrix,
    refuse_unregistered_variant,
    run_ablation,
    run_variant_trace,
    variant_ids,
    verify_mechanistic_inference_matrix,
)

FAMILY_EXPIRY = abl.FAMILY_HEALED_EXPIRY_DIVERGENCE
FAMILY_REVOKED = abl.FAMILY_REVOKED_REPLAY_DIVERGENCE
FAMILY_CLEAN = abl.FAMILY_CLEAN_CONFORMANT
FAMILY_RESTORED = abl.FAMILY_CLEAN_RESTORED_AUTHORITY

VERDICT_REJECT = "REJECT"
VERDICT_ADMIT = "ADMIT"


@pytest.fixture(scope="module")
def fixtures() -> dict[str, dict[str, object]]:
    builders = fault_family_fixtures()
    return {family: builders[family]() for family in FAULT_FAMILY_IDS}


@pytest.fixture(scope="module")
def matrix() -> dict[str, object]:
    return verify_mechanistic_inference_matrix()


def _cells_by_key(matrix: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (cell["variant_id"], cell["family_id"]): cell  # type: ignore[index]
        for cell in matrix["cells"]  # type: ignore[index]
    }


# ---------------------------------------------------------------------------
# Positive: every registered ablation runs end to end.
# ---------------------------------------------------------------------------


def test_registry_declares_exactly_the_preregistered_variants() -> None:
    assert set(ABLATION_REGISTRY) == {
        VARIANT_STATIC_ONLY,
        VARIANT_NO_DIFFERENTIAL,
        VARIANT_NO_EXPIRY_CHECK,
        VARIANT_COMMON_SAFETY_GATE,
    }
    assert variant_ids() == tuple(ABLATION_REGISTRY)


def test_every_variant_declares_exactly_one_ablated_mechanism() -> None:
    mechanisms = [spec.ablated_mechanism for spec in ABLATION_REGISTRY.values()]
    assert all(mechanisms)
    assert len(set(mechanisms)) == len(mechanisms), "one mechanism axis per variant"
    assert set(mechanisms) == {
        abl.ABLATED_TEMPORAL_DIMENSION,
        abl.ABLATED_MULTI_ENGINE_DIFFERENTIAL,
        abl.ABLATED_EXPIRY_CHECK,
        abl.ABLATED_CONFORMANCE_DETECTION,
    }


@pytest.mark.parametrize("variant_id", sorted(ABLATION_REGISTRY))
@pytest.mark.parametrize("family", sorted(FAULT_FAMILY_IDS))
def test_every_variant_runs_on_every_family_determined(
    variant_id: str, family: str, fixtures: dict[str, dict[str, object]]
) -> None:
    outcome = run_ablation(variant_id, {"case_id": f"C-{family}", "trace": fixtures[family]})
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in {"ADMIT", "REJECT"}
    assert outcome.counted_as_success is True
    payload = json.loads(outcome.detail)
    assert payload["variant_id"] == variant_id
    assert payload["ablated_mechanism"] == ABLATION_REGISTRY[variant_id].ablated_mechanism
    assert payload["case_id"] == f"C-{family}"


def test_mechanistic_inference_matrix_all_cells_match(matrix: dict[str, object]) -> None:
    assert matrix["all_cells_match"] is True
    assert matrix["cell_count"] == 5 * len(FAULT_FAMILY_IDS)
    for cell in matrix["cells"]:  # type: ignore[union-attr]
        assert cell["match"] is True, cell


def test_matrix_covers_every_variant_and_family(matrix: dict[str, object]) -> None:
    cells = _cells_by_key(matrix)
    for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY):
        for family in FAULT_FAMILY_IDS:
            assert (variant_id, family) in cells


def test_static_only_misses_healed_expiry_divergence(
    matrix: dict[str, object], fixtures: dict[str, dict[str, object]]
) -> None:
    reference = _cells_by_key(matrix)[(REFERENCE_VARIANT_ID, FAMILY_EXPIRY)]
    ablated = _cells_by_key(matrix)[(VARIANT_STATIC_ONLY, FAMILY_EXPIRY)]
    assert reference["observed"] == VERDICT_REJECT
    assert ablated["observed"] == VERDICT_ADMIT
    # The terminal view evaluates at the healing grant's tick, not the access
    # decision time: the temporal fact is discarded.
    result = run_variant_trace(VARIANT_STATIC_ONLY, fixtures[FAMILY_EXPIRY])
    assert result.reason_code == cand.RC_ABLATION_NO_TIME
    assert result.ablation == VARIANT_STATIC_ONLY


def test_no_differential_misses_every_divergence_family(matrix: dict[str, object]) -> None:
    cells = _cells_by_key(matrix)
    for family in (FAMILY_EXPIRY, FAMILY_REVOKED):
        assert cells[(REFERENCE_VARIANT_ID, family)]["observed"] == VERDICT_REJECT
        assert cells[(VARIANT_NO_DIFFERENTIAL, family)]["observed"] == VERDICT_ADMIT
    result = run_variant_trace(VARIANT_NO_DIFFERENTIAL, fault_family_fixtures()[FAMILY_EXPIRY]())
    assert result.reason_code == cand.RC_ABLATION_SINGLE_ENGINE
    assert result.ablation == VARIANT_NO_DIFFERENTIAL


def test_no_expiry_check_isolates_the_expiry_mechanism(matrix: dict[str, object]) -> None:
    """Removing ONLY the expiry check degrades exactly the expiry family."""
    cells = _cells_by_key(matrix)
    assert cells[(VARIANT_NO_EXPIRY_CHECK, FAMILY_EXPIRY)]["observed"] == VERDICT_ADMIT
    assert cells[(VARIANT_NO_EXPIRY_CHECK, FAMILY_REVOKED)]["observed"] == VERDICT_REJECT
    assert cells[(VARIANT_NO_EXPIRY_CHECK, FAMILY_CLEAN)]["observed"] == VERDICT_ADMIT
    # The revocation-family verdict is unchanged from the reference row:
    # single-factor isolation (no collateral mechanism change).
    assert (
        cells[(VARIANT_NO_EXPIRY_CHECK, FAMILY_REVOKED)]["observed"]
        == cells[(REFERENCE_VARIANT_ID, FAMILY_REVOKED)]["observed"]
    )


def test_common_safety_gate_misses_expiry_and_false_flags_restored(
    matrix: dict[str, object],
) -> None:
    cells = _cells_by_key(matrix)
    assert cells[(VARIANT_COMMON_SAFETY_GATE, FAMILY_EXPIRY)]["observed"] == VERDICT_ADMIT
    assert cells[(VARIANT_COMMON_SAFETY_GATE, FAMILY_REVOKED)]["observed"] == VERDICT_REJECT
    assert cells[(VARIANT_COMMON_SAFETY_GATE, FAMILY_RESTORED)]["observed"] == VERDICT_REJECT
    assert cells[(REFERENCE_VARIANT_ID, FAMILY_RESTORED)]["observed"] == VERDICT_ADMIT


def test_every_ablation_degrades_measurably_against_the_reference(
    matrix: dict[str, object],
) -> None:
    """Removing a mechanism is measurable: a detected-vs-missed delta exists."""
    observed = matrix["observed_degradation"]  # type: ignore[index]
    predicted = matrix["predicted_degradation"]  # type: ignore[index]
    for variant_id in ABLATION_REGISTRY:
        assert observed[variant_id]["measurably_degraded"] is True, variant_id
        assert observed[variant_id] == predicted[variant_id]
    reference_families = {
        cell["family_id"]  # type: ignore[index]
        for cell in matrix["cells"]  # type: ignore[union-attr]
        if cell["variant_id"] == REFERENCE_VARIANT_ID and cell["observed"] == VERDICT_REJECT  # type: ignore[index]
    }
    assert reference_families == {FAMILY_EXPIRY, FAMILY_REVOKED}


def test_full_candidate_reference_row_is_not_part_of_the_registry() -> None:
    assert REFERENCE_VARIANT_ID not in ABLATION_REGISTRY
    assert set(variant_ids()) == set(ABLATION_REGISTRY)


def test_pred_verdicts_are_frozen_design_constants() -> None:
    assert PREDICTED_VERDICTS[(REFERENCE_VARIANT_ID, FAMILY_EXPIRY)] == VERDICT_REJECT
    assert PREDICTED_VERDICTS[(VARIANT_STATIC_ONLY, FAMILY_EXPIRY)] == VERDICT_ADMIT
    design = mechanistic_inference_matrix()
    assert design["predicted_verdicts"][REFERENCE_VARIANT_ID][FAMILY_EXPIRY] == VERDICT_REJECT
    assert design["scale"].startswith("DEVELOPMENT")


def test_describe_ablations_design_record() -> None:
    record = describe_ablations()
    assert record["task_id"] == "SACMAT-ablation"
    assert record["reference_variant"] == REFERENCE_VARIANT_ID
    assert set(record["registry"]) == set(ABLATION_REGISTRY)
    assert record["manifest_signature"] == "run_ablation(name: str, case: Mapping) -> Outcome"


def test_determinism_identical_inputs_identical_results(
    fixtures: dict[str, dict[str, object]],
) -> None:
    for variant_id in ABLATION_REGISTRY:
        first = run_ablation(variant_id, {"case_id": "D1", "trace": fixtures[FAMILY_EXPIRY]})
        second = run_ablation(variant_id, {"case_id": "D1", "trace": fixtures[FAMILY_EXPIRY]})
        assert first == second
    first_matrix = verify_mechanistic_inference_matrix()
    second_matrix = verify_mechanistic_inference_matrix()
    assert first_matrix["cells"] == second_matrix["cells"]


def test_variant_trace_results_are_typed_and_serializable(
    fixtures: dict[str, dict[str, object]],
) -> None:
    for variant_id in ABLATION_REGISTRY:
        result = run_variant_trace(variant_id, fixtures[FAMILY_CLEAN])
        assert isinstance(result, cand.ConformanceResult)
        payload = result.to_dict()
        assert payload["ablation"] == variant_id
        json.dumps(payload)


# ---------------------------------------------------------------------------
# Adversarial: unregistered / nothing-removing variants refused fail-closed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bogus",
    ["no_replay_at_all", "full_candidate_v2", "", "FULL_CANDIDATE", "static-only"],
)
def test_unregistered_variant_refused_by_guard(bogus: str) -> None:
    with pytest.raises(abl.AblationError) as excinfo:
        refuse_unregistered_variant(bogus)
    assert excinfo.value.reason_code == RC_UNKNOWN_ABLATION_VARIANT


@pytest.mark.parametrize(
    "identity", [REFERENCE_VARIANT_ID, "sacmat-candidate-temporal-conformance"]
)
def test_nothing_removing_identity_refused_by_guard(identity: str) -> None:
    with pytest.raises(abl.AblationError) as excinfo:
        refuse_unregistered_variant(identity)
    assert excinfo.value.reason_code == RC_VARIANT_REMOVES_NOTHING


@pytest.mark.parametrize(
    "identity", [REFERENCE_VARIANT_ID, "sacmat-candidate-temporal-conformance"]
)
def test_nothing_removing_variant_refused_by_run_ablation(identity: str) -> None:
    outcome = run_ablation(
        identity, {"case_id": "C-refused", "trace": fault_family_fixtures()[FAMILY_EXPIRY]()}
    )
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert outcome.detail.startswith(RC_VARIANT_REMOVES_NOTHING)


@pytest.mark.parametrize(
    "bogus", ["no_replay_at_all", "everything_enabled", "static_only ", " Static_Only"]
)
def test_unregistered_variant_refused_by_run_ablation(bogus: str) -> None:
    outcome = run_ablation(
        bogus, {"case_id": "C-refused", "trace": fault_family_fixtures()[FAMILY_EXPIRY]()}
    )
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert outcome.detail.startswith(RC_UNKNOWN_ABLATION_VARIANT)


def test_unregistered_variant_refused_by_run_variant_trace() -> None:
    trace = fault_family_fixtures()[FAMILY_EXPIRY]()
    with pytest.raises(abl.AblationError) as excinfo:
        run_variant_trace("no_replay_at_all", trace)
    assert excinfo.value.reason_code == RC_UNKNOWN_ABLATION_VARIANT


def test_spec_without_ablated_mechanism_refused_at_construction() -> None:
    with pytest.raises(abl.AblationError) as excinfo:
        VariantSpec(
            variant_id="identity_row",
            title="The candidate untouched",
            ablated_mechanism="",
            description="removes nothing",
            expected_effect="none",
            reuses=("candidate.conformance_test",),
            applied_by="harness_modeled_gate",
        )
    assert excinfo.value.reason_code == RC_VARIANT_REMOVES_NOTHING


def test_registry_specs_never_remove_nothing() -> None:
    for spec in ABLATION_REGISTRY.values():
        # Every registered spec must survive the same guard it is served by.
        assert refuse_unregistered_variant(spec.variant_id) == spec
        assert spec.ablated_mechanism.strip()


def test_malformed_cases_never_become_safe_verdicts() -> None:
    trace = fault_family_fixtures()[FAMILY_EXPIRY]()
    not_a_mapping = run_ablation(VARIANT_STATIC_ONLY, ["not", "a", "case"])  # type: ignore[arg-type]
    assert not_a_mapping.observed_outcome == "EXECUTION_ERROR"
    assert not_a_mapping.counted_as_success is False
    missing_id = run_ablation(VARIANT_STATIC_ONLY, {"trace": trace})
    assert missing_id.observed_outcome == "INDETERMINATE"
    assert missing_id.detail.endswith(abl.RC_CASE_ID_MISSING)
    empty_id = run_ablation(VARIANT_STATIC_ONLY, {"case_id": "", "trace": trace})
    assert empty_id.observed_outcome == "INDETERMINATE"
    non_string_id = run_ablation(VARIANT_STATIC_ONLY, {"case_id": 7, "trace": trace})
    assert non_string_id.observed_outcome == "INDETERMINATE"
    missing_trace = run_ablation(VARIANT_STATIC_ONLY, {"case_id": "C9"})
    assert missing_trace.observed_outcome == "INDETERMINATE"
    assert missing_trace.detail.endswith(abl.RC_TRACE_MISSING)


def test_data_faults_surface_as_indeterminate_not_reject() -> None:
    empty = run_ablation(
        VARIANT_STATIC_ONLY, {"case_id": "C10", "trace": {"trace_id": "T", "events": []}}
    )
    assert empty.observed_outcome == "INDETERMINATE"
    unordered = run_ablation(
        VARIANT_NO_EXPIRY_CHECK,
        {
            "case_id": "C11",
            "trace": {
                "trace_id": "T",
                "events": [
                    {"kind": "GRANT", "principal": "p", "logical_time": 200},
                    {"kind": "GRANT", "principal": "p", "logical_time": 100},
                ],
            },
        },
    )
    assert unordered.observed_outcome == "INDETERMINATE"
    wiring = run_ablation(
        VARIANT_NO_DIFFERENTIAL,
        {"case_id": "C12", "trace": {"trace_id": "T", "events": {"kind": "GRANT"}}},
    )
    assert wiring.observed_outcome == "EXECUTION_ERROR"
    assert wiring.detail.startswith(f"{abl.ABLATIONS_VERSION}|")


def test_refusal_outcome_is_a_first_class_outcome_object() -> None:
    outcome = run_ablation("nope", {"case_id": "C13", "trace": {}})
    assert isinstance(outcome, Outcome)
    assert outcome.to_dict()["observed_outcome"] == "EXECUTION_ERROR"


def test_matrix_predictions_are_prespecified_not_retrofitted() -> None:
    """The matrix verifier must compare against frozen constants, not results."""
    design = mechanistic_inference_matrix()
    for (variant_id, family), verdict in PREDICTED_VERDICTS.items():
        assert design["predicted_verdicts"][variant_id][family] == verdict


def test_candidate_module_untouched_by_ablation_layer() -> None:
    """The ablation layer must not mutate the candidate's own ablation hooks."""
    trace = fault_family_fixtures()[FAMILY_EXPIRY]()
    direct = cand.ablation_no_time(trace)
    via_ablation = run_variant_trace(VARIANT_STATIC_ONLY, trace)
    assert direct.status == via_ablation.status
    assert via_ablation.ablation == VARIANT_STATIC_ONLY
    replaced = dataclasses.replace(direct, ablation=VARIANT_STATIC_ONLY)
    assert replaced == via_ablation
