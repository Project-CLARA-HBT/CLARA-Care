"""Atomic 6-Phase Linearizable OCC Commit Kernel for GLHS State Transitions.

Provides the non-bypassable transactional commit engine enforcing linearizable
Optimistic Concurrency Control (OCC) with canonical lock acquisition, dependency
revalidation, domain mutation execution, CAS partition progression, and transactional
outbox event dispatch.

The 6-phase atomic commit sequence:
    Phase 1: Fast idempotency pre-check with `GlhsAppliedTransition`.
    Phase 2: Canonical lock acquisition:
             PolicyAnchor(d) ≺ ProfileAndConsentAnchor(u) ≺_lex EntityPartitions(u, k)
             (`acquire_policy_lock_anchor` SHARED, `acquire_profile_and_consent_anchor` SHARED,
              `lock_entity_partitions` in canonical lexicographical order).
    Phase 3: Freshness & per-partition dependency revalidation under locks.
    Phase 4: Domain mutation callback execution.
    Phase 5: CAS-increment only WRITE partitions (successor_version = predecessor_version + 1),
             record `GlhsTransitionPartitionLink` rows.
    Phase 6: Insert `GlhsAppliedTransition` record and transactional outbox event.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar, overload
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsAppliedTransition,
    GlhsEntityVersionPartition,
    GlhsProposalDependency,
    GlhsTransitionPartitionLink,
)
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    fast_canonical_digest,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.lock_hierarchy import (
    LockMode,
    acquire_policy_lock_anchor,
    acquire_profile_and_consent_anchor,
    lock_entity_partitions,
)
from clara_api.lifemap.commands import add_outbox

T = TypeVar("T")


@dataclass(frozen=True)
class DependencySpec:
    """Normalized dependency specification for GLHS proposal validation."""

    dependency_kind: str  # "GOVERNANCE", "ENTITY", "EVIDENCE", "LEASE"
    dependency_key: str  # e.g. "medications:metformin" or "policy_epoch:medications"
    access_mode: str = "READ"  # "READ" or "WRITE"
    observed_version: int = 0
    observed_digest: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    canonicalization_profile: str = CANONICALIZATION_PROFILE


@dataclass(frozen=True)
class GlhsCommitContext:
    """Transactional context provided to domain mutation callbacks in Phase 4."""

    db: Session
    profile_id: int
    owner_user_id: int
    base_state_version: int
    effective_policy_version: str
    effective_consent_version: str
    locked_partitions: dict[tuple[str, str], GlhsEntityVersionPartition]
    dependencies: Sequence[DependencySpec]
    tenant_id: str
    operation_kind: str
    idempotency_key: str
    proposal_id: int | None
    custom_payload: Any = None


@dataclass(frozen=True)
class GlhsCommitResult(Generic[T]):
    """Result of an executed atomic GLHS commit."""

    applied_transition: GlhsAppliedTransition
    partition_links: list[GlhsTransitionPartitionLink]
    mutation_result: T | None
    idempotent_replay: bool
    transition_status: str


def compute_dependency_vector_digest(
    dependencies: Sequence[Any],
    *,
    profile: str = CANONICALIZATION_PROFILE,
) -> str:
    """Compute deterministic cryptographic SHA-256 digest over normalized dependency vector.

    Sorts dependencies canonically by (dependency_kind, dependency_key, access_mode, observed_version).
    """
    normalized: list[dict[str, Any]] = []
    for dep in dependencies:
        if isinstance(dep, Mapping):
            kind = dep.get("dependency_kind", "")
            key = dep.get("dependency_key", "")
            mode = dep.get("access_mode", "READ")
            ver = dep.get("observed_version", 0)
            digest = dep.get("observed_digest")
        else:
            kind = getattr(dep, "dependency_kind", "")
            key = getattr(dep, "dependency_key", "")
            mode = getattr(dep, "access_mode", "READ")
            ver = getattr(dep, "observed_version", 0)
            digest = getattr(dep, "observed_digest", None)

        normalized.append(
            {
                "access_mode": str(mode).upper(),
                "dependency_kind": str(kind).upper(),
                "dependency_key": str(key),
                "observed_digest": str(digest) if digest is not None else "",
                "observed_version": int(ver if ver is not None else 0),
            }
        )

    sorted_deps = sorted(
        normalized,
        key=lambda d: (
            d["dependency_kind"],
            d["dependency_key"],
            d["access_mode"],
            d["observed_version"],
        ),
    )
    return fast_canonical_digest(sorted_deps, profile=profile)


def parse_entity_partition_key(
    key: str,
    *,
    default_domain: str | None = None,
) -> tuple[str, str]:
    """Parse (domain, semantic_key) coordinate from entity dependency key.

    Supports formats:
      - '<domain>:<semantic_key>'
      - '<semantic_key>' (uses default_domain or 'general')
    """
    key_str = str(key).strip()
    if ":" in key_str:
        domain, semantic_key = key_str.split(":", 1)
        return domain.strip(), semantic_key.strip()
    return (default_domain or "general").strip(), key_str


def _normalize_dependency(
    dep: Any,
    *,
    default_domain: str | None = None,
) -> DependencySpec:
    """Normalize input dependency object, dict, or tuple to DependencySpec."""
    if isinstance(dep, DependencySpec):
        return dep
    if isinstance(dep, GlhsProposalDependency):
        return DependencySpec(
            dependency_kind=dep.dependency_kind,
            dependency_key=dep.dependency_key,
            access_mode=dep.access_mode,
            observed_version=dep.observed_version,
            observed_digest=dep.observed_digest,
            valid_from=dep.valid_from,
            valid_to=dep.valid_to,
            canonicalization_profile=dep.canonicalization_profile or CANONICALIZATION_PROFILE,
        )
    if isinstance(dep, Mapping):
        kind = dep.get("dependency_kind") or dep.get("kind") or "ENTITY"
        key = dep.get("dependency_key") or dep.get("key") or ""
        mode = dep.get("access_mode") or dep.get("mode") or "READ"
        ver = dep.get("observed_version") or dep.get("version") or 0
        digest = dep.get("observed_digest") or dep.get("digest")
        valid_from = dep.get("valid_from")
        valid_to = dep.get("valid_to")
        prof = dep.get("canonicalization_profile") or CANONICALIZATION_PROFILE
        return DependencySpec(
            dependency_kind=str(kind).upper(),
            dependency_key=str(key),
            access_mode=str(mode).upper(),
            observed_version=int(ver),
            observed_digest=str(digest) if digest is not None else None,
            valid_from=valid_from,
            valid_to=valid_to,
            canonicalization_profile=str(prof),
        )
    if isinstance(dep, (tuple, list)):
        if len(dep) == 2:
            d, k = dep[0], dep[1]
            return DependencySpec(
                dependency_kind="ENTITY",
                dependency_key=f"{d}:{k}",
                access_mode="WRITE",
                observed_version=0,
            )
        elif len(dep) >= 3:
            kind, key, ver = dep[0], dep[1], dep[2]
            mode = dep[3] if len(dep) > 3 else "READ"
            return DependencySpec(
                dependency_kind=str(kind).upper(),
                dependency_key=str(key),
                access_mode=str(mode).upper(),
                observed_version=int(ver),
            )

    kind = getattr(dep, "dependency_kind", "ENTITY")
    key = getattr(dep, "dependency_key", "")
    mode = getattr(dep, "access_mode", "READ")
    ver = getattr(dep, "observed_version", 0)
    digest = getattr(dep, "observed_digest", None)
    valid_from = getattr(dep, "valid_from", None)
    valid_to = getattr(dep, "valid_to", None)
    prof = getattr(dep, "canonicalization_profile", CANONICALIZATION_PROFILE)
    return DependencySpec(
        dependency_kind=str(kind).upper(),
        dependency_key=str(key),
        access_mode=str(mode).upper(),
        observed_version=int(ver),
        observed_digest=str(digest) if digest is not None else None,
        valid_from=valid_from,
        valid_to=valid_to,
        canonicalization_profile=str(prof),
    )


@overload
def execute_atomic_glhs_commit(
    db: Session,
    *,
    profile_id: int,
    idempotency_key: str,
    proposal_id: int | None = None,
    tenant_id: str = "default",
    operation_kind: str = "COMMIT_PROPOSAL",
    request_digest: str = "",
    disclosure_digest: str = "",
    audit_event_id: str | None = None,
    policy_domain: str | None = None,
    purpose: str = "self_care",
    dependencies: Sequence[Any] | None = None,
    write_partitions: (
        Sequence[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...] | None
    ) = None,
    expected_base_state_version: int | None = None,
    expected_policy_version: str | None = None,
    expected_consent_version: str | None = None,
    canonicalization_profile: str = CANONICALIZATION_PROFILE,
    mutation_callback: None = None,
    custom_payload: Any = None,
    aggregate_type: str = "glhs_transition",
    aggregate_public_id: str | None = None,
    event_type: str = "glhs.transition.applied",
) -> GlhsCommitResult[Any]: ...


@overload
def execute_atomic_glhs_commit(
    db: Session,
    *,
    profile_id: int,
    idempotency_key: str,
    proposal_id: int | None = None,
    tenant_id: str = "default",
    operation_kind: str = "COMMIT_PROPOSAL",
    request_digest: str = "",
    disclosure_digest: str = "",
    audit_event_id: str | None = None,
    policy_domain: str | None = None,
    purpose: str = "self_care",
    dependencies: Sequence[Any] | None = None,
    write_partitions: (
        Sequence[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...] | None
    ) = None,
    expected_base_state_version: int | None = None,
    expected_policy_version: str | None = None,
    expected_consent_version: str | None = None,
    canonicalization_profile: str = CANONICALIZATION_PROFILE,
    mutation_callback: Callable[[GlhsCommitContext], T],
    custom_payload: Any = None,
    aggregate_type: str = "glhs_transition",
    aggregate_public_id: str | None = None,
    event_type: str = "glhs.transition.applied",
) -> GlhsCommitResult[T]: ...


def execute_atomic_glhs_commit(
    db: Session,
    *,
    profile_id: int,
    idempotency_key: str,
    proposal_id: int | None = None,
    tenant_id: str = "default",
    operation_kind: str = "COMMIT_PROPOSAL",
    request_digest: str = "",
    disclosure_digest: str = "",
    audit_event_id: str | None = None,
    policy_domain: str | None = None,
    purpose: str = "self_care",
    dependencies: Sequence[Any] | None = None,
    write_partitions: (
        Sequence[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...] | None
    ) = None,
    expected_base_state_version: int | None = None,
    expected_policy_version: str | None = None,
    expected_consent_version: str | None = None,
    canonicalization_profile: str = CANONICALIZATION_PROFILE,
    mutation_callback: Callable[[GlhsCommitContext], Any] | None = None,
    custom_payload: Any = None,
    aggregate_type: str = "glhs_transition",
    aggregate_public_id: str | None = None,
    event_type: str = "glhs.transition.applied",
) -> GlhsCommitResult[Any]:
    """Execute linearizable 6-phase OCC atomic GLHS state transition commit.

    Phase 1: Fast idempotency pre-check with `GlhsAppliedTransition`.
    Phase 2: Canonical lock acquisition (`acquire_policy_lock_anchor` SHARED,
             `acquire_profile_and_consent_anchor` SHARED, `lock_entity_partitions`).
    Phase 3: Freshness & per-partition dependency revalidation under locks.
    Phase 4: Domain mutation callback execution.
    Phase 5: CAS-increment only WRITE partitions (successor_version = predecessor_version + 1),
             record `GlhsTransitionPartitionLink` rows.
    Phase 6: Insert `GlhsAppliedTransition` record and transactional outbox event.
    """
    if not idempotency_key or not str(idempotency_key).strip():
        raise GlhsInvariantError("missing_idempotency_key")
    if not operation_kind or not str(operation_kind).strip():
        raise GlhsInvariantError("missing_operation_kind")

    # =========================================================================
    # Phase 1: Fast idempotency pre-check with GlhsAppliedTransition
    # =========================================================================
    existing_query = select(GlhsAppliedTransition).where(
        GlhsAppliedTransition.tenant_id == tenant_id,
        GlhsAppliedTransition.operation_kind == operation_kind,
        GlhsAppliedTransition.idempotency_key == idempotency_key,
    )
    existing = db.execute(existing_query).scalar_one_or_none()

    if existing is None and proposal_id is not None and proposal_id > 0 and operation_kind == "COMMIT_PROPOSAL":
        existing = db.execute(
            select(GlhsAppliedTransition).where(
                GlhsAppliedTransition.proposal_id == proposal_id
            )
        ).scalar_one_or_none()

    if existing is not None:
        if request_digest and existing.request_digest and existing.request_digest != request_digest:
            raise GlhsInvariantError("idempotency_key_reused: idempotency_key_reuse_mismatch")

        existing_links = list(
            db.execute(
                select(GlhsTransitionPartitionLink)
                .where(GlhsTransitionPartitionLink.transition_id == existing.id)
                .order_by(GlhsTransitionPartitionLink.id)
            ).scalars()
        )
        return GlhsCommitResult(
            applied_transition=existing,
            partition_links=existing_links,
            mutation_result=None,
            idempotent_replay=True,
            transition_status=existing.transition_status,
        )

    # Normalize or load dependencies
    resolved_deps: list[DependencySpec] = []
    if dependencies is not None:
        resolved_deps = [
            _normalize_dependency(d, default_domain=policy_domain) for d in dependencies
        ]
    elif proposal_id is not None:
        db_deps = db.execute(
            select(GlhsProposalDependency)
            .where(GlhsProposalDependency.proposal_id == proposal_id)
            .order_by(
                GlhsProposalDependency.dependency_kind,
                GlhsProposalDependency.dependency_key,
            )
        ).scalars().all()
        resolved_deps = [_normalize_dependency(d, default_domain=policy_domain) for d in db_deps]

    # Collect entity partition coordinates for locking
    partition_coords: set[tuple[str, str]] = set()
    write_coords: set[tuple[str, str]] = set()

    for dep in resolved_deps:
        if dep.dependency_kind == "ENTITY":
            coord = parse_entity_partition_key(
                dep.dependency_key, default_domain=policy_domain
            )
            partition_coords.add(coord)
            if dep.access_mode == "WRITE":
                write_coords.add(coord)

    if write_partitions:
        for wp in write_partitions:
            if isinstance(wp, (tuple, list)) and len(wp) == 2:
                coord = (str(wp[0]).strip(), str(wp[1]).strip())
                partition_coords.add(coord)
                write_coords.add(coord)

    sorted_partition_coords = sorted(partition_coords, key=lambda c: (c[0], c[1]))

    # =========================================================================
    # Phase 2: Canonical lock acquisition
    # =========================================================================
    # 2.1: Policy Lock Anchor (Shared)
    acquire_policy_lock_anchor(db, policy_domain=policy_domain, mode=LockMode.SHARED)

    # 2.2: Profile & Consent Lock Anchor (Shared)
    base_state_version, owner_user_id = acquire_profile_and_consent_anchor(
        db, profile_id=profile_id, exclusive=False
    )

    # 2.3: Re-check idempotency under locks
    existing_locked = db.execute(
        select(GlhsAppliedTransition).where(
            GlhsAppliedTransition.tenant_id == tenant_id,
            GlhsAppliedTransition.operation_kind == operation_kind,
            GlhsAppliedTransition.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()

    if existing_locked is None and proposal_id is not None and proposal_id > 0 and operation_kind == "COMMIT_PROPOSAL":
        existing_locked = db.execute(
            select(GlhsAppliedTransition).where(
                GlhsAppliedTransition.proposal_id == proposal_id
            )
        ).scalar_one_or_none()

    if existing_locked is not None:
        if (
            request_digest
            and existing_locked.request_digest
            and existing_locked.request_digest != request_digest
        ):
            raise GlhsInvariantError("idempotency_key_reused: idempotency_key_reuse_mismatch")

        existing_links = list(
            db.execute(
                select(GlhsTransitionPartitionLink)
                .where(GlhsTransitionPartitionLink.transition_id == existing_locked.id)
                .order_by(GlhsTransitionPartitionLink.id)
            ).scalars()
        )
        return GlhsCommitResult(
            applied_transition=existing_locked,
            partition_links=existing_links,
            mutation_result=None,
            idempotent_replay=True,
            transition_status=existing_locked.transition_status,
        )

    # 2.4: Read current effective policy epoch and consent version under locks
    from clara_api.glhs.gateway import (
        _effective_policy_version,
        _governed_consent_version,
    )

    current_policy_version = _effective_policy_version(
        db, for_update=False, policy_domain=policy_domain
    )
    current_consent_version = _governed_consent_version(
        db, owner_user_id=owner_user_id, purpose=purpose, for_update=False
    )

    # 2.5: Lock entity partitions in canonical lexicographical order
    locked_partitions_list: list[GlhsEntityVersionPartition] = []
    if sorted_partition_coords:
        locked_partitions_list = lock_entity_partitions(
            db,
            profile_id=profile_id,
            partitions=sorted_partition_coords,
            policy_version=current_policy_version,
            consent_version=current_consent_version,
        )

    locked_map = {
        (p.domain, p.semantic_key): p for p in locked_partitions_list
    }

    # =========================================================================
    # Phase 3: Freshness & per-partition dependency revalidation under locks
    # =========================================================================
    if expected_base_state_version is not None and expected_base_state_version != base_state_version:
        raise GlhsInvariantError("stale_base_state_version")

    if expected_policy_version is not None and expected_policy_version != current_policy_version:
        raise GlhsInvariantError(
            f"stale_policy_version: expected {expected_policy_version}, got {current_policy_version}"
        )

    if expected_consent_version is not None and expected_consent_version != current_consent_version:
        raise GlhsInvariantError(
            f"stale_consent_version: expected {expected_consent_version}, got {current_consent_version}"
        )

    for dep in resolved_deps:
        if dep.dependency_kind == "ENTITY":
            coord = parse_entity_partition_key(
                dep.dependency_key, default_domain=policy_domain
            )
            part = locked_map.get(coord)
            if part is None:
                raise GlhsInvariantError(f"missing_entity_partition: {coord[0]}:{coord[1]}")
            if part.state_version != dep.observed_version:
                raise GlhsInvariantError(
                    f"stale_entity_partition: {dep.dependency_key} observed {dep.observed_version} != current {part.state_version}"
                )
            if dep.observed_digest and hasattr(part, "state_digest"):
                part_digest = getattr(part, "state_digest", None)
                if part_digest and part_digest != dep.observed_digest:
                    raise GlhsInvariantError(
                        f"stale_entity_digest: {dep.dependency_key} observed digest mismatch"
                    )

        elif dep.dependency_kind == "GOVERNANCE":
            key_lower = dep.dependency_key.lower()
            if "policy" in key_lower:
                from clara_api.glhs.gateway import read_current_policy_epoch
                epoch = read_current_policy_epoch(db, policy_domain=policy_domain)
                if epoch is not None:
                    if dep.observed_digest and dep.observed_digest != epoch.version:
                        raise GlhsInvariantError(
                            f"stale_governance_policy: observed {dep.observed_digest} != current {epoch.version}"
                        )
                else:
                    if (
                        dep.observed_digest
                        and dep.observed_digest not in ("glhs.v1", "commitloop.v1", current_policy_version)
                    ):
                        raise GlhsInvariantError(
                            f"stale_governance_policy: observed {dep.observed_digest} != current {current_policy_version}"
                        )
            elif "consent" in key_lower:
                if dep.observed_digest and dep.observed_digest != current_consent_version:
                    raise GlhsInvariantError(
                        f"stale_governance_consent: observed {dep.observed_digest} != current {current_consent_version}"
                    )

    # =========================================================================
    # Phase 4: Domain mutation callback execution
    # =========================================================================
    commit_context = GlhsCommitContext(
        db=db,
        profile_id=profile_id,
        owner_user_id=owner_user_id,
        base_state_version=base_state_version,
        effective_policy_version=current_policy_version,
        effective_consent_version=current_consent_version,
        locked_partitions=locked_map,
        dependencies=resolved_deps,
        tenant_id=tenant_id,
        operation_kind=operation_kind,
        idempotency_key=idempotency_key,
        proposal_id=proposal_id,
        custom_payload=custom_payload,
    )

    mutation_result: Any = None
    if mutation_callback is not None:
        mutation_result = mutation_callback(commit_context)

    # =========================================================================
    # Phase 5: CAS-increment only WRITE partitions & record partition links
    # =========================================================================
    now = datetime.now(UTC)
    write_partition_specs: list[dict[str, Any]] = []
    sorted_write_coords = sorted(write_coords, key=lambda c: (c[0], c[1]))

    # Map entity dependencies to get predecessor_digest if available
    dep_digest_map: dict[tuple[str, str], str | None] = {}
    for dep in resolved_deps:
        if dep.dependency_kind == "ENTITY":
            coord = parse_entity_partition_key(
                dep.dependency_key, default_domain=policy_domain
            )
            dep_digest_map[coord] = dep.observed_digest

    for domain, semantic_key in sorted_write_coords:
        part = locked_map.get((domain, semantic_key))
        if part is None:
            raise GlhsInvariantError(f"write_partition_not_found: {domain}:{semantic_key}")

        predecessor_version = part.state_version
        successor_version = predecessor_version + 1

        # CAS progression: update partition row
        part.state_version = successor_version
        part.policy_version = current_policy_version
        part.consent_version = current_consent_version
        part.updated_at = now

        predecessor_digest = dep_digest_map.get((domain, semantic_key))
        write_digest = fast_canonical_digest(
            {
                "domain": domain,
                "predecessor_version": predecessor_version,
                "semantic_key": semantic_key,
                "successor_version": successor_version,
            },
            profile=canonicalization_profile,
        )
        successor_digest = fast_canonical_digest(
            {
                "domain": domain,
                "semantic_key": semantic_key,
                "version": successor_version,
                "write_digest": write_digest,
            },
            profile=canonicalization_profile,
        )

        write_partition_specs.append(
            {
                "partition": part,
                "predecessor_version": predecessor_version,
                "successor_version": successor_version,
                "predecessor_digest": predecessor_digest,
                "successor_digest": successor_digest,
                "write_digest": write_digest,
            }
        )

    # =========================================================================
    # Phase 6: Insert GlhsAppliedTransition record and transactional outbox event
    # =========================================================================
    dep_vector_digest = compute_dependency_vector_digest(
        resolved_deps, profile=canonicalization_profile
    )

    if mutation_result is not None:
        if hasattr(mutation_result, "public_id"):
            digest_target: Any = {
                "id": str(mutation_result.public_id),
                "type": mutation_result.__class__.__name__,
            }
        elif hasattr(mutation_result, "__table__"):
            digest_target = {
                c.name: getattr(mutation_result, c.name)
                for c in mutation_result.__table__.columns
                if hasattr(mutation_result, c.name)
            }
        else:
            digest_target = mutation_result
        try:
            result_digest = fast_canonical_digest(
                digest_target, profile=canonicalization_profile
            )
        except Exception:
            result_digest = fast_canonical_digest(
                str(mutation_result), profile=canonicalization_profile
            )
    else:
        result_digest = ""

    applied_transition = GlhsAppliedTransition(
        public_id=uuid4().hex,
        profile_id=profile_id,
        tenant_id=tenant_id,
        proposal_id=proposal_id,
        operation_kind=operation_kind,
        idempotency_key=idempotency_key,
        transition_status="COMMITTED",
        request_digest=request_digest or "",
        result_digest=result_digest,
        dependency_vector_digest=dep_vector_digest,
        disclosure_digest=disclosure_digest or "",
        audit_event_id=audit_event_id,
        committed_at=now,
        recorded_at=now,
    )
    db.add(applied_transition)
    db.flush()

    created_links: list[GlhsTransitionPartitionLink] = []
    for spec in write_partition_specs:
        link = GlhsTransitionPartitionLink(
            public_id=uuid4().hex,
            transition_id=applied_transition.id,
            partition_id=spec["partition"].id,
            predecessor_version=spec["predecessor_version"],
            successor_version=spec["successor_version"],
            predecessor_digest=spec["predecessor_digest"],
            successor_digest=spec["successor_digest"],
            write_digest=spec["write_digest"],
            recorded_at=now,
        )
        db.add(link)
        created_links.append(link)

    db.flush()

    # Transactional outbox event
    outbox_event_id = fast_canonical_digest(
        {
            "idempotency_key": idempotency_key,
            "kind": event_type or "glhs.transition.applied",
            "proposal_id": proposal_id,
            "transition_id": applied_transition.public_id,
        },
        profile=canonicalization_profile,
    )
    add_outbox(
        db,
        event_id=outbox_event_id,
        profile_id=profile_id,
        aggregate_type=aggregate_type or "glhs_transition",
        aggregate_public_id=aggregate_public_id or applied_transition.public_id,
        event_type=event_type or "glhs.transition.applied",
    )
    db.flush()

    return GlhsCommitResult(
        applied_transition=applied_transition,
        partition_links=created_links,
        mutation_result=mutation_result,
        idempotent_replay=False,
        transition_status="COMMITTED",
    )
