"""Tests for PST-traces — Immutable trace and measurement capture (Phase P05, venue pst).

Validates:
- Target contract: write_trace(event) -> sha256.
- Strictly monotonic event IDs (auto-increment and explicit sequence).
- Reconstructability score and linkability score validation [0.0, 1.0].
- Cryptographic hash chain (prev_digest, payload_digest, entry_digest).
- CPU/DB duration and cost metrics tracking.
- Positive control: round-trip trace output matches source events.
- Positive control: harness pair_result adapter support.
- Positive control: file resumption and append mode.
- Sanitization: recursive redaction of credentials, secrets, and PHI.
- Adversarial control: tamper detection on outcome, score, reason, duration, payload.
- Adversarial control: broken hash chain detection.
- Adversarial control: monotonicity violation and reordering detection.
- Adversarial control: score out-of-range (<0, >1, NaN, Inf, non-numeric) detection.
- Adversarial control: credential leak and PHI leak detection blocks verification.
- Adversarial control: corruption, empty files, and missing files.
- Real sample artifact verification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.venue2027.pst.trace_writer import (
    GENESIS_PREV_DIGEST,
    REASON_CHAIN_INTEGRITY_BROKEN,
    REASON_CORRUPTED_TRACE,
    REASON_CREDENTIAL_LEAK_DETECTED,
    REASON_EMPTY_TRACE,
    REASON_NON_MONOTONIC_EVENT_ID,
    REASON_PHI_LEAK_DETECTED,
    REASON_SCORE_OUT_OF_RANGE,
    REASON_TAMPER_DETECTED,
    TraceEvent,
    TraceWriter,
    TraceWriterError,
    read_trace,
    verify_trace,
    verify_trace_details,
    write_trace,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_ARTIFACT = REPO_ROOT / "research/venue2027/proof/artifacts/pst_trace_sample.jsonl"


@pytest.fixture
def temp_trace_file(tmp_path: Path) -> Path:
    return tmp_path / "test_pst_trace.jsonl"


# ==============================================================================
# Positive Controls
# ==============================================================================


def test_write_trace_contract_returns_sha256(temp_trace_file: Path) -> None:
    """Target contract: write_trace(event) -> sha256 returns 64-char hex digest."""
    event = {
        "raw_outcome": "ADMIT",
        "reconstructability_score": 1.0,
        "linkability_score": 0.108,
        "reason_code": "RULE_FULL_EVIDENCE",
        "oracle_decision": {"expected_outcome": "ADMIT", "decision": "MATCH"},
        "actual_backend": "B3",
        "duration_seconds": 0.00015,
        "cpu_duration_seconds": 0.00012,
        "db_duration_seconds": 0.00003,
        "cpu_cost": 0.00001,
        "db_cost": 0.000005,
        "payload": {"case_id": "PST-CASE-01-FULL", "family": "full_evidence"},
    }
    digest = write_trace(event, trace_path=temp_trace_file)

    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert temp_trace_file.is_file()
    assert verify_trace(temp_trace_file) is True


def test_write_trace_flexible_signatures(temp_trace_file: Path) -> None:
    """Supports write_trace(event, path), write_trace(path, event), write_trace(event, trace_path=path)."""
    ev1 = {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.98}
    ev2 = {"raw_outcome": "REJECT", "reconstructability_score": 0.0, "linkability_score": 0.64}
    ev3 = {"raw_outcome": "ADMIT", "reconstructability_score": 0.75, "linkability_score": 0.108}

    d1 = write_trace(ev1, trace_path=temp_trace_file)
    d2 = write_trace(temp_trace_file, ev2)
    d3 = write_trace(ev3, temp_trace_file)

    assert len(d1) == 64 and len(d2) == 64 and len(d3) == 64
    assert verify_trace(temp_trace_file) is True
    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]


def test_monotonic_event_ids_auto_increment(temp_trace_file: Path) -> None:
    """Consecutive writes produce strictly increasing monotonic event_ids starting at 1."""
    writer = TraceWriter(temp_trace_file, actual_backend="B3")
    digests = [
        writer.write_trace(
            {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.98}
        ),
        writer.write_trace(
            {"raw_outcome": "REJECT", "reconstructability_score": 0.0, "linkability_score": 0.64}
        ),
        writer.write_trace(
            {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.108}
        ),
    ]

    assert len(digests) == 3
    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]
    assert records[0]["digest_refs"]["prev_digest"] == GENESIS_PREV_DIGEST
    assert records[1]["digest_refs"]["prev_digest"] == digests[0]
    assert records[2]["digest_refs"]["prev_digest"] == digests[1]


def test_explicit_monotonic_event_ids(temp_trace_file: Path) -> None:
    """Explicitly supplied strictly increasing event_ids are admitted."""
    writer = TraceWriter(temp_trace_file, actual_backend="B3")
    writer.append(
        {
            "event_id": 10,
            "raw_outcome": "ADMIT",
            "reconstructability_score": 0.9,
            "linkability_score": 0.2,
        }
    )
    writer.append(
        {
            "event_id": 25,
            "raw_outcome": "REJECT",
            "reconstructability_score": 0.1,
            "linkability_score": 0.8,
        }
    )
    writer.append(
        {
            "event_id": 100,
            "raw_outcome": "ADMIT",
            "reconstructability_score": 0.95,
            "linkability_score": 0.15,
        }
    )

    records = read_trace(temp_trace_file)
    assert [r["event_id"] for r in records] == [10, 25, 100]
    assert verify_trace(temp_trace_file) is True


def test_round_trip_matches_source_events(temp_trace_file: Path) -> None:
    """Round-trip read matches recorded telemetry fields faithfully."""
    writer = TraceWriter(temp_trace_file, actual_backend="ReceiptMin")
    event = {
        "raw_outcome": "ADMIT",
        "reconstructability_score": 0.88,
        "linkability_score": 0.15,
        "reason_code": "RULE_RECEIPT_ANCHORED",
        "oracle_decision": {"verdict": "MATCH", "ground_truth": "ADMIT"},
        "actual_backend": "ReceiptMin",
        "duration_seconds": 0.0035,
        "cpu_duration_seconds": 0.0030,
        "db_duration_seconds": 0.0005,
        "cpu_cost": 0.00002,
        "db_cost": 0.00001,
        "signature_refs": {"witness_id": "wit_001", "merkle_root": "a" * 64},
        "payload": {"case_id": "case-01", "policy_epoch": "epoch-1"},
    }
    digest = writer.append(event)
    records = read_trace(temp_trace_file)

    assert len(records) == 1
    rec = records[0]
    assert rec["raw_outcome"] == "ADMIT"
    assert rec["reconstructability_score"] == 0.88
    assert rec["linkability_score"] == 0.15
    assert rec["reason_code"] == "RULE_RECEIPT_ANCHORED"
    assert rec["oracle_decision"] == {"verdict": "MATCH", "ground_truth": "ADMIT"}
    assert rec["actual_backend"] == "ReceiptMin"
    assert rec["duration_cost"]["duration_seconds"] == 0.0035
    assert rec["duration_cost"]["cpu_duration_seconds"] == 0.0030
    assert rec["duration_cost"]["db_duration_seconds"] == 0.0005
    assert rec["signature_refs"]["witness_id"] == "wit_001"
    assert rec["payload"]["case_id"] == "case-01"
    assert rec["digest_refs"]["entry_digest"] == digest
    assert verify_trace(temp_trace_file) is True


def test_harness_pair_result_ingestion(temp_trace_file: Path) -> None:
    """Harness pair_result dictionary format is parsed and recorded correctly."""
    pair_record = {
        "record_kind": "pair_result",
        "arm_id": "B0",
        "campaign_id": "pst-sample-campaign",
        "case_id": "PST-CASE-01-FULL",
        "duration_seconds": 0.000141,
        "harness_version": "1.0.0",
        "linkability_score": 0.98,
        "reconstructability_score": 1.0,
        "logical_op_id": "pst-sample-campaign:B0::PST-CASE-01-FULL",
        "oracle": {
            "arm_id": "B0",
            "decision": "MATCH",
            "evidence_refs": [],
            "expected_outcome": "ADMIT",
            "oracle_id": "pst-forensic-reference",
            "reason_code": "RULE_FULL_EVIDENCE",
        },
        "outcome": {
            "counted_as_success": True,
            "detail": '{"baseline_id": "B0", "status": "RECONSTRUCT", "reconstructability": 1.0, "linkability": 0.98, "events_count": 1}',
            "observed_outcome": "ADMIT",
            "retriable": False,
        },
        "pair_digest": "60daae79720aeba4eaa8e06537a1f0e9fac1b487fbd83dc5e3c7141a404b523a",
        "python_version": "3.12.3",
        "recorded_at": 1794807735.545805,
        "seed": 2027,
        "source_commit": "75ad321ea230ad398d71f4a0afb26e0cdef83982",
    }
    digest = write_trace(pair_record, trace_path=temp_trace_file)
    records = read_trace(temp_trace_file)

    assert len(records) == 1
    rec = records[0]
    assert rec["actual_backend"] == "UNKNOWN"
    assert rec["payload"]["arm_id"] == "B0"
    assert rec["raw_outcome"] == "ADMIT"
    assert rec["reconstructability_score"] == 1.0
    assert rec["linkability_score"] == 0.98
    assert rec["oracle_decision"]["oracle_id"] == "pst-forensic-reference"
    assert rec["signature_refs"]["pair_digest"] == pair_record["pair_digest"]
    assert rec["digest_refs"]["entry_digest"] == digest
    assert verify_trace(temp_trace_file) is True


def test_trace_resumption_and_append(temp_trace_file: Path) -> None:
    """A new TraceWriter instance picks up state and continues the monotonic hash chain."""
    writer1 = TraceWriter(temp_trace_file, actual_backend="B0")
    d1 = writer1.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.98}
    )
    assert len(d1) == 64
    d2 = writer1.append(
        {"raw_outcome": "REJECT", "reconstructability_score": 0.0, "linkability_score": 0.64}
    )

    # Reopen trace file with second writer
    writer2 = TraceWriter(temp_trace_file, actual_backend="B3")
    assert writer2.last_event_id == 2
    assert writer2.last_entry_digest == d2

    d3 = writer2.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.108}
    )
    d4 = writer2.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 0.75, "linkability_score": 0.108}
    )

    records = read_trace(temp_trace_file)
    assert len(records) == 4
    assert [r["event_id"] for r in records] == [1, 2, 3, 4]
    assert records[2]["digest_refs"]["prev_digest"] == d2
    assert records[3]["digest_refs"]["prev_digest"] == d3
    assert records[3]["digest_refs"]["entry_digest"] == d4
    assert verify_trace(temp_trace_file) is True


def test_score_boundary_values(temp_trace_file: Path) -> None:
    """Exact boundary values 0.0 and 1.0 for both scores are valid."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "REJECT", "reconstructability_score": 0.0, "linkability_score": 0.0}
    )
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 1.0}
    )

    records = read_trace(temp_trace_file)
    assert records[0]["reconstructability_score"] == 0.0
    assert records[0]["linkability_score"] == 0.0
    assert records[1]["reconstructability_score"] == 1.0
    assert records[1]["linkability_score"] == 1.0
    assert verify_trace(temp_trace_file) is True


def test_trace_event_dataclass_input(temp_trace_file: Path) -> None:
    """TraceEvent dataclass instances are accepted and written correctly."""
    event = TraceEvent(
        raw_outcome="ADMIT",
        reconstructability_score=0.92,
        linkability_score=0.18,
        reason_code="RULE_RECEIPT_ANCHORED",
        oracle_decision={"expected_outcome": "ADMIT"},
        actual_backend="ReceiptMin",
        duration_seconds=0.0012,
        cpu_duration_seconds=0.0010,
        cpu_cost=0.00001,
        payload={"case_id": "test-dc"},
    )
    digest = write_trace(event, trace_path=temp_trace_file)
    assert len(digest) == 64
    assert verify_trace(temp_trace_file) is True


def test_sanitization_removes_phi_and_credentials(temp_trace_file: Path) -> None:
    """When sanitize=True, credentials and PHI are recursively scrubbed to [REDACTED_*]."""
    tainted = {
        "raw_outcome": "ADMIT",
        "reconstructability_score": 0.8,
        "linkability_score": 0.2,
        "api_key": "sk-1234567890abcdef12345678",
        "password": "SuperSecretPassword123!",
        "payload": {
            "patient_name": "Nguyen Van A",
            "patient_id": "patient-999",
            "ssn": "123-45-6789",
            "email": "patient@hospital.org",
            "phone": "555-123-4567",
            "safe_metadata": "diagnostic_imaging",
        },
    }
    write_trace(tainted, trace_path=temp_trace_file, sanitize=True)

    records = read_trace(temp_trace_file)
    rec = records[0]
    payload = rec["payload"]
    assert payload["patient_name"] == "[REDACTED_PHI]"
    assert payload["patient_id"] == "[REDACTED_PHI]"
    assert payload["ssn"] == "[REDACTED_PHI]"
    assert payload["email"] == "[REDACTED_PHI]"
    assert payload["phone"] == "[REDACTED_PHI]"
    assert "safe_metadata" not in payload
    assert verify_trace(temp_trace_file) is True


def test_real_sample_artifact_valid() -> None:
    """The permanent sample artifact research/venue2027/proof/artifacts/pst_trace_sample.jsonl is valid."""
    assert SAMPLE_ARTIFACT.is_file(), f"Sample artifact missing: {SAMPLE_ARTIFACT}"
    records = read_trace(SAMPLE_ARTIFACT)
    assert len(records) >= 4, f"Sample artifact should have >= 4 records, got {len(records)}"
    is_valid, reason = verify_trace_details(SAMPLE_ARTIFACT)
    assert is_valid is True, f"Sample artifact verification failed: {reason}"


# ==============================================================================
# Adversarial Controls
# ==============================================================================


def test_non_monotonic_explicit_id_rejected_on_write(temp_trace_file: Path) -> None:
    """Explicit event_id <= last_event_id raises NON_MONOTONIC_EVENT_ID."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {
            "event_id": 5,
            "raw_outcome": "ADMIT",
            "reconstructability_score": 1.0,
            "linkability_score": 0.5,
        }
    )

    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(
            {
                "event_id": 5,
                "raw_outcome": "ADMIT",
                "reconstructability_score": 1.0,
                "linkability_score": 0.5,
            }
        )
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID

    with pytest.raises(TraceWriterError) as exc_info2:
        writer.append(
            {
                "event_id": 3,
                "raw_outcome": "ADMIT",
                "reconstructability_score": 1.0,
                "linkability_score": 0.5,
            }
        )
    assert exc_info2.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID


def test_monotonicity_violation_tamper_detected_in_verification(
    temp_trace_file: Path,
) -> None:
    """Tampering event_ids in trace file so sequence is non-monotonic fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.5}
    )
    writer.append(
        {"raw_outcome": "REJECT", "reconstructability_score": 0.0, "linkability_score": 0.5}
    )

    # Tamper with second line's event_id
    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec2 = json.loads(lines[1])
    rec2["event_id"] = 1  # Duplicate of line 1
    lines[1] = json.dumps(rec2)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_NON_MONOTONIC_EVENT_ID in reason


@pytest.mark.parametrize(
    "bad_score",
    [-0.1, 1.01, float("nan"), float("inf"), float("-inf"), "not_a_number", None, True, False],
)
def test_reconstructability_score_out_of_range_rejected_on_write(
    temp_trace_file: Path, bad_score: object
) -> None:
    """reconstructability_score outside [0.0, 1.0] raises SCORE_OUT_OF_RANGE on write."""
    writer = TraceWriter(temp_trace_file)
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(
            {
                "raw_outcome": "ADMIT",
                "reconstructability_score": bad_score,
                "linkability_score": 0.5,
            }
        )
    assert exc_info.value.reason_code == REASON_SCORE_OUT_OF_RANGE


@pytest.mark.parametrize(
    "bad_score",
    [-0.5, 2.0, float("nan"), float("inf"), float("-inf"), "invalid", None, True, False],
)
def test_linkability_score_out_of_range_rejected_on_write(
    temp_trace_file: Path, bad_score: object
) -> None:
    """linkability_score outside [0.0, 1.0] raises SCORE_OUT_OF_RANGE on write."""
    writer = TraceWriter(temp_trace_file)
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(
            {
                "raw_outcome": "ADMIT",
                "reconstructability_score": 0.5,
                "linkability_score": bad_score,
            }
        )
    assert exc_info.value.reason_code == REASON_SCORE_OUT_OF_RANGE


def test_score_out_of_range_detected_in_verification(temp_trace_file: Path) -> None:
    """Tampering score to out-of-range in persisted trace fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 0.9, "linkability_score": 0.2}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["reconstructability_score"] = 1.5
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_SCORE_OUT_OF_RANGE in reason


def test_tamper_detection_raw_outcome(temp_trace_file: Path) -> None:
    """Modifying raw_outcome in trace file fails TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.5}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["raw_outcome"] = "REJECT"  # Tamper
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_tamper_detection_scores(temp_trace_file: Path) -> None:
    """Modifying scores in trace file fails TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.108}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["linkability_score"] = 0.5  # Tamper within [0, 1]
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_tamper_detection_payload(temp_trace_file: Path) -> None:
    """Modifying payload content in trace file fails TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {
            "raw_outcome": "ADMIT",
            "reconstructability_score": 1.0,
            "linkability_score": 0.2,
            "payload": {"case_id": "PST-CASE-01", "original": "true"},
        }
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["original"] = "false"  # Tamper
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_tamper_detection_reason_code(temp_trace_file: Path) -> None:
    """Modifying reason_code in trace file fails TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {
            "raw_outcome": "ADMIT",
            "reconstructability_score": 1.0,
            "linkability_score": 0.2,
            "reason_code": "ORIGINAL_REASON",
        }
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["reason_code"] = "TAMPERED_REASON"
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_broken_digest_chain_detected(temp_trace_file: Path) -> None:
    """Modifying prev_digest on second record fails CHAIN_INTEGRITY_BROKEN."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.5}
    )
    writer.append(
        {"raw_outcome": "REJECT", "reconstructability_score": 0.0, "linkability_score": 0.5}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec2 = json.loads(lines[1])
    rec2["digest_refs"]["prev_digest"] = "f" * 64  # Corrupt chain link
    lines[1] = json.dumps(rec2)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_CHAIN_INTEGRITY_BROKEN in reason


def test_unsanitized_credential_leak_rejected_on_write(temp_trace_file: Path) -> None:
    """When sanitize=False, raw credentials raise CREDENTIAL_LEAK_DETECTED on write."""
    writer = TraceWriter(temp_trace_file)
    tainted = {
        "raw_outcome": "ADMIT",
        "reconstructability_score": 1.0,
        "linkability_score": 0.5,
        "api_key": "sk-1234567890abcdef12345678",
    }
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(tainted, sanitize=False)
    assert exc_info.value.reason_code == REASON_CREDENTIAL_LEAK_DETECTED


def test_unsanitized_phi_leak_rejected_on_write(temp_trace_file: Path) -> None:
    """When sanitize=False, raw PHI raises PHI_LEAK_DETECTED on write."""
    writer = TraceWriter(temp_trace_file)
    tainted = {
        "raw_outcome": "ADMIT",
        "reconstructability_score": 1.0,
        "linkability_score": 0.5,
        "payload": {"patient_name": "Nguyen Van B", "ssn": "987-65-4321"},
    }
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(tainted, sanitize=False)
    assert exc_info.value.reason_code == REASON_PHI_LEAK_DETECTED


def test_credential_leak_detected_in_verification(temp_trace_file: Path) -> None:
    """Tampered trace file containing unredacted credentials fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.5}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["auth"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.unredacted_token"
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert (REASON_CREDENTIAL_LEAK_DETECTED in reason) or (REASON_TAMPER_DETECTED in reason)


def test_phi_leak_detected_in_verification(temp_trace_file: Path) -> None:
    """Tampered trace file containing unredacted PHI fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.append(
        {"raw_outcome": "ADMIT", "reconstructability_score": 1.0, "linkability_score": 0.5}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["patient_ssn"] = "123-45-6789"
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert (REASON_PHI_LEAK_DETECTED in reason) or (REASON_TAMPER_DETECTED in reason)


def test_empty_file_rejected(tmp_path: Path) -> None:
    """Empty trace file fails verification with EMPTY_TRACE."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("", encoding="utf-8")

    is_valid, reason = verify_trace_details(empty_file)
    assert is_valid is False
    assert REASON_EMPTY_TRACE in reason
    assert verify_trace(empty_file) is False


def test_corrupted_json_rejected(tmp_path: Path) -> None:
    """Trace file containing invalid JSON line fails verification with CORRUPTED_TRACE."""
    corrupt_file = tmp_path / "corrupt.jsonl"
    corrupt_file.write_text('{"event_id": 1}\n{not valid json}\n', encoding="utf-8")

    is_valid, reason = verify_trace_details(corrupt_file)
    assert is_valid is False
    assert REASON_CORRUPTED_TRACE in reason


def test_missing_file_rejected(tmp_path: Path) -> None:
    """Non-existent trace file fails verification with EMPTY_TRACE."""
    missing_file = tmp_path / "non_existent.jsonl"
    is_valid, reason = verify_trace_details(missing_file)
    assert is_valid is False
    assert REASON_EMPTY_TRACE in reason
    assert verify_trace(missing_file) is False


def test_missing_required_fields_rejected(tmp_path: Path) -> None:
    """Trace record missing required fields fails verification with CORRUPTED_TRACE."""
    bad_record_file = tmp_path / "bad_record.jsonl"
    bad_record_file.write_text(
        json.dumps({"event_id": 1, "raw_outcome": "ADMIT"}) + "\n", encoding="utf-8"
    )

    is_valid, reason = verify_trace_details(bad_record_file)
    assert is_valid is False
    assert REASON_CORRUPTED_TRACE in reason


def test_replay_tracked_development_bundle(tmp_path: Path) -> None:
    from evaluation.venue2027._shared.measurement import load_bundle_records

    _, manifest, pairs = load_bundle_records(SAMPLE_ARTIFACT.with_name("pst_run_bundle.jsonl"))
    target = tmp_path / "actual.jsonl"
    writer = TraceWriter(target)
    for pair in pairs:
        digest = writer.append(pair)
        assert writer.append(pair) == digest
    assert verify_trace(target)
    rows = read_trace(target)
    assert len(rows) == manifest["planned_pairs"] == 16
    for row, pair in zip(rows, pairs, strict=True):
        assert row["raw_outcome"] == pair["outcome"]["observed_outcome"]
        assert row["oracle_decision"]["decision"] == pair["oracle"]["decision"]
        assert row["signature_refs"]["pair_digest"] == pair["pair_digest"]
        assert row["payload"]["arm_id"] == pair["arm_id"]
        assert row["timestamp"] == pair["recorded_at"]
        assert row["duration_cost"]["cpu_duration_seconds"] is None
    assert target.read_bytes() == SAMPLE_ARTIFACT.read_bytes()


def test_reject_changed_retry_and_resume_after_tampering(tmp_path: Path) -> None:
    from evaluation.venue2027._shared.measurement import load_bundle_records

    _, _, pairs = load_bundle_records(SAMPLE_ARTIFACT.with_name("pst_run_bundle.jsonl"))
    target = tmp_path / "events.jsonl"
    writer = TraceWriter(target)
    writer.append(pairs[0])
    with pytest.raises(TraceWriterError):
        writer.append({**pairs[0], "duration_seconds": 100})
    with pytest.raises(TraceWriterError):
        writer.append({**pairs[0], "case_id": "changed_case"})
    rows = read_trace(target)
    rows[0]["reason_code"] = "MODIFIED"
    target.write_text(json.dumps(rows[0]) + "\n")
    before = target.read_bytes()
    with pytest.raises(TraceWriterError):
        writer.append(pairs[1])
    assert target.read_bytes() == before


def test_interleaved_writers_serialize(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "events.jsonl"
    writers = [TraceWriter(path) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda w: w.append({"raw_outcome": "REJECT"}), writers))
    assert verify_trace(path)
    assert [row["event_id"] for row in read_trace(path)] == list(range(1, 9))


def test_failure_retains_absent_measurements(tmp_path: Path) -> None:
    from evaluation.venue2027._shared.harness import _pair_digest
    from evaluation.venue2027._shared.measurement import load_bundle_records

    _, _, pairs = load_bundle_records(SAMPLE_ARTIFACT.with_name("pst_run_bundle.jsonl"))
    pair = dict(pairs[0], outcome={"observed_outcome": "EXECUTION_ERROR", "detail": "RuntimeError"})
    pair.update(
        pair_digest=_pair_digest(pair), reconstructability_score=None, linkability_score=None
    )
    target = tmp_path / "trace.jsonl"
    TraceWriter(target).append(pair)
    (row,) = read_trace(target)
    assert row["raw_outcome"] == "EXECUTION_ERROR"
    assert row["linkability_score"] is None
    assert row["reconstructability_score"] is None
    assert row["actual_backend"] == "UNKNOWN"
    assert verify_trace(target)
