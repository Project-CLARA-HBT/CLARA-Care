"""Tests for AIME-ablation — causal mechanism ablation variants.

Positive controls:
- Registry declares exactly the 5 preregistered ablation variants:
  without_history_contrast, without_consent_recheck, without_medication_allergy_gate,
  common_safety_gate, full_refresh.
- Every variant declares exactly one distinct mechanism axis.
- Registry specs survive their own guard.
- Every variant runs on every family fixture and returns a determined Outcome.
- The mechanistic inference matrix matches prespecified predictions across all cells.
- Removing history contrast misses a withdrawal hazard the full candidate catches (central contract).
- Removing consent recheck admits revoked consent the candidate rejects.
- Removing medication/allergy gate admits allergen report the candidate rejects.
- Common safety gate misses all mid-task temporal hazards.
- Full refresh forces regeneration (INDETERMINATE) on medication withdrawal.
- Single-factor isolation: each ablation preserves non-ablated safety axes.
- Determinism: identical input yields byte-identical result.

Adversarial controls (fail closed):
- Unregistered variant refused by guard (UNKNOWN_ABLATION_VARIANT).
- Unregistered variant refused by run_ablation (EXECUTION_ERROR, UNKNOWN_ABLATION_VARIANT).
- Removing-nothing identities (full_candidate, candidate arm id) refused by guard (VARIANT_REMOVES_NOTHING).
- Removing-nothing identities refused by run_ablation (EXECUTION_ERROR, VARIANT_REMOVES_NOTHING).
- VariantSpec declaring no ablated mechanism is refused at construction.
- Malformed cases (non-mapping, missing/non-string case_id, missing fields, PHI) fail closed.
- Independence: neither ablations module nor this test module imports oracle/label files (AST scan).
"""

from __future__ import annotations

import ast
import json
import pathlib
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.aime import ablations as abl
from evaluation.venue2027.aime import candidate as cand
from evaluation.venue2027.aime.ablations import (
    ABLATION_REGISTRY,
    FAULT_FAMILY_IDS,
    NON_ABLATION_IDENTITIES,
    PREDICTED_VERDICTS,
    RC_CASE_ID_MISSING,
    RC_CASE_ID_NOT_STRING,
    RC_CASE_NOT_AN_OBJECT,
    RC_UNKNOWN_ABLATION_VARIANT,
    RC_VARIANT_REMOVES_NOTHING,
    REFERENCE_VARIANT_ID,
    VARIANT_COMMON_SAFETY_GATE,
    VARIANT_FULL_REFRESH,
    VARIANT_WITHOUT_CONSENT_RECHECK,
    VARIANT_WITHOUT_HISTORY_CONTRAST,
    VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE,
    AblationError,
    VariantSpec,
    case_fixtures,
    mechanistic_inference_matrix,
    refuse_unregistered_variant,
    run_ablation,
    variant_ids,
    verify_mechanistic_inference_matrix,
)

FAMILY_STABLE = abl.FAMILY_STABLE
FAMILY_WITHDRAWN = abl.FAMILY_WITHDRAWN
FAMILY_REVOKED = abl.FAMILY_REVOKED
FAMILY_ALLERGY = abl.FAMILY_ALLERGY

VERDICT_ADMIT = abl.VERDICT_ADMIT
VERDICT_REJECT = abl.VERDICT_REJECT
VERDICT_INDETERMINATE = abl.VERDICT_INDETERMINATE


@pytest.fixture(scope="function")
def fixtures() -> dict[str, dict[str, Any]]:
    """Fresh fixture instances per test."""
    builders = case_fixtures()
    return {family: builders[family]() for family in FAULT_FAMILY_IDS}


@pytest.fixture(scope="module")
def matrix() -> dict[str, Any]:
    return verify_mechanistic_inference_matrix()


def _payload(outcome: Outcome) -> dict[str, Any]:
    return json.loads(outcome.detail)


# ---------------------------------------------------------------------------
# Positive controls: registry declarations and spec integrity.
# ---------------------------------------------------------------------------


def test_registry_declares_exactly_the_preregistered_variants() -> None:
    expected = {
        VARIANT_WITHOUT_HISTORY_CONTRAST,
        VARIANT_WITHOUT_CONSENT_RECHECK,
        VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE,
        VARIANT_COMMON_SAFETY_GATE,
        VARIANT_FULL_REFRESH,
    }
    assert set(ABLATION_REGISTRY) == expected
    assert variant_ids() == tuple(ABLATION_REGISTRY)


def test_every_variant_declares_exactly_one_distinct_mechanism() -> None:
    mechanisms = [spec.ablated_mechanism for spec in ABLATION_REGISTRY.values()]
    assert all(isinstance(m, str) and m.strip() for m in mechanisms)
    assert len(set(mechanisms)) == len(mechanisms), "each variant must ablate a distinct mechanism"
    assert set(mechanisms) == {
        abl.ABLATED_HISTORY_CONTRAST,
        abl.ABLATED_CONSENT_RECHECK,
        abl.ABLATED_MEDICATION_ALLERGY_GATE,
        abl.ABLATED_COMMON_SAFETY_GATE,
        abl.ABLATED_FULL_REFRESH,
    }


def test_registry_specs_survive_their_own_guard() -> None:
    for spec in ABLATION_REGISTRY.values():
        assert refuse_unregistered_variant(spec.variant_id) == spec


# ---------------------------------------------------------------------------
# Positive controls: end-to-end execution on all families.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant_id", list(ABLATION_REGISTRY))
def test_every_variant_runs_on_every_family_determined(
    variant_id: str, fixtures: dict[str, dict[str, Any]]
) -> None:
    for family in FAULT_FAMILY_IDS:
        case = {**fixtures[family], "case_id": f"TEST-{family}"}
        outcome = run_ablation(variant_id, case)
        assert outcome.observed_outcome in (
            VERDICT_ADMIT,
            VERDICT_REJECT,
            VERDICT_INDETERMINATE,
        )
        payload = _payload(outcome)
        assert payload["variant_id"] == variant_id
        assert payload["ablated_mechanism"] == ABLATION_REGISTRY[variant_id].ablated_mechanism
        assert payload["case_id"] == f"TEST-{family}"
        assert isinstance(payload["decision"], str)
        assert isinstance(payload["reason_code"], str)


def test_reference_row_admits_stable_and_rejects_all_hazards(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    ref_stable = abl._run_reference(fixtures[FAMILY_STABLE])
    assert ref_stable.observed_outcome == VERDICT_ADMIT

    for family in (FAMILY_WITHDRAWN, FAMILY_REVOKED, FAMILY_ALLERGY):
        ref_hazard = abl._run_reference(fixtures[family])
        assert ref_hazard.observed_outcome == VERDICT_REJECT


# ---------------------------------------------------------------------------
# Positive controls: mechanistic inference matrix.
# ---------------------------------------------------------------------------


def test_mechanistic_inference_matrix_all_cells_match(matrix: dict[str, Any]) -> None:
    assert matrix["all_cells_match"] is True
    assert matrix["cell_count"] == len(PREDICTED_VERDICTS)


def test_matrix_covers_every_variant_and_family(matrix: dict[str, Any]) -> None:
    observed = matrix["observed_verdicts"]
    assert set(observed) == {REFERENCE_VARIANT_ID, *ABLATION_REGISTRY}
    for families in observed.values():
        assert set(families) == set(FAULT_FAMILY_IDS)


def test_matrix_predictions_are_prespecified_not_retrofitted() -> None:
    design = mechanistic_inference_matrix()
    for (variant_id, family), verdict in PREDICTED_VERDICTS.items():
        assert design["predicted_verdicts"][variant_id][family] == verdict


# ---------------------------------------------------------------------------
# Positive controls: single-mechanism bypass contrasts (central claims).
# ---------------------------------------------------------------------------


def test_removing_history_contrast_misses_withdrawal_hazard_candidate_catches(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Removing history contrast misses a withdrawal hazard the full candidate catches."""
    case = fixtures[FAMILY_WITHDRAWN]
    full_cand = abl._run_reference(case)
    assert full_cand.observed_outcome == VERDICT_REJECT
    assert full_cand.detail == cand.REASON_WITHDRAWN_MEDICATION

    ablated = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, case)
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert ablated.counted_as_success is True
    payload = _payload(ablated)
    assert payload["decision"] == cand.DECISION_SAFE
    assert payload["reason_code"] == cand.REASON_NO_HAZARD

    # Alias check
    ablated_alias = run_ablation("no_history_contrast", case)
    assert ablated_alias.observed_outcome == VERDICT_ADMIT


def test_removing_consent_recheck_admits_revoked_consent(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Removing consent recheck admits revoked consent the full candidate rejects."""
    case = fixtures[FAMILY_REVOKED]
    full_cand = abl._run_reference(case)
    assert full_cand.observed_outcome == VERDICT_REJECT
    assert full_cand.detail == cand.REASON_CONSENT_REVOKED

    ablated = run_ablation(VARIANT_WITHOUT_CONSENT_RECHECK, case)
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert ablated.counted_as_success is True
    payload = _payload(ablated)
    assert payload["decision"] == cand.DECISION_SAFE
    assert payload["reason_code"] == cand.REASON_NO_HAZARD


def test_removing_medication_allergy_gate_admits_allergen(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Removing medication/allergy gate admits allergen report the candidate rejects."""
    case = fixtures[FAMILY_ALLERGY]
    full_cand = abl._run_reference(case)
    assert full_cand.observed_outcome == VERDICT_REJECT
    assert full_cand.detail == cand.REASON_ALLERGEN_PRESENT

    ablated = run_ablation(VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, case)
    assert ablated.observed_outcome == VERDICT_ADMIT
    assert ablated.counted_as_success is True
    payload = _payload(ablated)
    assert payload["decision"] == cand.DECISION_SAFE
    assert payload["reason_code"] == cand.REASON_NO_HAZARD


def test_common_safety_gate_misses_all_temporal_hazards(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Common safety gate admits withdrawal, revocation, and allergy mid-task."""
    for family in (FAMILY_WITHDRAWN, FAMILY_REVOKED, FAMILY_ALLERGY):
        outcome = run_ablation(VARIANT_COMMON_SAFETY_GATE, fixtures[family])
        assert outcome.observed_outcome == VERDICT_ADMIT
        assert outcome.counted_as_success is True


def test_full_refresh_forces_regeneration_on_withdrawal(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Full refresh yields INDETERMINATE requiring full regeneration on withdrawal."""
    outcome = run_ablation(VARIANT_FULL_REFRESH, fixtures[FAMILY_WITHDRAWN])
    assert outcome.observed_outcome == VERDICT_INDETERMINATE
    assert outcome.counted_as_success is False
    payload = _payload(outcome)
    assert payload["decision"] == cand.DECISION_INDETERMINATE
    assert payload["reason_code"] == cand.REASON_WITHDRAWN_MEDICATION


# ---------------------------------------------------------------------------
# Positive controls: single-factor isolation.
# ---------------------------------------------------------------------------


def test_single_factor_isolation(fixtures: dict[str, dict[str, Any]]) -> None:
    """Each ablation keeps non-ablated mechanisms fully enforced."""
    # without_history_contrast still rejects revoked consent and allergen
    assert (
        run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, fixtures[FAMILY_REVOKED]).observed_outcome
        == VERDICT_REJECT
    )
    assert (
        run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, fixtures[FAMILY_ALLERGY]).observed_outcome
        == VERDICT_REJECT
    )

    # without_consent_recheck still rejects medication withdrawal and allergen
    assert (
        run_ablation(VARIANT_WITHOUT_CONSENT_RECHECK, fixtures[FAMILY_WITHDRAWN]).observed_outcome
        == VERDICT_REJECT
    )
    assert (
        run_ablation(VARIANT_WITHOUT_CONSENT_RECHECK, fixtures[FAMILY_ALLERGY]).observed_outcome
        == VERDICT_REJECT
    )

    # without_medication_allergy_gate still rejects revoked consent and medication withdrawal
    assert (
        run_ablation(
            VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, fixtures[FAMILY_REVOKED]
        ).observed_outcome
        == VERDICT_REJECT
    )
    assert (
        run_ablation(
            VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, fixtures[FAMILY_WITHDRAWN]
        ).observed_outcome
        == VERDICT_REJECT
    )


def test_determinism(fixtures: dict[str, dict[str, Any]]) -> None:
    """Identical runs yield byte-identical outcomes and digests."""
    case = fixtures[FAMILY_STABLE]
    out1 = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, case)
    out2 = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, case)
    assert out1 == out2
    assert out1.detail == out2.detail


# ---------------------------------------------------------------------------
# Adversarial controls: unregistered and nothing-removing variant refusals.
# ---------------------------------------------------------------------------


def test_unregistered_variant_refused_by_guard() -> None:
    with pytest.raises(AblationError) as exc_info:
        refuse_unregistered_variant("unregistered_variant_name")
    assert exc_info.value.reason_code == RC_UNKNOWN_ABLATION_VARIANT


def test_unregistered_variant_refused_by_run_ablation(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    outcome = run_ablation("unregistered_variant_name", fixtures[FAMILY_STABLE])
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert RC_UNKNOWN_ABLATION_VARIANT in outcome.detail


@pytest.mark.parametrize("identity", list(NON_ABLATION_IDENTITIES))
def test_removing_nothing_refused_by_guard(identity: str) -> None:
    with pytest.raises(AblationError) as exc_info:
        refuse_unregistered_variant(identity)
    assert exc_info.value.reason_code == RC_VARIANT_REMOVES_NOTHING


@pytest.mark.parametrize("identity", list(NON_ABLATION_IDENTITIES))
def test_removing_nothing_refused_by_run_ablation(
    identity: str, fixtures: dict[str, dict[str, Any]]
) -> None:
    outcome = run_ablation(identity, fixtures[FAMILY_STABLE])
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert RC_VARIANT_REMOVES_NOTHING in outcome.detail


def test_variant_spec_declaring_no_mechanism_refused_at_construction() -> None:
    with pytest.raises(AblationError) as exc_info:
        VariantSpec(
            variant_id="toy",
            title="Toy variant",
            ablated_mechanism="",
            description="Removes nothing",
            expected_effect="none",
            reuses=(),
            applied_by="test",
        )
    assert exc_info.value.reason_code == RC_VARIANT_REMOVES_NOTHING


# ---------------------------------------------------------------------------
# Adversarial controls: malformed inputs fail closed.
# ---------------------------------------------------------------------------


def test_malformed_case_not_an_object() -> None:
    outcome = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, ["not", "a", "dict"])
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert RC_CASE_NOT_AN_OBJECT in outcome.detail


def test_malformed_case_missing_case_id(fixtures: dict[str, dict[str, Any]]) -> None:
    bad = dict(fixtures[FAMILY_STABLE])
    del bad["case_id"]
    outcome = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, bad)
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    assert RC_CASE_ID_MISSING in outcome.detail


def test_malformed_case_non_string_case_id(fixtures: dict[str, dict[str, Any]]) -> None:
    bad = dict(fixtures[FAMILY_STABLE])
    bad["case_id"] = 12345
    outcome = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, bad)
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    assert RC_CASE_ID_NOT_STRING in outcome.detail


def test_malformed_case_phi_field_refused(fixtures: dict[str, dict[str, Any]]) -> None:
    bad = dict(fixtures[FAMILY_STABLE])
    bad["patient_name"] = "Alice Smith"
    outcome = run_ablation(VARIANT_WITHOUT_HISTORY_CONTRAST, bad)
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    assert "PHI_FIELDS" in outcome.detail


# ---------------------------------------------------------------------------
# Adversarial controls: independence assertion.
# ---------------------------------------------------------------------------


def test_no_oracle_or_label_import_in_ablations_or_test_module() -> None:
    """Ablations and test modules must not import oracle or label modules."""
    here = pathlib.Path(__file__).resolve()
    ablations_path = here.parent / "ablations.py"
    banned = ("independent_oracle", "oracle_kernel", "truth", "labels")

    for path in (here, ablations_path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for marker in banned:
                        assert marker not in alias.name, f"{path.name} imports {alias.name!r}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for marker in banned:
                    assert marker not in node.module, f"{path.name} imports {node.module!r}"
