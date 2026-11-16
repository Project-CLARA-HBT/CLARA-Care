"""CLARA-Care 2027 POPETS task POPETS-traces — Immutable trace and measurement capture.

Purpose
-------
Implement append-only JSONL trace recording with monotonic event IDs, cryptographic
digest chaining, raw outcome and reason code capture, independent oracle decision
binding, CPU/DB/model duration and cost tracking, actual execution backend labeling,
and fail-closed sensitive content sanitization (no PHI, no patient identifiers).
Also provides integrity verification checking monotonicity of event IDs and
unbroken digest chains.

Allowed input
-------------
- Plain mappings or :class:`TraceRecord` instances containing:
  - ``raw_outcome`` / ``outcome``: outcome bucket (ADMIT, REJECT, INDETERMINATE, etc.)
  - ``reason_code``: stable machine-readable reason code
  - ``oracle_decision`` / ``oracle``: oracle truth / expected verdict dictionary
  - ``actual_backend`` / ``backend``: execution backend identifier
  - CPU/DB/model durations and costs (seconds / cost floats)
  - optional ``signature_ref`` / digest references
  - optional ``event_id`` (must be strictly monotonic if explicitly supplied)
  - optional non-PHI payload metadata

Failure semantics
-----------------
Fail closed with stable uppercase reason codes (:class:`TraceWriterError`):
- ``NON_MONOTONIC_EVENT_ID`` — incoming event ID is <= previous event ID.
- ``UNSANITIZED_PHI_REJECTED`` — record contains raw PHI or patient identifiers.
- ``PHI_FIELD_PRESENT`` — alias for detected PHI marker.
- ``DIGEST_MISMATCH`` — recomputed digest does not match recorded digest.
- ``CHAIN_CORRUPT`` — previous digest link broken.
- ``INVALID_RECORD`` — input record is malformed or invalid type.
- ``CORRUPTED_TRACE`` — trace file corrupted or unparseable.
- ``TRACE_FILE_ERROR`` — file I/O or path resolution failure.

Version
-------
``TRACE_WRITER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

TRACE_WRITER_VERSION: Final[str] = "1.0.0"

GENESIS_DIGEST: Final[str] = "0" * 64

# Stable reason codes
REASON_NON_MONOTONIC_EVENT_ID: Final[str] = "NON_MONOTONIC_EVENT_ID"
REASON_UNSANITIZED_PHI_REJECTED: Final[str] = "UNSANITIZED_PHI_REJECTED"
REASON_PHI_FIELD_PRESENT: Final[str] = "PHI_FIELD_PRESENT"
REASON_DIGEST_MISMATCH: Final[str] = "DIGEST_MISMATCH"
REASON_CHAIN_CORRUPT: Final[str] = "CHAIN_CORRUPT"
REASON_INVALID_RECORD: Final[str] = "INVALID_RECORD"
REASON_CORRUPTED_TRACE: Final[str] = "CORRUPTED_TRACE"
REASON_TRACE_FILE_ERROR: Final[str] = "TRACE_FILE_ERROR"

# Field markers and keys that indicate PHI / PII or patient identifiers
PHI_FIELD_EXACT: Final[frozenset[str]] = frozenset(
    {
        "name",
        "patient_name",
        "first_name",
        "last_name",
        "full_name",
        "email",
        "user_email",
        "patient_email",
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "address",
        "street_address",
        "home_address",
        "zip_code",
        "postal_code",
        "national_id",
        "passport",
        "passport_number",
        "mrn",
        "insurance_id",
        "dob",
        "date_of_birth",
        "birth_date",
        "patient_id",
        "patient",
        "patient_identifier",
        "ssn",
        "social_security",
        "social_security_number",
        "diagnosis",
        "symptom",
        "prescription",
        "medical_record_number",
    }
)

PHI_SUBSTRING_MARKERS: Final[tuple[str, ...]] = (
    "patient_id",
    "patient_name",
    "patient_ident",
    "national_id",
    "passport",
    "insurance_id",
    "date_of_birth",
    "medical_record",
)

# Common regex patterns for unsanitized sensitive strings
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
_SSN_RE = re.compile(r"^\d{3}-\d{2}-\d{4}$")


class TraceWriterError(ValueError):
    """Stable, machine-readable trace writer and verification failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def detect_phi(record: Any, prefix: str = "") -> list[str]:
    """Recursively inspect a record for PHI markers and patient identifiers."""
    hits: list[str] = []
    if isinstance(record, Mapping):
        for k, v in record.items():
            key_str = str(k).lower().strip()
            path_key = f"{prefix}.{k}" if prefix else str(k)
            # 1. Exact key match
            if key_str in PHI_FIELD_EXACT:
                hits.append(path_key)
            # 2. Substring marker match
            elif any(marker in key_str for marker in PHI_SUBSTRING_MARKERS):
                hits.append(path_key)
            elif key_str.startswith("mrn_") or key_str.endswith("_mrn"):
                hits.append(path_key)
            elif key_str.startswith("ssn_") or key_str.endswith("_ssn"):
                hits.append(path_key)
            # 3. Recurse into values
            hits.extend(detect_phi(v, prefix=path_key))
    elif isinstance(record, list | tuple | set):
        for idx, item in enumerate(record):
            path_key = f"{prefix}[{idx}]"
            hits.extend(detect_phi(item, prefix=path_key))
    elif isinstance(record, str):
        # Value pattern checks
        val_str = record.strip()
        if _EMAIL_RE.match(val_str):
            hits.append(f"{prefix}(email_value)")
        elif _SSN_RE.match(val_str):
            hits.append(f"{prefix}(ssn_value)")
    return hits


def sanitize_record(
    record: Mapping[str, Any],
    *,
    salt: str = "popets_trace_salt",
) -> dict[str, Any]:
    """Produce a sanitized copy of the record with PHI removed/anonymized."""
    sanitized: dict[str, Any] = {}
    for k, v in record.items():
        key_str = str(k).lower().strip()
        # Transform identifiable patient IDs into opaque one-way subject digests
        if key_str in {"patient_id", "patient_identifier", "patient"}:
            if v is not None:
                token = hashlib.sha256(f"{v}:{salt}".encode()).hexdigest()[:16]
                sanitized["subject_token"] = f"sub-{token}"
            continue
        # Drop identifiable PHI / PII fields
        if key_str in PHI_FIELD_EXACT or any(m in key_str for m in PHI_SUBSTRING_MARKERS):
            continue
        # Recursive sanitization for nested containers
        if isinstance(v, Mapping):
            nested = sanitize_record(v, salt=salt)
            sanitized[k] = nested
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_record(item, salt=salt) if isinstance(item, Mapping) else item
                for item in v
            ]
        else:
            sanitized[k] = copy.deepcopy(v)
    return sanitized


def compute_event_digest(record: Mapping[str, Any]) -> str:
    """Compute deterministic SHA-256 hex digest of a trace record.

    Excludes any existing ``event_digest`` field to enable self-referential
    verification.
    """
    clean_record = {k: v for k, v in record.items() if k != "event_digest"}
    payload = json.dumps(clean_record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class TraceRecord:
    """Strongly-typed representation of an immutable trace event."""

    event_id: int
    prev_digest: str
    raw_outcome: str
    reason_code: str
    oracle_decision: dict[str, Any] | str
    actual_backend: str
    cpu_duration_seconds: float = 0.0
    db_duration_seconds: float = 0.0
    model_duration_seconds: float = 0.0
    duration_seconds: float = 0.0
    cpu_cost: float = 0.0
    db_cost: float = 0.0
    model_cost: float = 0.0
    signature_ref: str = ""
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)
    event_digest: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable dictionary representation."""
        data: dict[str, Any] = {
            "event_id": self.event_id,
            "prev_digest": self.prev_digest,
            "raw_outcome": self.raw_outcome,
            "reason_code": self.reason_code,
            "oracle_decision": self.oracle_decision,
            "actual_backend": self.actual_backend,
            "cpu_duration_seconds": round(self.cpu_duration_seconds, 6),
            "db_duration_seconds": round(self.db_duration_seconds, 6),
            "model_duration_seconds": round(self.model_duration_seconds, 6),
            "duration_seconds": round(self.duration_seconds, 6),
            "cpu_cost": round(self.cpu_cost, 6),
            "db_cost": round(self.db_cost, 6),
            "model_cost": round(self.model_cost, 6),
            "signature_ref": self.signature_ref,
            "timestamp": round(self.timestamp, 6),
        }
        if self.payload:
            data["payload"] = self.payload
        if self.event_digest:
            data["event_digest"] = self.event_digest
        return data


class TraceWriter:
    """Append-only JSONL trace writer enforcing monotonicity and digest chains."""

    def __init__(
        self,
        trace_path: str | Path,
        *,
        default_backend: str = "popets_prov_tracker",
        auto_flush: bool = True,
    ) -> None:
        self.trace_path = Path(trace_path)
        self.default_backend = default_backend
        self.auto_flush = auto_flush
        self.last_event_id = 0
        self.last_digest = GENESIS_DIGEST
        self._init_state()

    def _init_state(self) -> None:
        """Read existing trace file to recover last_event_id and last_digest."""
        if not self.trace_path.is_file():
            return
        last_id = 0
        last_dig = GENESIS_DIGEST
        has_content = False
        try:
            with self.trace_path.open("r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, start=1):
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        record = json.loads(line_s)
                    except json.JSONDecodeError as exc:
                        raise TraceWriterError(
                            REASON_CORRUPTED_TRACE,
                            f"line {line_no} is not valid JSON: {exc}",
                        ) from exc
                    if not isinstance(record, dict):
                        raise TraceWriterError(
                            REASON_CORRUPTED_TRACE,
                            f"line {line_no} is not a JSON object",
                        )
                    eid = record.get("event_id")
                    if not isinstance(eid, int) or eid <= last_id:
                        raise TraceWriterError(
                            REASON_NON_MONOTONIC_EVENT_ID,
                            f"existing trace has non-monotonic event_id at line {line_no}: {eid} <= {last_id}",
                        )
                    last_id = eid
                    dig = record.get("event_digest")
                    if not isinstance(dig, str) or len(dig) != 64:
                        raise TraceWriterError(
                            REASON_CORRUPTED_TRACE,
                            f"line {line_no} lacks valid event_digest",
                        )
                    last_dig = dig
                    has_content = True
        except OSError as exc:
            raise TraceWriterError(
                REASON_TRACE_FILE_ERROR,
                f"failed to read {self.trace_path}: {exc}",
            ) from exc

        if has_content:
            self.last_event_id = last_id
            self.last_digest = last_dig

    def append(
        self,
        record: Mapping[str, Any] | TraceRecord,
        *,
        sanitize: bool = False,
    ) -> str:
        """Append one record to trace JSONL; returns the event_digest SHA-256."""
        # Convert TraceRecord to dict if needed
        data: dict[str, Any]
        if isinstance(record, TraceRecord):
            data = record.to_dict()
        elif isinstance(record, Mapping):
            data = dict(record)
        else:
            raise TraceWriterError(
                REASON_INVALID_RECORD,
                f"record must be Mapping or TraceRecord, got {type(record).__name__}",
            )

        # Sensitive content sanitization
        if sanitize:
            data = sanitize_record(data)

        # PHI boundary check (fail closed on unsanitized PHI)
        phi_hits = detect_phi(data)
        if phi_hits:
            raise TraceWriterError(
                REASON_UNSANITIZED_PHI_REJECTED,
                f"unsanitized PHI field rejected: {phi_hits}",
            )

        # Monotonic event ID enforcement
        explicit_eid = data.get("event_id")
        if explicit_eid is not None:
            if not isinstance(explicit_eid, int) or isinstance(explicit_eid, bool):
                raise TraceWriterError(
                    REASON_INVALID_RECORD,
                    f"event_id must be integer, got {explicit_eid!r}",
                )
            if explicit_eid <= self.last_event_id:
                raise TraceWriterError(
                    REASON_NON_MONOTONIC_EVENT_ID,
                    f"non-monotonic event ID refused: {explicit_eid} <= {self.last_event_id}",
                )
            event_id = explicit_eid
        else:
            event_id = self.last_event_id + 1

        # Extract standard fields with sensible defaults
        raw_outcome = str(
            data.get("raw_outcome")
            or data.get("outcome")
            or data.get("observed_outcome")
            or "ADMIT"
        )
        reason_code = str(data.get("reason_code") or data.get("reason") or "OK")
        oracle_dec = data.get("oracle_decision")
        if oracle_dec is None:
            oracle_dec = data.get("oracle", {})
        actual_backend = str(
            data.get("actual_backend") or data.get("backend") or self.default_backend
        )

        cpu_dur = float(data.get("cpu_duration_seconds", data.get("cpu_duration", 0.0)))
        db_dur = float(data.get("db_duration_seconds", data.get("db_duration", 0.0)))
        model_dur = float(data.get("model_duration_seconds", data.get("model_duration", 0.0)))
        dur = float(data.get("duration_seconds", cpu_dur + db_dur + model_dur))

        cpu_cost = float(data.get("cpu_cost", 0.0))
        db_cost = float(data.get("db_cost", 0.0))
        model_cost = float(data.get("model_cost", 0.0))

        signature_ref = str(data.get("signature_ref", data.get("signature", "")))
        timestamp = float(data.get("timestamp", time.time()))

        # Separate auxiliary payload
        standard_keys = {
            "event_id",
            "prev_digest",
            "event_digest",
            "raw_outcome",
            "outcome",
            "observed_outcome",
            "reason_code",
            "reason",
            "oracle_decision",
            "oracle",
            "actual_backend",
            "backend",
            "cpu_duration_seconds",
            "cpu_duration",
            "db_duration_seconds",
            "db_duration",
            "model_duration_seconds",
            "model_duration",
            "duration_seconds",
            "cpu_cost",
            "db_cost",
            "model_cost",
            "signature_ref",
            "signature",
            "timestamp",
            "payload",
        }
        aux_payload = {k: v for k, v in data.items() if k not in standard_keys}
        if "payload" in data and isinstance(data["payload"], Mapping):
            aux_payload.update(data["payload"])

        # Construct trace record entry
        entry: dict[str, Any] = {
            "event_id": event_id,
            "prev_digest": self.last_digest,
            "raw_outcome": raw_outcome,
            "reason_code": reason_code,
            "oracle_decision": oracle_dec,
            "actual_backend": actual_backend,
            "cpu_duration_seconds": round(cpu_dur, 6),
            "db_duration_seconds": round(db_dur, 6),
            "model_duration_seconds": round(model_dur, 6),
            "duration_seconds": round(dur, 6),
            "cpu_cost": round(cpu_cost, 6),
            "db_cost": round(db_cost, 6),
            "model_cost": round(model_cost, 6),
            "signature_ref": signature_ref,
            "timestamp": round(timestamp, 6),
        }
        if aux_payload:
            entry["payload"] = aux_payload

        # Seal cryptographic digest
        digest = compute_event_digest(entry)
        entry["event_digest"] = digest

        # Append to disk
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        try:
            with self.trace_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                if self.auto_flush:
                    fh.flush()
        except OSError as exc:
            raise TraceWriterError(
                REASON_TRACE_FILE_ERROR,
                f"failed to append to {self.trace_path}: {exc}",
            ) from exc

        # Advance internal state
        self.last_event_id = event_id
        self.last_digest = digest
        return digest

    def write(
        self,
        record: Mapping[str, Any] | TraceRecord,
        *,
        sanitize: bool = False,
    ) -> str:
        """Alias for append."""
        return self.append(record, sanitize=sanitize)

    def verify(self) -> bool:
        """Verify the integrity of this writer's trace file."""
        return verify_trace(self.trace_path)


def write_trace(
    trace_path_or_record: str | Path | Mapping[str, Any],
    record: Mapping[str, Any] | None = None,
    *,
    trace_path: str | Path | None = None,
    sanitize: bool = False,
    default_backend: str = "popets_prov_tracker",
) -> str:
    """Convenience functional interface for trace recording.

    Supports:
    - ``write_trace(trace_path, record, ...) -> sha256``
    - ``write_trace(record, trace_path=..., ...) -> sha256``
    """
    target_path: Path
    payload: Mapping[str, Any]

    if isinstance(trace_path_or_record, str | Path):
        target_path = Path(trace_path_or_record)
        if record is None:
            raise TraceWriterError(
                REASON_INVALID_RECORD,
                "missing record parameter when trace_path is provided as first argument",
            )
        payload = record
    elif isinstance(trace_path_or_record, Mapping):
        payload = trace_path_or_record
        if trace_path is None:
            target_path = Path("/tmp/popets_trace_default.jsonl")
        else:
            target_path = Path(trace_path)
    else:
        raise TraceWriterError(
            REASON_INVALID_RECORD,
            f"unsupported first argument: {type(trace_path_or_record).__name__}",
        )

    writer = TraceWriter(target_path, default_backend=default_backend)
    return writer.append(payload, sanitize=sanitize)


def verify_trace_detailed(trace_path: str | Path) -> tuple[bool, list[str]]:
    """Verify trace integrity returning (is_valid, list_of_defects).

    Checks:
    1. File exists and contains valid JSON lines.
    2. Monotonicity of event IDs.
    3. Unbroken digest chain (prev_digest links).
    4. Deterministic SHA-256 event digest match on every line.
    5. Absence of unsanitized PHI/PII markers.
    """
    path = Path(trace_path)
    defects: list[str] = []
    if not path.is_file():
        return False, [f"file not found: {path}"]

    last_id = 0
    expected_prev = GENESIS_DIGEST
    count = 0

    try:
        with path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line_s = line.strip()
                if not line_s:
                    continue
                count += 1
                try:
                    entry = json.loads(line_s)
                except json.JSONDecodeError as exc:
                    defects.append(f"line {line_no}: invalid JSON: {exc}")
                    continue
                if not isinstance(entry, dict):
                    defects.append(f"line {line_no}: record is not an object")
                    continue

                # 1. PHI check
                phi_hits = detect_phi(entry)
                if phi_hits:
                    defects.append(f"line {line_no}: unsanitized PHI present: {phi_hits}")

                # 2. Monotonic event_id
                eid = entry.get("event_id")
                if not isinstance(eid, int) or isinstance(eid, bool):
                    defects.append(f"line {line_no}: event_id is not integer: {eid!r}")
                elif eid <= last_id:
                    defects.append(f"line {line_no}: non-monotonic event_id: {eid} <= {last_id}")
                else:
                    last_id = eid

                # 3. Digest chain linkage
                prev_dig = entry.get("prev_digest")
                if prev_dig != expected_prev:
                    defects.append(
                        f"line {line_no}: broken digest chain: prev_digest={prev_dig!r} expected {expected_prev!r}"
                    )

                # 4. Digest recomputation
                recorded_dig = entry.get("event_digest")
                if not isinstance(recorded_dig, str):
                    defects.append(f"line {line_no}: missing event_digest")
                else:
                    recomputed = compute_event_digest(entry)
                    if recorded_dig != recomputed:
                        defects.append(
                            f"line {line_no}: digest mismatch: recorded {recorded_dig} != recomputed {recomputed}"
                        )
                    expected_prev = recorded_dig
    except OSError as exc:
        return False, [f"failed to read {path}: {exc}"]

    if count == 0:
        return False, ["trace file is empty"]

    return len(defects) == 0, defects


def verify_trace(trace_path: str | Path) -> bool:
    """Verify trace integrity: monotonicity of event IDs and unbroken digest chain."""
    ok, _ = verify_trace_detailed(trace_path)
    return ok


def read_trace(trace_path: str | Path) -> list[dict[str, Any]]:
    """Read all records from a trace JSONL file."""
    path = Path(trace_path)
    if not path.is_file():
        raise TraceWriterError(REASON_TRACE_FILE_ERROR, f"file not found: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line_s = line.strip()
            if line_s:
                records.append(json.loads(line_s))
    return records
