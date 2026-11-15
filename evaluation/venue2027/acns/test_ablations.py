"""Tests for ACNS-ablation — SoK reference-class ablation variants (synthetic only).

Positive controls: every registered reference class runs on every synthetic
evidence record via the task-manifest signature ``run_ablation(name, case)``,
returns structured JSON-serializable verdicts, and B3 (omits nothing) accepts
the fully-bound record. The mechanistic inference matrix is verified against
EXECUTED behavior: every ``detects`` cell fired, every ``blind`` cell stayed
silent, and each weaker class demonstrably misses a gap that B3 catches
(RQ2 witnesses at the ablation level).

Adversarial controls (fail-closed): an unregistered variant is refused
(``UNKNOWN_ABLATION_VARIANT``); a variant that omits nothing but is NOT the
registered B3 row is refused by the same gate; malformed cases and unknown
fixture records are first-class refusals, never counted as acceptances.
"""

from __future__ import annotations

import json
import typing

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.acns import _smoke_fixtures, ablations, baselines

ALL_RECORD_KEYS = sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS)
WEAKER_VARIANTS = (ablations.VARIANT_B0, ablations.VARIANT_B1, ablations.VARIANT_B2)


def _case(record_id: str, variant: str, case_id: str | None = None) -> dict[str, typing.Any]:
    return {
        "case_id": case_id or f"{record_id}/{variant}",
        "record_id": record_id,
        "variant": variant,
        "dataset": _smoke_fixtures.FIXTURE_DATASET,
    }


def _verdict(outcome: Outcome) -> dict[str, typing.Any]:
    return json.loads(outcome.detail.split(" | ")[0])


def _detected_codes(outcome: Outcome) -> set[str]:
    return {gap["gap_code"] for gap in _verdict(outcome)["gaps"]}


def _executed_detection_map() -> dict[str, set[str]]:
    """Run every variant over every fixture case and collect fired gap codes."""
    detected: dict[str, set[str]] = {}
    for name in ablations.ABLATION_REGISTRY:
        fired: set[str] = set()
        for record_id, variant in ALL_RECORD_KEYS:
            outcome = ablations.run_ablation(name, _case(record_id, variant))
            if outcome.observed_outcome == "REJECT":
                fired |= _detected_codes(outcome)
        detected[name] = fired
    return detected


# ---------------------------------------------------------------------------
# Positive controls: every registered reference class runs on every record.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant_id", ablations.ABLATION_IDS)
@pytest.mark.parametrize("record_key", ALL_RECORD_KEYS)
def test_positive_every_variant_runs_every_record(
    variant_id: str, record_key: tuple[str, str]
) -> None:
    record_id, variant = record_key
    outcome = ablations.run_ablation(variant_id, _case(record_id, variant))
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT", "NOT_RUN_EXTERNAL")
    if outcome.observed_outcome != "NOT_RUN_EXTERNAL":
        verdict = _verdict(outcome)
        assert verdict["baseline_id"] == variant_id
        assert verdict["omitted_component"] == (
            ablations.COMPONENT_NONE
            if variant_id == ablations.VARIANT_B3
            else ablations.ABLATION_REGISTRY[variant_id].omitted_component
        )
        for gap in verdict["gaps"]:
            assert gap["gap_code"] in baselines.KNOWN_GAP_CODES


def test_positive_b3_omits_nothing_and_accepts_fully_bound_record() -> None:
    """The B3 row omits NOTHING and accepts the fully-bound record at L3."""
    spec = ablations.ABLATION_REGISTRY[ablations.VARIANT_B3]
    assert spec.omitted_component == ablations.COMPONENT_NONE
    outcome = ablations.run_ablation(ablations.VARIANT_B3, _case("sok-claim-record-1", "bound"))
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    verdict = _verdict(outcome)
    assert verdict["granted_level"] == "L3-EXECUTED"
    assert verdict["gaps"] == []


@pytest.mark.parametrize(
    ("variant_id", "record_id", "variant"),
    [
        (ablations.VARIANT_B0, "sok-claim-record-2", "downgraded"),
        (ablations.VARIANT_B1, "sok-claim-record-2", "downgraded"),
        (ablations.VARIANT_B2, "sok-claim-record-2", "downgraded"),
    ],
)
def test_positive_weaker_stances_accept_downgraded_record(
    variant_id: str, record_id: str, variant: str
) -> None:
    """Each weaker class executes the SAME suite and shows its own semantics."""
    outcome = ablations.run_ablation(variant_id, _case(record_id, variant))
    assert outcome.observed_outcome == "ADMIT"


def test_positive_verdict_payload_is_json_serializable_and_typed() -> None:
    outcome = ablations.run_ablation(ablations.VARIANT_B1, _case("sok-claim-record-4", "replayed"))
    payload = json.loads(outcome.detail)
    json.dumps(payload)  # must not raise
    assert set(payload) >= {
        "baseline_id",
        "case_id",
        "granted_level",
        "verdict",
        "reason_code",
        "gaps",
        "ablation_version",
        "omitted_component",
        "blind_gap_codes",
    }
    assert payload["ablation_version"] == ablations.ACNS_ABLATIONS_VERSION


def test_positive_inference_matrix_covers_full_register_and_all_variants() -> None:
    matrix = ablations.inference_matrix()
    assert set(matrix) == baselines.KNOWN_GAP_CODES
    for cells in matrix.values():
        assert set(cells) == set(ablations.ABLATION_REGISTRY)
        for cell in cells.values():
            assert cell in (
                ablations.CELL_DETECTS,
                ablations.CELL_BLIND,
                ablations.CELL_NOT_APPLICABLE,
            )


def test_positive_inference_matrix_verified_against_executed_behavior() -> None:
    """Every detects cell fired; every blind cell stayed silent (mechanism proof)."""
    detected = _executed_detection_map()
    assert ablations.verify_inference_matrix(detected) is True


def test_positive_each_weaker_class_misses_a_gap_b3_catches() -> None:
    """The positive-witness separation: weaker classes demonstrably miss gaps."""
    detected = _executed_detection_map()
    b3 = detected[ablations.VARIANT_B3]
    assert "G2_RECEIPT_AS_EXECUTION" in b3  # downgrade witness
    assert "G4_SIGNATURE_AS_CONTEXT" in b3  # replay witness
    assert "G7_LEVEL_IMPLICIT_UPGRADE" in b3  # unbound witness
    for name in WEAKER_VARIANTS:
        missed = b3 - detected[name]
        assert missed, f"{name} unexpectedly detects everything B3 detects"
    # Specific defining blind spots, each mechanistically tied to the omitted
    # component:
    assert "G4_SIGNATURE_AS_CONTEXT" in (
        b3 - detected[ablations.VARIANT_B1]
    )  # B1 omits the receipt binding -> transplant undetectable
    assert "G2_RECEIPT_AS_EXECUTION" in (
        b3 - detected[ablations.VARIANT_B2]
    )  # B2 omits all artifacts -> anchor gone
    assert detected[ablations.VARIANT_B0] == set()  # B0 detects nothing at all


def test_positive_suite_report_is_consistent_and_same_cases() -> None:
    report = ablations.run_ablation_suite()
    assert report["inference_matrix_verified"] is True
    assert set(report["outcome_grid"]) == set(ablations.ABLATION_REGISTRY)
    for grid in report["outcome_grid"].values():
        assert set(grid) == set(report["case_keys"])
    assert (
        report["comparison"]["gaps_missed_by_weaker_variants"][ablations.VARIANT_B0]
        == report["comparison"]["gaps_b3_catches"]
    )


# ---------------------------------------------------------------------------
# Adversarial controls: unregistered variants and omit-nothing impostors.
# ---------------------------------------------------------------------------


def test_adversarial_unregistered_variant_is_refused() -> None:
    for bad in ("B4-full-copy", "B0-attestation-only-forged", "ALLOW-ALL", ""):
        refusal = ablations.run_ablation(bad, _case("sok-claim-record-1", "bound"))
        assert refusal.observed_outcome == "INVALID_RESULT"
        assert refusal.counted_as_success is False
        assert "UNKNOWN_ABLATION_VARIANT" in refusal.detail


def test_adversarial_refuse_unregistered_variant_gate_is_exact() -> None:
    assert ablations.refuse_unregistered_variant(ablations.VARIANT_B3) is None
    assert ablations.refuse_unregistered_variant(ablations.VARIANT_B0) is None
    for bad in ("B3-full", "no-omission-variant", "B3"):
        gate = ablations.refuse_unregistered_variant(bad)
        assert gate is not None
        assert gate.observed_outcome == "INVALID_RESULT"
        assert "UNKNOWN_ABLATION_VARIANT" in gate.detail


def test_adversarial_variant_omitting_nothing_but_unregistered_is_refused() -> None:
    """Omit-nothing semantics belong ONLY to the registered B3 row.

    A caller-declared "variant that omits nothing" with a fresh name is not
    in the registry and must never run as the full reference: omission
    completeness is a property OF the registered row, not of the name's
    self-description.
    """
    impostor = "B3-omits-nothing-but-unregistered"
    assert impostor not in ablations.ABLATION_REGISTRY
    refusal = ablations.run_ablation(impostor, _case("sok-claim-record-1", "bound"))
    assert refusal.observed_outcome == "INVALID_RESULT"
    assert refusal.counted_as_success is False
    assert "UNKNOWN_ABLATION_VARIANT" in refusal.detail
    # The genuine registered row still runs and accepts the same record.
    genuine = ablations.run_ablation(ablations.VARIANT_B3, _case("sok-claim-record-1", "bound"))
    assert genuine.observed_outcome == "ADMIT"


def test_adversarial_blind_cells_never_fire_on_downgrade_and_replay() -> None:
    """Direct witnesses: each weak variant CANNOT fire its defining blind rows."""
    downgrade = _case("sok-claim-record-2", "downgraded")
    replay = _case("sok-claim-record-4", "replayed")
    unbound = _case("sok-claim-record-3", "unbound")

    b0_downgrade = ablations.run_ablation(ablations.VARIANT_B0, downgrade)
    assert b0_downgrade.observed_outcome == "ADMIT"
    assert _detected_codes(b0_downgrade) == set()  # structurally silent

    b1_replay = ablations.run_ablation(ablations.VARIANT_B1, replay)
    assert b1_replay.observed_outcome == "ADMIT"
    assert "G4_SIGNATURE_AS_CONTEXT" not in _detected_codes(b1_replay)

    b2_unbound = ablations.run_ablation(ablations.VARIANT_B2, unbound)
    assert b2_unbound.observed_outcome == "ADMIT"
    assert _detected_codes(b2_unbound) == set()

    # B3 rejects every one of these records with the corresponding register row.
    b3_downgrade = ablations.run_ablation(ablations.VARIANT_B3, downgrade)
    assert b3_downgrade.observed_outcome == "REJECT"
    assert "G2_RECEIPT_AS_EXECUTION" in _detected_codes(b3_downgrade)
    b3_replay = ablations.run_ablation(ablations.VARIANT_B3, replay)
    assert b3_replay.observed_outcome == "REJECT"
    assert "G4_SIGNATURE_AS_CONTEXT" in _detected_codes(b3_replay)
    b3_unbound = ablations.run_ablation(ablations.VARIANT_B3, unbound)
    assert b3_unbound.observed_outcome == "REJECT"
    assert "G7_LEVEL_IMPLICIT_UPGRADE" in _detected_codes(b3_unbound)


def test_adversarial_matrix_rejects_false_detects_cell() -> None:
    """A matrix claiming a blind variant detects its blind row must fail verify."""
    assert (
        ablations.verify_inference_matrix({ablations.VARIANT_B0: {"G2_RECEIPT_AS_EXECUTION"}})
        is False
    )


def test_adversarial_malformed_case_fails_closed() -> None:
    for bad in ({}, {"record_id": 7, "variant": "bound"}, "not-a-mapping", 42):
        outcome = ablations.run_ablation(ablations.VARIANT_B3, bad)
        assert outcome.observed_outcome in ("INVALID_RESULT", "NOT_RUN_EXTERNAL")
        assert outcome.counted_as_success is False


def test_adversarial_unknown_record_is_not_run_external_never_a_safe_accept() -> None:
    outcome = ablations.run_ablation(ablations.VARIANT_B3, _case("record-not-pinned", "bound"))
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
