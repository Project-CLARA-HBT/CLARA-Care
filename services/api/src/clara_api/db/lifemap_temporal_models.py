"""LifeMap longitudinal intelligence temporal projection and invalidation models.

Provides persistence models for:
- LifeMapStateVersion: append-only, profile-scoped longitudinal state versioning
- LifeMapCacheInvalidationLedger: tamper-evident audit ledger for cache invalidations
- LifeMapTemporalProjectionCache: materialized temporal views and timeline projection cache
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clara_api.db.base import Base


def _public_id() -> str:
    """Return a non-enumerable API identifier."""
    return str(uuid4())


class LifeMapStateVersion(Base):
    """An append-only, profile-scoped version of longitudinal LifeMap health state.

    Monotonically increasing state version providing deterministic temporal
    boundaries for projection caching, conflict tracking, and bitemporal audit.
    """

    __tablename__ = "lifemap_state_versions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "state_version", name="uq_lifemap_profile_state_version"
        ),
        Index("ix_lifemap_state_versions_profile_ver", "profile_id", "state_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", server_default="default", nullable=False, index=True
    )
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(
        String(64), default="event_created", server_default="event_created", nullable=False
    )
    caused_by_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    caused_by_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    state_digest: Mapped[str | None] = mapped_column(String(72), nullable=True, index=True)
    active_event_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    effective_time_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_time_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class LifeMapCacheInvalidationLedger(Base):
    """Immutable audit and coordination ledger recording all cache invalidations.

    Tracks direct, scoped, and cascade invalidation operations against LifeMap
    temporal projection caches with idempotency and caller attribution.
    """

    __tablename__ = "lifemap_cache_invalidation_ledgers"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "idempotency_key", name="uq_lifemap_invalidation_idempotency"
        ),
        Index(
            "ix_lifemap_invalidation_scope_target",
            "profile_id",
            "invalidation_scope",
            "target_projection_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", server_default="default", nullable=False, index=True
    )
    invalidation_reason: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    invalidation_scope: Mapped[str] = mapped_column(
        String(64), default="all", server_default="all", nullable=False
    )
    target_projection_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    target_projection_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    from_state_version: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    to_state_version: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_event_revisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    affected_cache_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    cascade_depth: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    details_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class LifeMapTemporalProjectionCache(Base):
    """Materialized cache of derived LifeMap temporal views and timeline projections.

    Provides sub-millisecond query latency for timeline views, period digests,
    and biomarker trajectories while enforcing state versioning, cryptographic payload
    integrity, TTL expiration, and audit-linked cache invalidation.
    """

    __tablename__ = "lifemap_temporal_projection_caches"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "projection_type",
            "projection_key",
            "state_version",
            name="uq_lifemap_temporal_cache_identity",
        ),
        Index(
            "ix_lifemap_temporal_cache_lookup",
            "profile_id",
            "projection_type",
            "projection_key",
            "is_valid",
        ),
        Index(
            "ix_lifemap_temporal_cache_window",
            "profile_id",
            "window_start",
            "window_end",
        ),
        Index("ix_lifemap_temporal_cache_status_exp", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), default=_public_id, unique=True, index=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", server_default="default", nullable=False, index=True
    )
    projection_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    projection_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    as_of_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rule_version: Mapped[str] = mapped_column(
        String(64),
        default="lifemap_projection.v1",
        server_default="lifemap_projection.v1",
        nullable=False,
    )
    payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(72), nullable=False, index=True)
    item_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="active", server_default="active", index=True, nullable=False
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=sa.text("1"), index=True, nullable=False
    )
    cache_hit_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    invalidation_reason: Mapped[str | None] = mapped_column(String(96), nullable=True)
    invalidation_ledger_id: Mapped[int | None] = mapped_column(
        ForeignKey("lifemap_cache_invalidation_ledgers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    invalidation_ledger: Mapped[LifeMapCacheInvalidationLedger | None] = relationship(
        "LifeMapCacheInvalidationLedger"
    )
