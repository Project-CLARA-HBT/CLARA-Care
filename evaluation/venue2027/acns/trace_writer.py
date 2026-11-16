"""ACNS-traces — Immutable trace and measurement capture for ACNS 2027 SoK.

Purpose
-------
Task ACNS-traces (Phase P05, venue acns) delivers the append-only JSONL trace writer
and verification engine for the study "SoK: Evidence Boundaries of Attestation in
Tool-Using AI Systems" (research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md, RQ1-RQ3).

Per the task specification (research/venue2027/VENUES/acns/TASKS/ACNS-traces.md):
- Implements the exact target contract: `write_trace(event) -> sha256`.
- Append-only JSONL recording with:
  * strictly monotonic event IDs (integer sequence >= 1)
  * raw outcome (from canonical OUTCOME_BUCKETS)
  * reason code (stable uppercase reason code)
  * independent oracle decision
  * evidence gap code (from pre-registered ACNS gap register G1-G9 or "none")
  * signature and digest references (payload digest, cryptographic hash chain)
  * CPU, DB, and model duration/cost metrics
  * actual backend identifier
  * leak-safe sensitive content sanitization (PII, tokens, credentials, keys)
- Implements `verify_trace(trace_path) -> bool` for tamper, monotonicity, and leak detection.

Allowed input
-------------
`event`: A mapping or `TraceEvent` carrying event telemetry. Standard fields:
`raw_outcome`, `reason_code`, `oracle_decision`, `evidence_gap_code`, `actual_backend`,
`duration_seconds`, `cpu_duration_seconds`, `db_duration_seconds`,
`model_duration_seconds`, `model_cost_usd`, `signature_refs`, and `payload` (or `detail`).
Harness `pair_result` dictionaries from `evaluation.venue2027._shared.harness` are
directly accepted and mapped automatically.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- `INVALID_EVENT` — event is not a mapping or cannot be serialized.
- `CORRUPTED_TRACE` — trace file contains non-JSON lines or missing required fields.
- `NON_MONOTONIC_EVENT_ID` — event ID sequence is not strictly increasing.
- `TAMPER_DETECTED` — record digest or payload hash does not match content.
- `CHAIN_INTEGRITY_BROKEN` — prev_digest chain link does not match previous entry digest.
- `CREDENTIAL_LEAK_DETECTED` — unredacted credential or PII pattern discovered in trace.
- `EMPTY_TRACE` — trace file is empty or does not exist.

Version
-------
`ACNS_TRACE_WRITER_VERSION = "1.0.0"`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ACNS_TRACE_WRITER_VERSION: Final[str] = "1.0.0"

GENESIS_PREV_DIGEST: Final[str] = "0" * 64
DEFAULT_TRACE_PATH: Final[Path] = Path("research/venue2027/proof/artifacts/acns_trace_sample.jsonl")

#: Canonical outcome buckets from shared harness (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4).
ALLOWED_OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        "ADMIT",
        "REJECT",
        "INDETERMINATE",
        "TIMEOUT",
        "EXECUTION_ERROR",
        "NOT_RUN_EXTERNAL",
        "INVALID_RESULT",
    }
)

#: Pre-registered ACNS evidence gap codes (threat model §6 register G1-G9) + "none".
VALID_GAP_CODES: Final[frozenset[str]] = frozenset(
    {
        "none",
        "G1_TRANSPORT_ACK_AS_PROCESSING",
        "G2_RECEIPT_AS_EXECUTION",
        "G3_EXECUTION_AS_CONSUMPTION",
        "G4_SIGNATURE_AS_CONTEXT",
        "G5_MINT_TIME_AS_RELY_TIME",
        "G6_TIMESTAMP_AS_ORDERING",
        "G7_LEVEL_IMPLICIT_UPGRADE",
        "G8_AUTHORITY_SCOPE_CROSSING",
        "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
    }
)

# Sensitive dictionary keys to scrub (PII and credentials).
_CREDENTIAL_KEY_DENYLIST: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secret_key",
        "client_secret",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "auth_token",
        "bearer",
        "bearer_token",
        "private_key",
        "credential",
        "credentials",
        "authorization",
        "session_token",
        "cookie",
        "cookies",
    }
)

_PII_KEY_DENYLIST: Final[frozenset[str]] = frozenset(
    {
        "ssn",
        "social_security_number",
        "citizen_id",
        "national_id",
        "cmnd",
        "cccd",
        "identity_card",
        "passport",
        "so_ho_chieu",
        "mrn",
        "patient_name",
        "patient_id",
        "full_name",
        "first_name",
        "last_name",
        "phone",
        "phone_number",
        "so_dien_thoai",
        "email",
        "home_address",
        "address",
        "dia_chi",
        "date_of_birth",
        "dob",
        "birth_date",
        "birthdate",
        "bank_account",
        "credit_card",
    }
)

# Regex patterns for credential leak detection and sanitization.
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_API_KEY_PATTERN = re.compile(r"(?:sk|pk|ghp|key|api)-[A-Za-z0-9_\-]{16,}", re.IGNORECASE)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN[ A-Z_-]*PRIVATE KEY-----.*?-----END[ A-Z_-]*PRIVATE KEY-----", re.DOTALL
)
_CREDENTIAL_KV_PATTERN = re.compile(
    r"(?:password|secret|api_key|access_token|auth_token)\s*[:=]\s*['\"]?([^\s'\";,}]+)",
    re.IGNORECASE,
)

# Regex patterns for PII leak detection and sanitization.
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_LONG_DIGIT_PHONE_PATTERN = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)


class TraceWriterError(ValueError):
    """Stable, machine-readable trace writer error."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def canonical_json(data: Any) -> str:
    """Format data as deterministic, sorted, whitespace-compact JSON."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sanitize_sensitive_data(value: Any) -> Any:
    """Recursively scrub credentials and PII from mappings, lists, and strings.

    Replaces identified credentials with '[REDACTED_CREDENTIAL]' and PII with '[REDACTED_PII]'.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_k, raw_v in value.items():
            k_norm = str(raw_k).strip().lower()
            if k_norm in _CREDENTIAL_KEY_DENYLIST:
                sanitized[str(raw_k)] = "[REDACTED_CREDENTIAL]"
            elif k_norm in _PII_KEY_DENYLIST:
                sanitized[str(raw_k)] = "[REDACTED_PII]"
            else:
                sanitized[str(raw_k)] = sanitize_sensitive_data(raw_v)
        return sanitized

    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [sanitize_sensitive_data(item) for item in value]

    if isinstance(value, str):
        # Do not re-scrub if already redacted token
        if value in ("[REDACTED_CREDENTIAL]", "[REDACTED_PII]", "[REDACTED]"):
            return value

        cleaned = value
        # Private key blocks
        if _PRIVATE_KEY_PATTERN.search(cleaned):
            cleaned = _PRIVATE_KEY_PATTERN.sub("[REDACTED_CREDENTIAL]", cleaned)
        # Bearer tokens
        if _BEARER_PATTERN.search(cleaned):
            cleaned = _BEARER_PATTERN.sub("Bearer [REDACTED_CREDENTIAL]", cleaned)
        # API keys
        if _API_KEY_PATTERN.search(cleaned):
            cleaned = _API_KEY_PATTERN.sub("[REDACTED_CREDENTIAL]", cleaned)
        # Credential key-value assignments
        if _CREDENTIAL_KV_PATTERN.search(cleaned):
            cleaned = _CREDENTIAL_KV_PATTERN.sub(
                lambda m: m.group(0).replace(m.group(1), "[REDACTED_CREDENTIAL]"), cleaned
            )
        # SSN
        if _SSN_PATTERN.search(cleaned):
            cleaned = _SSN_PATTERN.sub("[REDACTED_PII]", cleaned)
        # Credit cards
        if _CREDIT_CARD_PATTERN.search(cleaned):
            cleaned = _CREDIT_CARD_PATTERN.sub("[REDACTED_PII]", cleaned)
        # Emails
        if _EMAIL_PATTERN.search(cleaned):
            cleaned = _EMAIL_PATTERN.sub("[REDACTED_PII]", cleaned)
        # Phone numbers
        if _LONG_DIGIT_PHONE_PATTERN.search(cleaned):
            cleaned = _LONG_DIGIT_PHONE_PATTERN.sub("[REDACTED_PII]", cleaned)

        return cleaned

    return value


def detect_sensitive_leak(value: Any, path: str = "") -> list[str]:
    """Inspect a record for any unredacted credential or PII marker.

    Returns a list of leak descriptions if any found; empty list if clean.
    """
    leaks: list[str] = []

    if isinstance(value, Mapping):
        for raw_k, raw_v in value.items():
            k_str = str(raw_k)
            k_norm = k_str.strip().lower()
            current_path = f"{path}.{k_str}" if path else k_str

            # Check if key is sensitive denylist and value is not properly redacted
            if k_norm in _CREDENTIAL_KEY_DENYLIST:
                if not (isinstance(raw_v, str) and raw_v.startswith("[REDACTED")):
                    leaks.append(f"CREDENTIAL_LEAK at key '{current_path}'")
            elif k_norm in _PII_KEY_DENYLIST:
                if not (isinstance(raw_v, str) and raw_v.startswith("[REDACTED")):
                    leaks.append(f"PII_LEAK at key '{current_path}'")
            else:
                leaks.extend(detect_sensitive_leak(raw_v, current_path))
        return leaks

    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for idx, item in enumerate(value):
            leaks.extend(detect_sensitive_leak(item, f"{path}[{idx}]"))
        return leaks

    if isinstance(value, str):
        if value.startswith("[REDACTED"):
            return leaks

        if _PRIVATE_KEY_PATTERN.search(value):
            leaks.append(f"CREDENTIAL_LEAK at '{path}': matches private key pattern")
        elif _BEARER_PATTERN.search(value) and "Bearer [REDACTED" not in value:
            leaks.append(f"CREDENTIAL_LEAK at '{path}': matches bearer token pattern")
        elif _API_KEY_PATTERN.search(value):
            leaks.append(f"CREDENTIAL_LEAK at '{path}': matches API key pattern")
        elif _CREDENTIAL_KV_PATTERN.search(value):
            leaks.append(f"CREDENTIAL_LEAK at '{path}': matches credential assignment pattern")
        elif _SSN_PATTERN.search(value):
            leaks.append(f"PII_LEAK at '{path}': matches SSN pattern")
        elif _CREDIT_CARD_PATTERN.search(value):
            leaks.append(f"PII_LEAK at '{path}': matches credit card pattern")
        elif _EMAIL_PATTERN.search(value):
            leaks.append(f"PII_LEAK at '{path}': matches email pattern")
        elif _LONG_DIGIT_PHONE_PATTERN.search(value):
            leaks.append(f"PII_LEAK at '{path}': matches phone number pattern")

    return leaks


@dataclasses.dataclass(frozen=True)
class TraceEvent:
    """Input event to record in the append-only trace."""

    raw_outcome: str = "INDETERMINATE"
    reason_code: str = "OK"
    oracle_decision: str = "NONE"
    evidence_gap_code: str = "none"
    actual_backend: str = "local_deterministic"
    duration_seconds: float = 0.0
    cpu_duration_seconds: float = 0.0
    db_duration_seconds: float = 0.0
    model_duration_seconds: float = 0.0
    model_cost_usd: float = 0.0
    signature_refs: dict[str, Any] = dataclasses.field(default_factory=dict)
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_outcome": self.raw_outcome,
            "reason_code": self.reason_code,
            "oracle_decision": self.oracle_decision,
            "evidence_gap_code": self.evidence_gap_code,
            "actual_backend": self.actual_backend,
            "duration_seconds": self.duration_seconds,
            "cpu_duration_seconds": self.cpu_duration_seconds,
            "db_duration_seconds": self.db_duration_seconds,
            "model_duration_seconds": self.model_duration_seconds,
            "model_cost_usd": self.model_cost_usd,
            "signature_refs": self.signature_refs,
            "payload": self.payload,
        }


def _normalize_event(event: Mapping[str, Any] | TraceEvent) -> dict[str, Any]:
    """Normalize event mapping or dataclass to standardized sanitized fields."""
    if isinstance(event, TraceEvent):
        raw = event.to_dict()
    elif isinstance(event, Mapping):
        raw = dict(event)
    else:
        raise TraceWriterError(
            "INVALID_EVENT", f"Expected Mapping or TraceEvent, got {type(event).__name__}"
        )

    # Extract outcome
    outcome = (
        raw.get("raw_outcome")
        or raw.get("observed_outcome")
        or (
            raw.get("outcome", {}).get("observed_outcome")
            if isinstance(raw.get("outcome"), Mapping)
            else None
        )
        or raw.get("outcome")
        or "INDETERMINATE"
    )
    if isinstance(outcome, str):
        outcome = outcome.strip().upper()
    else:
        outcome = "INDETERMINATE"
    if outcome not in ALLOWED_OUTCOMES:
        outcome = "INVALID_RESULT"

    # Extract reason code
    reason = (
        raw.get("reason_code")
        or raw.get("reason")
        or (
            raw.get("outcome", {}).get("reason_code")
            if isinstance(raw.get("outcome"), Mapping)
            else None
        )
        or "OK"
    )

    # Extract oracle decision
    oracle_raw = raw.get("oracle")
    oracle_decision = (
        raw.get("oracle_decision")
        or (oracle_raw.get("decision") if isinstance(oracle_raw, Mapping) else None)
        or "NONE"
    )

    # Extract evidence gap code
    gap_code = (
        raw.get("evidence_gap_code")
        or raw.get("gap_code")
        or (oracle_raw.get("gap_code") if isinstance(oracle_raw, Mapping) else None)
        or "none"
    )
    if isinstance(gap_code, Sequence) and not isinstance(gap_code, str | bytes):
        gap_code = gap_code[0] if gap_code else "none"
    gap_code = str(gap_code)

    # Extract backend
    backend = str(raw.get("actual_backend") or raw.get("backend") or "local_deterministic")

    # Extract timing and cost
    duration = float(raw.get("duration_seconds") or 0.0)
    cpu_duration = float(raw.get("cpu_duration_seconds") or raw.get("cpu_time") or 0.0)
    db_duration = float(raw.get("db_duration_seconds") or raw.get("db_time") or 0.0)
    model_duration = float(raw.get("model_duration_seconds") or raw.get("model_time") or 0.0)
    model_cost = float(raw.get("model_cost_usd") or raw.get("model_cost") or 0.0)

    # Extract signature references
    sig_refs: dict[str, Any] = {}
    if isinstance(raw.get("signature_refs"), Mapping):
        sig_refs.update(raw["signature_refs"])
    if "pair_digest" in raw:
        sig_refs["pair_digest"] = str(raw["pair_digest"])
    if "source_commit" in raw:
        sig_refs["source_commit"] = str(raw["source_commit"])

    # Extract payload details
    payload: dict[str, Any] = {}
    if isinstance(raw.get("payload"), Mapping):
        payload.update(raw["payload"])
    elif isinstance(raw.get("detail"), Mapping):
        payload.update(raw["detail"])

    # Include any remaining domain fields in payload
    standard_keys = {
        "raw_outcome",
        "observed_outcome",
        "outcome",
        "reason_code",
        "reason",
        "oracle_decision",
        "oracle",
        "evidence_gap_code",
        "gap_code",
        "actual_backend",
        "backend",
        "duration_seconds",
        "cpu_duration_seconds",
        "cpu_time",
        "db_duration_seconds",
        "db_time",
        "model_duration_seconds",
        "model_time",
        "model_cost_usd",
        "model_cost",
        "signature_refs",
        "pair_digest",
        "source_commit",
        "payload",
        "detail",
        "event_id",
        "digest_refs",
        "recorded_at",
        "timestamp",
    }
    for k, v in raw.items():
        if k not in standard_keys:
            payload[k] = v

    # Sanitize payload and signature refs
    sanitized_payload = sanitize_sensitive_data(payload)
    sanitized_sig_refs = sanitize_sensitive_data(sig_refs)

    return {
        "raw_outcome": outcome,
        "reason_code": str(reason),
        "oracle_decision": str(oracle_decision),
        "evidence_gap_code": gap_code,
        "actual_backend": backend,
        "duration_cost": {
            "duration_seconds": duration,
            "cpu_duration_seconds": cpu_duration,
            "db_duration_seconds": db_duration,
            "model_duration_seconds": model_duration,
            "model_cost_usd": model_cost,
        },
        "signature_refs": sanitized_sig_refs,
        "payload": sanitized_payload,
    }


def _compute_entry_digest(record: Mapping[str, Any], prev_digest: str, payload_digest: str) -> str:
    """Compute deterministic SHA-256 over record content excluding entry_digest itself."""
    record_for_digest = {k: v for k, v in record.items() if k != "digest_refs"}
    record_for_digest["digest_refs"] = {
        "payload_digest": payload_digest,
        "prev_digest": prev_digest,
    }
    return hashlib.sha256(canonical_json(record_for_digest).encode("utf-8")).hexdigest()


class TraceWriter:
    """Append-only, tamper-evident JSONL trace writer."""

    def __init__(self, trace_path: str | Path, actual_backend: str = "local_deterministic") -> None:
        self.trace_path = Path(trace_path)
        self.actual_backend = actual_backend
        self._last_event_id = 0
        self._last_digest = GENESIS_PREV_DIGEST
        self._init_state()

    def _init_state(self) -> None:
        """Read existing trace file if present to resume monotonic sequence and digest chain."""
        if not self.trace_path.exists():
            return

        lines = self.trace_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return

        last_id = 0
        last_digest = GENESIS_PREV_DIGEST
        for line_no, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
            except Exception as exc:
                raise TraceWriterError(
                    "CORRUPTED_TRACE", f"Line {line_no} is not valid JSON: {exc}"
                ) from exc

            event_id = rec.get("event_id")
            if not isinstance(event_id, int) or event_id <= last_id:
                raise TraceWriterError(
                    "NON_MONOTONIC_EVENT_ID",
                    f"Line {line_no} event_id {event_id} is not strictly greater than {last_id}",
                )
            last_id = event_id

            digest_refs = rec.get("digest_refs")
            if not isinstance(digest_refs, Mapping) or "entry_digest" not in digest_refs:
                raise TraceWriterError(
                    "CORRUPTED_TRACE", f"Line {line_no} is missing digest_refs.entry_digest"
                )
            last_digest = str(digest_refs["entry_digest"])

        self._last_event_id = last_id
        self._last_digest = last_digest

    def write_trace(self, event: Mapping[str, Any] | TraceEvent) -> str:
        """Append a normalized, sanitized event to the trace.

        Returns
        -------
        str
            The 64-character SHA-256 entry digest of the recorded trace line.
        """
        normalized = _normalize_event(event)
        if (
            self.actual_backend != "local_deterministic"
            and normalized["actual_backend"] == "local_deterministic"
        ):
            normalized["actual_backend"] = self.actual_backend

        # Increment monotonic sequence
        event_id = self._last_event_id + 1
        recorded_at = round(time.time(), 6)

        # Compute payload digest
        payload_digest = hashlib.sha256(
            canonical_json(normalized["payload"]).encode("utf-8")
        ).hexdigest()
        prev_digest = self._last_digest

        record: dict[str, Any] = {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "raw_outcome": normalized["raw_outcome"],
            "reason_code": normalized["reason_code"],
            "oracle_decision": normalized["oracle_decision"],
            "evidence_gap_code": normalized["evidence_gap_code"],
            "actual_backend": normalized["actual_backend"],
            "duration_cost": normalized["duration_cost"],
            "signature_refs": normalized["signature_refs"],
            "digest_refs": {
                "payload_digest": payload_digest,
                "prev_digest": prev_digest,
            },
            "payload": normalized["payload"],
        }

        entry_digest = _compute_entry_digest(record, prev_digest, payload_digest)
        record["digest_refs"]["entry_digest"] = entry_digest

        # Format line and append to file
        line = canonical_json(record) + "\n"
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as fh:
            fh.write(line)

        # Update in-memory state
        self._last_event_id = event_id
        self._last_digest = entry_digest
        return entry_digest

    def verify_trace(self) -> bool:
        """Verify the trace file managed by this writer."""
        return verify_trace(self.trace_path)


def write_trace(
    event: Mapping[str, Any] | TraceEvent,
    trace_path: str | Path | None = None,
    actual_backend: str | None = None,
) -> str:
    """Exact target contract: write_trace(event) -> sha256.

    Appends an event to the trace file (defaulting to DEFAULT_TRACE_PATH) and
    returns the record's SHA-256 entry digest.
    """
    path = Path(trace_path) if trace_path is not None else DEFAULT_TRACE_PATH
    writer = TraceWriter(path, actual_backend=actual_backend or "local_deterministic")
    return writer.write_trace(event)


def verify_trace_details(trace_path: str | Path) -> tuple[bool, str]:
    """Inspect trace file and return (is_valid, reason_message).

    Verifies:
    1. File exists and is non-empty.
    2. Every line is valid JSON with all required fields.
    3. Strictly monotonic event_ids starting from >= 1.
    4. Valid cryptographic hash chain (prev_digest link and entry_digest verification).
    5. Payload digest verification.
    6. Complete absence of unredacted credentials and PII.
    """
    path = Path(trace_path)
    if not path.is_file():
        return False, f"EMPTY_TRACE: file does not exist: {path}"

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"IO_ERROR: failed to read file: {exc}"

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return False, "EMPTY_TRACE: trace contains no records"

    expected_prev = GENESIS_PREV_DIGEST
    last_event_id = 0

    required_fields = (
        "event_id",
        "recorded_at",
        "raw_outcome",
        "reason_code",
        "oracle_decision",
        "evidence_gap_code",
        "actual_backend",
        "duration_cost",
        "digest_refs",
    )

    for idx, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except Exception as exc:
            return False, f"CORRUPTED_TRACE: line {idx} is invalid JSON: {exc}"

        if not isinstance(record, Mapping):
            return False, f"CORRUPTED_TRACE: line {idx} record is not a JSON object"

        for field in required_fields:
            if field not in record:
                return False, f"CORRUPTED_TRACE: line {idx} missing required field '{field}'"

        # Check monotonic event ID
        event_id = record["event_id"]
        if not isinstance(event_id, int) or event_id <= last_event_id:
            return (
                False,
                f"NON_MONOTONIC_EVENT_ID: line {idx} event_id {event_id} is not > {last_event_id}",
            )
        last_event_id = event_id

        # Check raw outcome
        outcome = record["raw_outcome"]
        if outcome not in ALLOWED_OUTCOMES:
            return False, f"CORRUPTED_TRACE: line {idx} invalid raw_outcome '{outcome}'"

        # Check digest references
        digest_refs = record["digest_refs"]
        if not isinstance(digest_refs, Mapping):
            return False, f"CORRUPTED_TRACE: line {idx} digest_refs is not a mapping"

        entry_digest = digest_refs.get("entry_digest")
        prev_digest = digest_refs.get("prev_digest")
        payload_digest = digest_refs.get("payload_digest")

        if not entry_digest or not prev_digest or not payload_digest:
            return False, f"CORRUPTED_TRACE: line {idx} incomplete digest_refs"

        # Check prev_digest chain link
        if prev_digest != expected_prev:
            return (
                False,
                f"CHAIN_INTEGRITY_BROKEN: line {idx} prev_digest '{prev_digest}' does not match expected '{expected_prev}'",
            )

        # Check payload digest
        payload = record.get("payload", {})
        recomputed_payload_digest = hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()
        if recomputed_payload_digest != payload_digest:
            return (
                False,
                f"TAMPER_DETECTED: line {idx} payload digest mismatch (expected {payload_digest}, got {recomputed_payload_digest})",
            )

        # Recompute entry digest
        recomputed_entry_digest = _compute_entry_digest(
            record, str(prev_digest), str(payload_digest)
        )
        if recomputed_entry_digest != entry_digest:
            return (
                False,
                f"TAMPER_DETECTED: line {idx} entry digest mismatch (declared {entry_digest}, computed {recomputed_entry_digest})",
            )

        # Check for credential / PII leaks
        leaks = detect_sensitive_leak(record)
        if leaks:
            return False, f"CREDENTIAL_LEAK_DETECTED: line {idx} leaks: {'; '.join(leaks)}"

        expected_prev = str(entry_digest)

    return True, "OK"


def verify_trace(trace_path: str | Path) -> bool:
    """Verify trace integrity. Returns True if valid, False if tampered or corrupt."""
    is_valid, _reason = verify_trace_details(trace_path)
    return is_valid


def read_trace(trace_path: str | Path) -> list[dict[str, Any]]:
    """Read all records from a verified trace file."""
    path = Path(trace_path)
    if not path.is_file():
        raise TraceWriterError("EMPTY_TRACE", f"Trace file does not exist: {path}")

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line_str = line.strip()
        if line_str:
            records.append(json.loads(line_str))
    return records
