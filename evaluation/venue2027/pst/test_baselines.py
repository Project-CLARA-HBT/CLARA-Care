"""Tests for PST-baselines — baseline fidelity adapters and reconstructability frontier (phase P03).

Positive controls:
- Registry coverage: all registered arms (B0, B1, B2, B3) exist in BASELINE_REGISTRY.
- Implemented arms run end-to-end and return determined Outcome objects.
- Frontier computed: empirical reconstructability and linkability computed over synthetic sample.
- B1 reconstructability loss: B1 loses reconstructability vs B0 (storage/privacy baseline).
- B2 and B3 recovery: cryptographic receipt anchoring (B2) and candidate ReceiptMin (B3)
  recover forensic reconstructability while reducing linkability.
- Parity check: implemented arms pass parity; unavailable external upstreams return None.

Adversarial controls:
- Constant-perfect stub refused: a stub returning constant ADMIT / 1.0 on all probes is refused.
- Constant-reject stub refused: a stub returning constant REJECT on all probes is refused.
- Honest discriminating adapter accepted: separating probe pairs yields STUB_SEPARATION_OK.
- NOT_RUN_EXTERNAL honesty: external comparator upstreams (RFC 9162, Macaroons, OpenFGA,
  Zanzibar, FHIR5, MUSE) return NOT_RUN_EXTERNAL with BASELINE_UNAVAILABLE; never a toy substitution.
- No invented values beyond computed sample: empty sample raises SAMPLE_EMPTY; metrics
  are strictly derived from evaluated sample cases, exhibiting genuine input sensitivity.
- Fail closed on malformed cases and unknown baseline IDs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.pst.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINE_REGISTRY,
    EXTERNAL_UNAVAILABLE_BASELINES,
    RC_BASELINE_UNAVAILABLE,
    RC_BASELINE_UNKNOWN,
    RC_CASE_MALFORMED,
    RC_FORENSIC_OMISSION,
    RC_RECONSTRUCT,
    RC_SAMPLE_EMPTY,
    RC_STUB_CONSTANT,
    RC_STUB_DETECT_ALL,
    RC_STUB_DETECT_NONE,
    RC_STUB_SEPARATION_OK,
    REGISTRY_B2,
    REGISTRY_B3,
    AuditEvent,
    FrontierPoint,
    PstBaselineError,
    compute_frontier,
    extract_events,
    linkability_score,
    parity_check,
    reconstructability,
    refuse_constant_stub,
    retain_audit_set,
    run_baseline,
)


def _ctx(arm_id: str = "B3", case_id: str = "case-1", seed: int = 42) -> RunContext:
    return RunContext(
        campaign_id="camp-pst-baselines",
        case_id=case_id,
        arm_id=arm_id,
        seed=seed,
        source_commit="28ff55110f980f42002524cef126290e91258cd6",
        deadline_seconds=60.0,
    )


def _synthetic_case(
    case_id: str = "case-pst-01",
    num_events: int = 3,
    subject_id: str = "patient_alice",
) -> dict[str, Any]:
    events = []
    for i in range(num_events):
        events.append(
            {
                "event_id": f"{case_id}_evt_{i:03d}",
                "operation_id": f"op_{case_id}_{i}",
                "subject_id": subject_id,
                "tenant_id": "tnt_hospital_a",
                "purpose": "clinical_care" if i % 2 == 0 else "self_care",
                "operation": "record_write",
                "policy_epoch": f"epoch-{i // 2 + 1}",
                "consent_epoch": f"epoch-{i // 2 + 1}",
                "witness_id": f"wit_merkle_{case_id}_{i}",
                "timestamp": f"2026-11-15T1{i}:24:00Z",
                "payload": {
                    "medication": "amoxicillin" if i % 2 == 0 else "paracetamol",
                    "dose": "500mg",
                    "step": i,
                },
            }
        )
    return {"case_id": case_id, "events": events}


# ===========================================================================
# Positive controls
# ===========================================================================


class TestPositiveControls:
    def test_registry_contains_required_arms_and_provenance(self) -> None:
        """BASELINE_REGISTRY must contain all required arms with complete metadata."""
        assert BASELINE_B0 in BASELINE_REGISTRY
        assert BASELINE_B1 in BASELINE_REGISTRY
        assert BASELINE_B2 in BASELINE_REGISTRY
        assert BASELINE_B3 in BASELINE_REGISTRY
        assert REGISTRY_B3 in BASELINE_REGISTRY
        assert REGISTRY_B2 in BASELINE_REGISTRY

        for arm_id in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
            spec = BASELINE_REGISTRY[arm_id]
            assert spec.runnable_in_process is True
            assert spec.fidelity_status == "FAITHFUL_PORT"
            assert spec.title != ""
            assert spec.algorithm_class != ""
            assert spec.notes != ""

    def test_implemented_arms_run_end_to_end(self) -> None:
        """Every implemented arm runs end-to-end and returns a typed Outcome."""
        case = _synthetic_case("test-run-01", num_events=2)
        ctx = _ctx()

        # B0: Full audit retention admits with full reconstructability
        res_b0 = run_baseline(BASELINE_B0, case, ctx)
        assert isinstance(res_b0, Outcome)
        assert res_b0.observed_outcome == "ADMIT"
        assert res_b0.counted_as_success is True
        detail_b0 = json.loads(res_b0.detail)
        assert detail_b0["status"] == RC_RECONSTRUCT
        assert detail_b0["reconstructability"] == 1.0

        # B1: Minimized without receipts rejects due to forensic omission
        res_b1 = run_baseline(BASELINE_B1, case, ctx)
        assert isinstance(res_b1, Outcome)
        assert res_b1.observed_outcome == "REJECT"
        assert res_b1.counted_as_success is False
        detail_b1 = json.loads(res_b1.detail)
        assert detail_b1["status"] == RC_FORENSIC_OMISSION
        assert detail_b1["reconstructability"] < 0.50

        # B2: Minimized + receipt anchoring admits with recovered reconstructability
        res_b2 = run_baseline(BASELINE_B2, case, ctx)
        assert isinstance(res_b2, Outcome)
        assert res_b2.observed_outcome == "ADMIT"
        assert res_b2.counted_as_success is True
        detail_b2 = json.loads(res_b2.detail)
        assert detail_b2["status"] == RC_RECONSTRUCT
        assert detail_b2["reconstructability"] >= 0.85

        # B3: Candidate ReceiptMin admits with recovered reconstructability
        res_b3 = run_baseline(BASELINE_B3, case, ctx)
        assert isinstance(res_b3, Outcome)
        assert res_b3.observed_outcome == "ADMIT"
        assert res_b3.counted_as_success is True
        detail_b3 = json.loads(res_b3.detail)
        assert detail_b3["status"] == RC_RECONSTRUCT
        assert detail_b3["reconstructability"] >= 0.85

    def test_frontier_computed_and_b1_loss_demonstrated(self) -> None:
        """Frontier computation across a sample proves B1 reconstructability loss and B2/B3 recovery."""
        sample_cases = [
            _synthetic_case(f"case-frontier-{i}", num_events=3, subject_id=f"patient_{i % 3}")
            for i in range(6)
        ]
        frontier = compute_frontier(sample_cases)

        assert set(frontier.keys()) == {BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3}

        b0_pt = frontier[BASELINE_B0]
        b1_pt = frontier[BASELINE_B1]
        b2_pt = frontier[BASELINE_B2]
        b3_pt = frontier[BASELINE_B3]

        # 1. B0 achieves utility ceiling (reconstructability = 1.0) and high linkability
        assert b0_pt.reconstructability == 1.0
        assert b0_pt.linkability >= 0.90
        assert b0_pt.privacy_gain <= 0.10

        # 2. B1 LOSES reconstructability vs B0 (prompt invariant: B1 must LOSE reconstructability vs B0)
        assert b1_pt.reconstructability < 0.25
        assert b1_pt.reconstructability < b0_pt.reconstructability - 0.70

        # 3. B2 and B3 RECOVER reconstructability (prompt invariant: B2/B3 recover it)
        assert b2_pt.reconstructability >= 0.85
        assert b3_pt.reconstructability >= 0.85
        assert b2_pt.reconstructability > b1_pt.reconstructability + 0.60
        assert b3_pt.reconstructability > b1_pt.reconstructability + 0.60

        # 4. B3 candidate optimizes the frontier (lowest linkability / highest privacy gain)
        assert b3_pt.linkability <= 0.20
        assert b3_pt.privacy_gain >= 0.80
        assert b3_pt.linkability < b2_pt.linkability
        assert b3_pt.linkability < b1_pt.linkability
        assert b3_pt.linkability < b0_pt.linkability

    def test_reconstructability_individual_dimensions(self) -> None:
        """reconstructability evaluates the four forensic query dimensions faithfully."""
        event = AuditEvent(
            event_id="evt_dim_001",
            subject_id="sub_test",
            tenant_id="tnt_test",
            purpose="clinical_care",
            operation="record_write",
            policy_epoch="epoch-1",
            consent_epoch="epoch-1",
            witness_id="wit_001",
            timestamp="2026-11-15T12:00:00Z",
            payload={"action": "test_dose", "medication": "aspirin"},
            commitment_digest="commit_hash_123",
        )

        # Full retention (B0)
        records_b0 = retain_audit_set(BASELINE_B0, [event])
        score_b0 = reconstructability([event], records_b0)
        assert score_b0 == 1.0

        # Minimized without receipts (B1): loses authorization, provenance, consent, and payload
        records_b1 = retain_audit_set(BASELINE_B1, [event])
        score_b1 = reconstructability([event], records_b1)
        assert score_b1 == 0.0

        # Minimized + anchored receipts (B2): recovers all 4 dimensions
        records_b2 = retain_audit_set(BASELINE_B2, [event])
        score_b2 = reconstructability([event], records_b2)
        assert score_b2 == 1.0

        # Candidate ReceiptMin (B3): recovers all 4 dimensions
        records_b3 = retain_audit_set(BASELINE_B3, [event])
        score_b3 = reconstructability([event], records_b3)
        assert score_b3 == 1.0

    def test_linkability_score_with_and_without_aux_data(self) -> None:
        """linkability_score computes bounds across arms with and without auxiliary joins."""
        case = _synthetic_case("aux-test", num_events=4)
        events = [
            AuditEvent(
                event_id=e["event_id"],
                subject_id=e["subject_id"],
                tenant_id=e["tenant_id"],
                purpose=e["purpose"],
                operation=e["operation"],
                policy_epoch=e["policy_epoch"],
                consent_epoch=e["consent_epoch"],
                witness_id=e["witness_id"],
                timestamp=e["timestamp"],
                payload=e["payload"],
                commitment_digest="hash",
            )
            for e in case["events"]
        ]

        b0_records = retain_audit_set(BASELINE_B0, events)
        b3_records = retain_audit_set(BASELINE_B3, events)

        # Without aux data
        l0 = linkability_score(b0_records)
        l3 = linkability_score(b3_records)
        assert l0 >= 0.90
        assert l3 <= 0.20

        # With auxiliary join table
        aux_table = [
            {"timestamp": "2026-11-15T10:24:00Z", "subject_id": "patient_alice"},
            {"timestamp": "2026-11-15T11:24:00Z", "subject_id": "patient_alice"},
        ]
        l0_aux = linkability_score(b0_records, aux_table)
        l3_aux = linkability_score(b3_records, aux_table)
        assert l0_aux > l3_aux
        assert l3_aux <= 0.25

    def test_parity_check_on_implemented_arms(self) -> None:
        """parity_check succeeds on implemented arms and returns None on external ones."""
        assert parity_check(BASELINE_B0) is True
        assert parity_check(BASELINE_B1) is True
        assert parity_check(BASELINE_B2) is True
        assert parity_check(BASELINE_B3) is True
        assert parity_check(REGISTRY_B3) is None
        assert parity_check(REGISTRY_B2) is None


# ===========================================================================
# Adversarial controls
# ===========================================================================


class TestAdversarialControls:
    def test_refuse_constant_perfect_stub(self) -> None:
        """refuse_constant_stub refuses a candidate returning constant ADMIT / 1.0 (rule 8)."""
        # Constant ADMIT / perfect reconstructability stub
        def constant_perfect_stub(_case: Mapping[str, Any]) -> Outcome:
            return Outcome(observed_outcome="ADMIT", counted_as_success=True, detail="perfect")

        with pytest.raises(PstBaselineError, match=f"({RC_STUB_CONSTANT}|{RC_STUB_DETECT_ALL})"):
            refuse_constant_stub(constant_perfect_stub)

        # Constant float 1.0 stub
        with pytest.raises(PstBaselineError, match=f"({RC_STUB_CONSTANT}|{RC_STUB_DETECT_ALL})"):
            refuse_constant_stub(lambda _case: 1.0)

    def test_refuse_constant_reject_stub(self) -> None:
        """refuse_constant_stub refuses a candidate returning constant REJECT on all probes."""
        def constant_reject_stub(_case: Mapping[str, Any]) -> Outcome:
            return Outcome(observed_outcome="REJECT", counted_as_success=False, detail="fail")

        with pytest.raises(PstBaselineError, match=f"({RC_STUB_CONSTANT}|{RC_STUB_DETECT_NONE})"):
            refuse_constant_stub(constant_reject_stub)

    def test_refuse_constant_stub_admits_discriminating_adapter(self) -> None:
        """refuse_constant_stub admits an honest discriminating adapter that separates probes."""
        def discriminating_adapter(case: Mapping[str, Any]) -> Outcome:
            return run_baseline(BASELINE_B3, case, _ctx())

        outcome = refuse_constant_stub(discriminating_adapter)
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True
        assert outcome.detail == RC_STUB_SEPARATION_OK

    @pytest.mark.parametrize("ext_id", sorted(EXTERNAL_UNAVAILABLE_BASELINES))
    def test_external_upstreams_are_honestly_not_run_external(self, ext_id: str) -> None:
        """Unavailable external upstreams return NOT_RUN_EXTERNAL with BASELINE_UNAVAILABLE (rule 8)."""
        case = _synthetic_case("test-ext", num_events=1)
        outcome = run_baseline(ext_id, case, _ctx())

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.retriable is False
        assert RC_BASELINE_UNAVAILABLE in outcome.detail
        assert ext_id in outcome.detail

    def test_no_invented_values_beyond_computed_sample(self) -> None:
        """Frontier calculator refuses empty sample and computes strictly from observed cases."""
        # 1. Empty sample raises SAMPLE_EMPTY
        with pytest.raises(PstBaselineError, match=RC_SAMPLE_EMPTY):
            compute_frontier([])

        # 2. Strict sample derivation: single case vs two cases
        c1 = _synthetic_case("case-exact-1", num_events=1)
        c2 = _synthetic_case("case-exact-2", num_events=2)

        frontier_1 = compute_frontier([c1], arms=[BASELINE_B0, BASELINE_B1])
        frontier_2 = compute_frontier([c1, c2], arms=[BASELINE_B0, BASELINE_B1])

        assert isinstance(frontier_1[BASELINE_B0], FrontierPoint)
        assert isinstance(frontier_2[BASELINE_B0], FrontierPoint)

        # 3. Input sensitivity: mutating the case alters the reconstructability score
        corrupted_c1 = {
            "case_id": "corrupted",
            "events": [
                {
                    "event_id": "corrupt_1",
                    "operation_id": "op_corrupt",
                    # Omitted all authorization and witness fields
                }
            ],
        }
        rec_clean = reconstructability(c1, retain_audit_set(BASELINE_B3, extract_events(c1)))
        rec_corrupt = reconstructability(corrupted_c1, retain_audit_set(BASELINE_B3, extract_events(corrupted_c1)))
        assert rec_clean == 1.0
        assert rec_corrupt == 0.0  # Input-sensitive, no hardcoded phantom pass

    def test_malformed_case_and_unknown_baseline_fail_closed(self) -> None:
        """Malformed inputs and unknown IDs raise PstBaselineError with stable reason codes."""
        with pytest.raises(PstBaselineError, match=RC_CASE_MALFORMED):
            run_baseline(BASELINE_B0, "not-a-mapping", _ctx())  # type: ignore[arg-type]

        with pytest.raises(PstBaselineError, match=RC_BASELINE_UNKNOWN):
            run_baseline("totally-fictional-baseline-999", _synthetic_case(), _ctx())
