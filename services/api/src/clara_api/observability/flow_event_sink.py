"""Opt-in durable flow-event sink (Requirement 7).

The runtime telemetry path keeps Flow_Events in a bounded in-memory
``FlowEventStore`` deque (``maxlen=1000``). That window is fine for live
streaming but is lost on restart and cannot serve analytics over a date range
that predates the deque. Behind ``admin_observability_persistent_store_enabled``
this module mirrors each appended Flow_Event into the durable
``flow_event_archive`` table so the analytics aggregator can query beyond the
in-memory capacity and across process restarts (Requirements 7.1, 7.2).

Two collaborators:

* :func:`FlowEventStore.append <clara_api.core.flow_event_store.FlowEventStore>`
  calls :meth:`FlowEventSink.persist` (best-effort, flag-gated) so every appended
  event is mirrored. The append path never breaks on a sink failure.
* :meth:`AnalyticsAggregator.clinical_metrics
  <clara_api.api.v1.endpoints.analytics.AnalyticsAggregator.clinical_metrics>`
  reads from :meth:`FlowEventSink.query` when the flag is enabled, else from the
  in-memory store that was passed in — so flags-off behavior equals the
  pre-feature baseline (Requirement 7.2).

Privacy by projection: the persisted ``event_json`` is the
``AnalyticsAggregator._project_pii_free`` projection of the Flow_Event's event
payload, further scrubbed by ``research_telemetry.strip_pii`` (PHR/identity
container denylist + email/long-digit value scrubbing), and the durable row
carries only opaque/structural fields
(``sequence``, ``source``, ``role``, ``intent``, ``model_used``,
``occurred_at``) — never ``user_id``, names, emails, free-text, or drug lists.
Durability therefore never introduces a PII surface (Requirement 11.1).

The ``flow_event_archive`` table is created by a separate Alembic migration
(spec task 1.3, revision ``20260420_0016``); this module declares a lightweight
ORM model bound to the shared :class:`~clara_api.db.base.Base` metadata that
mirrors that table. The model lives here (rather than in ``db/models.py``) to
keep the additive durable-store capability self-contained.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.core.config import get_settings
from clara_api.core.research_telemetry import strip_pii
from clara_api.db.base import Base

# Column bounds mirror the design data model / migration (spec task 1.3) so an
# application write never overflows the migrated schema.
_SOURCE_MAX = 48
_ROLE_MAX = 16
_INTENT_MAX = 48
_MODEL_USED_MAX = 64


def _now_utc() -> datetime:
    """Timezone-aware UTC ``now`` (parallels the audit-module helper)."""

    return datetime.now(UTC)


class FlowEventArchive(Base):
    """One PII-free durable mirror of a Flow_Event (table ``flow_event_archive``).

    Insert-only by convention: the sink only appends rows, mirroring the
    append-only in-memory deque it shadows.
    """

    __tablename__ = "flow_event_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Mirrors the in-memory ``FlowEventStore`` sequence (monotonic per process).
    sequence: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(_SOURCE_MAX), nullable=False)
    role: Mapped[str] = mapped_column(String(_ROLE_MAX), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(_INTENT_MAX), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(_MODEL_USED_MAX), nullable=True)
    # ``_project_pii_free``-projected event payload (verdict/status/confidence/
    # latency) — never raw query/answer/transcript/drug content.
    event_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, index=True, nullable=False
    )

    def as_record(self) -> dict[str, Any]:
        """Return a record shaped like an in-memory ``FlowEventStore`` entry.

        The shape (``timestamp``/``source``/``role``/``intent``/``model_used``/
        ``event``) matches what :class:`AnalyticsAggregator` consumes, so the
        durable read is a drop-in replacement for the in-memory snapshot.
        """

        occurred = self.occurred_at
        return {
            "sequence": self.sequence,
            "timestamp": occurred.isoformat() if occurred is not None else None,
            "source": self.source,
            "role": self.role,
            "intent": self.intent,
            "model_used": self.model_used,
            "event": self.event_json or {},
        }


def _truncate(value: Any, limit: int) -> str | None:
    """Coerce ``value`` to a bounded string (``None`` preserved for nullables)."""

    if value is None:
        return None
    return str(value)[:limit]


def _resolve_occurred_at(record: dict[str, Any]) -> datetime:
    """Resolve a UTC-aware ``occurred_at`` from a flow-event record."""

    parsed = AnalyticsAggregator._as_utc(record.get("timestamp"))
    return parsed if parsed is not None else _now_utc()


class FlowEventSink:
    """Durable, opt-in mirror of the in-memory ``FlowEventStore``.

    The sink owns its own short-lived sessions (created from ``SessionLocal``)
    so it can be driven from the append path without threading a request-scoped
    session through the telemetry plumbing. Each public method is gated by
    ``admin_observability_persistent_store_enabled`` and is a no-op when the flag
    is off, preserving the pre-feature baseline (Requirements 7.2, 12.2).
    """

    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _enabled() -> bool:
        return bool(get_settings().admin_observability_persistent_store_enabled)

    def _make_session(self) -> Session:
        if self._session_factory is not None:
            return self._session_factory()
        # Lazy import avoids importing the engine at module load (and keeps the
        # core telemetry path import-light when the feature is off).
        from clara_api.db.session import SessionLocal

        return SessionLocal()

    def persist(self, record: dict[str, Any]) -> None:
        """Mirror one appended Flow_Event into the durable archive (PII-free).

        The event payload is projected through
        ``AnalyticsAggregator._project_pii_free`` so only counts/verdicts/
        statuses/latencies survive (Requirement 11.1). A no-op when the durable
        store is disabled (Requirement 7.2).
        """

        if not self._enabled():
            return

        event = record.get("event")
        projected_event = AnalyticsAggregator._project_pii_free(
            event if isinstance(event, dict) else {}
        )
        # Defense-in-depth: the design's PII-free projection contract reuses both
        # ``_project_pii_free`` (analytics key-denylist) and
        # ``research_telemetry.strip_pii`` (PHR/identity container denylist +
        # email/long-digit value scrubbing). Composing them guarantees no PII —
        # including value-level markers under non-denylisted keys — ever reaches
        # the durable archive (Requirement 11.1).
        projected_event = strip_pii(projected_event)
        row = FlowEventArchive(
            sequence=int(record.get("sequence") or 0),
            source=_truncate(record.get("source"), _SOURCE_MAX) or "",
            role=_truncate(record.get("role"), _ROLE_MAX) or "",
            intent=_truncate(record.get("intent"), _INTENT_MAX),
            model_used=_truncate(record.get("model_used"), _MODEL_USED_MAX),
            event_json=projected_event,
            occurred_at=_resolve_occurred_at(record),
        )

        session = self._make_session()
        try:
            session.add(row)
            session.commit()
        finally:
            session.close()

    def query(self, *, start: date, end: date) -> list[dict[str, Any]]:
        """Return archived flow events within the inclusive ``[start, end]`` range.

        Records are shaped like in-memory ``FlowEventStore`` entries (see
        :meth:`FlowEventArchive.as_record`) and ordered oldest-first by sequence
        so the aggregator consumes them exactly as it consumes the live
        snapshot. Returns an empty list when the durable store is disabled
        (Requirement 7.2).
        """

        if not self._enabled():
            return []

        # Inclusive date window → half-open datetime bounds in UTC so a row at
        # any time on ``end`` is included (Requirement 7.3).
        lower = datetime.combine(start, time.min, tzinfo=UTC)
        upper = datetime.combine(end, time.max, tzinfo=UTC)

        session = self._make_session()
        try:
            stmt = (
                select(FlowEventArchive)
                .where(FlowEventArchive.occurred_at >= lower)
                .where(FlowEventArchive.occurred_at <= upper)
                .order_by(FlowEventArchive.sequence.asc(), FlowEventArchive.id.asc())
            )
            return [row.as_record() for row in session.execute(stmt).scalars()]
        finally:
            session.close()


_FLOW_EVENT_SINK = FlowEventSink()


def get_flow_event_sink() -> FlowEventSink:
    """Return the process-wide durable flow-event sink singleton."""

    return _FLOW_EVENT_SINK
