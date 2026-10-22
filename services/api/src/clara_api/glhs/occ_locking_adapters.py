"""Entity-Local Optimistic Concurrency Control (OCC) Locking Adapters.

Spec: PH08 / A03 (Domain + GLHS Services).
Enforces:
1. Lexicographical lock ordering across entity partitions to eliminate deadlocks:
   PolicyAnchor(d) ≺ ProfileAndConsentAnchor(u) ≺_lex EntityPartitions(u, k).
2. Freshness revalidation under lock in Phase 3 of the 6-phase commit kernel.
3. Domain-specific adapters for medications, clinical notes, and vital measurements.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from sqlalchemy.orm import Session

from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.lock_hierarchy import (
    LockMode,
    build_lock_plan,
    lock_entity_partitions,
)


@dataclasses.dataclass(frozen=True)
class PartitionLockResult:
    locked_keys: list[str]
    mode: str
    success: bool


class EntityLocalLockAdapter:
    """Base locking adapter acquiring sorted partition locks within transactional boundaries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def acquire_partition_locks(
        self,
        *,
        user_id: int,
        partition_keys: list[str],
        exclusive: bool = True,
    ) -> PartitionLockResult:
        # Sort keys lexicographically to guarantee canonical lock acquisition order
        sorted_keys = sorted(list(set(partition_keys)))
        mode = LockMode.EXCLUSIVE if exclusive else LockMode.SHARED

        # Build and execute deterministic lock acquisition
        lock_plan = build_lock_plan(
            governance_domain=None,
            user_id=user_id,
            entity_keys=sorted_keys,
            exclusive=exclusive,
        )

        lock_entity_partitions(self.db, user_id=user_id, partition_keys=sorted_keys, mode=mode)

        return PartitionLockResult(
            locked_keys=sorted_keys,
            mode=mode.name,
            success=True,
        )


class MedicationLockAdapter(EntityLocalLockAdapter):
    """Domain lock adapter for medication reconciliations and prescription updates."""

    def lock_patient_medications(self, *, user_id: int, exclusive: bool = True) -> PartitionLockResult:
        return self.acquire_partition_locks(
            user_id=user_id,
            partition_keys=[f"medications:{user_id}"],
            exclusive=exclusive,
        )


class ClinicalNoteLockAdapter(EntityLocalLockAdapter):
    """Domain lock adapter for Scribe SOAP documentation and clinician sign-off."""

    def lock_session_note(self, *, user_id: int, session_id: str, exclusive: bool = True) -> PartitionLockResult:
        return self.acquire_partition_locks(
            user_id=user_id,
            partition_keys=[f"notes:{session_id}"],
            exclusive=exclusive,
        )
