"""Unit tests for the AnalyticsAggregator (task 5.1).

Covers product metrics over identity/usage tables, clinical metrics over
FlowEventStore/APIMetricsStore data, date-range windowing, percentile
monotonicity, and the PII-free projection contract
(Requirements 7.4, 8.2, 11.5).
"""

from datetime import UTC, date, datetime, timedelta

from clara_api.api.v1.endpoints.analytics import (
    AnalyticsAggregator,
    ClinicalAnalytics,
    ProductAnalytics,
)
from clara_api.db import session as db_session
from clara_api.db.models import (
    CouncilCase,
    MedicineCabinet,
    MedicineItem,
    ScribeSession,
    SessionModel,
    User,
)
from clara_api.db.models import (
    Query as QueryModel,
)

_PASSWORD_HASH = "x" * 16


def _make_user(db, *, email: str, last_login_at, created_at) -> User:
    user = User(
        email=email,
        hashed_password=_PASSWORD_HASH,
        role="normal",
        full_name="Test User",
        last_login_at=last_login_at,
        created_at=created_at,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# _within_range
# ---------------------------------------------------------------------------


def test_within_range_includes_boundaries_and_excludes_outside() -> None:
    agg = AnalyticsAggregator()
    start = date(2026, 1, 10)
    end = date(2026, 1, 20)

    assert agg._within_range(datetime(2026, 1, 10, 0, 0, tzinfo=UTC), start, end) is True
    assert agg._within_range(datetime(2026, 1, 20, 23, 59, tzinfo=UTC), start, end) is True
    assert agg._within_range(datetime(2026, 1, 9, 23, 59, tzinfo=UTC), start, end) is False
    assert agg._within_range(datetime(2026, 1, 21, 0, 1, tzinfo=UTC), start, end) is False


def test_within_range_treats_naive_as_utc_and_none_as_excluded() -> None:
    agg = AnalyticsAggregator()
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)

    assert agg._within_range(datetime(2026, 1, 15, 12, 0), start, end) is True
    assert agg._within_range(None, start, end) is False
    assert agg._within_range("2026-01-15T12:00:00Z", start, end) is True


# ---------------------------------------------------------------------------
# _project_pii_free
# ---------------------------------------------------------------------------


def test_project_pii_free_drops_denylisted_keys_at_all_depths() -> None:
    agg = AnalyticsAggregator()
    record = {
        "count": 5,
        "email": "patient@example.com",
        "full_name": "Jane Doe",
        "query": "I have chest pain",
        "drug_names": ["warfarin", "aspirin"],
        "source_errors": ["openfda http_400"],
        "nested": {
            "user_input": "free text",
            "severity": "high",
            "items": [
                {"medication": "ibuprofen", "verdict": "pass"},
            ],
        },
    }

    projected = agg._project_pii_free(record)

    assert projected["count"] == 5
    assert "email" not in projected
    assert "full_name" not in projected
    assert "query" not in projected
    assert "drug_names" not in projected
    assert "source_errors" not in projected
    assert projected["nested"]["severity"] == "high"
    assert "user_input" not in projected["nested"]
    assert projected["nested"]["items"][0] == {"verdict": "pass"}


def test_project_pii_free_is_case_insensitive_and_preserves_scalars() -> None:
    agg = AnalyticsAggregator()
    projected = agg._project_pii_free({"Email": "a@b.com", "Severity": "low", "n": 1})
    assert "Email" not in projected
    assert projected["Severity"] == "low"
    assert projected["n"] == 1
    # Scalars / lists pass through untouched.
    assert agg._project_pii_free(42) == 42
    assert agg._project_pii_free(["a", "b"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# _percentile monotonicity
# ---------------------------------------------------------------------------


def test_percentile_is_monotonic_non_decreasing() -> None:
    agg = AnalyticsAggregator()
    samples = [120.0, 10.0, 50.0, 300.0, 75.0, 5.0]
    p50 = agg._percentile(samples, 50.0)
    p90 = agg._percentile(samples, 90.0)
    p99 = agg._percentile(samples, 99.0)
    assert p50 <= p90 <= p99
    assert agg._percentile([], 50.0) == 0.0
    assert agg._percentile([42.0], 99.0) == 42.0


# ---------------------------------------------------------------------------
# product_metrics
# ---------------------------------------------------------------------------


def test_product_metrics_counts_usage_within_range() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)

    with db_session.SessionLocal() as db:
        in_user = _make_user(
            db, email="in@range.clara", last_login_at=now, created_at=now - timedelta(days=10)
        )
        out_user = _make_user(
            db,
            email="out@range.clara",
            last_login_at=datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
            created_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        )

        session_row = SessionModel(user_id=in_user.id, title="S")
        db.add(session_row)
        db.flush()
        db.add(
            QueryModel(
                session_id=session_row.id,
                role="normal",
                user_input="hello",
                response_text="{}",
                created_at=now,
            )
        )
        db.add(
            CouncilCase(
                user_id=in_user.id, title="C", status="analyzed", transcript="", created_at=now
            )
        )
        db.add(
            ScribeSession(
                user_id=in_user.id, title="Sc", status="ready", transcript="", created_at=now
            )
        )
        cabinet = MedicineCabinet(user_id=in_user.id, label="cab")
        db.add(cabinet)
        db.flush()
        db.add(
            MedicineItem(
                cabinet_id=cabinet.id,
                drug_name="Warfarin",
                normalized_name="warfarin",
                created_at=now,
            )
        )
        # Out-of-range query should not count.
        out_session = SessionModel(user_id=out_user.id, title="S2")
        db.add(out_session)
        db.flush()
        db.add(
            QueryModel(
                session_id=out_session.id,
                role="normal",
                user_input="later",
                response_text="{}",
                created_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            )
        )
        db.commit()

        result = AnalyticsAggregator().product_metrics(db, start=start, end=end)

    assert isinstance(result, ProductAnalytics)
    assert result.range == (start, end)
    assert result.has_data is True
    usage = {row.surface: row.count for row in result.surface_usage}
    assert usage["chat"] == 1
    assert usage["council"] == 1
    assert usage["scribe"] == 1
    assert usage["selfmed"] == 1
    funnel = {row.stage: row.count for row in result.funnels}
    assert funnel["active_users"] == 1
    assert funnel["ran_query"] == 1
    assert funnel["used_clinical_tools"] == 1


def test_product_metrics_empty_range_reports_no_data() -> None:
    start = date(2020, 1, 1)
    end = date(2020, 1, 31)
    with db_session.SessionLocal() as db:
        _make_user(
            db,
            email="recent@range.clara",
            last_login_at=datetime(2026, 2, 1, tzinfo=UTC),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        db.commit()
        result = AnalyticsAggregator().product_metrics(db, start=start, end=end)

    assert result.has_data is False
    assert result.active_user_trend == []
    assert all(row.count == 0 for row in result.surface_usage)


def test_product_metrics_outputs_are_pii_free() -> None:
    now = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    with db_session.SessionLocal() as db:
        user = _make_user(
            db,
            email="secret@patient.clara",
            last_login_at=now,
            created_at=now - timedelta(days=5),
        )
        session_row = SessionModel(user_id=user.id, title="S")
        db.add(session_row)
        db.flush()
        db.add(
            QueryModel(
                session_id=session_row.id,
                role="normal",
                user_input="I take warfarin and aspirin daily",
                response_text="sensitive",
                created_at=now,
            )
        )
        db.commit()
        result = AnalyticsAggregator().product_metrics(db, start=start, end=end)

    serialized = result.model_dump_json()
    assert "secret@patient.clara" not in serialized
    assert "warfarin" not in serialized.lower()
    assert "aspirin" not in serialized.lower()


# ---------------------------------------------------------------------------
# clinical_metrics
# ---------------------------------------------------------------------------


def _event(timestamp: datetime, event: dict, *, source: str = "chat", **extra) -> dict:
    record = {
        "timestamp": timestamp.isoformat(),
        "source": source,
        "user_id": "u1",
        "role": "normal",
        "intent": extra.get("intent"),
        "model_used": extra.get("model_used"),
        "event": event,
    }
    return record


def test_clinical_metrics_aggregates_verdicts_and_blocked_claims() -> None:
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    ts = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)
    out_ts = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)

    flow_events = {
        "items": [
            _event(ts, {"stage": "verification", "status": "pass", "confidence": 0.95}),
            _event(ts, {"stage": "verification", "status": "warn", "confidence": 0.6}),
            _event(ts, {"stage": "verification", "status": "fail", "confidence": 0.3}),
            _event(ts, {"stage": "legal_guard", "status": "blocked"}),
            # out of range — excluded
            _event(out_ts, {"stage": "verification", "status": "pass"}),
        ]
    }

    result = AnalyticsAggregator().clinical_metrics(
        None, flow_events, {}, start=start, end=end
    )

    assert isinstance(result, ClinicalAnalytics)
    assert result.range == (start, end)
    assert result.verdicts.verified == 1
    assert result.verdicts.partially_verified == 1
    assert result.verdicts.contested == 1
    assert result.verdicts.blocked_claims == 1
    assert result.router_confidence == {"high": 1, "medium": 1, "low": 1}
    assert result.has_data is True


def test_clinical_metrics_ddi_severity_and_fallback_and_latency() -> None:
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    ts = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)

    flow_events = {
        "items": [
            _event(
                ts,
                {"stage": "ddi_aggregation", "risk_level": "medium", "latency_ms": 100.0},
                source="careguard",
            ),
            _event(
                ts,
                {"stage": "ddi_aggregation", "risk_level": "high", "latency_ms": 300.0},
                source="careguard",
            ),
            _event(
                ts,
                {"status": "completed", "fallback_used": True, "latency_ms": 50.0},
                source="research",
                intent="research_tier2",
                model_used="deepseek-deep_beta",
            ),
        ]
    }

    result = AnalyticsAggregator().clinical_metrics(
        None, flow_events, {}, start=start, end=end
    )

    assert result.ddi_severity.medium == 1
    assert result.ddi_severity.high == 1
    # 1 fallback out of 3 in-range events.
    assert result.fallback_rate_pct == round((1 / 3) * 100.0, 3)
    tiers = {row.tier for row in result.latency}
    assert "council" not in tiers
    assert "tier2_deep_beta" in tiers
    for row in result.latency:
        assert row.p50_ms <= row.p90_ms <= row.p99_ms


def test_clinical_metrics_falls_back_to_metrics_snapshot_latency() -> None:
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    metrics = {"requests_total": 10, "avg_latency_ms": 42.5}

    result = AnalyticsAggregator().clinical_metrics(
        None, {"items": []}, metrics, start=start, end=end
    )

    assert result.has_data is True
    assert len(result.latency) == 1
    assert result.latency[0].tier == "tier1"
    assert result.latency[0].p50_ms == 42.5


def test_clinical_metrics_empty_reports_no_data() -> None:
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    result = AnalyticsAggregator().clinical_metrics(
        None, {"items": []}, {}, start=start, end=end
    )
    assert result.has_data is False
    assert result.latency == []
    assert result.fallback_rate_pct == 0.0
