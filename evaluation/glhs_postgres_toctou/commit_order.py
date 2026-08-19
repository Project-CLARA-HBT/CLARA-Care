"""Commit-order instrumentation for the GLHS concurrency repetition study.

Per master-spec section 3.5, where the operator-owned isolated research
PostgreSQL permits, ``track_commit_timestamp=on`` is used and the durable
commit timestamps of both transactions are read back with
``pg_xact_commit_timestamp(xid)`` *after* both transactions have completed.
This is instrumentation, not production logic.

Hard rule:

    Ordering is NEVER inferred from transaction-id numeric order alone.
    PostgreSQL transaction ids indicate assignment order, not commit order.
    If database-level order remains unknowable for a repetition, the ordering
    confidence is ``INDETERMINATE`` and that is recorded honestly.

Confidence vocabulary (frozen in ``repeat_manifest``):

- ``DIRECT_ORDER_EVIDENCE``: at least two distinct durable commit timestamps
  establish the order directly.
- ``PARTIAL``: some durable commit timestamp evidence (or a strict monotonic
  client trace) exists but does not fully separate the two commits.
- ``INDETERMINATE``: no durable commit timestamp evidence; order unknowable.

This module never fabricates results and holds no global mutable state except
per-probe instance state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from evaluation.glhs_postgres_toctou.repeat_manifest import (
    ORDERING_CONFIDENCE_DIRECT,
    ORDERING_CONFIDENCE_INDETERMINATE,
    ORDERING_CONFIDENCE_PARTIAL,
)

MONOTONIC_EVIDENCE_NONE = "none"
MONOTONIC_EVIDENCE_STRICT = "strict_monotonic_client_order"


def probe_commit_timestamp_availability(connection: Any) -> dict[str, object]:
    """Probe ``track_commit_timestamp`` on the operator-owned research database.

    ``connection`` is any duck-typed handle exposing ``scalar(text(...))``.
    Returns the frozen availability flag plus the server-reported value.
    """
    try:
        setting = str(connection.scalar(text("SHOW track_commit_timestamp")) or "").strip().lower()
    except (SQLAlchemyError, TypeError, ValueError) as exc:  # pragma: no cover - defensive; never fabricate
        return {
            "available": False,
            "track_commit_timestamp": "unknown",
            "note": f"probe_failed:{type(exc).__name__}",
        }
    available = setting == "on"
    return {
        "available": available,
        "track_commit_timestamp": setting,
        "note": (
            "durable_commit_timestamps_available"
            if available
            else "durable_commit_timestamps_unavailable_recording_indeterminate"
        ),
    }


def classify_ordering_confidence(
    *,
    txids: Sequence[int],
    commit_timestamps: Mapping[int, str | None],
    monotonic_evidence: str = MONOTONIC_EVIDENCE_NONE,
) -> tuple[str, str]:
    """Classify ordering confidence from durable commit timestamps.

    Pure and deterministic. Transaction-id numeric order is never consulted.
    ``commit_timestamps`` maps a captured xid to its ISO-8601 commit timestamp
    (or ``None`` when ``pg_xact_commit_timestamp`` returned NULL / the setting
    was off).
    """
    resolved: list[tuple[int, str]] = [
        (xid, ts) for xid, ts in commit_timestamps.items() if ts is not None and xid in set(txids)
    ]
    if len(resolved) >= 2:
        distinct = len({ts for _xid, ts in resolved}) == len(resolved)
        if distinct:
            return (
                ORDERING_CONFIDENCE_DIRECT,
                "distinct_durable_commit_timestamps_establish_order",
            )
        return (
            ORDERING_CONFIDENCE_PARTIAL,
            "durable_commit_timestamps_available_but_equal",
        )
    if len(resolved) == 1:
        return (
            ORDERING_CONFIDENCE_PARTIAL,
            "single_durable_commit_timestamp_available",
        )
    if monotonic_evidence == MONOTONIC_EVIDENCE_STRICT:
        return (
            ORDERING_CONFIDENCE_PARTIAL,
            "strict_monotonic_client_trace_only_no_durable_timestamps",
        )
    return (
        ORDERING_CONFIDENCE_INDETERMINATE,
        "track_commit_timestamp_unavailable_no_durable_order",
    )


class CommitTimestampProbe:
    """Captures in-transaction xids and resolves durable commit timestamps.

    ``capture_xid_before_commit`` must be called while the transaction is still
    open (SQLAlchemy ``before_commit`` event or an explicit call immediately
    before ``session.commit()``), so ``txid_current()`` returns the xid of the
    transaction that is about to commit. After both transactions complete,
    ``resolve_commit_timestamps`` reads ``pg_xact_commit_timestamp(xid)`` for
    every captured xid in a fresh connection.
    """

    def __init__(self, *, availability: Mapping[str, object] | None = None) -> None:
        self._availability: Mapping[str, object] = (
            dict(availability)
            if availability is not None
            else {"available": False, "track_commit_timestamp": "off", "note": "not_probed"}
        )
        self._captured: dict[str, int] = {}
        self._auto_index = 0

    @property
    def availability(self) -> Mapping[str, object]:
        return self._availability

    @property
    def captured(self) -> Mapping[str, int]:
        return dict(self._captured)

    def record_availability(self, availability: Mapping[str, object]) -> None:
        self._availability = dict(availability)

    def capture_xid_before_commit(self, session: Any, party: str | None = None) -> int | None:
        """Capture the current transaction's xid immediately before commit.

        ``party`` labels the captured xid. When omitted, a stable
        ``tx-{n}`` label is auto-assigned, so every committed transaction is
        retained even when the session does not know which logical party it
        belongs to.
        """
        try:
            xid = int(session.scalar(text("SELECT txid_current()")))
        except (TypeError, ValueError):
            return None
        label = party if party else f"tx-{self._auto_index}"
        self._auto_index += 1
        self._captured[label] = xid
        return xid

    def resolve_commit_timestamps(self, connection: Any) -> dict[str, object]:
        """Resolve durable commit timestamps for all captured xids.

        ``connection`` is a fresh duck-typed handle exposing
        ``scalar(text(...), params)``. A NULL or error result for a single xid
        is recorded as ``None`` for that xid and never fabricated.
        """
        resolved: dict[str, object] = {}
        for party, xid in self._captured.items():
            timestamp: str | None = None
            try:
                raw = connection.scalar(
                    text("SELECT pg_xact_commit_timestamp(:xid)::text"), {"xid": xid}
                )
                if raw is not None:
                    timestamp = str(raw)
            except (SQLAlchemyError, TypeError, ValueError):
                timestamp = None
            resolved[party] = {
                "txid": xid,
                "commit_timestamp": timestamp,
                "durable_available": timestamp is not None,
            }
        return resolved

    def classify(self, resolved: Mapping[str, object]) -> tuple[str, str]:
        """Classify ordering confidence from the resolved commit timestamps."""
        txids = [int(item["txid"]) for item in resolved.values()]
        timestamps: dict[int, str | None] = {
            int(item["txid"]): (str(item["commit_timestamp"]) if item["commit_timestamp"] else None)
            for item in resolved.values()
        }
        monotonic = (
            MONOTONIC_EVIDENCE_STRICT
            if bool(self._availability.get("available"))
            else MONOTONIC_EVIDENCE_NONE
        )
        return classify_ordering_confidence(
            txids=txids, commit_timestamps=timestamps, monotonic_evidence=monotonic
        )


def attach_before_commit_capture(session: Any, probe: CommitTimestampProbe, party: str) -> None:
    """Attach a SQLAlchemy ``before_commit`` listener capturing the xid.

    For real SQLAlchemy sessions only. Duck-typed fake sessions are captured by
    calling ``probe.capture_xid_before_commit(session, party)`` directly in the
    runner.
    """
    from sqlalchemy import event

    def _on_before_commit(sess: Any) -> None:
        probe.capture_xid_before_commit(sess, party)

    event.listen(session, "before_commit", _on_before_commit)


def iso_now() -> str:
    """ISO-8601 UTC timestamp for execution records."""
    return datetime.now(UTC).isoformat()
