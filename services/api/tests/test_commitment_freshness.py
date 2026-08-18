"""P9/P11 regression tests: domain-versioned freshness clocks and expiry bounds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import PhrProfile, User
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.freshness import (
    FRESHNESS_CLOCK_VERSION,
    FreshnessClock,
    compute_freshness,
    freshness_for_commitment,
)
from clara_api.glhs.gateway import compile_thss
from clara_api.glhs.risk import DOMAIN_POLICIES
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="freshness@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        session.add(PhrProfile(user_id=owner.id))
        session.commit()
        yield session


def _scope(db: Session, *, valid_until: datetime | None = None) -> ProfileScope:
    return ProfileScope(
        actor=db.query(User).one(),
        profile=db.query(PhrProfile).one(),
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
        valid_until=valid_until,
    )


def test_freshness_clock_version_is_domain_versioned() -> None:
    assert FRESHNESS_CLOCK_VERSION == "glhs.freshness.v1"


def test_observed_at_clock_precedes_valid_from() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {
            "valid_from": cutoff - timedelta(days=500),
            "observed_at": cutoff - timedelta(days=1),
        },
        policy=DOMAIN_POLICIES["medications"],
        cutoff=cutoff,
    )
    assert result.fresh is True
    assert result.freshness_clock == FreshnessClock.SOURCE_OBSERVATION_TIME.value
    assert result.clock_value == cutoff - timedelta(days=1)
    assert result.max_age == timedelta(days=90)
    assert result.stale_reason is None


def test_old_valid_from_alone_is_not_stale_when_observed_at_fresh() -> None:
    """The exact P9 invariant: a stale valid_from is overruled by a fresh clock."""
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {
            "valid_from": cutoff - timedelta(days=400),
            "observed_at": cutoff - timedelta(days=5),
        },
        policy=DOMAIN_POLICIES["observations"],
        cutoff=cutoff,
    )
    assert result.fresh is True
    assert result.freshness_clock == FreshnessClock.SOURCE_OBSERVATION_TIME.value


def test_stale_by_valid_from_only_uses_clinical_valid_time_clock() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {"valid_from": cutoff - timedelta(days=120)},
        policy=DOMAIN_POLICIES["medications"],
        cutoff=cutoff,
    )
    assert result.fresh is False
    assert result.freshness_clock == FreshnessClock.CLINICAL_VALID_TIME.value
    assert result.clock_value == cutoff - timedelta(days=120)
    assert result.max_age == timedelta(days=90)
    assert "max_age=90d" in (result.stale_reason or "")
    assert "clock=clinical_valid_time" in (result.stale_reason or "")


def test_knowledge_time_precedes_valid_from() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {
            "valid_from": cutoff - timedelta(days=300),
            "known_at": cutoff - timedelta(days=10),
        },
        policy=DOMAIN_POLICIES["allergies"],
        cutoff=cutoff,
    )
    assert result.fresh is True
    assert result.freshness_clock == FreshnessClock.KNOWLEDGE_TIME.value
    assert result.clock_value == cutoff - timedelta(days=10)


def test_verification_at_clock_is_third_tier() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {
            "valid_from": cutoff - timedelta(days=300),
            "verification_at": cutoff - timedelta(days=3),
        },
        policy=DOMAIN_POLICIES["conditions"],
        cutoff=cutoff,
    )
    assert result.fresh is True
    assert result.freshness_clock == FreshnessClock.LAST_VERIFICATION_TIME.value
    assert result.clock_value == cutoff - timedelta(days=3)


def test_stale_knowledge_time_not_overruled_by_fresher_verification_at() -> None:
    """Precedence is fixed: a knowledge clock outranks a verification clock."""
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {
            "valid_from": cutoff - timedelta(days=500),
            "known_at": cutoff - timedelta(days=400),
            "verification_at": cutoff - timedelta(days=1),
        },
        policy=DOMAIN_POLICIES["allergies"],
        cutoff=cutoff,
    )
    assert result.fresh is False
    assert result.freshness_clock == FreshnessClock.KNOWLEDGE_TIME.value
    assert result.clock_value == cutoff - timedelta(days=400)


@pytest.mark.parametrize(
    ("domain", "days", "expected_fresh"),
    [
        ("medications", 89, True),
        ("medications", 91, False),
        ("allergies", 364, True),
        ("allergies", 366, False),
        ("conditions", 179, True),
        ("conditions", 181, False),
        ("observations", 29, True),
        ("observations", 31, False),
    ],
)
def test_domain_max_ages_from_risk_policy(domain: str, days: int, expected_fresh: bool) -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {"observed_at": cutoff - timedelta(days=days)},
        policy=DOMAIN_POLICIES[domain],
        cutoff=cutoff,
    )
    assert result.fresh is expected_fresh
    assert result.max_age == DOMAIN_POLICIES[domain].max_age


def test_missing_all_clocks_rejects() -> None:
    with pytest.raises(GlhsInvariantError, match="evidence_freshness_time_unavailable"):
        compute_freshness(
            {},
            policy=DOMAIN_POLICIES["medications"],
            cutoff=datetime(2026, 8, 1, tzinfo=UTC),
        )


def test_freshness_for_commitment_uses_anchor_known_time_over_anchor_valid_time() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = freshness_for_commitment(
        {
            "commitment_id": "c-1",
            "domain": "observations",
            "anchor_valid_time": (cutoff - timedelta(days=200)).isoformat(),
            "anchor_known_time": (cutoff - timedelta(days=5)).isoformat(),
            "evidence_ids": ["e-1"],
        },
        cutoff=cutoff,
    )
    assert result.fresh is True
    assert result.freshness_clock == FreshnessClock.KNOWLEDGE_TIME.value
    assert result.clock_value == cutoff - timedelta(days=5)


def test_freshness_for_commitment_stale_when_all_clocks_old() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = freshness_for_commitment(
        {
            "commitment_id": "c-2",
            "domain": "observations",
            "anchor_valid_time": (cutoff - timedelta(days=200)).isoformat(),
            "anchor_known_time": (cutoff - timedelta(days=200)).isoformat(),
        },
        cutoff=cutoff,
    )
    assert result.fresh is False
    assert result.freshness_clock == FreshnessClock.KNOWLEDGE_TIME.value
    assert result.stale_reason is not None


def test_freshness_for_commitment_rejects_unknown_domain() -> None:
    with pytest.raises(GlhsInvariantError, match="commitment_freshness_domain_unknown"):
        freshness_for_commitment(
            {"commitment_id": "c-3", "domain": "unknown", "anchor_known_time": "2026-08-01"},
            cutoff=datetime(2026, 8, 1, tzinfo=UTC),
        )


def test_commitment_snapshot_expiry_bounded_by_scope_valid_until(db: Session) -> None:
    scope = _scope(
        db, valid_until=datetime.now(UTC) + timedelta(seconds=60)
    )
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="expiry_bound",
        purpose=scope.purpose,
        valid_at=datetime(2026, 8, 1, tzinfo=UTC),
        known_at=datetime.now(UTC),
        allowed_domains=frozenset({"observations"}),
        expires_in=timedelta(minutes=5),
    )
    assert snapshot.expires_at == scope.valid_until
    assert snapshot.expires_at < datetime.now(UTC) + timedelta(minutes=5)


def test_generic_snapshot_expiry_bounded_by_scope_valid_until(db: Session) -> None:
    scope = _scope(
        db, valid_until=datetime.now(UTC) + timedelta(seconds=60)
    )
    snapshot = compile_thss(
        db,
        scope=scope,
        task="expiry_bound",
        purpose=scope.purpose,
        allowed_data_classes=frozenset({"observations"}),
        expires_in=timedelta(minutes=5),
    )
    assert snapshot.expires_at == scope.valid_until


def test_commitment_snapshot_scope_expired_rejects(db: Session) -> None:
    scope = _scope(
        db, valid_until=datetime.now(UTC) - timedelta(seconds=1)
    )
    with pytest.raises(GlhsInvariantError, match="commitment_snapshot_scope_expired"):
        compile_commitment_thss(
            db,
            scope=scope,
            task="expired_scope",
            purpose=scope.purpose,
            valid_at=datetime(2026, 8, 1, tzinfo=UTC),
            known_at=datetime.now(UTC),
            allowed_domains=frozenset({"observations"}),
        )


def test_generic_snapshot_scope_expired_rejects(db: Session) -> None:
    scope = _scope(
        db, valid_until=datetime.now(UTC) - timedelta(seconds=1)
    )
    with pytest.raises(GlhsInvariantError, match="snapshot_scope_expired"):
        compile_thss(
            db,
            scope=scope,
            task="expired_scope",
            purpose=scope.purpose,
            allowed_data_classes=frozenset({"observations"}),
        )


def test_freshness_result_is_pure_dict_mapping() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    result = compute_freshness(
        {"observed_at": cutoff - timedelta(days=1)},
        policy=DOMAIN_POLICIES["medications"],
        cutoff=cutoff,
    )
    payload = result.to_dict()
    assert payload["fresh"] is True
    assert payload["freshness_clock"] == FreshnessClock.SOURCE_OBSERVATION_TIME.value
    assert payload["max_age_seconds"] == 90 * 86400
    assert payload["stale_reason"] is None
