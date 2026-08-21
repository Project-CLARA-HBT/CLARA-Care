"""Tests for commit-order instrumentation.

These tests prove the ordering confidence classifier never infers order from
transaction-id numeric order and honestly reports INDETERMINATE when durable
commit timestamps are unavailable. No database is connected.
"""

from __future__ import annotations

from evaluation.glhs_postgres_toctou.commit_order import (
    CommitTimestampProbe,
    classify_ordering_confidence,
    probe_commit_timestamp_availability,
)
from evaluation.glhs_postgres_toctou.repeat_manifest import (
    ORDERING_CONFIDENCE_DIRECT,
    ORDERING_CONFIDENCE_INDETERMINATE,
    ORDERING_CONFIDENCE_PARTIAL,
)


class FakeScalar:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar(self, _statement: object, _params: object | None = None) -> object:
        return self._value


def test_probe_reports_available_when_track_commit_timestamp_on() -> None:
    result = probe_commit_timestamp_availability(FakeScalar("on"))
    assert result["available"] is True
    assert result["track_commit_timestamp"] == "on"


def test_probe_reports_unavailable_when_off() -> None:
    result = probe_commit_timestamp_availability(FakeScalar("off"))
    assert result["available"] is False
    assert result["track_commit_timestamp"] == "off"


def test_direct_evidence_from_distinct_durable_timestamps() -> None:
    confidence, reason = classify_ordering_confidence(
        txids=[101, 102],
        commit_timestamps={
            101: "2026-08-19T00:00:00.000Z",
            102: "2026-08-19T00:00:01.000Z",
        },
    )
    assert confidence == ORDERING_CONFIDENCE_DIRECT
    assert "distinct_durable_commit_timestamps" in reason


def test_never_infers_order_from_txid_numeric_order() -> None:
    # txid 102 numerically precedes 101 yet has no timestamp; ordering must be
    # INDETERMINATE, never derived from the numeric txid order.
    confidence, _reason = classify_ordering_confidence(
        txids=[101, 102], commit_timestamps={101: None, 102: None}
    )
    assert confidence == ORDERING_CONFIDENCE_INDETERMINATE


def test_partial_when_single_durable_timestamp() -> None:
    confidence, reason = classify_ordering_confidence(
        txids=[101, 102], commit_timestamps={101: "2026-08-19T00:00:00.000Z", 102: None}
    )
    assert confidence == ORDERING_CONFIDENCE_PARTIAL
    assert "single_durable_commit_timestamp" in reason


def test_partial_on_equal_timestamps() -> None:
    confidence, reason = classify_ordering_confidence(
        txids=[101, 102],
        commit_timestamps={
            101: "2026-08-19T00:00:00.000Z",
            102: "2026-08-19T00:00:00.000Z",
        },
    )
    assert confidence == ORDERING_CONFIDENCE_PARTIAL
    assert "equal" in reason


def test_indeterminate_when_unavailable_and_no_client_trace() -> None:
    confidence, reason = classify_ordering_confidence(
        txids=[101, 102], commit_timestamps={101: None, 102: None}
    )
    assert confidence == ORDERING_CONFIDENCE_INDETERMINATE
    assert "track_commit_timestamp_unavailable" in reason


def test_probe_captures_xid_before_commit_and_resolves() -> None:
    probe = CommitTimestampProbe(
        availability={"available": True, "track_commit_timestamp": "on", "note": "available"}
    )

    class FakeSession:
        def scalar(self, _statement: object) -> object:
            return 9001

    assert probe.capture_xid_before_commit(FakeSession(), party="governance") == 9001

    resolved = probe.resolve_commit_timestamps(FakeScalar("2026-08-19T00:00:00.000Z"))
    assert resolved["governance"]["txid"] == 9001
    assert resolved["governance"]["durable_available"] is True
    assert resolved["governance"]["commit_timestamp"] == "2026-08-19T00:00:00.000Z"

    confidence, _reason = probe.classify(resolved)
    assert confidence in {ORDERING_CONFIDENCE_DIRECT, ORDERING_CONFIDENCE_PARTIAL}


def test_probe_auto_labels_multiple_captures() -> None:
    probe = CommitTimestampProbe()

    class FakeSession:
        def __init__(self, value: int) -> None:
            self._value = value

        def scalar(self, _statement: object) -> object:
            return self._value

    probe.capture_xid_before_commit(FakeSession(11))
    probe.capture_xid_before_commit(FakeSession(12))
    captured = probe.captured
    assert set(captured) == {"tx-0", "tx-1"}
    assert set(captured.values()) == {11, 12}
