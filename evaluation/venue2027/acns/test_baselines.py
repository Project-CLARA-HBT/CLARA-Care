"""Tests for ACNS-baselines — EVIDENCE-BOUNDARY reference classes (synthetic only).

Positive controls: all four reference classes run on every synthetic evidence
record and return structured verdicts; the candidate reference class
(B3-evidence-boundary-aware) accepts exactly the fully-bound record.

Adversarial controls (the SoK witnesses, RQ2): each weaker stance FAILS to
detect the specific boundary gap that defines it — attestation-only misses the
receipt-to-execution downgrade, timestamp-only misses the unbound claim, and
receipt-without-binding accepts a replayed receipt — while B3 detects each.
Also: a constant-allow stub is refused, and unknown/NOT_RUN_EXTERNAL paths are
first-class (never silently counted as acceptances).
"""

from __future__ import annotations

import json
import typing

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.acns import _smoke_fixtures, baselines

ALL_RECORDS = sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS)


def _ctx(baseline_id: str, case_id: str = "case-1") -> dict[str, typing.Any]:
    return {"arm_id": baseline_id, "case_id": case_id, "seed": 0}


def _case(record_id: str, variant: str, case_id: str | None = None) -> dict[str, typing.Any]:
    return {
        "case_id": case_id or f"{record_id}/{variant}",
        "record_id": record_id,
        "variant": variant,
        "dataset": _smoke_fixtures.FIXTURE_DATASET,
    }


def _verdict(outcome: Outcome) -> dict[str, typing.Any]:
    return json.loads(outcome.detail.split(" | ")[0])


# ---------------------------------------------------------------------------
# Positive controls: all four reference classes run on synthetic records.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", baselines.BASELINE_IDS)
@pytest.mark.parametrize("record_key", ALL_RECORDS)
def test_positive_all_classes_classify_all_records(
    baseline_id: str, record_key: tuple[str, str]
) -> None:
    record_id, variant = record_key
    outcome = baselines.run_baseline(baseline_id, _case(record_id, variant), _ctx(baseline_id))
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT", "NOT_RUN_EXTERNAL")
    if outcome.observed_outcome != "NOT_RUN_EXTERNAL":
        verdict = _verdict(outcome)
        assert verdict["baseline_id"] == baseline_id
        assert verdict["reason_code"] != ""
        for gap in verdict["gaps"]:
            assert gap["gap_code"] in baselines.KNOWN_GAP_CODES


def test_positive_b3_accepts_fully_bound_record() -> None:
    outcome = baselines.run_baseline(
        "B3-evidence-boundary-aware",
        _case("sok-claim-record-1", "bound"),
        _ctx("B3-evidence-boundary-aware"),
    )
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    verdict = _verdict(outcome)
    assert verdict["granted_level"] == "L3-EXECUTED"
    assert verdict["gaps"] == []
    assert verdict["reason_code"] == "OK"


def test_positive_b0_accepts_claim_as_stated_without_receipt_binding() -> None:
    """B0 semantics: accepts any claimed attestation level, no receipt check."""
    outcome = baselines.run_baseline(
        "B0-attestation-only", _case("sok-claim-record-3", "unbound"), _ctx("B0-attestation-only")
    )
    assert outcome.observed_outcome == "ADMIT"
    verdict = _verdict(outcome)
    assert verdict["granted_level"] == "L2-ACKNOWLEDGED"
    # B0's defining blind spot: no gap is detected despite zero bindings.
    assert verdict["gaps"] == []


def test_positive_b1_accepts_when_receipt_present_ignoring_linkage() -> None:
    """B1 semantics: receipt presence is checked, claim linkage is ignored."""
    outcome = baselines.run_baseline(
        "B1-receipt-without-binding",
        _case("sok-claim-record-4", "replayed"),
        _ctx("B1-receipt-without-binding"),
    )
    assert outcome.observed_outcome == "ADMIT"


def test_positive_b2_infers_trust_from_timestamps() -> None:
    """B2 semantics: a fresh timestamp is treated as sufficient trust."""
    outcome = baselines.run_baseline(
        "B2-timestamp-only", _case("sok-claim-record-2", "downgraded"), _ctx("B2-timestamp-only")
    )
    assert outcome.observed_outcome == "ADMIT"
    verdict = _verdict(outcome)
    assert verdict["granted_level"] == "L3-EXECUTED"


def test_positive_structured_verdict_is_json_serializable() -> None:
    outcome = baselines.run_baseline(
        "B3-evidence-boundary-aware",
        _case("sok-claim-record-2", "downgraded"),
        _ctx("B3-evidence-boundary-aware"),
    )
    payload = json.loads(outcome.detail.split(" | ")[0])
    json.dumps(payload)  # must not raise
    assert set(payload) == {
        "baseline_id",
        "case_id",
        "granted_level",
        "verdict",
        "reason_code",
        "gaps",
        "baseline_version",
        "verdict_digest",
    }


# ---------------------------------------------------------------------------
# Adversarial controls: weaker stances FAIL to detect their defining gap.
# ---------------------------------------------------------------------------


def test_adversarial_attestation_only_fails_to_detect_downgrade_gap() -> None:
    """B0 accepts a receipt-quoted-as-execution claim at L3 — the G2 blind spot."""
    b0 = baselines.run_baseline(
        "B0-attestation-only",
        _case("sok-claim-record-2", "downgraded"),
        _ctx("B0-attestation-only"),
    )
    assert b0.observed_outcome == "ADMIT"
    assert _verdict(b0)["gaps"] == []


def test_adversarial_receipt_without_binding_fails_to_detect_downgrade_gap() -> None:
    """B1 also accepts the downgrade: receipt present, anchor unchecked."""
    b1 = baselines.run_baseline(
        "B1-receipt-without-binding",
        _case("sok-claim-record-2", "downgraded"),
        _ctx("B1-receipt-without-binding"),
    )
    assert b1.observed_outcome == "ADMIT"
    assert _verdict(b1)["gaps"] == []


def test_adversarial_timestamp_only_fails_to_detect_unbound_claim() -> None:
    """B2 accepts a claim with NO evidence binding because its timestamp is fresh."""
    b2 = baselines.run_baseline(
        "B2-timestamp-only", _case("sok-claim-record-3", "unbound"), _ctx("B2-timestamp-only")
    )
    assert b2.observed_outcome == "ADMIT"
    assert _verdict(b2)["gaps"] == []


def test_adversarial_receipt_without_binding_accepts_replayed_receipt() -> None:
    """B1 accepts a receipt bound to a DIFFERENT claim (G4 transplant succeeds)."""
    b1 = baselines.run_baseline(
        "B1-receipt-without-binding",
        _case("sok-claim-record-4", "replayed"),
        _ctx("B1-receipt-without-binding"),
    )
    assert b1.observed_outcome == "ADMIT"


def test_adversarial_b3_detects_downgrade_gap_the_others_miss() -> None:
    """The candidate reference class detects the receipt->execution downgrade."""
    b3 = baselines.run_baseline(
        "B3-evidence-boundary-aware",
        _case("sok-claim-record-2", "downgraded"),
        _ctx("B3-evidence-boundary-aware"),
    )
    assert b3.observed_outcome == "REJECT"
    assert b3.counted_as_success is False
    verdict = _verdict(b3)
    assert verdict["granted_level"] == "L2-ACKNOWLEDGED"
    gap_codes = {gap["gap_code"] for gap in verdict["gaps"]}
    assert "G2_RECEIPT_AS_EXECUTION" in gap_codes


def test_adversarial_b3_detects_unbound_claim_the_others_miss() -> None:
    b3 = baselines.run_baseline(
        "B3-evidence-boundary-aware",
        _case("sok-claim-record-3", "unbound"),
        _ctx("B3-evidence-boundary-aware"),
    )
    assert b3.observed_outcome == "REJECT"
    gap_codes = {gap["gap_code"] for gap in _verdict(b3)["gaps"]}
    assert "G7_LEVEL_IMPLICIT_UPGRADE" in gap_codes


def test_adversarial_b3_detects_replayed_receipt_the_others_miss() -> None:
    b3 = baselines.run_baseline(
        "B3-evidence-boundary-aware",
        _case("sok-claim-record-4", "replayed"),
        _ctx("B3-evidence-boundary-aware"),
    )
    assert b3.observed_outcome == "REJECT"
    gap_codes = {gap["gap_code"] for gap in _verdict(b3)["gaps"]}
    assert "G4_SIGNATURE_AS_CONTEXT" in gap_codes


def test_adversarial_separation_between_stances_is_witnessed() -> None:
    """Same record: all three weak stances accept, B3 rejects (RQ2 witness)."""
    case = _case("sok-claim-record-4", "replayed")
    weak = [
        baselines.run_baseline(baseline_id, case, _ctx(baseline_id)).observed_outcome
        for baseline_id in (
            "B0-attestation-only",
            "B1-receipt-without-binding",
            "B2-timestamp-only",
        )
    ]
    strong = baselines.run_baseline(
        "B3-evidence-boundary-aware", case, _ctx("B3-evidence-boundary-aware")
    ).observed_outcome
    assert weak == ["ADMIT", "ADMIT", "ADMIT"]
    assert strong == "REJECT"


# ---------------------------------------------------------------------------
# Fail-closed controls: constant-allow stubs and unknown inputs are refused.
# ---------------------------------------------------------------------------


def test_constant_allow_stub_is_refused() -> None:
    def constant_allow(
        baseline_id: str, case: typing.Mapping[str, typing.Any], ctx: typing.Any
    ) -> Outcome:
        return Outcome(observed_outcome="ADMIT", counted_as_success=True, detail="constant allow")

    assert (
        constant_allow(
            "NOT-A-BASELINE", _case("sok-claim-record-1", "bound"), _ctx("x")
        ).observed_outcome
        == "ADMIT"
    )
    refused = baselines.run_baseline(
        "NOT-A-BASELINE", _case("sok-claim-record-1", "bound"), _ctx("x")
    )
    assert refused.observed_outcome == "INVALID_RESULT"
    assert refused.counted_as_success is False
    assert "UNKNOWN_BASELINE" in refused.detail

    # Even with a valid baseline_id, a forged non-preregistered ctx arm is refused.
    forged = baselines.run_baseline(
        "B0-attestation-only", _case("sok-claim-record-1", "bound"), {"arm_id": "ALLOW-ALL"}
    )
    assert forged.observed_outcome == "INVALID_RESULT"
    assert "UNKNOWN_BASELINE" in forged.detail


def test_unknown_record_is_not_run_external_never_a_safe_accept() -> None:
    outcome = baselines.run_baseline(
        "B3-evidence-boundary-aware",
        _case("record-not-pinned", "bound"),
        _ctx("B3-evidence-boundary-aware"),
    )
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True


def test_malformed_case_fails_closed() -> None:
    for bad in ({}, {"record_id": 7, "variant": "bound"}, "not-a-mapping"):
        outcome = baselines.run_baseline("B0-attestation-only", bad, _ctx("B0-attestation-only"))
        assert outcome.observed_outcome in ("INVALID_RESULT", "NOT_RUN_EXTERNAL")
        assert outcome.counted_as_success is False


def test_non_mapping_case_object_is_refused() -> None:
    outcome = baselines.run_baseline("B0-attestation-only", 42, _ctx("B0-attestation-only"))
    assert outcome.observed_outcome == "INVALID_RESULT"
    assert "MALFORMED_CASE" in outcome.detail
