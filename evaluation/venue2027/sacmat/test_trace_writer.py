"""Tests for SACMAT-traces — Immutable trace and measurement capture (Phase P05, venue sacmat).

Validates:
- Target contract: write_trace(event) -> sha256.
- Strictly monotonic event IDs.
- Cryptographic hash chain (prev_digest, payload_digest, entry_digest).
- Delegation lineage capture and verification.
- CPU/DB duration and cost metrics tracking.
- Positive control: round-trip trace output matches source events.
- Positive control: harness pair_result adapter support.
- Positive control: file resumption and append mode.
- Sanitization: recursive redaction of credentials and PII.
- Adversarial control: tamper detection on outcome, reason, lineage, oracle, durations, digests.
- Adversarial control: monotonicity violation and reordering detection.
- Adversarial control: credential leak and PII leak detection blocks verification.
- Adversarial control: corruption, empty files, and missing files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.venue2027.sacmat.trace_writer import (
    DEFAULT_TRACE_PATH,
    GENESIS_PREV_DIGEST,
    REASON_CHAIN_INTEGRITY_BROKEN,
    REASON_CORRUPTED_TRACE,
    REASON_CREDENTIAL_LEAK_DETECTED,
    REASON_EMPTY_TRACE,
    REASON_INVALID_RECORD,
    REASON_NON_MONOTONIC_EVENT_ID,
    REASON_TAMPER_DETECTED,
    TraceEvent,
    TraceWriter,
    TraceWriterError,
    detect_sensitive_leak,
    read_trace,
    verify_trace,
    verify_trace_details,
    write_trace,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_ARTIFACT = REPO_ROOT / DEFAULT_TRACE_PATH


@pytest.fixture
def temp_trace_file(tmp_path: Path) -> Path:
    return tmp_path / "test_trace.jsonl"


# ==============================================================================
# Positive Controls
# ==============================================================================


def test_write_trace_contract_returns_sha256(temp_trace_file: Path) -> None:
    """Target contract: write_trace(event) -> sha256 returns 64-char hex digest."""
    event = {
        "raw_outcome": "ADMIT",
        "reason_code": "CONFORMANT",
        "oracle_decision": {"expected_outcome": "ADMIT"},
        "delegation_lineage": ["patient-root", "doctor-delegate-1"],
        "actual_backend": "candidate",
        "duration_seconds": 0.0015,
        "cpu_duration_seconds": 0.0012,
        "db_duration_seconds": 0.0003,
        "cpu_cost": 0.00001,
        "db_cost": 0.000005,
        "payload": {"case_id": "T1_CONFORMANT", "trace_id": "trace-01"},
    }
    digest = write_trace(event, trace_path=temp_trace_file)

    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert temp_trace_file.is_file()
    assert verify_trace(temp_trace_file) is True


def test_monotonic_event_ids(temp_trace_file: Path) -> None:
    """Consecutive writes produce strictly increasing monotonic event_ids starting at 1."""
    writer = TraceWriter(temp_trace_file, actual_backend="candidate")
    digests = [
        writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "CONFORMANT"}),
        writer.write_trace({"raw_outcome": "REJECT", "reason_code": "DELEGATION_CYCLE"}),
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
            reason_code="CONFORMANT",
            oracle_decision={"expected_outcome": "ADMIT", "verdict": "PERMIT"},
            delegation_lineage=["patient-root", "doctor-delegate-1"],
            actual_backend="candidate",
            duration_seconds=0.0012,
            cpu_duration_seconds=0.001,
            db_duration_seconds=0.0002,
            model_duration_seconds=0.0,
            cpu_cost=0.00002,
            db_cost=0.00001,
            model_cost_usd=0.0,
            signature_refs={"pair_digest": "abcdef123456"},
            payload={"case_id": "case-01", "scope": "treatment"},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            reason_code="REVOCATION_BEFORE_REPLAY",
            oracle_decision={"expected_outcome": "REJECT", "verdict": "DENY"},
            delegation_lineage=["patient-root", "delegate-1"],
            actual_backend="cedar",
            duration_seconds=0.0008,
            cpu_duration_seconds=0.0006,
            db_duration_seconds=0.0002,
            model_duration_seconds=0.0,
            cpu_cost=0.00001,
            db_cost=0.000005,
            model_cost_usd=0.0,
            signature_refs={"pair_digest": "789012abcdef"},
            payload={"case_id": "case-02", "scope": "research"},
        ),
    ]

    for ev in events:
        write_trace(ev, trace_path=temp_trace_file)

    records = read_trace(temp_trace_file)
    assert len(records) == 2

    # Verify event 1
    r1 = records[0]
    assert r1["raw_outcome"] == "ADMIT"
    assert r1["reason_code"] == "CONFORMANT"
    assert r1["oracle_decision"] == {"expected_outcome": "ADMIT", "verdict": "PERMIT"}
    assert r1["delegation_lineage"] == ["patient-root", "doctor-delegate-1"]
    assert r1["actual_backend"] == "candidate"
    assert r1["duration_cost"]["cpu_duration_seconds"] == 0.001
    assert r1["duration_cost"]["db_duration_seconds"] == 0.0002
    assert r1["payload"]["case_id"] == "case-01"

    # Verify event 2
    r2 = records[1]
    assert r2["raw_outcome"] == "REJECT"
    assert r2["reason_code"] == "REVOCATION_BEFORE_REPLAY"
    assert r2["oracle_decision"] == {"expected_outcome": "REJECT", "verdict": "DENY"}
    assert r2["delegation_lineage"] == ["patient-root", "delegate-1"]
    assert r2["actual_backend"] == "cedar"
    assert r2["payload"]["case_id"] == "case-02"

    assert verify_trace(temp_trace_file) is True


def test_delegation_lineage_recorded_and_verified(temp_trace_file: Path) -> None:
    """Traces with multi-hop delegation chains and cycles are accurately recorded and verified."""
    writer = TraceWriter(temp_trace_file, actual_backend="openfga")

    lineage_multihop = ["patient-root", "delegate-1", "delegate-2", "delegate-3"]
    lineage_cycle = ["patient-root", "delegate-1", "delegate-2", "delegate-1"]

    writer.write_trace(
        {
            "raw_outcome": "ADMIT",
            "reason_code": "DELEGATION_VALID",
            "delegation_lineage": lineage_multihop,
        }
    )
    writer.write_trace(
        {
            "raw_outcome": "REJECT",
            "reason_code": "DELEGATION_CYCLE",
            "delegation_lineage": lineage_cycle,
        }
    )

    records = read_trace(temp_trace_file)
    assert records[0]["delegation_lineage"] == lineage_multihop
    assert records[1]["delegation_lineage"] == lineage_cycle
    assert verify_trace(temp_trace_file) is True


def test_cpu_db_duration_and_cost_metrics(temp_trace_file: Path) -> None:
    """CPU and DB duration and cost metrics are preserved and structured cleanly."""
    event = {
        "raw_outcome": "ADMIT",
        "reason_code": "OK",
        "cpu_duration_seconds": 0.0025,
        "db_duration_seconds": 0.0011,
        "duration_seconds": 0.0036,
        "cpu_cost": 0.00003,
        "db_cost": 0.000015,
        "model_duration_seconds": 0.0,
        "model_cost_usd": 0.0,
    }
    write_trace(event, trace_path=temp_trace_file)

    rec = read_trace(temp_trace_file)[0]
    dc = rec["duration_cost"]
    assert dc["cpu_duration_seconds"] == 0.0025
    assert dc["db_duration_seconds"] == 0.0011
    assert dc["duration_seconds"] == 0.0036
    assert dc["cpu_cost"] == 0.00003
    assert dc["db_cost"] == 0.000015
    assert verify_trace(temp_trace_file) is True


def test_harness_pair_result_adapter(temp_trace_file: Path) -> None:
    """Harness pair_result records from _shared.harness are adapted automatically."""
    pair_record = {
        "record_kind": "pair_result",
        "logical_op_id": "sacmat_campaign:candidate::T1_PERMIT",
        "campaign_id": "sacmat_campaign",
        "arm_id": "candidate",
        "case_id": "T1_PERMIT",
        "seed": 42,
        "source_commit": "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614",
        "outcome": {
            "observed_outcome": "ADMIT",
            "counted_as_success": True,
            "retriable": False,
            "detail": "CONFORMANT",
        },
        "oracle": {
            "expected_outcome": "ADMIT",
            "rule": "conformant",
        },
        "duration_seconds": 0.00234,
        "pair_digest": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    }
    digest = write_trace(pair_record, trace_path=temp_trace_file)
    assert len(digest) == 64

    rec = read_trace(temp_trace_file)[0]
    assert rec["raw_outcome"] == "ADMIT"
    assert rec["reason_code"] == "CONFORMANT"
    assert rec["actual_backend"] == "candidate"
    assert rec["oracle_decision"]["expected_outcome"] == "ADMIT"
    assert rec["signature_refs"]["pair_digest"] == pair_record["pair_digest"]
    assert rec["payload"]["case_id"] == "T1_PERMIT"
    assert verify_trace(temp_trace_file) is True


def test_resumption_and_append_mode(temp_trace_file: Path) -> None:
    """A new TraceWriter instance appends to an existing trace preserving monotonicity and hash chain."""
    writer1 = TraceWriter(temp_trace_file, actual_backend="candidate")
    dig1 = writer1.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    dig2 = writer1.write_trace({"raw_outcome": "REJECT", "reason_code": "EXPIRED"})
    assert len(dig1) == 64
    assert len(dig2) == 64

    # Create new writer instance pointing to the same file
    writer2 = TraceWriter(temp_trace_file, actual_backend="cedar")
    assert writer2.last_event_id == 2
    assert writer2.last_entry_digest == dig2

    dig3 = writer2.write_trace({"raw_outcome": "ADMIT", "reason_code": "REGRANT"})

    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]
    assert records[2]["digest_refs"]["prev_digest"] == dig2
    assert records[2]["digest_refs"]["entry_digest"] == dig3
    assert records[2]["actual_backend"] == "cedar"
    assert verify_trace(temp_trace_file) is True


def test_sanitization_positive(temp_trace_file: Path) -> None:
    """Credentials and PII are redacted recursively during trace writing."""
    event = {
        "raw_outcome": "ADMIT",
        "reason_code": "OK",
        "payload": {
            "api_key": "sk-1234567890abcdef123456",
            "password": "secret_password_123",
            "token": "token_xyz",
            "patient_name": "Nguyen Van A",
            "email": "patient@hospital.vn",
            "ssn": "123-45-6789",
            "phone": "+84 912 345 678",
            "header": "Authorization: Bearer my_bearer_token_abc123",
            "safe_metadata": "public-research-case",
        },
    }
    write_trace(event, trace_path=temp_trace_file, sanitize=True)

    records = read_trace(temp_trace_file)
    p = records[0]["payload"]
    assert p["api_key"] == "[REDACTED_CREDENTIAL]"
    assert p["password"] == "[REDACTED_CREDENTIAL]"
    assert p["token"] == "[REDACTED_CREDENTIAL]"
    assert p["patient_name"] == "[REDACTED_PII]"
    assert p["email"] == "[REDACTED_PII]"
    assert p["ssn"] == "[REDACTED_PII]"
    assert p["phone"] == "[REDACTED_PII]"
    assert "Bearer [REDACTED_CREDENTIAL]" in p["header"]
    assert p["safe_metadata"] == "public-research-case"

    assert detect_sensitive_leak(records[0]) == []
    assert verify_trace(temp_trace_file) is True


def test_sample_artifact_valid() -> None:
    """The committed sample artifact passes verification."""
    if SAMPLE_ARTIFACT.is_file():
        assert verify_trace(SAMPLE_ARTIFACT) is True
        records = read_trace(SAMPLE_ARTIFACT)
        assert len(records) >= 5


# ==============================================================================
# Adversarial / Negative Controls
# ==============================================================================


def test_adversarial_tamper_raw_outcome(temp_trace_file: Path) -> None:
    """Tampering with raw_outcome in any line causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "DELEGATION_CYCLE"})
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec0 = json.loads(lines[0])
    rec0["raw_outcome"] = "ADMIT"  # Maliciously flip REJECT to ADMIT
    lines[0] = json.dumps(rec0, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_reason_code(temp_trace_file: Path) -> None:
    """Tampering with reason_code causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "DELEGATION_EXPIRED"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["reason_code"] = "OK"  # Tamper reason code
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_delegation_lineage(temp_trace_file: Path) -> None:
    """Tampering with delegation_lineage fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {
            "raw_outcome": "ADMIT",
            "reason_code": "OK",
            "delegation_lineage": ["patient-root", "delegate-1"],
        }
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["delegation_lineage"] = ["patient-root", "forged-delegate"]
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_oracle_decision(temp_trace_file: Path) -> None:
    """Tampering with oracle_decision fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {
            "raw_outcome": "REJECT",
            "oracle_decision": {"expected_outcome": "REJECT"},
        }
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["oracle_decision"] = {"expected_outcome": "ADMIT"}  # forged oracle verdict
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_duration_cost(temp_trace_file: Path) -> None:
    """Tampering with duration_cost fields fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "duration_seconds": 1.5})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["duration_cost"]["duration_seconds"] = 0.0001  # forged lower latency
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_entry_digest(temp_trace_file: Path) -> None:
    """Forging entry_digest breaks hash chain verification."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    writer.write_trace({"raw_outcome": "REJECT", "reason_code": "CYCLE"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec0 = json.loads(lines[0])
    rec0["digest_refs"]["entry_digest"] = "0" * 64
    lines[0] = json.dumps(rec0, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert (
        REASON_TAMPER_DETECTED in reason
        or REASON_CHAIN_INTEGRITY_BROKEN in reason
    )


def test_adversarial_tamper_prev_digest(temp_trace_file: Path) -> None:
    """Tampering with prev_digest breaks chain integrity check."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec1 = json.loads(lines[1])
    rec1["digest_refs"]["prev_digest"] = "f" * 64
    lines[1] = json.dumps(rec1, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_CHAIN_INTEGRITY_BROKEN in reason


def test_adversarial_non_monotonic_event_id(temp_trace_file: Path) -> None:
    """Non-monotonic or duplicate event IDs cause verify_trace to fail."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec1 = json.loads(lines[1])
    rec1["event_id"] = 1  # Duplicate event_id = 1
    lines[1] = json.dumps(rec1, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_NON_MONOTONIC_EVENT_ID in reason


def test_adversarial_explicit_decreasing_event_id(temp_trace_file: Path) -> None:
    """Explicitly providing a non-monotonic event_id on write raises TraceWriterError."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "event_id": 5})

    with pytest.raises(TraceWriterError) as exc_info:
        writer.write_trace({"raw_outcome": "ADMIT", "event_id": 3})
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID

    with pytest.raises(TraceWriterError) as exc_info2:
        writer.write_trace({"raw_outcome": "ADMIT", "event_id": 5})
    assert exc_info2.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID


def test_adversarial_credential_leak_blocks_verification(temp_trace_file: Path) -> None:
    """Unsanitized credentials in trace file cause verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    # Write event bypassing sanitization
    writer.write_trace(
        {
            "raw_outcome": "ADMIT",
            "reason_code": "OK",
            "payload": {"api_key": "sk-unredacted_secret_key_12345"},
        },
        sanitize=False,
    )

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_CREDENTIAL_LEAK_DETECTED in reason


def test_adversarial_pii_leak_blocks_verification(temp_trace_file: Path) -> None:
    """Unsanitized PII in trace file causes verify_trace to return False."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {
            "raw_outcome": "ADMIT",
            "reason_code": "OK",
            "payload": {
                "patient_name": "Tran Van B",
                "ssn": "987-65-4321",
                "email": "doctor@hospital.org",
            },
        },
        sanitize=False,
    )

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_CREDENTIAL_LEAK_DETECTED in reason


def test_adversarial_corrupted_json(temp_trace_file: Path) -> None:
    """Corrupted JSON lines in trace file fail verification."""
    temp_trace_file.write_text(
        '{"event_id": 1, "raw_outcome": "ADMIT"}\nnot_a_valid_json_line\n',
        encoding="utf-8",
    )
    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_CORRUPTED_TRACE in reason


def test_adversarial_empty_file(temp_trace_file: Path) -> None:
    """An empty trace file fails verification."""
    temp_trace_file.write_text("", encoding="utf-8")
    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_EMPTY_TRACE in reason


def test_adversarial_missing_file(tmp_path: Path) -> None:
    """A non-existent trace file fails verification."""
    non_existent = tmp_path / "does_not_exist.jsonl"
    assert verify_trace(non_existent) is False
    valid, reason = verify_trace_details(non_existent)
    assert valid is False
    assert REASON_EMPTY_TRACE in reason


def test_adversarial_unknown_raw_outcome(temp_trace_file: Path) -> None:
    """An unknown raw_outcome bucket fails verification."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "reason_code": "OK"})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["raw_outcome"] = "UNKNOWN_CUSTOM_OUTCOME"
    lines[0] = json.dumps(rec, sort_keys=True)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(temp_trace_file) is False
    valid, reason = verify_trace_details(temp_trace_file)
    assert valid is False
    assert REASON_CORRUPTED_TRACE in reason


def test_adversarial_invalid_input_record(temp_trace_file: Path) -> None:
    """Invalid input types raise TraceWriterError with INVALID_RECORD."""
    writer = TraceWriter(temp_trace_file)
    with pytest.raises(TraceWriterError) as exc_info:
        writer.write_trace("not_a_mapping")  # type: ignore[arg-type]
    assert exc_info.value.reason_code == REASON_INVALID_RECORD
