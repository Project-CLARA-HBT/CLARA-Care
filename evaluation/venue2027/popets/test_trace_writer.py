"""CLARA-Care 2027 POPETS task POPETS-traces — Unit and adversarial tests for trace_writer.

Tests cover:
- Positive controls:
  - Round-trip writing and reading of append-only trace JSONL.
  - Monotonic event ID assignment and validation.
  - Cryptographic digest chaining (prev_digest linking) and SHA-256 verification.
  - CPU/DB/model duration and cost tracking, backend labeling, oracle decision binding.
  - Sanitization of patient identifiers and PHI fields.
  - Resuming append on an existing trace file without breaking continuity.
  - Verification of the real sample artifact.
- Adversarial controls:
  - Non-monotonic event IDs refused (equal or decreasing).
  - Unsanitized PHI fields rejected fail-closed (patient_name, MRN, SSN, email, nested).
  - Corrupted trace fails verification (tampered payload, tampered digest, broken chain).
  - Swapped/out-of-order trace entries fail verification.
  - Malformed JSON lines fail verification.
  - Injected PHI lines fail verification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.venue2027.popets.trace_writer import (
    GENESIS_DIGEST,
    REASON_NON_MONOTONIC_EVENT_ID,
    REASON_UNSANITIZED_PHI_REJECTED,
    TraceRecord,
    TraceWriter,
    TraceWriterError,
    detect_phi,
    read_trace,
    sanitize_record,
    verify_trace,
    verify_trace_detailed,
    write_trace,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_ARTIFACT = (
    REPO_ROOT / "research" / "venue2027" / "proof" / "artifacts" / "popets_trace_sample.jsonl"
)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_positive_trace_writer_roundtrip(tmp_path: Path) -> None:
    """Writes valid trace JSONL, events are monotonic, sanitized, and verify successfully."""
    trace_path = tmp_path / "test_trace.jsonl"
    writer = TraceWriter(trace_path, default_backend="popets_prov_tracker")

    records = [
        {
            "raw_outcome": "ADMIT",
            "reason_code": "AUTH_GRANTED",
            "oracle_decision": {"expected_outcome": "ADMIT", "truth": "ADMIT"},
            "actual_backend": "popets_prov_tracker",
            "cpu_duration_seconds": 0.002,
            "db_duration_seconds": 0.001,
            "model_duration_seconds": 0.005,
            "cpu_cost": 0.0001,
            "db_cost": 0.00005,
            "model_cost": 0.0002,
            "case_id": "case_fresh_001",
        },
        {
            "raw_outcome": "REJECT",
            "reason_code": "REVOCATION_COMPLETE",
            "oracle_decision": {"expected_outcome": "REJECT", "truth": "REJECT"},
            "actual_backend": "popets_prov_tracker",
            "cpu_duration_seconds": 0.001,
            "db_duration_seconds": 0.0005,
            "model_duration_seconds": 0.0,
            "case_id": "case_revoked_002",
        },
        {
            "raw_outcome": "ADMIT",
            "reason_code": "CACHE_HIT",
            "oracle_decision": {"expected_outcome": "ADMIT"},
            "case_id": "case_cache_003",
        },
    ]

    digests: list[str] = []
    for r in records:
        dig = writer.append(r)
        assert len(dig) == 64
        digests.append(dig)

    # File exists and contains 3 lines
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    # Integrity verification
    assert verify_trace(trace_path) is True
    ok, defects = verify_trace_detailed(trace_path)
    assert ok is True
    assert defects == []

    # Verify content and monotonicity
    read_back = read_trace(trace_path)
    assert len(read_back) == 3
    assert [e["event_id"] for e in read_back] == [1, 2, 3]
    assert read_back[0]["prev_digest"] == GENESIS_DIGEST
    assert read_back[1]["prev_digest"] == digests[0]
    assert read_back[2]["prev_digest"] == digests[1]
    assert read_back[0]["raw_outcome"] == "ADMIT"
    assert read_back[1]["raw_outcome"] == "REJECT"
    assert read_back[1]["reason_code"] == "REVOCATION_COMPLETE"


def test_positive_auto_monotonic_event_ids(tmp_path: Path) -> None:
    """Omitting event_id automatically allocates strictly monotonic IDs."""
    trace_path = tmp_path / "auto_ids.jsonl"
    writer = TraceWriter(trace_path)

    for i in range(10):
        writer.append({"raw_outcome": "ADMIT", "seq": i})

    entries = read_trace(trace_path)
    assert len(entries) == 10
    event_ids = [e["event_id"] for e in entries]
    assert event_ids == list(range(1, 11))
    assert verify_trace(trace_path) is True


def test_positive_explicit_strictly_monotonic_event_ids(tmp_path: Path) -> None:
    """Explicitly providing strictly increasing event IDs succeeds."""
    trace_path = tmp_path / "explicit_ids.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"event_id": 10, "raw_outcome": "ADMIT"})
    writer.append({"event_id": 25, "raw_outcome": "ADMIT"})
    writer.append({"event_id": 100, "raw_outcome": "REJECT"})

    entries = read_trace(trace_path)
    assert [e["event_id"] for e in entries] == [10, 25, 100]
    assert verify_trace(trace_path) is True


def test_positive_digest_chain_continuity(tmp_path: Path) -> None:
    """Cryptographic hash chain is verified: each event binds the prior event's digest."""
    trace_path = tmp_path / "chain.jsonl"
    writer = TraceWriter(trace_path)

    d1 = writer.append({"raw_outcome": "ADMIT", "step": "register"})
    d2 = writer.append({"raw_outcome": "ADMIT", "step": "dispatch"})
    d3 = writer.append({"raw_outcome": "REJECT", "step": "probe"})

    entries = read_trace(trace_path)
    assert entries[0]["prev_digest"] == GENESIS_DIGEST
    assert entries[0]["event_digest"] == d1
    assert entries[1]["prev_digest"] == d1
    assert entries[1]["event_digest"] == d2
    assert entries[2]["prev_digest"] == d2
    assert entries[2]["event_digest"] == d3
    assert verify_trace(trace_path) is True


def test_positive_trace_resumes_cleanly(tmp_path: Path) -> None:
    """A new TraceWriter instance opened on an existing file resumes the chain seamlessly."""
    trace_path = tmp_path / "resume.jsonl"

    w1 = TraceWriter(trace_path)
    w1.append({"raw_outcome": "ADMIT", "phase": 1})
    d2 = w1.append({"raw_outcome": "ADMIT", "phase": 2})

    # Second instance reopens same path
    w2 = TraceWriter(trace_path)
    assert w2.last_event_id == 2
    assert w2.last_digest == d2

    d3 = w2.append({"raw_outcome": "REJECT", "phase": 3})
    assert w2.last_event_id == 3
    assert w2.last_digest == d3

    assert verify_trace(trace_path) is True
    entries = read_trace(trace_path)
    assert len(entries) == 3
    assert [e["event_id"] for e in entries] == [1, 2, 3]
    assert entries[2]["prev_digest"] == d2


def test_positive_sanitization_removes_and_anonymizes_phi(tmp_path: Path) -> None:
    """Sanitizing a record replaces patient identifiers with tokens and strips PHI."""
    raw = {
        "patient_id": "PATIENT-9988",
        "patient_name": "Nguyen Van A",
        "mrn": "MRN-12345",
        "email": "patient@hospital.vn",
        "raw_outcome": "ADMIT",
        "reason_code": "PROCESSED",
        "case_id": "case_sanitized_001",
    }
    assert len(detect_phi(raw)) > 0

    sanitized = sanitize_record(raw)
    assert detect_phi(sanitized) == []
    assert "patient_name" not in sanitized
    assert "mrn" not in sanitized
    assert "email" not in sanitized
    assert "patient_id" not in sanitized
    assert "subject_token" in sanitized
    assert sanitized["subject_token"].startswith("sub-")

    trace_path = tmp_path / "sanitized.jsonl"
    writer = TraceWriter(trace_path)
    writer.append(raw, sanitize=True)

    assert verify_trace(trace_path) is True
    entries = read_trace(trace_path)
    assert len(entries) == 1
    assert "patient_name" not in entries[0]
    assert entries[0]["payload"]["subject_token"].startswith("sub-")


def test_positive_trace_record_dataclass(tmp_path: Path) -> None:
    """TraceRecord dataclass instance is accepted by TraceWriter."""
    trace_path = tmp_path / "dataclass.jsonl"
    writer = TraceWriter(trace_path)

    rec = TraceRecord(
        event_id=1,
        prev_digest=GENESIS_DIGEST,
        raw_outcome="ADMIT",
        reason_code="CONSENT_RECORDED",
        oracle_decision={"status": "OK"},
        actual_backend="postgres_audit",
        cpu_duration_seconds=0.003,
        db_duration_seconds=0.002,
        model_duration_seconds=0.001,
        duration_seconds=0.006,
        cpu_cost=0.00015,
        db_cost=0.00008,
        model_cost=0.0001,
        signature_ref="sig:ed25519:sample",
    )
    dig = writer.append(rec)
    assert len(dig) == 64
    assert verify_trace(trace_path) is True


def test_positive_functional_write_trace(tmp_path: Path) -> None:
    """Functional write_trace helper appends records and returns valid digest."""
    trace_path = tmp_path / "func_trace.jsonl"
    d1 = write_trace(trace_path, {"raw_outcome": "ADMIT", "step": 1})
    d2 = write_trace(trace_path, {"raw_outcome": "REJECT", "step": 2})

    assert len(d1) == 64
    assert len(d2) == 64
    assert verify_trace(trace_path) is True


def test_positive_verify_sample_artifact() -> None:
    """Real sample artifact exists, contains valid monotonic entries, and passes verify_trace."""
    assert SAMPLE_ARTIFACT.is_file(), f"missing sample artifact at {SAMPLE_ARTIFACT}"
    assert verify_trace(SAMPLE_ARTIFACT) is True
    entries = read_trace(SAMPLE_ARTIFACT)
    assert len(entries) >= 5
    # Strict monotonicity of IDs
    eids = [e["event_id"] for e in entries]
    assert eids == sorted(eids)
    assert len(set(eids)) == len(eids)


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_adversarial_non_monotonic_event_id_equal_refused(tmp_path: Path) -> None:
    """Attempting to append an event with event_id equal to last_event_id is refused."""
    trace_path = tmp_path / "non_monotonic_equal.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"event_id": 1, "raw_outcome": "ADMIT"})
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"event_id": 1, "raw_outcome": "ADMIT"})

    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID
    assert "non-monotonic event ID refused" in str(exc_info.value)


def test_adversarial_non_monotonic_event_id_decreasing_refused(tmp_path: Path) -> None:
    """Attempting to append an event with event_id < last_event_id is refused."""
    trace_path = tmp_path / "non_monotonic_decreasing.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"event_id": 5, "raw_outcome": "ADMIT"})
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"event_id": 4, "raw_outcome": "REJECT"})

    assert exc_info.value.reason_code == REASON_NON_MONOTONIC_EVENT_ID


def test_adversarial_unsanitized_patient_name_rejected(tmp_path: Path) -> None:
    """Record containing patient_name without sanitization is rejected fail-closed."""
    trace_path = tmp_path / "phi_name.jsonl"
    writer = TraceWriter(trace_path)

    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"patient_name": "Tran Thi B", "raw_outcome": "ADMIT"})

    assert exc_info.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED
    assert "unsanitized PHI field rejected" in str(exc_info.value)


def test_adversarial_unsanitized_patient_id_rejected(tmp_path: Path) -> None:
    """Record containing patient_id without sanitization is rejected."""
    trace_path = tmp_path / "phi_id.jsonl"
    writer = TraceWriter(trace_path)

    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"patient_id": "P-00123", "raw_outcome": "ADMIT"})

    assert exc_info.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED


def test_adversarial_unsanitized_mrn_and_ssn_rejected(tmp_path: Path) -> None:
    """Records containing MRN or SSN fields are rejected fail-closed."""
    trace_path = tmp_path / "phi_identifiers.jsonl"
    writer = TraceWriter(trace_path)

    with pytest.raises(TraceWriterError) as exc_info1:
        writer.append({"mrn": "MRN-999", "raw_outcome": "ADMIT"})
    assert exc_info1.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED

    with pytest.raises(TraceWriterError) as exc_info2:
        writer.append({"ssn": "000-12-3456", "raw_outcome": "ADMIT"})
    assert exc_info2.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED


def test_adversarial_unsanitized_email_pattern_rejected(tmp_path: Path) -> None:
    """Record containing an email value even under custom key is rejected."""
    trace_path = tmp_path / "phi_email_val.jsonl"
    writer = TraceWriter(trace_path)

    with pytest.raises(TraceWriterError) as exc_info:
        writer.append({"contact_endpoint": "doctor@clinic.org", "raw_outcome": "ADMIT"})
    assert exc_info.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED


def test_adversarial_nested_phi_rejected(tmp_path: Path) -> None:
    """PHI nested deeply inside auxiliary dict or list is detected and rejected."""
    trace_path = tmp_path / "nested_phi.jsonl"
    writer = TraceWriter(trace_path)

    nested_payload = {
        "raw_outcome": "ADMIT",
        "metadata": {
            "session": {"phone": "+84901234567"},
        },
    }
    with pytest.raises(TraceWriterError) as exc_info:
        writer.append(nested_payload)
    assert exc_info.value.reason_code == REASON_UNSANITIZED_PHI_REJECTED


def test_adversarial_corrupted_payload_fails_verification(tmp_path: Path) -> None:
    """Modifying a field in the trace JSONL file causes verify_trace to fail."""
    trace_path = tmp_path / "tamper_payload.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"raw_outcome": "REJECT", "reason_code": "REVOKED"})
    writer.append({"raw_outcome": "REJECT", "reason_code": "REVOKED"})

    # Tamper with outcome in the first line
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    corrupt_line = json.loads(lines[0])
    corrupt_line["raw_outcome"] = "ADMIT"  # Tampered: REJECT -> ADMIT
    lines[0] = json.dumps(corrupt_line)
    trace_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(trace_path) is False
    ok, defects = verify_trace_detailed(trace_path)
    assert ok is False
    assert any("digest mismatch" in d for d in defects)


def test_adversarial_corrupted_event_digest_fails_verification(tmp_path: Path) -> None:
    """Tampering with event_digest causes verify_trace to fail."""
    trace_path = tmp_path / "tamper_digest.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"raw_outcome": "ADMIT"})
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    corrupt_line = json.loads(lines[0])
    corrupt_line["event_digest"] = "f" * 64  # Fake digest
    trace_path.write_text(json.dumps(corrupt_line) + "\n", encoding="utf-8")

    assert verify_trace(trace_path) is False


def test_adversarial_broken_digest_chain_fails_verification(tmp_path: Path) -> None:
    """Tampering with prev_digest breaks the hash chain and causes verify_trace to fail."""
    trace_path = tmp_path / "chain_break.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"raw_outcome": "ADMIT"})
    writer.append({"raw_outcome": "ADMIT"})

    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    line2 = json.loads(lines[1])
    line2["prev_digest"] = "e" * 64  # Broken link
    # Recompute digest for line2 to isolate prev_digest mismatch defect
    from evaluation.venue2027.popets.trace_writer import compute_event_digest

    line2["event_digest"] = compute_event_digest(line2)
    lines[1] = json.dumps(line2)
    trace_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_trace(trace_path) is False
    ok, defects = verify_trace_detailed(trace_path)
    assert ok is False
    assert any("broken digest chain" in d for d in defects)


def test_adversarial_swapped_lines_fail_verification(tmp_path: Path) -> None:
    """Swapping lines in the trace violates monotonicity and chain integrity."""
    trace_path = tmp_path / "swapped.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"raw_outcome": "ADMIT", "step": 1})
    writer.append({"raw_outcome": "ADMIT", "step": 2})

    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    # Swap lines 0 and 1
    swapped = [lines[1], lines[0]]
    trace_path.write_text("\n".join(swapped) + "\n", encoding="utf-8")

    assert verify_trace(trace_path) is False
    ok, defects = verify_trace_detailed(trace_path)
    assert ok is False
    assert any("non-monotonic" in d or "broken digest chain" in d for d in defects)


def test_adversarial_malformed_json_fails_verification(tmp_path: Path) -> None:
    """A trace containing a non-JSON corrupted line fails verification."""
    trace_path = tmp_path / "malformed.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"raw_outcome": "ADMIT"})
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write("NOT_VALID_JSON{{{corrupt\n")

    assert verify_trace(trace_path) is False


def test_adversarial_injected_phi_in_trace_fails_verification(tmp_path: Path) -> None:
    """If an existing trace file contains injected PHI, verify_trace fails."""
    trace_path = tmp_path / "injected_phi.jsonl"
    writer = TraceWriter(trace_path)

    writer.append({"raw_outcome": "ADMIT"})

    # Tamper by injecting patient_name and recalculating digest
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(lines[0])
    entry["patient_name"] = "Alice Injected"
    from evaluation.venue2027.popets.trace_writer import compute_event_digest

    entry["event_digest"] = compute_event_digest(entry)
    trace_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    assert verify_trace(trace_path) is False
    ok, defects = verify_trace_detailed(trace_path)
    assert ok is False
    assert any("unsanitized PHI" in d for d in defects)


def test_adversarial_empty_file_fails_verification(tmp_path: Path) -> None:
    """Empty trace file fails verification (no verifiable evidence)."""
    empty_path = tmp_path / "empty.jsonl"
    empty_path.touch()
    assert verify_trace(empty_path) is False


def test_adversarial_missing_file_fails_verification(tmp_path: Path) -> None:
    """Non-existent file fails verification."""
    missing_path = tmp_path / "non_existent.jsonl"
    assert verify_trace(missing_path) is False
