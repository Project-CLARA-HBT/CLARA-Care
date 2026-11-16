"""DIMVA-traces — Immutable trace and measurement capture for DIMVA 2027.

Purpose
-------
Task DIMVA-traces (Phase P05, venue dimva) delivers the append-only JSONL trace writer
and verification engine for the study "GovernanceTrace: Detecting Adaptive
Authorization-Boundary Probing from Minimal Agent Events"
(research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md, RQ1-RQ3; task contract
research/venue2027/VENUES/dimva/TASKS/DIMVA-traces.md).

Per the task specification:
- Implements the exact target contract: `write_trace(event) -> sha256`.
- Append-only JSONL recording with:
  * strictly monotonic event IDs (sequence 1, 2, 3...)
  * raw outcome (from canonical OUTCOME_BUCKETS: ADMIT, REJECT, INDETERMINATE, etc.)
  * detector score (monotone evidence score bounded strictly in [0.0, 1.0])
  * detection decision (DETECT, NO_DETECT, INDETERMINATE, etc.)
  * reason code (stable machine-readable uppercase string)
  * independent oracle decision (expected verdict / truth label)
  * CPU/DB/model duration and cost metrics (duration_seconds, cpu_duration_seconds, cpu_cost, etc.)
  * actual backend identifier (candidate, B0, B1, B2, B3, etc.)
  * cryptographic hash chain (prev_digest, payload_digest, entry_digest)
  * leak-safe sensitive content sanitization (zero PHI, zero user secrets/credentials)
- Implements `verify_trace(trace_path) -> bool` for tamper, monotonicity, score range [0, 1], and leak detection.

Allowed input
-------------
`event`: A mapping or `TraceEvent` carrying probing detection telemetry. Standard fields:
`raw_outcome`, `detector_score`, `detection_decision`, `reason_code`, `oracle_decision`,
`actual_backend`, `duration_seconds`, `cpu_duration_seconds`, `db_duration_seconds`,
`model_duration_seconds`, `cpu_cost`, `db_cost`, `model_cost_usd`, `signature_refs`,
and `payload`.
Harness `pair_result` dictionaries from `evaluation.venue2027._shared.harness` are
directly accepted and mapped automatically.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes on :class:`TraceWriterError`:
- `NON_MONOTONIC_EVENT_ID` — event ID sequence is not strictly increasing.
- `SCORE_OUT_OF_RANGE` — detector_score is not a finite float in [0.0, 1.0].
- `TAMPER_DETECTED` — record digest or payload hash does not match content.
- `CHAIN_INTEGRITY_BROKEN` — prev_digest chain link does not match previous entry digest.
- `CREDENTIAL_LEAK_DETECTED` — unredacted credential or secret pattern discovered in trace.
- `PHI_LEAK_DETECTED` — unredacted PHI or patient identifier pattern discovered in trace.
- `EMPTY_TRACE` — trace file is empty or does not exist.
- `CORRUPTED_TRACE` — trace file contains non-JSON lines or missing required fields.
- `INVALID_RECORD` — input record is malformed or invalid type.

Version
-------
``DIMVA_TRACE_WRITER_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

DIMVA_TRACE_WRITER_VERSION: Final[str] = "1.0.0"

GENESIS_PREV_DIGEST: Final[str] = "0" * 64
DEFAULT_TRACE_PATH: Final[Path] = Path(
    "research/venue2027/proof/artifacts/dimva_trace_sample.jsonl"
)

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

# Canonical detection decisions for DIMVA probing detector arms
ALLOWED_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "DETECT",
        "NO_DETECT",
        "INDETERMINATE",
        "TIMEOUT",
        "EXECUTION_ERROR",
        "NOT_RUN_EXTERNAL",
        "INVALID_RESULT",
        "UNKNOWN",
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
        "patient_name",
        "patient_id",
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
        "home_address",
        "street_address",
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


def sanitize_sensitive_data(value: Any) -> Any:
    """Recursively scrub credentials and PHI from mappings, lists, and strings.

    Replaces identified credentials with '[REDACTED_CREDENTIAL]' and PHI with '[REDACTED_PHI]'.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_k, raw_v in value.items():
            k_norm = str(raw_k).strip().lower()
            if k_norm in _CREDENTIAL_KEY_DENYLIST:
                sanitized[str(raw_k)] = "[REDACTED_CREDENTIAL]"
            elif k_norm in _PHI_KEY_DENYLIST:
                sanitized[str(raw_k)] = "[REDACTED_PHI]"
            else:
                sanitized[str(raw_k)] = sanitize_sensitive_data(raw_v)
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
                if not (isinstance(raw_v, str) and raw_v.startswith("[REDACTED")):
                    leaks.append(f"CREDENTIAL_LEAK at key '{current_path}'")
            elif k_norm in _PHI_KEY_DENYLIST:
                if not (isinstance(raw_v, str) and raw_v.startswith("[REDACTED")):
                    leaks.append(f"PHI_LEAK at key '{current_path}'")
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
            leaks.append(f"PHI_LEAK at '{path}': matches SSN pattern")
        elif _CREDIT_CARD_PATTERN.search(value):
            leaks.append(f"PHI_LEAK at '{path}': matches credit card pattern")
        elif _EMAIL_PATTERN.search(value):
            leaks.append(f"PHI_LEAK at '{path}': matches email pattern")
        elif _PHONE_PATTERN.search(value):
            leaks.append(f"PHI_LEAK at '{path}': matches phone number pattern")

    return leaks


@dataclasses.dataclass(frozen=True)
class TraceEvent:
    """Input event to record in the append-only DIMVA trace."""

    raw_outcome: str = "INDETERMINATE"
    detector_score: float = 0.0
    detection_decision: str = "INDETERMINATE"
    reason_code: str = "OK"
    oracle_decision: Any = "NONE"
    actual_backend: str = "candidate"
    duration_seconds: float = 0.0
    cpu_duration_seconds: float = 0.0
    db_duration_seconds: float = 0.0
    model_duration_seconds: float = 0.0
    cpu_cost: float = 0.0
    db_cost: float = 0.0
    model_cost_usd: float = 0.0
    signature_refs: dict[str, str] = dataclasses.field(default_factory=dict)
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _extract_score_from_str(text: str) -> float | None:
    """Extract numeric score from detail or text if formatted as 'score=<float>'."""
    if not text or "score=" not in text:
        return None
    try:
        match = re.search(r"score=([0-9eE\.\+\-]+)", text)
        if match:
            val = float(match.group(1))
            return val if math.isfinite(val) else None
    except (ValueError, IndexError):
        pass
    return None


def _normalize_event(
    event: Mapping[str, Any] | TraceEvent,
    default_backend: str = "candidate",
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

    # 1. Detect harness pair_result format
    if data.get("record_kind") == "pair_result":
        outcome_map = data.get("outcome") or {}
        raw_outcome = outcome_map.get("observed_outcome", "INDETERMINATE")
        detail = str(outcome_map.get("detail", "") or "")

        # Score extraction
        score: float = 0.0
        if data.get("detector_score") is not None:
            score = float(data["detector_score"])
        elif data.get("score") is not None:
            score = float(data["score"])
        else:
            extracted = _extract_score_from_str(detail)
            if extracted is not None:
                score = extracted

        # Decision extraction
        decision = str(data.get("detection_decision") or data.get("decision") or "").strip()
        if not decision:
            if raw_outcome == "REJECT":
                decision = "DETECT"
            elif raw_outcome == "ADMIT":
                decision = "NO_DETECT"
            else:
                decision = str(raw_outcome)

        # Reason code extraction
        reason_code = str(data.get("reason_code") or data.get("reason") or "").strip()
        if not reason_code:
            if "|" in detail:
                reason_code = detail.split("|")[0].strip()
            elif detail:
                reason_code = detail
            else:
                reason_code = "OK"

        oracle_dec = data.get("oracle", {})
        backend = str(data.get("arm_id") or default_backend)
        duration_s = float(data.get("duration_seconds", 0.0))
        pair_digest = data.get("pair_digest", "")
        sig_refs = {"pair_digest": str(pair_digest)} if pair_digest else {}
        payload = {k: v for k, v in data.items() if k not in ("outcome", "oracle", "pair_digest")}
        return {
            "raw_outcome": str(raw_outcome).upper(),
            "detector_score": score,
            "detection_decision": decision,
            "reason_code": str(reason_code),
            "oracle_decision": oracle_dec,
            "actual_backend": backend,
            "duration_seconds": duration_s,
            "cpu_duration_seconds": float(data.get("cpu_duration_seconds", duration_s)),
            "db_duration_seconds": float(data.get("db_duration_seconds", 0.0)),
            "model_duration_seconds": float(data.get("model_duration_seconds", 0.0)),
            "cpu_cost": float(data.get("cpu_cost", 0.0)),
            "db_cost": float(data.get("db_cost", 0.0)),
            "model_cost_usd": float(data.get("model_cost_usd", 0.0)),
            "signature_refs": sig_refs,
            "payload": payload,
        }

    # 2. Extract standard raw outcome
    raw_outcome = data.get("raw_outcome") or data.get("outcome") or "INDETERMINATE"
    if isinstance(raw_outcome, Mapping):
        raw_outcome = raw_outcome.get("observed_outcome", "INDETERMINATE")
    raw_outcome_str = str(raw_outcome).upper()
    if raw_outcome_str == "PERMIT":
        raw_outcome_str = "ADMIT"
    elif raw_outcome_str == "DENY":
        raw_outcome_str = "REJECT"

    if raw_outcome_str not in ALLOWED_OUTCOMES:
        raise TraceWriterError(
            REASON_INVALID_RECORD,
            f"raw_outcome {raw_outcome!r} not in {sorted(ALLOWED_OUTCOMES)}",
        )

    # 3. Extract detector score
    score_raw = data.get("detector_score")
    if score_raw is None:
        score_raw = data.get("score")
    if score_raw is None:
        detail_cand = str(data.get("detail", "") or data.get("reason_code", "") or "")
        extracted = _extract_score_from_str(detail_cand)
        score_raw = extracted if extracted is not None else 0.0

    if (
        isinstance(score_raw, bool)
        or not isinstance(score_raw, int | float)
        or not math.isfinite(float(score_raw))
        or not (0.0 <= float(score_raw) <= 1.0)
    ):
        raise TraceWriterError(
            REASON_SCORE_OUT_OF_RANGE,
            f"detector_score {score_raw!r} outside valid range [0.0, 1.0]",
        )
    detector_score = float(score_raw)

    # 4. Extract detection decision
    decision_raw = data.get("detection_decision") or data.get("decision")
    if decision_raw is None:
        if raw_outcome_str == "REJECT":
            decision_raw = "DETECT"
        elif raw_outcome_str == "ADMIT":
            decision_raw = "NO_DETECT"
        else:
            decision_raw = raw_outcome_str
    detection_decision = str(decision_raw).upper()
    if detection_decision not in ALLOWED_DECISIONS:
        detection_decision = str(decision_raw)

    # 5. Extract reason code
    reason_code = data.get("reason_code") or data.get("reason")
    if reason_code is None:
        detail_cand = str(data.get("detail", "") or "")
        if "|" in detail_cand:
            reason_code = detail_cand.split("|")[0].strip()
        elif detail_cand:
            reason_code = detail_cand
        else:
            reason_code = "OK"

    # 6. Extract oracle decision
    oracle_dec = data.get("oracle_decision")
    if oracle_dec is None:
        oracle_dec = data.get("oracle", "NONE")

    backend = str(
        data.get("actual_backend") or data.get("backend") or data.get("arm_id") or default_backend
    )

    # 7. Durations and costs
    dur_cost = data.get("duration_cost")
    if isinstance(dur_cost, Mapping):
        duration_s = float(dur_cost.get("duration_seconds", 0.0))
        cpu_dur = float(dur_cost.get("cpu_duration_seconds", 0.0))
        db_dur = float(dur_cost.get("db_duration_seconds", 0.0))
        model_dur = float(dur_cost.get("model_duration_seconds", 0.0))
        cpu_c = float(dur_cost.get("cpu_cost", 0.0))
        db_c = float(dur_cost.get("db_cost", 0.0))
        model_c = float(dur_cost.get("model_cost_usd", 0.0))
    else:
        duration_s = float(data.get("duration_seconds", 0.0))
        cpu_dur = float(data.get("cpu_duration_seconds", duration_s))
        db_dur = float(data.get("db_duration_seconds", 0.0))
        model_dur = float(data.get("model_duration_seconds", 0.0))
        cpu_c = float(data.get("cpu_cost", 0.0))
        db_c = float(data.get("db_cost", 0.0))
        model_c = float(data.get("model_cost_usd", 0.0))

    sig_refs = data.get("signature_refs", {})
    if not isinstance(sig_refs, dict):
        sig_refs = {"ref": str(sig_refs)}

    # 8. Payload
    payload = data.get("payload")
    if payload is None:
        std_keys = {
            "raw_outcome",
            "outcome",
            "detector_score",
            "score",
            "detection_decision",
            "decision",
            "reason_code",
            "reason",
            "detail",
            "oracle_decision",
            "oracle",
            "actual_backend",
            "backend",
            "arm_id",
            "duration_seconds",
            "cpu_duration_seconds",
            "db_duration_seconds",
            "model_duration_seconds",
            "cpu_cost",
            "db_cost",
            "model_cost_usd",
            "duration_cost",
            "signature_refs",
            "event_id",
        }
        payload = {k: v for k, v in data.items() if k not in std_keys}
    elif not isinstance(payload, dict):
        payload = {"data": payload}

    result = {
        "raw_outcome": raw_outcome_str,
        "detector_score": detector_score,
        "detection_decision": detection_decision,
        "reason_code": str(reason_code),
        "oracle_decision": oracle_dec,
        "actual_backend": backend,
        "duration_seconds": duration_s,
        "cpu_duration_seconds": cpu_dur,
        "db_duration_seconds": db_dur,
        "model_duration_seconds": model_dur,
        "cpu_cost": cpu_c,
        "db_cost": db_c,
        "model_cost_usd": model_c,
        "signature_refs": sig_refs,
        "payload": payload,
    }
    if "event_id" in data:
        result["event_id"] = data["event_id"]
    return result


class TraceWriter:
    """Append-only cryptographic trace writer for DIMVA experiments."""

    def __init__(
        self,
        trace_path: str | Path | None = None,
        *,
        actual_backend: str = "candidate",
        default_backend: str | None = None,
    ) -> None:
        self.trace_path = Path(trace_path) if trace_path is not None else DEFAULT_TRACE_PATH
        self.actual_backend = default_backend or actual_backend
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_event_id: int = 0
        self.last_entry_digest: str = GENESIS_PREV_DIGEST
        self._init_state()

    def _init_state(self) -> None:
        """Scan existing trace file to initialize monotonic ID and digest chain state."""
        if not self.trace_path.is_file() or self.trace_path.stat().st_size == 0:
            self.last_event_id = 0
            self.last_entry_digest = GENESIS_PREV_DIGEST
            return

        records = read_trace(self.trace_path)
        if records:
            last_rec = records[-1]
            self.last_event_id = int(last_rec["event_id"])
            self.last_entry_digest = str(last_rec["digest_refs"]["entry_digest"])

    def append(
        self,
        event: Mapping[str, Any] | TraceEvent,
        *,
        sanitize: bool = True,
    ) -> str:
        """Append an event to the trace file and return the record's entry digest."""
        norm_event = _normalize_event(event, default_backend=self.actual_backend)

        if sanitize:
            norm_event = sanitize_sensitive_data(norm_event)

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

        duration_cost = {
            "duration_seconds": round(norm_event["duration_seconds"], 6),
            "cpu_duration_seconds": round(norm_event["cpu_duration_seconds"], 6),
            "db_duration_seconds": round(norm_event["db_duration_seconds"], 6),
            "model_duration_seconds": round(norm_event["model_duration_seconds"], 6),
            "cpu_cost": round(norm_event["cpu_cost"], 6),
            "db_cost": round(norm_event["db_cost"], 6),
            "model_cost_usd": round(norm_event["model_cost_usd"], 6),
        }

        record: dict[str, Any] = {
            "event_id": event_id,
            "timestamp": time.time(),
            "version": DIMVA_TRACE_WRITER_VERSION,
            "actual_backend": norm_event["actual_backend"],
            "raw_outcome": norm_event["raw_outcome"],
            "detector_score": float(norm_event["detector_score"]),
            "detection_decision": norm_event["detection_decision"],
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
        with self.trace_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

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

    writer = TraceWriter(target_path, actual_backend=actual_backend or "candidate")
    return writer.append(event_to_write, sanitize=sanitize)


def read_trace(trace_path: str | Path) -> list[dict[str, Any]]:
    """Read all records from a verified trace file."""
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
    4. Detector score is a finite float in [0.0, 1.0].
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
        "detector_score",
        "detection_decision",
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

        # 3. Score range [0.0, 1.0]
        score = record["detector_score"]
        if (
            score is None
            or isinstance(score, bool)
            or not isinstance(score, int | float)
            or not math.isfinite(float(score))
            or not (0.0 <= float(score) <= 1.0)
        ):
            return (
                False,
                f"{REASON_SCORE_OUT_OF_RANGE}: line {idx} detector_score {score!r} outside [0.0, 1.0]",
            )

        # 4. Allowed raw outcome
        outcome = record["raw_outcome"]
        if outcome not in ALLOWED_OUTCOMES:
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
