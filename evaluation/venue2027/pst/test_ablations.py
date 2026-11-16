"""Tests for PST-ablation — causal mechanism ablation variants for ReceiptMin.

Positive controls:
- Every registered variant runs through the task-manifest signature
  ``run_ablation(name, case) -> Outcome`` on every frozen family and returns
  a determined Outcome (ADMIT/REJECT) with expected detail.
- Mechanistic inference matrix verifies all 25 variant x family cells
  against their preregistered predictions (``all_cells_match`` is True).
- Removing purpose-binding causes cross-purpose linkability:
  ``without_purpose_binding`` ADMITs cross-purpose linkage that ``full_candidate`` REJECTs.
- Removing epoch-key rotation causes long-term linkability:
  ``without_epoch_rotation`` ADMITs longitudinal cross-epoch linkage that ``full_candidate`` REJECTs.
- Removing retention enforcement causes post-retention exposure:
  ``without_retention_enforcement`` ADMITs expired data queries that ``full_candidate`` REJECTs.
- Common safety gate admits tampered proofs and lacks cryptographic assurance.
- Clean control: ``clean_reconstruction`` is admitted by all variants.
- Aliases resolve cleanly and determinism holds.

Adversarial controls (fail closed):
- Unregistered variant id is refused with ``UNKNOWN_ABLATION_VARIANT``.
- Identity removing no mechanism is refused with ``VARIANT_REMOVES_NOTHING``.
- VariantSpec declaring no ablated mechanism or impostor 'none' is refused at construction.
- Malformed cases (non-mapping, missing/empty case_id, empty workload) fail closed.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.pst import ablations as abl
from evaluation.venue2027.pst import candidate as cand

ALL_VARIANT_IDS = (
    abl.VARIANT_WITHOUT_PURPOSE_BINDING,
    abl.VARIANT_WITHOUT_EPOCH_ROTATION,
    abl.VARIANT_WITHOUT_RETENTION_ENFORCEMENT,
    abl.VARIANT_WITH_COMMON_SAFETY_GATE,
    abl.VARIANT_FULL_CANDIDATE,
)


@pytest.fixture(scope="function")
def fixtures() -> dict[str, dict[str, Any]]:
    """Fresh fixture dictionary per test function."""
    builders = abl.case_fixtures()
    return {family: builders[family]() for family in abl.FAULT_FAMILY_IDS}


# ---------------------------------------------------------------------------
# Positive controls: registry structure & declared mechanisms
# ---------------------------------------------------------------------------


def test_registry_structure_and_declared_mechanisms() -> None:
    assert set(abl.ABLATION_REGISTRY) == set(ALL_VARIANT_IDS)
    assert abl.variant_ids() == tuple(abl.ABLATION_REGISTRY)

    mechanisms = [spec.ablated_mechanism for spec in abl.ABLATION_REGISTRY.values()]
    assert len(mechanisms) == len(set(mechanisms)), "each ablation mechanism must be unique"

    assert cand.CANDIDATE_ID not in abl.ABLATION_REGISTRY
    assert abl.REFERENCE_VARIANT_ID == abl.VARIANT_FULL_CANDIDATE

    for spec in abl.ABLATION_REGISTRY.values():
        assert spec.title.strip()
        assert spec.description.strip()
        assert spec.expected_effect.strip()
        assert spec.applied_by.strip()
        assert len(spec.reuses) >= 1

    desc = abl.describe_ablations()
    assert desc["task_id"] == abl.ABLATION_TASK_ID
    assert desc["candidate_id"] == cand.CANDIDATE_ID
    assert set(desc["registry"]) == set(abl.ABLATION_REGISTRY)


@pytest.mark.parametrize("variant_id", ALL_VARIANT_IDS)
def test_variant_spec_to_dict_roundtrip(variant_id: str) -> None:
    spec = abl.ABLATION_REGISTRY[variant_id]
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
@pytest.mark.parametrize("family_id", abl.FAULT_FAMILY_IDS)
def test_every_variant_runs_on_every_family(
    variant_id: str,
    family_id: str,
    fixtures: dict[str, dict[str, Any]],
) -> None:
    case = fixtures[family_id]
    outcome = abl.run_ablation(variant_id, case)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in (abl.VERDICT_ADMIT, abl.VERDICT_REJECT)
    assert outcome.counted_as_success is True

    detail = json.loads(outcome.detail)
    assert detail["ablations_version"] == abl.PST_ABLATIONS_VERSION
    assert detail["variant_id"] == variant_id
    assert detail["ablated_mechanism"] == abl.ABLATION_REGISTRY[variant_id].ablated_mechanism
    assert detail["case_id"] == case["case_id"]


# ---------------------------------------------------------------------------
# Positive controls: mechanistic inference matrix
# ---------------------------------------------------------------------------


def test_mechanistic_inference_matrix_design_record() -> None:
    matrix = abl.mechanistic_inference_matrix()
    assert matrix["ablations_version"] == abl.PST_ABLATIONS_VERSION
    assert matrix["task_id"] == abl.ABLATION_TASK_ID
    assert matrix["reference_variant"] == abl.REFERENCE_VARIANT_ID
    assert set(matrix["variants"]) == set(abl.ABLATION_REGISTRY)

    for variant_id in abl.ABLATION_REGISTRY:
        for family_id in abl.FAULT_FAMILY_IDS:
            assert matrix["predicted_verdicts"][variant_id][family_id] in (
                abl.VERDICT_ADMIT,
                abl.VERDICT_REJECT,
            )

    degradation = matrix["degradation_axes"]
    for variant_id in (
        abl.VARIANT_WITHOUT_PURPOSE_BINDING,
        abl.VARIANT_WITHOUT_EPOCH_ROTATION,
        abl.VARIANT_WITHOUT_RETENTION_ENFORCEMENT,
        abl.VARIANT_WITH_COMMON_SAFETY_GATE,
    ):
        assert degradation[variant_id]["measurably_degraded"] is True

    # Full candidate is the reference ceiling, not degraded
    assert degradation[abl.VARIANT_FULL_CANDIDATE]["measurably_degraded"] is False


def test_verify_mechanistic_inference_matrix_all_cells_match() -> None:
    verification = abl.verify_mechanistic_inference_matrix()
    assert verification["all_cells_match"] is True
    assert verification["cell_count"] == len(abl.FAULT_FAMILY_IDS) * len(abl.ABLATION_REGISTRY)
    assert verification["observed_degradation"] == verification["predicted_degradation"]

    for cell in verification["cells"]:
        assert cell["match"] is True, f"Mismatch in cell {cell}"


# ---------------------------------------------------------------------------
# Positive controls: removing specific mechanisms causes expected failures
# ---------------------------------------------------------------------------


def test_removing_purpose_binding_causes_cross_purpose_linkability(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Removing purpose binding collapses purpose isolation, admitting cross-purpose linkage."""
    case = fixtures[abl.FAMILY_CROSS_PURPOSE_LINKAGE]

    # Full candidate protects privacy: distinct pseudonyms across purposes -> REJECT linkage
    ref_outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case)
    assert ref_outcome.observed_outcome == abl.VERDICT_REJECT

    # Without purpose binding: identical pseudonyms across purposes -> ADMIT linkage leak
    ablation_outcome = abl.run_ablation(abl.VARIANT_WITHOUT_PURPOSE_BINDING, case)
    assert ablation_outcome.observed_outcome == abl.VERDICT_ADMIT

    # Direct pseudonym check
    psn_clinical = abl.derive_pseudonym(
        abl.VARIANT_FULL_CANDIDATE, "tnt-1", "clinical_care", "epoch-1", "patient-001"
    )
    psn_research = abl.derive_pseudonym(
        abl.VARIANT_FULL_CANDIDATE, "tnt-1", "research_analytics", "epoch-1", "patient-001"
    )
    assert psn_clinical != psn_research, "candidate must isolate pseudonyms across purposes"

    psn_ablation_clinical = abl.derive_pseudonym(
        abl.VARIANT_WITHOUT_PURPOSE_BINDING, "tnt-1", "clinical_care", "epoch-1", "patient-001"
    )
    psn_ablation_research = abl.derive_pseudonym(
        abl.VARIANT_WITHOUT_PURPOSE_BINDING,
        "tnt-1",
        "research_analytics",
        "epoch-1",
        "patient-001",
    )
    assert (
        psn_ablation_clinical == psn_ablation_research
    ), "without purpose-binding, pseudonyms must collide across purposes"


def test_removing_epoch_rotation_causes_long_term_linkability(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Removing epoch rotation uses static keys, admitting longitudinal cross-epoch linkage."""
    case = fixtures[abl.FAMILY_LONG_TERM_EPOCH_LINKAGE]

    # Full candidate rotates keys per epoch -> REJECT linkage
    ref_outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case)
    assert ref_outcome.observed_outcome == abl.VERDICT_REJECT

    # Without epoch rotation: static key -> ADMIT linkage leak
    ablation_outcome = abl.run_ablation(abl.VARIANT_WITHOUT_EPOCH_ROTATION, case)
    assert ablation_outcome.observed_outcome == abl.VERDICT_ADMIT

    # Direct pseudonym check
    psn_epoch1 = abl.derive_pseudonym(
        abl.VARIANT_FULL_CANDIDATE, "tnt-1", "clinical_care", "epoch-1", "patient-002"
    )
    psn_epoch2 = abl.derive_pseudonym(
        abl.VARIANT_FULL_CANDIDATE, "tnt-1", "clinical_care", "epoch-2", "patient-002"
    )
    assert psn_epoch1 != psn_epoch2, "candidate must rotate pseudonyms across epochs"

    psn_ablation_epoch1 = abl.derive_pseudonym(
        abl.VARIANT_WITHOUT_EPOCH_ROTATION, "tnt-1", "clinical_care", "epoch-1", "patient-002"
    )
    psn_ablation_epoch2 = abl.derive_pseudonym(
        abl.VARIANT_WITHOUT_EPOCH_ROTATION, "tnt-1", "clinical_care", "epoch-2", "patient-002"
    )
    assert (
        psn_ablation_epoch1 == psn_ablation_epoch2
    ), "without epoch rotation, pseudonyms must collide across epochs"


def test_removing_retention_enforcement_causes_post_retention_exposure(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Removing retention enforcement retains data indefinitely, exposing expired fields."""
    case = fixtures[abl.FAMILY_POST_RETENTION_EXPOSURE]

    # Full candidate purges expired data -> REJECT
    ref_outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case)
    assert ref_outcome.observed_outcome == abl.VERDICT_REJECT

    # Without retention enforcement -> ADMIT (expired data exposed)
    ablation_outcome = abl.run_ablation(abl.VARIANT_WITHOUT_RETENTION_ENFORCEMENT, case)
    assert ablation_outcome.observed_outcome == abl.VERDICT_ADMIT


def test_common_safety_gate_admits_tampered_proofs(
    fixtures: dict[str, dict[str, Any]],
) -> None:
    """Common safety gate lacks cryptographic digest checks, admitting tampered claims."""
    case = fixtures[abl.FAMILY_TAMPERED_WITNESS_PROOF]

    # Full candidate verifies cryptographic omitted_field_digest -> REJECT
    ref_outcome = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, case)
    assert ref_outcome.observed_outcome == abl.VERDICT_REJECT

    # Common safety gate lacks crypto verification -> ADMIT
    ablation_outcome = abl.run_ablation(abl.VARIANT_WITH_COMMON_SAFETY_GATE, case)
    assert ablation_outcome.observed_outcome == abl.VERDICT_ADMIT


def test_clean_control_admitted_by_all_variants(fixtures: dict[str, dict[str, Any]]) -> None:
    """Clean authorized query is admitted by reference ceiling and all variants."""
    case = fixtures[abl.FAMILY_CLEAN_RECONSTRUCTION]

    for variant_id in abl.ABLATION_REGISTRY:
        outcome = abl.run_ablation(variant_id, case)
        assert outcome.observed_outcome == abl.VERDICT_ADMIT, f"{variant_id} failed clean control"


def test_variant_aliases_resolve_cleanly(fixtures: dict[str, dict[str, Any]]) -> None:
    case = fixtures[abl.FAMILY_CLEAN_RECONSTRUCTION]
    for alias, canonical in abl.VARIANT_ALIASES.items():
        spec = abl.refuse_unregistered_variant(alias)
        assert spec.variant_id == canonical

        outcome_alias = abl.run_ablation(alias, case)
        outcome_canonical = abl.run_ablation(canonical, case)
        assert outcome_alias.observed_outcome == outcome_canonical.observed_outcome
        assert outcome_alias.counted_as_success == outcome_canonical.counted_as_success


def test_determinism_and_freeze(fixtures: dict[str, dict[str, Any]]) -> None:
    case = fixtures[abl.FAMILY_CROSS_PURPOSE_LINKAGE]
    run1 = abl.run_ablation(abl.VARIANT_WITHOUT_PURPOSE_BINDING, case)
    run2 = abl.run_ablation(abl.VARIANT_WITHOUT_PURPOSE_BINDING, case)
    assert run1.observed_outcome == run2.observed_outcome
    assert run1.detail == run2.detail

    assert abl.PREDICTED_VERDICTS == dict(abl.PREDICTED_VERDICTS)


# ---------------------------------------------------------------------------
# Adversarial controls: refusals & fail-closed behavior
# ---------------------------------------------------------------------------


def test_adversarial_refuse_unregistered_variant() -> None:
    for bad in ("unregistered_variant_x", "unknown_ablation", "allow_all"):
        with pytest.raises(abl.AblationError) as exc_info:
            abl.refuse_unregistered_variant(bad)
        assert exc_info.value.reason_code == abl.RC_UNKNOWN_ABLATION_VARIANT

        case = {"case_id": "test-unregistered", "events": []}
        outcome = abl.run_ablation(bad, case)
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.counted_as_success is False
        assert abl.RC_UNKNOWN_ABLATION_VARIANT in outcome.detail


def test_adversarial_refuse_removing_nothing() -> None:
    for identity in (cand.CANDIDATE_ID, "PST-candidate", "candidate", "removes_nothing"):
        with pytest.raises(abl.AblationError) as exc_info:
            abl.refuse_unregistered_variant(identity)
        assert exc_info.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING

        case = {"case_id": "test-removing-nothing", "events": []}
        outcome = abl.run_ablation(identity, case)
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.counted_as_success is False
        assert abl.RC_VARIANT_REMOVES_NOTHING in outcome.detail


def test_adversarial_spec_declaring_no_mechanism_refused() -> None:
    with pytest.raises(abl.AblationError) as exc_info:
        abl.VariantSpec(
            variant_id="empty_mechanism",
            title="Empty",
            ablated_mechanism="",
            description="desc",
            expected_effect="effect",
            reuses=("candidate",),
            applied_by="hook",
        )
    assert exc_info.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING

    with pytest.raises(abl.AblationError) as exc_info2:
        abl.VariantSpec(
            variant_id="whitespace_mechanism",
            title="Whitespace",
            ablated_mechanism="   ",
            description="desc",
            expected_effect="effect",
            reuses=("candidate",),
            applied_by="hook",
        )
    assert exc_info2.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING

    with pytest.raises(abl.AblationError) as exc_info3:
        abl.VariantSpec(
            variant_id="impostor_none",
            title="Impostor None",
            ablated_mechanism="none",
            description="desc",
            expected_effect="effect",
            reuses=("candidate",),
            applied_by="hook",
        )
    assert exc_info3.value.reason_code == abl.RC_VARIANT_REMOVES_NOTHING


def test_adversarial_malformed_cases() -> None:
    # Not a mapping
    res1 = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, "not a mapping")  # type: ignore[arg-type]
    assert res1.observed_outcome == "EXECUTION_ERROR"
    assert abl.RC_CASE_NOT_AN_OBJECT in res1.detail

    # Missing case_id
    res2 = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"events": []})
    assert res2.observed_outcome == "INDETERMINATE"
    assert abl.RC_CASE_ID_MISSING in res2.detail

    # Non-string case_id
    res3 = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"case_id": 12345, "events": []})
    assert res3.observed_outcome == "INDETERMINATE"
    assert abl.RC_CASE_ID_NOT_STRING in res3.detail

    # Missing events and query
    res4 = abl.run_ablation(abl.VARIANT_FULL_CANDIDATE, {"case_id": "c1"})
    assert res4.observed_outcome == "INDETERMINATE"
    assert abl.RC_WORKLOAD_MALFORMED in res4.detail
