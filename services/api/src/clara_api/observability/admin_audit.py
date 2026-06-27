"""Append-only admin-action audit trail (Requirement 9).

Every privileged admin mutation (knowledge-source create/upload/document-status,
RAG source update, ingestion/eval trigger, alert acknowledge) appends exactly
one :class:`AdminAuditRecord` capturing an *opaque* actor reference, the action,
the target identifier, the outcome, a PII-free ``meta_json`` payload, and a
timestamp (Requirement 9.1). The trail is **append-only**: this module exposes
only inserts and a most-recent-first read — there is no update or delete path
(Requirements 9.2, 9.4), mirroring the established ``phr/audit.py`` discipline.

Both the write and the read are gated by ``admin_audit_log_enabled``. With the
flag off, :func:`record_admin_action` is an inert no-op (returns ``None``,
writes nothing) and :func:`list_admin_actions` returns an empty list, so the
pre-feature baseline behavior is preserved (Requirements 12.2, 12.4).

The ``admin_audit_log`` table is created by a separate Alembic migration
(spec task 1.3); this module declares a lightweight ORM model bound to the
shared :class:`~clara_api.db.base.Base` metadata that mirrors that table. The
model lives here (rather than in ``db/models.py``) to keep the additive audit
capability self-contained.

No PII is ever stored: ``actor_ref`` is an opaque (hashed) user reference and
``meta_json`` is passed through the existing PII-free projection
(``AnalyticsAggregator._project_pii_free``) so only counts/flags/identifiers
survive — never names, emails, free-text, or drug lists (Requirements 9.3,
11.3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.core.config import get_settings
from clara_api.db.base import Base

# Action vocabulary (kept short and stable so the trail is greppable). These
# mirror the design's ``admin_audit_log.action`` examples; callers may pass any
# bounded string, but using these constants keeps the trail consistent.
ACTION_KB_SOURCE_CREATE = "kb_source.create"
ACTION_KB_SOURCE_UPLOAD = "kb_source.upload"
ACTION_KB_DOCUMENT_STATUS = "kb_document.status"
ACTION_RAG_SOURCE_UPDATE = "rag_source.update"
ACTION_INGESTION_RUN = "ingestion.run"
ACTION_EVAL_RUN = "eval.run"
ACTION_ALERT_ACK = "alert.ack"

# Outcome vocabulary.
OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"

# Column bounds mirror the design data model so application writes never exceed
# the migrated schema (spec task 1.3).
_ACTOR_REF_MAX = 64
_ACTION_MAX = 48
_TARGET_MAX = 128
_OUTCOME_MAX = 16


def _now_utc() -> datetime:
    """Timezone-aware UTC ``now`` (parallels the compliance audit helpers)."""

    return datetime.now(UTC)


class AdminAuditRecord(Base):
    """One immutable admin-action audit row (table ``admin_audit_log``).

    Insert-only by convention: nothing in this module (or, per Requirement 9.2,
    in application code) updates or deletes a committed row.
    """

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Opaque (hashed) actor reference — never a raw email / user id / name.
    actor_ref: Mapped[str] = mapped_column(String(_ACTOR_REF_MAX), index=True)
    action: Mapped[str] = mapped_column(String(_ACTION_MAX), index=True)
    target: Mapped[str] = mapped_column(String(_TARGET_MAX), default="")
    outcome: Mapped[str] = mapped_column(String(_OUTCOME_MAX), default=OUTCOME_SUCCESS)
    # Counts / flags only — never PII (projected on write).
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, index=True
    )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable, PII-free view of this record."""

        created = self.created_at
        return {
            "id": self.id,
            "actor_ref": self.actor_ref,
            "action": self.action,
            "target": self.target,
            "outcome": self.outcome,
            "meta": self.meta_json or {},
            "created_at": created.isoformat() if created is not None else None,
        }


def _truncate(value: Any, limit: int) -> str:
    """Coerce ``value`` to a bounded string so a write never overflows a column."""

    text = "" if value is None else str(value)
    return text[:limit]


def record_admin_action(
    db: Session,
    actor_ref: str,
    action: str,
    target: str = "",
    outcome: str = OUTCOME_SUCCESS,
    meta: dict | None = None,
) -> AdminAuditRecord | None:
    """Append exactly one admin-action audit row (insert-only).

    Args:
        db: Active SQLAlchemy session (the caller owns commit/rollback).
        actor_ref: Opaque (hashed) actor reference. Must not be raw PII; the
            value is stored verbatim (bounded), so callers are responsible for
            hashing the user id before passing it.
        action: Bounded action verb (see the ``ACTION_*`` constants).
        target: Bounded target identifier (source id / job id / alert id).
        outcome: ``"success"`` or ``"failure"`` (a failed mutation still records
            a row — Requirement 9.5).
        meta: Optional structured context. Passed through the PII-free
            projection so only counts/flags/identifiers survive
            (Requirements 9.3, 11.3).

    Returns:
        The inserted :class:`AdminAuditRecord`, or ``None`` when the audit trail
        is disabled (``admin_audit_log_enabled`` off) — in which case nothing is
        written (Requirements 12.2, 12.4).
    """

    if not get_settings().admin_audit_log_enabled:
        return None

    # Project meta through the shared PII-free redaction so no names, emails,
    # free-text, or drug lists are ever persisted (Requirements 9.3, 11.3).
    projected_meta = AnalyticsAggregator._project_pii_free(dict(meta or {}))

    row = AdminAuditRecord(
        actor_ref=_truncate(actor_ref, _ACTOR_REF_MAX),
        action=_truncate(action, _ACTION_MAX),
        target=_truncate(target, _TARGET_MAX),
        outcome=_truncate(outcome, _OUTCOME_MAX),
        meta_json=projected_meta,
        created_at=_now_utc(),
    )
    db.add(row)
    db.flush()  # assign id without committing; caller owns the transaction.
    return row


def list_admin_actions(db: Session, *, limit: int | None = None) -> list[AdminAuditRecord]:
    """Return admin-action audit rows ordered most-recent-first (Requirement 9.4).

    Returns an empty list when the audit trail is disabled
    (``admin_audit_log_enabled`` off), preserving the pre-feature baseline
    (Requirement 12.2). No update/delete path is exposed (Requirement 9.2).
    """

    if not get_settings().admin_audit_log_enabled:
        return []

    stmt = select(AdminAuditRecord).order_by(
        AdminAuditRecord.created_at.desc(), AdminAuditRecord.id.desc()
    )
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars())
