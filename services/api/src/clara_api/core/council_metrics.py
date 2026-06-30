"""No-PII Council observability metrics (Requirements 7.1, 7.2, 7.3).

Behind ``COUNCIL_OBSERVABILITY_ENABLED`` the Council orchestration path records a
small set of **no-PII** operational signals: per-deliberation-stage flow events
(``{stage, duration_ms, outcome}``) and run-level metrics (``{latency_ms,
specialist_count, conflict_count, emergency_triggered, fallback_used}``). With
the flag off nothing is recorded and the Council behaves exactly as today —
``CouncilOrchestrationService.record_stage`` / ``record_run_metrics`` return
early before touching this store (Requirements 7.5, 9.2).

Privacy contract (Requirements 7.2, 7.3, 9.5): every value folded into the store
is a **stage label (enum), outcome label (enum), count, bounded number, or
boolean** — never a transcript, symptom, lab, medication, history string, or any
user identifier. The two record seams are the single ingest points and accept
only those coarse arguments, so clinical free text present elsewhere can never
reach the aggregate.

The store is an in-process, thread-safe aggregate mirroring the established
``CareGuardMetricsStore`` in ``core/careguard_metrics.py``; its aggregate read is
intended for admin/operator surfaces only.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from threading import Lock
from typing import Any

# Allowlisted deliberation-stage labels (the six pipeline steps from the design's
# streaming flow). Anything outside this set is bucketed under a generic label so
# an unexpected/attacker-supplied string can never be persisted verbatim as a
# high-cardinality (potentially PII-bearing) metric key.
_KNOWN_STAGES: frozenset[str] = frozenset(
    {
        "intake_normalized",
        "specialist_assessment",
        "conflict_review",
        "consensus_decision",
        "safety_gate",
        "final_recommendation",
    }
)
_OTHER_STAGE_LABEL = "other"

# Allowlisted stage outcomes. Anything else folds to ``error`` so a stage is
# never recorded as a success on a malformed/unknown outcome token.
_KNOWN_OUTCOMES: frozenset[str] = frozenset({"success", "error"})
_DEFAULT_OUTCOME_LABEL = "error"

# Bound the retained latency sample buffers so the store stays O(1) in memory
# regardless of traffic; percentiles are computed over the retained window.
_MAX_LATENCY_SAMPLES = 2048


def _coerce_stage_label(value: Any) -> str:
    """Map an arbitrary stage token to a known enum label or ``other``."""

    if not isinstance(value, str):
        return _OTHER_STAGE_LABEL
    normalized = value.strip().lower()
    return normalized if normalized in _KNOWN_STAGES else _OTHER_STAGE_LABEL


def _coerce_outcome_label(value: Any) -> str:
    """Map an arbitrary outcome token to a known enum label or ``error``."""

    if not isinstance(value, str):
        return _DEFAULT_OUTCOME_LABEL
    normalized = value.strip().lower()
    return normalized if normalized in _KNOWN_OUTCOMES else _DEFAULT_OUTCOME_LABEL


def _coerce_duration_ms(value: Any) -> float | None:
    """Coerce a duration into a non-negative, finite float (ms), else ``None``."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    candidate = float(value)
    if math.isnan(candidate) or math.isinf(candidate):
        return None
    return max(0.0, candidate)


def _coerce_count(value: Any) -> int | None:
    """Coerce a count into a non-negative int, else ``None`` (booleans rejected)."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    candidate = float(value)
    if math.isnan(candidate) or math.isinf(candidate):
        return None
    return max(0, int(candidate))


# ---------------------------------------------------------------------------
# No-PII redaction guard (task 7.2, Requirements 7.3, 7.4, 9.5)
# ---------------------------------------------------------------------------
# A centralized denylist guard applied to **every** Council telemetry writer so
# no writer path can emit patient-identifiable or clinical free-text content.
# It mirrors the key set used by the web analytics facade
# (``apps/web/lib/analytics/index.ts``) and the mobile analytics client
# (``apps/mobile/lib/core/analytics.dart``) so all three tiers strip the same
# fields, and it extends that set with the Council-specific clinical keys named
# in the requirements (history, lab values, free-text reasons / chief complaint).
#
# Matching is by **normalized key** (lowercased, non-alphanumerics removed) so
# compound/nested keys such as ``patient_email``, ``drug_names``,
# ``free_text_reason`` or ``Symptom List`` are all caught. Redaction is recursive
# and drops the offending key entirely at any nesting depth; coarse, non-PII keys
# (counts, labels, booleans, durations) pass through unchanged so the existing
# coarse ``council_viewed`` / ``council_run`` payloads survive intact
# (Requirement 7.4).

# Exact normalized keys that always denote PII or clinical free-text content.
_PII_DENYLIST_EXACT: frozenset[str] = frozenset(
    {
        # Names / identity (mirrors web + mobile)
        "name",
        "fullname",
        "firstname",
        "lastname",
        "givenname",
        "familyname",
        "surname",
        "displayname",
        "username",
        "patientname",
        # Contact / identifiers
        "email",
        "emailaddress",
        "mail",
        "phone",
        "phonenumber",
        "address",
        "ssn",
        "nationalid",
        "dob",
        "dateofbirth",
        "birthdate",
        # Free-text query / message content
        "q",
        "query",
        "question",
        "prompt",
        "message",
        "text",
        "content",
        "input",
        "userinput",
        "search",
        "searchquery",
        "body",
        "note",
        "notes",
        "transcript",
        # Free-text clinical reasons (Council oversight / intake)
        "reason",
        "reasons",
        "reasontext",
        "freetext",
        "chiefcomplaint",
        "complaint",
        "complaints",
        "finding",
        "findings",
        # Clinical content
        "drug",
        "drugs",
        "druglist",
        "medication",
        "medications",
        "medicine",
        "medicines",
        "symptom",
        "symptoms",
        "allergy",
        "allergies",
        "diagnosis",
        "prescription",
        "labs",
        "lab",
        "labvalue",
        "labvalues",
        "labresult",
        "labresults",
        "history",
        "medicalhistory",
        "pasthistory",
        "pmh",
    }
)

# Normalized substrings that mark a key as PII / clinical even when compound.
# Kept conservative so the coarse metric keys (``latency_ms``,
# ``specialist_count``, ``conflict_count``, ``emergency_triggered``,
# ``fallback_used``, ``stage``, ``duration_ms``, ``outcome``) are never caught.
_PII_DENYLIST_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "email",
        "query",
        "freetext",
        "userinput",
        "drug",
        "medicine",
        "medication",
        "symptom",
        "allergy",
        "diagnos",
        "prescription",
        "transcript",
        "patient",
        "password",
        "history",
        "complaint",
    }
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_telemetry_key(key: Any) -> str:
    """Normalize a key to lowercase alphanumerics for denylist matching."""

    if not isinstance(key, str):
        key = str(key)
    return _NON_ALNUM.sub("", key.lower())


def is_pii_telemetry_key(key: Any) -> bool:
    """Return ``True`` when a telemetry key must be dropped before emission.

    Matches the curated exact denylist first, then the conservative substring
    patterns. An empty/normalization-stripped key is never treated as PII.
    """

    normalized = _normalize_telemetry_key(key)
    if not normalized:
        return False
    if normalized in _PII_DENYLIST_EXACT:
        return True
    return any(pattern in normalized for pattern in _PII_DENYLIST_SUBSTRINGS)


def _redact_value(value: Any) -> Any:
    """Recursively redact PII keys inside nested mappings/sequences."""

    if isinstance(value, Mapping):
        return redact_telemetry(value)
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


def redact_telemetry(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Drop every PII / clinical free-text key from a telemetry payload.

    The single, centralized no-PII guard for all Council telemetry writers
    (Requirements 7.3, 7.4, 9.5). Returns a new ``dict`` with any denylisted key
    removed at **any** nesting depth (through nested mappings and lists), while
    coarse non-PII keys pass through unchanged. Pure and deterministic so it can
    be exercised directly by property/regression tests.
    """

    if not isinstance(payload, Mapping):
        return {}
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if is_pii_telemetry_key(key):
            continue  # drop the PII/clinical key entirely
        redacted[key] = _redact_value(value)
    return redacted


def _percentile(samples: list[float], pct: float) -> float:
    """Linear-interpolation percentile (monotonic in ``pct``)."""

    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[int(rank)])
    weight = rank - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


class CouncilMetricsStore:
    """Thread-safe in-process aggregate of no-PII Council metrics."""

    def __init__(self) -> None:
        self._lock = Lock()
        # Per-stage flow events.
        self._stage_events_total = 0
        self._by_stage: Counter[str] = Counter()
        self._by_stage_outcome: Counter[str] = Counter()
        self._stage_latency_count = 0
        self._stage_latency_sum_ms = 0.0
        self._stage_latency_samples: list[float] = []
        # Run-level metrics.
        self._runs_total = 0
        self._run_latency_count = 0
        self._run_latency_sum_ms = 0.0
        self._run_latency_samples: list[float] = []
        self._specialist_count_sum = 0
        self._conflict_count_sum = 0
        self._emergency_triggered_total = 0
        self._fallback_used_total = 0

    def record_stage(self, *, stage: str, duration_ms: float, outcome: str) -> None:
        """Fold one **no-PII** per-stage flow event into the aggregate.

        Only the stage label (enum), the outcome label (enum), and a bounded
        duration are retained — never clinical content (Requirement 7.1, 7.3).
        """

        stage_label = _coerce_stage_label(stage)
        outcome_label = _coerce_outcome_label(outcome)
        duration = _coerce_duration_ms(duration_ms)

        with self._lock:
            self._stage_events_total += 1
            self._by_stage[stage_label] += 1
            self._by_stage_outcome[f"{stage_label}:{outcome_label}"] += 1
            if duration is not None:
                self._stage_latency_count += 1
                self._stage_latency_sum_ms += duration
                self._stage_latency_samples.append(duration)
                if len(self._stage_latency_samples) > _MAX_LATENCY_SAMPLES:
                    self._stage_latency_samples.pop(0)

    def record_run(
        self,
        *,
        latency_ms: float | None,
        specialist_count: int | None,
        conflict_count: int | None,
        emergency_triggered: bool,
        fallback_used: bool,
    ) -> None:
        """Fold one run's **no-PII** run-level metrics into the aggregate.

        Every argument is a count, bounded number, or boolean; nothing free-text
        is retained (Requirement 7.2, 7.3).
        """

        latency = _coerce_duration_ms(latency_ms)
        specialists = _coerce_count(specialist_count)
        conflicts = _coerce_count(conflict_count)

        with self._lock:
            self._runs_total += 1
            if latency is not None:
                self._run_latency_count += 1
                self._run_latency_sum_ms += latency
                self._run_latency_samples.append(latency)
                if len(self._run_latency_samples) > _MAX_LATENCY_SAMPLES:
                    self._run_latency_samples.pop(0)
            if specialists is not None:
                self._specialist_count_sum += specialists
            if conflicts is not None:
                self._conflict_count_sum += conflicts
            if bool(emergency_triggered):
                self._emergency_triggered_total += 1
            if bool(fallback_used):
                self._fallback_used_total += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable aggregate of counts/rates/percentiles."""

        with self._lock:
            stage_events_total = self._stage_events_total
            by_stage = dict(self._by_stage)
            by_stage_outcome = dict(self._by_stage_outcome)
            stage_latency_count = self._stage_latency_count
            stage_latency_sum_ms = self._stage_latency_sum_ms
            stage_latency_samples = list(self._stage_latency_samples)
            runs_total = self._runs_total
            run_latency_count = self._run_latency_count
            run_latency_sum_ms = self._run_latency_sum_ms
            run_latency_samples = list(self._run_latency_samples)
            specialist_count_sum = self._specialist_count_sum
            conflict_count_sum = self._conflict_count_sum
            emergency_triggered_total = self._emergency_triggered_total
            fallback_used_total = self._fallback_used_total

        avg_stage_latency_ms = (
            round(stage_latency_sum_ms / stage_latency_count, 3)
            if stage_latency_count
            else 0.0
        )
        avg_run_latency_ms = (
            round(run_latency_sum_ms / run_latency_count, 3) if run_latency_count else 0.0
        )
        avg_specialist_count = (
            round(specialist_count_sum / runs_total, 3) if runs_total else 0.0
        )
        avg_conflict_count = round(conflict_count_sum / runs_total, 3) if runs_total else 0.0
        emergency_rate_pct = (
            round((emergency_triggered_total / runs_total) * 100.0, 3) if runs_total else 0.0
        )
        fallback_rate_pct = (
            round((fallback_used_total / runs_total) * 100.0, 3) if runs_total else 0.0
        )

        return {
            "stage_events_total": stage_events_total,
            "by_stage": by_stage,
            "by_stage_outcome": by_stage_outcome,
            "stage_latency": {
                "count": stage_latency_count,
                "avg_ms": avg_stage_latency_ms,
                "p50_ms": round(_percentile(stage_latency_samples, 50.0), 3),
                "p90_ms": round(_percentile(stage_latency_samples, 90.0), 3),
                "p99_ms": round(_percentile(stage_latency_samples, 99.0), 3),
            },
            "runs_total": runs_total,
            "run_latency": {
                "count": run_latency_count,
                "avg_ms": avg_run_latency_ms,
                "p50_ms": round(_percentile(run_latency_samples, 50.0), 3),
                "p90_ms": round(_percentile(run_latency_samples, 90.0), 3),
                "p99_ms": round(_percentile(run_latency_samples, 99.0), 3),
            },
            "avg_specialist_count": avg_specialist_count,
            "avg_conflict_count": avg_conflict_count,
            "emergency_triggered_total": emergency_triggered_total,
            "emergency_rate_pct": emergency_rate_pct,
            "fallback_used_total": fallback_used_total,
            "fallback_rate_pct": fallback_rate_pct,
        }

    def reset(self) -> None:
        """Clear all counters (used by tests for isolation)."""

        with self._lock:
            self._stage_events_total = 0
            self._by_stage.clear()
            self._by_stage_outcome.clear()
            self._stage_latency_count = 0
            self._stage_latency_sum_ms = 0.0
            self._stage_latency_samples.clear()
            self._runs_total = 0
            self._run_latency_count = 0
            self._run_latency_sum_ms = 0.0
            self._run_latency_samples.clear()
            self._specialist_count_sum = 0
            self._conflict_count_sum = 0
            self._emergency_triggered_total = 0
            self._fallback_used_total = 0


_council_metrics_store = CouncilMetricsStore()


def get_council_metrics_store() -> CouncilMetricsStore:
    return _council_metrics_store
