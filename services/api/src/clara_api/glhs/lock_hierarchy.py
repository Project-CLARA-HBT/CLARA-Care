"""Unified Canonical Governance Lock Hierarchy for GLHS and Consent.

Defines and enforces the single shared canonical lock sequence across all
gateways (GST, Commitment, and Compliance/Consent endpoints):

    PolicyAnchor(d) ≺ ProfileAndConsentAnchor(u) ≺_lex EntityPartitions(u, k) ≺ LeaseState(l)

Solves the Phantom Problem on append-only ledgers (``user_consents`` and
``governance_policy_epochs``):
- A SELECT ... FOR UPDATE on the latest row does NOT block concurrent INSERTs of newer rows.
- Stable Lock Anchors (transactional advisory locks in PostgreSQL and row-level locks on
  stable anchor rows) serialize concurrent policy advances and consent grants/revocations
  with GST/Commitment transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsEntityVersionPartition,
    GlhsStateVersion,
    GovernancePolicyEpoch,
    PhrProfile,
    User,
)
from clara_api.glhs.domain import POLICY_VERSION, GlhsInvariantError


def is_postgres(db: Session) -> bool:
    """Return True if the database backend dialect is PostgreSQL."""
    try:
        bind = db.get_bind()
        return bool(bind is not None and bind.dialect.name == "postgresql")
    except Exception:
        return False


def acquire_advisory_xact_lock(db: Session, key: str) -> None:
    """Acquire a transaction-scoped exclusive advisory lock in PostgreSQL.

    In PostgreSQL, uses pg_advisory_xact_lock(hashtext(:key)), which is
    automatically released at the end of the transaction (commit or rollback).
    In SQLite/other non-PostgreSQL dialects, this is a safe no-op.
    """
    if is_postgres(db):
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": key},
        )


# --- Policy Lock Anchor -------------------------------------------------------


def acquire_policy_lock_anchor(db: Session, *, policy_domain: str | None = None) -> None:
    """Acquire stable lock anchor for governance policy epochs.

    In PostgreSQL, acquires a transactional advisory lock on the policy domain
    and global epoch namespace. This guarantees that creating, activating, or
    advancing a GovernancePolicyEpoch cannot run concurrently with a GST commit
    reading the effective policy epoch.
    """
    domain_key = policy_domain if policy_domain is not None else "__global__"
    acquire_advisory_xact_lock(db, f"policy_epoch:{domain_key}")
    if policy_domain is not None:
        acquire_advisory_xact_lock(db, "policy_epoch:__global__")


def create_governance_policy_epoch(
    db: Session,
    *,
    policy_domain: str,
    version: str,
    active_from: datetime,
    canonical_digest: str,
) -> GovernancePolicyEpoch:
    """Create and persist a new GovernancePolicyEpoch under the Policy Lock Anchor."""
    acquire_policy_lock_anchor(db, policy_domain=policy_domain)
    epoch = GovernancePolicyEpoch(
        policy_domain=policy_domain,
        version=version,
        active_from=active_from,
        canonical_digest=canonical_digest,
    )
    db.add(epoch)
    db.flush()
    return epoch


# --- Subject Profile & Consent Lock Anchor ------------------------------------


def acquire_consent_lock_anchor(
    db: Session,
    *,
    user_id: int | None = None,
    profile_id: int | None = None,
) -> None:
    """Acquire the stable per-subject consent lock anchor.

    Must be held by any transaction that writes (grants/revokes) user consent,
    and by GST/Commitment transitions when locking subject state and verifying consent.

    Acquires:
    1. PostgreSQL transactional advisory locks for user_consent and phr_profile.
    2. Row-level locks on PhrProfile and User rows (SELECT ... FOR UPDATE).
    """
    if profile_id is not None:
        acquire_advisory_xact_lock(db, f"phr_profile:{profile_id}")
        profile_row = db.execute(
            select(PhrProfile.id, PhrProfile.user_id)
            .where(PhrProfile.id == profile_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if profile_row is not None and user_id is None:
            user_id = profile_row.user_id

    if user_id is not None:
        acquire_advisory_xact_lock(db, f"user_consent:{user_id}")
        if profile_id is None:
            db.execute(
                select(PhrProfile.id)
                .where(PhrProfile.user_id == user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).fetchall()
        db.execute(
            select(User.id)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).fetchall()


def _profile_lock_statement(profile_id: int):
    """Return the SELECT ... FOR UPDATE statement for a PhrProfile row."""
    return select(PhrProfile.id).where(PhrProfile.id == profile_id).with_for_update()


def current_state_version(db: Session, *, profile_id: int) -> int:
    """Return the highest GLHS state version counter for the profile."""
    row = db.execute(
        select(GlhsStateVersion.state_version)
        .where(GlhsStateVersion.profile_id == profile_id)
        .order_by(GlhsStateVersion.state_version.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(row or 0)


def acquire_profile_and_consent_anchor(
    db: Session,
    *,
    profile_id: int,
) -> tuple[int, int]:
    """Acquire Profile & Consent Lock Anchor (Step 2 in Canonical Lock Hierarchy).

    Locks the PhrProfile row, acquires transactional advisory locks for both
    profile_id and user_id, and returns (base_state_version, owner_user_id).
    Raises GlhsInvariantError("profile_not_found") if the profile does not exist.
    """
    profile = db.execute(
        select(PhrProfile.id, PhrProfile.user_id)
        .where(PhrProfile.id == profile_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if profile is None:
        raise GlhsInvariantError("profile_not_found")

    owner_user_id = profile.user_id
    acquire_advisory_xact_lock(db, f"phr_profile:{profile_id}")
    acquire_advisory_xact_lock(db, f"user_consent:{owner_user_id}")

    base_version = current_state_version(db, profile_id=profile_id)
    return base_version, owner_user_id


# --- Entity Partition Locks (Canonical Lexicographical Order) -----------------


def get_or_create_entity_partition(
    db: Session,
    *,
    profile_id: int,
    domain: str,
    semantic_key: str,
    policy_version: str = POLICY_VERSION,
    consent_version: str = "not_required",
) -> GlhsEntityVersionPartition:
    """Retrieve or initialize the DAG entity version partition."""
    existing = db.execute(
        select(GlhsEntityVersionPartition).where(
            GlhsEntityVersionPartition.profile_id == profile_id,
            GlhsEntityVersionPartition.domain == domain,
            GlhsEntityVersionPartition.semantic_key == semantic_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return cast(GlhsEntityVersionPartition, existing)
    partition = GlhsEntityVersionPartition(
        profile_id=profile_id,
        domain=domain,
        semantic_key=semantic_key,
        state_version=1,
        policy_version=policy_version,
        consent_version=consent_version,
    )
    db.add(partition)
    db.flush()
    return partition


def lock_entity_partitions(
    db: Session,
    *,
    profile_id: int,
    partitions: list[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...],
    policy_version: str = POLICY_VERSION,
    consent_version: str = "not_required",
) -> list[GlhsEntityVersionPartition]:
    """Acquire SELECT ... FOR UPDATE row locks on entity partitions in canonical sorted order.

    Batches partition queries with in_() clause, reducing database round-trips
    from O(M) to O(1) while strictly preserving canonical lexicographical lock order \\prec_{lex}.
    """
    sorted_keys = sorted(set(partitions), key=lambda item: (item[0], item[1]))
    if not sorted_keys:
        return []

    # Step 1: Batch query all existing partitions in O(1)
    if len(sorted_keys) == 1:
        d, k = sorted_keys[0]
        existing_rows = db.execute(
            select(GlhsEntityVersionPartition).where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                GlhsEntityVersionPartition.domain == d,
                GlhsEntityVersionPartition.semantic_key == k,
            )
        ).scalars().all()
    else:
        existing_rows = db.execute(
            select(GlhsEntityVersionPartition).where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                tuple_(
                    GlhsEntityVersionPartition.domain,
                    GlhsEntityVersionPartition.semantic_key,
                ).in_(sorted_keys),
            )
        ).scalars().all()

    existing_map = {(p.domain, p.semantic_key): p for p in existing_rows}
    created_any = False
    for domain, semantic_key in sorted_keys:
        if (domain, semantic_key) not in existing_map:
            new_partition = GlhsEntityVersionPartition(
                profile_id=profile_id,
                domain=domain,
                semantic_key=semantic_key,
                state_version=1,
                policy_version=policy_version,
                consent_version=consent_version,
            )
            db.add(new_partition)
            created_any = True
            existing_map[(domain, semantic_key)] = new_partition

    if created_any:
        db.flush()

    # Step 2: Acquire SELECT ... FOR UPDATE row locks in a single O(1) batched query,
    # strictly ordered by (domain, semantic_key) in SQL to preserve canonical lexicographical order \prec_lex
    if len(sorted_keys) == 1:
        d, k = sorted_keys[0]
        locked_rows = db.execute(
            select(GlhsEntityVersionPartition)
            .where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                GlhsEntityVersionPartition.domain == d,
                GlhsEntityVersionPartition.semantic_key == k,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalars().all()
    else:
        locked_rows = db.execute(
            select(GlhsEntityVersionPartition)
            .where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                tuple_(
                    GlhsEntityVersionPartition.domain,
                    GlhsEntityVersionPartition.semantic_key,
                ).in_(sorted_keys),
            )
            .order_by(
                GlhsEntityVersionPartition.domain.asc(),
                GlhsEntityVersionPartition.semantic_key.asc(),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalars().all()

    locked_map = {(row.domain, row.semantic_key): row for row in locked_rows}
    return [locked_map[key] for key in sorted_keys if key in locked_map]


def increment_partition_versions(
    db: Session,
    *,
    partitions: list[GlhsEntityVersionPartition] | tuple[GlhsEntityVersionPartition, ...],
    consent_version: str | None = None,
    policy_version: str | None = None,
) -> None:
    """Advance local state_version counters on touched entity partitions (DAG Nodes)."""
    now = datetime.now(UTC)
    for partition in partitions:
        partition.state_version += 1
        if consent_version is not None:
            partition.consent_version = consent_version
        if policy_version is not None:
            partition.policy_version = policy_version
        partition.updated_at = now
    db.flush()


# --- Unified Canonical Lock Hierarchy Orchestrator ---------------------------


@dataclass(frozen=True)
class CanonicalLocks:
    """Result of acquiring canonical GLHS locks in strict total order."""

    base_state_version: int
    owner_user_id: int
    effective_policy_version: str
    effective_consent_version: str
    locked_partitions: list[GlhsEntityVersionPartition]


def acquire_canonical_glhs_locks(
    db: Session,
    *,
    profile_id: int,
    policy_domain: str | None = None,
    partitions: (
        list[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...] | None
    ) = None,
    purpose: str = "self_care",
) -> CanonicalLocks:
    """Acquire canonical GLHS locks in strict unified hierarchy order:

    PolicyAnchor(d) ≺ ProfileAndConsentAnchor(u) ≺_lex EntityPartitions(u, k) ≺ LeaseState(l)

    Step 1: Policy Lock Anchor
    Step 2: Profile & Consent Lock Anchor (_lock_profile_state)
    Step 3: Re-read & verify active UserConsent and GovernancePolicyEpoch under active locks
    Step 4: Entity partitions in lexicographical canonical order (lock_entity_partitions)
    """
    from clara_api.glhs.gateway import (
        _effective_policy_version,
        _governed_consent_version,
    )

    # Step 1: Policy Lock Anchor
    acquire_policy_lock_anchor(db, policy_domain=policy_domain)

    # Step 2: Profile & Consent Lock Anchor
    base_state_version, owner_user_id = acquire_profile_and_consent_anchor(
        db, profile_id=profile_id
    )

    # Step 3: Re-read & verify active UserConsent and GovernancePolicyEpoch under active locks
    current_policy_version = _effective_policy_version(
        db, for_update=True, policy_domain=policy_domain
    )
    current_consent_version = _governed_consent_version(
        db, owner_user_id=owner_user_id, purpose=purpose, for_update=True
    )

    # Step 4: Entity partitions in lexicographical canonical order
    locked_partitions: list[GlhsEntityVersionPartition] = []
    if partitions:
        locked_partitions = lock_entity_partitions(
            db,
            profile_id=profile_id,
            partitions=partitions,
            policy_version=current_policy_version,
            consent_version="not_required",
        )

    return CanonicalLocks(
        base_state_version=base_state_version,
        owner_user_id=owner_user_id,
        effective_policy_version=current_policy_version,
        effective_consent_version=current_consent_version,
        locked_partitions=locked_partitions,
    )
