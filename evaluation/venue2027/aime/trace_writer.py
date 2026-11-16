"""AIME-traces — Immutable trace and measurement capture for AIME 2027.

Purpose
-------
Task AIME-traces (Phase P05, venue aime) delivers the append-only JSONL trace writer
and verification engine for the study "Counterfactual Clinical Workflow Safety under
Changing Consent and Medication Histories"
(research/venue2027/VENUES/aime/RESEARCH_BLUEPRINT.md, RQ1-RQ3).

Per the task specification (research/venue2027/VENUES/aime/TASKS/AIME-traces.md):
- Target contract: write_trace(event) -> sha256.
- Append-only JSONL recording with:
  * strictly monotonic event IDs (sequence integer >= 1)
  * raw outcome (from canonical OUTCOME_BUCKETS)
  * clinical safety reason (reason_code)
  * independent oracle decision
  * signature and digest references (cryptographic hash chain)
  * CPU, DB, and model duration/cost metrics
  * actual execution backend identifier
  * sensitive content sanitization (strict check: NO patient identifiers, NO clinical PHI)
- Verification function: verify_trace(trace_path) -> bool.

Allowed input
-------------
Mappings or :class:`TraceRecord` instances containing:
- `raw_outcome` / `outcome`: outcome bucket (ADMIT, REJECT, INDETERMINATE, etc.)
- `clinical_safety_reason` / `reason_code`: stable machine-readable reason code
- `oracle_decision` / `oracle`: oracle decision or truth dictionary
- `actual_backend` / `backend`: execution backend identifier
- CPU/DB/model durations and costs (seconds / cost floats)
- optional `signature_refs` / `signature_ref` / `pair_digest`
- optional `event_id` (must be strictly monotonic if explicitly supplied)
- optional non-PHI payload metadata
Harness pair result dictionaries from :mod:`evaluation.venue2027._shared.harness`
are directly accepted and mapped automatically.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes (:class:`TraceWriterError`):
- `NON_MONOTONIC_EVENT_ID` — event ID sequence is not strictly increasing.
- `UNSANITIZED_PHI_REJECTED` — record contains raw PHI or patient identifiers.
- `PHI_FIELD_PRESENT` — alias for detected PHI marker.
- `TAMPER_DETECTED` — record digest or payload hash does not match content.
- `CHAIN_INTEGRITY_BROKEN` — prev_digest chain link does not match previous entry digest.
- `CORRUPTED_TRACE` — trace file contains non-JSON lines or missing required fields.
- `EMPTY_TRACE` — trace file is empty or does not exist.
- `INVALID_RECORD` — input record is malformed or invalid type.
- `TRACE_FILE_ERROR` — file I/O or path resolution failure.

Version
-------
`AIME_TRACE_WRITER_VERSION = "1.0.0"`.
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

AIME_TRACE_WRITER_VERSION: Final[str] = "1.0.0"

GENESIS_PREV_DIGEST: Final[str] = "0" * 64
DEFAULT_TRACE_PATH: Final[Path] = Path("research/venue2027/proof/artifacts/aime_trace_sample.jsonl")

# Canonical outcome buckets from shared harness (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4).
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
REASON_UNSANITIZED_PHI_REJECTED: Final[str] = "UNSANITIZED_PHI_REJECTED"
REASON_PHI_FIELD_PRESENT: Final[str] = "PHI_FIELD_PRESENT"
REASON_TAMPER_DETECTED: Final[str] = "TAMPER_DETECTED"
REASON_CHAIN_INTEGRITY_BROKEN: Final[str] = "CHAIN_INTEGRITY_BROKEN"
REASON_CORRUPTED_TRACE: Final[str] = "CORRUPTED_TRACE"
REASON_EMPTY_TRACE: Final[str] = "EMPTY_TRACE"
REASON_INVALID_RECORD: Final[str] = "INVALID_RECORD"
REASON_TRACE_FILE_ERROR: Final[str] = "TRACE_FILE_ERROR"

# Exact patient identifier keys
PATIENT_IDENTIFIER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "patient_id",
        "patient_identifier",
        "patient",
        "patient_name",
        "subject_name",
        "mrn",
        "medical_record_number",
        "ssn",
        "social_security",
        "social_security_number",
        "national_id",
        "citizen_id",
        "identity_card",
        "cmnd",
        "cccd",
        "passport",
        "passport_number",
        "so_ho_chieu",
        "insurance_id",
        "insurance_number",
        "health_insurance_id",
        "bhyt",
        "so_bhyt",
        "dob",
        "date_of_birth",
        "birth_date",
        "birthdate",
        "ngay_sinh",
    }
)

# Demographic PII keys
DEMOGRAPHIC_PII_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "ho_va_ten",
        "email",
        "user_email",
        "patient_email",
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "so_dien_thoai",
        "address",
        "street_address",
        "home_address",
        "dia_chi",
        "zip_code",
        "postal_code",
    }
)

# Credential keys
CREDENTIAL_KEYS: Final[frozenset[str]] = frozenset(
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

ALL_SENSITIVE_KEYS: Final[frozenset[str]] = (
    PATIENT_IDENTIFIER_KEYS | DEMOGRAPHIC_PII_KEYS | CREDENTIAL_KEYS
)

PHI_SUBSTRING_MARKERS: Final[tuple[str, ...]] = (
    "patient_id",
    "patient_name",
    "patient_ident",
    "medical_record",
    "national_id",
    "passport",
    "insurance_id",
    "date_of_birth",
)

# Regex patterns for sensitive text content
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_API_KEY_RE = re.compile(r"(?:sk|pk|ghp|key|api)-[A-Za-z0-9_\-]{16,}", re.IGNORECASE)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN[ A-Z_-]*PRIVATE KEY-----.*?-----END[ A-Z_-]*PRIVATE KEY-----",
    re.DOTALL,
)
_CREDENTIAL_KV_RE = re.compile(
    r"(?:password|secret|api_key|access_token|auth_token)\s*[:=]\s*['\"]?([^\s'\";,}]+)",
    re.IGNORECASE,
)


class TraceWriterError(ValueError):
    """Stable, machine-readable trace writer and verification failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def canonical_json(data: Any) -> str:
    """Format data as deterministic, sorted, whitespace-compact JSON."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def detect_phi(record: Any, prefix: str = "") -> list[str]:
    """Recursively inspect a record for patient identifiers, clinical PHI, and credentials.

    Returns a list of leak descriptions if any unredacted sensitive markers are found.
    """
    leaks: list[str] = []

    if isinstance(record, Mapping):
        for raw_k, raw_v in record.items():
            key_str = str(raw_k).lower().strip()
            path_key = f"{prefix}.{raw_k}" if prefix else str(raw_k)

            # Check if key is sensitive denylist and value is not a redaction marker
            if key_str in PATIENT_IDENTIFIER_KEYS:
                if not (isinstance(raw_v, str) and raw_v.startswith(("[REDACTED", "sub-"))):
                    leaks.append(f"PATIENT_IDENTIFIER_LEAK at '{path_key}'")
            elif key_str in DEMOGRAPHIC_PII_KEYS:
                if not (isinstance(raw_v, str) and raw_v.startswith(("[REDACTED", "sub-"))):
                    leaks.append(f"DEMOGRAPHIC_PII_LEAK at '{path_key}'")
            elif key_str in CREDENTIAL_KEYS:
                if not (isinstance(raw_v, str) and raw_v.startswith("[REDACTED")):
                    leaks.append(f"CREDENTIAL_LEAK at '{path_key}'")
            elif any(marker in key_str for marker in PHI_SUBSTRING_MARKERS):
                if not (isinstance(raw_v, str) and raw_v.startswith(("[REDACTED", "sub-"))):
                    leaks.append(f"PHI_MARKER_LEAK at '{path_key}'")
            else:
                leaks.extend(detect_phi(raw_v, prefix=path_key))

    elif isinstance(record, Sequence) and not isinstance(record, str | bytes):
        for idx, item in enumerate(record):
            path_key = f"{prefix}[{idx}]"
            leaks.extend(detect_phi(item, prefix=path_key))

    elif isinstance(record, str):
        val_str = record.strip()
        if val_str.startswith(("[REDACTED", "sub-")):
            return leaks

        if _PRIVATE_KEY_RE.search(val_str):
            leaks.append(f"CREDENTIAL_LEAK at '{prefix}': matches private key pattern")
        elif _BEARER_RE.search(val_str) and "Bearer [REDACTED" not in val_str:
            leaks.append(f"CREDENTIAL_LEAK at '{prefix}': matches bearer token pattern")
        elif _API_KEY_RE.search(val_str):
            leaks.append(f"CREDENTIAL_LEAK at '{prefix}': matches API key pattern")
        elif _CREDENTIAL_KV_RE.search(val_str):
            leaks.append(f"CREDENTIAL_LEAK at '{prefix}': matches credential assignment pattern")
        elif _SSN_RE.search(val_str):
            leaks.append(f"PHI_LEAK at '{prefix}': matches SSN pattern")
        elif _CREDIT_CARD_RE.search(val_str):
            leaks.append(f"PII_LEAK at '{prefix}': matches credit card pattern")
        elif _EMAIL_RE.search(val_str):
            leaks.append(f"PII_LEAK at '{prefix}': matches email pattern")
        elif _PHONE_RE.search(val_str):
            leaks.append(f"PII_LEAK at '{prefix}': matches phone number pattern")

    return leaks


def sanitize_sensitive_data(
    value: Any,
    *,
    salt: str = "aime_trace_salt",
) -> Any:
    """Recursively scrub patient identifiers, clinical PHI, and credentials.

    - Transforms `patient_id` / `patient` to opaque deterministic subject token `sub-<16 hex>`.
    - Redacts patient identifiers and demographic PII with `[REDACTED_PHI]`.
    - Redacts credentials with `[REDACTED_CREDENTIAL]`.
    - Redacts regex patterns in strings.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_k, raw_v in value.items():
            k_norm = str(raw_k).strip().lower()

            if k_norm in {"patient_id", "patient_identifier", "patient"}:
                if raw_v is not None:
                    token = hashlib.sha256(f"{raw_v}:{salt}".encode()).hexdigest()[:16]
                    sanitized[str(raw_k)] = f"sub-{token}"
                continue

            if k_norm in PATIENT_IDENTIFIER_KEYS or k_norm in DEMOGRAPHIC_PII_KEYS:
                sanitized[str(raw_k)] = "[REDACTED_PHI]"
            elif k_norm in CREDENTIAL_KEYS:
                sanitized[str(raw_k)] = "[REDACTED_CREDENTIAL]"
            elif any(marker in k_norm for marker in PHI_SUBSTRING_MARKERS):
                sanitized[str(raw_k)] = "[REDACTED_PHI]"
            else:
                sanitized[str(raw_k)] = sanitize_sensitive_data(raw_v, salt=salt)
        return sanitized

    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [sanitize_sensitive_data(item, salt=salt) for item in value]

    if isinstance(value, str):
        if value.startswith(("[REDACTED", "sub-")):
            return value

        cleaned = value
        if _PRIVATE_KEY_RE.search(cleaned):
            cleaned = _PRIVATE_KEY_RE.sub("[REDACTED_CREDENTIAL]", cleaned)
        if _BEARER_RE.search(cleaned):
            cleaned = _BEARER_RE.sub("Bearer [REDACTED_CREDENTIAL]", cleaned)
        if _API_KEY_RE.search(cleaned):
            cleaned = _API_KEY_RE.sub("[REDACTED_CREDENTIAL]", cleaned)
        if _CREDENTIAL_KV_RE.search(cleaned):
            cleaned = _CREDENTIAL_KV_RE.sub(
                lambda m: m.group(0).replace(m.group(1), "[REDACTED_CREDENTIAL]"), cleaned
            )
        if _SSN_RE.search(cleaned):
            cleaned = _SSN_RE.sub("[REDACTED_PHI]", cleaned)
        if _CREDIT_CARD_RE.search(cleaned):
            cleaned = _CREDIT_CARD_RE.sub("[REDACTED_PII]", cleaned)
        if _EMAIL_RE.search(cleaned):
            cleaned = _EMAIL_RE.sub("[REDACTED_PII]", cleaned)
        if _PHONE_RE.search(cleaned):
            cleaned = _PHONE_RE.sub("[REDACTED_PII]", cleaned)

        return cleaned

    return value


def sanitize_record(
    record: Mapping[str, Any],
    *,
    salt: str = "aime_trace_salt",
) -> dict[str, Any]:
    """Produce a sanitized copy of a record dictionary."""
    sanitized = sanitize_sensitive_data(record, salt=salt)
    if isinstance(sanitized, dict):
        return sanitized
    return dict(sanitized)


@dataclasses.dataclass(frozen=True)
class TraceRecord:
    """Strongly-typed representation of an immutable AIME trace event."""

    event_id: int = 0
    raw_outcome: str = "ADMIT"
    clinical_safety_reason: str = "RULE_STABLE_HISTORY"
    reason_code: str = ""
    oracle_decision: dict[str, Any] | str = dataclasses.field(default_factory=dict)
    actual_backend: str = "aime_clinical_workflow"
    duration_seconds: float = 0.0
    cpu_duration_seconds: float = 0.0
    db_duration_seconds: float = 0.0
    model_duration_seconds: float = 0.0
    cpu_cost: float = 0.0
    db_cost: float = 0.0
    model_cost: float = 0.0
    model_cost_usd: float = 0.0
    signature_refs: dict[str, Any] = dataclasses.field(default_factory=dict)
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)
    recorded_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        reason = self.reason_code or self.clinical_safety_reason
        return {
            "event_id": self.event_id,
            "raw_outcome": self.raw_outcome,
            "clinical_safety_reason": self.clinical_safety_reason or reason,
            "reason_code": reason,
            "oracle_decision": self.oracle_decision,
            "actual_backend": self.actual_backend,
            "duration_seconds": self.duration_seconds,
            "cpu_duration_seconds": self.cpu_duration_seconds,
            "db_duration_seconds": self.db_duration_seconds,
            "model_duration_seconds": self.model_duration_seconds,
            "cpu_cost": self.cpu_cost,
            "db_cost": self.db_cost,
            "model_cost": self.model_cost or self.model_cost_usd,
            "model_cost_usd": self.model_cost_usd or self.model_cost,
            "signature_refs": self.signature_refs,
            "payload": self.payload,
            "recorded_at": self.recorded_at,
        }


def _normalize_event(event: Mapping[str, Any] | TraceRecord) -> dict[str, Any]:
    """Normalize event mapping or TraceRecord to standard field mapping."""
    if isinstance(event, TraceRecord):
        raw = event.to_dict()
    elif isinstance(event, Mapping):
        raw = dict(event)
    else:
        raise TraceWriterError(
            REASON_INVALID_RECORD,
            f"record must be Mapping or TraceRecord, got {type(event).__name__}",
        )

    # 1. Outcome extraction & canonicalization
    outcome = (
        raw.get("raw_outcome")
        or raw.get("observed_outcome")
        or (
            raw.get("outcome", {}).get("observed_outcome")
            if isinstance(raw.get("outcome"), Mapping)
            else None
        )
        or raw.get("outcome")
        or "ADMIT"
    )
    if isinstance(outcome, str):
        outcome = outcome.strip().upper()
    else:
        outcome = "INDETERMINATE"
    if outcome not in ALLOWED_OUTCOMES:
        outcome = "INVALID_RESULT"

    # 2. Clinical safety reason / reason code
    reason = (
        raw.get("clinical_safety_reason")
        or raw.get("reason_code")
        or raw.get("reason")
        or (
            raw.get("outcome", {}).get("reason_code")
            if isinstance(raw.get("outcome"), Mapping)
            else None
        )
        or (
            raw.get("outcome", {}).get("detail")
            if isinstance(raw.get("outcome"), Mapping)
            else None
        )
        or "RULE_STABLE_HISTORY"
    )

    # 3. Oracle decision
    oracle_raw = raw.get("oracle_decision")
    if oracle_raw is None:
        oracle_raw = raw.get("oracle")
    if oracle_raw is None:
        oracle_decision: dict[str, Any] | str = "NONE"
    elif isinstance(oracle_raw, Mapping):
        oracle_decision = dict(oracle_raw)
    else:
        oracle_decision = str(oracle_raw)

    # 4. Actual backend
    backend = str(raw.get("actual_backend") or raw.get("backend") or "aime_clinical_workflow")

    # 5. Timing and costs
    cpu_dur = float(raw.get("cpu_duration_seconds", raw.get("cpu_duration", 0.0)))
    db_dur = float(raw.get("db_duration_seconds", raw.get("db_duration", 0.0)))
    model_dur = float(raw.get("model_duration_seconds", raw.get("model_duration", 0.0)))
    duration = float(
        raw.get(
            "duration_seconds",
            raw.get("duration", cpu_dur + db_dur + model_dur),
        )
    )

    cpu_cost = float(raw.get("cpu_cost", 0.0))
    db_cost = float(raw.get("db_cost", 0.0))
    model_cost = float(raw.get("model_cost_usd", raw.get("model_cost", 0.0)))

    # 6. Signature references
    sig_refs: dict[str, Any] = {}
    if isinstance(raw.get("signature_refs"), Mapping):
        sig_refs.update(raw["signature_refs"])
    elif "signature_ref" in raw and raw["signature_ref"]:
        sig_refs["signature_ref"] = str(raw["signature_ref"])
    if "pair_digest" in raw and raw["pair_digest"]:
        sig_refs["pair_digest"] = str(raw["pair_digest"])
    if "source_commit" in raw and raw["source_commit"]:
        sig_refs["source_commit"] = str(raw["source_commit"])

    # 7. Payload
    payload: dict[str, Any] = {}
    if isinstance(raw.get("payload"), Mapping):
        payload.update(raw["payload"])
    elif isinstance(raw.get("detail"), Mapping):
        payload.update(raw["detail"])

    standard_keys = {
        "event_id",
        "prev_digest",
        "entry_digest",
        "event_digest",
        "recorded_at",
        "timestamp",
        "raw_outcome",
        "observed_outcome",
        "outcome",
        "clinical_safety_reason",
        "reason_code",
        "reason",
        "oracle_decision",
        "oracle",
        "actual_backend",
        "backend",
        "duration_seconds",
        "duration",
        "cpu_duration_seconds",
        "cpu_duration",
        "db_duration_seconds",
        "db_duration",
        "model_duration_seconds",
        "model_duration",
        "cpu_cost",
        "db_cost",
        "model_cost",
        "model_cost_usd",
        "duration_cost",
        "signature_refs",
        "signature_ref",
        "signature",
        "pair_digest",
        "source_commit",
        "digest_refs",
        "payload",
        "detail",
    }
    for k, v in raw.items():
        if k not in standard_keys:
            payload[k] = v

    return {
        "event_id": raw.get("event_id"),
        "raw_outcome": outcome,
        "clinical_safety_reason": str(reason),
        "reason_code": str(reason),
        "oracle_decision": oracle_decision,
        "actual_backend": backend,
        "duration_seconds": round(duration, 6),
        "cpu_duration_seconds": round(cpu_dur, 6),
        "db_duration_seconds": round(db_dur, 6),
        "model_duration_seconds": round(model_dur, 6),
        "cpu_cost": round(cpu_cost, 6),
        "db_cost": round(db_cost, 6),
        "model_cost": round(model_cost, 6),
        "model_cost_usd": round(model_cost, 6),
        "signature_refs": sig_refs,
        "payload": payload,
        "recorded_at": raw.get("recorded_at", raw.get("timestamp")),
    }


def _compute_entry_digest(record: Mapping[str, Any], prev_digest: str, payload_digest: str) -> str:
    """Compute deterministic SHA-256 over record content excluding entry_digest."""
    record_for_digest = {
        k: v for k, v in record.items() if k not in ("digest_refs", "event_digest")
    }
    record_for_digest["prev_digest"] = prev_digest
    record_for_digest["digest_refs"] = {
        "payload_digest": payload_digest,
        "prev_digest": prev_digest,
    }
    return hashlib.sha256(canonical_json(record_for_digest).encode("utf-8")).hexdigest()


class TraceWriter:
    """Append-only, tamper-evident JSONL trace writer for AIME studies."""

    def __init__(
        self,
        trace_path: str | Path,
        *,
        actual_backend: str = "aime_clinical_workflow",
        auto_flush: bool = True,
    ) -> None:
        self.trace_path = Path(trace_path)
        self.actual_backend = actual_backend
        self.auto_flush = auto_flush
        self._last_event_id = 0
        self._last_digest = GENESIS_PREV_DIGEST
        self._init_state()

    def _init_state(self) -> None:
        """Read existing trace file if present to recover monotonic sequence and chain link."""
        if not self.trace_path.is_file():
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
                    REASON_CORRUPTED_TRACE,
                    f"line {line_no} is not valid JSON: {exc}",
                ) from exc

            if not isinstance(rec, Mapping):
                raise TraceWriterError(
                    REASON_CORRUPTED_TRACE,
                    f"line {line_no} record is not a JSON object",
                )

            event_id = rec.get("event_id")
            if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id <= last_id:
                raise TraceWriterError(
                    REASON_NON_MONOTONIC_EVENT_ID,
                    f"line {line_no} event_id {event_id} is not strictly greater than {last_id}",
                )
            last_id = event_id

            digest_refs = rec.get("digest_refs")
            if isinstance(digest_refs, Mapping) and "entry_digest" in digest_refs:
                last_digest = str(digest_refs["entry_digest"])
            elif "event_digest" in rec:
                last_digest = str(rec["event_digest"])
            else:
                raise TraceWriterError(
                    REASON_CORRUPTED_TRACE,
                    f"line {line_no} is missing digest_refs.entry_digest",
                )

        self._last_event_id = last_id
        self._last_digest = last_digest

    def append(
        self,
        event: Mapping[str, Any] | TraceRecord,
        *,
        sanitize: bool = False,
    ) -> str:
        """Append one record to trace JSONL; returns the entry SHA-256 digest."""
        normalized = _normalize_event(event)

        # Sanitization & PHI check
        if sanitize:
            normalized["payload"] = sanitize_sensitive_data(normalized["payload"])
            normalized["signature_refs"] = sanitize_sensitive_data(normalized["signature_refs"])
            if isinstance(normalized["oracle_decision"], Mapping):
                normalized["oracle_decision"] = sanitize_sensitive_data(
                    normalized["oracle_decision"]
                )

        phi_hits = detect_phi(normalized)
        if phi_hits:
            raise TraceWriterError(
                REASON_UNSANITIZED_PHI_REJECTED,
                f"unsanitized PHI field rejected: {phi_hits}",
            )

        # Monotonic event ID enforcement
        explicit_eid = normalized.get("event_id")
        if explicit_eid is not None:
            if not isinstance(explicit_eid, int) or isinstance(explicit_eid, bool):
                raise TraceWriterError(
                    REASON_INVALID_RECORD,
                    f"event_id must be integer, got {explicit_eid!r}",
                )
            if explicit_eid <= self._last_event_id:
                raise TraceWriterError(
                    REASON_NON_MONOTONIC_EVENT_ID,
                    f"non-monotonic event ID refused: {explicit_eid} <= {self._last_event_id}",
                )
            event_id = explicit_eid
        else:
            event_id = self._last_event_id + 1

        recorded_at = normalized["recorded_at"]
        if recorded_at is None or not isinstance(recorded_at, int | float):
            recorded_at = round(time.time(), 6)
        else:
            recorded_at = round(float(recorded_at), 6)

        actual_backend = (
            self.actual_backend
            if self.actual_backend != "aime_clinical_workflow"
            and normalized["actual_backend"] == "aime_clinical_workflow"
            else normalized["actual_backend"]
        )

        payload_digest = hashlib.sha256(
            canonical_json(normalized["payload"]).encode("utf-8")
        ).hexdigest()
        prev_digest = self._last_digest

        duration_cost = {
            "duration_seconds": normalized["duration_seconds"],
            "cpu_duration_seconds": normalized["cpu_duration_seconds"],
            "db_duration_seconds": normalized["db_duration_seconds"],
            "model_duration_seconds": normalized["model_duration_seconds"],
            "cpu_cost": normalized["cpu_cost"],
            "db_cost": normalized["db_cost"],
            "model_cost": normalized["model_cost"],
            "model_cost_usd": normalized["model_cost_usd"],
        }

        record: dict[str, Any] = {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "raw_outcome": normalized["raw_outcome"],
            "clinical_safety_reason": normalized["clinical_safety_reason"],
            "reason_code": normalized["reason_code"],
            "oracle_decision": normalized["oracle_decision"],
            "actual_backend": actual_backend,
            "duration_seconds": normalized["duration_seconds"],
            "cpu_duration_seconds": normalized["cpu_duration_seconds"],
            "db_duration_seconds": normalized["db_duration_seconds"],
            "model_duration_seconds": normalized["model_duration_seconds"],
            "cpu_cost": normalized["cpu_cost"],
            "db_cost": normalized["db_cost"],
            "model_cost": normalized["model_cost"],
            "model_cost_usd": normalized["model_cost_usd"],
            "duration_cost": duration_cost,
            "signature_refs": normalized["signature_refs"],
            "digest_refs": {
                "payload_digest": payload_digest,
                "prev_digest": prev_digest,
            },
            "payload": normalized["payload"],
        }

        record["prev_digest"] = prev_digest
        entry_digest = _compute_entry_digest(record, prev_digest, payload_digest)
        record["digest_refs"]["entry_digest"] = entry_digest
        record["event_digest"] = entry_digest

        line = canonical_json(record) + "\n"
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.trace_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                if self.auto_flush:
                    fh.flush()
        except OSError as exc:
            raise TraceWriterError(
                REASON_TRACE_FILE_ERROR,
                f"failed to append to {self.trace_path}: {exc}",
            ) from exc

        self._last_event_id = event_id
        self._last_digest = entry_digest
        return entry_digest

    def write_trace(
        self,
        event: Mapping[str, Any] | TraceRecord,
        *,
        sanitize: bool = False,
    ) -> str:
        """Alias for append matching the write_trace method naming."""
        return self.append(event, sanitize=sanitize)

    def verify(self) -> bool:
        """Verify the trace file managed by this writer."""
        return verify_trace(self.trace_path)


def write_trace(
    trace_path_or_event: str | Path | Mapping[str, Any] | TraceRecord,
    event: Mapping[str, Any] | TraceRecord | None = None,
    *,
    trace_path: str | Path | None = None,
    actual_backend: str | None = None,
    sanitize: bool = False,
) -> str:
    """Exact target contract: write_trace(event) -> sha256.

    Supports:
    - write_trace(event) -> writes to DEFAULT_TRACE_PATH
    - write_trace(event, trace_path=path)
    - write_trace(path, event)
    """
    target_path: Path
    payload: Mapping[str, Any] | TraceRecord

    if isinstance(trace_path_or_event, str | Path):
        target_path = Path(trace_path_or_event)
        if event is None:
            raise TraceWriterError(
                REASON_INVALID_RECORD,
                "missing event parameter when trace_path is provided as first argument",
            )
        payload = event
    elif isinstance(trace_path_or_event, Mapping | TraceRecord):
        payload = trace_path_or_event
        target_path = Path(trace_path) if trace_path is not None else DEFAULT_TRACE_PATH
    else:
        raise TraceWriterError(
            REASON_INVALID_RECORD,
            f"unsupported first argument: {type(trace_path_or_event).__name__}",
        )

    backend = actual_backend or "aime_clinical_workflow"
    writer = TraceWriter(target_path, actual_backend=backend)
    return writer.append(payload, sanitize=sanitize)


def verify_trace_details(trace_path: str | Path) -> tuple[bool, list[str]]:
    """Inspect trace file and return (is_valid, list_of_defects).

    Verifies:
    1. File exists and contains valid JSON lines.
    2. Strictly monotonic event IDs starting from >= 1.
    3. Unbroken cryptographic digest chain (prev_digest link).
    4. Deterministic SHA-256 entry digest and payload digest on every line.
    5. Absence of unsanitized PHI, patient identifiers, or credentials.
    6. Canonical outcome and required fields presence.
    """
    path = Path(trace_path)
    defects: list[str] = []
    if not path.is_file():
        return False, [f"{REASON_EMPTY_TRACE}: file does not exist: {path}"]

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, [f"{REASON_TRACE_FILE_ERROR}: failed to read file: {exc}"]

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return False, [f"{REASON_EMPTY_TRACE}: trace contains no records"]

    expected_prev = GENESIS_PREV_DIGEST
    last_event_id = 0

    required_fields = (
        "event_id",
        "recorded_at",
        "raw_outcome",
        "clinical_safety_reason",
        "oracle_decision",
        "actual_backend",
        "digest_refs",
    )

    for idx, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            defects.append(f"{REASON_CORRUPTED_TRACE}: line {idx} is invalid JSON: {exc}")
            continue

        if not isinstance(record, Mapping):
            defects.append(f"{REASON_CORRUPTED_TRACE}: line {idx} record is not a JSON object")
            continue

        for field in required_fields:
            if field not in record:
                defects.append(
                    f"{REASON_CORRUPTED_TRACE}: line {idx} missing required field '{field}'"
                )

        # 1. Monotonic event ID
        eid = record.get("event_id")
        if not isinstance(eid, int) or isinstance(eid, bool):
            defects.append(
                f"{REASON_NON_MONOTONIC_EVENT_ID}: line {idx} event_id is not integer: {eid!r}"
            )
        elif eid <= last_event_id:
            defects.append(
                f"{REASON_NON_MONOTONIC_EVENT_ID}: line {idx} event_id {eid} <= {last_event_id}"
            )
        else:
            last_event_id = eid

        # 2. Canonical outcome
        outcome = record.get("raw_outcome")
        if outcome not in ALLOWED_OUTCOMES:
            defects.append(f"{REASON_CORRUPTED_TRACE}: line {idx} invalid raw_outcome '{outcome}'")

        # 3. Digest refs and hash chain
        digest_refs = record.get("digest_refs")
        if not isinstance(digest_refs, Mapping):
            defects.append(f"{REASON_CORRUPTED_TRACE}: line {idx} digest_refs is not a mapping")
            continue

        entry_digest = digest_refs.get("entry_digest")
        prev_digest = digest_refs.get("prev_digest")
        payload_digest = digest_refs.get("payload_digest")

        if not entry_digest or not prev_digest or not payload_digest:
            defects.append(f"{REASON_CORRUPTED_TRACE}: line {idx} incomplete digest_refs")
            continue

        if prev_digest != expected_prev:
            defects.append(
                f"{REASON_CHAIN_INTEGRITY_BROKEN}: line {idx} prev_digest '{prev_digest}' "
                f"!= expected '{expected_prev}'"
            )

        payload = record.get("payload", {})
        recomputed_payload_digest = hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()
        if recomputed_payload_digest != payload_digest:
            defects.append(
                f"{REASON_TAMPER_DETECTED}: line {idx} payload digest mismatch: "
                f"recorded {payload_digest} != computed {recomputed_payload_digest}"
            )

        recomputed_entry_digest = _compute_entry_digest(
            record, str(prev_digest), str(payload_digest)
        )
        if recomputed_entry_digest != entry_digest:
            defects.append(
                f"{REASON_TAMPER_DETECTED}: line {idx} entry digest mismatch: "
                f"recorded {entry_digest} != computed {recomputed_entry_digest}"
            )

        # 4. Strict PHI check
        phi_leaks = detect_phi(record)
        if phi_leaks:
            defects.append(
                f"{REASON_UNSANITIZED_PHI_REJECTED}: line {idx} PHI/PII present: {'; '.join(phi_leaks)}"
            )

        expected_prev = str(entry_digest)

    return len(defects) == 0, defects


def verify_trace(trace_path: str | Path) -> bool:
    """Verify trace integrity: monotonicity of event IDs, unbroken digest chain, and no PHI.

    Returns True if valid, False if tampered, corrupted, non-monotonic, or contains PHI.
    """
    ok, _ = verify_trace_details(trace_path)
    return ok


def read_trace(trace_path: str | Path) -> list[dict[str, Any]]:
    """Read all records from a verified trace file."""
    path = Path(trace_path)
    if not path.is_file():
        raise TraceWriterError(REASON_EMPTY_TRACE, f"trace file does not exist: {path}")

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line_str = line.strip()
        if line_str:
            records.append(json.loads(line_str))
    return records
