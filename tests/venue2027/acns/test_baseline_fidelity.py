"""Baseline fidelity vectors for ACNS-baselines (Task ACNS-baseline_tests).

Purpose
-------
Fidelity suite for the four EVIDENCE-BOUNDARY reference classes in
``evaluation/venue2027/acns/baselines.py`` (the real baseline module, imported
directly — no reimplementation, no stub). For EACH reference class
(B0-attestation-only, B1-receipt-without-binding, B2-timestamp-only,
B3-evidence-boundary-aware) this module runs:

- one POSITIVE vector: the evidence boundary is correctly assessed on the
  pinned synthetic record where the class's declared semantics hold; and
- one ADVERSARIAL NEGATIVE vector: a downgrade / unbound / replayed claim
  that the boundary-aware class (B3) refuses but the weaker class accepts —
  the weaker class's miss is itself asserted as the fidelity evidence, since
  each class's blind spot is definitional (its policy omits exactly one
  boundary check).

Allowed input
-------------
Only the pinned synthetic fixture records of ``_smoke_fixtures.py``
(dataset ``synthetic-acns-2027``); no network, no database, no clock, no live
provider, no PHI/PII. Cases are the JSON-serializable mappings accepted by
``baselines.run_baseline``.

Failure semantics
-----------------
A vector fails the suite when the real module deviates from its declared
class semantics (a weak class wrongly detecting its defining blind spot, a
class flipping ACCEPT/REJECT, or B3 accepting a boundary violation). Errors
surface as normal assertion failures with the structured verdict payload;
the module-under-test's own stable reason codes (UNKNOWN_BASELINE,
MALFORMED_CASE, NOT_RUN_EXTERNAL) are exercised as-is and never counted as
safe acceptances.

Version
-------
``BASELINE_FIDELITY_VECTORS_VERSION = "1.0.0"`` over
``ACNS_BASELINES_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import json
import typing

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.acns import _smoke_fixtures, baselines

BASELINE_FIDELITY_VECTORS_VERSION = "1.0.0"

B0 = "B0-attestation-only"
B1 = "B1-receipt-without-binding"
B2 = "B2-timestamp-only"
B3 = "B3-evidence-boundary-aware"

ALL_RECORDS = sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS)


def _ctx(baseline_id: str, case_id: str) -> dict[str, typing.Any]:
    return {"arm_id": baseline_id, "case_id": case_id, "seed": 0}


def _case(record_id: str, variant: str, case_id: str) -> dict[str, typing.Any]:
    return {
        "case_id": case_id,
        "record_id": record_id,
        "variant": variant,
        "dataset": _smoke_fixtures.FIXTURE_DATASET,
    }


def _verdict(outcome: Outcome) -> dict[str, typing.Any]:
    return json.loads(outcome.detail.split(" | ")[0])


def _gap_codes(outcome: Outcome) -> set[str]:
    return {gap["gap_code"] for gap in _verdict(outcome)["gaps"]}


def _run(baseline_id: str, record_id: str, variant: str, case_id: str) -> Outcome:
    return baselines.run_baseline(
        baseline_id, _case(record_id, variant, case_id), _ctx(baseline_id, case_id)
    )


# ---------------------------------------------------------------------------
# Positive vectors: one per class — the boundary is correctly assessed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("baseline_id", "record_id", "variant", "expected_observed", "expected_level"),
    [
        # B0 accepts any claimed level as stated, blind to artifacts: on the
        # unbound record it admits at the asserted L2 with zero gaps — its
        # correct positive behavior.
        pytest.param(B0, "sok-claim-record-3", "unbound", "ADMIT", "L2-ACKNOWLEDGED", id="B0"),
        # B1 checks receipt presence only: on the replayed record the receipt
        # artifact exists, so presence holds and it admits — its correct
        # positive behavior (linkage is out of its scope).
        pytest.param(B1, "sok-claim-record-4", "replayed", "ADMIT", "L3-EXECUTED", id="B1"),
        # B2 infers trust from timestamps: the downgraded record carries a
        # fresh timestamp, so it admits at the asserted L3 — its correct
        # positive behavior (artifacts are out of its scope).
        pytest.param(B2, "sok-claim-record-2", "downgraded", "ADMIT", "L3-EXECUTED", id="B2"),
        # B3 requires bound + verifiable + anchored evidence: on the fully
        # bound record every dimension check holds, so it admits — the
        # boundary-aware class's correct positive behavior.
        pytest.param(B3, "sok-claim-record-1", "bound", "ADMIT", "L3-EXECUTED", id="B3"),
    ],
)
def test_positive_boundary_correctly_assessed(
    baseline_id: str,
    record_id: str,
    variant: str,
    expected_observed: str,
    expected_level: str,
) -> None:
    case_id = f"fidelity-pos/{baseline_id}/{variant}"
    outcome = _run(baseline_id, record_id, variant, case_id)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == expected_observed
    assert outcome.counted_as_success is (expected_observed == "ADMIT")
    verdict = _verdict(outcome)
    assert verdict["baseline_id"] == baseline_id
    assert verdict["case_id"] == case_id
    assert verdict["granted_level"] == expected_level
    assert verdict["verdict"] == "ACCEPT"
    assert verdict["reason_code"] == "OK"
    # Fidelity: the class's own policy produces exactly the gaps its declared
    # semantics allow (weak stances see nothing on their positive vectors).
    assert verdict["gaps"] == []
    json.dumps(verdict)  # structured verdict stays JSON-serializable


# ---------------------------------------------------------------------------
# Adversarial negative vectors: one per class — a downgrade / unbound /
# replayed claim the class accepts but B3 refuses. The weak class's MISS is
# the fidelity evidence and is asserted explicitly.
# ---------------------------------------------------------------------------


def test_negative_B0_misses_receipt_quoted_as_execution_downgrade() -> None:
    """B0 reads the claimed level off the claim text: a provider receipt
    quoted as proof of *execution* (G2 downgrade, record-2) is admitted at
    L3 with zero gaps. B3 refuses the same claim and caps it at L2."""
    b0 = _run(B0, "sok-claim-record-2", "downgraded", "fidelity-neg/B0/downgraded")
    assert b0.observed_outcome == "ADMIT"
    assert b0.counted_as_success is True
    assert _verdict(b0)["gaps"] == []

    b3 = _run(B3, "sok-claim-record-2", "downgraded", "fidelity-neg/B0/downgraded")
    assert b3.observed_outcome == "REJECT"
    assert b3.counted_as_success is False
    assert "G2_RECEIPT_AS_EXECUTION" in _gap_codes(b3)


def test_negative_B1_misses_replayed_receipt_transplant() -> None:
    """B1 stops at 'a receipt exists': a receipt bound to a DIFFERENT claim
    (G4 transplant, record-4) is admitted. B3 refuses the same claim and
    flags the context-binding failure."""
    b1 = _run(B1, "sok-claim-record-4", "replayed", "fidelity-neg/B1/replayed")
    assert b1.observed_outcome == "ADMIT"
    assert b1.counted_as_success is True
    assert _verdict(b1)["gaps"] == []

    b3 = _run(B3, "sok-claim-record-4", "replayed", "fidelity-neg/B1/replayed")
    assert b3.observed_outcome == "REJECT"
    assert "G4_SIGNATURE_AS_CONTEXT" in _gap_codes(b3)


def test_negative_B2_misses_unbound_claim_on_timestamp_freshness() -> None:
    """B2 infers trust purely from freshness: a claim with NO evidence
    binding at all (G7/G9, record-3) is admitted because its timestamp is
    fresh. B3 refuses the same claim for the missing binding."""
    b2 = _run(B2, "sok-claim-record-3", "unbound", "fidelity-neg/B2/unbound")
    assert b2.observed_outcome == "ADMIT"
    assert b2.counted_as_success is True
    assert _verdict(b2)["gaps"] == []

    b3 = _run(B3, "sok-claim-record-3", "unbound", "fidelity-neg/B2/unbound")
    assert b3.observed_outcome == "REJECT"
    assert "G7_LEVEL_IMPLICIT_UPGRADE" in _gap_codes(b3)


def test_negative_B3_refuses_downgrade_unbound_and_replayed() -> None:
    """B3, the boundary-aware class, must refuse every adversarial variant —
    a B3 that accepted any of them would itself be a fidelity failure."""
    for record_id, variant, expected_gap in (
        ("sok-claim-record-2", "downgraded", "G2_RECEIPT_AS_EXECUTION"),
        ("sok-claim-record-3", "unbound", "G7_LEVEL_IMPLICIT_UPGRADE"),
        ("sok-claim-record-4", "replayed", "G4_SIGNATURE_AS_CONTEXT"),
    ):
        outcome = _run(B3, record_id, variant, f"fidelity-neg/B3/{variant}")
        assert outcome.observed_outcome == "REJECT", variant
        assert outcome.counted_as_success is False
        assert expected_gap in _gap_codes(outcome), variant


def test_negative_weak_stance_misses_are_the_witness_separation() -> None:
    """Same adversarial record (replayed): all three weak stances miss the
    transplant while B3 refuses — the RQ2 witness expressed as fidelity."""
    case_id = "fidelity-neg/witness/replayed"
    weak = [
        _run(baseline_id, "sok-claim-record-4", "replayed", case_id) for baseline_id in (B0, B1, B2)
    ]
    strong = _run(B3, "sok-claim-record-4", "replayed", case_id)
    assert [outcome.observed_outcome for outcome in weak] == ["ADMIT", "ADMIT", "ADMIT"]
    assert strong.observed_outcome == "REJECT"


# ---------------------------------------------------------------------------
# Fail-closed fidelity: unknown class / forged arm / unknown record / malformed
# case are stable reason codes, never counted as safe acceptances.
# ---------------------------------------------------------------------------


def test_fail_closed_unknown_class_and_forged_arm_refused() -> None:
    for _baseline_id, ctx in ((B3, _ctx(B3, "fidelity-fc/1")), (B0, {"arm_id": "ALLOW-ALL"})):
        refused = baselines.run_baseline(
            "NOT-A-CLASS", _case("sok-claim-record-1", "bound", "fidelity-fc/1"), ctx
        )
        assert refused.observed_outcome == "INVALID_RESULT"
        assert refused.counted_as_success is False
        assert "UNKNOWN_BASELINE" in refused.detail


def test_fail_closed_unknown_record_is_not_run_external() -> None:
    outcome = baselines.run_baseline(
        B3, _case("record-not-pinned", "bound", "fidelity-fc/2"), _ctx(B3, "fidelity-fc/2")
    )
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True


def test_fail_closed_malformed_case_is_invalid_result() -> None:
    outcome = baselines.run_baseline(B0, 42, _ctx(B0, "fidelity-fc/3"))
    assert outcome.observed_outcome == "INVALID_RESULT"
    assert outcome.counted_as_success is False
    assert "MALFORMED_CASE" in outcome.detail
