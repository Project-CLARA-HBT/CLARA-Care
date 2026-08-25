"""Unit and regression tests for GLHS Lock Hierarchy & Phantom Prevention."""

from __future__ import annotations

import random
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock

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
    LockClass,
    LockDependency,
    LockMode,
    acquire_advisory_xact_lock,
    acquire_advisory_xact_lock_shared,
    acquire_canonical_glhs_locks,
    acquire_consent_lock_anchor,
    acquire_governance_anchor,
    acquire_policy_lock_anchor,
    acquire_profile_and_consent_anchor,
    build_lock_plan,
    create_governance_policy_epoch,
    get_or_create_entity_partition,
    increment_partition_versions,
    is_postgres,
    key_to_advisory_lock_pair,
    resolve_lock_class,
    resolve_lock_mode,
)


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_user_and_profile(db: Session) -> tuple[User, PhrProfile]:
    user = User(email=f"lock_tester_{random.randint(1000, 9999)}@example.com", hashed_password="pw", role="normal")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Lock Tester")
    db.add(profile)
    db.flush()
    return user, profile


# ==============================================================================
# 1. Pure Function: build_lock_plan
# ==============================================================================


def test_resolve_lock_class_all_seven_classes() -> None:
    # Class 1: Tenant/Global Policy
    assert resolve_lock_class("tenant_policy") == LockClass.TENANT_GLOBAL_POLICY
    assert resolve_lock_class("global_policy") == LockClass.TENANT_GLOBAL_POLICY
    assert resolve_lock_class("global") == LockClass.TENANT_GLOBAL_POLICY
    assert resolve_lock_class(1) == LockClass.TENANT_GLOBAL_POLICY

    # Class 2: Domain Policy
    assert resolve_lock_class("domain_policy") == LockClass.DOMAIN_POLICY
    assert resolve_lock_class("policy_domain") == LockClass.DOMAIN_POLICY
    assert resolve_lock_class("domain") == LockClass.DOMAIN_POLICY
    assert resolve_lock_class(2) == LockClass.DOMAIN_POLICY

    # Class 3: Subject Consent/Profile
    assert resolve_lock_class("subject_consent") == LockClass.SUBJECT_CONSENT_PROFILE
    assert resolve_lock_class("subject_profile") == LockClass.SUBJECT_CONSENT_PROFILE
    assert resolve_lock_class("consent") == LockClass.SUBJECT_CONSENT_PROFILE
    assert resolve_lock_class("profile") == LockClass.SUBJECT_CONSENT_PROFILE
    assert resolve_lock_class(3) == LockClass.SUBJECT_CONSENT_PROFILE

    # Class 4: Evidence/Source
    assert resolve_lock_class("evidence") == LockClass.EVIDENCE_SOURCE
    assert resolve_lock_class("source") == LockClass.EVIDENCE_SOURCE
    assert resolve_lock_class("evidence_source") == LockClass.EVIDENCE_SOURCE
    assert resolve_lock_class(4) == LockClass.EVIDENCE_SOURCE

    # Class 5: Entity Partitions
    assert resolve_lock_class("entity_partition") == LockClass.ENTITY_PARTITIONS
    assert resolve_lock_class("entity") == LockClass.ENTITY_PARTITIONS
    assert resolve_lock_class("partition") == LockClass.ENTITY_PARTITIONS
    assert resolve_lock_class(5) == LockClass.ENTITY_PARTITIONS

    # Class 6: Lease/Reservation
    assert resolve_lock_class("lease") == LockClass.LEASE_RESERVATION
    assert resolve_lock_class("reservation") == LockClass.LEASE_RESERVATION
    assert resolve_lock_class(6) == LockClass.LEASE_RESERVATION

    # Class 7: Idempotency Key
    assert resolve_lock_class("idempotency_key") == LockClass.IDEMPOTENCY_KEY
    assert resolve_lock_class("idempotency") == LockClass.IDEMPOTENCY_KEY
    assert resolve_lock_class(7) == LockClass.IDEMPOTENCY_KEY


def test_resolve_lock_mode() -> None:
    assert resolve_lock_mode("SHARED") == LockMode.SHARED
    assert resolve_lock_mode("READ") == LockMode.SHARED
    assert resolve_lock_mode("shared") == LockMode.SHARED
    assert resolve_lock_mode(False) == LockMode.SHARED

    assert resolve_lock_mode("EXCLUSIVE") == LockMode.EXCLUSIVE
    assert resolve_lock_mode("WRITE") == LockMode.EXCLUSIVE
    assert resolve_lock_mode("exclusive") == LockMode.EXCLUSIVE
    assert resolve_lock_mode(True) == LockMode.EXCLUSIVE

    with pytest.raises(GlhsInvariantError, match="invalid_lock_mode"):
        resolve_lock_mode("INVALID_MODE")


def test_build_lock_plan_total_order_classes_1_to_7() -> None:
    """Verify strict total order across classes 1 to 7 regardless of input ordering."""
    reversed_dependencies = [
        LockDependency(kind="idempotency_key", key="idem-999", mode="EXCLUSIVE"),
        LockDependency(kind="lease", key="lease-res-1", mode="SHARED"),
        LockDependency(kind="entity_partition", key="medications:rx-warfarin", mode="EXCLUSIVE"),
        LockDependency(kind="evidence", key="ev-doc-001", mode="SHARED"),
        LockDependency(kind="subject_consent", key="user:42", mode="SHARED"),
        LockDependency(kind="domain_policy", key="medications", mode="SHARED"),
        LockDependency(kind="tenant_policy", key="tenant-global", mode="SHARED"),
    ]

    plan = build_lock_plan(reversed_dependencies)
    assert len(plan) == 7

    assert plan[0].lock_class == LockClass.TENANT_GLOBAL_POLICY
    assert plan[0].key == "tenant-global"
    assert plan[0].mode == LockMode.SHARED

    assert plan[1].lock_class == LockClass.DOMAIN_POLICY
    assert plan[1].key == "medications"

    assert plan[2].lock_class == LockClass.SUBJECT_CONSENT_PROFILE
    assert plan[2].key == "user:42"

    assert plan[3].lock_class == LockClass.EVIDENCE_SOURCE
    assert plan[3].key == "ev-doc-001"

    assert plan[4].lock_class == LockClass.ENTITY_PARTITIONS
    assert plan[4].key == "medications:rx-warfarin"
    assert plan[4].mode == LockMode.EXCLUSIVE

    assert plan[5].lock_class == LockClass.LEASE_RESERVATION
    assert plan[5].key == "lease-res-1"

    assert plan[6].lock_class == LockClass.IDEMPOTENCY_KEY
    assert plan[6].key == "idem-999"
    assert plan[6].mode == LockMode.EXCLUSIVE


def test_build_lock_plan_lexicographical_order_within_class() -> None:
    """Keys within the same class are sorted in strict lexicographical (raw UTF-8 byte) order."""
    dependencies = [
        {"kind": "entity_partition", "key": "observations:vital-hr"},
        {"kind": "entity_partition", "key": "medications:rx-warfarin"},
        {"kind": "entity_partition", "key": "allergies:allergy-penicillin"},
        {"kind": "entity_partition", "key": "conditions:diag-hypertension"},
        {"kind": "entity_partition", "key": "medications:rx-aspirin"},
    ]
    plan = build_lock_plan(dependencies)
    keys = [item.key for item in plan]
    assert keys == [
        "allergies:allergy-penicillin",
        "conditions:diag-hypertension",
        "medications:rx-aspirin",
        "medications:rx-warfarin",
        "observations:vital-hr",
    ]


def test_build_lock_plan_duplicate_collapsing_and_mode_escalation() -> None:
    """Duplicate keys within the same class collapse to one item, with EXCLUSIVE > SHARED."""
    # Test 1: SHARED + SHARED -> SHARED
    plan_shared = build_lock_plan([
        {"kind": "domain_policy", "key": "medications", "mode": "SHARED"},
        {"kind": "domain_policy", "key": "medications", "mode": "SHARED"},
    ])
    assert len(plan_shared) == 1
    assert plan_shared[0].mode == LockMode.SHARED

    # Test 2: SHARED + EXCLUSIVE -> EXCLUSIVE (Escalation)
    plan_escalate_1 = build_lock_plan([
        {"kind": "domain_policy", "key": "medications", "mode": "SHARED"},
        {"kind": "domain_policy", "key": "medications", "mode": "EXCLUSIVE"},
        {"kind": "domain_policy", "key": "medications", "mode": "SHARED"},
    ])
    assert len(plan_escalate_1) == 1
    assert plan_escalate_1[0].mode == LockMode.EXCLUSIVE

    # Test 3: EXCLUSIVE + SHARED -> EXCLUSIVE
    plan_escalate_2 = build_lock_plan([
        LockDependency(kind="entity_partition", key="medications:rx-001", mode="EXCLUSIVE"),
        LockDependency(kind="entity_partition", key="medications:rx-001", mode="SHARED"),
    ])
    assert len(plan_escalate_2) == 1
    assert plan_escalate_2[0].mode == LockMode.EXCLUSIVE


def test_build_lock_plan_order_invariance_and_determinism() -> None:
    """Randomly shuffled inputs produce the exact same lock plan every time."""
    deps = [
        {"kind": "tenant_policy", "key": "tenant-1", "mode": "SHARED"},
        {"kind": "domain_policy", "key": "medications", "mode": "SHARED"},
        {"kind": "subject_consent", "key": "user:1", "mode": "SHARED"},
        {"kind": "evidence", "key": "ev-1", "mode": "SHARED"},
        {"kind": "entity_partition", "key": "allergies:peanuts", "mode": "EXCLUSIVE"},
        {"kind": "entity_partition", "key": "medications:aspirin", "mode": "SHARED"},
        {"kind": "lease", "key": "lease-1", "mode": "SHARED"},
        {"kind": "idempotency_key", "key": "key-123", "mode": "EXCLUSIVE"},
    ]

    base_plan = build_lock_plan(deps)
    base_tuples = [(item.lock_class, item.key, item.mode) for item in base_plan]

    for seed in range(20):
        shuffled = list(deps)
        random.Random(seed).shuffle(shuffled)
        shuffled_plan = build_lock_plan(shuffled)
        shuffled_tuples = [(item.lock_class, item.key, item.mode) for item in shuffled_plan]
        assert shuffled_tuples == base_tuples


def test_build_lock_plan_various_input_formats() -> None:
    """Supports dataclasses, dicts, tuples, and custom objects."""
    class CustomDep:
        def __init__(self, kind: str, key: str, mode: str):
            self.kind = kind
            self.key = key
            self.mode = mode

    mixed_inputs = [
        LockDependency(kind="tenant_policy", key="tenant-1", mode="SHARED"),
        {"kind": "domain_policy", "key": "medications", "mode": "SHARED"},
        ("subject_consent", "user:42", "SHARED"),
        ("evidence", "ev-100"),  # Default mode=SHARED
        CustomDep("entity_partition", "rx-001", "EXCLUSIVE"),
    ]

    plan = build_lock_plan(mixed_inputs)
    assert len(plan) == 5
    assert [item.lock_class for item in plan] == [
        LockClass.TENANT_GLOBAL_POLICY,
        LockClass.DOMAIN_POLICY,
        LockClass.SUBJECT_CONSENT_PROFILE,
        LockClass.EVIDENCE_SOURCE,
        LockClass.ENTITY_PARTITIONS,
    ]
    assert plan[4].mode == LockMode.EXCLUSIVE


def test_build_lock_plan_rejection_of_unknown_dependency_kinds() -> None:
    """Raises GlhsInvariantError when an unknown kind or class is encountered."""
    with pytest.raises(GlhsInvariantError, match="unknown_dependency_kind"):
        build_lock_plan([{"kind": "unknown_random_kind", "key": "xyz"}])

    with pytest.raises(GlhsInvariantError, match="unknown_dependency_kind"):
        build_lock_plan([{"kind": 999, "key": "xyz"}])

    with pytest.raises(GlhsInvariantError, match="unknown_dependency_kind"):
        build_lock_plan([{"kind": 0, "key": "xyz"}])


def test_build_lock_plan_rejection_of_invalid_keys_or_none() -> None:
    with pytest.raises(GlhsInvariantError, match="missing_dependency"):
        build_lock_plan([None])

    with pytest.raises(GlhsInvariantError, match="missing_lock_key"):
        build_lock_plan([{"kind": "domain_policy", "key": ""}])

    with pytest.raises(GlhsInvariantError, match="missing_lock_key"):
        build_lock_plan([("domain_policy", None)])


def test_build_lock_plan_empty_or_none() -> None:
    assert len(build_lock_plan([])) == 0
    assert len(build_lock_plan(None)) == 0


# ==============================================================================
# 2. Database Advisory Anchors: acquire_governance_anchor & acquire_policy_lock_anchor
# ==============================================================================


def test_is_postgres_detection(db: Session) -> None:
    assert is_postgres(db) is False


def test_acquire_governance_anchor_sqlite_runs_safely(db: Session) -> None:
    acquire_governance_anchor(db, "policy_epoch:__global__", mode="SHARED")
    acquire_governance_anchor(db, "policy_epoch:__global__", mode="EXCLUSIVE")
    acquire_advisory_xact_lock(db, "test_exclusive")
    acquire_advisory_xact_lock_shared(db, "test_shared")


def test_key_to_advisory_lock_pair_64bit_sha256() -> None:
    """Verify 64-bit SHA-256 pair derivation produces two 32-bit signed ints without collisions."""
    k1, k2 = key_to_advisory_lock_pair("policy_epoch:__global__")
    assert isinstance(k1, int)
    assert isinstance(k2, int)
    assert -2147483648 <= k1 <= 2147483647
    assert -2147483648 <= k2 <= 2147483647

    # Determinism
    k1_b, k2_b = key_to_advisory_lock_pair("policy_epoch:__global__")
    assert (k1, k2) == (k1_b, k2_b)

    # Distinct keys produce distinct pairs
    k1_med, k2_med = key_to_advisory_lock_pair("policy_epoch:medications")
    assert (k1, k2) != (k1_med, k2_med)


def test_acquire_governance_anchor_postgres_mocked() -> None:
    mock_db = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_db.get_bind.return_value = mock_bind

    k1, k2 = key_to_advisory_lock_pair("policy_epoch:__global__")

    # SHARED mode
    acquire_governance_anchor(mock_db, "policy_epoch:__global__", mode="SHARED")
    mock_db.execute.assert_called_once()
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "pg_advisory_xact_lock_shared(:k1, :k2)" in sql_text
    assert mock_db.execute.call_args[0][1] == {"k1": k1, "k2": k2}

    # EXCLUSIVE mode
    mock_db.reset_mock()
    acquire_governance_anchor(mock_db, "policy_epoch:__global__", mode="EXCLUSIVE")
    mock_db.execute.assert_called_once()
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "pg_advisory_xact_lock(:k1, :k2)" in sql_text
    assert "pg_advisory_xact_lock_shared" not in sql_text
    assert mock_db.execute.call_args[0][1] == {"k1": k1, "k2": k2}


def test_acquire_policy_lock_anchor_canonical_sequence() -> None:
    mock_db = MagicMock(spec=Session)
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_db.get_bind.return_value = mock_bind

    # Acquire policy anchor with domain "medications" in SHARED mode
    acquire_policy_lock_anchor(mock_db, policy_domain="medications", mode="SHARED")

    # Strict canonical order: Class 1 (Global) then Class 2 (Domain)
    assert mock_db.execute.call_count == 2
    first_call_params = mock_db.execute.call_args_list[0][0][1]
    second_call_params = mock_db.execute.call_args_list[1][0][1]
    k1_global, k2_global = key_to_advisory_lock_pair("policy_epoch:__global__")
    k1_med, k2_med = key_to_advisory_lock_pair("policy_epoch:medications")
    assert first_call_params == {"k1": k1_global, "k2": k2_global}
    assert second_call_params == {"k1": k1_med, "k2": k2_med}


def test_acquire_policy_lock_anchor_runs_safely_on_sqlite(db: Session) -> None:
    acquire_policy_lock_anchor(db, policy_domain="medications")
    acquire_policy_lock_anchor(db)
    acquire_policy_lock_anchor(db, "medications", "EXCLUSIVE")


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


# ==============================================================================
# 3. Subject Profile & Consent Anchors (Shared vs Exclusive)
# ==============================================================================


def test_acquire_consent_lock_anchor_shared_and_exclusive(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    # Shared mode (exclusive=False)
    acquire_consent_lock_anchor(db, user_id=user.id, exclusive=False)
    acquire_consent_lock_anchor(db, profile_id=profile.id, exclusive=False)

    # Exclusive mode (exclusive=True)
    acquire_consent_lock_anchor(db, user_id=user.id, exclusive=True)
    acquire_consent_lock_anchor(db, profile_id=profile.id, exclusive=True)


def test_acquire_profile_and_consent_anchor_shared_and_exclusive(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    # Default shared
    base_ver, owner_id = acquire_profile_and_consent_anchor(db, profile_id=profile.id, exclusive=False)
    assert base_ver == 0
    assert owner_id == user.id

    # Exclusive
    base_ver_ex, owner_id_ex = acquire_profile_and_consent_anchor(db, profile_id=profile.id, exclusive=True)
    assert base_ver_ex == 0
    assert owner_id_ex == user.id


def test_acquire_profile_and_consent_anchor_profile_not_found(db: Session) -> None:
    with pytest.raises(GlhsInvariantError, match="profile_not_found"):
        acquire_profile_and_consent_anchor(db, profile_id=999999)


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


# ==============================================================================
# 4. Entity Partition Concurrency Fix & Canonical Ordering
# ==============================================================================


def test_get_or_create_entity_partition_creates_and_retrieves(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    part1 = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="medications", semantic_key="rx-aspirin"
    )
    assert part1.id is not None
    assert part1.state_version == 1

    # Second call returns the existing partition
    part2 = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="medications", semantic_key="rx-aspirin"
    )
    assert part2.id == part1.id


def test_lock_entity_partitions_batched_query_and_lexicographical_order(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    partitions_input = [
        ("observations", "vital-bp"),
        ("medications", "rx-warfarin"),
        ("allergies", "allergy-penicillin"),
        ("conditions", "diag-hypertension"),
        ("medications", "rx-aspirin"),
    ]

    # First call creates and locks all 5 partitions in O(1) batched round-trips
    locked = acquire_canonical_glhs_locks(
        db,
        profile_id=profile.id,
        policy_domain="medications",
        partitions=partitions_input,
    )
    assert len(locked.locked_partitions) == 5

    # Verify strictly ordered according to \prec_lex
    keys = [(p.domain, p.semantic_key) for p in locked.locked_partitions]
    assert keys == [
        ("allergies", "allergy-penicillin"),
        ("conditions", "diag-hypertension"),
        ("medications", "rx-aspirin"),
        ("medications", "rx-warfarin"),
        ("observations", "vital-bp"),
    ]

    # Second call locks existing partitions in O(1) batched query
    locked_2 = acquire_canonical_glhs_locks(
        db,
        profile_id=profile.id,
        policy_domain="medications",
        partitions=partitions_input,
    )
    assert len(locked_2.locked_partitions) == 5
    assert [(p.domain, p.semantic_key) for p in locked_2.locked_partitions] == keys


def test_acquire_canonical_glhs_locks_strict_total_order(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    grant_row = PhrConsentService.grant(db, user_id=user.id, purpose="personalization", version="2026-v1")
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
    assert locks.effective_consent_version == f"phr_personalization:2026-v1:{grant_row.id}"
    assert len(locks.locked_partitions) == 2
    # Verify sorted lexicographically (domain, semantic_key)
    assert (locks.locked_partitions[0].domain, locks.locked_partitions[0].semantic_key) == ("conditions", "diag-002")
    assert (locks.locked_partitions[1].domain, locks.locked_partitions[1].semantic_key) == ("medications", "rx-001")


def test_acquire_canonical_glhs_locks_profile_not_found(db: Session) -> None:
    with pytest.raises(GlhsInvariantError, match="profile_not_found"):
        acquire_canonical_glhs_locks(db, profile_id=99999)


def test_increment_partition_versions(db: Session) -> None:
    user, profile = _create_user_and_profile(db)
    part = get_or_create_entity_partition(
        db, profile_id=profile.id, domain="medications", semantic_key="rx-001"
    )
    assert part.state_version == 1

    increment_partition_versions(
        db,
        partitions=[part],
        consent_version="consent-v2",
        policy_version="policy-v3",
    )
    assert part.state_version == 2
    assert part.consent_version == "consent-v2"
    assert part.policy_version == "policy-v3"
