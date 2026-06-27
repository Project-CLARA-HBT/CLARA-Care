"""Analytics module for CLARA_API.

This module hosts the Product_Analytics and Clinical_Analytics layer:
the PII-free Pydantic response schemas (this task), the
``AnalyticsAggregator`` (task 5.2), and the admin-gated
``/system/analytics/*`` endpoints (tasks 5.5/5.6).

The schemas mirror the design's "Analytics data model and endpoints"
section. Every outward-facing shape carries only counts, distributions,
percentiles, verdicts, timestamps, and opaque identifiers — never raw
query text, drug lists, names, or emails (Requirements 7.4, 8.2, 11.5).
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    CouncilCase,
    MedicineItem,
    ScribeSession,
    SessionModel,
    User,
)
from clara_api.db.models import (
    Query as QueryModel,
)

# ---------------------------------------------------------------------------
# Product_Analytics response schemas (Requirement 7)
# ---------------------------------------------------------------------------


class ActiveUsersPoint(BaseModel):
    """A single point on the active-user trend line."""

    date: date
    active_users: int = 0


class SurfaceUsage(BaseModel):
    """Per-Surface usage count.

    ``surface`` is one of: chat|research|selfmed|careguard|council|scribe|
    admin|dashboard.
    """

    surface: str
    count: int = 0


class FunnelStage(BaseModel):
    """A single stage in a conversion funnel."""

    stage: str
    count: int = 0


class ProductAnalytics(BaseModel):
    """Aggregated product/usage analytics for the admin dashboard.

    ``has_data`` drives the explicit empty-state on the dashboard (7.5);
    an empty range returns this populated shape with ``has_data=False``.
    """

    generated_at: datetime
    range: tuple[date, date]
    active_user_trend: list[ActiveUsersPoint] = Field(default_factory=list)
    surface_usage: list[SurfaceUsage] = Field(default_factory=list)
    funnels: list[FunnelStage] = Field(default_factory=list)
    # cohort -> retained counts (PII-free; counts/distributions only)
    retention: list[dict[str, Any]] = Field(default_factory=list)
    has_data: bool = False


# ---------------------------------------------------------------------------
# Clinical_Analytics response schemas (Requirement 8)
# ---------------------------------------------------------------------------


class VerdictDistribution(BaseModel):
    """FIDES verification verdict distribution."""

    verified: int = 0
    partially_verified: int = 0
    contested: int = 0
    unsupported: int = 0
    # CRITICAL claims blocked by FIDES verification (8.4)
    blocked_claims: int = 0


class DdiSeverityDistribution(BaseModel):
    """DDI severity distribution across CareGuard analyses."""

    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0


class LatencyPercentiles(BaseModel):
    """Per-tier latency percentiles in milliseconds.

    ``tier`` is one of: tier1|tier2_deep|tier2_deep_beta|council.
    """

    tier: str
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p99_ms: float = 0.0


class ClinicalAnalytics(BaseModel):
    """Aggregated clinical-quality and pipeline-health analytics.

    Derived entirely from existing observability sources (FlowEventStore,
    APIMetricsStore, control-tower config) — no duplicate collection path
    (Requirement 8.2). ``has_data`` drives the empty-state on the dashboard.
    """

    generated_at: datetime
    range: tuple[date, date]
    verdicts: VerdictDistribution = Field(default_factory=VerdictDistribution)
    ddi_severity: DdiSeverityDistribution = Field(default_factory=DdiSeverityDistribution)
    # role/intent confidence buckets (counts only, no PII)
    router_confidence: dict[str, Any] = Field(default_factory=dict)
    fallback_rate_pct: float = 0.0
    latency: list[LatencyPercentiles] = Field(default_factory=list)
    has_data: bool = False


# ---------------------------------------------------------------------------
# AnalyticsAggregator (Requirements 7.4, 8.2, 11.5)
# ---------------------------------------------------------------------------

# Keys that may carry PII or free-text medical content. They are dropped by
# ``_project_pii_free`` before any record is folded into an outward-facing
# aggregation (Requirements 7.4, 9.4, 11.5).
_PII_DENYLIST_KEYS: frozenset[str] = frozenset(
    {
        # identity
        "email",
        "full_name",
        "name",
        "first_name",
        "last_name",
        "display_name",
        "phone",
        "address",
        "user_email",
        # free-text query / answer content
        "user_input",
        "query",
        "query_text",
        "message",
        "question",
        "prompt",
        "answer",
        "response_text",
        "transcript",
        # drug / medication lists
        "drug_name",
        "drug_names",
        "drugs",
        "drug_list",
        "medicine",
        "medicines",
        "medication",
        "medications",
        "medication_list",
        "medicine_list",
        # raw connector diagnostics
        "source_errors",
        "raw_source_errors",
    }
)

_SEVERITY_BUCKETS: frozenset[str] = frozenset({"low", "medium", "high", "critical"})


class AnalyticsAggregator:
    """Aggregates Product_Analytics and Clinical_Analytics from existing sources.

    Product metrics are computed from the existing identity/usage tables
    (``User``, ``SessionModel``, ``Query``, ``CouncilCase``, ``ScribeSession``,
    ``MedicineItem``). Clinical metrics are derived entirely from the existing
    observability surfaces — ``FlowEventStore`` records and the
    ``APIMetricsStore`` snapshot — so no duplicate collection path is
    introduced (Requirement 8.2).

    Every outward-facing value is a count, distribution, percentile, verdict,
    timestamp, or opaque identifier. Raw query text, drug lists, names, emails,
    and raw ``source_errors`` are never emitted (Requirements 7.4, 11.5).
    """

    # -- windowing & projection helpers -----------------------------------

    @staticmethod
    def _within_range(ts: datetime | None, start: date, end: date) -> bool:
        """Return True when ``ts`` falls within the inclusive ``[start, end]`` range.

        Naive datetimes are treated as UTC. ``None`` is never in range.
        """

        normalized = AnalyticsAggregator._as_utc(ts)
        if normalized is None:
            return False
        observed = normalized.date()
        return start <= observed <= end

    @staticmethod
    def _project_pii_free(record: Any) -> Any:
        """Recursively drop PII / free-text fields from a record.

        Removes denylisted keys (case-insensitive) at any nesting depth so the
        sanitized record carries only counts, distributions, severities,
        verdicts, timestamps, and opaque identifiers (Requirements 7.4, 11.5).
        """

        if isinstance(record, dict):
            projected: dict[str, Any] = {}
            for key, value in record.items():
                if isinstance(key, str) and key.strip().lower() in _PII_DENYLIST_KEYS:
                    continue
                projected[key] = AnalyticsAggregator._project_pii_free(value)
            return projected
        if isinstance(record, (list, tuple)):
            return [AnalyticsAggregator._project_pii_free(item) for item in record]
        return record

    @staticmethod
    def _as_utc(value: Any) -> datetime | None:
        """Coerce a datetime or ISO-8601 string into a UTC-aware datetime."""

        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _percentile(samples: list[float], pct: float) -> float:
        """Linear-interpolation percentile.

        Monotonic in ``pct`` for a fixed sample set, so p50 <= p90 <= p99
        always holds (Property 12).
        """

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

    @staticmethod
    def _classify_tier(record: dict[str, Any]) -> str:
        """Map a flow-event record to a latency tier label."""

        source = str(record.get("source") or "").strip().lower()
        intent = str(record.get("intent") or "").strip().lower()
        model_used = str(record.get("model_used") or "").strip().lower()

        if source == "council" or "council" in intent:
            return "council"
        if source == "research" or "research" in intent or "tier2" in intent:
            if "deep_beta" in model_used or "deepbeta" in model_used:
                return "tier2_deep_beta"
            return "tier2_deep"
        return "tier1"

    # -- product analytics -------------------------------------------------

    def product_metrics(self, db: Session, *, start: date, end: date) -> ProductAnalytics:
        """Aggregate usage analytics from existing identity/usage tables."""

        generated_at = datetime.now(tz=UTC)

        user_rows = db.execute(select(User.id, User.last_login_at, User.created_at)).all()
        query_rows = db.execute(
            select(SessionModel.user_id, QueryModel.created_at).join(
                QueryModel, QueryModel.session_id == SessionModel.id
            )
        ).all()
        council_rows = db.execute(select(CouncilCase.user_id, CouncilCase.created_at)).all()
        scribe_rows = db.execute(select(ScribeSession.user_id, ScribeSession.created_at)).all()
        medicine_rows = db.execute(select(MedicineItem.created_at)).all()

        # Active-user trend: distinct users whose last login falls on each day.
        trend_users: dict[date, set[int]] = {}
        for user_id, last_login_at, _created_at in user_rows:
            normalized = self._as_utc(last_login_at)
            if normalized is None or not self._within_range(normalized, start, end):
                continue
            trend_users.setdefault(normalized.date(), set()).add(int(user_id))
        active_user_trend = [
            ActiveUsersPoint(date=day, active_users=len(users))
            for day, users in sorted(trend_users.items())
        ]

        # Per-Surface usage counts (within range).
        chat_count = sum(
            1 for _uid, created_at in query_rows if self._within_range(created_at, start, end)
        )
        council_count = sum(
            1 for _uid, created_at in council_rows if self._within_range(created_at, start, end)
        )
        scribe_count = sum(
            1 for _uid, created_at in scribe_rows if self._within_range(created_at, start, end)
        )
        selfmed_count = sum(
            1 for (created_at,) in medicine_rows if self._within_range(created_at, start, end)
        )
        surface_usage = [
            SurfaceUsage(surface="chat", count=chat_count),
            SurfaceUsage(surface="council", count=council_count),
            SurfaceUsage(surface="scribe", count=scribe_count),
            SurfaceUsage(surface="selfmed", count=selfmed_count),
        ]

        # Conversion funnel (distinct users at each stage, within range).
        active_user_ids = {
            int(user_id)
            for user_id, last_login_at, _created_at in user_rows
            if self._within_range(last_login_at, start, end)
        }
        query_user_ids = {
            int(user_id)
            for user_id, created_at in query_rows
            if self._within_range(created_at, start, end)
        }
        clinical_user_ids = {
            int(user_id)
            for user_id, created_at in council_rows
            if self._within_range(created_at, start, end)
        } | {
            int(user_id)
            for user_id, created_at in scribe_rows
            if self._within_range(created_at, start, end)
        }
        funnels = [
            FunnelStage(stage="active_users", count=len(active_user_ids)),
            FunnelStage(stage="ran_query", count=len(query_user_ids)),
            FunnelStage(stage="used_clinical_tools", count=len(clinical_user_ids)),
        ]

        # Retention cohorts (signup month -> retained within range). PII-free:
        # only cohort label and counts are emitted.
        cohort_sizes: dict[str, set[int]] = {}
        cohort_retained: dict[str, set[int]] = {}
        for user_id, last_login_at, created_at in user_rows:
            created = self._as_utc(created_at)
            if created is None or not self._within_range(created, start, end):
                continue
            cohort_key = created.strftime("%Y-%m")
            cohort_sizes.setdefault(cohort_key, set()).add(int(user_id))
            if self._within_range(last_login_at, start, end):
                cohort_retained.setdefault(cohort_key, set()).add(int(user_id))
        retention = [
            {
                "cohort": cohort_key,
                "cohort_size": len(cohort_sizes[cohort_key]),
                "retained": len(cohort_retained.get(cohort_key, set())),
            }
            for cohort_key in sorted(cohort_sizes)
        ]

        has_data = bool(
            active_user_trend
            or chat_count
            or council_count
            or scribe_count
            or selfmed_count
            or retention
        )

        return ProductAnalytics(
            generated_at=generated_at,
            range=(start, end),
            active_user_trend=active_user_trend,
            surface_usage=surface_usage,
            funnels=funnels,
            retention=retention,
            has_data=has_data,
        )

    # -- clinical analytics ------------------------------------------------

    def clinical_metrics(
        self,
        db: Session,
        flow_events: Any,
        metrics: Any,
        *,
        start: date,
        end: date,
    ) -> ClinicalAnalytics:
        """Aggregate clinical-quality/pipeline-health analytics.

        Derived from ``flow_events`` (FlowEventStore records) and ``metrics``
        (APIMetricsStore snapshot) only — no new collection path (8.2). ``db``
        is accepted for signature parity with ``product_metrics`` and future
        control-tower lookups.
        """

        _ = db  # reserved for control-tower config lookups; no DB write/read needed today
        generated_at = datetime.now(tz=UTC)

        # When the durable store is enabled, read the range-windowed archive so
        # analytics cover events beyond the in-memory deque and across restarts
        # (Requirement 7.1). When disabled, fall back to the in-memory snapshot
        # that was passed in, preserving the pre-feature baseline (Req 7.2).
        records = self._resolve_clinical_records(flow_events, start=start, end=end)
        metrics_snapshot = metrics if isinstance(metrics, dict) else {}

        verdicts = VerdictDistribution()
        ddi_severity = DdiSeverityDistribution()
        confidence_buckets = {"high": 0, "medium": 0, "low": 0}
        latency_samples: dict[str, list[float]] = {}
        in_range_total = 0
        fallback_total = 0

        for record in records:
            timestamp = record.get("timestamp")
            if not self._within_range(timestamp, start, end):
                continue
            in_range_total += 1

            event = record.get("event")
            event = event if isinstance(event, dict) else {}
            status = str(event.get("status") or "").strip().lower()

            # FIDES verdict distribution + blocked CRITICAL claims (8.4).
            if status in {"pass", "verified"}:
                verdicts.verified += 1
            elif status in {"warn", "partial", "partially_verified"}:
                verdicts.partially_verified += 1
            elif status in {"fail", "contested", "contradicted"}:
                verdicts.contested += 1
            elif status in {"unsupported", "insufficient"}:
                verdicts.unsupported += 1
            if status == "blocked":
                verdicts.blocked_claims += 1

            # DDI severity distribution (CareGuard signals).
            severity = self._extract_severity(record, event)
            if severity in _SEVERITY_BUCKETS:
                setattr(ddi_severity, severity, getattr(ddi_severity, severity) + 1)

            # Router role/intent confidence buckets.
            confidence = event.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                if confidence >= 0.8:
                    confidence_buckets["high"] += 1
                elif confidence >= 0.5:
                    confidence_buckets["medium"] += 1
                else:
                    confidence_buckets["low"] += 1

            # Fallback rate.
            if (
                bool(event.get("fallback_used"))
                or bool(event.get("fallback_reason"))
                or status == "fallback"
            ):
                fallback_total += 1

            # Per-tier latency samples.
            latency = self._extract_latency(event)
            if latency is not None:
                latency_samples.setdefault(self._classify_tier(record), []).append(latency)

        fallback_rate_pct = (
            round((fallback_total / in_range_total) * 100.0, 3) if in_range_total else 0.0
        )

        latency = [
            LatencyPercentiles(
                tier=tier,
                p50_ms=round(self._percentile(samples, 50.0), 3),
                p90_ms=round(self._percentile(samples, 90.0), 3),
                p99_ms=round(self._percentile(samples, 99.0), 3),
            )
            for tier, samples in sorted(latency_samples.items())
        ]

        # Fall back to the metrics snapshot average when no per-tier latency
        # samples are present, so the dashboard still has a data point.
        requests_total = self._coerce_int(metrics_snapshot.get("requests_total"))
        avg_latency_ms = self._coerce_float(metrics_snapshot.get("avg_latency_ms"))
        if not latency and requests_total > 0 and avg_latency_ms > 0.0:
            latency = [
                LatencyPercentiles(
                    tier="tier1",
                    p50_ms=round(avg_latency_ms, 3),
                    p90_ms=round(avg_latency_ms, 3),
                    p99_ms=round(avg_latency_ms, 3),
                )
            ]

        has_data = bool(in_range_total) or requests_total > 0

        return ClinicalAnalytics(
            generated_at=generated_at,
            range=(start, end),
            verdicts=verdicts,
            ddi_severity=ddi_severity,
            router_confidence=confidence_buckets,
            fallback_rate_pct=fallback_rate_pct,
            latency=latency,
            has_data=has_data,
        )

    # -- internal clinical helpers ----------------------------------------

    @staticmethod
    def _resolve_clinical_records(
        flow_events: Any, *, start: date, end: date
    ) -> list[dict[str, Any]]:
        """Choose the clinical-event source based on the durable-store flag.

        When ``admin_observability_persistent_store_enabled`` is on, read the
        range-windowed durable archive via the ``FlowEventSink`` (events beyond
        the in-memory deque and across restarts — Requirement 7.1). When off,
        normalize the in-memory ``flow_events`` snapshot that was passed in, so
        behavior equals the pre-feature baseline (Requirement 7.2).
        """

        # Lazy imports avoid a circular import (the sink imports this module).
        from clara_api.core.config import get_settings

        if get_settings().admin_observability_persistent_store_enabled:
            from clara_api.observability.flow_event_sink import get_flow_event_sink

            return get_flow_event_sink().query(start=start, end=end)
        return AnalyticsAggregator._iter_event_records(flow_events)

    @staticmethod
    def _iter_event_records(flow_events: Any) -> list[dict[str, Any]]:
        """Normalize flow-event input into a list of record dicts."""

        if isinstance(flow_events, dict):
            items = flow_events.get("items")
            source = items if isinstance(items, list) else []
        elif isinstance(flow_events, list):
            source = flow_events
        else:
            return []
        return [item for item in source if isinstance(item, dict)]

    @staticmethod
    def _extract_severity(record: dict[str, Any], event: dict[str, Any]) -> str | None:
        """Resolve a DDI severity bucket from a CareGuard-related event."""

        source = str(record.get("source") or "").strip().lower()
        candidate: Any = None
        if "risk_level" in event:
            candidate = event.get("risk_level")
        else:
            stage = str(event.get("stage") or "").lower()
            if "severity" in event and (source == "careguard" or "ddi" in stage):
                candidate = event.get("severity")
        if not isinstance(candidate, str):
            return None
        normalized = candidate.strip().lower()
        return normalized if normalized in _SEVERITY_BUCKETS else None

    @staticmethod
    def _extract_latency(event: dict[str, Any]) -> float | None:
        """Resolve a non-negative latency sample (ms) from an event, if present."""

        for key in ("latency_ms", "duration_ms", "elapsed_ms", "latency"):
            value = event.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                latency = float(value)
                if latency >= 0.0:
                    return latency
        return None

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _coerce_float(value: Any) -> float:
        try:
            return max(float(value), 0.0)
        except (TypeError, ValueError):
            return 0.0
