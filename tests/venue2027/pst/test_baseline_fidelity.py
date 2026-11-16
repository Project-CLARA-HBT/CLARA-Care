"""Baseline fidelity conformance suite for PST-baseline_tests (Phase P03, venue pst).

Purpose
-------
Fidelity test suite for the four implemented PST baseline arms in
``evaluation/venue2027/pst/baselines.py`` (ReceiptMin: Measuring Forensic
Reconstructability under Purpose-Bound Audit Minimization):

- B0: Full plaintext append-only audit log (utility upper bound / privacy lower bound).
- B1: Minimized without receipts / content digests only (storage/privacy baseline, weak audit utility).
- B2: Minimized log with cryptographic receipt anchoring (witness anchors + commitment digests).
- B3: Purpose-bound minimized receipt and retention map (candidate ReceiptMin).

For EACH implemented PST baseline:
- One UPSTREAM-STYLE POSITIVE VECTOR: asserts the documented guarantee holds end-to-end
  through the real ``run_baseline`` entry point and underlying evaluation functions.
- One ADVERSARIAL NEGATIVE VECTOR: asserts the baseline's documented blind spot, weakness,
  or security boundary under attack (e.g. B1 fails to answer forensic queries requiring stripped
  evidence; B2 linkability exceeds B3 under cross-epoch pseudonym clustering; B0 exposes raw
  plaintext identifiers and maximum linkability; B3 resists pseudonym clustering and refuses stubs).

Additionally:
- Records observable behaviour per baseline in ``OBSERVED_BEHAVIOUR``.
- Asserts UNAVAILABLE_NOT_RUN external baselines (RFC 9162 CT-Merkle, KMS-encrypted log,
  Macaroons NDSS 2014, OpenFGA, Zanzibar, FHIR R5, MUSE, RATS RFC 9334, NIST ABAC, WHO 2021)
  report honestly as ``NOT_RUN_EXTERNAL`` with ``BASELINE_UNAVAILABLE``; never replaced by stubs
  (EXECUTION_CONTRACT rule 8).
- Verifies fail-closed error semantics on malformed cases and unknown baseline IDs.

Allowed input
-------------
Synthetic, JSON-serializable clinical audit events (no network, no database, no clock,
no live LLM/provider; no real patient data, no production secrets). All vectors deterministic.

Failure semantics
-----------------
Baselines fail closed with stable uppercase reason codes (RC_RECONSTRUCT, RC_FORENSIC_OMISSION,
RC_BASELINE_UNAVAILABLE, RC_BASELINE_UNKNOWN, RC_CASE_MALFORMED, RC_SAMPLE_EMPTY,
RC_STUB_CONSTANT, RC_STUB_DETECT_ALL, RC_STUB_DETECT_NONE, RC_STUB_SEPARATION_OK).
Tests assert these codes and never accept bare exceptions or silent drops as safe rejections.

Version
-------
``PST_BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"`` against
``baselines.PST_BASELINES_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import json
from typing import Any, Final

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.pst import baselines
from evaluation.venue2027.pst.baselines import (
    BASELINE_B0,
    BASELINE_B0_FULL,
    BASELINE_B1,
    BASELINE_B1_MIN_NO_RECEIPT,
    BASELINE_B2,
    BASELINE_B2_MIN_ANCHORED,
    BASELINE_B3,
    BASELINE_B3_RECEIPTMIN,
    BASELINE_REGISTRY,
    EXTERNAL_UNAVAILABLE_BASELINES,
    IMPLEMENTED_BASELINES,
    PST_BASELINES_VERSION,
    RC_BASELINE_UNAVAILABLE,
    RC_BASELINE_UNKNOWN,
    RC_CASE_MALFORMED,
    RC_CONTEXT_MALFORMED,
    RC_FORENSIC_OMISSION,
    RC_RECONSTRUCT,
    RC_SAMPLE_EMPTY,
    RC_STUB_CONSTANT,
    RC_STUB_DETECT_ALL,
    RC_STUB_DETECT_NONE,
    RC_STUB_SEPARATION_OK,
    REGISTRY_B0,
    REGISTRY_B1,
    REGISTRY_B4,
    AuditEvent,
    AuditRecord,
    FrontierPoint,
    PstBaselineError,
    answerable_probe_case,
    compute_frontier,
    extract_events,
    linkability_score,
    parity_check,
    reconstructability,
    refuse_constant_stub,
    retain_audit_set,
    run_baseline,
    unanswerable_probe_case,
)

PST_BASELINE_FIDELITY_TESTS_VERSION: Final[str] = "1.0.0"

#: Observable behaviour recorded per baseline (task contract requirement).
OBSERVED_BEHAVIOUR: Final[dict[str, str]] = {
    BASELINE_B0: (
        "B0 (full plaintext append-only audit log): Retains raw plaintext subject "
        "identifiers, payloads, timestamps, witness anchors, and epoch attestations. "
        "Achieves 100% forensic reconstructability (score 1.0, ADMIT with status "
        "RECONSTRUCT) across all four forensic dimensions (authorization, provenance, "
        "commit eligibility, content verification). However, exhibits maximum "
        "linkability risk (~0.98) due to unpseudonymized subject IDs and exact timestamps, "
        "providing a zero-privacy baseline (privacy gain <= 0.05)."
    ),
    BASELINE_B1: (
        "B1 (minimized without receipts / content digests only): Strips sensitive clinical "
        "payloads, witness anchors, policy epochs, and consent epochs, retaining only "
        "unsalted subject hashes and operation metadata. Reduces linkability to ~0.64 "
        "(privacy gain ~0.36) but suffers complete forensic amnesia on evidence-requiring "
        "queries (reconstructability 0.0 < 0.25, REJECT with status FORENSIC_OMISSION). "
        "Demonstrates the failure of naive audit minimization without cryptographic receipt anchoring."
    ),
    BASELINE_B2: (
        "B2 (minimized log with cryptographic receipt anchoring): Retains salted pseudonyms, "
        "commitment digests, witness anchors, and epoch proofs while stripping raw payloads. "
        "Recovers forensic reconstructability (score 1.0, ADMIT with status RECONSTRUCT). "
        "However, uses static pseudonyms across epochs and exact timestamps, leaving "
        "linkability elevated (~0.41) under cross-epoch pseudonym clustering, exceeding B3."
    ),
    BASELINE_B3: (
        "B3 (purpose-bound minimized receipt and retention map / candidate ReceiptMin): "
        "Combines purpose-bound HMAC pseudonyms derived per (tenant, purpose, epoch), "
        "hour-coarsened timestamps, explicit retention maps, and commitment receipts with witness anchors. "
        "Achieves full forensic reconstructability (score 1.0, ADMIT with status RECONSTRUCT) "
        "while bounding linkability to <= 0.20 (~0.11), strictly dominating B2 and B1 on the frontier."
    ),
}


# ---------------------------------------------------------------------------
# Synthetic test case and context generators (deterministic, no clocks/network)
# ---------------------------------------------------------------------------


def _ctx(arm_id: str = "B3", case_id: str = "case-fid-01", seed: int = 42) -> RunContext:
    return RunContext(
        campaign_id="camp-pst-baseline-fidelity",
        case_id=case_id,
        arm_id=arm_id,
        seed=seed,
        source_commit="08dbda2900c97a208b3228639f51998db833bb60",
        deadline_seconds=60.0,
    )


def _synthetic_event(
    event_id: str = "evt_fid_001",
    subject_id: str = "patient_alice",
    tenant_id: str = "tnt_hospital_a",
    purpose: str = "clinical_care",
    operation: str = "record_write",
    policy_epoch: str = "epoch-1",
    consent_epoch: str = "epoch-1",
    witness_id: str = "wit_merkle_001",
    timestamp: str = "2026-11-15T10:15:30Z",
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    p = payload if payload is not None else {"medication": "amoxicillin", "dosage": "500mg"}
    digest = baselines._sha256(baselines._canonical_json(p))
    return AuditEvent(
        event_id=event_id,
        subject_id=subject_id,
        tenant_id=tenant_id,
        purpose=purpose,
        operation=operation,
        policy_epoch=policy_epoch,
        consent_epoch=consent_epoch,
        witness_id=witness_id,
        timestamp=timestamp,
        payload=p,
        commitment_digest=digest,
    )


def _synthetic_case(
    case_id: str = "case-pst-fid-01",
    num_events: int = 3,
    subject_id: str = "patient_alice",
    tenant_id: str = "tnt_hospital_a",
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for i in range(num_events):
        epoch = f"epoch-{(i // 2) + 1}"
        purpose = "clinical_care" if i % 2 == 0 else "research_study"
        payload = {
            "medication": "amoxicillin" if i % 2 == 0 else "metformin",
            "dose": f"{250 * (i + 1)}mg",
            "step": i,
        }
        digest = baselines._sha256(baselines._canonical_json(payload))
        events.append(
            {
                "event_id": f"{case_id}_evt_{i:03d}",
                "operation_id": f"op_{case_id}_{i}",
                "subject_id": subject_id,
                "tenant_id": tenant_id,
                "purpose": purpose,
                "operation": "record_write",
                "policy_epoch": epoch,
                "consent_epoch": epoch,
                "witness_id": f"wit_merkle_{case_id}_{i}",
                "timestamp": f"2026-11-15T1{i}:24:00Z",
                "payload": payload,
                "commitment_digest": digest,
            }
        )
    return {"case_id": case_id, "events": events}


# ---------------------------------------------------------------------------
# Module and Registry Metadata Tests
# ---------------------------------------------------------------------------


class TestModuleMetadataAndRegistryFidelity:
    """Validate module version, registry completeness, and recorded behaviour."""

    def test_module_version_and_contract_pins(self) -> None:
        """Module versions and test suite versions are properly pinned."""
        assert PST_BASELINES_VERSION == "1.0.0"
        assert PST_BASELINE_FIDELITY_TESTS_VERSION == "1.0.0"

    def test_implemented_arms_present_in_registry(self) -> None:
        """All four primary arms (B0, B1, B2, B3) exist with faithful port status."""
        for arm in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
            assert arm in BASELINE_REGISTRY
            spec = BASELINE_REGISTRY[arm]
            assert spec.runnable_in_process is True
            assert spec.fidelity_status == "FAITHFUL_PORT"
            assert arm in IMPLEMENTED_BASELINES

    def test_observed_behaviour_recorded_for_all_implemented_arms(self) -> None:
        """Every implemented arm has an explicit entry in OBSERVED_BEHAVIOUR."""
        for arm in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
            assert arm in OBSERVED_BEHAVIOUR
            assert len(OBSERVED_BEHAVIOUR[arm]) > 50


# ---------------------------------------------------------------------------
# Arm B0: Full Plaintext Append-Only Log
# ---------------------------------------------------------------------------


class TestB0FullRetentionFidelity:
    """Fidelity vectors for Arm B0 (full plaintext append-only audit log)."""

    def test_b0_positive_vector_full_forensic_reconstruction(self) -> None:
        """Upstream positive: B0 retains full plaintext and answers all forensic queries.

        On an authorized clinical action case, B0 preserves raw payloads, subject identifiers,
        witness anchors, and epoch attestations. Reconstructability is 1.0 (100% across all
        four query classes: authorization, provenance, commit eligibility, content verification),
        yielding Outcome ADMIT with status RECONSTRUCT.
        """
        case = _synthetic_case("case-b0-pos", num_events=2)
        outcome = run_baseline(BASELINE_B0, case, _ctx(BASELINE_B0, "case-b0-pos"))

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

        detail = json.loads(outcome.detail)
        assert detail["status"] == RC_RECONSTRUCT
        assert detail["reconstructability"] == 1.0
        assert detail["baseline_id"] == BASELINE_B0
        assert detail["events_count"] == 2

        # Verify underlying retained records retain full plaintext
        events = extract_events(case)
        records = retain_audit_set(BASELINE_B0, events)
        assert len(records) == 2
        for r in records:
            assert isinstance(r, AuditRecord)
            assert r.pseudonym is None  # Plaintext subject_id retained directly
            assert "payload" in r.retained_fields
            assert r.retained_fields["subject_id"] == "patient_alice"
            assert r.witness_anchor is not None
            assert r.epoch_proofs is not None

        # Clean answerable reference probe also succeeds
        probe_outcome = run_baseline(
            BASELINE_B0, answerable_probe_case(), _ctx(BASELINE_B0, "b0-probe")
        )
        assert probe_outcome.observed_outcome == "ADMIT"

        # Parity check reproduces expected reference behavior
        assert parity_check(BASELINE_B0) is True
        assert parity_check(BASELINE_B0_FULL) is True
        assert parity_check(REGISTRY_B0) is True

    def test_b0_adversarial_negative_vector_identity_exposure_and_max_linkability(self) -> None:
        """Adversarial negative: B0 exposes unpseudonymized identities and maximum linkability.

        Under an adversary inspecting audit logs, B0 reveals raw subject identifiers across
        events and epochs without pseudonymization. Linkability score reaches the upper ceiling
        (~0.98), exhibiting severe privacy exposure (privacy gain <= 0.05). Furthermore, when
        evidence is absent from the source (unanswerable omission case), B0 cannot fabricate
        missing evidence and rejects (reconstructability < 0.70).
        """
        case = _synthetic_case("case-b0-neg", num_events=4)
        events = extract_events(case)
        records = retain_audit_set(BASELINE_B0, events)

        # 1. Plaintext identifier leakage: raw subject_id is directly visible in retained fields
        raw_subjects = [r.retained_fields.get("subject_id") for r in records]
        assert all(s == "patient_alice" for s in raw_subjects)

        # 2. Maximum linkability risk under cross-event correlation
        link_score = linkability_score(records)
        assert link_score >= 0.95
        privacy_gain = 1.0 - link_score
        assert privacy_gain <= 0.05

        # 3. Auxiliary join vulnerability: timestamps and metadata correlate with aux data
        aux_data = [
            {"timestamp": "2026-11-15T10:24:00Z", "subject_id": "patient_alice"},
            {"timestamp": "2026-11-15T11:24:00Z", "subject_id": "patient_alice"},
        ]
        link_with_aux = linkability_score(records, aux_data)
        assert link_with_aux >= 0.85
        assert link_with_aux > 0.80

        # 4. Forensic discrimination: on unanswerable omission probe, B0 cannot invent missing epochs
        unans = unanswerable_probe_case()
        unans_outcome = run_baseline(BASELINE_B0, unans, _ctx(BASELINE_B0, "b0-unans"))
        assert unans_outcome.observed_outcome == "REJECT"
        assert unans_outcome.counted_as_success is False
        unans_detail = json.loads(unans_outcome.detail)
        assert unans_detail["status"] == RC_FORENSIC_OMISSION
        assert unans_detail["reconstructability"] < 0.70


# ---------------------------------------------------------------------------
# Arm B1: Minimized Without Receipts
# ---------------------------------------------------------------------------


class TestB1MinimizedWithoutReceiptsFidelity:
    """Fidelity vectors for Arm B1 (minimized without receipts / content digests only)."""

    def test_b1_positive_vector_payload_stripping_and_storage_minimization(self) -> None:
        """Upstream positive: B1 achieves storage minimization by stripping raw payloads.

        B1 drops sensitive clinical payloads and replaces raw subject IDs with an unsalted
        hash pseudonym (sha256_<hex>), reducing linkability from 0.98 (B0) to ~0.64.
        The baseline's parity check verifies expected omission behavior on the reference probe.
        """
        case = _synthetic_case("case-b1-pos", num_events=2)
        events = extract_events(case)
        records = retain_audit_set(BASELINE_B1, events)

        assert len(records) == 2
        for r in records:
            # Raw payload is completely stripped
            assert "payload" not in r.retained_fields
            # Raw subject_id is replaced with unsalted hash
            assert "subject_id" not in r.retained_fields
            assert r.pseudonym is not None
            assert r.pseudonym.startswith("sha256_")

        # Linkability is reduced compared to B0 full retention
        link_b1 = linkability_score(records)
        assert link_b1 < 0.75
        assert link_b1 < 0.95

        # Parity check reproduces expected reference behavior (honest REJECT on answerable probe)
        assert parity_check(BASELINE_B1) is True
        assert parity_check(BASELINE_B1_MIN_NO_RECEIPT) is True
        assert parity_check(REGISTRY_B1) is True

    def test_b1_adversarial_negative_vector_forensic_omission_on_evidence_queries(self) -> None:
        """Adversarial negative: B1 fails to answer forensic queries requiring stripped evidence.

        Because B1 stripped payloads, witness anchors, policy epochs, and consent epochs
        without cryptographic receipt anchoring:
        - Authorization query fails (no purpose, policy epoch, or epoch proofs)
        - Provenance query fails (no commitment digest, no witness anchor)
        - Commit eligibility query fails (no consent epoch proof)
        - Action content verification fails (no payload, no commitment digest)
        Reconstructability drops to 0.0 (< 0.25 threshold), resulting in Outcome REJECT
        with status FORENSIC_OMISSION.
        """
        case = _synthetic_case("case-b1-neg", num_events=3)
        outcome = run_baseline(BASELINE_B1, case, _ctx(BASELINE_B1, "case-b1-neg"))

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is False

        detail = json.loads(outcome.detail)
        assert detail["status"] == RC_FORENSIC_OMISSION
        assert detail["reconstructability"] < 0.25
        assert detail["reconstructability"] == 0.0
        assert detail["baseline_id"] == BASELINE_B1

        # Underlying retained records have zero cryptographic anchors
        events = extract_events(case)
        records = retain_audit_set(BASELINE_B1, events)
        for r in records:
            assert r.commitment_digest is None
            assert r.witness_anchor is None
            assert r.epoch_proofs is None
            assert r.omitted_field_digest is None


# ---------------------------------------------------------------------------
# Arm B2: Minimized With Receipt Anchoring
# ---------------------------------------------------------------------------


class TestB2MinimizedWithReceiptAnchoringFidelity:
    """Fidelity vectors for Arm B2 (minimized log with cryptographic receipt anchoring)."""

    def test_b2_positive_vector_receipt_anchoring_recovers_reconstruction(self) -> None:
        """Upstream positive: receipt anchoring recovers forensic reconstructability.

        Even though raw clinical payloads are stripped from storage, B2 retains salted
        pseudonyms, commitment digests, witness anchors, and epoch proofs.
        All four forensic query classes are answerable (reconstructability = 1.0 >= 0.85),
        returning Outcome ADMIT with status RECONSTRUCT.
        """
        case = _synthetic_case("case-b2-pos", num_events=2)
        outcome = run_baseline(BASELINE_B2, case, _ctx(BASELINE_B2, "case-b2-pos"))

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

        detail = json.loads(outcome.detail)
        assert detail["status"] == RC_RECONSTRUCT
        assert detail["reconstructability"] >= 0.85
        assert detail["reconstructability"] == 1.0
        assert detail["baseline_id"] == BASELINE_B2

        # Verify underlying records: payload stripped, but cryptographic anchors retained
        events = extract_events(case)
        records = retain_audit_set(BASELINE_B2, events)
        for r in records:
            assert "payload" not in r.retained_fields
            assert r.commitment_digest is not None
            assert r.witness_anchor is not None
            assert r.witness_anchor.startswith("anchor_")
            assert r.epoch_proofs is not None
            assert r.epoch_proofs.get("anchored") is True
            assert r.omitted_field_digest is not None
            assert r.pseudonym is not None
            assert r.pseudonym.startswith("psn_")

        # Parity check reproduces expected reference behavior
        assert parity_check(BASELINE_B2) is True
        assert parity_check(BASELINE_B2_MIN_ANCHORED) is True

    def test_b2_adversarial_negative_vector_linkability_exceeds_b3_under_pseudonym_clustering(
        self,
    ) -> None:
        """Adversarial negative: B2 linkability exceeds B3 under pseudonym clustering.

        B2 uses static salted pseudonyms (psn_<hash>) that persist across epochs and
        purposes for the same subject, alongside exact timestamps. Under an adversary
        clustering pseudonyms across distinct epochs (e.g. epoch-1 vs epoch-2) and purposes,
        B2 pseudonyms remain identical, yielding linkability ~0.41, which strictly and
        substantially exceeds candidate B3 (~0.11).
        """
        # Multi-epoch, multi-purpose case for the same patient
        case = _synthetic_case("case-b2-link", num_events=4, subject_id="patient_alice")
        events = extract_events(case)

        records_b2 = retain_audit_set(BASELINE_B2, events)
        records_b3 = retain_audit_set(BASELINE_B3, events)

        # B2 pseudonyms are STATIC across different epochs for the same patient
        b2_pseudonyms = {r.pseudonym for r in records_b2}
        assert len(b2_pseudonyms) == 1  # All 4 events share identical pseudonym!

        # B3 pseudonyms are ROTATED per (tenant, purpose, epoch) via epoch-keyed HMAC
        b3_pseudonyms = {r.pseudonym for r in records_b3}
        assert len(b3_pseudonyms) > 1  # Pseudonyms differ across epochs and purposes

        # Empirical linkability score: B2 linkability strictly exceeds B3
        link_b2 = linkability_score(records_b2)
        link_b3 = linkability_score(records_b3)

        assert link_b2 > link_b3
        assert link_b2 >= 0.35
        assert link_b3 <= 0.20
        assert link_b2 - link_b3 >= 0.20  # Significant linkage gap demonstrated


# ---------------------------------------------------------------------------
# Arm B3: Candidate ReceiptMin (Purpose-Bound Minimized Receipts)
# ---------------------------------------------------------------------------


class TestB3CandidateReceiptMinFidelity:
    """Fidelity vectors for Arm B3 (candidate ReceiptMin: purpose-bound receipts)."""

    def test_b3_positive_vector_optimal_frontier_reconstruction(self) -> None:
        """Upstream positive: ReceiptMin recovers full forensic reconstruction.

        Through purpose-bound HMAC receipts, witness anchors, epoch proofs, coarsened timestamps,
        and explicit retention maps, B3 achieves 100% forensic reconstructability
        (reconstructability = 1.0, Outcome ADMIT with status RECONSTRUCT).
        """
        case = _synthetic_case("case-b3-pos", num_events=3)
        outcome = run_baseline(BASELINE_B3, case, _ctx(BASELINE_B3, "case-b3-pos"))

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

        detail = json.loads(outcome.detail)
        assert detail["status"] == RC_RECONSTRUCT
        assert detail["reconstructability"] >= 0.85
        assert detail["reconstructability"] == 1.0
        assert detail["linkability"] <= 0.20
        assert detail["baseline_id"] == BASELINE_B3

        # Verify underlying records: purpose-bound pseudonym, coarsened timestamp, retention map
        events = extract_events(case)
        records = retain_audit_set(BASELINE_B3, events)
        for r in records:
            assert r.pseudonym is not None
            assert r.pseudonym.startswith("psn_rm_")
            assert r.timestamp is not None
            assert r.timestamp.endswith(":00:00Z")  # Hour-coarsened timestamp
            assert r.retention_map is not None
            assert r.retention_map.get("payload") == "dropped_at_commit"
            assert r.epoch_proofs is not None
            assert r.epoch_proofs.get("purpose_bound") is True

        # Parity check reproduces expected reference behavior
        assert parity_check(BASELINE_B3) is True
        assert parity_check(BASELINE_B3_RECEIPTMIN) is True
        assert parity_check(REGISTRY_B4) is True

    def test_b3_adversarial_negative_vector_adversarial_pseudonym_clustering_defeated(
        self,
    ) -> None:
        """Adversarial negative: adversary cannot link B3 pseudonyms across epochs/purposes.

        Under an adversary attempting cross-epoch and cross-purpose linkage, B3 derives
        epoch-keyed HMAC pseudonyms bound to (tenant, purpose, policy_epoch) and coarsens
        timestamps. Cross-epoch clustering fails, bounding linkability to <= 0.20 (~0.11),
        strictly dominating B2 (~0.41) and B1 (~0.64) on the privacy-reconstructability frontier.
        """
        case = _synthetic_case("case-b3-neg", num_events=4, subject_id="patient_alice")
        events = extract_events(case)
        records_b3 = retain_audit_set(BASELINE_B3, events)

        # Pseudonyms are distinct across epochs and purposes
        pseudonyms = [r.pseudonym for r in records_b3]
        assert len(set(pseudonyms)) >= 2

        # Linkability is strictly bounded
        link_b3 = linkability_score(records_b3)
        assert link_b3 <= 0.20
        privacy_gain = 1.0 - link_b3
        assert privacy_gain >= 0.80

    def test_b3_adversarial_stub_refusal_discrimination(self) -> None:
        """Adversarial negative: constant-perfect and detect-all stubs are refused.

        refuse_constant_stub verifies that the candidate adapter discriminates between
        answerable and unanswerable probe pairs, rejecting constant-perfect stubs
        (CONSTANT_STUB_REFUSED / STUB_DETECT_ALL_REFUSED) and accepting discriminating adapters.
        """
        # 1. B3 itself separates answerable and unanswerable probes cleanly
        adapter_outcome = refuse_constant_stub(
            lambda probe: run_baseline(BASELINE_B3, probe, _ctx(BASELINE_B3, "probe"))
        )
        assert adapter_outcome.observed_outcome == "ADMIT"
        assert adapter_outcome.detail == RC_STUB_SEPARATION_OK

        # 2. Constant-perfect stub returning ADMIT on all probes is refused
        with pytest.raises(PstBaselineError) as exc_all:
            refuse_constant_stub(
                lambda probe: Outcome(
                    observed_outcome="ADMIT",
                    counted_as_success=True,
                    retriable=False,
                    detail="constant_admit",
                )
            )
        assert exc_all.value.reason_code in (RC_STUB_CONSTANT, RC_STUB_DETECT_ALL)

        # 3. Constant-reject stub returning REJECT on all probes is refused
        with pytest.raises(PstBaselineError) as exc_none:
            refuse_constant_stub(
                lambda probe: Outcome(
                    observed_outcome="REJECT",
                    counted_as_success=False,
                    retriable=False,
                    detail="constant_reject",
                )
            )
        assert exc_none.value.reason_code in (RC_STUB_CONSTANT, RC_STUB_DETECT_NONE)


# ---------------------------------------------------------------------------
# Reconstruction-versus-Linkability Frontier Comparative Analysis
# ---------------------------------------------------------------------------


class TestFrontierPropertiesAndTradeoffs:
    """Validate empirical frontier coordinates and mathematical ordering across arms."""

    def test_frontier_empirical_ordering_across_cohort(self) -> None:
        """Frontier coordinates derived strictly from sample reflect expected ordering.

        No invented numbers: every coordinate is derived mechanically from the sample cases.
        Asserts:
        - B0 achieves utility upper bound (reconstructability = 1.0) and linkability ceiling (>= 0.95).
        - B1 loses reconstructability (< 0.25) vs B0.
        - B2 recovers reconstructability (>= 0.85) but linkability remains elevated (~0.41).
        - B3 recovers reconstructability (>= 0.85) while minimizing linkability (<= 0.20),
          strictly dominating B2 in privacy gain.
        """
        cohort = [
            _synthetic_case(f"cohort-case-{i}", num_events=3, subject_id=f"patient_{i % 3}")
            for i in range(6)
        ]
        frontier = compute_frontier(cohort)

        assert set(frontier.keys()) == {BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3}

        pt0 = frontier[BASELINE_B0]
        pt1 = frontier[BASELINE_B1]
        pt2 = frontier[BASELINE_B2]
        pt3 = frontier[BASELINE_B3]

        assert isinstance(pt0, FrontierPoint)
        assert isinstance(pt3, FrontierPoint)

        # Reconstructability ordering
        assert pt0.reconstructability == 1.0
        assert pt1.reconstructability < 0.25
        assert pt2.reconstructability >= 0.85
        assert pt3.reconstructability >= 0.85
        assert pt2.reconstructability > pt1.reconstructability + 0.60
        assert pt3.reconstructability > pt1.reconstructability + 0.60

        # Linkability ordering: B0 > B1 > B2 > B3
        assert pt0.linkability > pt1.linkability
        assert pt1.linkability > pt2.linkability
        assert pt2.linkability > pt3.linkability
        assert pt3.linkability <= 0.20

        # Privacy gain ordering: B3 > B2 > B1 > B0
        assert pt3.privacy_gain > pt2.privacy_gain
        assert pt2.privacy_gain > pt1.privacy_gain
        assert pt1.privacy_gain > pt0.privacy_gain

        # Serialization check
        d3 = pt3.to_dict()
        assert d3["arm_id"] == BASELINE_B3
        assert "reconstructability" in d3
        assert "linkability" in d3
        assert "privacy_gain" in d3


# ---------------------------------------------------------------------------
# External Unavailable Baselines (Rule 8 Honesty Tests)
# ---------------------------------------------------------------------------


class TestUnavailableExternalBaselinesHonesty:
    """Verify honest reporting of external upstreams without runnable local sources (Rule 8)."""

    @pytest.mark.parametrize("baseline_id", sorted(EXTERNAL_UNAVAILABLE_BASELINES))
    def test_unavailable_baselines_report_not_run_external_honestly(self, baseline_id: str) -> None:
        """Every external unavailable baseline returns NOT_RUN_EXTERNAL with BASELINE_UNAVAILABLE.

        Never replaced by a custom toy stub under the pinned name (EXECUTION_CONTRACT rule 8).
        Counted as success is False, retriable is False, and parity_check returns None.
        """
        case = _synthetic_case("case-ext-honesty", num_events=1)
        outcome = run_baseline(baseline_id, case, _ctx(baseline_id, "case-ext-honesty"))

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.retriable is False
        assert outcome.detail.startswith(RC_BASELINE_UNAVAILABLE)
        assert baseline_id in outcome.detail

        # Parity check returns None for unavailable external upstreams
        assert parity_check(baseline_id) is None

        # Registry metadata confirms external non-runnable status
        assert baseline_id in BASELINE_REGISTRY
        spec = BASELINE_REGISTRY[baseline_id]
        assert spec.runnable_in_process is False
        assert spec.fidelity_status == "UNAVAILABLE_NOT_RUN"


# ---------------------------------------------------------------------------
# Fail-Closed Error Semantics and Boundary Tests
# ---------------------------------------------------------------------------


class TestFailClosedErrorSemantics:
    """Assert stable uppercase reason codes on malformed inputs and unknown arms."""

    def test_unknown_baseline_id_raises_baseline_unknown(self) -> None:
        """Requesting an unknown baseline raises PstBaselineError with RC_BASELINE_UNKNOWN."""
        case = _synthetic_case("case-unknown", num_events=1)
        with pytest.raises(PstBaselineError) as exc:
            run_baseline("unknown_phantom_arm", case, _ctx())
        assert exc.value.reason_code == RC_BASELINE_UNKNOWN

    def test_malformed_case_raises_case_malformed(self) -> None:
        """Passing non-mapping case structures raises PstBaselineError with RC_CASE_MALFORMED."""
        with pytest.raises(PstBaselineError) as exc_case:
            run_baseline(BASELINE_B0, "not_a_mapping", _ctx())  # type: ignore[arg-type]
        assert exc_case.value.reason_code == RC_CASE_MALFORMED

        with pytest.raises(PstBaselineError) as exc_extract:
            extract_events(["invalid", "sequence"])  # type: ignore[arg-type]
        assert exc_extract.value.reason_code == RC_CASE_MALFORMED

        with pytest.raises(PstBaselineError) as exc_rec:
            reconstructability(12345, [])  # type: ignore[arg-type]
        assert exc_rec.value.reason_code == RC_CASE_MALFORMED

        with pytest.raises(PstBaselineError) as exc_link:
            linkability_score(12345)  # type: ignore[arg-type]
        assert exc_link.value.reason_code == RC_CASE_MALFORMED

    def test_empty_sample_frontier_raises_sample_empty(self) -> None:
        """compute_frontier over empty sample raises PstBaselineError with RC_SAMPLE_EMPTY."""
        with pytest.raises(PstBaselineError) as exc:
            compute_frontier([])
        assert exc.value.reason_code == RC_SAMPLE_EMPTY
        assert "empty sample" in exc.value.detail

    def test_stub_refusal_empty_probes_raises_context_malformed(self) -> None:
        """refuse_constant_stub with empty probe sets raises RC_CONTEXT_MALFORMED."""
        with pytest.raises(PstBaselineError) as exc:
            refuse_constant_stub(lambda _: Outcome("ADMIT"), answerable_probes=())
        assert exc.value.reason_code == RC_CONTEXT_MALFORMED
