"""Unified Canonical Governance Lock Hierarchy for GLHS and Consent.

Defines and enforces the single shared canonical lock sequence across all
gateways (GST, Commitment, and Compliance/Consent endpoints):

    PolicyAnchor(d) ≺ ProfileAndConsentAnchor(u) ≺_lex EntityPartitions(u, k) ≺ LeaseState(l)

Total Order across Classes 1 through 7:
    Class 1: Tenant/Global Policy
    Class 2: Domain Policy
    Class 3: Subject Consent/Profile
    Class 4: Evidence/Source
    Class 5: Entity Partitions
    Class 6: Lease/Reservation
    Class 7: Idempotency Key

Solves the Phantom Problem on append-only ledgers (``user_consents`` and
``governance_policy_epochs``):
- A SELECT ... FOR UPDATE on the latest row does NOT block concurrent INSERTs of newer rows.
- Stable Lock Anchors (transactional advisory locks in PostgreSQL and row-level locks on
  stable anchor rows) serialize concurrent policy advances and consent grants/revocations
  with GST/Commitment transitions.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any, cast

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


class LockClass(IntEnum):
    """Canonical lock hierarchy classes (total order 1 through 7)."""

    TENANT_GLOBAL_POLICY = 1
    DOMAIN_POLICY = 2
    SUBJECT_CONSENT_PROFILE = 3
    EVIDENCE_SOURCE = 4
    ENTITY_PARTITIONS = 5
    LEASE_RESERVATION = 6
    IDEMPOTENCY_KEY = 7


class LockMode(StrEnum):
    """Lock acquisition mode."""

    SHARED = "SHARED"
    EXCLUSIVE = "EXCLUSIVE"


_KIND_TO_LOCK_CLASS: dict[str, LockClass] = {
    # Class 1: Tenant/Global Policy
    "tenant_policy": LockClass.TENANT_GLOBAL_POLICY,
    "global_policy": LockClass.TENANT_GLOBAL_POLICY,
    "tenant_global_policy": LockClass.TENANT_GLOBAL_POLICY,
    "policy_global": LockClass.TENANT_GLOBAL_POLICY,
    "global": LockClass.TENANT_GLOBAL_POLICY,
    "tenant": LockClass.TENANT_GLOBAL_POLICY,
    "tenant_global": LockClass.TENANT_GLOBAL_POLICY,
    "tenant_lock": LockClass.TENANT_GLOBAL_POLICY,
    "global_lock": LockClass.TENANT_GLOBAL_POLICY,
    # Class 2: Domain Policy
    "domain_policy": LockClass.DOMAIN_POLICY,
    "policy_domain": LockClass.DOMAIN_POLICY,
    "domain": LockClass.DOMAIN_POLICY,
    "policy": LockClass.DOMAIN_POLICY,
    # Class 3: Subject Consent/Profile
    "subject_consent": LockClass.SUBJECT_CONSENT_PROFILE,
    "subject_profile": LockClass.SUBJECT_CONSENT_PROFILE,
    "consent": LockClass.SUBJECT_CONSENT_PROFILE,
    "profile": LockClass.SUBJECT_CONSENT_PROFILE,
    "user_consent": LockClass.SUBJECT_CONSENT_PROFILE,
    "phr_profile": LockClass.SUBJECT_CONSENT_PROFILE,
    "subject": LockClass.SUBJECT_CONSENT_PROFILE,
    "subject_consent_profile": LockClass.SUBJECT_CONSENT_PROFILE,
    "user": LockClass.SUBJECT_CONSENT_PROFILE,
    # Class 4: Evidence/Source
    "evidence": LockClass.EVIDENCE_SOURCE,
    "source": LockClass.EVIDENCE_SOURCE,
    "evidence_source": LockClass.EVIDENCE_SOURCE,
    "health_source": LockClass.EVIDENCE_SOURCE,
    "evidence_ptr": LockClass.EVIDENCE_SOURCE,
    # Class 5: Entity Partitions
    "entity_partition": LockClass.ENTITY_PARTITIONS,
    "entity_partitions": LockClass.ENTITY_PARTITIONS,
    "entity": LockClass.ENTITY_PARTITIONS,
    "partition": LockClass.ENTITY_PARTITIONS,
    "entity_version_partition": LockClass.ENTITY_PARTITIONS,
    # Class 6: Lease/Reservation
    "lease": LockClass.LEASE_RESERVATION,
    "reservation": LockClass.LEASE_RESERVATION,
    "lease_reservation": LockClass.LEASE_RESERVATION,
    # Class 7: Idempotency Key
    "idempotency_key": LockClass.IDEMPOTENCY_KEY,
    "idempotency": LockClass.IDEMPOTENCY_KEY,
    "idempotency_lock": LockClass.IDEMPOTENCY_KEY,
}


def resolve_lock_class(kind: Any) -> LockClass:
    """Resolve dependency kind or integer class to LockClass.

    Raises GlhsInvariantError if kind is unknown.
    """
    if isinstance(kind, LockClass):
        return kind
    if isinstance(kind, int):
        try:
            return LockClass(kind)
        except ValueError as err:
            raise GlhsInvariantError(f"unknown_dependency_kind: {kind}") from err
    if isinstance(kind, str):
        normalized = kind.strip().lower()
        if normalized in _KIND_TO_LOCK_CLASS:
            return _KIND_TO_LOCK_CLASS[normalized]
        if normalized.isdigit():
            val = int(normalized)
            if 1 <= val <= 7:
                return LockClass(val)
    raise GlhsInvariantError(f"unknown_dependency_kind: {kind}")


def resolve_lock_mode(mode: Any) -> LockMode:
    """Resolve lock mode to LockMode.SHARED or LockMode.EXCLUSIVE.

    Raises GlhsInvariantError if mode is invalid.
    """
    if isinstance(mode, LockMode):
        return mode
    if isinstance(mode, bool):
        return LockMode.EXCLUSIVE if mode else LockMode.SHARED
    if isinstance(mode, str):
        normalized = mode.strip().upper()
        if normalized in ("EXCLUSIVE", "WRITE", "X", "W"):
            return LockMode.EXCLUSIVE
        if normalized in ("SHARED", "READ", "S", "R"):
            return LockMode.SHARED
    raise GlhsInvariantError(f"invalid_lock_mode: {mode}")


@dataclass(frozen=True)
class LockPlanItem:
    """A canonical lock plan item."""

    lock_class: LockClass
    key: str
    mode: LockMode = LockMode.SHARED
    kind: str | None = None


@dataclass(frozen=True)
class LockDependency:
    """Input dependency representation for building a lock plan."""

    kind: str | LockClass | int
    key: str
    mode: LockMode | str | bool = LockMode.SHARED


@dataclass(frozen=True)
class LockPlan:
    """Deterministic, canonically ordered sequence of lock acquisitions."""

    items: tuple[LockPlanItem, ...]

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> LockPlanItem:
        return self.items[index]


def _extract_dependency_info(dep: Any) -> tuple[LockClass, str, LockMode]:
    """Extract (lock_class, key, mode) from various dependency representations."""
    if dep is None:
        raise GlhsInvariantError("missing_dependency")

    if isinstance(dep, (tuple, list)):
        if len(dep) == 2:
            kind, key = dep
            raw_mode: Any = LockMode.SHARED
        elif len(dep) >= 3:
            kind, key, raw_mode = dep[0], dep[1], dep[2]
        else:
            raise GlhsInvariantError("invalid_dependency_tuple")
        if key is None or str(key).strip() == "":
            raise GlhsInvariantError("missing_lock_key")
        return resolve_lock_class(kind), str(key), resolve_lock_mode(raw_mode)

    if isinstance(dep, dict):
        kind = (
            dep.get("kind")
            or dep.get("type")
            or dep.get("lock_class")
            or dep.get("category")
        )
        key = (
            dep.get("key")
            or dep.get("resource_key")
            or dep.get("target")
            or dep.get("lock_key")
            or dep.get("semantic_key")
            or dep.get("name")
            or dep.get("id")
        )
        raw_mode = dep.get("mode") if "mode" in dep else dep.get("access_mode", LockMode.SHARED)
        if "exclusive" in dep:
            raw_mode = LockMode.EXCLUSIVE if dep["exclusive"] else LockMode.SHARED
        if key is None or str(key).strip() == "":
            raise GlhsInvariantError("missing_lock_key")
        return resolve_lock_class(kind), str(key), resolve_lock_mode(raw_mode)

    # Generic object/dataclass
    kind = (
        getattr(dep, "kind", None)
        or getattr(dep, "lock_class", None)
        or getattr(dep, "type", None)
        or getattr(dep, "category", None)
    )
    key = (
        getattr(dep, "key", None)
        or getattr(dep, "resource_key", None)
        or getattr(dep, "target", None)
        or getattr(dep, "lock_key", None)
        or getattr(dep, "semantic_key", None)
        or getattr(dep, "name", None)
        or getattr(dep, "id", None)
    )
    raw_mode = getattr(dep, "mode", None)
    if raw_mode is None:
        raw_mode = getattr(dep, "access_mode", None)
    if raw_mode is None and hasattr(dep, "exclusive"):
        raw_mode = LockMode.EXCLUSIVE if dep.exclusive else LockMode.SHARED
    if raw_mode is None:
        raw_mode = LockMode.SHARED

    if key is None or str(key).strip() == "":
        raise GlhsInvariantError("missing_lock_key")
    return resolve_lock_class(kind), str(key), resolve_lock_mode(raw_mode)


def build_lock_plan(dependencies: Iterable[Any] | None) -> LockPlan:
    """Build a pure, deterministic canonical lock plan across classes 1 to 7.

    Total order:
        Class 1: Tenant/Global Policy
        Class 2: Domain Policy
        Class 3: Subject Consent/Profile
        Class 4: Evidence/Source
        Class 5: Entity Partitions
        Class 6: Lease/Reservation
        Class 7: Idempotency Key

    Within each class, locks are ordered by raw UTF-8 bytes of the key.
    Duplicate keys within the same class are collapsed, with mode escalation:
        EXCLUSIVE > SHARED

    Refuses unknown dependency kinds by raising GlhsInvariantError.
    """
    if dependencies is None:
        return LockPlan(items=())

    grouped: dict[tuple[LockClass, str], LockMode] = {}

    for dep in dependencies:
        lock_class, key, mode = _extract_dependency_info(dep)
        group_key = (lock_class, key)
        if group_key not in grouped:
            grouped[group_key] = mode
        else:
            # Mode escalation: EXCLUSIVE > SHARED
            if mode == LockMode.EXCLUSIVE:
                grouped[group_key] = LockMode.EXCLUSIVE

    # Strict canonical sort:
    # 1. LockClass ascending (1 through 7)
    # 2. Raw UTF-8 bytes of key ascending
    sorted_group_keys = sorted(
        grouped.keys(),
        key=lambda item: (item[0].value, item[1].encode("utf-8")),
    )

    items = tuple(
        LockPlanItem(
            lock_class=lc,
            key=k,
            mode=grouped[(lc, k)],
        )
        for lc, k in sorted_group_keys
    )

    return LockPlan(items=items)


def is_postgres(db: Session) -> bool:
    """Return True if the database backend dialect is PostgreSQL."""
    try:
        bind = db.get_bind()
        return bool(bind is not None and bind.dialect.name == "postgresql")
    except Exception:
        return False


def acquire_advisory_xact_lock(db: Session, key: str | int) -> None:
    """Acquire a transaction-scoped exclusive advisory lock in PostgreSQL.

    In PostgreSQL, uses pg_advisory_xact_lock(hashtext(:key)), which is
    automatically released at the end of the transaction (commit or rollback).
    In SQLite/other non-PostgreSQL dialects, this is a safe no-op.
    """
    acquire_governance_anchor(db, key, mode=LockMode.EXCLUSIVE)


def acquire_advisory_xact_lock_shared(db: Session, key: str | int) -> None:
    """Acquire a transaction-scoped shared advisory lock in PostgreSQL.

    Allows concurrent shared readers (GST transitions) while blocking exclusive writers.
    """
    acquire_governance_anchor(db, key, mode=LockMode.SHARED)


def acquire_governance_anchor(
    db: Session,
    key: str | int,
    mode: str | LockMode = "SHARED",
) -> None:
    """Acquire a governance anchor PostgreSQL transactional advisory lock.

    In PostgreSQL, uses pg_advisory_xact_lock_shared for SHARED mode
    and pg_advisory_xact_lock for EXCLUSIVE mode.
    In SQLite/other non-PostgreSQL dialects, this is a safe no-op.
    """
    resolved_mode = resolve_lock_mode(mode)
    if is_postgres(db):
        if isinstance(key, int):
            if resolved_mode == LockMode.EXCLUSIVE:
                db.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": key},
                )
            else:
                db.execute(
                    text("SELECT pg_advisory_xact_lock_shared(:key)"),
                    {"key": key},
                )
        else:
            if resolved_mode == LockMode.EXCLUSIVE:
                db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                    {"key": str(key)},
                )
            else:
                db.execute(
                    text("SELECT pg_advisory_xact_lock_shared(hashtext(:key))"),
                    {"key": str(key)},
                )


# --- Policy Lock Anchor -------------------------------------------------------


def acquire_policy_lock_anchor(
    db: Session,
    policy_domain: str | None = None,
    mode: str | LockMode = "SHARED",
) -> None:
    """Acquire stable lock anchor for governance policy epochs.

    In PostgreSQL, acquires transactional advisory lock(s) in strict canonical order:
    1. Class 1: Global policy anchor ("policy_epoch:__global__")
    2. Class 2: Domain policy anchor ("policy_epoch:<policy_domain>") if policy_domain specified.
    """
    resolved_mode = resolve_lock_mode(mode)
    acquire_governance_anchor(db, "policy_epoch:__global__", mode=resolved_mode)
    if policy_domain is not None and policy_domain != "__global__":
        acquire_governance_anchor(db, f"policy_epoch:{policy_domain}", mode=resolved_mode)


def create_governance_policy_epoch(
    db: Session,
    *,
    policy_domain: str,
    version: str,
    active_from: datetime,
    canonical_digest: str,
) -> GovernancePolicyEpoch:
    """Create and persist a new GovernancePolicyEpoch under the Policy Lock Anchor."""
    acquire_policy_lock_anchor(db, policy_domain=policy_domain, mode=LockMode.EXCLUSIVE)
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
    exclusive: bool = True,
) -> None:
    """Acquire the stable per-subject consent lock anchor.

    Must be held by any transaction that writes (grants/revokes) user consent (exclusive=True),
    and by GST/Commitment transitions when locking subject state and verifying consent (exclusive=False).

    Strict unified canonical acquisition sequence:
    Step 2a: Always lock User row: SELECT id FROM users WHERE id = :user_id (FOR UPDATE if exclusive, FOR SHARE if shared)
    Step 2b: Lock PhrProfile row(s): SELECT id FROM phr_profiles WHERE ... (FOR UPDATE if exclusive, FOR SHARE if shared)
    Step 2c: Transactional advisory locks: user_consent:<user_id> then phr_profile:<profile_id>
    """
    if profile_id is not None and user_id is None:
        profile_lookup = db.execute(
            select(PhrProfile.user_id).where(PhrProfile.id == profile_id)
        ).first()
        if profile_lookup is not None:
            user_id = profile_lookup.user_id

    lock_mode = LockMode.EXCLUSIVE if exclusive else LockMode.SHARED

    if user_id is not None:
        # Step 2a: Always lock User row first
        db.execute(
            select(User.id)
            .where(User.id == user_id)
            .with_for_update(read=not exclusive)
            .execution_options(populate_existing=True)
        ).fetchall()

        # Step 2b: Lock PhrProfile row(s) second
        profile_ids: list[int] = []
        if profile_id is not None:
            db.execute(
                select(PhrProfile.id)
                .where(PhrProfile.id == profile_id)
                .with_for_update(read=not exclusive)
                .execution_options(populate_existing=True)
            ).fetchall()
            profile_ids = [profile_id]
        else:
            p_rows = db.execute(
                select(PhrProfile.id)
                .where(PhrProfile.user_id == user_id)
                .order_by(PhrProfile.id.asc())
                .with_for_update(read=not exclusive)
                .execution_options(populate_existing=True)
            ).scalars().all()
            profile_ids = list(p_rows)

        # Step 2c: Transactional advisory locks
        acquire_governance_anchor(db, f"user_consent:{user_id}", mode=lock_mode)
        for pid in profile_ids:
            acquire_governance_anchor(db, f"phr_profile:{pid}", mode=lock_mode)
    elif profile_id is not None:
        db.execute(
            select(PhrProfile.id)
            .where(PhrProfile.id == profile_id)
            .with_for_update(read=not exclusive)
            .execution_options(populate_existing=True)
        ).fetchall()
        acquire_governance_anchor(db, f"phr_profile:{profile_id}", mode=lock_mode)


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
    exclusive: bool = False,
) -> tuple[int, int]:
    """Acquire Profile & Consent Lock Anchor (Step 2 in Canonical Lock Hierarchy).

    Strict unified canonical acquisition sequence:
    Step 2a: Always lock User row (FOR UPDATE if exclusive, FOR SHARE if shared)
    Step 2b: Lock PhrProfile row (FOR UPDATE if exclusive, FOR SHARE if shared)
    Step 2c: Transactional advisory locks: user_consent:<user_id> then phr_profile:<profile_id>

    Returns (base_state_version, owner_user_id).
    Raises GlhsInvariantError("profile_not_found") if the profile does not exist.
    """
    profile_lookup = db.execute(
        select(PhrProfile.id, PhrProfile.user_id).where(PhrProfile.id == profile_id)
    ).first()
    if profile_lookup is None:
        raise GlhsInvariantError("profile_not_found")

    owner_user_id = profile_lookup.user_id
    lock_mode = LockMode.EXCLUSIVE if exclusive else LockMode.SHARED

    # Step 2a: Lock User row FIRST
    user_stmt = select(User.id).where(User.id == owner_user_id)
    user_stmt = user_stmt.with_for_update(read=not exclusive)
    db.execute(user_stmt.execution_options(populate_existing=True)).fetchall()

    # Step 2b: Lock PhrProfile row SECOND
    profile_stmt = (
        select(PhrProfile.id, PhrProfile.user_id)
        .where(PhrProfile.id == profile_id)
        .with_for_update(read=not exclusive)
    )
    profile = db.execute(
        profile_stmt.execution_options(populate_existing=True)
    ).first()
    if profile is None:
        raise GlhsInvariantError("profile_not_found")

    # Step 2c: Transactional advisory locks (Shared vs. Exclusive)
    acquire_governance_anchor(db, f"user_consent:{owner_user_id}", mode=lock_mode)
    acquire_governance_anchor(db, f"phr_profile:{profile_id}", mode=lock_mode)

    base_version = current_state_version(db, profile_id=profile_id)
    return base_version, owner_user_id


# --- Entity Partition Locks (Canonical Lexicographical Order) -----------------


def _insert_partition_on_conflict_do_nothing(
    db: Session,
    *,
    profile_id: int,
    domain: str,
    semantic_key: str,
    policy_version: str = POLICY_VERSION,
    consent_version: str = "not_required",
) -> None:
    """Insert a single entity partition row with ON CONFLICT DO NOTHING semantics."""
    dialect_name = ""
    try:
        bind = db.get_bind()
        if bind is not None and bind.dialect is not None:
            dialect_name = bind.dialect.name
    except Exception:
        pass

    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        pg_stmt = (
            pg_insert(GlhsEntityVersionPartition)
            .values(
                profile_id=profile_id,
                domain=domain,
                semantic_key=semantic_key,
                state_version=1,
                policy_version=policy_version,
                consent_version=consent_version,
            )
            .on_conflict_do_nothing(
                index_elements=["profile_id", "domain", "semantic_key"]
            )
        )
        db.execute(pg_stmt)
    elif dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        sqlite_stmt = (
            sqlite_insert(GlhsEntityVersionPartition)
            .values(
                profile_id=profile_id,
                domain=domain,
                semantic_key=semantic_key,
                state_version=1,
                policy_version=policy_version,
                consent_version=consent_version,
            )
            .on_conflict_do_nothing()
        )
        db.execute(sqlite_stmt)
    else:
        existing = db.execute(
            select(GlhsEntityVersionPartition).where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                GlhsEntityVersionPartition.domain == domain,
                GlhsEntityVersionPartition.semantic_key == semantic_key,
            )
        ).scalar_one_or_none()
        if existing is None:
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


def _batch_insert_partitions_on_conflict_do_nothing(
    db: Session,
    *,
    profile_id: int,
    keys: Sequence[tuple[str, str]],
    policy_version: str = POLICY_VERSION,
    consent_version: str = "not_required",
) -> None:
    """Batch-insert entity partition rows with ON CONFLICT DO NOTHING semantics."""
    if not keys:
        return

    dialect_name = ""
    try:
        bind = db.get_bind()
        if bind is not None and bind.dialect is not None:
            dialect_name = bind.dialect.name
    except Exception:
        pass

    values = [
        {
            "profile_id": profile_id,
            "domain": d,
            "semantic_key": k,
            "state_version": 1,
            "policy_version": policy_version,
            "consent_version": consent_version,
        }
        for d, k in keys
    ]

    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        pg_stmt = pg_insert(GlhsEntityVersionPartition).values(values).on_conflict_do_nothing(
            index_elements=["profile_id", "domain", "semantic_key"]
        )
        db.execute(pg_stmt)
    elif dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        sqlite_stmt = sqlite_insert(GlhsEntityVersionPartition).values(values).on_conflict_do_nothing()
        db.execute(sqlite_stmt)
    else:
        for d, k in keys:
            _insert_partition_on_conflict_do_nothing(
                db,
                profile_id=profile_id,
                domain=d,
                semantic_key=k,
                policy_version=policy_version,
                consent_version=consent_version,
            )


def get_or_create_entity_partition(
    db: Session,
    *,
    profile_id: int,
    domain: str,
    semantic_key: str,
    policy_version: str = POLICY_VERSION,
    consent_version: str = "not_required",
) -> GlhsEntityVersionPartition:
    """Retrieve or initialize the DAG entity version partition safely under concurrency.

    Acquires logical partition advisory lock before INSERT ... ON CONFLICT DO NOTHING
    to prevent race conditions when creating initial partition rows.
    """
    existing = db.execute(
        select(GlhsEntityVersionPartition).where(
            GlhsEntityVersionPartition.profile_id == profile_id,
            GlhsEntityVersionPartition.domain == domain,
            GlhsEntityVersionPartition.semantic_key == semantic_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return cast(GlhsEntityVersionPartition, existing)

    # Step 1: Acquire logical partition advisory lock
    acquire_advisory_xact_lock(
        db, f"entity_partition:{profile_id}:{domain}:{semantic_key}"
    )

    # Step 2: INSERT ... ON CONFLICT DO NOTHING
    _insert_partition_on_conflict_do_nothing(
        db,
        profile_id=profile_id,
        domain=domain,
        semantic_key=semantic_key,
        policy_version=policy_version,
        consent_version=consent_version,
    )

    # Step 3: Fetch the partition row
    partition = db.execute(
        select(GlhsEntityVersionPartition).where(
            GlhsEntityVersionPartition.profile_id == profile_id,
            GlhsEntityVersionPartition.domain == domain,
            GlhsEntityVersionPartition.semantic_key == semantic_key,
        ).execution_options(populate_existing=True)
    ).scalar_one()
    return cast(GlhsEntityVersionPartition, partition)


def lock_entity_partitions(
    db: Session,
    *,
    profile_id: int,
    partitions: list[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...],
    policy_version: str = POLICY_VERSION,
    consent_version: str = "not_required",
) -> list[GlhsEntityVersionPartition]:
    """Acquire SELECT ... FOR UPDATE row locks on entity partitions in canonical sorted order.

    1. Sort partition keys canonically (lexicographical total order).
    2. Check existing partitions.
    3. For any missing partition, acquire logical partition advisory lock and INSERT ... ON CONFLICT DO NOTHING.
    4. Acquire SELECT ... FOR UPDATE row locks in a single batched query ordered by (domain, semantic_key).
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

    existing_set = {(p.domain, p.semantic_key) for p in existing_rows}
    missing_keys = [k for k in sorted_keys if k not in existing_set]

    # Step 2: For any missing partitions, acquire logical advisory locks and insert safely
    if missing_keys:
        for domain, semantic_key in missing_keys:
            acquire_advisory_xact_lock(
                db, f"entity_partition:{profile_id}:{domain}:{semantic_key}"
            )

        _batch_insert_partitions_on_conflict_do_nothing(
            db,
            profile_id=profile_id,
            keys=missing_keys,
            policy_version=policy_version,
            consent_version=consent_version,
        )

    # Step 3: Acquire SELECT ... FOR UPDATE row locks in canonical lexicographical order
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

    Step 1: Policy Lock Anchor (Shared)
    Step 2: Profile & Consent Lock Anchor (Shared)
    Step 3: Re-read & verify active UserConsent and GovernancePolicyEpoch under active locks
    Step 4: Entity partitions in lexicographical canonical order (lock_entity_partitions)
    """
    from clara_api.glhs.gateway import (
        _effective_policy_version,
        _governed_consent_version,
    )

    # Step 1: Policy Lock Anchor (Shared)
    acquire_policy_lock_anchor(db, policy_domain=policy_domain, mode=LockMode.SHARED)

    # Step 2: Profile & Consent Lock Anchor (Shared)
    base_state_version, owner_user_id = acquire_profile_and_consent_anchor(
        db, profile_id=profile_id, exclusive=False
    )

    # Step 3: Re-read & verify active UserConsent and GovernancePolicyEpoch under active locks
    current_policy_version = _effective_policy_version(
        db, for_update=False, policy_domain=policy_domain
    )
    current_consent_version = _governed_consent_version(
        db, owner_user_id=owner_user_id, purpose=purpose, for_update=False
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
