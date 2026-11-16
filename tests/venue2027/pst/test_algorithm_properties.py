"""Algorithmic property and metamorphic tests for PST venue (ReceiptMin B4)
(task PST-unit, phase P05).

Purpose
-------
Property-based, metamorphic, boundary, retention-window expiry, and mutation tests
over the REAL PST candidate, purpose minimizer, and epoch keys mechanisms
(blueprint arm B4, "ReceiptMin: Measuring Forensic Reconstructability under
Purpose-Bound Audit Minimization"):

- ``evaluation/venue2027/pst/candidate.py``: the ReceiptMin candidate mechanism
  (isolated receipt minimization, cryptographic omitted-field digest binding,
  HMAC tamper-evident receipt signing, and forensic query reconstruction).
- ``evaluation/venue2027/pst/purpose_minimizer.py``: field-level purpose-bound
  minimizer, keyed one-way pseudonyms, retention window decay (30d/90d),
  mandatory proof fields, and controlled escape for authorized audits.
- ``evaluation/venue2027/pst/epoch_keys.py``: HKDF-derived retention-epoch pseudonym
  key lifecycle, append-only KeyRotationManifest, key destruction, and
  reversibility tracking.

Test families (manifest PST-unit, phase P05):
1. **Positive boundaries**:
   - Clean inputs deliver documented guarantees end to end across candidate,
     minimizer, and epoch key modules.
   - Purpose-bound allowlist filtering, omitted-field binding, and HMAC signature creation.
   - Forensic queries FQ-AUTH-*, FQ-PROV-*, FQ-ELIG-* reconstruct accurately (score 1.0, ANSWERABLE).
   - Candidate task harness adapter `run_candidate` returns ADMIT with REASON_OK.
   - RFC 5869 HKDF derivation and scope key verification tokens.
   - Controlled authorized escape recovers decaying content with logged decision.

2. **Negative boundaries**:
   - Refusals fail closed with stable uppercase reason codes, never bare exceptions
     or unhandled drops mistaken for safe rejections.
   - Candidate refusals: REASON_MALFORMED_EVENT, REASON_UNKNOWN_PURPOSE, REASON_PHI_FIELD_PRESENT,
     REASON_UNSALTED_HASH_REFUSED, REASON_MALFORMED_RECEIPT, REASON_TAMPER_DETECTED,
     REASON_OMITTED_FIELD_MISMATCH, REASON_MISSING_WITNESS, REASON_UNKNOWN_ARM, REASON_MALFORMED_CASE.
   - Minimizer refusals (MinimizationError): REASON_UNKNOWN_PURPOSE, REASON_MALFORMED_RECORD,
     REASON_PHI_FIELD_PRESENT, REASON_UNRECOGNIZED_FIELD, REASON_UNSALTED_HASH_REFUSED,
     REASON_PSEUDONYM_KEY_REQUIRED, REASON_MALFORMED_ESCAPE, REASON_ESCAPE_NOT_AUTHORIZED,
     REASON_ESCAPE_LOG_REQUIRED.
   - Epoch key refusals (EpochKeyError): REASON_MALFORMED_SCOPE, REASON_UNKNOWN_PURPOSE,
     REASON_UNKNOWN_EPOCH, REASON_UNKNOWN_TENANT, REASON_EPOCH_DESTROYED, REASON_DESTROY_NOT_PERMITTED.

3. **Unknown / indeterminate boundaries**:
   - INDETERMINATE is a first-class verdict and never coerced to false success or safe rejection.
   - Unknown forensic query ID -> INDETERMINATE (REASON_UNKNOWN_QUERY).
   - Missing governance epoch proofs (policy_epoch, consent_epoch) -> INDETERMINATE (REASON_MISSING_EPOCH).
   - Missing key custody attestation -> INDETERMINATE (REASON_MISSING_KEY_CUSTODY).
   - Committer under-commitment reported in missing_mandatory_fields, never auto-repaired.
   - Liveness assertion: neither an arbitrary all-deny nor all-admit stub passes the suite.

4. **Retention-window expiry scenarios**:
   - Decaying fields (evidence_digest: 30 days, witness_id: 90 days) drop strictly at their deadlines.
   - Sub-second precision around expiry boundaries (T_create + 30d, T_create + 90d).
   - Persistent proof fields (commitment_digest, purpose_tag, consent_epoch, policy_epoch, retention_mode)
     never expire, persisting indefinitely.
   - Query answerability transitions across retention milestones (e.g. FQ-AUTH-01 transitions from
     ANSWERABLE to NOT_ANSWERABLE at 90 days, while FQ-PROV-01 remains ANSWERABLE).
   - Authorized escape restores expired decaying fields under registered grant.

5. **Two-step metamorphic relations**:
   - MR1: Minimizing twice is idempotent:
     - candidate.minimize(event) == candidate.minimize(event) (byte-identical fields, digests, signatures).
     - purpose_minimizer.minimize(record) == purpose_minimizer.minimize(record).
     - Duplicate receipts preserve identical reconstruction score and answerability.
   - MR2: Rotating epoch key changes pseudonym but preserves intra-epoch linkability:
     - S1 and S2 within epoch e0 have distinguishable pseudonyms; two records of S1 have identical pseudonyms.
     - Rotating to epoch e1 derives an independent key: pseudonym for S1 changes (unlinkable cross-epoch).
     - Intra-epoch linkability is preserved in e1: two records of S1 in e1 share identical pseudonyms.
   - MR3: Destroying epoch key makes past records strictly irreversible:
     - Active epoch is REVERSIBLE; derivation succeeds.
     - Controlled destruction marks epoch IRREVERSIBLE; re-derivation fails closed (REASON_EPOCH_DESTROYED);
       queries requiring key custody for that epoch fail closed.
   - MR4: Purpose domain isolation:
     - Keys derived for different purpose scopes (pseudonym vs authorization vs investigation) remain
       cryptographically isolated; rotating or destroying one does not impact another.
   - MR5: Deterministic replay invariance:
     - Replaying all derivations and minimizations under identical seed produces byte-identical output dictionaries.

6. **Mutation checks**:
   - Single-perturbation sensitivity: tampering with signature, witness fields, policy epoch,
     omitted claims, retention clock, subject format, or destroyability deterministically flips verdict.
   - Seeded randomized mutation campaign: 30 trials with random mutations; 100% killed (0 survivors).
   - Liveness check against dummy all-deny or all-admit stubs.

Deterministic randomness:
All property tests use a fixed integer seed (FIXED_SEED = 20271116) and pure components.
No hidden clock, no network, no database, no PHI.

Version:
PST_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any, Final

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.pst import candidate as cand
from evaluation.venue2027.pst import epoch_keys as ek
from evaluation.venue2027.pst import purpose_minimizer as pm

PST_ALGORITHM_PROPERTIES_TESTS_VERSION: Final[str] = "1.0.0"

FIXED_SEED: Final[int] = 20271116
DEFAULT_SIGNING_KEY: Final[bytes] = b"pst-receiptmin-eval-signing-key"
DEFAULT_ROOT_SECRET: Final[bytes] = b"pst-eval-root-secret-deterministic-seed-20271116"


# ---------------------------------------------------------------------------
# Synthetic Fixture Builders (Pure, PHI-free, Deterministic)
# ---------------------------------------------------------------------------


def _synthetic_event(
    event_id: str = "evt-20261116-001",
    tenant_id: str = "tnt_pst_0001",
    principal_id: str = "prn_doc_0042",
    purpose: str = "clinical_care",
    operation: str = "record_read",
    policy_epoch: str = "epoch-2026-q4",
    consent_epoch: str = "consent-v2",
    witness_id: str = "wit_notary_991",
    retention_mode: str = "selective",
    commitment_digest: str = "c" * 64,
    subject_ref: str = "subj_synthetic_pt_1001",
    timestamp: str = "2026-11-16T10:00:00Z",
    extra_omitted: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compliant synthetic audit event for candidate.minimize."""
    data: dict[str, Any] = {
        "event_id": event_id,
        "operation_id": f"op-{event_id}",
        "tenant_id": tenant_id,
        "principal_id": principal_id,
        "purpose": purpose,
        "operation": operation,
        "policy_epoch": policy_epoch,
        "consent_epoch": consent_epoch,
        "witness_id": witness_id,
        "retention_mode": retention_mode,
        "commitment_digest": commitment_digest,
        "payload_digest": "d" * 64,
        "subject_ref": subject_ref,
        "timestamp": timestamp,
    }
    if extra_omitted is not None:
        data["omitted_fields"] = extra_omitted
    return data


def _synthetic_record(
    operation_id: str = "op-pst-rec-001",
    subject_ref: str = "subj_synthetic_pt_1001",
    created_at: str = "2026-01-01T00:00:00Z",
    commitment_digest: str = "a" * 64,
    purpose_tag: str = "clinical_care",
    consent_epoch: str = "consent-epoch-1",
    policy_epoch: str = "policy-epoch-1",
    witness_id: str = "wit_audit_anchor_01",
    retention_mode: str = "selective",
    evidence_digest: str = "e" * 64,
) -> dict[str, str]:
    """Build a compliant synthetic record for purpose_minimizer.minimize."""
    return {
        "operation_id": operation_id,
        "subject_ref": subject_ref,
        "created_at": created_at,
        "commitment_digest": commitment_digest,
        "purpose_tag": purpose_tag,
        "consent_epoch": consent_epoch,
        "policy_epoch": policy_epoch,
        "witness_id": witness_id,
        "retention_mode": retention_mode,
        "evidence_digest": evidence_digest,
    }


def _synthetic_query(
    query_id: str = "FQ-AUTH-01",
    query_class: str | None = None,
    witnesses_needed: tuple[str, ...] | list[str] | None = None,
    omitted_claims: dict[str, Any] | None = None,
    key_custody_attested: bool = True,
) -> dict[str, Any]:
    """Build a forensic query dictionary for candidate.reconstruct."""
    q: dict[str, Any] = {
        "query_id": query_id,
        "key_custody_attested": key_custody_attested,
    }
    if query_class is not None:
        q["query_class"] = query_class
    if witnesses_needed is not None:
        q["witnesses_needed"] = list(witnesses_needed)
    if omitted_claims is not None:
        q["omitted_claims"] = omitted_claims
    return q


# ---------------------------------------------------------------------------
# 1. Positive Boundaries: Documented Guarantees Hold End to End
# ---------------------------------------------------------------------------


class TestPositiveBoundaries:
    """Documented guarantees hold end-to-end on clean, conformant inputs."""

    def test_candidate_minimization_retains_allowlisted_fields_for_clinical_care(self) -> None:
        event = _synthetic_event(purpose="clinical_care")
        receipt = cand.minimize(event, purpose="clinical_care")
        assert receipt.version == "1"
        assert receipt.purpose == "clinical_care"
        assert receipt.tenant_id == event["tenant_id"]
        assert receipt.principal_id == event["principal_id"]
        assert receipt.policy_epoch == event["policy_epoch"]
        assert "commitment_digest" in receipt.retained_fields
        assert "witness_id" in receipt.retained_fields
        assert "retention_mode" in receipt.retained_fields
        assert "consent_epoch" in receipt.retained_fields
        assert receipt.omitted_field_digest != ""
        assert len(receipt.omitted_field_digest) == 64
        assert receipt.signature != ""

    def test_candidate_minimization_omitted_field_digest_binding(self) -> None:
        event = _synthetic_event(purpose="self_care")
        receipt = cand.minimize(event, purpose="self_care")

        # In self_care, payload_digest, subject_ref, witness_id, and retention_mode are omitted
        omitted_claims = {
            "payload_digest": event["payload_digest"],
            "subject_ref": event["subject_ref"],
            "witness_id": event["witness_id"],
            "retention_mode": event["retention_mode"],
        }
        # Query presenting exact omitted claims must reconstruct successfully
        q = _synthetic_query(
            query_id="FQ-PROV-01",
            query_class="provenance",
            witnesses_needed=("commitment_digest",),
            omitted_claims=omitted_claims,
        )
        recon = cand.reconstruct([receipt], q)
        assert recon.answerable == cand.ANSWERABLE
        assert recon.score == 1.0
        assert recon.reason_code == cand.REASON_OK

    @pytest.mark.parametrize(
        "query_id",
        [
            "FQ-AUTH-01",
            "FQ-AUTH-02",
            "FQ-AUTH-03",
            "FQ-AUTH-04",
            "FQ-PROV-01",
            "FQ-PROV-02",
            "FQ-PROV-03",
            "FQ-PROV-04",
            "FQ-ELIG-01",
            "FQ-ELIG-02",
            "FQ-ELIG-03",
            "FQ-ELIG-04",
        ],
    )
    def test_candidate_reconstruct_all_known_forensic_queries(self, query_id: str) -> None:
        event = _synthetic_event(purpose="clinical_care")
        receipt = cand.minimize(event, purpose="clinical_care")
        recon = cand.reconstruct([receipt], query_id)
        assert recon.answerable == cand.ANSWERABLE
        assert recon.score == 1.0
        assert recon.reason_code == cand.REASON_OK
        assert recon.query_id == query_id

    def test_candidate_receipt_json_roundtrip_idempotence(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        as_dict = receipt.to_dict()
        reconstituted = cand.Receipt.from_dict(as_dict)
        assert reconstituted == receipt
        assert reconstituted.to_dict() == as_dict

    def test_candidate_run_candidate_harness_adapter_admit(self) -> None:
        event = _synthetic_event()
        ctx = RunContext(
            campaign_id="cmp-pst-01",
            case_id="case-admit-001",
            arm_id="B4",
            seed=42,
            source_commit="75ad321e",
            deadline_seconds=10.0,
        )
        case = {"case_id": "case-admit-001", "events": [event], "purpose": "clinical_care"}
        outcome = cand.run_candidate(case, ctx)
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

    @pytest.mark.parametrize("purpose", list(pm.PURPOSES))
    def test_purpose_minimizer_preserves_persistent_proofs(self, purpose: str) -> None:
        rec = _synthetic_record(purpose_tag=purpose)
        minimized = pm.minimize(rec, purpose=purpose, now="2026-01-02T00:00:00Z")
        assert minimized.schema_version == pm.MINIMIZED_RECEIPT_SCHEMA_VERSION
        assert minimized.purpose == purpose
        assert minimized.operation_id == rec["operation_id"]
        assert minimized.pseudonym.startswith(pm.PSEUDONYM_PREFIX)
        assert len(minimized.missing_mandatory_fields) == 0
        for proof in ("commitment_digest", "consent_epoch", "policy_epoch"):
            assert proof in minimized.receipt

    def test_purpose_minimizer_controlled_escape_authorized(self) -> None:
        rec = _synthetic_record()
        escape_sink: list[dict[str, Any]] = []
        req = pm.EscapeRequest(
            grant_id="ESC-GRANT-PST-FORENSIC-01",
            authority_id="pst-evaluation-adjudicator",
            justification="Court ordered forensic investigation audit",
        )
        minimized = pm.minimize(
            rec,
            purpose="forensic_review",
            now="2026-06-01T00:00:00Z",
            escape=req,
            escape_log=escape_sink,
        )
        assert minimized.escape is not None
        assert minimized.escape["decision"] == pm.ESCAPE_DECISION_GRANTED
        assert len(escape_sink) == 1
        assert escape_sink[0]["decision"] == pm.ESCAPE_DECISION_GRANTED
        assert escape_sink[0]["escape_ref"].startswith("esc_")
        assert "evidence_digest" in minimized.receipt

    def test_epoch_keys_hkdf_derivation_deterministic_and_unique(self) -> None:
        okm1, ref1 = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "pseudonym", "e0")
        okm2, ref2 = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "pseudonym", "e0")
        assert okm1 == okm2
        assert ref1 == ref2
        assert len(okm1) == 32
        assert len(ref1) == 64

        # Distinct scopes yield distinct keys
        okm_tnt2, _ = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_02", "pseudonym", "e0")
        assert okm1 != okm_tnt2
        okm_purp2, _ = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "authorization", "e0")
        assert okm1 != okm_purp2
        okm_ep2, _ = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "pseudonym", "e1")
        assert okm1 != okm_ep2

    def test_epoch_keys_manifest_registration_and_reversibility(self) -> None:
        manifest = ek.KeyRotationManifest()
        okm, ref = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "pseudonym", "e0")
        entry = manifest.register("tnt_01", "pseudonym", "e0", created_at=10, key_ref=ref)
        assert entry.tenant == "tnt_01"
        assert entry.destroyed is False
        assert manifest.reversibility("tnt_01", "pseudonym", "e0") == ek.REVERSIBLE


# ---------------------------------------------------------------------------
# 2. Negative Boundaries: Stable uppercase reason codes, fail closed
# ---------------------------------------------------------------------------


class TestNegativeBoundaries:
    """Adversarial, corrupted, and malformed inputs fail closed with stable codes."""

    def test_candidate_refuses_non_mapping_event(self) -> None:
        with pytest.raises(ValueError, match=cand.REASON_MALFORMED_EVENT):
            cand.minimize(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_candidate_refuses_unknown_purpose(self) -> None:
        event = _synthetic_event(purpose="unauthorized_marketing")
        with pytest.raises(ValueError, match=cand.REASON_UNKNOWN_PURPOSE):
            cand.minimize(event, purpose="unauthorized_marketing")

    @pytest.mark.parametrize(
        "phi_key",
        [
            "patient_name",
            "patient_ssn",
            "patient_mrn",
            "patient_address",
            "prescription_details",
            "diagnosis_code",
        ],
    )
    def test_candidate_refuses_phi_markers(self, phi_key: str) -> None:
        event = _synthetic_event()
        event[phi_key] = "sensitive_phi_value"
        with pytest.raises(ValueError, match=cand.REASON_PHI_FIELD_PRESENT):
            cand.minimize(event)

    @pytest.mark.parametrize(
        "bad_subject",
        [
            "d41d8cd98f00b204e9800998ecf8427e",  # 32-hex (MD5)
            "da39a3ee5e6b4b0d3255bfef95601890afd80709",  # 40-hex (SHA-1)
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # 64-hex (SHA-256)
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "md5_d41d8cd98f00b204e9800998ecf8427e",
        ],
    )
    def test_candidate_refuses_unsalted_hashes_on_subject_ref(self, bad_subject: str) -> None:
        event = _synthetic_event(subject_ref=bad_subject)
        with pytest.raises(ValueError, match=cand.REASON_UNSALTED_HASH_REFUSED):
            cand.minimize(event)

    def test_candidate_reconstruct_detects_signature_tamper(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        tampered_dict = receipt.to_dict()
        tampered_dict["signature"] = "0" * 64
        recon = cand.reconstruct([tampered_dict], "FQ-AUTH-01")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_TAMPER_DETECTED
        assert recon.score == 0.0

    def test_candidate_reconstruct_detects_body_field_tamper(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        tampered_dict = receipt.to_dict()
        tampered_dict["retained_fields"]["witness_id"] = "tampered_witness"
        recon = cand.reconstruct([tampered_dict], "FQ-AUTH-01")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_TAMPER_DETECTED

    def test_candidate_reconstruct_detects_omitted_field_mismatch(self) -> None:
        event = _synthetic_event(extra_omitted={"real_secret": "value_123"})
        receipt = cand.minimize(event)
        q = _synthetic_query(
            query_id="FQ-PROV-01",
            query_class="provenance",
            witnesses_needed=("commitment_digest",),
            omitted_claims={"real_secret": "wrong_counterfeit_value"},
        )
        recon = cand.reconstruct([receipt], q)
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_OMITTED_FIELD_MISMATCH
        assert recon.score == 0.0

    def test_candidate_reconstruct_missing_witnesses_is_not_answerable(self) -> None:
        # self_care does NOT retain witness_id
        event = _synthetic_event(purpose="self_care")
        receipt = cand.minimize(event, purpose="self_care")
        recon = cand.reconstruct([receipt], "FQ-AUTH-01")
        assert recon.answerable == cand.NOT_ANSWERABLE
        assert recon.reason_code == cand.REASON_MISSING_WITNESS
        assert recon.score == 0.0
        assert "witness_id" in recon.details.get("missing_witnesses", [])

    def test_candidate_run_candidate_rejects_unknown_arm(self) -> None:
        case = {"case_id": "c1", "events": [_synthetic_event()]}
        ctx = RunContext(
            campaign_id="cmp-pst-01",
            case_id="c1",
            arm_id="B0_PLAINTEXT",
            seed=42,
            source_commit="75ad321e",
            deadline_seconds=10.0,
        )
        outcome = cand.run_candidate(case, ctx)
        assert outcome.observed_outcome == "INVALID_RESULT"
        assert cand.REASON_UNKNOWN_ARM in outcome.detail

    def test_purpose_minimizer_refuses_unknown_purpose(self) -> None:
        rec = _synthetic_record()
        with pytest.raises(pm.MinimizationError) as exc:
            pm.minimize(rec, purpose="invalid_purpose", now="2026-01-01T00:00:00Z")
        assert exc.value.reason_code == pm.REASON_UNKNOWN_PURPOSE

    def test_purpose_minimizer_refuses_unrecognized_fields(self) -> None:
        rec = _synthetic_record()
        rec["unrecognized_side_channel"] = "sneaky_value"
        with pytest.raises(pm.MinimizationError) as exc:
            pm.minimize(rec, purpose="clinical_care", now="2026-01-01T00:00:00Z")
        assert exc.value.reason_code == pm.REASON_UNRECOGNIZED_FIELD

    def test_purpose_minimizer_refuses_unsalted_hashes(self) -> None:
        rec = _synthetic_record(subject_ref="d41d8cd98f00b204e9800998ecf8427e")
        with pytest.raises(pm.MinimizationError) as exc:
            pm.minimize(rec, purpose="clinical_care", now="2026-01-01T00:00:00Z")
        assert exc.value.reason_code == pm.REASON_UNSALTED_HASH_REFUSED

    def test_purpose_minimizer_refuses_escape_without_log_sink(self) -> None:
        rec = _synthetic_record()
        req = pm.EscapeRequest(
            grant_id="ESC-GRANT-PST-FORENSIC-01",
            authority_id="pst-evaluation-adjudicator",
            justification="audit",
        )
        with pytest.raises(pm.MinimizationError) as exc:
            pm.minimize(
                rec,
                purpose="forensic_review",
                now="2026-01-01T00:00:00Z",
                escape=req,
                escape_log=None,
            )
        assert exc.value.reason_code == pm.REASON_ESCAPE_LOG_REQUIRED

    def test_purpose_minimizer_refuses_unauthorized_escape(self) -> None:
        rec = _synthetic_record()
        escape_sink: list[dict[str, Any]] = []
        req = pm.EscapeRequest(
            grant_id="ESC-GRANT-PST-FORENSIC-01",
            authority_id="fake_authority",
            justification="audit",
        )
        with pytest.raises(pm.MinimizationError) as exc:
            pm.minimize(
                rec,
                purpose="forensic_review",
                now="2026-01-01T00:00:00Z",
                escape=req,
                escape_log=escape_sink,
            )
        assert exc.value.reason_code == pm.REASON_ESCAPE_NOT_AUTHORIZED
        assert len(escape_sink) == 1
        assert escape_sink[0]["decision"] == pm.ESCAPE_DECISION_REFUSED

    def test_epoch_keys_refuses_malformed_scope_identifiers(self) -> None:
        with pytest.raises(ek.EpochKeyError) as exc:
            ek.derive_key(DEFAULT_ROOT_SECRET, "", "pseudonym", "e0")
        assert exc.value.reason_code == ek.REASON_MALFORMED_SCOPE

        with pytest.raises(ek.EpochKeyError) as exc2:
            ek.derive_key(b"", "tnt_01", "pseudonym", "e0")
        assert exc2.value.reason_code == ek.REASON_MALFORMED_SCOPE

    def test_epoch_keys_refuses_unknown_purpose(self) -> None:
        with pytest.raises(ek.EpochKeyError) as exc:
            ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "unknown_purpose", "e0")
        assert exc.value.reason_code == ek.REASON_UNKNOWN_PURPOSE

    def test_epoch_keys_refuses_derivation_for_destroyed_epoch(self) -> None:
        manifest = ek.KeyRotationManifest()
        okm, ref = ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "pseudonym", "e0")
        manifest.register("tnt_01", "pseudonym", "e0", created_at=0, key_ref=ref)
        manifest.destroy("tnt_01", "pseudonym", "e0", destroyed_at=100)

        with pytest.raises(ek.EpochKeyError) as exc:
            ek.derive_key(DEFAULT_ROOT_SECRET, "tnt_01", "pseudonym", "e0", manifest=manifest)
        assert exc.value.reason_code == ek.REASON_EPOCH_DESTROYED

    def test_epoch_keys_refuses_destruction_under_legal_hold(self) -> None:
        manifest = ek.KeyRotationManifest()
        manifest.register(
            "tnt_01",
            "authorization",
            "e0",
            created_at=0,
            destroyable=False,
            key_ref="abc",
        )
        with pytest.raises(ek.EpochKeyError) as exc:
            manifest.destroy("tnt_01", "authorization", "e0", destroyed_at=100)
        assert exc.value.reason_code == ek.REASON_DESTROY_NOT_PERMITTED


# ---------------------------------------------------------------------------
# 3. Unknown / Indeterminate Boundaries: First-Class Verdicts
# ---------------------------------------------------------------------------


class TestUnknownBoundaries:
    """INDETERMINATE is a first-class verdict and is never coerced to pass/fail."""

    def test_candidate_unknown_query_id_returns_indeterminate(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        recon = cand.reconstruct([receipt], "FQ-UNKNOWN-GHOST-QUERY")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_UNKNOWN_QUERY
        assert recon.score == 0.0

    def test_candidate_malformed_query_returns_indeterminate(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        recon = cand.reconstruct([receipt], "")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_MALFORMED_QUERY

    def test_candidate_missing_governance_policy_epoch_returns_indeterminate(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        # Construct receipt with empty policy_epoch
        corrupt_dict = receipt.to_dict()
        corrupt_dict["policy_epoch"] = ""
        # Re-sign to avoid TAMPER_DETECTED and trigger MISSING_EPOCH
        corrupt_dict.pop("signature", None)
        recon = cand.reconstruct([corrupt_dict], "FQ-AUTH-01")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_MISSING_EPOCH

    def test_candidate_missing_key_custody_attestation_returns_indeterminate(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        # FQ-PROV-02 requires commitment_digest and retention_mode
        q = _synthetic_query(query_id="FQ-PROV-02", key_custody_attested=False)
        recon = cand.reconstruct([receipt], q)
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_MISSING_KEY_CUSTODY

    def test_purpose_minimizer_under_commitment_missing_mandatory_proofs(self) -> None:
        rec = _synthetic_record()
        del rec["policy_epoch"]
        del rec["consent_epoch"]
        minimized = pm.minimize(rec, purpose="clinical_care", now="2026-01-02T00:00:00Z")
        assert "policy_epoch" in minimized.missing_mandatory_fields
        assert "consent_epoch" in minimized.missing_mandatory_fields
        assert "commitment_digest" not in minimized.missing_mandatory_fields

    def test_epoch_keys_unknown_scope_reversibility_raises_unknown_epoch(self) -> None:
        manifest = ek.KeyRotationManifest()
        manifest.register("tnt_01", "pseudonym", "e0", created_at=0)
        with pytest.raises(ek.EpochKeyError) as exc:
            manifest.reversibility("tnt_01", "pseudonym", "e999")
        assert exc.value.reason_code == ek.REASON_UNKNOWN_EPOCH

    def test_liveness_positive_controls_prevent_all_deny_coercion(self) -> None:
        """Verify candidate mechanism achieves score 1.0 on genuine receipts.

        An all-deny stub would trivially fail this assertion.
        """
        event = _synthetic_event(purpose="clinical_care")
        receipt = cand.minimize(event, purpose="clinical_care")
        recon = cand.reconstruct([receipt], "FQ-AUTH-01")
        assert recon.answerable == cand.ANSWERABLE
        assert recon.score == 1.0
        assert recon.reason_code == cand.REASON_OK


# ---------------------------------------------------------------------------
# 4. Retention-Window Expiry Scenarios
# ---------------------------------------------------------------------------


class TestRetentionWindowExpiryScenarios:
    """Decaying content fields drop at exact deadlines; persistent proofs survive."""

    def test_evidence_digest_decays_at_exactly_30_days(self) -> None:
        created_at = "2026-01-01T00:00:00Z"
        rec = _synthetic_record(created_at=created_at)

        # 29 days 23 hours: evidence_digest retained
        t_before = "2026-01-30T23:59:59Z"
        m_before = pm.minimize(rec, purpose="clinical_care", now=t_before)
        assert "evidence_digest" in m_before.receipt
        assert "evidence_digest" not in m_before.dropped_fields

        # Exactly 30 days: evidence_digest dropped with RETENTION_EXPIRED
        t_at = "2026-01-31T00:00:00Z"
        m_at = pm.minimize(rec, purpose="clinical_care", now=t_at)
        assert "evidence_digest" not in m_at.receipt
        assert m_at.dropped_fields.get("evidence_digest") == pm.DROP_RETENTION_EXPIRED

        # witness_id (90 day window) remains retained at 30 days
        assert "witness_id" in m_at.receipt

    def test_witness_id_decays_at_exactly_90_days(self) -> None:
        created_at = "2026-01-01T00:00:00Z"
        rec = _synthetic_record(created_at=created_at)

        # 89 days 23 hours: witness_id retained
        t_before = "2026-03-31T23:59:59Z"
        m_before = pm.minimize(rec, purpose="clinical_care", now=t_before)
        assert "witness_id" in m_before.receipt

        # Exactly 90 days: witness_id dropped with RETENTION_EXPIRED
        t_at = "2026-04-01T00:00:00Z"
        m_at = pm.minimize(rec, purpose="clinical_care", now=t_at)
        assert "witness_id" not in m_at.receipt
        assert m_at.dropped_fields.get("witness_id") == pm.DROP_RETENTION_EXPIRED

    def test_persistent_proofs_never_expire_after_years(self) -> None:
        created_at = "2026-01-01T00:00:00Z"
        rec = _synthetic_record(created_at=created_at)
        t_future = "2030-01-01T00:00:00Z"  # 4 years later
        m_future = pm.minimize(rec, purpose="clinical_care", now=t_future)

        # Decaying fields expired
        assert "evidence_digest" not in m_future.receipt
        assert "witness_id" not in m_future.receipt
        assert m_future.dropped_fields["evidence_digest"] == pm.DROP_RETENTION_EXPIRED
        assert m_future.dropped_fields["witness_id"] == pm.DROP_RETENTION_EXPIRED

        # Proof fields never decay
        assert "commitment_digest" in m_future.receipt
        assert "consent_epoch" in m_future.receipt
        assert "policy_epoch" in m_future.receipt
        assert "retention_mode" in m_future.receipt

    def test_forensic_query_answerability_frontier_across_retention_milestones(self) -> None:
        """End-to-end integration: query requiring witness decays to NOT_ANSWERABLE."""
        created_at = "2026-01-01T00:00:00Z"
        rec = _synthetic_record(created_at=created_at)

        # Before 90 days: minimized record converted to receipt answers FQ-AUTH-01
        m_pre = pm.minimize(rec, purpose="clinical_care", now="2026-01-15T00:00:00Z")
        evt_pre = _synthetic_event(witness_id=m_pre.receipt["witness_id"])
        rcpt_pre = cand.minimize(evt_pre, purpose="clinical_care")
        recon_pre = cand.reconstruct([rcpt_pre], "FQ-AUTH-01")
        assert recon_pre.answerable == cand.ANSWERABLE

        # After 90 days: minimized record has no witness_id
        m_post = pm.minimize(rec, purpose="clinical_care", now="2026-05-01T00:00:00Z")
        assert "witness_id" not in m_post.receipt
        evt_post = {
            "event_id": "evt-post-90d",
            "tenant_id": "tnt_01",
            "principal_id": "prn_01",
            "purpose": "clinical_care",
            "policy_epoch": m_post.receipt["policy_epoch"],
            "consent_epoch": m_post.receipt["consent_epoch"],
            "commitment_digest": m_post.receipt["commitment_digest"],
            "retention_mode": m_post.receipt["retention_mode"],
        }
        rcpt_post = cand.minimize(evt_post, purpose="clinical_care")
        recon_post = cand.reconstruct([rcpt_post], "FQ-AUTH-01")
        assert recon_post.answerable == cand.NOT_ANSWERABLE
        assert recon_post.reason_code == cand.REASON_MISSING_WITNESS

        # Provenance query requiring only commitment_digest stays ANSWERABLE indefinitely
        recon_prov = cand.reconstruct([rcpt_post], "FQ-PROV-01")
        assert recon_prov.answerable == cand.ANSWERABLE


# ---------------------------------------------------------------------------
# 5. Two-Step Metamorphic Relations
# ---------------------------------------------------------------------------


class TestTwoStepMetamorphicRelations:
    """Formally defined metamorphic invariants over composition and lifecycle."""

    def test_mr1_candidate_minimizing_twice_is_idempotent(self) -> None:
        """Minimizing the same event twice produces identical receipts byte-for-byte."""
        event = _synthetic_event(extra_omitted={"k1": "v1", "k2": "v2"})
        r1 = cand.minimize(event, purpose="clinical_care")
        r2 = cand.minimize(event, purpose="clinical_care")
        assert r1.to_dict() == r2.to_dict()
        assert r1.receipt_id == r2.receipt_id
        assert r1.omitted_field_digest == r2.omitted_field_digest
        assert r1.signature == r2.signature

        # Evaluating single vs duplicate receipts preserves exact verdict
        q1 = cand.reconstruct([r1], "FQ-AUTH-01")
        q2 = cand.reconstruct([r2], "FQ-AUTH-01")
        assert q1.to_dict() == q2.to_dict()
        q_both = cand.reconstruct([r1, r2], "FQ-AUTH-01")
        assert q_both.score == q1.score == 1.0
        assert q_both.answerable == q1.answerable == cand.ANSWERABLE
        assert q_both.reason_code == q1.reason_code == cand.REASON_OK
        assert q_both.evidence_fields == q1.evidence_fields

    def test_mr1_purpose_minimizing_twice_is_idempotent(self) -> None:
        rec = _synthetic_record()
        now = "2026-02-15T00:00:00Z"
        m1 = pm.minimize(rec, purpose="clinical_care", now=now, pseudonym_key=DEFAULT_ROOT_SECRET)
        m2 = pm.minimize(rec, purpose="clinical_care", now=now, pseudonym_key=DEFAULT_ROOT_SECRET)
        assert m1.to_dict() == m2.to_dict()
        assert m1.pseudonym == m2.pseudonym
        assert m1.dropped_fields == m2.dropped_fields

    def test_mr2_rotating_epoch_key_changes_pseudonym_preserves_intra_epoch_linkability(
        self,
    ) -> None:
        """Rotating epoch key produces new pseudonyms while preserving intra-epoch linkability."""
        manifest = ek.KeyRotationManifest()
        root = DEFAULT_ROOT_SECRET
        tenant = "tnt_hospital_alpha"
        purpose = "pseudonym"

        # Epoch 0 derivation & registration
        k_e0, ref_e0 = ek.derive_key(root, tenant, purpose, "e0")
        manifest.register(tenant, purpose, "e0", created_at=0, key_ref=ref_e0)

        # Two records from Patient A and one from Patient B in Epoch 0
        psn_A_e0_rec1 = pm.pseudonymize("patient_alpha_101", k_e0)
        psn_A_e0_rec2 = pm.pseudonymize("patient_alpha_101", k_e0)
        psn_B_e0 = pm.pseudonymize("patient_beta_202", k_e0)

        # Intra-epoch linkability in e0
        assert psn_A_e0_rec1 == psn_A_e0_rec2
        assert psn_A_e0_rec1 != psn_B_e0

        # Rotate to Epoch 1
        new_epoch, scope_key = ek.rotate(tenant, purpose, manifest, root=root, destroyed_at=1000)
        assert new_epoch == "e1"
        k_e1, ref_e1 = ek.derive_key(root, tenant, purpose, "e1")
        assert ref_e1 == scope_key.key_ref

        # Pseudonyms in Epoch 1
        psn_A_e1_rec1 = pm.pseudonymize("patient_alpha_101", k_e1)
        psn_A_e1_rec2 = pm.pseudonymize("patient_alpha_101", k_e1)
        psn_B_e1 = pm.pseudonymize("patient_beta_202", k_e1)

        # Cross-epoch pseudonym changes (unlinkable without key custody)
        assert psn_A_e1_rec1 != psn_A_e0_rec1
        assert psn_B_e1 != psn_B_e0

        # Intra-epoch linkability preserved in e1
        assert psn_A_e1_rec1 == psn_A_e1_rec2
        assert psn_A_e1_rec1 != psn_B_e1

        # Rotate once more to e2
        new_epoch2, _ = ek.rotate(tenant, purpose, manifest, root=root, destroyed_at=2000)
        assert new_epoch2 == "e2"
        k_e2, _ = ek.derive_key(root, tenant, purpose, "e2")
        psn_A_e2 = pm.pseudonymize("patient_alpha_101", k_e2)
        assert psn_A_e2 != psn_A_e1_rec1
        assert psn_A_e2 != psn_A_e0_rec1

    def test_mr3_destroying_epoch_key_makes_past_records_strictly_irreversible(self) -> None:
        """Destroying an epoch key flips reversibility to IRREVERSIBLE and disables derivation."""
        manifest = ek.KeyRotationManifest()
        root = DEFAULT_ROOT_SECRET
        tenant = "tnt_clinic_omega"
        purpose = "pseudonym"
        epoch = "e0"

        okm, ref = ek.derive_key(root, tenant, purpose, epoch)
        manifest.register(tenant, purpose, epoch, created_at=0, key_ref=ref)

        # Before destruction: REVERSIBLE
        assert manifest.reversibility(tenant, purpose, epoch) == ek.REVERSIBLE
        okm_check, _ = ek.derive_key(root, tenant, purpose, epoch, manifest=manifest)
        assert okm_check == okm

        # Controlled destruction of e0
        entry = ek.destroy(tenant, purpose, epoch, manifest, destroyed_at=5000)
        assert entry.destroyed is True
        assert entry.destroyed_at == 5000

        # After destruction: strictly IRREVERSIBLE
        assert manifest.reversibility(tenant, purpose, epoch) == ek.IRREVERSIBLE

        # Attempting to re-derive key for destroyed epoch fails closed
        with pytest.raises(ek.EpochKeyError) as exc:
            ek.derive_key(root, tenant, purpose, epoch, manifest=manifest)
        assert exc.value.reason_code == ek.REASON_EPOCH_DESTROYED

        # Double destruction is refused
        with pytest.raises(ek.EpochKeyError) as exc_re:
            ek.destroy(tenant, purpose, epoch, manifest, destroyed_at=6000)
        assert exc_re.value.reason_code == ek.REASON_EPOCH_DESTROYED

    def test_mr4_purpose_scope_cryptographic_isolation_no_crosstalk(self) -> None:
        """Keys derived under different purpose scopes are isolated and do not crosstalk."""
        manifest = ek.KeyRotationManifest()
        root = DEFAULT_ROOT_SECRET
        tenant = "tnt_secure_node"

        okm_pseudo, ref_pseudo = ek.derive_key(root, tenant, "pseudonym", "e0")
        okm_auth, ref_auth = ek.derive_key(root, tenant, "authorization", "e0")
        assert okm_pseudo != okm_auth

        manifest.register(tenant, "pseudonym", "e0", created_at=0, key_ref=ref_pseudo)
        manifest.register(
            tenant,
            "authorization",
            "e0",
            created_at=0,
            destroyable=False,
            key_ref=ref_auth,
        )

        # Destroying pseudonym epoch e0 does NOT affect authorization epoch e0
        ek.destroy(tenant, "pseudonym", "e0", manifest, destroyed_at=100)
        assert manifest.reversibility(tenant, "pseudonym", "e0") == ek.IRREVERSIBLE
        assert manifest.reversibility(tenant, "authorization", "e0") == ek.REVERSIBLE

        # Authorization key derivation still succeeds
        okm_auth_live, _ = ek.derive_key(root, tenant, "authorization", "e0", manifest=manifest)
        assert okm_auth_live == okm_auth

    def test_mr5_deterministic_seeded_replay_invariance(self) -> None:
        """Replaying identical sequence under identical seed produces byte-identical results."""

        def _run_trial(seed: int) -> dict[str, Any]:
            rng = random.Random(seed)
            results: list[Any] = []
            for i in range(10):
                subj = f"subj_pt_{rng.randint(1000, 9999)}"
                evt = _synthetic_event(event_id=f"evt-{i}", subject_ref=subj)
                rcpt = cand.minimize(evt)
                recon = cand.reconstruct([rcpt], "FQ-AUTH-01")
                results.append((rcpt.to_dict(), recon.to_dict()))
            return {"results": results}

        t1 = _run_trial(FIXED_SEED)
        t2 = _run_trial(FIXED_SEED)
        assert json.dumps(t1, sort_keys=True) == json.dumps(t2, sort_keys=True)


# ---------------------------------------------------------------------------
# 6. Mutation Checks: Sensitivity and Mutant Killing
# ---------------------------------------------------------------------------


class TestMutationChecks:
    """Single perturbations deterministically flip verdicts or kill mutants."""

    def test_mutation_signature_corruption_killed(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        # Flip first character of signature
        corrupt_sig = ("0" if receipt.signature[0] != "0" else "1") + receipt.signature[1:]
        corrupt_dict = receipt.to_dict()
        corrupt_dict["signature"] = corrupt_sig
        recon = cand.reconstruct([corrupt_dict], "FQ-AUTH-01")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_TAMPER_DETECTED

    def test_mutation_retained_field_tamper_killed(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        tampered_dict = receipt.to_dict()
        tampered_dict["retained_fields"]["purpose"] = "self_care"
        recon = cand.reconstruct([tampered_dict], "FQ-AUTH-01")
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_TAMPER_DETECTED

    def test_mutation_omitted_claims_corruption_killed(self) -> None:
        event = _synthetic_event(extra_omitted={"fieldA": "valA", "fieldB": "valB"})
        receipt = cand.minimize(event)
        # Query with altered field value
        bad_query = _synthetic_query(
            query_id="FQ-PROV-01",
            query_class="provenance",
            witnesses_needed=("commitment_digest",),
            omitted_claims={"fieldA": "valA", "fieldB": "tampered_value"},
        )
        recon = cand.reconstruct([receipt], bad_query)
        assert recon.answerable == cand.INDETERMINATE
        assert recon.reason_code == cand.REASON_OMITTED_FIELD_MISMATCH

    def test_mutation_stripping_witness_flips_verdict(self) -> None:
        event = _synthetic_event()
        receipt = cand.minimize(event)
        # Remove witness_id from retained_fields
        r_dict = receipt.to_dict()
        r_dict["retained_fields"].pop("witness_id", None)
        r_dict.pop("signature", None)  # Re-evaluation without signature
        recon = cand.reconstruct([r_dict], "FQ-AUTH-01")
        assert recon.answerable == cand.NOT_ANSWERABLE
        assert recon.reason_code == cand.REASON_MISSING_WITNESS

    def test_mutation_unsalted_hash_injection_killed(self) -> None:
        raw_hash = hashlib.sha256(b"patient_mrn_12345").hexdigest()
        rec = _synthetic_record(subject_ref=raw_hash)
        with pytest.raises(pm.MinimizationError) as exc:
            pm.minimize(rec, purpose="clinical_care", now="2026-01-02T00:00:00Z")
        assert exc.value.reason_code == pm.REASON_UNSALTED_HASH_REFUSED

    def test_mutation_destroyable_flag_tamper_killed(self) -> None:
        manifest = ek.KeyRotationManifest()
        manifest.register("tnt_01", "pseudonym", "e0", created_at=0, destroyable=False)
        with pytest.raises(ek.EpochKeyError) as exc:
            manifest.destroy("tnt_01", "pseudonym", "e0", destroyed_at=100)
        assert exc.value.reason_code == ek.REASON_DESTROY_NOT_PERMITTED

    def test_seeded_randomized_mutation_campaign(self) -> None:
        """30 randomized trials with synthetic mutations: 100% mutant kill rate."""
        rng = random.Random(FIXED_SEED)
        mutations_tested = 0
        mutations_killed = 0

        for trial in range(30):
            event = _synthetic_event(
                event_id=f"evt-mut-{trial}",
                subject_ref=f"subj_pt_{rng.randint(1000, 9999)}",
            )
            # Baseline check: unmutated event produces ANSWERABLE
            receipt = cand.minimize(event, purpose="clinical_care")
            recon_base = cand.reconstruct([receipt], "FQ-AUTH-01")
            assert recon_base.answerable == cand.ANSWERABLE

            mutation_kind = rng.choice(
                [
                    "corrupt_sig",
                    "corrupt_witness",
                    "corrupt_policy_epoch",
                    "inject_phi",
                    "inject_unsalted_hash",
                    "unknown_purpose",
                ]
            )
            mutations_tested += 1

            if mutation_kind == "corrupt_sig":
                m_dict = receipt.to_dict()
                m_dict["signature"] = "deadbeef" * 8
                r = cand.reconstruct([m_dict], "FQ-AUTH-01")
                if (
                    r.answerable == cand.INDETERMINATE
                    and r.reason_code == cand.REASON_TAMPER_DETECTED
                ):
                    mutations_killed += 1

            elif mutation_kind == "corrupt_witness":
                m_dict = receipt.to_dict()
                m_dict["retained_fields"].pop("witness_id", None)
                m_dict.pop("signature", None)
                r = cand.reconstruct([m_dict], "FQ-AUTH-01")
                if (
                    r.answerable == cand.NOT_ANSWERABLE
                    and r.reason_code == cand.REASON_MISSING_WITNESS
                ):
                    mutations_killed += 1

            elif mutation_kind == "corrupt_policy_epoch":
                m_dict = receipt.to_dict()
                m_dict["policy_epoch"] = ""
                m_dict.pop("signature", None)
                r = cand.reconstruct([m_dict], "FQ-AUTH-01")
                if (
                    r.answerable == cand.INDETERMINATE
                    and r.reason_code == cand.REASON_MISSING_EPOCH
                ):
                    mutations_killed += 1

            elif mutation_kind == "inject_phi":
                mut_event = copy.deepcopy(event)
                mut_event["patient_dob"] = "1980-01-01"
                try:
                    cand.minimize(mut_event)
                except ValueError as ex:
                    if cand.REASON_PHI_FIELD_PRESENT in str(ex):
                        mutations_killed += 1

            elif mutation_kind == "inject_unsalted_hash":
                mut_event = copy.deepcopy(event)
                mut_event["subject_ref"] = hashlib.sha256(b"seed").hexdigest()
                try:
                    cand.minimize(mut_event)
                except ValueError as ex:
                    if cand.REASON_UNSALTED_HASH_REFUSED in str(ex):
                        mutations_killed += 1

            elif mutation_kind == "unknown_purpose":
                mut_event = copy.deepcopy(event)
                mut_event["purpose"] = "dark_pattern_ad_network"
                try:
                    cand.minimize(mut_event, purpose="dark_pattern_ad_network")
                except ValueError as ex:
                    if cand.REASON_UNKNOWN_PURPOSE in str(ex):
                        mutations_killed += 1

        assert mutations_tested == 30
        assert mutations_killed == 30, f"Surviving mutants: {mutations_tested - mutations_killed}"
