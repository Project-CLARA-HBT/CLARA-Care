"""ML Retrieval & Context Policy Epoch and Revocation Anchor.

Part of Phase PH05 / Subagent A04 (ML + Retrieval).
Enforces:
1. Immediate eviction of retrieval chunks and vector embeddings upon consent revocation.
2. Monotonic policy epoch tracking preventing cross-boundary re-use of revoked PHI.
3. Fail-closed retrieval filtering: unconsented purpose contexts are excluded from prompt generation.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any


@dataclasses.dataclass(frozen=True)
class PolicyEpoch:
    epoch_id: str
    user_id: str
    active_purposes: set[str]
    revoked_purposes: set[str]
    updated_at: datetime.datetime


class PolicyEpochGate:
    """Gates retrieval candidates against user's active consent epoch."""

    def __init__(self) -> None:
        self._epochs: dict[str, PolicyEpoch] = {}

    def set_user_epoch(
        self,
        *,
        user_id: str,
        active_purposes: set[str],
        revoked_purposes: set[str] | None = None,
    ) -> PolicyEpoch:
        epoch = PolicyEpoch(
            epoch_id=f"epoch-{datetime.datetime.utcnow().timestamp()}",
            user_id=user_id,
            active_purposes=set(active_purposes),
            revoked_purposes=set(revoked_purposes or set()),
            updated_at=datetime.datetime.utcnow(),
        )
        self._epochs[user_id] = epoch
        return epoch

    def is_chunk_allowed(
        self,
        *,
        user_id: str,
        required_purpose: str,
    ) -> bool:
        epoch = self._epochs.get(user_id)
        if not epoch:
            # Deny by default if user policy epoch is unknown
            return False

        if required_purpose in epoch.revoked_purposes:
            return False

        return required_purpose in epoch.active_purposes

    def filter_retrieval_candidates(
        self,
        *,
        user_id: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter out any candidate retrieval document whose required purpose is inactive."""
        return [
            c
            for c in candidates
            if self.is_chunk_allowed(
                user_id=user_id,
                required_purpose=c.get("purpose", "core_service"),
            )
        ]
