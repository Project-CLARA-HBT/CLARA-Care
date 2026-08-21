"""Observer-only cache measurement for the GovRed W2 workstream.

W2 requires *observer-only* cache measurement: an evaluation must be able to
determine whether a governed-disclosure cache serves stale data after a
governance change (consent revocation / policy change) **without** deleting or
invalidating the cache it measures.  This module is that pure abstraction.  It
defines the read-only cache surface (which deliberately exposes no
``delete``/invalidate method), the five W2 observation fields, and a
``measure`` helper that derives them from read-only probes.

W2 defect note (documented, not fixed here): the current research measurement
endpoint
``services/api/src/clara_api/api/v1/endpoints/govred_research.py`` contains a
self-fulfilling ``if arm.revalidate_governance: store.delete(cache_key)`` at
``govred_research.py:190-191``.  Because the research arm itself performs the
invalidation, ``cache_present_after_revoke`` is decided by the arm's own delete
rather than by an independent, governance-driven invalidation hook, so the
endpoint cannot measure whether the cache would have been invalidated on its
own.  W2 requires observer-only measurement; that endpoint is intentionally NOT
modified here (root will gate that change).  See
``research/govred_rivf/cache_path_audit.md`` for the full audit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

#: Single source of truth for the W2 concrete cache-observation fields.  A cache
#: family contract (``family_contracts.py``) requires exactly these fields.
CACHE_OBSERVATION_FIELDS: tuple[str, ...] = (
    "stale_cache_entry_exists",
    "stale_cache_returned",
    "governance_reevaluation_occurred",
    "stale_cache_caused_invalid_persistent_commit",
    "revocation_to_not_visible_latency",
)


class ReadOnlyCacheStore(Protocol):
    """Read-only cache surface; deliberately exposes no mutation method.

    An observer-backed implementation of this protocol must never delete or
    invalidate an entry.  The protocol intentionally has no ``delete``,
    ``set``, or ``invalidate`` method, so an observer cannot mutate the cache
    it is measuring.  Implementations may back this surface with a live Redis
    client, an isolated HTTP observation, or an offline snapshot.
    """

    def exists(self, key: str) -> bool: ...

    def get_bytes(self, key: str) -> bytes | None: ...

    def get_ttl(self, key: str) -> int | None: ...


@dataclass(frozen=True)
class CacheObservation:
    """Sanitized, payload-free observation of one governed-disclosure cache key.

    Field semantics (the W2 measurement contract):

    * ``stale_cache_entry_exists`` — a cache entry is still present after the
      governance change that should have invalidated it.
    * ``stale_cache_returned`` — the stale entry was actually served on the
      read path rather than skipped by re-evaluation.
    * ``governance_reevaluation_occurred`` — governance (consent/policy) was
      re-evaluated on the read path instead of trusting the cached entry.
    * ``stale_cache_caused_invalid_persistent_commit`` — the stale entry was
      used as the basis of a persistent commit that governance should have
      rejected.
    * ``revocation_to_not_visible_latency`` — milliseconds from the governance
      change until the stale entry is no longer visible (``0.0`` when it was
      never visible after the change).
    """

    stale_cache_entry_exists: bool
    stale_cache_returned: bool
    governance_reevaluation_occurred: bool
    stale_cache_caused_invalid_persistent_commit: bool
    revocation_to_not_visible_latency: float

    def asdict(self) -> dict[str, object]:
        return asdict(self)  # type: ignore[return-value]

    @classmethod
    def absent(cls) -> CacheObservation:
        """Return the neutral observation used when no cache is measurable.

        Callers must prefer this over a guessed observation whenever the cache
        is unreachable, because every field defaults to the no-claim value.
        """

        return cls(
            stale_cache_entry_exists=False,
            stale_cache_returned=False,
            governance_reevaluation_occurred=False,
            stale_cache_caused_invalid_persistent_commit=False,
            revocation_to_not_visible_latency=0.0,
        )


class ImmutableSnapshotStore:
    """Read-only view over an immutable key snapshot; never mutates anything.

    This is the offline/unit implementation of :class:`ReadOnlyCacheStore`.  It
    is immutable and exposes only the read-only surface, so it cannot delete or
    invalidate an entry.  ``read_count`` lets tests assert that measurement is
    read-only.
    """

    def __init__(self, snapshot: dict[str, bytes], ttl: dict[str, int] | None = None) -> None:
        self._snapshot = dict(snapshot)
        self._ttl = dict(ttl or {})
        self._reads = 0

    def exists(self, key: str) -> bool:
        self._reads += 1
        return key in self._snapshot

    def get_bytes(self, key: str) -> bytes | None:
        self._reads += 1
        return self._snapshot.get(key)

    def get_ttl(self, key: str) -> int | None:
        self._reads += 1
        return self._ttl.get(key)

    @property
    def read_count(self) -> int:
        return self._reads


def measure(
    *,
    store: ReadOnlyCacheStore,
    cache_key: str,
    revoked_at_monotonic: float,
    stale_served: bool,
    governance_reevaluated: bool,
    invalid_persistent_commit: bool,
    now_monotonic: float,
) -> CacheObservation:
    """Derive the W2 cache observation from read-only probes of ``store``.

    This helper never writes to ``store``; it only calls the read-only
    ``exists`` surface.  If the cache is unreachable, callers should return
    ``CacheObservation.absent()`` instead of fabricating a positive result.
    ``stale_served`` / ``governance_reevaluated`` / ``invalid_persistent_commit``
    are independently observed facts about the read/admission path, not cache
    writes.
    """

    entry_exists = store.exists(cache_key)
    latency_ms = (
        0.0 if not entry_exists else max(0.0, (now_monotonic - revoked_at_monotonic) * 1000.0)
    )
    return CacheObservation(
        stale_cache_entry_exists=entry_exists,
        stale_cache_returned=entry_exists and bool(stale_served),
        governance_reevaluation_occurred=bool(governance_reevaluated),
        stale_cache_caused_invalid_persistent_commit=bool(invalid_persistent_commit),
        revocation_to_not_visible_latency=latency_ms,
    )


def require_fields(observation: CacheObservation) -> None:
    """Fail closed if an observation is missing any W2 field.

    Guards against contract drift between the typed observation and the field
    names a cache family requires.
    """

    missing = set(CACHE_OBSERVATION_FIELDS) - set(asdict(observation))
    if missing:
        raise ValueError("govred_cache_observation_fields_missing:" + ",".join(sorted(missing)))
