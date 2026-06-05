"""Property tests for the analytics aggregation layer.

These tests exercise ``AnalyticsAggregator`` directly (no network, no
TestClient) so they stay fully hermetic. They lock the design's correctness
properties for the analytics layer:

Feature: product-polish-analytics, Property 12 (task 5.3)
    Date-range windowing + percentile monotonicity — every returned data point
    lies within the requested range (out-of-range excluded) and latency
    percentiles satisfy p50 <= p90 <= p99.
    Validates: Requirements 7.3, 8.3

Feature: product-polish-analytics, Property 13 (task 5.4)
    PII-free outputs — for arbitrary underlying records (including injected
    email/name/free-text query/drug-list fields), the Product/Clinical
    aggregation output contains no email, name, free-text query content, or
    drug lists.
    Validates: Requirements 7.4, 11.5

Feature: product-polish-analytics, Property 15 (task 5.7)
    Blocked-claims counting — the Clinical blocked-claims metric equals the
    count of in-range events where a CRITICAL claim failed verification and was
    blocked.
    Validates: Requirements 8.4
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_api.api.v1.endpoints.analytics import (
    AnalyticsAggregator,
    ClinicalAnalytics,
    ProductAnalytics,
)
from clara_api.db import session as db_session
from clara_api.db.models import (
    MedicineCabinet,
    MedicineItem,
    SessionModel,
    User,
)
from clara_api.db.models import (
    Query as QueryModel,
)

# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

_PASSWORD_HASH = "x" * 16

# A fixed analytics window. The aggregator treats the bounds inclusively.
WINDOW_START = date(2026, 1, 1)
WINDOW_END = date(2026, 2, 28)
# Midday so day-offsets never straddle a date boundary by accident.
WINDOW_BASE = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

# Statuses that each map to exactly one verdict bucket in the aggregator.
# "blocked" is counted by ``blocked_claims`` (a separate counter), the other
# four each map to exactly one verdict field, so a stream built from this set
# contributes exactly one count per in-range event.
VERDICT_STATUSES = ["pass", "warn", "fail", "unsupported", "blocked"]
# Statuses that are NOT counted as blocked claims.
NON_BLOCK_STATUSES = ["pass", "warn", "fail", "unsupported"]


def _ts_for_offset(offset_days: int) -> datetime:
    return WINDOW_BASE + timedelta(days=offset_days)


def _in_range(offset_days: int) -> bool:
    return WINDOW_START <= _ts_for_offset(offset_days).date() <= WINDOW_END


def _record(
    ts: datetime,
    event: dict[str, Any],
    *,
    source: str = "chat",
    **extra: Any,
) -> dict[str, Any]:
    """Build a FlowEventStore-shaped record for the aggregator."""

    return {
        "timestamp": ts.isoformat(),
        "source": source,
        "user_id": "u1",
        "role": "normal",
        "intent": extra.get("intent"),
        "model_used": extra.get("model_used"),
        "event": event,
    }


# ---------------------------------------------------------------------------
# Property 12: date-range windowing
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    events=st.lists(
        st.tuples(st.integers(min_value=-20, max_value=70), st.sampled_from(VERDICT_STATUSES)),
        max_size=40,
    )
)
def test_property12_windowing_excludes_out_of_range_clinical(
    events: list[tuple[int, str]],
) -> None:
    """Feature: product-polish-analytics, Property 12.

    Out-of-range flow events are excluded; only in-range events are counted.
    Each in-range event contributes exactly one verdict/blocked count, so the
    summed counters equal the number of in-range events.
    """

    flow_events = {
        "items": [
            _record(_ts_for_offset(offset), {"stage": "verification", "status": status})
            for offset, status in events
        ]
    }

    result = AnalyticsAggregator().clinical_metrics(
        None, flow_events, {}, start=WINDOW_START, end=WINDOW_END
    )

    assert isinstance(result, ClinicalAnalytics)
    assert result.range == (WINDOW_START, WINDOW_END)

    expected_in_range = sum(1 for offset, _status in events if _in_range(offset))
    counted = (
        result.verdicts.verified
        + result.verdicts.partially_verified
        + result.verdicts.contested
        + result.verdicts.unsupported
        + result.verdicts.blocked_claims
    )
    assert counted == expected_in_range
    assert result.has_data is (expected_in_range > 0)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(offsets=st.lists(st.integers(min_value=-25, max_value=80), min_size=1, max_size=8))
def test_property12_product_trend_points_within_range(offsets: list[int]) -> None:
    """Feature: product-polish-analytics, Property 12.

    Every active-user-trend point produced by ``product_metrics`` falls inside
    the requested range, regardless of how login timestamps are distributed.
    """

    with db_session.SessionLocal() as db:
        for offset in offsets:
            login_at = _ts_for_offset(offset)
            db.add(
                User(
                    email=f"{uuid.uuid4().hex}@trend.clara",
                    hashed_password=_PASSWORD_HASH,
                    role="normal",
                    full_name="Trend User",
                    last_login_at=login_at,
                    created_at=login_at - timedelta(days=1),
                )
            )
        db.commit()

        result = AnalyticsAggregator().product_metrics(db, start=WINDOW_START, end=WINDOW_END)

    assert isinstance(result, ProductAnalytics)
    assert result.range == (WINDOW_START, WINDOW_END)
    for point in result.active_user_trend:
        assert WINDOW_START <= point.date <= WINDOW_END


# ---------------------------------------------------------------------------
# Property 12: percentile monotonicity
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    latencies=st.lists(
        st.floats(
            min_value=0.0,
            max_value=1_000_000.0,
            allow_nan=False,
            allow_infinity=False,
            allow_subnormal=False,
        ),
        min_size=1,
        max_size=50,
    )
)
def test_property12_latency_percentiles_are_monotonic(latencies: list[float]) -> None:
    """Feature: product-polish-analytics, Property 12.

    For any in-range latency sample set, each returned tier satisfies
    p50 <= p90 <= p99.
    """

    flow_events = {
        "items": [
            _record(
                _ts_for_offset(10),
                {"status": "pass", "latency_ms": latency},
                source="chat",
            )
            for latency in latencies
        ]
    }

    result = AnalyticsAggregator().clinical_metrics(
        None, flow_events, {}, start=WINDOW_START, end=WINDOW_END
    )

    assert result.latency, "expected at least one latency tier from in-range samples"
    for row in result.latency:
        assert row.p50_ms <= row.p90_ms <= row.p99_ms


@settings(max_examples=200, deadline=None)
@given(
    samples=st.lists(
        st.floats(
            min_value=0.0,
            max_value=1_000_000.0,
            allow_nan=False,
            allow_infinity=False,
            allow_subnormal=False,
        ),
        min_size=1,
        max_size=60,
    )
)
def test_property12_percentile_helper_is_non_decreasing(samples: list[float]) -> None:
    """Feature: product-polish-analytics, Property 12.

    The percentile helper is monotone non-decreasing in the requested
    percentile for any fixed latency-sample set. Latencies are non-negative
    milliseconds, and the aggregator emits percentiles rounded to 3 decimals
    (``clinical_metrics``); the assertion mirrors that emitted precision so it
    reflects the real contract rather than raw IEEE-754 interpolation noise.
    """

    agg = AnalyticsAggregator()
    p50 = round(agg._percentile(samples, 50.0), 3)
    p90 = round(agg._percentile(samples, 90.0), 3)
    p99 = round(agg._percentile(samples, 99.0), 3)
    assert p50 <= p90 <= p99


# ---------------------------------------------------------------------------
# Property 13: PII-free outputs
# ---------------------------------------------------------------------------

_SENTINEL = "PIISENTINEL"

# Lowercase ASCII alphabet for building DB-safe email/drug fragments.
_LOWER_ASCII = st.characters(min_codepoint=97, max_codepoint=122)


@settings(max_examples=150, deadline=None)
@given(
    count=st.integers(min_value=0, max_value=10_000),
    severity=st.sampled_from(["low", "medium", "high", "critical"]),
    pii=st.text(min_size=1, max_size=40).map(lambda s: f"{_SENTINEL}_{s}"),
)
def test_property13_project_pii_free_drops_denylisted_fields(
    count: int, severity: str, pii: str
) -> None:
    """Feature: product-polish-analytics, Property 13.

    ``_project_pii_free`` drops denylisted PII / free-text keys at every depth
    while preserving safe counts/severities/verdicts, and the projected record
    contains none of the injected PII values.
    """

    record = {
        "count": count,
        "severity": severity,
        "email": pii,
        "full_name": pii,
        "query": pii,
        "drug_names": [pii],
        "medications": [pii],
        "source_errors": [pii],
        "nested": {
            "user_input": pii,
            "verdict": "pass",
            "medication_list": [pii],
            "items": [{"message": pii, "risk_level": severity}],
        },
    }

    projected = AnalyticsAggregator._project_pii_free(record)

    # Safe fields preserved.
    assert projected["count"] == count
    assert projected["severity"] == severity
    assert projected["nested"]["verdict"] == "pass"
    assert projected["nested"]["items"][0]["risk_level"] == severity

    # Denylisted fields dropped at every depth.
    for key in ("email", "full_name", "query", "drug_names", "medications", "source_errors"):
        assert key not in projected
    assert "user_input" not in projected["nested"]
    assert "medication_list" not in projected["nested"]
    assert "message" not in projected["nested"]["items"][0]

    # No injected PII value survives anywhere in the projection.
    assert _SENTINEL not in json.dumps(projected)


@settings(max_examples=150, deadline=None)
@given(
    email=st.text(min_size=1, max_size=30).map(lambda s: f"{_SENTINEL}email_{s}"),
    name=st.text(min_size=1, max_size=30).map(lambda s: f"{_SENTINEL}name_{s}"),
    query=st.text(min_size=1, max_size=40).map(lambda s: f"{_SENTINEL}query_{s}"),
    drug=st.text(min_size=1, max_size=30).map(lambda s: f"{_SENTINEL}drug_{s}"),
)
def test_property13_clinical_output_is_pii_free(
    email: str, name: str, query: str, drug: str
) -> None:
    """Feature: product-polish-analytics, Property 13.

    Even when raw flow-event records carry email/name/free-text/drug fields,
    the assembled ``ClinicalAnalytics`` response emits only counts and never
    leaks the injected PII.
    """

    flow_events = {
        "items": [
            {
                "timestamp": _ts_for_offset(15).isoformat(),
                "source": "careguard",
                "user_id": "u1",
                "email": email,
                "full_name": name,
                "query": query,
                "drug_names": [drug],
                "event": {
                    "stage": "ddi_aggregation",
                    "status": "blocked",
                    "risk_level": "critical",
                    "confidence": 0.9,
                    "latency_ms": 42.0,
                    "user_input": query,
                    "medications": [drug],
                },
            }
        ]
    }

    result = AnalyticsAggregator().clinical_metrics(
        None, flow_events, {}, start=WINDOW_START, end=WINDOW_END
    )

    blob = result.model_dump_json()
    assert _SENTINEL not in blob
    for value in (email, name, query, drug):
        assert value not in blob


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    email_part=st.text(min_size=1, max_size=20, alphabet=_LOWER_ASCII),
    name_part=st.text(min_size=1, max_size=20).map(lambda s: f"{_SENTINEL}name_{s}"),
    query_part=st.text(min_size=1, max_size=30).map(lambda s: f"{_SENTINEL}query_{s}"),
    drug_part=st.text(min_size=1, max_size=20, alphabet=_LOWER_ASCII),
)
def test_property13_product_output_is_pii_free(
    email_part: str, name_part: str, query_part: str, drug_part: str
) -> None:
    """Feature: product-polish-analytics, Property 13.

    The assembled ``ProductAnalytics`` response (computed from identity/usage
    tables holding emails, names, free-text queries, and drug lists) emits only
    counts/distributions and never leaks the underlying PII.
    """

    email = f"{uuid.uuid4().hex}_{email_part}@pii.clara"
    drug = f"{_SENTINEL}drug{uuid.uuid4().hex[:8]}{drug_part}"
    now = _ts_for_offset(20)

    with db_session.SessionLocal() as db:
        user = User(
            email=email,
            hashed_password=_PASSWORD_HASH,
            role="normal",
            full_name=name_part,
            last_login_at=now,
            created_at=now - timedelta(days=2),
        )
        db.add(user)
        db.flush()

        session_row = SessionModel(user_id=user.id, title="S")
        db.add(session_row)
        db.flush()
        db.add(
            QueryModel(
                session_id=session_row.id,
                role="normal",
                user_input=query_part,
                response_text="{}",
                created_at=now,
            )
        )
        cabinet = MedicineCabinet(user_id=user.id, label="cab")
        db.add(cabinet)
        db.flush()
        db.add(
            MedicineItem(
                cabinet_id=cabinet.id,
                drug_name=drug,
                normalized_name=drug.lower(),
                created_at=now,
            )
        )
        db.commit()

        result = AnalyticsAggregator().product_metrics(db, start=WINDOW_START, end=WINDOW_END)

    blob = result.model_dump_json()
    assert _SENTINEL not in blob
    assert email not in blob
    assert name_part not in blob
    assert query_part not in blob
    assert drug not in blob


# ---------------------------------------------------------------------------
# Property 15: blocked-claims counting
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    events=st.lists(
        st.tuples(
            st.integers(min_value=-20, max_value=70),  # day offset (in/out of range)
            st.booleans(),  # blocked CRITICAL claim?
            st.sampled_from(NON_BLOCK_STATUSES),  # otherwise verdict status
        ),
        max_size=40,
    )
)
def test_property15_blocked_claims_equals_in_range_blocked(
    events: list[tuple[int, bool, str]],
) -> None:
    """Feature: product-polish-analytics, Property 15.

    The blocked-claims metric equals the number of in-range events whose
    CRITICAL claim failed verification and was blocked. Non-blocked verdicts and
    out-of-range blocked events are excluded.
    """

    items: list[dict[str, Any]] = []
    for offset, is_blocked, other_status in events:
        status = "blocked" if is_blocked else other_status
        items.append(
            _record(
                _ts_for_offset(offset),
                {
                    "stage": "verification",
                    "status": status,
                    "claim_severity": "critical",
                },
            )
        )

    result = AnalyticsAggregator().clinical_metrics(
        None, {"items": items}, {}, start=WINDOW_START, end=WINDOW_END
    )

    expected_blocked = sum(
        1 for offset, is_blocked, _status in events if is_blocked and _in_range(offset)
    )
    assert result.verdicts.blocked_claims == expected_blocked
