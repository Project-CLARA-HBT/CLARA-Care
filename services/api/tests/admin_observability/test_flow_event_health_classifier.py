"""Unit tests for the extracted flow-event health classifier (spec task 5.3).

Feature: clara-admin-observability

Covers Requirements 5.4 / 5.5: the pure ``classify_flow_event_health`` projection
must reproduce the previously-inlined ``/ecosystem`` ``ok``/``degraded``/``down``
decision exactly (age + count + error ratio). These are example/edge tests that
pin the behavior; the universal staleness-rule property (P11) lands in the
``[PBT]`` sub-task 5.4.
"""

from __future__ import annotations

from clara_api.api.v1.endpoints.system import (
    FLOW_EVENT_ERROR_RATIO_THRESHOLD,
    FLOW_EVENT_STALENESS_MINUTES,
    classify_flow_event_health,
)


def test_down_when_no_events_and_unknown_age() -> None:
    assert (
        classify_flow_event_health(
            minutes_since_last_event=None, event_count=0, error_ratio=1.0
        )
        == "down"
    )


def test_degraded_when_stale_with_items() -> None:
    assert (
        classify_flow_event_health(
            minutes_since_last_event=FLOW_EVENT_STALENESS_MINUTES + 0.1,
            event_count=5,
            error_ratio=0.0,
        )
        == "degraded"
    )


def test_down_when_stale_age_but_no_items() -> None:
    assert (
        classify_flow_event_health(
            minutes_since_last_event=FLOW_EVENT_STALENESS_MINUTES + 100.0,
            event_count=0,
            error_ratio=0.0,
        )
        == "down"
    )


def test_degraded_when_fresh_but_error_ratio_at_threshold() -> None:
    assert (
        classify_flow_event_health(
            minutes_since_last_event=1.0,
            event_count=10,
            error_ratio=FLOW_EVENT_ERROR_RATIO_THRESHOLD,
        )
        == "degraded"
    )


def test_ok_when_fresh_and_low_error_ratio() -> None:
    assert (
        classify_flow_event_health(
            minutes_since_last_event=1.0,
            event_count=10,
            error_ratio=FLOW_EVENT_ERROR_RATIO_THRESHOLD - 0.01,
        )
        == "ok"
    )


def test_boundary_age_at_threshold_is_not_stale() -> None:
    # Strictly greater-than staleness rule: exactly at the threshold is fresh.
    assert (
        classify_flow_event_health(
            minutes_since_last_event=FLOW_EVENT_STALENESS_MINUTES,
            event_count=3,
            error_ratio=0.0,
        )
        == "ok"
    )
