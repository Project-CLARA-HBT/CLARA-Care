"""Tests for ACNS-candidate — SoK evidence-boundary ANALYSIS INSTRUMENT.

Positive controls: bound claims are accepted (IN_BOUNDARY); the downgrade
(receipt-quoted-as-execution), unbound, replayed-receipt, timestamp-only and
purpose-crossing claims are flagged as BOUNDARY_GAP with the CORRECT
pre-registered G-code from the threat-model register; INDETERMINATE claims are
retained, never coerced; the coverage matrix is computed exactly.

Adversarial controls (the SoK proof obligations):
- ABLATION CONTRAST: ablation_ignore_gaps() inflates coverage to an unsound
  1.0 in-boundary fraction with gap-register coverage 0.0 on the SAME corpus —
  proving gap detection is the instrument and the accounting is not.
- describe_mechanism() asserts the ANALYTIC INSTRUMENT contribution class and
  contains NO new-mechanism claim.
- determinism: repeated classifications and matrices are byte-identical.
- synthetic-only: every input is a synthetic-acns-2027 fixture or inline
  literal; the module performs no I/O, no clock, no randomness.
"""

from __future__ import annotations

import json
import typing

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.acns import _smoke_fixtures, candidate

ALL_RECORDS = sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS)


def _case(record_id: str, variant: str, case_id: str | None = None) -> dict[str, typing.Any]:
    return {
        "case_id": case_id or f"{record_id}/{variant}",
        "record_id": record_id,
        "variant": variant,
        "dataset": _smoke_fixtures.FIXTURE_DATASET,
    }


def _payload(outcome: Outcome) -> dict[str, typing.Any]:
    return json.loads(outcome.detail)


def _bound_claim(**overrides: typing.Any) -> dict[str, typing.Any]:
    claim: dict[str, typing.Any] = {
        "claim_id": "claim-exec-1",
        "dimension": "execution",
        "asserted_level": "L3-EXECUTED",
        "evidence_bindings": [
            {
                "dimension": "execution",
                "binding_kind": "attested-bound",
                "receipt_id": "rcpt-r1",
            }
        ],
        "attested_execution": True,
        "schedule_checked_at_rely_time": True,
        "timestamp": "2026-11-15T00:00:00Z",
    }
    claim.update(overrides)
    return claim


def _receipts_table() -> dict[str, typing.Any]:
    return {
        "rcpt-r1": {
            "receipt_id": "rcpt-r1",
            "bound_to_claim_id": "claim-exec-1",
            "digest_binding": "sha256:" + "1" * 64,
            "schedule_checked_at_rely_time": True,
        }
    }


# ---------------------------------------------------------------------------
# Positive controls: bound claims are within the evidence boundary.
# ---------------------------------------------------------------------------


def test_positive_bound_claim_is_in_boundary() -> None:
    assessment = candidate.classify_claim(_bound_claim(), _receipts_table())
    assert assessment.boundary_status == "IN_BOUNDARY"
    assert assessment.gap_codes == ()
    assert assessment.reason_code == "OK"
    assert assessment.asserted_level == "L3-EXECUTED"
    assert assessment.to_dict()["instrument_id"] == candidate.CANDIDATE_ID


@pytest.mark.parametrize("record_key", ALL_RECORDS)
def test_positive_run_candidate_classifies_all_fixture_records(
    record_key: tuple[str, str],
) -> None:
    record_id, variant = record_key
    outcome = candidate.run_candidate(_case(record_id, variant), {"arm_id": candidate.CANDIDATE_ID})
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT")
    payload = _payload(outcome)
    assert payload["instrument_id"] == candidate.CANDIDATE_ID
    assert payload["assessments"]
    assert payload["coverage"]["total_claims"] >= 1


def test_positive_clean_fixture_record_is_fully_in_boundary() -> None:
    outcome = candidate.run_candidate(
        _case("sok-claim-record-1", "bound"), {"arm_id": candidate.CANDIDATE_ID}
    )
    assert outcome.observed_outcome == "ADMIT"
    payload = _payload(outcome)
    assert all(a["boundary_status"] == "IN_BOUNDARY" for a in payload["assessments"])


# ---------------------------------------------------------------------------
# Gap-register controls: each claimed implication failure gets its G-code.
# ---------------------------------------------------------------------------


def test_gap_receipt_quoted_as_execution_is_G2() -> None:
    # Downgrade: provider receipt bound to THIS claim but NO attested anchor
    # (a receipt alone caps execution claims at L2, threat model §6 G2).
    claim = _bound_claim(
        claim_id="claim-exec-1",
        evidence_bindings=[
            {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "rcpt-r1"}
        ],
        attested_execution=False,
    )
    assessment = candidate.classify_claim(claim, _receipts_table())
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G2_RECEIPT_AS_EXECUTION" in assessment.gap_codes


def test_gap_unbound_claim_is_G7_and_G9_free() -> None:
    # Unbound: asserted level floats free of the lattice (G7; not G9, the
    # dimension itself is a known lattice dimension).
    claim = _bound_claim(claim_id="claim-r3", evidence_bindings=[], dimension="receipt")
    claim["asserted_level"] = "L2-ACKNOWLEDGED"
    assessment = candidate.classify_claim(claim)
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G7_LEVEL_IMPLICIT_UPGRADE" in assessment.gap_codes
    assert "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE" not in assessment.gap_codes


def test_gap_replayed_receipt_is_G4() -> None:
    # Transplant: receipt bound to a DIFFERENT claim (signature-valid,
    # context-invalid).
    other = dict(_receipts_table()["rcpt-r1"])
    other["bound_to_claim_id"] = "claim-other"
    claim = _bound_claim(
        claim_id="claim-this",
        evidence_bindings=[
            {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "rcpt-r1"}
        ],
        attested_execution=True,
    )
    assessment = candidate.classify_claim(claim, {"rcpt-r1": other})
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G4_SIGNATURE_AS_CONTEXT" in assessment.gap_codes


def test_gap_transport_ack_read_as_processing_is_G1() -> None:
    claim = _bound_claim(
        claim_id="claim-g1",
        dimension="receipt",
        asserted_level="L2-ACKNOWLEDGED",
        evidence_bindings=[
            {"dimension": "receipt", "binding_kind": "transport-ack", "receipt_id": ""}
        ],
        attested_execution=False,
    )
    assessment = candidate.classify_claim(claim)
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G1_TRANSPORT_ACK_AS_PROCESSING" in assessment.gap_codes


def test_gap_execution_without_persisted_side_effect_is_G3() -> None:
    claim = _bound_claim(
        claim_id="claim-g3",
        dimension="consumption",
        asserted_level="L4-COMMITTED",
        attested_execution=True,
        consumption_record=False,
    )
    assessment = candidate.classify_claim(claim)
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G3_EXECUTION_AS_CONSUMPTION" in assessment.gap_codes


def test_gap_no_rely_time_schedule_check_is_G5() -> None:
    claim = _bound_claim(schedule_checked_at_rely_time=False)
    assessment = candidate.classify_claim(claim, _receipts_table())
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G5_MINT_TIME_AS_RELY_TIME" in assessment.gap_codes


def test_gap_timestamp_only_claim_is_G6() -> None:
    claim = _bound_claim(timestamp="")
    assessment = candidate.classify_claim(claim, _receipts_table())
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G6_TIMESTAMP_AS_ORDERING" in assessment.gap_codes


def test_gap_purpose_scope_crossing_is_G8() -> None:
    claim = _bound_claim(
        claim_id="claim-g8",
        purpose_scope={"authorized_purpose": "care_plan_read", "claimed_purpose": "billing_export"},
        purpose_binding_checked=False,
    )
    assessment = candidate.classify_claim(claim, _receipts_table())
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G8_AUTHORITY_SCOPE_CROSSING" in assessment.gap_codes


def test_gap_unknown_dimension_is_G9() -> None:
    claim = _bound_claim(
        claim_id="claim-g9", dimension="telepathy", asserted_level="L2-ACKNOWLEDGED"
    )
    assessment = candidate.classify_claim(claim)
    assert assessment.boundary_status == "BOUNDARY_GAP"
    assert "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE" in assessment.gap_codes


# ---------------------------------------------------------------------------
# INDETERMINATE retention: undecidable inputs are never coerced.
# ---------------------------------------------------------------------------


def test_indeterminate_missing_asserted_level_is_retained() -> None:
    assessment = candidate.classify_claim({"claim_id": "x", "dimension": "execution"})
    assert assessment.boundary_status == "INDETERMINATE"
    assert assessment.undecidable_fields == ("asserted_level",)
    assert assessment.gap_codes == ()


def test_indeterminate_missing_dimension_is_retained() -> None:
    assessment = candidate.classify_claim({"claim_id": "x", "asserted_level": "L2"})
    assert assessment.boundary_status == "INDETERMINATE"
    assert assessment.undecidable_fields == ("dimension",)


def test_indeterminate_malformed_claim_is_fail_closed() -> None:
    assessment = candidate.classify_claim("not-a-mapping")  # type: ignore[arg-type]
    assert assessment.boundary_status == "INDETERMINATE"
    assert assessment.reason_code == "MALFORMED_CLAIM"


# ---------------------------------------------------------------------------
# Coverage matrix: exact accounting across records.
# ---------------------------------------------------------------------------


def test_coverage_matrix_counts_exact_partitions() -> None:
    claims = [
        _bound_claim(),  # in-boundary
        _bound_claim(  # G2 gap: receipt bound to THIS claim, no attested anchor
            claim_id="claim-exec-1",
            attested_execution=False,
            evidence_bindings=[
                {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "rcpt-r1"}
            ],
        ),
        {"claim_id": "c3", "dimension": "execution"},  # indeterminate
    ]
    coverage = candidate.coverage_matrix(claims, _receipts_table())
    assert coverage.total_claims == 3
    assert coverage.in_boundary_count == 1
    assert coverage.boundary_gap_count == 1
    assert coverage.indeterminate_count == 1
    assert coverage.in_boundary_fraction == pytest.approx(1 / 3)
    assert coverage.gap_code_counts["G2_RECEIPT_AS_EXECUTION"] == 1
    assert coverage.ablated is False
    assert len(coverage.digest) == 16


def test_coverage_matrix_over_full_fixture_corpus() -> None:
    claims: list[dict[str, typing.Any]] = []
    for (_rid, _variant), record in sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS.items()):
        claim_case = record["claims_case"]
        assert isinstance(claim_case, dict)
        claims.extend(claim_case["claims"])
    coverage = candidate.coverage_matrix(claims)
    assert coverage.total_claims == len(claims)
    assert (
        coverage.in_boundary_count + coverage.boundary_gap_count + coverage.indeterminate_count
        == coverage.total_claims
    )
    exercised = sum(1 for count in coverage.gap_code_counts.values() if count > 0)
    assert coverage.gap_register_coverage == pytest.approx(exercised / len(candidate.GAP_REGISTER))


def test_coverage_matrix_empty_corpus_is_all_zero() -> None:
    coverage = candidate.coverage_matrix([])
    assert coverage.total_claims == 0
    assert coverage.in_boundary_fraction == 0.0
    assert coverage.gap_register_coverage == 0.0


# ---------------------------------------------------------------------------
# Adversarial: the ablation proves gap detection IS the instrument.
# ---------------------------------------------------------------------------


def test_adversarial_ablation_inflates_coverage_on_gap_corpus() -> None:
    # Same corpus, same accounting, only gap detection switched off: the
    # in-boundary fraction inflates to 1.0 and register coverage collapses
    # to 0.0 — the measurable proof that the gap detection, not the
    # accounting, is the instrument.
    claims = [
        _bound_claim(),
        _bound_claim(  # G2 gap: receipt bound to THIS claim, no attested anchor
            claim_id="claim-exec-1",
            attested_execution=False,
            evidence_bindings=[
                {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "rcpt-r1"}
            ],
        ),
        _bound_claim(claim_id="c3", timestamp=""),
    ]
    real = candidate.coverage_matrix(claims, _receipts_table())
    ablated = candidate.ablation_ignore_gaps(claims, _receipts_table())
    assert real.boundary_gap_count >= 2
    assert real.in_boundary_fraction < 1.0
    assert ablated.ablated is True
    assert ablated.boundary_gap_count == 0
    assert ablated.in_boundary_count == ablated.total_claims
    assert ablated.in_boundary_fraction == 1.0
    assert ablated.gap_register_coverage == 0.0
    assert all(count == 0 for count in ablated.gap_code_counts.values())
    assert ablated.in_boundary_fraction > real.in_boundary_fraction
    assert ablated.gap_register_coverage < real.gap_register_coverage


def test_adversarial_ablation_on_full_fixture_corpus_collapses_register() -> None:
    claims = [
        claim
        for record in _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS.values()
        for claim in record["claims_case"]["claims"]  # type: ignore[union-attr]
    ]
    real = candidate.coverage_matrix(claims)
    ablated = candidate.ablation_ignore_gaps(claims)
    assert real.boundary_gap_count > 0
    assert ablated.boundary_gap_count == 0
    assert ablated.in_boundary_fraction == 1.0
    assert ablated.gap_register_coverage == 0.0
    assert real.gap_register_coverage > ablated.gap_register_coverage


# ---------------------------------------------------------------------------
# Adversarial: contribution-class guard (SoK, not a mechanism).
# ---------------------------------------------------------------------------


def test_adversarial_describe_mechanism_declares_analytic_instrument() -> None:
    description = candidate.describe_mechanism()
    assert description["contribution_class"] == "ANALYTIC_INSTRUMENT"
    assert description["is_mechanism"] is False
    assert description["is_new_mechanism_claim"] is False
    assert description["study_class"] == "SoK"
    assert description["runtime_enforcement"] is False
    assert description["detects_attacks"] is False
    assert description["prevents_attacks"] is False
    assert description["gates_enforced"] == []
    blob = json.dumps(description).lower()
    assert "not a mechanism" in blob


# ---------------------------------------------------------------------------
# Adversarial: determinism and synthetic-only purity.
# ---------------------------------------------------------------------------


def test_determinism_classify_and_coverage_are_repeatable() -> None:
    claim = _bound_claim(
        attested_execution=False,
        evidence_bindings=[
            {"dimension": "execution", "binding_kind": "receipt-bound", "receipt_id": "rcpt-r1"}
        ],
    )
    first = candidate.classify_claim(claim, _receipts_table()).to_dict()
    second = candidate.classify_claim(claim, _receipts_table()).to_dict()
    assert first == second
    claims = [claim, _bound_claim()]
    matrix_one = candidate.coverage_matrix(claims, _receipts_table()).to_dict()
    matrix_two = candidate.coverage_matrix(claims, _receipts_table()).to_dict()
    assert matrix_one == matrix_two
    run_one = candidate.run_candidate(
        _case("sok-claim-record-2", "downgraded"), {"arm_id": candidate.CANDIDATE_ID}
    ).detail
    run_two = candidate.run_candidate(
        _case("sok-claim-record-2", "downgraded"), {"arm_id": candidate.CANDIDATE_ID}
    ).detail
    assert run_one == run_two


def test_adversarial_unknown_arm_refused() -> None:
    outcome = candidate.run_candidate(_case("sok-claim-record-1", "bound"), {"arm_id": "ghost-arm"})
    assert outcome.observed_outcome == "INVALID_RESULT"
    assert "UNKNOWN_ARM" in outcome.detail


def test_adversarial_malformed_case_fail_closed() -> None:
    outcome = candidate.run_candidate("not-a-mapping", {"arm_id": candidate.CANDIDATE_ID})  # type: ignore[arg-type]
    assert outcome.observed_outcome == "INVALID_RESULT"
    assert "MALFORMED_CASE" in outcome.detail


def test_adversarial_unknown_record_is_not_run_external() -> None:
    outcome = candidate.run_candidate(
        _case("no-such-record", "no-such-variant"), {"arm_id": candidate.CANDIDATE_ID}
    )
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.retriable is True
    assert outcome.counted_as_success is False


def test_adversarial_downgraded_fixture_record_is_rejected_with_G2() -> None:
    outcome = candidate.run_candidate(
        _case("sok-claim-record-2", "downgraded"), {"arm_id": candidate.CANDIDATE_ID}
    )
    assert outcome.observed_outcome == "REJECT"
    payload = _payload(outcome)
    gap_codes = [code for a in payload["assessments"] for code in a["gap_codes"]]
    assert "G2_RECEIPT_AS_EXECUTION" in gap_codes


def test_adversarial_synthetic_only_dataset_markers() -> None:
    # Every fixture record declares the synthetic dataset; the instrument
    # description names synthetic-acns-2027 and no network/provider surface.
    assert _smoke_fixtures.FIXTURE_DATASET == "synthetic-acns-2027"
    description = candidate.describe_mechanism()
    assert description["dataset"] == "synthetic-acns-2027"
    source = candidate.__doc__ or ""
    assert "no network" in source
