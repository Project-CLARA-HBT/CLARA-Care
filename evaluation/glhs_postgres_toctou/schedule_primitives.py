"""Shared non-development schedule primitives for the W4 GLHS concurrency v2 workstream.

These primitives form the public vocabulary shared by the persisted governance
writers (``governance_writers``), the v2 observer (``observer_v2``) and the v2
validator (``validate_v2``). They are extracted conceptually from the v1
``development_probe`` but never import its private helpers, and they never open
a database connection: sessions and transactions are duck-typed handles that
callers inject. There is no global mutable state in this module.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4


def now_monotonic_ns() -> int:
    """Return the current monotonic timestamp in nanoseconds."""
    return time.monotonic_ns()


def elapsed_ms(start_ns: int, end_ns: int | None = None) -> float:
    """Return the monotonic wall-clock duration between two stamps in ms."""
    end = now_monotonic_ns() if end_ns is None else end_ns
    return round((end - start_ns) / 1_000_000.0, 3)


def sha256_hex(value: str) -> str:
    """Return the lowercase SHA-256 hex digest of ``value``."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_idempotency_key(prefix: str) -> str:
    """Return a random, process-unique idempotency key with a stable prefix."""
    return f"{prefix}:{uuid4().hex}"


def snapshot_binding_digest(snapshot: object) -> tuple[str, str]:
    """Require the reviewed manifest-digest binding contract, without fallback.

    Conceptually equivalent to the v1 development probe's binding contract: only
    a non-empty string ``manifest_digest`` on the snapshot is accepted. No legacy
    or alternative binding field is allowed.
    """
    manifest_digest = getattr(snapshot, "manifest_digest", None)
    if isinstance(manifest_digest, str) and manifest_digest:
        return manifest_digest, "manifest_digest"
    raise ValueError("snapshot_manifest_digest_contract_unavailable")


def classify_concurrent_commit_order(
    *,
    outcome: str,
    revoke_commit_ns: object,
    commit_start_ns: object,
    commit_complete_ns: object,
) -> tuple[str, bool | None]:
    """Classify a consent-revocation vs transition-commit race.

    Only ordering facts the driver actually observed are used. A completed
    revoke observed before the commit started proves the attempted commit is
    post-revocation; a successful transition there is forbidden, never
    indeterminate. Overlapping windows stay indeterminate.
    """
    observed_revoke_before_commit_start = (
        isinstance(revoke_commit_ns, int)
        and isinstance(commit_start_ns, int)
        and revoke_commit_ns < commit_start_ns
    )
    if outcome != "transition_committed":
        return (
            "rejected_after_observed_revoke_commit"
            if observed_revoke_before_commit_start
            else "rejected_during_or_before_governance_race",
            False,
        )
    if observed_revoke_before_commit_start:
        return "forbidden_transition_committed_after_observed_revoke", True
    if (
        isinstance(revoke_commit_ns, int)
        and isinstance(commit_complete_ns, int)
        and commit_complete_ns < revoke_commit_ns
    ):
        return "transition_committed_before_observed_revoke_commit", False
    return "indeterminate_ordering_transition_committed", None


def classify_proposal_order(
    *,
    outcome: str,
    revoke_commit_ns: object,
    proposal_complete_ns: object,
) -> tuple[str, bool | None]:
    """Classify a consent-revocation vs proposal-writer race.

    A proposal that completed before the observed revocation commit is
    admissible; anything else that committed stays indeterminate.
    """
    if outcome != "proposal_committed":
        return "rejected_after_or_during_governance_race", False
    if (
        isinstance(revoke_commit_ns, int)
        and isinstance(proposal_complete_ns, int)
        and proposal_complete_ns < revoke_commit_ns
    ):
        return "proposal_committed_before_observed_revoke_commit", False
    return "indeterminate_ordering_proposal_committed", None


class SessionLike(Protocol):
    """Duck-typed database session/transaction handle required by the writers.

    ``add``/``flush``/``commit``/``rollback`` form the write path; ``get`` and
    ``scalar`` back the load steps when a loader is not supplied. A caller may
    also expose a domain loader (e.g. ``load_consent_target``) directly on the
    session.
    """

    def add(self, instance: object) -> None: ...
    def flush(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def get(self, model: type, ident: object) -> object | None: ...
    def scalar(self, statement: object) -> object: ...


class BarrierLike(Protocol):
    """Minimal barrier interface consumed by the governance writers."""

    def wait(self, phase: str = "release") -> int: ...
    @property
    def broken(self) -> bool: ...
    def reset(self) -> None: ...


@dataclass(frozen=True)
class TraceEvent:
    """A begin/commit/rollback boundary with a monotonic timestamp."""

    event: str
    monotonic_ns: int
    backend_pid: int | None
    txid: int | None


@dataclass(frozen=True)
class LockWait:
    """A lock acquisition attempt and its observed wait duration."""

    lock: str
    waited_ns: int
    acquired: bool


def _backend_pid(session: object | None) -> int | None:
    if session is None:
        return None
    value = getattr(session, "backend_pid", None)
    return value if isinstance(value, int) else None


def _txid(session: object | None) -> int | None:
    if session is None:
        return None
    value = getattr(session, "txid", None)
    return value if isinstance(value, int) else None


class TransactionTrace:
    """Per-schedule transaction trace collector (a caller-owned handle).

    Records begin/commit/rollback events plus lock-wait observations with
    monotonic timestamps. Backend pid and transaction id are captured from the
    duck-typed session when it exposes them, otherwise they are ``None``. No
    global state is mutated.
    """

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._lock_waits: list[LockWait] = []

    def begin(self, session: object | None = None) -> None:
        self._events.append(
            TraceEvent("begin", now_monotonic_ns(), _backend_pid(session), _txid(session))
        )

    def commit(self, session: object | None = None) -> None:
        self._events.append(
            TraceEvent("commit", now_monotonic_ns(), _backend_pid(session), _txid(session))
        )

    def rollback(self, session: object | None = None) -> None:
        self._events.append(
            TraceEvent("rollback", now_monotonic_ns(), _backend_pid(session), _txid(session))
        )

    def lock_wait(self, *, lock: str, waited_ns: int, acquired: bool) -> None:
        self._lock_waits.append(LockWait(lock, waited_ns, acquired))

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    @property
    def lock_waits(self) -> tuple[LockWait, ...]:
        return tuple(self._lock_waits)

    def to_dict(self) -> dict[str, object]:
        return {
            "events": [
                {
                    "event": event.event,
                    "monotonic_ns": event.monotonic_ns,
                    "backend_pid": event.backend_pid,
                    "txid": event.txid,
                }
                for event in self._events
            ],
            "lock_waits": [
                {"lock": wait.lock, "waited_ns": wait.waited_ns, "acquired": wait.acquired}
                for wait in self._lock_waits
            ],
        }
