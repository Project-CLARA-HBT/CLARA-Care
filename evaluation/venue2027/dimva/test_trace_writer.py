"""Tests for DIMVA-traces — Immutable trace and measurement capture (Phase P05, venue dimva).

Validates:
- Target contract: write_trace(event) -> sha256.
- Strictly monotonic event IDs (auto-increment and explicit sequence).
- Score range [0, 1] enforcement and validation.
- Cryptographic hash chain (prev_digest, payload_digest, entry_digest).
- CPU/DB duration and cost metrics tracking.
- Positive control: round-trip trace output matches source events.
- Positive control: harness pair_result adapter support.
- Positive control: file resumption and append mode.
- Sanitization: recursive redaction of credentials, secrets, and PHI.
- Adversarial control: tamper detection on outcome, score, decision, reason, durations, payload.
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

from evaluation.venue2027.dimva.trace_writer import (
    DEFAULT_TRACE_PATH,
    GENESIS_PREV_DIGEST,
    REASON_CHAIN_INTEGRITY_BROKEN,
    REASON_CORRUPTED_TRACE,
    REASON_CREDENTIAL_LEAK_DETECTED,
    REASON_EMPTY_TRACE,
    REASON_INVALID_RECORD,
    REASON_NON_MONOTONIC_EVENT_ID,
    REASON_PHI_LEAK_DETECTED,
    REASON_SCORE_OUT_OF_RANGE,
    REASON_TAMPER_DETECTED,
    TraceEvent,
    TraceWriter,
    TraceWriterError,
    detect_sensitive_leak,
    read_trace,
    sanitize_sensitive_data,
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
        "raw_outcome": "REJECT",
        "detector_score": 0.85,
        "detection_decision": "DETECT",
        "reason_code": "CAMPAIGN_STRUCTURE_DETECTED",
        "oracle_decision": {"expected_outcome": "ADMIT", "truth_label": "ATTACK"},
        "actual_backend": "candidate",
        "duration_seconds": 0.0015,
        "cpu_duration_seconds": 0.0012,
        "db_duration_seconds": 0.0003,
        "cpu_cost": 0.00001,
        "db_cost": 0.000005,
        "payload": {"case_id": "case-01-probe", "actor_id": "actor_test"},
    }
    digest = write_trace(event, trace_path=temp_trace_file)

    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert temp_trace_file.is_file()
    assert verify_trace(temp_trace_file) is True


def test_monotonic_event_ids_auto_increment(temp_trace_file: Path) -> None:
    """Consecutive writes produce strictly increasing monotonic event_ids starting at 1."""
    writer = TraceWriter(temp_trace_file, actual_backend="candidate")
    digests = [
        writer.write_trace(
            {"raw_outcome": "ADMIT", "detector_score": 0.1, "reason_code": "NO_ALARM"}
        ),
        writer.write_trace(
            {"raw_outcome": "REJECT", "detector_score": 0.9, "reason_code": "CAMPAIGN_DETECTED"}
        ),
        writer.write_trace(
            {"raw_outcome": "INDETERMINATE", "detector_score": 0.0, "reason_code": "MALFORMED"}
        ),
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


def test_monotonic_event_ids_explicit(temp_trace_file: Path) -> None:
    """Explicitly provided monotonic event_ids are preserved if strictly increasing."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"event_id": 10, "raw_outcome": "ADMIT", "detector_score": 0.2})
    writer.write_trace({"event_id": 25, "raw_outcome": "REJECT", "detector_score": 0.7})
    writer.write_trace({"event_id": 50, "raw_outcome": "ADMIT", "detector_score": 0.3})

    records = read_trace(temp_trace_file)
    assert [r["event_id"] for r in records] == [10, 25, 50]
    assert verify_trace(temp_trace_file) is True


def test_score_range_valid_boundaries(temp_trace_file: Path) -> None:
    """Boundary scores 0.0, 1.0, and intermediate values are valid."""
    writer = TraceWriter(temp_trace_file)
    for score in (0.0, 0.000001, 0.5, 0.999999, 1.0):
        writer.write_trace({"raw_outcome": "ADMIT", "detector_score": score})

    records = read_trace(temp_trace_file)
    assert len(records) == 5
    assert records[0]["detector_score"] == 0.0
    assert records[-1]["detector_score"] == 1.0
    assert verify_trace(temp_trace_file) is True


def test_score_extraction_from_detail(temp_trace_file: Path) -> None:
    """Detector score and reason are extracted from detail string if not explicitly given."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {
            "raw_outcome": "REJECT",
            "detail": "CAMPAIGN_STRUCTURE_DETECTED|score=0.876543",
        }
    )

    records = read_trace(temp_trace_file)
    assert len(records) == 1
    assert records[0]["detector_score"] == pytest.approx(0.876543)
    assert records[0]["reason_code"] == "CAMPAIGN_STRUCTURE_DETECTED"
    assert records[0]["detection_decision"] == "DETECT"
    assert verify_trace(temp_trace_file) is True


def test_round_trip_matches_source_events(temp_trace_file: Path) -> None:
    """Round-trip trace output faithfully matches source events and preserves all fields."""
    events = [
        TraceEvent(
            raw_outcome="ADMIT",
            detector_score=0.05,
            detection_decision="NO_DETECT",
            reason_code="NO_ALARM",
            oracle_decision={"expected_outcome": "REJECT", "truth_label": "BENIGN"},
            actual_backend="candidate",
            duration_seconds=0.0012,
            cpu_duration_seconds=0.001,
            db_duration_seconds=0.0002,
            model_duration_seconds=0.0,
            cpu_cost=0.00001,
            db_cost=0.000002,
            model_cost_usd=0.0,
            signature_refs={"sig_id": "sig-01"},
            payload={"case_id": "case-round-trip-1", "tool": "read_records"},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            detector_score=0.92,
            detection_decision="DETECT",
            reason_code="CAMPAIGN_STRUCTURE_DETECTED",
            oracle_decision={"expected_outcome": "ADMIT", "truth_label": "ATTACK"},
            actual_backend="B3",
            duration_seconds=0.0025,
            cpu_duration_seconds=0.002,
            db_duration_seconds=0.0005,
            model_duration_seconds=0.0,
            cpu_cost=0.00002,
            db_cost=0.000005,
            model_cost_usd=0.0,
            signature_refs={"sig_id": "sig-02"},
            payload={"case_id": "case-round-trip-2", "denials": 9},
        ),
    ]

    for ev in events:
        write_trace(ev, trace_path=temp_trace_file)

    records = read_trace(temp_trace_file)
    assert len(records) == 2

    r0 = records[0]
    assert r0["event_id"] == 1
    assert r0["raw_outcome"] == "ADMIT"
    assert r0["detector_score"] == pytest.approx(0.05)
    assert r0["detection_decision"] == "NO_DETECT"
    assert r0["reason_code"] == "NO_ALARM"
    assert r0["actual_backend"] == "candidate"
    assert r0["duration_cost"]["cpu_duration_seconds"] == pytest.approx(0.001)
    assert r0["payload"]["case_id"] == "case-round-trip-1"

    r1 = records[1]
    assert r1["event_id"] == 2
    assert r1["raw_outcome"] == "REJECT"
    assert r1["detector_score"] == pytest.approx(0.92)
    assert r1["detection_decision"] == "DETECT"
    assert r1["reason_code"] == "CAMPAIGN_STRUCTURE_DETECTED"
    assert r1["actual_backend"] == "B3"

    assert verify_trace(temp_trace_file) is True


def test_harness_pair_result_adapter(temp_trace_file: Path) -> None:
    """Harness pair_result dictionary format is cleanly adapted."""
    pair_result = {
        "record_kind": "pair_result",
        "logical_op_id": "DIMVA-campaign:candidate::case-100",
        "campaign_id": "DIMVA-campaign",
        "arm_id": "candidate",
        "case_id": "case-100",
        "seed": 42,
        "source_commit": "08dbda2900c97a208b3228639f51998db833bb60",
        "outcome": {
            "observed_outcome": "REJECT",
            "counted_as_success": True,
            "retriable": False,
            "detail": "CAMPAIGN_STRUCTURE_DETECTED|score=0.880000",
        },
        "oracle": {
            "expected_outcome": "ADMIT",
            "truth_label": "ATTACK",
            "scenario_family": "low_and_slow",
        },
        "duration_seconds": 0.003456,
        "cpu_duration_seconds": 0.003100,
        "pair_digest": "a" * 64,
    }

    digest = write_trace(pair_result, trace_path=temp_trace_file)
    assert len(digest) == 64

    records = read_trace(temp_trace_file)
    assert len(records) == 1
    r = records[0]
    assert r["raw_outcome"] == "REJECT"
    assert r["detector_score"] == pytest.approx(0.88)
    assert r["detection_decision"] == "DETECT"
    assert r["reason_code"] == "CAMPAIGN_STRUCTURE_DETECTED"
    assert r["actual_backend"] == "candidate"
    assert r["oracle_decision"]["truth_label"] == "ATTACK"
    assert r["signature_refs"]["pair_digest"] == "a" * 64
    assert r["duration_cost"]["duration_seconds"] == pytest.approx(0.003456)
    assert verify_trace(temp_trace_file) is True


def test_resumption_and_append_mode(temp_trace_file: Path) -> None:
    """Writer re-initializes from existing trace file without corrupting monotonicity or chain."""
    writer1 = TraceWriter(temp_trace_file, actual_backend="candidate")
    writer1.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.1})
    writer1.write_trace({"raw_outcome": "REJECT", "detector_score": 0.8})

    writer2 = TraceWriter(temp_trace_file, actual_backend="candidate")
    assert writer2.last_event_id == 2
    writer2.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.2})

    records = read_trace(temp_trace_file)
    assert len(records) == 3
    assert [r["event_id"] for r in records] == [1, 2, 3]
    assert verify_trace(temp_trace_file) is True


def test_sanitization_redacts_credentials_and_phi(temp_trace_file: Path) -> None:
    """Credentials, tokens, API keys, and PHI in event data are scrubbed before writing."""
    event = {
        "raw_outcome": "ADMIT",
        "detector_score": 0.15,
        "reason_code": "NO_ALARM",
        "payload": {
            "api_key": "sk-1234567890abcdef123456",
            "password": "supersecretpassword123",
            "token": "ghp_abcdefghijklmnopqrstuvwxyz1234",
            "patient_name": "Nguyen Van A",
            "ssn": "123-45-6789",
            "email": "patient@hospital.vn",
            "phone": "+84-90-123-4567",
            "nested": {
                "secret_key": "nested-secret-key-val",
                "dob": "1980-01-01",
                "note": "Authorization: Bearer my-secret-bearer-token-12345",
            },
        },
    }

    write_trace(event, trace_path=temp_trace_file)
    records = read_trace(temp_trace_file)
    assert len(records) == 1
    p = records[0]["payload"]

    assert p["api_key"] == "[REDACTED_CREDENTIAL]"
    assert p["password"] == "[REDACTED_CREDENTIAL]"
    assert p["token"] == "[REDACTED_CREDENTIAL]"
    assert p["patient_name"] == "[REDACTED_PHI]"
    assert p["ssn"] == "[REDACTED_PHI]"
    assert p["email"] == "[REDACTED_PHI]"
    assert p["phone"] == "[REDACTED_PHI]"
    assert p["nested"]["secret_key"] == "[REDACTED_CREDENTIAL]"
    assert p["nested"]["dob"] == "[REDACTED_PHI]"
    assert "my-secret-bearer-token-12345" not in p["nested"]["note"]

    # File must pass verification because everything was sanitized
    assert verify_trace(temp_trace_file) is True


def test_detect_sensitive_leak_utility() -> None:
    """Direct verification of sensitive leak detector."""
    clean_data = {"tool": "search", "actor": "agent-1", "count": 5}
    assert detect_sensitive_leak(clean_data) == []

    credential_data = {"api_key": "unredacted-key-1234"}
    leaks = detect_sensitive_leak(credential_data)
    assert len(leaks) >= 1
    assert "CREDENTIAL_LEAK" in leaks[0]

    phi_data = {"patient_name": "Tran Van B"}
    leaks_phi = detect_sensitive_leak(phi_data)
    assert len(leaks_phi) >= 1
    assert "PHI_LEAK" in leaks_phi[0]


def test_sanitize_sensitive_data_direct() -> None:
    """Direct unit testing of recursive sanitizer."""
    raw = {
        "actor": "agent-1",
        "secret": "topsecret",
        "phone_number": "555-123-4567",
        "notes": ["ok", "contact: user@example.com"],
    }
    sanitized = sanitize_sensitive_data(raw)
    assert sanitized["secret"] == "[REDACTED_CREDENTIAL]"
    assert sanitized["phone_number"] == "[REDACTED_PHI]"
    assert "[REDACTED_PHI]" in sanitized["notes"][1]


def test_sample_artifact_verifies() -> None:
    """The real sample artifact in proof/artifacts exists and passes full verification."""
    assert SAMPLE_ARTIFACT.is_file(), f"Sample artifact missing at {SAMPLE_ARTIFACT}"
    assert verify_trace(SAMPLE_ARTIFACT) is True

    records = read_trace(SAMPLE_ARTIFACT)
    assert len(records) >= 5
    for r in records:
        assert 0.0 <= r["detector_score"] <= 1.0
        assert r["raw_outcome"] in ("ADMIT", "REJECT", "INDETERMINATE")


# ==============================================================================
# Adversarial Controls: Monotonicity
# ==============================================================================


def test_adversarial_non_monotonic_explicit_id(temp_trace_file: Path) -> None:
    """Explicit event_id <= last_event_id is rejected fail-closed with NON_MONOTONIC_EVENT_ID."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"event_id": 5, "raw_outcome": "ADMIT", "detector_score": 0.1})

    # Same ID
    with pytest.raises(TraceWriterError) as exc_info:
        writer.write_trace({"event_id": 5, "raw_outcome": "ADMIT", "detector_score": 0.1})
    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID

    # Decreasing ID
    with pytest.raises(TraceWriterError) as exc_info2:
        writer.write_trace({"event_id": 3, "raw_outcome": "ADMIT", "detector_score": 0.1})
    assert exc_info2.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID


def test_adversarial_tamper_event_id_in_file(temp_trace_file: Path) -> None:
    """Tampering with event_id ordering in trace file causes verify_trace to fail."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.1})
    writer.write_trace({"raw_outcome": "REJECT", "detector_score": 0.8})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec2 = json.loads(lines[1])
    rec2["event_id"] = 1  # Make non-monotonic (1, 1)
    lines[1] = json.dumps(rec2)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_NON_MONOTONIC_EVENT_ID in reason


# ==============================================================================
# Adversarial Controls: Score Range [0, 1]
# ==============================================================================


@pytest.mark.parametrize(
    "invalid_score", [-0.001, -1.0, 1.0001, 2.5, float("nan"), float("inf"), True, False, "high"]
)
def test_adversarial_score_out_of_range_raises(
    temp_trace_file: Path, invalid_score: object
) -> None:
    """detector_score outside [0.0, 1.0], NaN, Inf, bool, or non-numeric raises SCORE_OUT_OF_RANGE."""
    writer = TraceWriter(temp_trace_file)
    with pytest.raises(TraceWriterError) as exc_info:
        writer.write_trace({"raw_outcome": "ADMIT", "detector_score": invalid_score})
    assert exc_info.value.reason_code == REASON_SCORE_OUT_OF_RANGE


def test_adversarial_tamper_score_in_file_out_of_range(temp_trace_file: Path) -> None:
    """Tampering a score in the trace file to be outside [0.0, 1.0] causes verify_trace to fail."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.5})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["detector_score"] = 1.5  # Tamper to > 1.0
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_SCORE_OUT_OF_RANGE in reason


# ==============================================================================
# Adversarial Controls: Tamper Detection
# ==============================================================================


def test_adversarial_tamper_raw_outcome(temp_trace_file: Path) -> None:
    """Modifying raw_outcome without recomputing entry digest triggers TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.1})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["raw_outcome"] = "REJECT"  # Tamper
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_detector_score_in_range(temp_trace_file: Path) -> None:
    """Modifying detector_score (even within [0, 1]) triggers TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.1})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["detector_score"] = 0.9  # Valid range, but tampered
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_detection_decision(temp_trace_file: Path) -> None:
    """Modifying detection_decision triggers TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {"raw_outcome": "ADMIT", "detection_decision": "NO_DETECT", "detector_score": 0.1}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["detection_decision"] = "DETECT"  # Tamper
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_payload(temp_trace_file: Path) -> None:
    """Modifying a payload field triggers TAMPER_DETECTED (payload digest mismatch)."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {
            "raw_outcome": "REJECT",
            "detector_score": 0.8,
            "payload": {"case_id": "original_case_id"},
        }
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["case_id"] = "tampered_case_id"
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_durations(temp_trace_file: Path) -> None:
    """Modifying duration_cost metrics triggers TAMPER_DETECTED."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace(
        {"raw_outcome": "ADMIT", "detector_score": 0.1, "cpu_duration_seconds": 0.001}
    )

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["duration_cost"]["cpu_duration_seconds"] = 999.0
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_TAMPER_DETECTED in reason


def test_adversarial_tamper_broken_hash_chain(temp_trace_file: Path) -> None:
    """Modifying prev_digest on second record triggers CHAIN_INTEGRITY_BROKEN."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.1})
    writer.write_trace({"raw_outcome": "REJECT", "detector_score": 0.8})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec2 = json.loads(lines[1])
    rec2["digest_refs"]["prev_digest"] = "f" * 64  # Break chain link
    lines[1] = json.dumps(rec2)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_CHAIN_INTEGRITY_BROKEN in reason


# ==============================================================================
# Adversarial Controls: Sanitization & Leak Detection
# ==============================================================================


def test_adversarial_credential_leak_blocks_verification(temp_trace_file: Path) -> None:
    """Unredacted credentials in a trace file cause verify_trace to fail."""
    writer = TraceWriter(temp_trace_file)
    # Write with sanitize=False to simulate an adversarial or buggy bypass
    writer.write_trace(
        {
            "raw_outcome": "ADMIT",
            "detector_score": 0.1,
            "payload": {"api_key": "sk-adversarial-leak-key-12345"},
        },
        sanitize=False,
    )

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_CREDENTIAL_LEAK_DETECTED in reason


def test_adversarial_phi_leak_blocks_verification(temp_trace_file: Path) -> None:
    """Unredacted PHI (patient SSN, MRN, phone) causes verify_trace to fail."""
    writer = TraceWriter(temp_trace_file)
    # Write with sanitize=False
    writer.write_trace(
        {
            "raw_outcome": "ADMIT",
            "detector_score": 0.1,
            "payload": {"patient_name": "Nguyen Van A", "mrn": "MRN-99999"},
        },
        sanitize=False,
    )

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert (REASON_PHI_LEAK_DETECTED in reason) or (REASON_CREDENTIAL_LEAK_DETECTED in reason)


# ==============================================================================
# Adversarial Controls: File Structure & Corruptions
# ==============================================================================


def test_adversarial_empty_file(tmp_path: Path) -> None:
    """Empty trace file returns False with EMPTY_TRACE."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.touch()

    is_valid, reason = verify_trace_details(empty_file)
    assert is_valid is False
    assert REASON_EMPTY_TRACE in reason
    assert verify_trace(empty_file) is False


def test_adversarial_nonexistent_file(tmp_path: Path) -> None:
    """Nonexistent trace file returns False with EMPTY_TRACE."""
    missing_file = tmp_path / "missing.jsonl"
    is_valid, reason = verify_trace_details(missing_file)
    assert is_valid is False
    assert REASON_EMPTY_TRACE in reason
    assert verify_trace(missing_file) is False


def test_adversarial_corrupted_json(temp_trace_file: Path) -> None:
    """Non-JSON content in trace file returns False with CORRUPTED_TRACE."""
    temp_trace_file.write_text("NOT_JSON_LINE\n", encoding="utf-8")
    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_CORRUPTED_TRACE in reason
    assert verify_trace(temp_trace_file) is False


def test_adversarial_missing_required_field(temp_trace_file: Path) -> None:
    """Record missing required field returns False with CORRUPTED_TRACE."""
    writer = TraceWriter(temp_trace_file)
    writer.write_trace({"raw_outcome": "ADMIT", "detector_score": 0.1})

    lines = temp_trace_file.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    del rec["detector_score"]  # Remove required field
    lines[0] = json.dumps(rec)
    temp_trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, reason = verify_trace_details(temp_trace_file)
    assert is_valid is False
    assert REASON_CORRUPTED_TRACE in reason


def test_adversarial_invalid_record_type(temp_trace_file: Path) -> None:
    """Invalid event type raises TraceWriterError(INVALID_RECORD)."""
    with pytest.raises(TraceWriterError) as exc_info:
        write_trace("NOT_AN_EVENT_OR_PATH", record_or_path=None, trace_path=temp_trace_file)
    assert exc_info.value.reason_code == REASON_INVALID_RECORD
