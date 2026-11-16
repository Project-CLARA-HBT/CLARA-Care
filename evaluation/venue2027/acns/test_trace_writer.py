"""Tests for ACNS-traces — Immutable trace and measurement capture (Phase P05, venue acns).

Validates:
- Target contract: write_trace(event) -> sha256.
- Strictly monotonic event IDs.
- Positive control: round-trip trace output matches source events.
- Positive control: valid cryptographic hash chain and payload digests.
- Resumption and append mode.
- Sanitization: recursive redaction of credentials and PII.
- Adversarial control: tamper detection on outcome, reason, gap code, payload, and digests.
- Adversarial control: monotonicity violation and reordering detection.
- Adversarial control: credential leak and PII leak detection blocks verification.
- Adversarial control: corruption, empty files, and broken genesis blocks.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.venue2027.acns.trace_writer import (
    GENESIS_PREV_DIGEST,
    TraceEvent,
    TraceWriter,
    TraceWriterError,
    _compute_entry_digest,
    canonical_json,
    detect_sensitive_leak,
    read_trace,
    verify_trace,
    verify_trace_details,
    write_trace,
)


@pytest.fixture
def temp_trace_file(tmp_path: Path) -> Path:
    return tmp_path / "test_trace.jsonl"


# ==============================================================================
# Positive / Supported Controls
# ==============================================================================


def test_write_trace_contract_returns_sha256(temp_trace_file: Path) -> None:
    """Target contract: write_trace(event) -> sha256 returns 64-char hex digest."""
    event = {
        "raw_outcome": "ADMIT",
        "reason_code": "OK",
        "oracle_decision": "PASS",
        "evidence_gap_code": "none",
        "duration_seconds": 0.0012,
        "actual_backend": "local_deterministic",
        "payload": {"claim_id": "c1", "status": "verified"},
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
        writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"}),
        writer.write_trace({"raw_outcome": "REJECT", "reason_code": "G2_RECEIPT_AS_EXECUTION"}),
        writer.write_trace({"raw_outcome": "INDETERMINATE", "reason_code": "PENDING"}),
    ]

    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]

    # Verify digest chain links
    assert records[0]["digest_refs"]["prev_digest"] == GENESIS_PREV_DIGEST
    assert records[0]["digest_refs"]["entry_digest"] == digests[0]
    assert records[1]["digest_refs"]["prev_digest"] == digests[0]
    assert records[1]["digest_refs"]["entry_digest"] == digests[1]
    assert records[2]["digest_refs"]["prev_digest"] == digests[1]
    assert records[2]["digest_refs"]["entry_digest"] == digests[2]

    assert verify_trace(temp_trace_file) is True


def test_round_trip_matches_source_events(temp_trace_file: Path) -> None:
    """Round-trip trace output faithfully matches source events and preserves all fields."""
    events = [
        TraceEvent(
            raw_outcome="ADMIT",
            reason_code="OK",
            oracle_decision="PASS",
            evidence_gap_code="none",
            actual_backend="local_deterministic",
            duration_seconds=0.00045,
            cpu_duration_seconds=0.0003,
            db_duration_seconds=0.0,
            model_duration_seconds=0.0,
            model_cost_usd=0.0,
            signature_refs={"pair_digest": "abc123digest"},
            payload={"case_id": "case-01", "arm": "B3-evidence-boundary-aware"},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            reason_code="G2_RECEIPT_AS_EXECUTION",
            oracle_decision="PASS",
            evidence_gap_code="G2_RECEIPT_AS_EXECUTION",
            actual_backend="injected_mock",
            duration_seconds=0.00085,
            cpu_duration_seconds=0.0005,
            db_duration_seconds=0.0001,
            model_duration_seconds=0.0,
            model_cost_usd=0.0,
            signature_refs={"pair_digest": "def456digest"},
            payload={"case_id": "case-02", "arm": "B1-receipt-without-binding"},
        ),
    ]

    writer = TraceWriter(temp_trace_file)
    for evt in events:
        writer.write_trace(evt)

    records = read_trace(temp_trace_file)
    assert len(records) == 2

    # Check first record
    assert records[0]["raw_outcome"] == "ADMIT"
    assert records[0]["reason_code"] == "OK"
    assert records[0]["oracle_decision"] == "PASS"
    assert records[0]["evidence_gap_code"] == "none"
    assert records[0]["actual_backend"] == "local_deterministic"
    assert records[0]["duration_cost"]["duration_seconds"] == 0.00045
    assert records[0]["duration_cost"]["cpu_duration_seconds"] == 0.0003
    assert records[0]["signature_refs"]["pair_digest"] == "abc123digest"
    assert records[0]["payload"]["case_id"] == "case-01"

    # Check second record
    assert records[1]["raw_outcome"] == "REJECT"
    assert records[1]["reason_code"] == "G2_RECEIPT_AS_EXECUTION"
    assert records[1]["oracle_decision"] == "PASS"
    assert records[1]["evidence_gap_code"] == "G2_RECEIPT_AS_EXECUTION"
    assert records[1]["actual_backend"] == "injected_mock"
    assert records[1]["duration_cost"]["duration_seconds"] == 0.00085
    assert records[1]["payload"]["case_id"] == "case-02"

    assert verify_trace(temp_trace_file) is True


def test_sample_trace_artifact_is_verified() -> None:
    """The real sample trace artifact exists, has 16 records, and passes verification."""
    sample_path = Path("research/venue2027/proof/artifacts/acns_trace_sample.jsonl")
    assert sample_path.is_file()
    assert verify_trace(sample_path) is True
    records = read_trace(sample_path)
    assert len(records) == 16
    assert [r["event_id"] for r in records] == list(range(1, 17))


def test_resumed_writer_preserves_monotonicity_and_hash_chain(temp_trace_file: Path) -> None:
    """Instantiating a new TraceWriter on an existing file resumes monotonic sequence and chain."""
    w1 = TraceWriter(temp_trace_file)
    d1 = w1.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    d2 = w1.write_trace({"raw_outcome": "REJECT", "reason_code": "G4_SIGNATURE_AS_CONTEXT"})
    assert d1 != d2

    # New writer on same file
    w2 = TraceWriter(temp_trace_file)
    assert w2._last_event_id == 2
    assert w2._last_digest == d2

    d3 = w2.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]
    assert records[2]["digest_refs"]["prev_digest"] == d2
    assert records[2]["digest_refs"]["entry_digest"] == d3

    assert verify_trace(temp_trace_file) is True


def test_harness_pair_result_mapping_support(temp_trace_file: Path) -> None:
    """Directly supports records conforming to shared harness pair_result format."""
    pair_record = {
        "record_kind": "pair_result",
        "arm_id": "B3-evidence-boundary-aware",
        "case_id": "sok-claim-record-2/downgraded",
        "campaign_id": "acns-sok-evidence-boundaries-campaign",
        "duration_seconds": 6.6e-05,
        "pair_digest": "2ccc86e4e012a146641460bd34f3b90b3ac54e520354c65f1d9b81abc8ba7979",
        "source_commit": "28ff55110f980f42002524cef126290e91258cd6",
        "outcome": {
            "observed_outcome": "REJECT",
            "counted_as_success": False,
            "reason_code": "G2_RECEIPT_AS_EXECUTION",
        },
        "oracle": {
            "decision": "PASS",
            "expected_outcome": "REJECT",
            "gap_code": "G2_RECEIPT_AS_EXECUTION",
        },
    }
    digest = write_trace(pair_record, trace_path=temp_trace_file)
    assert len(digest) == 64

    records = read_trace(temp_trace_file)
    assert len(records) == 1
    assert records[0]["raw_outcome"] == "REJECT"
    assert records[0]["reason_code"] == "G2_RECEIPT_AS_EXECUTION"
    assert records[0]["oracle_decision"] == "PASS"
    assert records[0]["evidence_gap_code"] == "G2_RECEIPT_AS_EXECUTION"
    assert records[0]["signature_refs"]["pair_digest"] == pair_record["pair_digest"]
    assert records[0]["signature_refs"]["source_commit"] == pair_record["source_commit"]

    assert verify_trace(temp_trace_file) is True


def test_sanitization_scrubs_credentials_and_pii(temp_trace_file: Path) -> None:
    """Sensitive dictionary keys and pattern values are scrubbed before trace emission."""
    dirty_event = {
        "raw_outcome": "ADMIT",
        "reason_code": "OK",
        "api_key": "sk-ant-api03-1234567890abcdef1234567890",
        "secret": "top-secret-signing-key",
        "password": "mypassword123",
        "patient_name": "Tran Van B",
        "email": "patient@hospital.org",
        "ssn": "123-45-6789",
        "phone": "+84901234567",
        "payload": {
            "safe_metadata": "public-research-corpus",
            "header": "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake",
            "nested_pii": {
                "doctor_email": "doc@medical-council.vn",
                "patient_ssn": "987-65-4321",
                "phone_number": "(555) 123-4567",
            },
        },
    }

    digest = write_trace(dirty_event, trace_path=temp_trace_file)
    assert len(digest) == 64

    records = read_trace(temp_trace_file)
    rec = records[0]

    # Verify top-level scrubbed keys
    assert rec["payload"]["api_key"] == "[REDACTED_CREDENTIAL]"
    assert rec["payload"]["secret"] == "[REDACTED_CREDENTIAL]"
    assert rec["payload"]["password"] == "[REDACTED_CREDENTIAL]"
    assert rec["payload"]["patient_name"] == "[REDACTED_PII]"
    assert rec["payload"]["email"] == "[REDACTED_PII]"
    assert rec["payload"]["ssn"] == "[REDACTED_PII]"
    assert rec["payload"]["phone"] == "[REDACTED_PII]"

    # Verify nested pattern scrubbing
    assert rec["payload"]["safe_metadata"] == "public-research-corpus"
    assert "Bearer [REDACTED_CREDENTIAL]" in rec["payload"]["header"]
    assert rec["payload"]["nested_pii"]["doctor_email"] == "[REDACTED_PII]"
    assert rec["payload"]["nested_pii"]["patient_ssn"] == "[REDACTED_PII]"
    assert rec["payload"]["nested_pii"]["phone_number"] == "[REDACTED_PII]"

    # Verify no leaks remain in trace file
    assert detect_sensitive_leak(rec) == []
    assert verify_trace(temp_trace_file) is True


# ==============================================================================
# Adversarial / Negative Controls
# ==============================================================================


def test_adversarial_tamper_outcome_fails_verification(temp_trace_file: Path) -> None:
    """Tampering with raw_outcome in any line causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "G2_RECEIPT_AS_EXECUTION"})
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec0 = json.loads(lines[0])
    rec0["raw_outcome"] = "ADMIT"  # Maliciously flip REJECT to ADMIT
    lines[0] = json.dumps(rec0, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "TAMPER_DETECTED" in reason


def test_adversarial_tamper_reason_code_fails_verification(temp_trace_file: Path) -> None:
    """Tampering with reason_code causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "G2_RECEIPT_AS_EXECUTION"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["reason_code"] = "OK"  # Tamper reason code
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "TAMPER_DETECTED" in reason


def test_adversarial_tamper_duration_cost_fails_verification(temp_trace_file: Path) -> None:
    """Tampering with duration_cost metrics causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "duration_seconds": 1.25})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["duration_cost"]["duration_seconds"] = 0.05  # Forged lower latency
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "TAMPER_DETECTED" in reason


def test_adversarial_tamper_payload_fails_verification(temp_trace_file: Path) -> None:
    """Tampering with payload data causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "payload": {"verified": True}})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["verified"] = False  # Tamper payload
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "TAMPER_DETECTED" in reason


def test_adversarial_broken_hash_chain_fails_verification(temp_trace_file: Path) -> None:
    """Deleting an intermediate line breaks chain prev_digest links and fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "G4_SIGNATURE_AS_CONTEXT"})
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    # Delete line 1 (the middle event)
    lines_tampered = [lines[0], lines[2]]
    temp_trace_file.write_text("\n".join(lines_tampered) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert ("CHAIN_INTEGRITY_BROKEN" in reason) or ("NON_MONOTONIC_EVENT_ID" in reason)


def test_adversarial_reordering_fails_monotonicity(temp_trace_file: Path) -> None:
    """Reordering events in the trace fails monotonicity and hash chain checks."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "G2_RECEIPT_AS_EXECUTION"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    # Swap order
    lines_swapped = [lines[1], lines[0]]
    temp_trace_file.write_text("\n".join(lines_swapped) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False


def test_adversarial_credential_leak_blocks_verification(temp_trace_file: Path) -> None:
    """A trace containing an unredacted credential leaks is blocked fail-closed."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    # Manually tamper by injecting an unredacted API key into payload while attempting
    # to repair digests
    records = read_trace(temp_trace_file)
    rec = records[0]
    rec["payload"]["leaked_key"] = "sk-proj-9999999999888888887777777"
    # Recompute digests to bypass pure hash check
    p_dig = hashlib.sha256(canonical_json(rec["payload"]).encode("utf-8")).hexdigest()
    rec["digest_refs"]["payload_digest"] = p_dig
    e_dig = _compute_entry_digest(rec, rec["digest_refs"]["prev_digest"], p_dig)
    rec["digest_refs"]["entry_digest"] = e_dig

    temp_trace_file.write_text(canonical_json(rec) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "CREDENTIAL_LEAK_DETECTED" in reason


def test_adversarial_pii_leak_blocks_verification(temp_trace_file: Path) -> None:
    """A trace containing an unredacted SSN/PII is blocked fail-closed."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    records = read_trace(temp_trace_file)
    rec = records[0]
    rec["payload"]["unredacted_ssn"] = "000-12-3456"

    p_dig = hashlib.sha256(canonical_json(rec["payload"]).encode("utf-8")).hexdigest()
    rec["digest_refs"]["payload_digest"] = p_dig
    e_dig = _compute_entry_digest(rec, rec["digest_refs"]["prev_digest"], p_dig)
    rec["digest_refs"]["entry_digest"] = e_dig

    temp_trace_file.write_text(canonical_json(rec) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "CREDENTIAL_LEAK_DETECTED" in reason  # PII leak detected


def test_adversarial_corrupt_files_fail_verification(tmp_path: Path) -> None:
    """Nonexistent files, empty files, and malformed JSON fail verification."""
    non_existent = tmp_path / "does_not_exist.jsonl"
    assert verify_trace(non_existent) is False

    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("", encoding="utf-8")
    assert verify_trace(empty_file) is False

    corrupt_json = tmp_path / "corrupt.jsonl"
    corrupt_json.write_text("{not valid json\n", encoding="utf-8")
    assert verify_trace(corrupt_json) is False


def test_adversarial_bad_genesis_digest_fails(temp_trace_file: Path) -> None:
    """Genesis entry with non-zero prev_digest fails chain integrity."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["digest_refs"]["prev_digest"] = "f" * 64  # Bad genesis link
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert "CHAIN_INTEGRITY_BROKEN" in reason


def test_writer_refuses_corrupted_existing_file(temp_trace_file: Path) -> None:
    """TraceWriter refuses to open or append to a corrupted existing trace file."""
    temp_trace_file.write_text(
        '{"event_id": 1, "digest_refs": {"entry_digest": "abc"}}\n{"event_id": 1}\n'
    )
    with pytest.raises(TraceWriterError) as exc_info:
        TraceWriter(temp_trace_file)
    assert exc_info.value.reason_code == "NON_MONOTONIC_EVENT_ID"
