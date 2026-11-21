"""Version 1.1 append-only JSONL telemetry for synthetic PST development runs.

Accept explicit telemetry or harness pair results. Pin a published trace hash or
final digest and row count to detect truncation or complete file replacement.
Missing component timings, monetary costs, scores, and backend observations are
retained as unknown. Report malformed input and integrity errors via TraceWriterError.
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, TextIO

from evaluation.venue2027._shared.harness import _pair_digest

PST_TRACE_WRITER_VERSION: Final[str] = "1.1.0"

GENESIS_PREV_DIGEST: Final[str] = "0" * 64
DEFAULT_TRACE_PATH: Final[Path] = Path("artifacts/venue2027/pst/local/trace.jsonl")

# Canonical outcome buckets from shared harness (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4)
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

# Stable reason codes
REASON_NON_MONOTONIC_EVENT_ID: Final[str] = "NON_MONOTONIC_EVENT_ID"
REASON_SCORE_OUT_OF_RANGE: Final[str] = "SCORE_OUT_OF_RANGE"
REASON_TAMPER_DETECTED: Final[str] = "TAMPER_DETECTED"
REASON_CHAIN_INTEGRITY_BROKEN: Final[str] = "CHAIN_INTEGRITY_BROKEN"
REASON_CREDENTIAL_LEAK_DETECTED: Final[str] = "CREDENTIAL_LEAK_DETECTED"
REASON_PHI_LEAK_DETECTED: Final[str] = "PHI_LEAK_DETECTED"
REASON_EMPTY_TRACE: Final[str] = "EMPTY_TRACE"
REASON_CORRUPTED_TRACE: Final[str] = "CORRUPTED_TRACE"
REASON_INVALID_RECORD: Final[str] = "INVALID_RECORD"

# Sensitive dictionary keys to scrub (credentials and user secrets)
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
        "user_secret",
    }
)

# Sensitive dictionary keys to scrub (PHI and patient identifiers)
_PHI_KEY_DENYLIST: Final[frozenset[str]] = frozenset(
    {
        "ssn",
        "social_security",
        "social_security_number",
        "citizen_id",
        "national_id",
        "cmnd",
        "cccd",
        "identity_card",
        "passport",
        "passport_number",
        "mrn",
        "medical_record_number",
        "name",
        "query",
        "drug_list",
        "drugs",
        "patient_name",
        "patient_id",
        "patient",
        "first_name",
        "last_name",
        "full_name",
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "so_dien_thoai",
        "email",
        "patient_email",
        "user_email",
        "home_address",
        "street_address",
        "address",
        "dia_chi",
        "date_of_birth",
        "dob",
        "birth_date",
        "birthdate",
        "diagnosis",
        "symptom",
        "prescription",
        "bank_account",
        "credit_card",
    }
)

_PHI_SUBSTRING_MARKERS: Final[tuple[str, ...]] = (
    "patient_id",
    "patient_name",
    "patient_ident",
    "national_id",
    "passport",
    "date_of_birth",
    "medical_record",
)

# Regex patterns for credential leak detection and sanitization
_BEARER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE
)
_API_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:sk|pk|ghp|key|api)-[A-Za-z0-9_\-]{16,}", re.IGNORECASE
)
_PRIVATE_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"-----BEGIN[ A-Z_-]*PRIVATE KEY-----.*?-----END[ A-Z_-]*PRIVATE KEY-----", re.DOTALL
)
_CREDENTIAL_KV_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:password|secret|api_key|access_token|auth_token)\s*[:=]\s*['\"]?([^\s'\";,}]+)",
    re.IGNORECASE,
)

# Regex patterns for PHI leak detection and sanitization
_EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
)
_SSN_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_PHONE_PATTERN: Final[re.Pattern[str]] = re.compile(
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


def _compute_payload_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _compute_entry_digest(record: dict[str, Any]) -> str:
    cleaned = {k: v for k, v in record.items() if k != "entry_digest"}
    if "digest_refs" in cleaned and isinstance(cleaned["digest_refs"], dict):
        cleaned["digest_refs"] = {
            k: v for k, v in cleaned["digest_refs"].items() if k != "entry_digest"
        }
    return hashlib.sha256(canonical_json(cleaned).encode("utf-8")).hexdigest()


def _is_phi_key(key_str: str) -> bool:
    norm = key_str.strip().lower()
    if norm in _PHI_KEY_DENYLIST:
        return True
    if any(marker in norm for marker in _PHI_SUBSTRING_MARKERS):
        return True
    if norm.startswith("mrn_") or norm.endswith("_mrn"):
        return True
    if norm.startswith("ssn_") or norm.endswith("_ssn"):
        return True
    return False


def sanitize_sensitive_data(value: Any) -> Any:
    """Recursively scrub credentials and PHI from mappings, lists, and strings.

    Replaces identified credentials with '[REDACTED_CREDENTIAL]' and PHI with '[REDACTED_PHI]'.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_k, raw_v in value.items():
            k_str = str(raw_k)
            k_norm = k_str.strip().lower()
            if k_norm in _CREDENTIAL_KEY_DENYLIST:
                sanitized[k_str] = "[REDACTED_CREDENTIAL]"
            elif _is_phi_key(k_norm):
                sanitized[k_str] = "[REDACTED_PHI]"
            else:
                sanitized[k_str] = sanitize_sensitive_data(raw_v)
        return sanitized

    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [sanitize_sensitive_data(item) for item in value]

    if isinstance(value, str):
        if value in ("[REDACTED_CREDENTIAL]", "[REDACTED_PHI]", "[REDACTED]"):
            return value

        cleaned = value
        if _PRIVATE_KEY_PATTERN.search(cleaned):
            cleaned = _PRIVATE_KEY_PATTERN.sub("[REDACTED_CREDENTIAL]", cleaned)
        if _BEARER_PATTERN.search(cleaned):
            cleaned = _BEARER_PATTERN.sub("Bearer [REDACTED_CREDENTIAL]", cleaned)
        if _API_KEY_PATTERN.search(cleaned):
            cleaned = _API_KEY_PATTERN.sub("[REDACTED_CREDENTIAL]", cleaned)
        if _CREDENTIAL_KV_PATTERN.search(cleaned):
            cleaned = _CREDENTIAL_KV_PATTERN.sub(
                lambda m: m.group(0).replace(m.group(1), "[REDACTED_CREDENTIAL]"), cleaned
            )
        if _SSN_PATTERN.search(cleaned):
            cleaned = _SSN_PATTERN.sub("[REDACTED_PHI]", cleaned)
        if _CREDIT_CARD_PATTERN.search(cleaned):
            cleaned = _CREDIT_CARD_PATTERN.sub("[REDACTED_PHI]", cleaned)
        if _EMAIL_PATTERN.search(cleaned):
            cleaned = _EMAIL_PATTERN.sub("[REDACTED_PHI]", cleaned)
        if _PHONE_PATTERN.search(cleaned):
            cleaned = _PHONE_PATTERN.sub("[REDACTED_PHI]", cleaned)

        return cleaned

    return value


def detect_sensitive_leak(value: Any, path: str = "") -> list[str]:
    """Inspect a record for any unredacted credential, secret, or PHI marker.

    Returns a list of leak descriptions if any found; empty list if clean.
    """
    leaks: list[str] = []

    if isinstance(value, Mapping):
        for raw_k, raw_v in value.items():
            k_str = str(raw_k)
            k_norm = k_str.strip().lower()
            current_path = f"{path}.{k_str}" if path else k_str

            if k_norm in _CREDENTIAL_KEY_DENYLIST:
                if not (
                    isinstance(raw_v, str)
                    and raw_v in ("[REDACTED_CREDENTIAL]", "[REDACTED_PHI]", "[REDACTED]")
                ):
                    leaks.append(f"CREDENTIAL_LEAK at key '{current_path}'")
            elif _is_phi_key(k_norm):
                if not (
                    isinstance(raw_v, str)
                    and raw_v in ("[REDACTED_CREDENTIAL]", "[REDACTED_PHI]", "[REDACTED]")
                ):
                    leaks.append(f"PHI_LEAK at key '{current_path}'")
            else:
                leaks.extend(detect_sensitive_leak(raw_v, current_path))
        return leaks

    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for idx, item in enumerate(value):
            leaks.extend(detect_sensitive_leak(item, f"{path}[{idx}]"))
        return leaks

    if isinstance(value, str):
        if value in ("[REDACTED_CREDENTIAL]", "[REDACTED_PHI]", "[REDACTED]"):
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
            leaks.append(f"PHI_LEAK at '{path}': matches SSN pattern")
        elif _CREDIT_CARD_PATTERN.search(value):
            leaks.append(f"PHI_LEAK at '{path}': matches credit card pattern")
        elif _EMAIL_PATTERN.search(value):
            leaks.append(f"PHI_LEAK at '{path}': matches email pattern")
        elif _PHONE_PATTERN.search(value):
            leaks.append(f"PHI_LEAK at '{path}': matches phone number pattern")

    return leaks


def _validate_score(val: Any, name: str) -> float:
    """Validate that score is a finite float in [0.0, 1.0]."""
    if val is None or isinstance(val, bool) or not isinstance(val, int | float):
        raise TraceWriterError(
            REASON_SCORE_OUT_OF_RANGE,
            f"{name} must be a numeric float, got {val!r}",
        )
    fval = float(val)
    if not math.isfinite(fval) or not (0.0 <= fval <= 1.0):
        raise TraceWriterError(
            REASON_SCORE_OUT_OF_RANGE,
            f"{name} {fval!r} outside [0.0, 1.0]",
        )
    return fval


@dataclasses.dataclass(frozen=True)
class TraceEvent:
    """Input event to record in the append-only PST trace."""

    raw_outcome: str = "INDETERMINATE"
    reconstructability_score: float | None = None
    linkability_score: float | None = None
    reason_code: str = "OK"
    oracle_decision: Any = "NONE"
    actual_backend: str = "UNKNOWN"
    duration_seconds: float | None = None
    cpu_duration_seconds: float | None = None
    db_duration_seconds: float | None = None
    model_duration_seconds: float | None = None
    cpu_cost: float | None = None
    db_cost: float | None = None
    model_cost_usd: float | None = None
    signature_refs: dict[str, str] = dataclasses.field(default_factory=dict)
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)
    event_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


MEASUREMENTS = (
    "duration_seconds",
    "cpu_duration_seconds",
    "db_duration_seconds",
    "model_duration_seconds",
    "cpu_cost",
    "db_cost",
    "model_cost_usd",
)


def _normalize_event(
    event: Mapping[str, Any] | TraceEvent,
    default_backend: str = "UNKNOWN",
) -> dict[str, Any]:
    """Normalize input event into a uniform dictionary representation."""
    data: dict[str, Any]
    if isinstance(event, TraceEvent):
        data = event.to_dict()
    elif isinstance(event, Mapping):
        data = dict(event)
    else:
        raise TraceWriterError(
            REASON_INVALID_RECORD,
            f"Event must be a Mapping or TraceEvent, got {type(event).__name__}",
        )

    pair = data.get("record_kind") == "pair_result"
    if pair:
        try:
            expected_digest = _pair_digest(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise TraceWriterError(REASON_INVALID_RECORD, "invalid harness pair") from exc
        if data.get("pair_digest") != expected_digest:
            raise TraceWriterError(REASON_TAMPER_DETECTED, "source pair digest mismatch")
        outcome = data["outcome"]
        oracle = data.get("oracle")
        if not isinstance(outcome, dict) or not isinstance(oracle, dict):
            raise TraceWriterError(REASON_INVALID_RECORD, "invalid pair outcome or oracle")
        raw = outcome.get("observed_outcome")
        detail = outcome.get("detail", "")
        try:
            detail_object = json.loads(detail)
        except (TypeError, ValueError):
            detail_object = {}
        details = detail_object if isinstance(detail_object, dict) else {}
        payload = {
            key: data[key]
            for key in (
                "arm_id",
                "campaign_id",
                "case_id",
                "logical_op_id",
                "source_commit",
                "seed",
                "harness_version",
                "python_version",
            )
            if key in data
        }
        if not isinstance(payload.get("logical_op_id"), str) or not payload["logical_op_id"]:
            raise TraceWriterError(REASON_INVALID_RECORD, "missing logical operation id")
        # Never copy free-text upstream error detail to telemetry.
        oracle = {
            k: v
            for k, v in oracle.items()
            if k
            in (
                "arm_id",
                "decision",
                "expected_outcome",
                "oracle_id",
                "reason_code",
                "oracle_error",
            )
        }
        data = {
            **{key: data[key] for key in (*MEASUREMENTS, "actual_backend") if key in data},
            "raw_outcome": raw,
            "oracle_decision": oracle,
            "reason_code": details.get("status") or raw,
            "timestamp": data.get("recorded_at"),
            "reconstructability_score": data.get(
                "reconstructability_score", details.get("reconstructability")
            ),
            "linkability_score": data.get("linkability_score", details.get("linkability")),
            "signature_refs": {
                "pair_digest": expected_digest,
                "source_event_sha256": _compute_payload_digest(data),
            },
            "payload": payload,
        }

    raw = data.get("raw_outcome", data.get("outcome", "INDETERMINATE"))
    if isinstance(raw, Mapping):
        raw = raw.get("observed_outcome")
    raw = str(raw).upper()
    raw = {"PERMIT": "ADMIT", "DENY": "REJECT"}.get(raw, raw)
    if raw not in ALLOWED_OUTCOMES:
        raise TraceWriterError(REASON_INVALID_RECORD, "unknown raw outcome")
    output = {
        "raw_outcome": raw,
        "reason_code": data.get("reason_code", data.get("reason", "UNKNOWN")),
        "oracle_decision": data.get("oracle_decision", data.get("oracle", "UNKNOWN")),
        "actual_backend": data.get("actual_backend") or data.get("backend") or default_backend,
        "event_id": data.get("event_id"),
        "timestamp": data.get("timestamp"),
        "signature_refs": data.get("signature_refs", {}),
    }
    for key in ("reconstructability", "linkability"):
        long_key = key + "_score"
        value = data.get(long_key, data.get(key))
        if value is None and (pair or long_key not in data or isinstance(event, TraceEvent)):
            output[long_key] = None
        else:
            output[long_key] = _validate_score(value, long_key)
    for key in (*MEASUREMENTS, "timestamp"):
        value = data.get(key)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise TraceWriterError(REASON_INVALID_RECORD, f"invalid {key}")
        output[key] = value
    payload = data.get("payload")
    if payload is None:
        payload = {k: v for k, v in data.items() if k not in output}
    if not isinstance(payload, Mapping):
        raise TraceWriterError(REASON_INVALID_RECORD, "invalid payload")
    output["payload"] = dict(payload)
    return output


class TraceWriter:
    """Append-only cryptographic trace writer for PST experiments."""

    def __init__(
        self,
        trace_path: str | Path | None = None,
        *,
        actual_backend: str = "UNKNOWN",
        default_backend: str | None = None,
    ) -> None:
        self.trace_path = Path(trace_path) if trace_path is not None else DEFAULT_TRACE_PATH
        self.actual_backend = default_backend or actual_backend
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_event_id: int = 0
        self.last_entry_digest: str = GENESIS_PREV_DIGEST
        with self.trace_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            self._init_state()

    def _init_state(self) -> list[dict[str, Any]]:
        if self.trace_path.stat().st_size == 0:
            self.last_event_id = 0
            self.last_entry_digest = GENESIS_PREV_DIGEST
            return []
        valid, reason = verify_trace_details(self.trace_path)
        if not valid:
            raise TraceWriterError(reason.split(":", 1)[0], "existing trace failed verification")
        records = read_trace(self.trace_path)
        last = records[-1]
        self.last_event_id = last["event_id"]
        self.last_entry_digest = last["digest_refs"]["entry_digest"]
        return records

    def append(self, event: Mapping[str, Any] | TraceEvent, *, sanitize: bool = True) -> str:
        """Serialize updates across local POSIX writers, including reopened handles."""
        with self.trace_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            records = self._init_state()
            return self._append_locked(handle, records, event, sanitize)

    def _append_locked(
        self,
        handle: TextIO,
        records: list[dict[str, Any]],
        event: Mapping[str, Any] | TraceEvent,
        sanitize: bool,
    ) -> str:
        norm_event = _normalize_event(event, default_backend=self.actual_backend)

        if sanitize:
            norm_event = sanitize_sensitive_data(norm_event)

        # Check for unredacted sensitive leaks (fail closed)
        leaks = detect_sensitive_leak(norm_event)
        if leaks:
            has_credential = any("CREDENTIAL_LEAK" in item for item in leaks)
            leak_code = (
                REASON_CREDENTIAL_LEAK_DETECTED if has_credential else REASON_PHI_LEAK_DETECTED
            )
            raise TraceWriterError(leak_code, f"Unredacted sensitive leak: {'; '.join(leaks)}")

        # Accept only synthetic measurement metadata. Arbitrary text and nested
        # application payloads have no place in this paper's evidence artifact.
        norm_event["payload"] = {
            k: v
            for k, v in norm_event["payload"].items()
            if k
            in (
                "arm_id",
                "case_id",
                "campaign_id",
                "logical_op_id",
                "source_commit",
                "seed",
                "harness_version",
                "python_version",
                "family",
                "policy_epoch",
            )
            or isinstance(v, str)
            and v in ("[REDACTED_CREDENTIAL]", "[REDACTED_PHI]")
        }
        op = norm_event["payload"].get("logical_op_id")
        if op and isinstance(event, Mapping) and event.get("record_kind") == "pair_result":
            for prior in records:
                if prior["payload"].get("logical_op_id") == op:
                    if prior["signature_refs"] == norm_event["signature_refs"]:
                        return str(prior["digest_refs"]["entry_digest"])
                    raise TraceWriterError(
                        REASON_TAMPER_DETECTED, "changed retry for logical operation"
                    )
        explicit_id = norm_event.get("event_id")
        if explicit_id is not None:
            if (
                not isinstance(explicit_id, int)
                or isinstance(explicit_id, bool)
                or explicit_id <= self.last_event_id
            ):
                raise TraceWriterError(
                    REASON_NON_MONOTONIC_EVENT_ID,
                    f"explicit event_id {explicit_id!r} <= previous {self.last_event_id}",
                )
            event_id = explicit_id
        else:
            event_id = self.last_event_id + 1

        payload = norm_event["payload"]
        payload_digest = _compute_payload_digest(payload)
        prev_digest = self.last_entry_digest

        duration_cost = {key: norm_event[key] for key in MEASUREMENTS}

        record: dict[str, Any] = {
            "event_id": event_id,
            "timestamp": time.time()
            if norm_event["timestamp"] is None
            else norm_event["timestamp"],
            "version": PST_TRACE_WRITER_VERSION,
            "actual_backend": norm_event["actual_backend"],
            "raw_outcome": norm_event["raw_outcome"],
            "reconstructability_score": norm_event["reconstructability_score"],
            "linkability_score": norm_event["linkability_score"],
            "reason_code": norm_event["reason_code"],
            "oracle_decision": norm_event["oracle_decision"],
            "duration_cost": duration_cost,
            "signature_refs": norm_event["signature_refs"],
            "payload": payload,
            "digest_refs": {
                "prev_digest": prev_digest,
                "payload_digest": payload_digest,
            },
        }

        entry_digest = _compute_entry_digest(record)
        record["digest_refs"]["entry_digest"] = entry_digest

        line = canonical_json(record)
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())

        self.last_event_id = event_id
        self.last_entry_digest = entry_digest
        return entry_digest

    def write_trace(
        self,
        event: Mapping[str, Any] | TraceEvent,
        *,
        sanitize: bool = True,
    ) -> str:
        """Alias for append."""
        return self.append(event, sanitize=sanitize)

    def verify(self) -> bool:
        """Verify the integrity of this writer's trace file."""
        return verify_trace(self.trace_path)


def write_trace(
    event_or_path: Mapping[str, Any] | TraceEvent | str | Path,
    record_or_path: Mapping[str, Any] | TraceEvent | str | Path | None = None,
    *,
    trace_path: str | Path | None = None,
    actual_backend: str | None = None,
    sanitize: bool = True,
) -> str:
    """Exact target contract: write_trace(event) -> sha256.

    Supports:
    - write_trace(event) -> sha256 (writes to DEFAULT_TRACE_PATH)
    - write_trace(event, trace_path=...) -> sha256
    - write_trace(trace_path, event) -> sha256
    - write_trace(event, trace_path, ...) -> sha256
    """
    target_path: Path
    event_to_write: Mapping[str, Any] | TraceEvent

    if isinstance(event_or_path, str | Path):
        target_path = Path(event_or_path)
        if record_or_path is None or not isinstance(record_or_path, Mapping | TraceEvent):
            raise TraceWriterError(
                REASON_INVALID_RECORD,
                "When first argument is a path, second argument must be event data",
            )
        event_to_write = record_or_path
    elif isinstance(record_or_path, str | Path):
        target_path = Path(record_or_path)
        if not isinstance(event_or_path, Mapping | TraceEvent):
            raise TraceWriterError(
                REASON_INVALID_RECORD,
                "Event data must be a Mapping or TraceEvent",
            )
        event_to_write = event_or_path
    else:
        target_path = Path(trace_path) if trace_path is not None else DEFAULT_TRACE_PATH
        if not isinstance(event_or_path, Mapping | TraceEvent):
            raise TraceWriterError(
                REASON_INVALID_RECORD,
                f"event must be a Mapping or TraceEvent, got {type(event_or_path).__name__}",
            )
        event_to_write = event_or_path

    writer = TraceWriter(target_path, actual_backend=actual_backend or "UNKNOWN")
    return writer.append(event_to_write, sanitize=sanitize)


def read_trace(trace_path: str | Path) -> list[dict[str, Any]]:
    """Decode JSONL records. Use verify_trace before trusting their contents."""
    path = Path(trace_path)
    if not path.is_file():
        raise TraceWriterError(REASON_EMPTY_TRACE, f"Trace file does not exist: {path}")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise TraceWriterError(REASON_EMPTY_TRACE, f"Trace file is empty: {path}")

    records: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        line_str = line.strip()
        if not line_str:
            continue
        try:
            record = json.loads(line_str)
        except json.JSONDecodeError as exc:
            raise TraceWriterError(
                REASON_CORRUPTED_TRACE, f"Line {idx} invalid JSON: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise TraceWriterError(REASON_CORRUPTED_TRACE, f"Line {idx} record is not a dict")
        records.append(record)

    return records


def verify_trace_details(trace_path: str | Path) -> tuple[bool, str]:
    """Inspect trace file and return (is_valid, reason_message).

    Verifies:
    1. File exists and is non-empty.
    2. Every line is valid JSON with all required fields.
    3. Strictly monotonic event_ids starting from >= 1.
    4. Reconstructability and linkability scores are finite floats in [0.0, 1.0].
    5. Valid cryptographic hash chain (prev_digest link and entry_digest verification).
    6. Payload digest verification.
    7. Complete absence of unredacted credentials and PHI.
    """
    path = Path(trace_path)
    if not path.is_file():
        return False, f"{REASON_EMPTY_TRACE}: file does not exist: {path}"

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"IO_ERROR: failed to read file: {exc}"

    if not content.endswith("\n") and content:
        return False, f"{REASON_CORRUPTED_TRACE}: incomplete final line"
    if not content.strip():
        return False, f"{REASON_EMPTY_TRACE}: trace file is empty: {path}"

    lines = content.splitlines()
    records: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        line_str = line.strip()
        if not line_str:
            continue
        try:
            record = json.loads(line_str)
        except json.JSONDecodeError as exc:
            return False, f"{REASON_CORRUPTED_TRACE}: line {idx} invalid JSON: {exc}"
        if not isinstance(record, dict):
            return False, f"{REASON_CORRUPTED_TRACE}: line {idx} is not a JSON object"
        records.append(record)

    if not records:
        return False, f"{REASON_EMPTY_TRACE}: trace file contains no records"

    required_fields = (
        "event_id",
        "raw_outcome",
        "reconstructability_score",
        "linkability_score",
        "reason_code",
        "oracle_decision",
        "actual_backend",
        "duration_cost",
        "digest_refs",
    )

    last_event_id = 0
    expected_prev = GENESIS_PREV_DIGEST

    for idx, record in enumerate(records, start=1):
        # 1. Required fields
        for field in required_fields:
            if field not in record:
                return (
                    False,
                    f"{REASON_CORRUPTED_TRACE}: line {idx} missing required field '{field}'",
                )

        # 2. Monotonic event_id
        event_id = record["event_id"]
        if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id <= last_event_id:
            return (
                False,
                f"{REASON_NON_MONOTONIC_EVENT_ID}: line {idx} event_id {event_id!r} <= previous {last_event_id}",
            )
        last_event_id = event_id

        # 3. Score ranges [0.0, 1.0]
        rec_score = record["reconstructability_score"]
        if rec_score is not None and (
            isinstance(rec_score, bool)
            or not isinstance(rec_score, int | float)
            or not math.isfinite(float(rec_score))
            or not (0.0 <= float(rec_score) <= 1.0)
        ):
            return (
                False,
                f"{REASON_SCORE_OUT_OF_RANGE}: line {idx} reconstructability_score {rec_score!r} outside [0.0, 1.0]",
            )

        link_score = record["linkability_score"]
        if link_score is not None and (
            isinstance(link_score, bool)
            or not isinstance(link_score, int | float)
            or not math.isfinite(float(link_score))
            or not (0.0 <= float(link_score) <= 1.0)
        ):
            return (
                False,
                f"{REASON_SCORE_OUT_OF_RANGE}: line {idx} linkability_score {link_score!r} outside [0.0, 1.0]",
            )

        # 4. Allowed raw outcome
        outcome = record["raw_outcome"]
        if not isinstance(outcome, str) or outcome not in ALLOWED_OUTCOMES:
            return (
                False,
                f"{REASON_CORRUPTED_TRACE}: line {idx} unknown raw_outcome: {outcome!r}",
            )

        # 5. Digest references structure
        digests = record.get("digest_refs")
        if not isinstance(digests, dict):
            return (
                False,
                f"{REASON_CORRUPTED_TRACE}: line {idx} 'digest_refs' is not a mapping",
            )
        for dkey in ("prev_digest", "payload_digest", "entry_digest"):
            if dkey not in digests or not isinstance(digests[dkey], str):
                return (
                    False,
                    f"{REASON_CORRUPTED_TRACE}: line {idx} missing or non-string '{dkey}'",
                )

        # 6. Check prev_digest chain link
        prev_digest = digests["prev_digest"]
        if prev_digest != expected_prev:
            return (
                False,
                f"{REASON_CHAIN_INTEGRITY_BROKEN}: line {idx} prev_digest mismatch (expected {expected_prev}, got {prev_digest})",
            )

        # 7. Check payload digest
        payload = record.get("payload", {})
        payload_digest = digests["payload_digest"]
        recomputed_payload_digest = _compute_payload_digest(payload)
        if recomputed_payload_digest != payload_digest:
            return (
                False,
                f"{REASON_TAMPER_DETECTED}: line {idx} payload digest mismatch (declared {payload_digest}, computed {recomputed_payload_digest})",
            )

        # 8. Check entry digest
        entry_digest = digests["entry_digest"]
        recomputed_entry_digest = _compute_entry_digest(record)
        if recomputed_entry_digest != entry_digest:
            return (
                False,
                f"{REASON_TAMPER_DETECTED}: line {idx} entry digest mismatch (declared {entry_digest}, computed {recomputed_entry_digest})",
            )

        # 9. Check credential and PHI leaks
        leaks = detect_sensitive_leak(record)
        if leaks:
            has_credential = any("CREDENTIAL_LEAK" in item for item in leaks)
            leak_code = (
                REASON_CREDENTIAL_LEAK_DETECTED if has_credential else REASON_PHI_LEAK_DETECTED
            )
            return (
                False,
                f"{leak_code}: line {idx} sensitive leaks: {'; '.join(leaks)}",
            )

        expected_prev = str(entry_digest)

    return True, "OK"


def verify_trace(trace_path: str | Path) -> bool:
    """Verify trace integrity. Returns True if valid, False if tampered or corrupt."""
    is_valid, _reason = verify_trace_details(trace_path)
    return is_valid
