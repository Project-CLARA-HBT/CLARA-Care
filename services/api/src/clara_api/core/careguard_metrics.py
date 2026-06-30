"""No-PII CareGuard observability metrics (Requirements 9.3, 9.4, 9.5).

Behind ``CAREGUARD_OBSERVABILITY_ENABLED`` the CareGuard analysis paths record a
small set of **no-PII** operational metrics: per-source usage, fallback rate,
normalization confidence, the active DDI rule-set version, and per-check
latency. With the flag off nothing is recorded and the endpoints behave exactly
as today (Requirement 12.1, 12.2).

Privacy contract (Requirement 9.2, 9.3, 11.4): every value folded into the
store is a **count, enum label, version string, or bounded number** — never a
drug name, brand, free-text note, allergy, symptom, or any user identifier. The
``record_careguard_check`` projection is the single ingest seam and extracts
*only* the allowlisted no-PII fields from an analysis result, so a drug name or
identifier present elsewhere in the payload can never reach the store.

The store is an in-process, thread-safe aggregate mirroring the existing
``APIMetricsStore`` in ``core/metrics.py``; the aggregate read is exposed only
to admin roles (Requirement 9.5).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from threading import Lock
from typing import Any

# Allowlisted enum labels. Anything outside these sets is bucketed under a
# generic label so an unexpected/attacker-supplied string can never be persisted
# verbatim as a high-cardinality (potentially PII-bearing) key.
_KNOWN_SOURCES: frozenset[str] = frozenset(
    {"local_rules", "rxnav", "rxnorm", "openfda", "drugbank"}
)
_KNOWN_RISK_LEVELS: frozenset[str] = frozenset(
    {"low", "medium", "high", "critical", "unknown"}
)
_OTHER_SOURCE_LABEL = "other"
_UNKNOWN_RISK_LABEL = "unknown"

# Rule-set version labels are low-cardinality, operator-controlled identifiers
# (e.g. ``v1`` / ``v1+drugbank-2026-01``). They are clamped in length and stripped
# of newlines defensively before use as a metric key.
_MAX_VERSION_LABEL_CHARS = 64
_UNKNOWN_VERSION_LABEL = "unknown"

# Bound the retained latency sample buffer so the store stays O(1) in memory
# regardless of traffic; percentiles are computed over the retained window.
_MAX_LATENCY_SAMPLES = 2048


def _coerce_source_label(value: Any) -> str:
    """Map an arbitrary source token to a known enum label or ``other``."""

    if not isinstance(value, str):
        return _OTHER_SOURCE_LABEL
    normalized = value.strip().lower()
    return normalized if normalized in _KNOWN_SOURCES else _OTHER_SOURCE_LABEL


def _coerce_risk_label(value: Any) -> str:
    """Map an arbitrary risk token to a known enum label or ``unknown``."""

    if not isinstance(value, str):
        return _UNKNOWN_RISK_LABEL
    normalized = value.strip().lower()
    return normalized if normalized in _KNOWN_RISK_LEVELS else _UNKNOWN_RISK_LABEL


def _coerce_version_label(value: Any) -> str:
    """Coerce a rule-set version into a bounded, single-line label."""

    if not isinstance(value, str):
        return _UNKNOWN_VERSION_LABEL
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return _UNKNOWN_VERSION_LABEL
    return cleaned[:_MAX_VERSION_LABEL_CHARS]


def _coerce_confidence(value: Any) -> float | None:
    """Coerce a normalization confidence into a ``[0.0, 1.0]`` float, else None."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    confidence = float(value)
    if math.isnan(confidence) or math.isinf(confidence):
        return None
    return max(0.0, min(1.0, confidence))


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


class CareGuardMetricsStore:
    """Thread-safe in-process aggregate of no-PII CareGuard metrics."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._checks_total = 0
        self._fallback_total = 0
        self._by_source: Counter[str] = Counter()
        self._by_risk_level: Counter[str] = Counter()
        self._by_rule_set_version: Counter[str] = Counter()
        self._latency_count = 0
        self._latency_sum_ms = 0.0
        self._latency_samples: list[float] = []
        self._confidence_count = 0
        self._confidence_sum = 0.0
        self._confidence_buckets: Counter[str] = Counter()

    def record(
        self,
        *,
        source_used: Sequence[str] | None,
        fallback_used: bool,
        risk_level: str | None,
        rule_set_version: str | None,
        latency_ms: float | None,
        normalization_confidences: Sequence[float] | None = None,
    ) -> None:
        """Fold a single check's **no-PII** signals into the aggregate.

        Every argument is sanitized to an enum label, version string, or bounded
        number before storage; nothing free-text is retained.
        """

        sources = [
            _coerce_source_label(item)
            for item in (source_used or [])
            if isinstance(item, str)
        ]
        risk_label = _coerce_risk_label(risk_level)
        version_label = _coerce_version_label(rule_set_version)

        latency_value: float | None = None
        if not isinstance(latency_ms, bool) and isinstance(latency_ms, (int, float)):
            candidate = float(latency_ms)
            if not math.isnan(candidate) and not math.isinf(candidate):
                latency_value = max(0.0, candidate)

        confidences = [
            coerced
            for coerced in (
                _coerce_confidence(raw) for raw in (normalization_confidences or [])
            )
            if coerced is not None
        ]

        with self._lock:
            self._checks_total += 1
            if fallback_used:
                self._fallback_total += 1
            for source in sources:
                self._by_source[source] += 1
            self._by_risk_level[risk_label] += 1
            self._by_rule_set_version[version_label] += 1

            if latency_value is not None:
                self._latency_count += 1
                self._latency_sum_ms += latency_value
                self._latency_samples.append(latency_value)
                if len(self._latency_samples) > _MAX_LATENCY_SAMPLES:
                    # Drop the oldest sample to keep a bounded rolling window.
                    self._latency_samples.pop(0)

            for confidence in confidences:
                self._confidence_count += 1
                self._confidence_sum += confidence
                if confidence >= 0.8:
                    self._confidence_buckets["high"] += 1
                elif confidence >= 0.5:
                    self._confidence_buckets["medium"] += 1
                else:
                    self._confidence_buckets["low"] += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable aggregate of counts/rates/percentiles."""

        with self._lock:
            checks_total = self._checks_total
            fallback_total = self._fallback_total
            by_source = dict(self._by_source)
            by_risk_level = dict(self._by_risk_level)
            by_rule_set_version = dict(self._by_rule_set_version)
            latency_count = self._latency_count
            latency_sum_ms = self._latency_sum_ms
            latency_samples = list(self._latency_samples)
            confidence_count = self._confidence_count
            confidence_sum = self._confidence_sum
            confidence_buckets = dict(self._confidence_buckets)

        fallback_rate_pct = (
            round((fallback_total / checks_total) * 100.0, 3) if checks_total else 0.0
        )
        avg_latency_ms = (
            round(latency_sum_ms / latency_count, 3) if latency_count else 0.0
        )
        avg_normalization_confidence = (
            round(confidence_sum / confidence_count, 4) if confidence_count else 0.0
        )

        return {
            "checks_total": checks_total,
            "fallback_total": fallback_total,
            "fallback_rate_pct": fallback_rate_pct,
            "by_source": by_source,
            "by_risk_level": by_risk_level,
            "by_rule_set_version": by_rule_set_version,
            "latency": {
                "count": latency_count,
                "avg_ms": avg_latency_ms,
                "p50_ms": round(_percentile(latency_samples, 50.0), 3),
                "p90_ms": round(_percentile(latency_samples, 90.0), 3),
                "p99_ms": round(_percentile(latency_samples, 99.0), 3),
            },
            "normalization_confidence": {
                "count": confidence_count,
                "avg": avg_normalization_confidence,
                "buckets": confidence_buckets,
            },
        }

    def reset(self) -> None:
        """Clear all counters (used by tests for isolation)."""

        with self._lock:
            self._checks_total = 0
            self._fallback_total = 0
            self._by_source.clear()
            self._by_risk_level.clear()
            self._by_rule_set_version.clear()
            self._latency_count = 0
            self._latency_sum_ms = 0.0
            self._latency_samples.clear()
            self._confidence_count = 0
            self._confidence_sum = 0.0
            self._confidence_buckets.clear()


_careguard_metrics_store = CareGuardMetricsStore()


def get_careguard_metrics_store() -> CareGuardMetricsStore:
    return _careguard_metrics_store


def record_careguard_check(
    result: Mapping[str, Any],
    *,
    latency_ms: float | None = None,
    normalization_confidences: Sequence[float] | None = None,
    store: CareGuardMetricsStore | None = None,
) -> None:
    """Extract only no-PII fields from an analysis ``result`` and record them.

    This is the single ingest seam for CareGuard observability. It reads only
    the allowlisted operational fields — ``metadata.source_used``,
    ``metadata.fallback_used`` (or top-level ``fallback_used``),
    ``metadata.local_ddi_rules_version``, and ``risk.level`` — and the caller-
    supplied per-medicine normalization confidences. It never reads drug names,
    alert messages, allergies, symptoms, notes, or any identifier, so the
    aggregate cannot carry PII (Requirements 9.2, 9.3, 11.4).
    """

    target = store or get_careguard_metrics_store()

    metadata = result.get("metadata") if isinstance(result, Mapping) else None
    metadata_obj: Mapping[str, Any] = metadata if isinstance(metadata, Mapping) else {}

    raw_sources = metadata_obj.get("source_used")
    source_used = list(raw_sources) if isinstance(raw_sources, (list, tuple)) else []

    fallback_used = bool(
        (isinstance(result, Mapping) and result.get("fallback_used"))
        or metadata_obj.get("fallback_used")
    )

    rule_set_version = metadata_obj.get("local_ddi_rules_version")

    risk = result.get("risk") if isinstance(result, Mapping) else None
    risk_level = risk.get("level") if isinstance(risk, Mapping) else None

    target.record(
        source_used=source_used,
        fallback_used=fallback_used,
        risk_level=risk_level if isinstance(risk_level, str) else None,
        rule_set_version=rule_set_version if isinstance(rule_set_version, str) else None,
        latency_ms=latency_ms,
        normalization_confidences=normalization_confidences,
    )
