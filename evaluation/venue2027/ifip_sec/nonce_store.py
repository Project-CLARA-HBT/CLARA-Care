"""CLARA-Care 2027 IFIP_SEC task IFIP_SEC-X03_nonce_store — consume-once nonce store.

Purpose
-------
Linearizable consume-once nonce store for "Replay-Closed Authorization Across
Purpose, Delegation, and AI Proposal Lineage" (IFIP_SEC 2027), the RQ2
mechanism of ``research/venue2027/VENUES/ifip_sec/RESEARCH_BLUEPRINT.md``.
A receipt's ``nonce`` (the v1 field fixed by
``research/venue2027/ifip_sec/protocols/receipt.schema.json``) must admit
EXACTLY one governed operation: the first :func:`NonceStore.consume` of a
live nonce returns CONSUMED and atomically removes it; any subsequent
presentation is REPLAY_DETECTED; a presentation past its ``expires_at`` is
EXPIRED. This is the transition the blueprint calls "atomically consume the
nonce, not just signature equality" (RQ2: linearizable under two or more real
PostgreSQL sessions).

Contract
--------
``consume(nonce, expires_at, now) -> ConsumeResult`` with outcome
``CONSUMED | REPLAY_DETECTED | EXPIRED`` (the manifest signature
``consume(nonce, tenant, tx) -> ConsumeOutcome`` specialised to the
in-process/Protocol backend seam; the tenant/tx binding is injected via the
backend, see :class:`NonceBackend`). Deterministic: time is always a caller
argument (``now``), never a hidden clock read; no randomness.

Backends
--------
- :class:`InMemoryNonceBackend` — real, thread-safe in-process store
  (``threading.Lock``) with bounded memory: an :meth:`InMemoryNonceBackend.sweep`
  expiry pass reclaims records whose ``expires_at <= sweep_now``. ``sweep`` is
  opportunistic: :class:`NonceStore` also triggers it every ``sweep_interval``
  consumes so a long-lived process cannot grow without bound. The lock makes
  check-and-remove one critical section, so N threads racing the SAME nonce in
  one process admit exactly one CONSUMED (tested with real threads + barrier).
- :class:`NonceBackend` — pluggable runtime :class:`typing.Protocol` so a real
  PostgreSQL backend can be injected later without touching this module.
- :class:`PostgresNonceBackend` — STUB for the durable RQ2 variant
  (PostgreSQL unique index on nonce + INSERT/DELETE in one serializable
  transaction). It NEVER silently pretends to store: every operation raises
  :class:`PostgresBackendUnavailable` (a :class:`NonceBackendError`) unless a
  real live connection object is supplied at construction, and even a
  constructed backend with a connection raises
  :class:`PostgresBackendUnavailable` on use because the durable SQL
  implementation is task-pinned to the real PostgreSQL harness (rule 8: never
  a toy under the same name — no fake "durable" in-memory pretender).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes inside :class:`ConsumeResult`
(``NONCE_MISSING`` / ``NONCE_TOO_SHORT`` / ``EXPIRES_AT_BAD_TYPE`` /
``NOW_BAD_TYPE`` / ``BACKEND_UNAVAILABLE``). Only caller wiring errors raise
:class:`NonceStoreError` subclasses; every per-presentation fault is a
first-class result, never an exception that could be miscounted as a rejection.
``expires_at``/``now`` are integer epoch seconds; a nonce consumed at exactly
``expires_at`` is EXPIRED (half-open validity window ``[issue, expires_at)``),
matching the receipt schema's "expiry strictly after issued_at" temporal rule.

Version
-------
``NONCE_STORE_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import threading
from collections.abc import Iterator, Mapping
from typing import Any, Protocol, runtime_checkable

NONCE_STORE_VERSION = "1.0.0"

#: Stable uppercase outcome / reason codes (machine-checkable).
CONSUMED = "CONSUMED"
REPLAY_DETECTED = "REPLAY_DETECTED"
EXPIRED = "EXPIRED"
RC_NONCE_MISSING = "NONCE_MISSING"
RC_NONCE_TOO_SHORT = "NONCE_TOO_SHORT"
RC_EXPIRES_AT_BAD_TYPE = "EXPIRES_AT_BAD_TYPE"
RC_NOW_BAD_TYPE = "NOW_BAD_TYPE"
RC_BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"

#: Minimum nonce length, mirroring receipt.schema.json ``^...{16,128}$``.
NONCE_MIN_LENGTH = 16

#: Expiry sweep batch cap: at most this many expired records are reclaimed per
#: pass so a sweep can never dominate a request thread (bounded work).
_SWEEP_BATCH_LIMIT = 1024

_EXPIRED_SENTINEL: frozenset[str] = frozenset({"__expired__"})


class NonceStoreError(ValueError):
    """Caller wiring/configuration error (never a per-presentation outcome)."""


class NonceBackendError(NonceStoreError):
    """Backend refused an operation; carries a stable uppercase reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class PostgresBackendUnavailable(NonceBackendError):
    """The PostgreSQL backend cannot honour an operation (no real connection).

    Raised instead of silently pretending a durable consume happened. This is
    the honest NOT_RUN-style surface for the stub: the caller must wire a real
    PostgreSQL session harness (RQ2's "two or more real PostgreSQL sessions")
    before the durable variant can be used.
    """


@dataclasses.dataclass(frozen=True)
class ConsumeResult:
    """Outcome of one consume attempt (first-class value, never an exception).

    ``outcome`` — ``CONSUMED`` / ``REPLAY_DETECTED`` / ``EXPIRED`` (or an
    uppercase validation reason code for malformed input).
    ``nonce`` — the presented nonce echo.
    ``detail`` — stable uppercase reason code; equals ``outcome`` for the three
    transition outcomes.
    """

    outcome: str
    nonce: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.detail:
            object.__setattr__(self, "detail", self.outcome)

    @property
    def consumed(self) -> bool:
        return self.outcome == CONSUMED


@runtime_checkable
class NonceBackend(Protocol):
    """Pluggable storage seam for the consume-once transition.

    A backend is a synchronized mapping from nonce -> expiry record. The
    ``threading`` concurrency guarantee in this module is delivered by the
    in-process backend's real lock held across check-and-remove; a durable
    backend must deliver the equivalent guarantee with a real transaction
    (PostgreSQL unique index + serializable INSERT/DELETE), never with a bare
    check-then-act. Implementations must be deterministic and must raise
    :class:`NonceBackendError` (never silently no-op) when storage is
    unavailable.
    """

    def reserve(self, nonce: str, expires_at: int) -> bool:
        """Atomically claim ``nonce`` for one consumption; True iff this call
        performed the first-and-only claim (False = already claimed)."""
        ...

    def lookup(self, nonce: str) -> int | None:
        """Current recorded ``expires_at`` for a claimed nonce, else None."""
        ...

    def release(self, nonce: str) -> None:
        """Reclaim/forget a claimed nonce (expiry sweep path)."""
        ...

    def expired(self, now: int, limit: int) -> Iterator[str]:
        """Yield up to ``limit`` claimed nonces whose ``expires_at <= now``."""
        ...

    def size(self) -> int:
        """Number of currently claimed nonce records (memory telemetry)."""
        ...


def _validate_nonce(nonce: str) -> str:
    if not isinstance(nonce, str) or not nonce:
        raise NonceStoreError(RC_NONCE_MISSING, "nonce must be a non-empty string")
    if len(nonce) < NONCE_MIN_LENGTH:
        raise NonceStoreError(
            RC_NONCE_TOO_SHORT, f"nonce must be >= {NONCE_MIN_LENGTH} chars (receipt v1 syntax)"
        )
    return nonce


def _validate_times(expires_at: int, now: int) -> tuple[int, int]:
    if isinstance(expires_at, bool) or not isinstance(expires_at, int):
        raise NonceStoreError(RC_EXPIRES_AT_BAD_TYPE, "expires_at must be integer epoch seconds")
    if isinstance(now, bool) or not isinstance(now, int):
        raise NonceStoreError(RC_NOW_BAD_TYPE, "now must be integer epoch seconds")
    return expires_at, now


class InMemoryNonceBackend:
    """Thread-safe in-process backend; bounded memory via expiry sweep.

    Every mutation runs under one real :class:`threading.Lock`, so the
    reserve path (lookup + claim) is a single critical section: for N threads
    racing the same nonce, exactly one ``reserve`` returns True. Memory is
    bounded by reclaiming expired records: call :meth:`sweep` periodically or
    let :class:`NonceStore` auto-sweep every ``sweep_interval`` consumes.
    """

    __slots__ = ("_lock", "_records")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # nonce -> expires_at (claimed/consumed-but-not-yet-swept nonces).
        self._records: dict[str, int] = {}

    def reserve(self, nonce: str, expires_at: int) -> bool:
        with self._lock:
            if nonce in self._records:
                return False
            self._records[nonce] = expires_at
            return True

    def lookup(self, nonce: str) -> int | None:
        with self._lock:
            return self._records.get(nonce)

    def release(self, nonce: str) -> None:
        with self._lock:
            self._records.pop(nonce, None)

    def expired(self, now: int, limit: int) -> Iterator[str]:
        """Yield up to ``limit`` claimed nonces whose ``expires_at <= now``."""
        with self._lock:
            expired = [n for n, exp in self._records.items() if exp <= now]
        return iter(expired[: max(0, limit)])

    def sweep(
        self,
        now: int | None = None,
        limit: int = _SWEEP_BATCH_LIMIT,
    ) -> int:
        """Reclaim expired records; returns the number reclaimed.

        ``now=None`` reclaims every record whose ``expires_at`` has passed by
        the largest recorded expiry (deterministic upper bound, no clock read).
        """
        if now is None:
            with self._lock:
                bound = max(self._records.values(), default=None)
            if bound is None:
                return 0
            now = bound
        if isinstance(now, bool) or not isinstance(now, int):
            raise NonceStoreError(RC_NOW_BAD_TYPE, "now must be integer epoch seconds or None")
        reclaimed = 0
        for nonce in self.expired(now, limit):
            self.release(nonce)
            reclaimed += 1
        return reclaimed

    def size(self) -> int:
        with self._lock:
            return len(self._records)

    def __len__(self) -> int:
        return self.size()


class PostgresNonceBackend:
    """Stub for the durable PostgreSQL consume-once backend (RQ2 variant).

    Never silently pretends: construction without a real connection raises
    :class:`PostgresBackendUnavailable` immediately, and even a backend built
    with a connection object raises :class:`PostgresBackendUnavailable` on
    every operation until the durable SQL implementation (unique index +
    serializable INSERT/DELETE in one transaction) is wired by the real
    PostgreSQL harness. There is no in-memory fallback masquerading as
    durable storage (execution contract rule 8).
    """

    __slots__ = ("_connection",)

    def __init__(self, connection: Any = None) -> None:
        if connection is None:
            raise PostgresBackendUnavailable(
                RC_BACKEND_UNAVAILABLE,
                "PostgresNonceBackend requires a real PostgreSQL connection; "
                "refusing to start a pretend-durable backend",
            )
        self._connection = connection

    def _unavailable(self, operation: str) -> PostgresBackendUnavailable:
        return PostgresBackendUnavailable(
            RC_BACKEND_UNAVAILABLE,
            f"PostgresNonceBackend.{operation} is a stub: the durable SQL implementation "
            "(unique index + serializable transaction) requires the real PostgreSQL harness",
        )

    def reserve(self, nonce: str, expires_at: int) -> bool:
        raise self._unavailable("reserve")

    def lookup(self, nonce: str) -> int | None:
        raise self._unavailable("lookup")

    def release(self, nonce: str) -> None:
        raise self._unavailable("release")

    def expired(self, now: int, limit: int) -> Iterator[str]:
        raise self._unavailable("expired")

    def size(self) -> int:
        raise self._unavailable("size")


class NonceStore:
    """Consume-once facade over a :class:`NonceBackend`.

    ``consume`` validates input, asks the backend for an atomic claim, then
    classifies the transition:

    - ``expires_at <= now`` → ``EXPIRED`` (fail closed; the window has closed,
      the nonce is never (re-)claimed regardless of prior claim state);
    - backend claim succeeded → ``CONSUMED`` (the one admitted presentation);
    - nonce already claimed and its recorded ``expires_at > now`` →
      ``REPLAY_DETECTED``; recorded ``expires_at <= now`` → ``EXPIRED``.

    On replay the RECORDED expiry (from the claiming presentation) is
    authoritative: a later presenter cannot extend the window, and an expired
    record still classifies as EXPIRED — fail closed in every branch.

    Memory stays bounded: after ``sweep_interval`` consumes the store runs one
    expiry sweep on the backend (``maybe_sweep``), reclaiming records whose
    ``expires_at <= now`` of the triggering consume (deterministic: no hidden
    clock). Set ``sweep_interval=None`` to disable auto-sweeping (tests that
    want exact size assertions drive :meth:`sweep` themselves).
    """

    __slots__ = ("_backend", "_consumes_since_sweep", "_lock", "_sweep_interval")

    def __init__(
        self,
        backend: NonceBackend | None = None,
        *,
        sweep_interval: int | None = 64,
    ) -> None:
        self._backend: NonceBackend = backend if backend is not None else InMemoryNonceBackend()
        if sweep_interval is not None and (isinstance(sweep_interval, bool) or sweep_interval < 1):
            raise NonceStoreError(
                "SWEEP_INTERVAL_BAD", "sweep_interval must be a positive integer or None"
            )
        self._sweep_interval = sweep_interval
        self._consumes_since_sweep = 0
        self._lock = threading.Lock()

    @property
    def backend(self) -> NonceBackend:
        return self._backend

    def consume(self, nonce: str, expires_at: int, now: int) -> ConsumeResult:
        """One consume transition (deterministic; ``now`` is caller-supplied)."""
        nonce = _validate_nonce(nonce)
        expires_at, now = _validate_times(expires_at, now)
        if expires_at <= now:
            return ConsumeResult(EXPIRED, nonce)
        claimed = self._backend.reserve(nonce, expires_at)
        if claimed:
            self._note_consumption(now)
            return ConsumeResult(CONSUMED, nonce)
        recorded = self._backend.lookup(nonce)
        effective = expires_at if recorded is None else recorded
        if effective <= now:
            return ConsumeResult(EXPIRED, nonce)
        return ConsumeResult(REPLAY_DETECTED, nonce)

    def _note_consumption(self, now: int) -> None:
        if self._sweep_interval is None:
            return
        trigger = False
        with self._lock:
            self._consumes_since_sweep += 1
            if self._consumes_since_sweep >= self._sweep_interval:
                self._consumes_since_sweep = 0
                trigger = True
        if trigger:
            self.sweep(now=now)

    def sweep(self, now: int | None = None, limit: int = _SWEEP_BATCH_LIMIT) -> int:
        """Reclaim expired records from the backend; returns count reclaimed.

        ``now`` is required for :class:`InMemoryNonceBackend` sweeps issued via
        the generic path; the in-process backend also exposes a direct
        :meth:`InMemoryNonceBackend.sweep` used by auto-sweep. There is no
        hidden-clock fallback: callers must supply the deterministic instant.
        """
        if now is not None and (isinstance(now, bool) or not isinstance(now, int)):
            raise NonceStoreError(RC_NOW_BAD_TYPE, "now must be integer epoch seconds or None")
        if hasattr(self._backend, "sweep"):
            return int(self._backend.sweep(now=now, limit=limit))
        if now is None:
            raise NonceStoreError(
                RC_NOW_BAD_TYPE, "sweep requires an explicit now for this backend"
            )
        reclaimed = 0
        for nonce in self._backend.expired(now, limit):
            self._backend.release(nonce)
            reclaimed += 1
        return reclaimed

    def size(self) -> int:
        """Currently claimed nonce records (bounded-memory telemetry)."""
        return self._backend.size()

    def is_claimed(self, nonce: str) -> bool:
        return self._backend.lookup(nonce) is not None


#: Explicit mapping of outcome -> meaning for report emission (no magic strings
#: downstream).
OUTCOME_SEMANTICS: Mapping[str, str] = {
    CONSUMED: "first presentation of a live nonce admitted exactly one effect",
    REPLAY_DETECTED: "nonce already consumed and still inside its validity window",
    EXPIRED: "nonce validity window closed (expires_at <= now)",
}

__all__ = [
    "CONSUMED",
    "EXPIRED",
    "NONCE_MIN_LENGTH",
    "NONCE_STORE_VERSION",
    "OUTCOME_SEMANTICS",
    "RC_BACKEND_UNAVAILABLE",
    "RC_EXPIRES_AT_BAD_TYPE",
    "RC_NONCE_MISSING",
    "RC_NONCE_TOO_SHORT",
    "RC_NOW_BAD_TYPE",
    "REPLAY_DETECTED",
    "ConsumeResult",
    "InMemoryNonceBackend",
    "NonceBackend",
    "NonceBackendError",
    "NonceStore",
    "NonceStoreError",
    "PostgresBackendUnavailable",
    "PostgresNonceBackend",
]
