"""Unit tests for the opt-in durable flow-event sink (spec task 7.1).

Feature: clara-admin-observability

Covers Requirements 7.1 (durable, range-queryable mirror of Flow_Events), 7.2
(flags-off ⇒ in-memory baseline; flags-on ⇒ persisted + queryable), and 11.1
(the durable mirror is PII-free). These are example/contract tests that pin the
sink's behavior; the universal properties (P15 toggle equivalence, P16
windowing) land in the ``[PBT]`` sub-tasks 7.2/7.3.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.core.flow_event_store import FlowEventStore
from clara_api.observability.flow_event_sink import FlowEventSink, get_flow_event_sink

from . import adversarial_pii_payload, assert_no_pii


def _record(
    *,
    sequence: int,
    timestamp: datetime,
    source: str = "careguard",
    role: str = "doctor",
    intent: str | None = "ddi_check",
    model_used: str | None = "tier1",
    event: dict | None = None,
) -> dict:
    """Build a record shaped like a ``FlowEventStore`` entry."""

    return {
        "sequence": sequence,
        "timestamp": timestamp.isoformat(),
        "source": source,
        "user_id": "patient.zero@example.com",  # must never reach the archive
        "role": role,
        "intent": intent,
        "model_used": model_used,
        "event": event if event is not None else {"status": "pass"},
    }


# ---------------------------------------------------------------------------
# Flags-off ⇒ no-op baseline (Requirement 7.2)
# ---------------------------------------------------------------------------
def test_persist_is_noop_when_disabled() -> None:
    sink = FlowEventSink()
    now = datetime.now(tz=UTC)
    # With the durable-store flag off (default), persist writes nothing and
    # query returns an empty list — the pre-feature baseline.
    sink.persist(_record(sequence=1, timestamp=now))
    assert sink.query(start=now.date(), end=now.date()) == []


def test_aggregator_reads_in_memory_snapshot_when_disabled() -> None:
    now = datetime.now(tz=UTC)
    today = now.date()
    snapshot = {
        "items": [
            {
                "timestamp": now.isoformat(),
                "source": "chat",
                "role": "normal",
                "event": {"status": "blocked"},
            }
        ]
    }
    # Flag off → aggregator folds the passed in-memory snapshot, not the sink.
    result = AnalyticsAggregator().clinical_metrics(None, snapshot, {}, start=today, end=today)
    assert result.verdicts.blocked_claims == 1
    assert result.has_data is True


# ---------------------------------------------------------------------------
# Flags-on ⇒ persisted, PII-free, range-queryable (Requirements 7.1, 11.1)
# ---------------------------------------------------------------------------
def test_persist_mirrors_pii_free_and_query_returns_record(
    set_flags: Callable[..., None],
) -> None:
    set_flags(admin_observability_persistent_store_enabled=True)
    sink = get_flow_event_sink()
    now = datetime.now(tz=UTC)

    # Seed the event with adversarial PII; only coarse signals may survive.
    event = adversarial_pii_payload()
    sink.persist(_record(sequence=7, timestamp=now, event=event))

    rows = sink.query(start=now.date(), end=now.date())
    assert len(rows) == 1
    row = rows[0]
    assert row["sequence"] == 7
    assert row["source"] == "careguard"
    assert row["role"] == "doctor"
    assert row["intent"] == "ddi_check"
    # Coarse, non-identifying signals survive the projection.
    assert row["event"]["status"] == "blocked"
    assert row["event"]["count"] == event["count"]
    # No user_id column exists on the archive, so the (PII) user ref is dropped.
    assert "user_id" not in row
    # Nothing PII leaked through the projected row.
    assert_no_pii(rows)


def test_query_excludes_out_of_range(set_flags: Callable[..., None]) -> None:
    set_flags(admin_observability_persistent_store_enabled=True)
    sink = get_flow_event_sink()

    in_range = datetime.now(tz=UTC)
    out_of_range = datetime(2020, 1, 1, tzinfo=UTC)
    sink.persist(_record(sequence=1, timestamp=out_of_range))
    sink.persist(_record(sequence=2, timestamp=in_range))

    rows = sink.query(start=in_range.date(), end=in_range.date())
    assert [r["sequence"] for r in rows] == [2]


def test_query_inclusive_window(set_flags: Callable[..., None]) -> None:
    set_flags(admin_observability_persistent_store_enabled=True)
    sink = get_flow_event_sink()

    # An event at the very start of the day on the lower bound is included.
    boundary = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)
    sink.persist(_record(sequence=1, timestamp=boundary))
    rows = sink.query(start=date(2024, 6, 1), end=date(2024, 6, 1))
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Aggregator-read switch (Requirement 7.1/7.2)
# ---------------------------------------------------------------------------
def test_aggregator_reads_from_sink_when_enabled(set_flags: Callable[..., None]) -> None:
    set_flags(admin_observability_persistent_store_enabled=True)
    sink = get_flow_event_sink()
    now = datetime.now(tz=UTC)
    today = now.date()
    sink.persist(
        _record(
            sequence=1,
            timestamp=now,
            source="chat",
            role="normal",
            event={"status": "blocked"},
        )
    )

    # Pass an EMPTY in-memory snapshot: the aggregator must pull from the sink.
    result = AnalyticsAggregator().clinical_metrics(None, {"items": []}, {}, start=today, end=today)
    assert result.verdicts.blocked_claims == 1
    assert result.has_data is True


# ---------------------------------------------------------------------------
# End-to-end: FlowEventStore.append mirrors into the sink when enabled
# ---------------------------------------------------------------------------
def test_append_mirrors_into_sink(set_flags: Callable[..., None]) -> None:
    set_flags(admin_observability_persistent_store_enabled=True)
    store = FlowEventStore()
    now = datetime.now(tz=UTC)
    store.append(
        source="chat",
        user_id="patient.zero@example.com",
        role="normal",
        intent=None,
        model_used=None,
        event={"status": "pass", "confidence": 0.9},
        occurred_at=now.isoformat(),
    )

    rows = get_flow_event_sink().query(start=now.date(), end=now.date())
    assert len(rows) == 1
    assert rows[0]["source"] == "chat"
    assert_no_pii(rows)


def test_append_does_not_mirror_when_disabled() -> None:
    store = FlowEventStore()
    now = datetime.now(tz=UTC)
    store.append(
        source="chat",
        user_id="u@example.com",
        role="normal",
        intent=None,
        model_used=None,
        event={"status": "pass"},
        occurred_at=now.isoformat(),
    )
    # Durable store disabled by default → nothing mirrored.
    assert get_flow_event_sink().query(start=now.date(), end=now.date()) == []
