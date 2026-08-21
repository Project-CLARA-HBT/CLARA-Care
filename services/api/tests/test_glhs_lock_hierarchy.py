"""Unit and regression tests for GLHS Lock Hierarchy & Phantom Prevention."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.compliance import consent as compliance_consent
from clara_api.core.consent import PhrConsentService
from clara_api.db.base import Base
from clara_api.db.models import (
    PhrProfile,
    User,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import read_current_policy_epoch
from clara_api.glhs.lock_hierarchy import (
    acquire_canonical_glhs_locks,
    acquire_consent_lock_anchor,
    acquire_policy_lock_anchor,
    create_governance_policy_epoch,
    is_postgres,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_user_and_profile(db: Session) -> tuple[User, PhrProfile]:
    user = User(email="lock_tester@example.com", hashed_password="pw", role="normal")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Lock Tester")
    db.add(profile)
    db.flush()
    return user, profile


def test_is_postgres_detection(db: Session) -> None:
    assert is_postgres(db) is False


def test_acquire_policy_lock_anchor_runs_safely_on_sqlite(db: Session) -> None:
    acquire_policy_lock_anchor(db, policy_domain="medications")
    acquire_policy_lock_anchor(db)


def test_acquire_consent_lock_anchor_locks_subject(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    acquire_consent_lock_anchor(db, user_id=user.id)
    acquire_consent_lock_anchor(db, profile_id=profile.id)


def test_create_governance_policy_epoch_acquires_lock(db: Session) -> None:
    epoch = create_governance_policy_epoch(
        db,
        policy_domain="medications",
        version="policy-v2",
        active_from=datetime.now(UTC),
        canonical_digest="d" * 64,
    )
    db.commit()
    assert epoch.id is not None
    read_epoch = read_current_policy_epoch(db, policy_domain="medications", for_update=True)
    assert read_epoch is not None
    assert read_epoch.version == "policy-v2"


def test_core_consent_grant_and_revoke_participate_in_lock_anchor(db: Session) -> None:
    user, _ = _create_user_and_profile(db)
    grant_row = PhrConsentService.grant(db, user_id=user.id, purpose="personalization", version="v1")
    assert grant_row.id is not None
    assert PhrConsentService.is_granted(db, user_id=user.id, purpose="personalization") is True

    revoke_row = PhrConsentService.revoke(db, user_id=user.id, purpose="personalization")
    assert revoke_row.id is not None
    assert PhrConsentService.is_granted(db, user_id=user.id, purpose="personalization") is False


def test_compliance_consent_grant_and_withdraw_participate_in_lock_anchor(db: Session) -> None:
    user, _ = _create_user_and_profile(db)
    grant_row = compliance_consent.grant(db, user_id=user.id, purpose="research", version="v1")
    assert grant_row.id is not None
    assert compliance_consent.has_consent(db, user_id=user.id, purpose="research") is True

    withdraw_row = compliance_consent.withdraw(db, user_id=user.id, purpose="research")
    assert withdraw_row.id is not None
    assert compliance_consent.has_consent(db, user_id=user.id, purpose="research") is False


def test_acquire_canonical_glhs_locks_strict_total_order(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    PhrConsentService.grant(db, user_id=user.id, purpose="personalization", version="2026-v1")
    db.commit()

    locks = acquire_canonical_glhs_locks(
        db,
        profile_id=profile.id,
        policy_domain="medications",
        partitions=[("medications", "rx-001"), ("conditions", "diag-002")],
        purpose="personalization",
    )
    assert locks.base_state_version == 0
    assert locks.owner_user_id == user.id
    assert locks.effective_policy_version == "glhs.v1"
    assert locks.effective_consent_version == "phr_personalization:2026-v1"
    assert len(locks.locked_partitions) == 2
    # Verify sorted lexicographically (domain, semantic_key)
    assert (locks.locked_partitions[0].domain, locks.locked_partitions[0].semantic_key) == ("conditions", "diag-002")
    assert (locks.locked_partitions[1].domain, locks.locked_partitions[1].semantic_key) == ("medications", "rx-001")


def test_acquire_canonical_glhs_locks_profile_not_found(db: Session) -> None:
    with pytest.raises(GlhsInvariantError, match="profile_not_found"):
        acquire_canonical_glhs_locks(db, profile_id=99999)
