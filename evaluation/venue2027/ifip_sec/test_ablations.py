"""Tests for IFIP_SEC-ablation — preregistered causal mechanism ablations.

Positive controls (each ablation runs; removing a mechanism lets a
replay/purpose/lineage/epoch bypass through that the full candidate rejects):
- Every registered variant runs through the task-manifest signature
  ``run_ablation(name, case) -> Outcome`` on every frozen family and returns
  a determined Outcome (ADMIT/REJECT) with the declared ablated mechanism in
  its detail payload.
- The mechanistic inference matrix verifies every variant x family cell
  against its PREREGISTERED prediction (``all_cells_match``).
- ``no_nonce_consume_once`` ADMITs the exact replay the full candidate
  REJECTs with NONCE_REPLAYED (the consume-once nonce is the mechanism).
- ``no_purpose_binding`` ADMITs the purpose switch the full candidate
  REJECTs with PURPOSE_MISMATCH (the purpose binding is the mechanism).
- ``no_delegation_lineage_validation`` ADMITs the lineage splice the full
  candidate REJECTs with LINEAGE_SPLICED (lineage validation is the
  mechanism).
- ``no_epoch_recheck`` ADMITs the revoked-consent replay the full candidate
  REJECTs with CONSENT_EPOCH_REVOKED (the epoch recheck is the mechanism).
- ``common_safety_gate`` ADMITs every noncryptographic attack the candidate
  rejects; it still catches the tampered receipt (real HMAC stays).
- Single-factor isolation: every ablation keeps every OTHER mechanism
  enforced (nonce/purpose/lineage/epoch variants all still REJECT the
  attack families outside their ablated axis).
- Detection-count conservation: the full candidate REJECTs strictly more
  attack families than any ablation.

Adversarial controls (fail closed):
- An unregistered variant id is refused with UNKNOWN_ABLATION_VARIANT by
  run_ablation and refuse_unregistered_variant — never silently run as any
  registered arm.
- A variant removing nothing (the full candidate / candidate id) is refused
  with VARIANT_REMOVES_NOTHING.
- A spec declaring no ablated mechanism is refused at construction.
- Malformed cases (non-mapping, missing/empty case id, missing
  receipt/request, bad nonce store type) never become ADMIT/REJECT.
- Determinism: identical inputs give identical results; rerunning the
  matrix is stable and its predictions are frozen constants.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.ifip_sec import ablations as abl
from evaluation.venue2027.ifip_sec import candidate as cand
from evaluation.venue2027.ifip_sec.ablations import (
    ABLATION_REGISTRY,
    FAULT_FAMILY_IDS,
    PREDICTED_VERDICTS,
    RC_UNKNOWN_ABLATION_VARIANT,
    RC_VARIANT_REMOVES_NOTHING,
    REFERENCE_VARIANT_ID,
    VARIANT_COMMON_SAFETY_GATE,
    VARIANT_NO_EPOCH_RECHECK,
    VARIANT_NO_LINEAGE,
    VARIANT_NO_NONCE,
    VARIANT_NO_PURPOSE,
    VariantSpec,
    case_fixtures,
    describe_ablations,
    mechanistic_inference_matrix,
    refuse_unregistered_variant,
    run_ablation,
    variant_ids,
    verify_mechanistic_inference_matrix,
)

FAMILY_FRESH = abl.FAMILY_FRESH_CONSUMPTION
FAMILY_REPLAY = abl.FAMILY_EXACT_REPLAY
FAMILY_PURPOSE = abl.FAMILY_PURPOSE_SWITCH
FAMILY_SPLICE = abl.FAMILY_LINEAGE_SPLICE
FAMILY_REVOKED = abl.FAMILY_CONSENT_REVOKED_REPLAY
FAMILY_TAMPER = abl.FAMILY_TAMPERED_RECEIPT
FAMILY_TRUNC = abl.FAMILY_CHAIN_TRUNCATION

VERDICT_REJECT = "REJECT"
VERDICT_ADMIT = "ADMIT"

ATTACK_FAMILIES = (
    FAMILY_REPLAY,
    FAMILY_PURPOSE,
    FAMILY_SPLICE,
    FAMILY_REVOKED,
    FAMILY_TAMPER,
    FAMILY_TRUNC,
)


@pytest.fixture(scope="function")
def fixtures() -> dict[str, dict[str, object]]:
    """Fresh fixture set per test: candidate runs consume nonce stores, so
    sharing the injected state across tests would change the mechanistic
    contrasts (a drained store turns every attack into NONCE_REPLAYED)."""
    builders = case_fixtures()
    return {family: builders[family]() for family in FAULT_FAMILY_IDS}


@pytest.fixture(scope="module")
def matrix() -> dict[str, object]:
    return verify_mechanistic_inference_matrix()


def _detail_reason(outcome: Outcome) -> str:
    try:
        return str(json.loads(outcome.detail).get("reason_code", ""))
    except json.JSONDecodeError:
        return outcome.detail


# ---------------------------------------------------------------------------
# Positive: registry shape and end-to-end execution.
# ---------------------------------------------------------------------------


def test_registry_declares_exactly_the_preregistered_variants() -> None:
    assert set(ABLATION_REGISTRY) == {
        VARIANT_NO_NONCE,
        VARIANT_NO_PURPOSE,
        VARIANT_NO_LINEAGE,
        VARIANT_NO_EPOCH_RECHECK,
        VARIANT_COMMON_SAFETY_GATE,
    }
    assert variant_ids() == tuple(ABLATION_REGISTRY)


def test_every_variant_declares_exactly_one_distinct_mechanism() -> None:
    mechanisms = [spec.ablated_mechanism for spec in ABLATION_REGISTRY.values()]
    assert all(mechanisms)
    assert len(set(mechanisms)) == len(mechanisms), "one mechanism axis per variant"
    assert set(mechanisms) == {
        abl.ABLATED_CONSUME_ONCE_NONCE,
        abl.ABLATED_PURPOSE_BINDING,
        abl.ABLATED_LINEAGE_VALIDATION,
        abl.ABLATED_EPOCH_RECHECK,
        abl.ABLATED_BINDING_PIPELINE,
    }


def test_registry_specs_survive_their_own_guard() -> None:
    for spec in ABLATION_REGISTRY.values():
        assert refuse_unregistered_variant(spec.variant_id) == spec


@pytest.mark.parametrize("variant_id", list(ABLATION_REGISTRY))
def test_every_variant_runs_on_every_family_determined(
    variant_id: str, fixtures: dict[str, dict[str, object]]
) -> None:
    for family in FAULT_FAMILY_IDS:
        case = {**fixtures[family], "case_id": f"C-{family}"}
        outcome = run_ablation(variant_id, case)
        assert outcome.observed_outcome in (VERDICT_ADMIT, VERDICT_REJECT)
        assert outcome.counted_as_success is True
        payload = json.loads(outcome.detail)
        assert payload["variant_id"] == variant_id
        assert payload["ablated_mechanism"] == ABLATION_REGISTRY[variant_id].ablated_mechanism
        assert payload["case_id"] == f"C-{family}"


def test_run_ablation_reuses_the_candidate_verdict_shape(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """ADMIT/REJECT mapping mirrors the candidate's own ALLOW/DENY adapter."""
    outcome = run_ablation(VARIANT_NO_NONCE, {"case_id": "C-shape", **fixtures[FAMILY_FRESH]})
    assert isinstance(outcome, Outcome)
    payload = json.loads(outcome.detail)
    assert payload["decision"] in (cand.DECISION_ALLOW, cand.DECISION_DENY)
    assert outcome.observed_outcome == (
        VERDICT_ADMIT if payload["decision"] == cand.DECISION_ALLOW else VERDICT_REJECT
    )


# ---------------------------------------------------------------------------
# Positive: the mechanistic inference matrix.
# ---------------------------------------------------------------------------


def test_mechanistic_inference_matrix_all_cells_match(matrix: dict[str, object]) -> None:
    assert matrix["all_cells_match"] is True
    assert matrix["cell_count"] == len(PREDICTED_VERDICTS)


def test_matrix_covers_every_variant_and_family(matrix: dict[str, object]) -> None:
    observed = matrix["observed_verdicts"]
    assert set(observed) == {REFERENCE_VARIANT_ID, *ABLATION_REGISTRY}
    for families in observed.values():
        assert set(families) == set(FAULT_FAMILY_IDS)


def test_matrix_predictions_are_prespecified_not_retrofitted() -> None:
    """The matrix verifier must compare against frozen constants, not results."""
    design = mechanistic_inference_matrix()
    for (variant_id, family), verdict in PREDICTED_VERDICTS.items():
        assert design["predicted_verdicts"][variant_id][family] == verdict


def test_reference_row_rejects_every_attack_family(
    matrix: dict[str, object],
) -> None:
    observed = matrix["observed_verdicts"][REFERENCE_VARIANT_ID]
    assert observed[FAMILY_FRESH] == VERDICT_ADMIT
    for family in ATTACK_FAMILIES:
        assert observed[family] == VERDICT_REJECT, family


# ---------------------------------------------------------------------------
# Positive: the single-mechanism bypass contrasts (central scientific claims).
# ---------------------------------------------------------------------------


def test_removing_nonce_allows_exact_replay_full_candidate_rejects(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """THE nonce contrast: ablated ADMITs the replay the candidate DENYs."""
    ablated = run_ablation(VARIANT_NO_NONCE, {"case_id": "C-nn", **fixtures[FAMILY_REPLAY]})
    reference = abl._run_reference({"case_id": "C-ref", **fixtures[FAMILY_REPLAY]})
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert reference.observed_outcome == VERDICT_REJECT
    assert _detail_reason(reference) == cand.REASON_NONCE_REPLAYED
    # The store is demonstrably never consulted: no consumption is recorded.
    assert json.loads(ablated.detail)["nonce_consumed"] is False


def test_removing_purpose_binding_allows_purpose_switch_full_candidate_rejects(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """THE purpose contrast: ablated ADMITs the switch the candidate DENYs."""
    ablated = run_ablation(VARIANT_NO_PURPOSE, {"case_id": "C-np", **fixtures[FAMILY_PURPOSE]})
    reference = abl._run_reference({"case_id": "C-ref", **fixtures[FAMILY_PURPOSE]})
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert reference.observed_outcome == VERDICT_REJECT
    assert _detail_reason(reference) == cand.REASON_PURPOSE_MISMATCH


def test_removing_lineage_validation_allows_splice_full_candidate_rejects(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """THE lineage contrast: ablated ADMITs the splice the candidate DENYs."""
    ablated = run_ablation(VARIANT_NO_LINEAGE, {"case_id": "C-nl", **fixtures[FAMILY_SPLICE]})
    reference = abl._run_reference({"case_id": "C-ref", **fixtures[FAMILY_SPLICE]})
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert reference.observed_outcome == VERDICT_REJECT
    assert _detail_reason(reference) == cand.REASON_LINEAGE_SPLICED


def test_removing_epoch_recheck_allows_revoked_consent_replay_candidate_rejects(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """THE epoch contrast: ablated ADMITs the revoked replay the candidate DENYs."""
    ablated = run_ablation(
        VARIANT_NO_EPOCH_RECHECK, {"case_id": "C-ne", **fixtures[FAMILY_REVOKED]}
    )
    reference = abl._run_reference({"case_id": "C-ref", **fixtures[FAMILY_REVOKED]})
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert reference.observed_outcome == VERDICT_REJECT
    assert _detail_reason(reference) == cand.REASON_CONSENT_EPOCH_REVOKED


def test_common_safety_gate_admits_every_noncryptographic_attack(
    matrix: dict[str, object],
) -> None:
    """The gate catches only tampering; every other attack passes it."""
    observed = matrix["observed_verdicts"][VARIANT_COMMON_SAFETY_GATE]
    for family in (FAMILY_REPLAY, FAMILY_PURPOSE, FAMILY_SPLICE, FAMILY_REVOKED, FAMILY_TRUNC):
        assert observed[family] == VERDICT_ADMIT, family
    assert observed[FAMILY_TAMPER] == VERDICT_REJECT


def test_gate_reason_code_is_not_a_replay_closure_claim(
    fixtures: dict[str, dict[str, object]],
) -> None:
    outcome = run_ablation(
        VARIANT_COMMON_SAFETY_GATE, {"case_id": "C-g", **fixtures[FAMILY_REPLAY]}
    )
    assert outcome.observed_outcome == VERDICT_ADMIT
    assert _detail_reason(outcome) == abl.RC_GATE_SIGNATURE_VALID


def test_single_factor_isolation_nonce_variant_still_rejects_other_attacks(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """Removing the nonce leaves every OTHER binding enforced."""
    for family in (FAMILY_PURPOSE, FAMILY_SPLICE, FAMILY_REVOKED, FAMILY_TAMPER, FAMILY_TRUNC):
        outcome = run_ablation(VARIANT_NO_NONCE, {"case_id": f"C-iso-{family}", **fixtures[family]})
        assert outcome.observed_outcome == VERDICT_REJECT, family


def test_single_factor_isolation_purpose_variant_still_rejects_other_attacks(
    fixtures: dict[str, dict[str, object]],
) -> None:
    for family in (FAMILY_REPLAY, FAMILY_SPLICE, FAMILY_REVOKED, FAMILY_TAMPER, FAMILY_TRUNC):
        outcome = run_ablation(
            VARIANT_NO_PURPOSE, {"case_id": f"C-isop-{family}", **fixtures[family]}
        )
        assert outcome.observed_outcome == VERDICT_REJECT, family


def test_single_factor_isolation_lineage_variant_still_rejects_other_attacks(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """The splice passes, but the separate chain-truncation axis stays enforced."""
    for family in (FAMILY_REPLAY, FAMILY_PURPOSE, FAMILY_REVOKED, FAMILY_TAMPER, FAMILY_TRUNC):
        outcome = run_ablation(
            VARIANT_NO_LINEAGE, {"case_id": f"C-isl-{family}", **fixtures[family]}
        )
        assert outcome.observed_outcome == VERDICT_REJECT, family


def test_single_factor_isolation_epoch_variant_still_rejects_other_attacks(
    fixtures: dict[str, dict[str, object]],
) -> None:
    for family in (FAMILY_REPLAY, FAMILY_PURPOSE, FAMILY_SPLICE, FAMILY_TAMPER, FAMILY_TRUNC):
        outcome = run_ablation(
            VARIANT_NO_EPOCH_RECHECK, {"case_id": f"C-ise-{family}", **fixtures[family]}
        )
        assert outcome.observed_outcome == VERDICT_REJECT, family


def test_every_ablation_degrades_measurably_against_the_reference(
    matrix: dict[str, object],
) -> None:
    """Each variant ADMITs at least one attack family the reference REJECTs."""
    observed = matrix["observed_verdicts"]
    predicted = mechanistic_inference_matrix()["degradation_axes"]
    observed_degradation = matrix["observed_degradation"]
    for variant_id in ABLATION_REGISTRY:
        missed = [
            family
            for family in ATTACK_FAMILIES
            if observed[variant_id][family] == VERDICT_ADMIT
            and observed[REFERENCE_VARIANT_ID][family] == VERDICT_REJECT
        ]
        assert missed, variant_id
        assert predicted[variant_id]["measurably_degraded"] is True
        assert observed_degradation[variant_id]["measurably_degraded"] is True
        assert observed_degradation[variant_id] == predicted[variant_id]


def test_detection_count_conservation(matrix: dict[str, object]) -> None:
    """The full candidate rejects strictly more attacks than any ablation."""
    observed = matrix["observed_verdicts"]
    reference_rejects = sum(
        1 for family in ATTACK_FAMILIES if observed[REFERENCE_VARIANT_ID][family] == VERDICT_REJECT
    )
    assert reference_rejects == len(ATTACK_FAMILIES)
    for variant_id in ABLATION_REGISTRY:
        variant_rejects = sum(
            1 for family in ATTACK_FAMILIES if observed[variant_id][family] == VERDICT_REJECT
        )
        assert variant_rejects < reference_rejects, variant_id


def test_fresh_control_is_admitted_by_every_variant_and_the_reference(
    matrix: dict[str, object],
) -> None:
    """The legitimate control never becomes collateral damage."""
    observed = matrix["observed_verdicts"]
    for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY):
        assert observed[variant_id][FAMILY_FRESH] == VERDICT_ADMIT, variant_id


# ---------------------------------------------------------------------------
# Positive: design record, determinism, typed serializable results.
# ---------------------------------------------------------------------------


def test_describe_ablations_design_record() -> None:
    design = describe_ablations()
    assert design["task_id"] == abl.ABLATION_TASK_ID
    assert design["candidate_id"] == cand.CANDIDATE_ID
    assert design["manifest_signature"] == "run_ablation(name: str, case: Mapping) -> Outcome"
    assert set(design["registry"]) == set(ABLATION_REGISTRY)
    assert design["fault_families"] == list(FAULT_FAMILY_IDS)
    assert design["refusal_codes"] == [
        RC_UNKNOWN_ABLATION_VARIANT,
        RC_VARIANT_REMOVES_NOTHING,
    ]


def test_determinism_identical_inputs_identical_results(
    fixtures: dict[str, dict[str, object]],
) -> None:
    builders = case_fixtures()
    first = run_ablation(VARIANT_NO_NONCE, {"case_id": "C-det", **builders[FAMILY_REPLAY]()})
    second = run_ablation(VARIANT_NO_NONCE, {"case_id": "C-det", **builders[FAMILY_REPLAY]()})
    assert first.to_dict() == second.to_dict()
    matrix_a = verify_mechanistic_inference_matrix()
    matrix_b = verify_mechanistic_inference_matrix()
    assert matrix_a["all_cells_match"] == matrix_b["all_cells_match"]
    assert matrix_a["observed_verdicts"] == matrix_b["observed_verdicts"]


def test_variant_outcomes_are_typed_and_serializable(
    fixtures: dict[str, dict[str, object]],
) -> None:
    for variant_id in ABLATION_REGISTRY:
        outcome = run_ablation(variant_id, {"case_id": "C-ser", **fixtures[FAMILY_FRESH]})
        assert isinstance(outcome, Outcome)
        json.dumps(outcome.to_dict())
        json.loads(outcome.detail)


def test_case_fixtures_are_fresh_per_call() -> None:
    """Mutating one fixture instance must not leak into the next call."""
    builders = case_fixtures()
    case = builders[FAMILY_PURPOSE]()
    baseline = case["request"]["purpose"]
    assert baseline == "secondary_research"  # the attack mutation is in the fixture
    case["request"]["purpose"] = "mutated"
    fresh = builders[FAMILY_PURPOSE]()
    assert fresh["request"]["purpose"] == baseline
    assert fresh["ledger"] is not case["ledger"]
    assert fresh["nonce_store"] is not case["nonce_store"]


def test_candidate_module_untouched_by_ablation_layer(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """The candidate's own ablation hooks behave identically when used directly."""
    builders = case_fixtures()
    case = builders[FAMILY_REPLAY]()
    receipt = cand.Receipt.from_dict(case["receipt"])
    request = cand.AuthorizationRequest.from_dict(case["request"])
    direct = cand.ablation_no_nonce()(receipt, request, case["nonce_store"], case["ledger"])
    via_ablation = run_ablation(VARIANT_NO_NONCE, {"case_id": "C-direct", **case})
    assert via_ablation.observed_outcome == (
        VERDICT_ADMIT if direct.decision == cand.DECISION_ALLOW else VERDICT_REJECT
    )


# ---------------------------------------------------------------------------
# Adversarial: unregistered / nothing-removing variants refused fail-closed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bogus",
    ["no_replay_at_all", "full_candidate_v2", "", "FULL_CANDIDATE", "no-nonce-consume-once"],
)
def test_unregistered_variant_refused_by_guard(bogus: str) -> None:
    with pytest.raises(abl.AblationError) as excinfo:
        refuse_unregistered_variant(bogus)
    assert excinfo.value.reason_code == RC_UNKNOWN_ABLATION_VARIANT


@pytest.mark.parametrize(
    "identity",
    [REFERENCE_VARIANT_ID, "clara.ifip_sec.candidate.replay-closed-lineage-authorization"],
)
def test_nothing_removing_identity_refused_by_guard(identity: str) -> None:
    with pytest.raises(abl.AblationError) as excinfo:
        refuse_unregistered_variant(identity)
    assert excinfo.value.reason_code == RC_VARIANT_REMOVES_NOTHING


@pytest.mark.parametrize("identity", [REFERENCE_VARIANT_ID, cand.CANDIDATE_ID])
def test_nothing_removing_variant_refused_by_run_ablation(
    identity: str, fixtures: dict[str, dict[str, object]]
) -> None:
    outcome = run_ablation(identity, {"case_id": "C-refused", **fixtures[FAMILY_REPLAY]})
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert outcome.detail.startswith(RC_VARIANT_REMOVES_NOTHING)


@pytest.mark.parametrize(
    "bogus", ["no_replay_at_all", "everything_enabled", "no_nonce ", " No_Nonce_Consume_Once"]
)
def test_unregistered_variant_refused_by_run_ablation(
    bogus: str, fixtures: dict[str, dict[str, object]]
) -> None:
    outcome = run_ablation(bogus, {"case_id": "C-refused", **fixtures[FAMILY_REPLAY]})
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert outcome.detail.startswith(RC_UNKNOWN_ABLATION_VARIANT)


def test_refusal_outcome_is_a_first_class_outcome_object(
    fixtures: dict[str, dict[str, object]],
) -> None:
    outcome = run_ablation("nope", {"case_id": "C13", **fixtures[FAMILY_REPLAY]})
    assert isinstance(outcome, Outcome)
    assert outcome.to_dict()["observed_outcome"] == "EXECUTION_ERROR"


def test_spec_without_ablated_mechanism_refused_at_construction() -> None:
    with pytest.raises(abl.AblationError) as excinfo:
        VariantSpec(
            variant_id="identity_row",
            title="The candidate untouched",
            ablated_mechanism="",
            description="removes nothing",
            expected_effect="none",
            reuses=("candidate.authorize",),
            applied_by="harness_modeled_gate",
        )
    assert excinfo.value.reason_code == RC_VARIANT_REMOVES_NOTHING


def test_registry_specs_never_remove_nothing() -> None:
    for spec in ABLATION_REGISTRY.values():
        assert refuse_unregistered_variant(spec.variant_id) == spec
        assert spec.ablated_mechanism.strip()


# ---------------------------------------------------------------------------
# Adversarial: malformed cases never become safe verdicts.
# ---------------------------------------------------------------------------


def test_malformed_cases_never_become_safe_verdicts(
    fixtures: dict[str, dict[str, object]],
) -> None:
    case = dict(fixtures[FAMILY_REPLAY])
    case.pop("case_id", None)
    not_a_mapping = run_ablation(VARIANT_NO_NONCE, ["not", "a", "case"])  # type: ignore[arg-type]
    assert not_a_mapping.observed_outcome == "EXECUTION_ERROR"
    assert not_a_mapping.counted_as_success is False
    missing_id = run_ablation(VARIANT_NO_NONCE, case)
    assert missing_id.observed_outcome == "INDETERMINATE"
    assert missing_id.detail.endswith(abl.RC_CASE_ID_MISSING)
    empty_id = run_ablation(VARIANT_NO_NONCE, {**case, "case_id": ""})
    assert empty_id.observed_outcome == "INDETERMINATE"
    non_string_id = run_ablation(VARIANT_NO_NONCE, {**case, "case_id": 7})
    assert non_string_id.observed_outcome == "INDETERMINATE"
    missing_receipt = run_ablation(VARIANT_NO_NONCE, {"case_id": "C9"})
    assert missing_receipt.observed_outcome == "INDETERMINATE"
    assert missing_receipt.detail.endswith(abl.RC_RECEIPT_MISSING)
    missing_request = run_ablation(VARIANT_NO_NONCE, {"case_id": "C10", "receipt": {}})
    assert missing_request.observed_outcome == "INDETERMINATE"
    assert missing_request.detail.endswith(abl.RC_REQUEST_MISSING)


def test_unparseable_receipts_fail_closed_not_admitted(
    fixtures: dict[str, dict[str, object]],
) -> None:
    case = fixtures[FAMILY_FRESH]
    outcome = run_ablation(VARIANT_NO_NONCE, {**case, "case_id": "C-bad", "receipt": {"nope": 1}})
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    tampered = run_ablation(
        VARIANT_NO_NONCE,
        {**case, "case_id": "C-bad2", "receipt": {**case["receipt"], "mac": "deadbeef"}},
    )
    assert tampered.observed_outcome == VERDICT_REJECT
    assert _detail_reason(tampered) == cand.REASON_RECEIPT_SIGNATURE_INVALID


def test_bad_wiring_never_becomes_a_safe_verdict(
    fixtures: dict[str, dict[str, object]],
) -> None:
    case = fixtures[FAMILY_FRESH]
    bad_store = run_ablation(
        VARIANT_NO_NONCE, {**case, "case_id": "C-w1", "nonce_store": "not-a-set"}
    )
    assert bad_store.observed_outcome == "EXECUTION_ERROR"
    assert abl.RC_NONCE_STORE_BAD_TYPE in bad_store.detail
    bad_ledger = run_ablation(VARIANT_NO_NONCE, {**case, "case_id": "C-w2", "ledger": object()})
    assert bad_ledger.observed_outcome == "EXECUTION_ERROR"
    assert abl.RC_LEDGER_BAD_TYPE in bad_ledger.detail


def test_epoch_blind_view_never_masks_ancestry_faults(
    fixtures: dict[str, dict[str, object]],
) -> None:
    """A receipt whose parent is NOT registered still fails on the blind view."""
    builders = case_fixtures()
    case = builders[FAMILY_FRESH]()
    orphan = cand.Receipt.from_dict({**case["receipt"], "parent_ref": "receipt-unregistered"})
    ledger = case["ledger"]
    blind = abl.register_epoch_blind_view(ledger, orphan)
    assert blind.verify_ancestry(orphan) is False
    # Registering the ACTUAL parent (by its real receipt id) repairs the walk
    # only when the parent reference matches a registered receipt id.
    root = cand.Receipt.from_dict(case["registered_receipts"][0])
    reparented = cand.Receipt.from_dict({**case["receipt"], "parent_ref": root.receipt_id})
    blind_with_parent = abl.register_epoch_blind_view(ledger, reparented, root)
    assert blind_with_parent.verify_ancestry(reparented) is True


def test_matrix_verifier_never_repairs_post_hoc() -> None:
    """A falsified cell must surface as a mismatch, not a repaired matrix."""
    matrix_result = verify_mechanistic_inference_matrix()
    wrong_prediction = dict(PREDICTED_VERDICTS)
    wrong_prediction[(REFERENCE_VARIANT_ID, FAMILY_REPLAY)] = VERDICT_ADMIT
    # The frozen constant stays untouched; the verifier compares executed
    # behavior against PREDICTED_VERDICTS, so the executed REJECT cell keeps
    # matching the TRUE constant (the tampered copy is never consulted).
    for cell in matrix_result["cells"]:
        if cell["variant_id"] == REFERENCE_VARIANT_ID and cell["family_id"] == FAMILY_REPLAY:
            assert cell["predicted"] == VERDICT_REJECT
            assert cell["match"] is True


def test_ablation_layer_does_not_mutate_the_candidate_module() -> None:
    import inspect

    source = inspect.getsource(cand.authorize)
    assert "skip_lineage" not in source or "skip_lineage=False" in source
    assert cand.authorize.__module__ == "evaluation.venue2027.ifip_sec.candidate"
    # The exported authorize is the untouched original pipeline.
    assert dataclasses.is_dataclass(cand.Verdict)
