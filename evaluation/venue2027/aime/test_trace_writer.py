"""Tests for AIME-traces — Immutable trace and measurement capture (Phase P05, venue aime).

Validates:
- Exact target contract: write_trace(event) -> sha256.
- Monotonic event ID sequencing and resumption.
- Round-trip preservation of clinical outcomes, reasons, oracles, costs, and backends.
- Cryptographic hash chaining (prev_digest linking and deterministic entry digests).
- Sensitive content sanitization (patient identifiers, clinical PHI, credentials).
- Fail-closed adversarial controls:
  * Non-monotonic event IDs refused.
  * Unsanitized patient identifiers and PHI fields rejected.
  * Tamper detection across outcomes, reasons, oracles, payloads, and costs.
  * Broken hash chain and reordering detection.
  * Malformed, empty, and corrupted traces.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.venue2027.aime.trace_writer import (
    GENESIS_PREV_DIGEST,
    REASON_CHAIN_INTEGRITY_BROKEN,
    REASON_CORRUPTED_TRACE,
    REASON_EMPTY_TRACE,
    REASON_NON_MONOTONIC_EVENT_ID,
    REASON_TAMPER_DETECTED,
    REASON_UNSANITIZED_PHI_REJECTED,
    TraceRecord,
    TraceWriter,
    TraceWriterError,
    canonical_json,
    detect_phi,
    read_trace,
    sanitize_record,
    verify_trace,
    verify_trace_details,
    write_trace,
)


@pytest.fixture
def temp_trace_file(tmp_path: Path) -> Path:
    return tmp_path / "test_aime_trace.jsonl"


# ==============================================================================
# Positive Controls
# ==============================================================================


def test_write_trace_contract_returns_sha256(temp_trace_file: Path) -> None:
    """Exact target contract: write_trace(event) -> sha256 returns 64-char hex string."""
    event = {
        "raw_outcome": "ADMIT",
        "clinical_safety_reason": "RULE_STABLE_HISTORY",
        "oracle_decision": {"decision": "PASS", "expected_outcome": "ADMIT"},
        "actual_backend": "aime_clinical_workflow",
        "duration_seconds": 0.0015,
        "payload": {"case_id": "AIME-SYNTH-001", "action": "MAINTAIN_THERAPY"},
    }
    digest = write_trace(event, trace_path=temp_trace_file)

    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert temp_trace_file.is_file()
    assert verify_trace(temp_trace_file) is True


def test_monotonic_event_ids(temp_trace_file: Path) -> None:
    """Consecutive writes produce strictly increasing monotonic event_ids starting at 1."""
    writer = TraceWriter(temp_trace_file)
    digests = [
        writer.append(
            {
                "raw_outcome": "ADMIT",
                "clinical_safety_reason": "RULE_STABLE_HISTORY",
                "oracle_decision": {"decision": "PASS"},
            }
        ),
        writer.append(
            {
                "raw_outcome": "REJECT",
                "clinical_safety_reason": "RULE_CONSENT_CHANGE",
                "oracle_decision": {"decision": "FAIL"},
            }
        ),
        writer.append(
            {
                "raw_outcome": "INDETERMINATE",
                "clinical_safety_reason": "RULE_RECONCILIATION",
                "oracle_decision": {"decision": "PENDING_CLINICIAN_REVIEW"},
            }
        ),
    ]

    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]

    # Verify cryptographic digest chaining
    assert records[0]["digest_refs"]["prev_digest"] == GENESIS_PREV_DIGEST
    assert records[0]["digest_refs"]["entry_digest"] == digests[0]
    assert records[1]["digest_refs"]["prev_digest"] == digests[0]
    assert records[1]["digest_refs"]["entry_digest"] == digests[1]
    assert records[2]["digest_refs"]["prev_digest"] == digests[1]
    assert records[2]["digest_refs"]["entry_digest"] == digests[2]

    assert verify_trace(temp_trace_file) is True


def test_round_trip_preserves_all_clinical_fields(temp_trace_file: Path) -> None:
    """Round-trip trace output faithfully matches source events and preserves all fields."""
    event = TraceRecord(
        event_id=1,
        raw_outcome="REJECT",
        clinical_safety_reason="RULE_MEDICATION_WITHDRAWAL",
        oracle_decision={
            "decision": "FAIL",
            "expected_outcome": "REJECT",
            "reason_code": "RULE_MEDICATION_WITHDRAWAL",
        },
        actual_backend="clara_deepseek_clinical_v3",
        duration_seconds=0.0125,
        cpu_duration_seconds=0.0025,
        db_duration_seconds=0.0010,
        model_duration_seconds=0.0090,
        cpu_cost=0.00005,
        db_cost=0.00002,
        model_cost=0.00045,
        model_cost_usd=0.00045,
        signature_refs={"source_commit": "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614"},
        payload={"vignette_id": "V-042", "withdrawn_medication": "metformin"},
    )

    writer = TraceWriter(temp_trace_file)
    digest = writer.append(event)
    assert len(digest) == 64

    records = read_trace(temp_trace_file)
    assert len(records) == 1
    r = records[0]

    assert r["event_id"] == 1
    assert r["raw_outcome"] == "REJECT"
    assert r["clinical_safety_reason"] == "RULE_MEDICATION_WITHDRAWAL"
    assert r["reason_code"] == "RULE_MEDICATION_WITHDRAWAL"
    assert r["oracle_decision"]["decision"] == "FAIL"
    assert r["actual_backend"] == "clara_deepseek_clinical_v3"
    assert r["duration_seconds"] == 0.0125
    assert r["cpu_duration_seconds"] == 0.0025
    assert r["db_duration_seconds"] == 0.0010
    assert r["model_duration_seconds"] == 0.0090
    assert r["model_cost_usd"] == 0.00045
    assert r["signature_refs"]["source_commit"] == "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614"
    assert r["payload"]["vignette_id"] == "V-042"
    assert r["payload"]["withdrawn_medication"] == "metformin"

    assert verify_trace(temp_trace_file) is True


def test_harness_pair_result_compatibility(temp_trace_file: Path) -> None:
    """Directly accepts and records harness pair_result dictionaries."""
    harness_record = {
        "record_kind": "pair_result",
        "logical_op_id": "aime-study-2027:B4::AIME-SYNTH-0005",
        "campaign_id": "aime-study-2027",
        "arm_id": "B4-selective-refresh",
        "case_id": "AIME-SYNTH-0005",
        "seed": 2027,
        "source_commit": "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614",
        "outcome": {
            "observed_outcome": "REJECT",
            "counted_as_success": True,
            "retriable": False,
            "detail": "ALLERGEN_CONTRAINDICATION: amoxicillin allergy declared",
            "reason_code": "RULE_ALLERGY_UPDATE",
        },
        "oracle": {
            "decision": "PASS",
            "expected_outcome": "REJECT",
            "oracle_id": "aime-clinical-reference",
            "reason_code": "RULE_ALLERGY_UPDATE",
        },
        "duration_seconds": 0.00035,
        "pair_digest": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "actual_backend": "aime_clinical_workflow",
    }

    digest = write_trace(harness_record, trace_path=temp_trace_file)
    assert len(digest) == 64

    records = read_trace(temp_trace_file)
    assert len(records) == 1
    assert records[0]["raw_outcome"] == "REJECT"
    assert records[0]["clinical_safety_reason"] == "RULE_ALLERGY_UPDATE"
    assert records[0]["signature_refs"]["pair_digest"] == harness_record["pair_digest"]
    assert records[0]["signature_refs"]["source_commit"] == harness_record["source_commit"]
    assert verify_trace(temp_trace_file) is True


def test_trace_writer_resumption(temp_trace_file: Path) -> None:
    """Opening an existing trace file resumes the sequence and maintains unbroken chain."""
    writer1 = TraceWriter(temp_trace_file)
    d1 = writer1.append({"raw_outcome": "ADMIT", "clinical_safety_reason": "RULE_STABLE_HISTORY"})
    assert len(d1) == 64
    d2 = writer1.append({"raw_outcome": "REJECT", "clinical_safety_reason": "RULE_CONSENT_CHANGE"})

    # Initialize a new writer on the same file
    writer2 = TraceWriter(temp_trace_file)
    assert writer2._last_event_id == 2
    assert writer2._last_digest == d2

    d3 = writer2.append({"raw_outcome": "ADMIT", "clinical_safety_reason": "RULE_STABLE_HISTORY"})

    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]
    assert records[2]["digest_refs"]["prev_digest"] == d2
    assert records[2]["digest_refs"]["entry_digest"] == d3
    assert verify_trace(temp_trace_file) is True


def test_explicit_monotonic_event_id(temp_trace_file: Path) -> None:
    """Explicit monotonic event IDs are accepted if strictly greater than previous."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"event_id": 10, "raw_outcome": "ADMIT"})
    writer.append({"event_id": 25, "raw_outcome": "REJECT"})
    writer.append({"event_id": 100, "raw_outcome": "ADMIT"})

    records = read_trace(temp_trace_file)
    assert [r["event_id"] for r in records] == [10, 25, 100]
    assert verify_trace(temp_trace_file) is True


def test_sanitization_scrubs_patient_identifiers_and_credentials(
    temp_trace_file: Path,
) -> None:
    """Sanitization removes or redacts all patient identifiers and credentials."""
    raw_event = {
        "raw_outcome": "ADMIT",
        "clinical_safety_reason": "RULE_STABLE_HISTORY",
        "payload": {
            "patient_id": "PT-998822",
            "patient_name": "Nguyen Van A",
            "mrn": "MRN-123456",
            "ssn": "123-45-6789",
            "dob": "1980-01-01",
            "phone": "+84 912 345 678",
            "email": "patient@hospital.vn",
            "api_key": "sk-12345678901234567890",
            "notes": "Patient phone is 0912345678 and email is patient@hospital.vn",
        },
    }

    # Before sanitization, detect_phi flags multiple leaks
    leaks = detect_phi(raw_event)
    assert len(leaks) >= 5

    # Sanitize and write
    sanitized = sanitize_record(raw_event)
    assert detect_phi(sanitized) == []
    assert sanitized["payload"]["patient_id"].startswith("sub-")
    assert sanitized["payload"]["patient_name"] == "[REDACTED_PHI]"
    assert sanitized["payload"]["mrn"] == "[REDACTED_PHI]"
    assert sanitized["payload"]["ssn"] == "[REDACTED_PHI]"

    # Append with sanitize=True
    writer = TraceWriter(temp_trace_file)
    digest = writer.append(raw_event, sanitize=True)
    assert len(digest) == 64

    records = read_trace(temp_trace_file)
    assert len(records) == 1
    assert records[0]["payload"]["patient_id"].startswith("sub-")
    assert records[0]["payload"]["patient_name"] == "[REDACTED_PHI]"
    assert records[0]["payload"]["api_key"] == "[REDACTED_CREDENTIAL]"
    assert verify_trace(temp_trace_file) is True


def test_real_sample_trace_artifact_verifies() -> None:
    """The committed sample trace artifact exists, is non-empty, and verifies."""
    sample_path = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "venue2027"
        / "proof"
        / "artifacts"
        / "aime_trace_sample.jsonl"
    )
    assert sample_path.is_file(), f"Sample artifact not found at {sample_path}"
    records = read_trace(sample_path)
    assert len(records) == 30
    assert verify_trace(sample_path) is True


# ==============================================================================
# Adversarial Controls
# ==============================================================================


def test_non_monotonic_event_ids_refused_on_append(temp_trace_file: Path) -> None:
    """Non-monotonic event IDs (equal or decreasing) are refused with stable reason code."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"event_id": 5, "raw_outcome": "ADMIT"})

    # Equal event_id
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"event_id": 5, "raw_outcome": "REJECT"})
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID

    # Decreasing event_id
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"event_id": 4, "raw_outcome": "REJECT"})
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID

    # Non-integer event_id
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"event_id": "six", "raw_outcome": "REJECT"})
    assert exc_info.value.reason_code == "INVALID_RECORD"


@pytest.mark.parametrize(
    "phi_key,phi_value",
    [
        ("patient_name", "Tran Van B"),
        ("patient_id", "P-8844"),
        ("mrn", "MRN-998877"),
        ("medical_record_number", "MED-001"),
        ("ssn", "987-65-4321"),
        ("date_of_birth", "1995-12-31"),
        ("insurance_id", "INS-4455"),
        ("phone", "+1 555 123 4567"),
        ("email", "doctor@clinic.org"),
        ("api_key", "sk-live-0123456789abcdef"),
    ],
)
def test_unsanitized_phi_rejected_fail_closed(
    temp_trace_file: Path, phi_key: str, phi_value: str
) -> None:
    """Unsanitized PHI or credentials fail closed with UNSANITIZED_PHI_REJECTED."""
    writer = TraceWriter(temp_trace_file)
    event = {
        "raw_outcome": "ADMIT",
        "clinical_safety_reason": "RULE_STABLE_HISTORY",
        "payload": {phi_key: phi_value},
    }

    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(event, sanitize=False)
    assert exc_info.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED


def test_nested_phi_rejected(temp_trace_file: Path) -> None:
    """Deeply nested PHI markers are caught and rejected."""
    writer = TraceWriter(temp_trace_file)
    event = {
        "raw_outcome": "ADMIT",
        "payload": {
            "clinical_context": {
                "demographics": {
                    "nested_patient_identifier": "HIDDEN-PATIENT-ID",
                }
            }
        },
    }

    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(event, sanitize=False)
    assert exc_info.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED


def test_tamper_detection_outcome_modified(temp_trace_file: Path) -> None:
    """Modifying raw_outcome on disk is detected as TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"raw_outcome": "REJECT", "clinical_safety_reason": "RULE_CONSENT_CHANGE"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[0])
    data["raw_outcome"] = "ADMIT"  # Tamper REJECT -> ADMIT
    temp_trace_file.write_text(canonical_json(data) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_TAMPER_DETECTED in d for d in defects)


def test_tamper_detection_clinical_reason_modified(temp_trace_file: Path) -> None:
    """Modifying clinical_safety_reason on disk is detected as TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"raw_outcome": "REJECT", "clinical_safety_reason": "RULE_ALLERGY_UPDATE"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[0])
    data["clinical_safety_reason"] = "RULE_STABLE_HISTORY"
    temp_trace_file.write_text(canonical_json(data) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_TAMPER_DETECTED in d for d in defects)


def test_tamper_detection_oracle_modified(temp_trace_file: Path) -> None:
    """Modifying oracle_decision on disk is detected as TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {
            "raw_outcome": "REJECT",
            "oracle_decision": {"decision": "FAIL", "expected_outcome": "REJECT"},
        }
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[0])
    data["oracle_decision"]["decision"] = "PASS"  # Tamper oracle verdict
    temp_trace_file.write_text(canonical_json(data) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_TAMPER_DETECTED in d for d in defects)


def test_tamper_detection_payload_modified(temp_trace_file: Path) -> None:
    """Modifying payload content on disk is detected via payload_digest mismatch."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"raw_outcome": "ADMIT", "payload": {"dose_mg": 50}})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[0])
    data["payload"]["dose_mg"] = 500  # Tamper clinical dose
    temp_trace_file.write_text(canonical_json(data) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_TAMPER_DETECTED in d for d in defects)


def test_chain_integrity_broken_by_tampered_prev_digest(temp_trace_file: Path) -> None:
    """Tampering with prev_digest breaks chain integrity."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"raw_outcome": "ADMIT"})
    writer.append({"raw_outcome": "REJECT"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    entry2 = json.loads(lines[1])
    entry2["digest_refs"]["prev_digest"] = "f" * 64
    lines[1] = canonical_json(entry2)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_CHAIN_INTEGRITY_BROKEN in d for d in defects)


def test_reordering_or_swapping_entries_fails_verification(temp_trace_file: Path) -> None:
    """Swapping two entries in a trace fails monotonicity and chain verification."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"raw_outcome": "ADMIT"})
    writer.append({"raw_outcome": "REJECT"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    # Swap line 0 and line 1
    swapped = [lines[1], lines[0]]
    temp_trace_file.write_text("\n".join(swapped) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(
        REASON_NON_MONOTONIC_EVENT_ID in d or REASON_CHAIN_INTEGRITY_BROKEN in d for d in defects
    )


def test_injected_phi_line_fails_trace_verification(temp_trace_file: Path) -> None:
    """A trace containing an unredacted patient identifier fails verify_trace."""
    writer = TraceWriter(temp_trace_file)
    writer.append({"raw_outcome": "ADMIT"})

    # Manually append an entry that contains PHI
    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    entry1 = json.loads(lines[0])
    entry2 = dict(entry1)
    entry2["event_id"] = 2
    entry2["payload"] = {"patient_name": "Le Thi C"}
    # Note: even if entry2 has matching hashes, the PHI check must fail verification!
    payload_dig = "0" * 64
    entry2["digest_refs"] = {
        "prev_digest": entry1["digest_refs"]["entry_digest"],
        "payload_digest": payload_dig,
        "entry_digest": "1" * 64,
    }
    lines.append(canonical_json(entry2))
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_UNSANITIZED_PHI_REJECTED in d for d in defects)


def test_corrupted_trace_and_empty_file_handling(temp_trace_file: Path) -> None:
    """Empty files, non-existent files, and non-JSON lines fail closed."""
    # Non-existent
    non_existent = temp_trace_file.parent / "does_not_exist.jsonl"
    assert verify_trace(non_existent) is False

    # Empty file
    temp_trace_file.write_text("", encoding="utf-8")
    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_EMPTY_TRACE in d for d in defects)

    # Malformed JSON
    temp_trace_file.write_text("{not valid json\n", encoding="utf-8")
    is_valid, defects = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert any(REASON_CORRUPTED_TRACE in d for d in defects)
