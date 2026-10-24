"""Tests for LifeMap temporal projection caching, state versioning, and invalidation ledger.

Covers:
- Allow: state version advancement, caching, retrieval, cache hit tracking
- Deny: validation errors for negative IDs, empty keys, invalid scopes
- Duplicate & Concurrency: idempotent cache replacement, idempotency key on ledger
- Invalidation scopes: 'all', 'projection_type', 'single_projection', 'key_prefix', 'temporal_window'
- TTL & Stale: expiration detection and pruning
- Isolation: multi-profile and multi-tenant partitioning
- Hash verification: canonical SHA-256 payload digests
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clara_api.db.base import Base
from clara_api.db.lifemap_temporal_cache import (
    LifeMapCacheValidationError,
    advance_lifemap_state_version,
    compute_payload_hash,
    get_cached_temporal_projection,
    get_current_state_version,
    invalidate_temporal_projection_cache,
    prune_expired_projections,
    set_cached_temporal_projection,
)
from clara_api.db.lifemap_temporal_models import (
    LifeMapCacheInvalidationLedger,
    LifeMapStateVersion,
    LifeMapTemporalProjectionCache,
)
from clara_api.db.models import PhrProfile, User


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a fresh SQLite in-memory database with all models created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Seed test users and profiles
    user1 = User(
        email="patient1@clara.local",
        hashed_password="pw_hash_test_123",
        role="normal",
        full_name="Nguyen Van A",
    )
    user2 = User(
        email="patient2@clara.local",
        hashed_password="pw_hash_test_456",
        role="normal",
        full_name="Tran Thi B",
    )
    session.add_all([user1, user2])
    session.flush()

    profile1 = PhrProfile(
        id=1,
        user_id=user1.id,
        public_id="prof_11111111-1111-1111-1111-111111111111",
        full_name="Nguyen Van A",
        status="active",
    )
    profile2 = PhrProfile(
        id=2,
        user_id=user2.id,
        public_id="prof_22222222-2222-2222-2222-222222222222",
        full_name="Tran Thi B",
        status="active",
    )
    session.add_all([profile1, profile2])
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_advance_state_version_monotonic(db_session: Session) -> None:
    """Test monotonic advancement of longitudinal state versions for a profile."""
    assert get_current_state_version(db_session, profile_id=1) == 0

    v1 = advance_lifemap_state_version(
        db_session,
        profile_id=1,
        change_type="event_created",
        active_event_count=1,
    )
    db_session.commit()

    assert isinstance(v1, LifeMapStateVersion)
    assert v1.state_version == 1
    assert v1.change_type == "event_created"
    assert v1.active_event_count == 1
    assert v1.state_digest is not None
    assert get_current_state_version(db_session, profile_id=1) == 1

    v2 = advance_lifemap_state_version(
        db_session,
        profile_id=1,
        change_type="event_revised",
        active_event_count=2,
    )
    db_session.commit()

    assert v2.state_version == 2
    assert v2.change_type == "event_revised"
    assert get_current_state_version(db_session, profile_id=1) == 2

    # Verify profile 2 is still uninitialized
    assert get_current_state_version(db_session, profile_id=2) == 0


def test_advance_state_version_validation(db_session: Session) -> None:
    """Test rejection of malformed state version advancement arguments."""
    with pytest.raises(LifeMapCacheValidationError):
        advance_lifemap_state_version(db_session, profile_id=0, change_type="event_created")

    with pytest.raises(LifeMapCacheValidationError):
        advance_lifemap_state_version(db_session, profile_id=1, change_type="")


def test_set_and_get_cached_projection(db_session: Session) -> None:
    """Test standard projection caching, retrieval, and hit-count tracking."""
    payload = {
        "items": [
            {"id": "ev_1", "kind": "medication", "title": "Paracetamol 500mg"},
            {"id": "ev_2", "kind": "symptom", "title": "Sốt nhẹ"},
        ],
        "summary": "2 clinical events in 30d window",
    }
    window_start = datetime(2026, 9, 1, tzinfo=UTC)
    window_end = datetime(2026, 10, 1, tzinfo=UTC)

    entry = set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:window=30d:kinds=all",
        payload=payload,
        state_version=1,
        window_start=window_start,
        window_end=window_end,
    )
    db_session.commit()

    assert entry.id is not None
    assert entry.is_valid is True
    assert entry.status == "active"
    assert entry.cache_hit_count == 0
    assert entry.item_count == 2
    assert entry.payload_hash == compute_payload_hash(payload)

    # First retrieval: should hit cache and increment hit count
    hit1 = get_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:window=30d:kinds=all",
    )
    db_session.commit()

    assert hit1 is not None
    assert hit1.id == entry.id
    assert hit1.cache_hit_count == 1
    assert hit1.payload_json == payload

    # Second retrieval
    hit2 = get_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:window=30d:kinds=all",
    )
    db_session.commit()

    assert hit2 is not None
    assert hit2.cache_hit_count == 2


def test_cached_projection_validation(db_session: Session) -> None:
    """Test validation errors for invalid caching and lookup arguments."""
    with pytest.raises(LifeMapCacheValidationError):
        set_cached_temporal_projection(
            db_session,
            profile_id=-1,
            projection_type="timeline",
            projection_key="key1",
            payload={"test": 1},
            state_version=1,
        )

    with pytest.raises(LifeMapCacheValidationError):
        set_cached_temporal_projection(
            db_session,
            profile_id=1,
            projection_type="",
            projection_key="key1",
            payload={"test": 1},
            state_version=1,
        )

    with pytest.raises(LifeMapCacheValidationError):
        get_cached_temporal_projection(
            db_session,
            profile_id=1,
            projection_type="timeline",
            projection_key="",
        )


def test_idempotent_cache_replacement(db_session: Session) -> None:
    """Test re-setting a projection with updated payload updates in-place."""
    payload_v1 = {"version": 1, "data": "initial"}
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="summary",
        projection_key="summary:monthly:2026-10",
        payload=payload_v1,
        state_version=1,
    )
    db_session.commit()

    payload_v2 = {"version": 2, "data": "updated"}
    updated = set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="summary",
        projection_key="summary:monthly:2026-10",
        payload=payload_v2,
        state_version=1,
    )
    db_session.commit()

    assert updated.payload_json == payload_v2
    assert updated.payload_hash == compute_payload_hash(payload_v2)

    # Ensure only 1 row exists
    total = (
        db_session.query(LifeMapTemporalProjectionCache)
        .filter_by(profile_id=1, projection_type="summary")
        .count()
    )
    assert total == 1


def test_ttl_expiration_handling(db_session: Session) -> None:
    """Test that expired cache entries are marked expired and not returned."""
    payload = {"data": "ephemeral"}
    # Cache with negative TTL so it is already expired
    now = datetime.now(UTC)
    entry = set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="trend",
        projection_key="trend:glucose:7d",
        payload=payload,
        state_version=1,
        ttl_seconds=1,
    )
    # Manually backdate expires_at
    entry.expires_at = now - timedelta(seconds=10)
    db_session.commit()

    # Retrieval should detect expiration and return None
    result = get_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="trend",
        projection_key="trend:glucose:7d",
    )
    db_session.commit()

    assert result is None
    # Verify DB status transitioned to expired
    db_session.refresh(entry)
    assert entry.is_valid is False
    assert entry.status == "expired"


def test_invalidation_scope_all(db_session: Session) -> None:
    """Test invalidation with scope 'all' marks all active caches invalid."""
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:1",
        payload={"a": 1},
        state_version=1,
    )
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="summary",
        projection_key="summary:1",
        payload={"b": 2},
        state_version=1,
    )
    db_session.commit()

    ledger, count = invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="event_revised",
        scope="all",
        from_state_version=1,
        to_state_version=2,
    )
    db_session.commit()

    assert count == 2
    assert isinstance(ledger, LifeMapCacheInvalidationLedger)
    assert ledger.affected_cache_count == 2
    assert ledger.invalidation_reason == "event_revised"
    assert ledger.invalidation_scope == "all"

    # All caches for profile 1 should be invalidated
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="timeline", projection_key="timeline:1"
        )
        is None
    )
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="summary", projection_key="summary:1"
        )
        is None
    )


def test_invalidation_scope_projection_type(db_session: Session) -> None:
    """Test invalidation targeting only a specific projection_type."""
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:1",
        payload={"a": 1},
        state_version=1,
    )
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="summary",
        projection_key="summary:1",
        payload={"b": 2},
        state_version=1,
    )
    db_session.commit()

    ledger, count = invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="summary_rule_upgraded",
        scope="projection_type",
        target_projection_type="summary",
    )
    db_session.commit()

    assert count == 1
    assert ledger.affected_cache_count == 1

    # summary is invalidated, timeline remains active
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="summary", projection_key="summary:1"
        )
        is None
    )
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="timeline", projection_key="timeline:1"
        )
        is not None
    )


def test_invalidation_scope_key_prefix(db_session: Session) -> None:
    """Test invalidation targeting caches matching a key prefix."""
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:window=30d:all",
        payload={"a": 1},
        state_version=1,
    )
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="timeline:window=90d:all",
        payload={"b": 2},
        state_version=1,
    )
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="trend",
        projection_key="trend:bp",
        payload={"c": 3},
        state_version=1,
    )
    db_session.commit()

    ledger, count = invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="timeline_recalc",
        scope="key_prefix",
        key_prefix="timeline:window=30d",
    )
    db_session.commit()

    assert count == 1
    assert ledger.affected_cache_count == 1

    assert (
        get_cached_temporal_projection(
            db_session,
            profile_id=1,
            projection_type="timeline",
            projection_key="timeline:window=30d:all",
        )
        is None
    )
    assert (
        get_cached_temporal_projection(
            db_session,
            profile_id=1,
            projection_type="timeline",
            projection_key="timeline:window=90d:all",
        )
        is not None
    )


def test_invalidation_scope_temporal_window(db_session: Session) -> None:
    """Test invalidating caches whose temporal interval intersects an invalidation window."""
    # Cache 1: 2026-08-01 to 2026-08-31 (outside invalidation window)
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="august",
        payload={"month": 8},
        state_version=1,
        window_start=datetime(2026, 8, 1, tzinfo=UTC),
        window_end=datetime(2026, 8, 31, tzinfo=UTC),
    )
    # Cache 2: 2026-09-01 to 2026-09-30 (inside invalidation window)
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="september",
        payload={"month": 9},
        state_version=1,
        window_start=datetime(2026, 9, 1, tzinfo=UTC),
        window_end=datetime(2026, 9, 30, tzinfo=UTC),
    )
    db_session.commit()

    # Invalidate window covering September
    ledger, count = invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="september_event_revoked",
        scope="temporal_window",
        window_start=datetime(2026, 9, 15, tzinfo=UTC),
        window_end=datetime(2026, 9, 20, tzinfo=UTC),
    )
    db_session.commit()

    assert count == 1
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="timeline", projection_key="september"
        )
        is None
    )
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="timeline", projection_key="august"
        )
        is not None
    )


def test_invalidation_idempotency(db_session: Session) -> None:
    """Test that repeating an invalidation with identical idempotency_key is a safe no-op."""
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="summary",
        projection_key="key1",
        payload={"data": 1},
        state_version=1,
    )
    db_session.commit()

    key = "idem_req_12345"
    ledger1, count1 = invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="user_request",
        scope="all",
        idempotency_key=key,
    )
    db_session.commit()
    assert count1 == 1

    # Second call with same idempotency key
    ledger2, count2 = invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="user_request",
        scope="all",
        idempotency_key=key,
    )
    assert count2 == 0
    assert ledger1.id == ledger2.id


def test_profile_and_tenant_isolation(db_session: Session) -> None:
    """Test that caches for profile 1 and profile 2 remain strictly isolated."""
    set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="common_key",
        payload={"profile": 1},
        state_version=1,
        tenant_id="tenant_a",
    )
    set_cached_temporal_projection(
        db_session,
        profile_id=2,
        projection_type="timeline",
        projection_key="common_key",
        payload={"profile": 2},
        state_version=1,
        tenant_id="tenant_b",
    )
    db_session.commit()

    # Invalidate profile 1
    invalidate_temporal_projection_cache(
        db_session,
        profile_id=1,
        reason="profile_1_purge",
        scope="all",
    )
    db_session.commit()

    # Profile 1 is invalidated
    assert (
        get_cached_temporal_projection(
            db_session, profile_id=1, projection_type="timeline", projection_key="common_key"
        )
        is None
    )
    # Profile 2 remains active and unaffected
    p2 = get_cached_temporal_projection(
        db_session, profile_id=2, projection_type="timeline", projection_key="common_key"
    )
    assert p2 is not None
    assert p2.payload_json == {"profile": 2}
    assert p2.tenant_id == "tenant_b"


def test_prune_expired_projections(db_session: Session) -> None:
    """Test background sweep of expired projections."""
    now = datetime.now(UTC)
    e1 = set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="exp_1",
        payload={"val": 1},
        state_version=1,
        ttl_seconds=1,
    )
    e1.expires_at = now - timedelta(seconds=60)

    e2 = set_cached_temporal_projection(
        db_session,
        profile_id=1,
        projection_type="timeline",
        projection_key="live_1",
        payload={"val": 2},
        state_version=1,
        ttl_seconds=3600,
    )
    db_session.commit()

    pruned = prune_expired_projections(db_session, before=now)
    db_session.commit()

    assert pruned == 1
    db_session.refresh(e1)
    db_session.refresh(e2)
    assert e1.is_valid is False
    assert e1.status == "expired"
    assert e2.is_valid is True
    assert e2.status == "active"
