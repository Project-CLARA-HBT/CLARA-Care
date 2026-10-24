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
        profile_id: int,
        partition_keys: list[str],
        exclusive: bool = True,
        user_id: int | None = None,
    ) -> PartitionLockResult:
        parsed_tuples: list[tuple[str, str]] = []
        for k in partition_keys:
            if ":" in k:
                d, s = k.split(":", 1)
                parsed_tuples.append((d, s))
            else:
                parsed_tuples.append(("general", k))

        sorted_tuples = sorted(list(set(parsed_tuples)), key=lambda item: (item[0], item[1]))
        lock_entity_partitions(
            self.db,
            profile_id=profile_id,
            partitions=sorted_tuples,
            read_only=not exclusive,
        )

        return PartitionLockResult(
            locked_keys=[f"{d}:{k}" for d, k in sorted_tuples],
            mode="EXCLUSIVE" if exclusive else "SHARED",
            success=True,
        )


class MedicationLockAdapter(EntityLocalLockAdapter):
    """Domain lock adapter for medication reconciliations and prescription updates."""

    def lock_patient_medications(
        self,
        *,
        profile_id: int | None = None,
        user_id: int | None = None,
        exclusive: bool = True,
    ) -> PartitionLockResult:
        pid = profile_id if profile_id is not None else (user_id or 1)
        return self.acquire_partition_locks(
            profile_id=pid,
            partition_keys=[f"medications:{pid}"],
            exclusive=exclusive,
            user_id=user_id,
        )


class ClinicalNoteLockAdapter(EntityLocalLockAdapter):
    """Domain lock adapter for Scribe SOAP documentation and clinician sign-off."""

    def lock_session_note(
        self,
        *,
        session_id: str,
        profile_id: int | None = None,
        user_id: int | None = None,
        exclusive: bool = True,
    ) -> PartitionLockResult:
        pid = profile_id if profile_id is not None else (user_id or 1)
        return self.acquire_partition_locks(
            profile_id=pid,
            partition_keys=[f"notes:{session_id}"],
            exclusive=exclusive,
            user_id=user_id,
        )


class LifeMapCaptureLockAdapter(EntityLocalLockAdapter):
    """Domain lock adapter for LifeMap Universal Capture candidate extraction and OCC conflict resolution.

    Acquires entity partition locks in canonical lexicographical order:
    - `capture_session:<session_id>`
    - `lifemap_timeline:<profile_id>`
    - `glhs_continuity:<profile_id>`
    """

    def lock_capture_extraction(
        self,
        *,
        profile_id: int,
        session_id: str,
        user_id: int | None = None,
        exclusive: bool = True,
    ) -> PartitionLockResult:
        keys = [
            f"capture_session:{session_id}",
            f"glhs_continuity:{profile_id}",
            f"lifemap_timeline:{profile_id}",
        ]
        return self.acquire_partition_locks(
            profile_id=profile_id,
            partition_keys=keys,
            exclusive=exclusive,
            user_id=user_id,
        )

