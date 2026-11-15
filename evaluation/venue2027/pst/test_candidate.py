"""Unit tests for the PST venue candidate algorithm (task PST-candidate, phase P04).

Deliverables tested:
- evaluation/venue2027/pst/candidate.py: isolated ReceiptMin mechanism.
- Positive controls: minimal receipts reconstruct primary forensic queries.
- Fewer bytes retained than full retention.
- Fail-closed behavior: unknown or malformed query -> INDETERMINATE.
- Independence assertion: candidate module does NOT import the independent oracle or labels.
- Determinism and JSON serializability.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from evaluation.venue2027.pst import candidate as cand

# --- Fixtures ----------------------------------------------------------------


def _sample_full_event() -> dict[str, str]:
    """A realistic full raw event before minimization."""
    return {
        "event_id": "evt-20261116-001",
        "operation_id": "op-9901",
        "tenant_id": "tnt_0a1b2c3d",
        "principal_id": "prn_9f8e7d6c",
        "purpose": "clinical_care",
        "operation": "record_read",
        "policy_epoch": "epoch-4",
        "consent_epoch": "epoch-consent-2",
        "witness_id": "wit_witness123",
        "retention_mode": "selective",
        "commitment_digest": "a" * 64,
        "payload_digest": "b" * 64,
        "subject_ref": "subj_synthetic_patient_001",
        "created_at": "2026-11-16T10:00:00Z",
    }


def _sample_query_auth() -> dict[str, object]:
    return {
        "query_id": "FQ-AUTH-01",
        "query_class": "authorization",
        "witnesses_needed": ["purpose_tag", "witness_id"],
    }


def _sample_query_prov() -> dict[str, object]:
    return {
        "query_id": "FQ-PROV-01",
        "query_class": "provenance",
        "witnesses_needed": ["commitment_digest"],
    }


def _sample_query_elig() -> dict[str, object]:
    return {
        "query_id": "FQ-ELIG-01",
        "query_class": "commit_eligibility",
        "witnesses_needed": ["purpose_tag", "consent_epoch"],
    }


# --- Positive Controls: Forensic Reconstruction ------------------------------


def test_reconstruct_primary_forensic_queries() -> None:
    event = _sample_full_event()
    receipt = cand.minimize(event, purpose="clinical_care")

    # FQ-AUTH-01: authorization with purpose_tag and witness_id
    res_auth = cand.reconstruct([receipt], _sample_query_auth())
    assert res_auth.answerable == cand.ANSWERABLE
    assert res_auth.score == 1.0
    assert res_auth.reason_code == cand.REASON_OK
    assert "witness_id" in res_auth.evidence_fields

    # FQ-PROV-01: provenance with commitment_digest
    res_prov = cand.reconstruct([receipt], _sample_query_prov())
    assert res_prov.answerable == cand.ANSWERABLE
    assert res_prov.score == 1.0

    # FQ-ELIG-01: commit eligibility with consent_epoch
    res_elig = cand.reconstruct([receipt], _sample_query_elig())
    assert res_elig.answerable == cand.ANSWERABLE
    assert res_elig.score == 1.0


def test_reconstruct_by_frozen_query_id_string() -> None:
    event = _sample_full_event()
    receipt = cand.minimize(event, purpose="clinical_care")

    res = cand.reconstruct([receipt], "FQ-AUTH-02")
    assert res.answerable == cand.ANSWERABLE
    assert res.score == 1.0


def test_omitted_field_digest_verification() -> None:
    event = _sample_full_event()
    receipt = cand.minimize(event, purpose="self_care")

    # In self_care, payload_digest and witness_id are omitted and bound in omitted_field_digest
    assert "witness_id" not in receipt.retained_fields
    assert receipt.omitted_field_digest

    # In self_care, payload_digest, subject_ref, witness_id, and retention_mode are omitted
    omitted_claims = {
        "payload_digest": event["payload_digest"],
        "subject_ref": event["subject_ref"],
        "witness_id": event["witness_id"],
        "retention_mode": event["retention_mode"],
    }
    query = {
        "query_id": "FQ-PROV-01",
        "query_class": "provenance",
        "witnesses_needed": ["commitment_digest"],
        "omitted_claims": omitted_claims,
    }
    res_valid = cand.reconstruct([receipt], query)
    assert res_valid.answerable == cand.ANSWERABLE

    # False claim -> fails closed with OMITTED_FIELD_MISMATCH -> INDETERMINATE
    bad_claims = dict(omitted_claims)
    bad_claims["witness_id"] = "tampered_witness"
    query_bad = {
        "query_id": "FQ-PROV-01",
        "query_class": "provenance",
        "witnesses_needed": ["commitment_digest"],
        "omitted_claims": bad_claims,
    }
    res_bad = cand.reconstruct([receipt], query_bad)
    assert res_bad.answerable == cand.INDETERMINATE
    assert res_bad.reason_code == cand.REASON_OMITTED_FIELD_MISMATCH


# --- Byte Reduction vs Full Raw Event ----------------------------------------


def test_fewer_bytes_than_full_retention() -> None:
    # Full event with longitudinal metadata
    full_event = _sample_full_event()
    full_event["diagnostic_context"] = "patient_reported_acute_headache_and_visual_blurring" * 10
    full_event["internal_trace"] = json.dumps([{"stack": ["layer1", "layer2", "layer3"]}] * 5)
    full_event["clinical_notes"] = "Observations indicate potential migraine with aura." * 5

    full_bytes = len(json.dumps(full_event, sort_keys=True).encode("utf-8"))

    receipt = cand.minimize(full_event, purpose="clinical_care")
    receipt_bytes = len(json.dumps(receipt.to_dict(), sort_keys=True).encode("utf-8"))

    # Minimal receipt strips free-text / clinical context, keeping only bounded tokens and digest
    assert receipt_bytes < full_bytes
    reduction_pct = (full_bytes - receipt_bytes) / full_bytes * 100
    assert reduction_pct > 30.0, f"Expected >30% byte reduction, got {reduction_pct:.1f}%"


# --- Fail-Closed Controls (INDETERMINATE / NOT_ANSWERABLE) -------------------


def test_unknown_query_fails_closed_to_indeterminate() -> None:
    event = _sample_full_event()
    receipt = cand.minimize(event, purpose="clinical_care")

    # Unknown query ID string
    res1 = cand.reconstruct([receipt], "FQ-UNKNOWN-999")
    assert res1.answerable == cand.INDETERMINATE
    assert res1.reason_code == cand.REASON_UNKNOWN_QUERY

    # Unknown query class in dict
    res2 = cand.reconstruct([receipt], {"query_id": "Q-X", "query_class": "unsupported_class"})
    assert res2.answerable == cand.INDETERMINATE
    assert res2.reason_code == cand.REASON_UNKNOWN_QUERY

    # Malformed query
    res3 = cand.reconstruct([receipt], 12345)  # type: ignore[arg-type]
    assert res3.answerable == cand.INDETERMINATE
    assert res3.reason_code == cand.REASON_MALFORMED_QUERY


def test_missing_witness_returns_not_answerable() -> None:
    event = _sample_full_event()
    # self_care purpose drops witness_id
    receipt = cand.minimize(event, purpose="self_care")
    assert "witness_id" not in receipt.retained_fields

    # FQ-AUTH-01 requires witness_id -> NOT_ANSWERABLE
    res = cand.reconstruct([receipt], _sample_query_auth())
    assert res.answerable == cand.NOT_ANSWERABLE
    assert res.score == 0.0
    assert res.reason_code == cand.REASON_MISSING_WITNESS
    assert "witness_id" in res.details.get("missing_witnesses", [])


def test_tampered_receipt_fails_closed_to_indeterminate() -> None:
    event = _sample_full_event()
    receipt = cand.minimize(event, purpose="clinical_care")

    # Tamper with policy epoch
    tampered_dict = receipt.to_dict()
    tampered_dict["policy_epoch"] = "epoch-999_tampered"
    tampered_receipt = cand.Receipt.from_dict(tampered_dict)

    res = cand.reconstruct([tampered_receipt], _sample_query_prov())
    assert res.answerable == cand.INDETERMINATE
    assert res.reason_code == cand.REASON_TAMPER_DETECTED


def test_missing_key_custody_fails_closed_to_indeterminate() -> None:
    event = _sample_full_event()
    receipt = cand.minimize(event, purpose="clinical_care")

    query = {
        "query_id": "FQ-PROV-04",
        "query_class": "provenance",
        "witnesses_needed": ["commitment_digest", "witness_id"],
        "key_custody_attested": False,
    }
    res = cand.reconstruct([receipt], query)
    assert res.answerable == cand.INDETERMINATE
    assert res.reason_code == cand.REASON_MISSING_KEY_CUSTODY


def test_phi_field_in_event_is_refused() -> None:
    event = _sample_full_event()
    event["patient_name"] = "Alice"
    with pytest.raises(ValueError, match="PHI_FIELD_PRESENT"):
        cand.minimize(event, purpose="clinical_care")


def test_unsalted_hash_subject_is_refused() -> None:
    event = _sample_full_event()
    event["subject_ref"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    with pytest.raises(ValueError, match="UNSALTED_HASH_REFUSED"):
        cand.minimize(event, purpose="clinical_care")


# --- Harness Adapter (run_candidate) Controls --------------------------------


def test_run_candidate_adapter_positive() -> None:
    case = {
        "case_id": "PST-CASE-01",
        "purpose": "clinical_care",
        "events": [_sample_full_event()],
        "query": _sample_query_prov(),
    }
    outcome = cand.run_candidate(case, {"arm_id": "B4"})
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True


def test_run_candidate_adapter_reject() -> None:
    case = {
        "case_id": "PST-CASE-05",
        "purpose": "self_care",  # drops witness_id
        "events": [_sample_full_event()],
        "query": _sample_query_auth(),  # needs witness_id
    }
    outcome = cand.run_candidate(case, {"arm_id": "B4"})
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is True


def test_run_candidate_adapter_indeterminate() -> None:
    case = {
        "case_id": "PST-CASE-07",
        "purpose": "clinical_care",
        "events": [_sample_full_event()],
        "query": "FQ-UNKNOWN-1234",
    }
    outcome = cand.run_candidate(case, {"arm_id": "B4"})
    assert outcome.observed_outcome == cand.INDETERMINATE
    assert outcome.counted_as_success is False


def test_run_candidate_adapter_unknown_arm() -> None:
    case = {"case_id": "PST-CASE-01", "events": [_sample_full_event()]}
    outcome = cand.run_candidate(case, {"arm_id": "UNREGISTERED_ARM"})
    assert outcome.observed_outcome == "INVALID_RESULT"


# --- Determinism and Serialization -------------------------------------------


def test_minimize_and_reconstruct_are_deterministic() -> None:
    event = _sample_full_event()
    r1 = cand.minimize(event, purpose="clinical_care")
    r2 = cand.minimize(event, purpose="clinical_care")

    assert r1.to_dict() == r2.to_dict()
    assert r1.signature == r2.signature

    res1 = cand.reconstruct([r1], _sample_query_prov())
    res2 = cand.reconstruct([r2], _sample_query_prov())
    assert res1.to_dict() == res2.to_dict()


def test_describe_mechanism_metadata() -> None:
    desc = cand.describe_mechanism()
    assert desc["candidate_id"] == cand.CANDIDATE_ID
    assert desc["blueprint_arm"] == "B4"
    assert "purpose_bound_field_allowlist" in desc["features"]


# --- Independence Assertion --------------------------------------------------


FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "evaluation.venue2027.pst.independent_oracle",
        "evaluation.venue2027.pst.generate_dataset",
        "evaluation.venue2027._shared.oracle_kernel",
    }
)
FORBIDDEN_BASENAMES: frozenset[str] = frozenset(
    {"independent_oracle", "generate_dataset", "oracle_kernel"}
)


def _scan_imports(file_path: pathlib.Path) -> set[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_candidate_independence() -> None:
    """The candidate module must NOT import the independent oracle or label datasets."""
    candidate_path = pathlib.Path(cand.__file__).resolve()
    imported_modules = _scan_imports(candidate_path)

    for mod in imported_modules:
        parts = mod.split(".")
        assert mod not in FORBIDDEN_MODULES, f"Forbidden module imported: {mod}"
        assert not any(
            base in FORBIDDEN_BASENAMES for base in parts
        ), f"Forbidden base imported: {mod}"
