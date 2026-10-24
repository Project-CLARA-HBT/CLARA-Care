"""LifeMap temporal projection cache management and invalidation services.

Provides high-performance caching, state version tracking, bitemporal windowing,
and tamper-evident cache invalidation ledger operations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from clara_api.db.lifemap_temporal_models import (
    LifeMapCacheInvalidationLedger,
    LifeMapStateVersion,
    LifeMapTemporalProjectionCache,
)


class LifeMapCacheError(Exception):
    """Base exception for LifeMap cache and state version errors."""


class LifeMapCacheValidationError(LifeMapCacheError):
    """Raised when projection cache inputs or parameters fail validation."""


class LifeMapStateVersionError(LifeMapCacheError):
    """Raised when longitudinal state version advancement fails."""


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalize datetime to timezone-aware UTC datetime."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def compute_payload_hash(payload: Any) -> str:
    """Compute a deterministic SHA-256 digest of canonicalized JSON payload.

    Follows RFC 8785 JSON Canonicalization Scheme principles (sorted keys,
    strict separators, UTF-8 encoding).
    """
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def get_current_state_version(db: Session, *, profile_id: int) -> int:
    """Return the current maximum state version for a profile, or 0 if uninitialized."""
    if profile_id <= 0:
        raise LifeMapCacheValidationError(f"Invalid profile_id: {profile_id}")
    val = db.execute(
        select(func.coalesce(func.max(LifeMapStateVersion.state_version), 0)).where(
            LifeMapStateVersion.profile_id == profile_id
        )
    ).scalar_one()
    return int(val)


def advance_lifemap_state_version(
    db: Session,
    *,
    profile_id: int,
    change_type: str,
    valid_at: datetime | None = None,
    caused_by_event_id: int | None = None,
    caused_by_revision_id: int | None = None,
    actor_user_id: int | None = None,
    state_digest: str | None = None,
    active_event_count: int = 0,
    effective_time_start: datetime | None = None,
    effective_time_end: datetime | None = None,
    metadata_json: dict[str, Any] | None = None,
    tenant_id: str = "default",
) -> LifeMapStateVersion:
    """Advance the profile's longitudinal state version monotonically.

    Establishes an append-only state boundary that grounds all subsequent
    temporal projection caches and invalidation checks.
    """
    if profile_id <= 0:
        raise LifeMapCacheValidationError(f"Invalid profile_id: {profile_id}")
    if not change_type or not change_type.strip():
        raise LifeMapCacheValidationError("change_type cannot be empty")

    now = datetime.now(UTC)
    clinical_valid_at = _ensure_utc(valid_at) or now

    current_version = get_current_state_version(db, profile_id=profile_id)
    next_version = current_version + 1

    computed_digest = state_digest
    if not computed_digest:
        fingerprint_data = {
            "profile_id": profile_id,
            "state_version": next_version,
            "change_type": change_type,
            "caused_by_event_id": caused_by_event_id,
            "caused_by_revision_id": caused_by_revision_id,
            "valid_at": clinical_valid_at.isoformat(),
        }
        computed_digest = compute_payload_hash(fingerprint_data)

    version_row = LifeMapStateVersion(
        profile_id=profile_id,
        tenant_id=tenant_id,
        state_version=next_version,
        change_type=change_type.strip(),
        caused_by_event_id=caused_by_event_id,
        caused_by_revision_id=caused_by_revision_id,
        actor_user_id=actor_user_id,
        state_digest=computed_digest,
        active_event_count=max(0, active_event_count),
        effective_time_start=effective_time_start,
        effective_time_end=effective_time_end,
        valid_at=clinical_valid_at,
        metadata_json=metadata_json,
    )
    db.add(version_row)
    db.flush()
    return version_row


def get_cached_temporal_projection(
    db: Session,
    *,
    profile_id: int,
    projection_type: str,
    projection_key: str,
    state_version: int | None = None,
    touch: bool = True,
) -> LifeMapTemporalProjectionCache | None:
    """Retrieve an active cached projection matching profile, type, and key.

    Verifies TTL expiration and updates cache hit metrics when valid.
    """
    if profile_id <= 0:
        raise LifeMapCacheValidationError(f"Invalid profile_id: {profile_id}")
    if not projection_type or not projection_type.strip():
        raise LifeMapCacheValidationError("projection_type cannot be empty")
    if not projection_key or not projection_key.strip():
        raise LifeMapCacheValidationError("projection_key cannot be empty")

    query = select(LifeMapTemporalProjectionCache).where(
        LifeMapTemporalProjectionCache.profile_id == profile_id,
        LifeMapTemporalProjectionCache.projection_type == projection_type.strip(),
        LifeMapTemporalProjectionCache.projection_key == projection_key.strip(),
        LifeMapTemporalProjectionCache.is_valid.is_(True),
    )
    if state_version is not None:
        if state_version < 0:
            raise LifeMapCacheValidationError(f"Invalid state_version: {state_version}")
        query = query.where(LifeMapTemporalProjectionCache.state_version == state_version)
    else:
        query = query.order_by(LifeMapTemporalProjectionCache.state_version.desc())

    row = db.execute(query).scalars().first()
    if row is None:
        return None

    now = datetime.now(UTC)
    exp = _ensure_utc(row.expires_at)
    if exp is not None and exp <= now:
        row.is_valid = False
        row.status = "expired"
        db.flush()
        return None

    if touch:
        row.cache_hit_count += 1
        row.last_accessed_at = now
        db.flush()

    return row


def set_cached_temporal_projection(
    db: Session,
    *,
    profile_id: int,
    projection_type: str,
    projection_key: str,
    payload: dict[str, Any] | list[Any],
    state_version: int,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    as_of_time: datetime | None = None,
    rule_version: str = "lifemap_projection.v1",
    ttl_seconds: int | None = None,
    item_count: int | None = None,
    tenant_id: str = "default",
) -> LifeMapTemporalProjectionCache:
    """Store or update a materialized temporal projection in the cache."""
    if profile_id <= 0:
        raise LifeMapCacheValidationError(f"Invalid profile_id: {profile_id}")
    if not projection_type or not projection_type.strip():
        raise LifeMapCacheValidationError("projection_type cannot be empty")
    if not projection_key or not projection_key.strip():
        raise LifeMapCacheValidationError("projection_key cannot be empty")
    if state_version < 0:
        raise LifeMapCacheValidationError(f"Invalid state_version: {state_version}")
    if payload is None:
        raise LifeMapCacheValidationError("payload cannot be None")

    now = datetime.now(UTC)
    payload_hash = compute_payload_hash(payload)

    if item_count is None:
        if isinstance(payload, list):
            item_count = len(payload)
        elif isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list):
            item_count = len(payload["items"])
        else:
            item_count = 1

    expires_at = None
    if ttl_seconds is not None and ttl_seconds > 0:
        expires_at = now + timedelta(seconds=ttl_seconds)

    # Check for existing cache entry with exact (profile_id, type, key, state_version)
    existing = db.execute(
        select(LifeMapTemporalProjectionCache).where(
            LifeMapTemporalProjectionCache.profile_id == profile_id,
            LifeMapTemporalProjectionCache.projection_type == projection_type.strip(),
            LifeMapTemporalProjectionCache.projection_key == projection_key.strip(),
            LifeMapTemporalProjectionCache.state_version == state_version,
        )
    ).scalars().first()

    if existing is not None:
        existing.tenant_id = tenant_id
        existing.window_start = window_start
        existing.window_end = window_end
        existing.as_of_time = as_of_time or now
        existing.rule_version = rule_version
        existing.payload_json = payload
        existing.payload_hash = payload_hash
        existing.item_count = item_count
        existing.status = "active"
        existing.is_valid = True
        existing.expires_at = expires_at
        existing.invalidated_at = None
        existing.invalidation_reason = None
        existing.invalidation_ledger_id = None
        existing.generated_at = now
        db.flush()
        return existing

    new_row = LifeMapTemporalProjectionCache(
        profile_id=profile_id,
        tenant_id=tenant_id,
        projection_type=projection_type.strip(),
        projection_key=projection_key.strip(),
        state_version=state_version,
        window_start=window_start,
        window_end=window_end,
        as_of_time=as_of_time or now,
        rule_version=rule_version,
        payload_json=payload,
        payload_hash=payload_hash,
        item_count=item_count,
        status="active",
        is_valid=True,
        cache_hit_count=0,
        expires_at=expires_at,
        generated_at=now,
    )
    db.add(new_row)
    db.flush()
    return new_row


def invalidate_temporal_projection_cache(
    db: Session,
    *,
    profile_id: int,
    reason: str,
    scope: str = "all",
    target_projection_type: str | None = None,
    target_projection_key: str | None = None,
    key_prefix: str | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    from_state_version: int | None = None,
    to_state_version: int | None = None,
    source_event_id: int | None = None,
    source_revision_id: int | None = None,
    triggered_by_user_id: int | None = None,
    idempotency_key: str | None = None,
    details_json: dict[str, Any] | list[Any] | None = None,
    cascade_depth: int = 0,
    tenant_id: str = "default",
) -> tuple[LifeMapCacheInvalidationLedger, int]:
    """Execute scoped cache invalidation and append an immutable ledger entry.

    Supports scopes:
    - 'all': invalidates all active caches for the profile
    - 'projection_type': invalidates caches matching target_projection_type
    - 'key_prefix': invalidates caches whose key starts with key_prefix
    - 'single_projection': invalidates specific target_projection_type + key
    - 'temporal_window': invalidates caches whose temporal window overlaps [window_start, window_end]
    """
    if profile_id <= 0:
        raise LifeMapCacheValidationError(f"Invalid profile_id: {profile_id}")
    if not reason or not reason.strip():
        raise LifeMapCacheValidationError("invalidation reason cannot be empty")

    valid_scopes = {
        "all",
        "projection_type",
        "key_prefix",
        "single_projection",
        "temporal_window",
    }
    if scope not in valid_scopes:
        raise LifeMapCacheValidationError(
            f"Invalid invalidation scope: {scope}. Must be one of {valid_scopes}"
        )

    # Check idempotency
    if idempotency_key and idempotency_key.strip():
        existing_ledger = db.execute(
            select(LifeMapCacheInvalidationLedger).where(
                LifeMapCacheInvalidationLedger.profile_id == profile_id,
                LifeMapCacheInvalidationLedger.idempotency_key == idempotency_key.strip(),
            )
        ).scalars().first()
        if existing_ledger is not None:
            return existing_ledger, 0

    now = datetime.now(UTC)

    # Build query for matching active caches
    query = select(LifeMapTemporalProjectionCache).where(
        LifeMapTemporalProjectionCache.profile_id == profile_id,
        LifeMapTemporalProjectionCache.is_valid.is_(True),
    )

    if scope == "projection_type":
        if not target_projection_type:
            raise LifeMapCacheValidationError(
                "target_projection_type required for scope 'projection_type'"
            )
        query = query.where(
            LifeMapTemporalProjectionCache.projection_type == target_projection_type.strip()
        )
    elif scope == "single_projection":
        if not target_projection_type or not target_projection_key:
            raise LifeMapCacheValidationError(
                "target_projection_type and target_projection_key required for 'single_projection'"
            )
        query = query.where(
            LifeMapTemporalProjectionCache.projection_type == target_projection_type.strip(),
            LifeMapTemporalProjectionCache.projection_key == target_projection_key.strip(),
        )
    elif scope == "key_prefix":
        if not key_prefix:
            raise LifeMapCacheValidationError("key_prefix required for scope 'key_prefix'")
        query = query.where(
            LifeMapTemporalProjectionCache.projection_key.startswith(key_prefix.strip())
        )
    elif scope == "temporal_window":
        filters = []
        if window_start is not None:
            filters.append(
                or_(
                    LifeMapTemporalProjectionCache.window_end.is_(None),
                    LifeMapTemporalProjectionCache.window_end >= window_start,
                )
            )
        if window_end is not None:
            filters.append(
                or_(
                    LifeMapTemporalProjectionCache.window_start.is_(None),
                    LifeMapTemporalProjectionCache.window_start <= window_end,
                )
            )
        if filters:
            query = query.where(*filters)

    matching_rows = list(db.execute(query).scalars())

    ledger_row = LifeMapCacheInvalidationLedger(
        profile_id=profile_id,
        tenant_id=tenant_id,
        invalidation_reason=reason.strip(),
        invalidation_scope=scope,
        target_projection_type=target_projection_type.strip() if target_projection_type else None,
        target_projection_key=target_projection_key.strip() if target_projection_key else None,
        window_start=window_start,
        window_end=window_end,
        from_state_version=from_state_version,
        to_state_version=to_state_version,
        source_event_id=source_event_id,
        source_revision_id=source_revision_id,
        triggered_by_user_id=triggered_by_user_id,
        idempotency_key=idempotency_key.strip() if idempotency_key else None,
        affected_cache_count=len(matching_rows),
        cascade_depth=cascade_depth,
        details_json=details_json,
        occurred_at=now,
    )
    db.add(ledger_row)
    db.flush()

    for row in matching_rows:
        row.is_valid = False
        row.status = "invalidated"
        row.invalidated_at = now
        row.invalidation_reason = reason.strip()
        row.invalidation_ledger_id = ledger_row.id

    db.flush()
    return ledger_row, len(matching_rows)


def prune_expired_projections(
    db: Session,
    *,
    before: datetime | None = None,
) -> int:
    """Identify and mark expired projection caches as expired.

    Returns the count of transitioned cache entries.
    """
    cutoff = _ensure_utc(before) or datetime.now(UTC)
    active_rows = list(
        db.execute(
            select(LifeMapTemporalProjectionCache).where(
                LifeMapTemporalProjectionCache.expires_at.is_not(None),
                LifeMapTemporalProjectionCache.is_valid.is_(True),
            )
        ).scalars()
    )
    count = 0
    for row in active_rows:
        exp = _ensure_utc(row.expires_at)
        if exp is not None and exp <= cutoff:
            row.is_valid = False
            row.status = "expired"
            count += 1

    if count > 0:
        db.flush()
    return count
