"""CLARA-Care 2027 POPETS task POPETS-candidate — proposed candidate mechanism.

Purpose
-------
Implement the POPETS venue's proposed candidate (blueprint arm B4,
``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``, task
``research/venue2027/VENUES/popets/TASKS/POPETS-candidate.md``): the
*revocation-complete future-disclosure cache*. Every cache entry carries a
dependency set of ``(subject, purpose, consent_epoch)`` triples. A revocation
``revoke(subject, purpose, epoch)`` invalidates exactly the entries whose
dependency set intersects the revoked scope AND every transitively derived
entry, following reverse dependency edges (derivation edges recorded at
``put`` time) to closure. This is the design response to RQ1: post-revocation
model dispatches must not re-disclose revoked context through transitive
caches, retry payloads, embedding pointers or fallback transports even when
the derived artifact's own declared dependency labels do not name the revoked
scope (under-declared provenance). Invalidation is exact: entries with no
dependency on the revoked scope and no derivation path from an invalidated
entry stay live — this is a dependency-closure invalidation, never a full
cache flush.

Mechanism-isolation ablation
----------------------------
``ablation_no_reverse_edges()`` returns the same cache with reverse-edge
closure disabled: only entries whose OWN dependency set intersects the revoked
scope are invalidated, so a transitively derived entry whose recorded
dependencies are stable remains servable. Reading such an entry after the
revocation is an executable leakage event (``served_from_revoked_ancestry``
on the read result), which is how the test suite proves the reverse edges —
not the dependency labels alone — are the load-bearing mechanism. The ablation
mirrors the declared gap of the ``purpose-bound-cache-keying`` design
reference in ``baselines.py``.

Candidate design only: this module encodes a mechanism and its executable
invariants. It makes NO empirical claims (no measured rates, no dataset
results, no utility numbers). Consistent with the blueprint's guarantee
boundary, it governs FUTURE dispatches only: bytes already delivered to any
external provider before revocation are OUT_OF_SCOPE_PAST and no model
memorization erasure is claimed or implied.

Allowed input
-------------
- ``put(key, value, deps, derived_from=())``: ``key`` a non-empty string;
  ``value`` a non-empty string (cached context; only its byte length is
  reported, content is never serialized into aggregates); ``deps`` a
  non-empty collection of :class:`Dependency` (or mappings
  ``{"subject", "purpose", "consent_epoch"}`` or ``(subject, purpose, epoch)``
  triples); ``derived_from`` an optional collection of existing parent cache
  keys this entry was derived from (records the derivation edges the reverse
  closure follows). ``put`` is refused (stable ``ValueError`` reason codes)
  when a declared dependency or a derivation parent is already revoked
  (``REVOKED_DEPENDENCY``) — the cache never accepts revoked context.
- ``get(key, purpose, epoch)``: returns a :class:`CacheReadResult` with status
  ``HIT`` | ``CACHE_MISS`` | ``REVOKED_ENTRY`` | ``EPOCH_STALE`` |
  ``PURPOSE_MISMATCH``. A HIT requires the entry's dependency set to cover
  the requesting ``(purpose, epoch)``; cross-purpose reads are refused
  structurally (``PURPOSE_MISMATCH``), superseded-epoch reads are refused
  (``EPOCH_STALE``), tombstoned entries are refused (``REVOKED_ENTRY``).
- ``revoke(subject, purpose, epoch)``: records the revoked scope, computes
  the dependency closure (direct dep intersection + reverse-edge BFS),
  tombstones the mode-appropriate set, and appends a deterministic
  JSON-serializable record to the revocation log. Idempotent per
  ``(subject, purpose, epoch)`` event.
- ``describe_mechanism()``: JSON-serializable statement of the mechanism,
  enforcement flags, guarantees and non-guarantees.
- ``run_candidate(case, ctx)``: deterministic adapter mapping a
  ``cache_ops``-style case to the operations above and returning the shared
  harness :class:`Outcome` (the task contract's
  ``run_candidate(case, ctx) -> Outcome`` boundary).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. Malformed input to ``put`` /
``get`` / ``revoke`` is an explicit refusal raised as ``ValueError`` with the
reason code as message prefix (``KEY_MALFORMED``, ``VALUE_MALFORMED``,
``DEPS_MALFORMED``, ``PURPOSE_MALFORMED``, ``EPOCH_MALFORMED``,
``SUBJECT_MALFORMED``, ``DERIVATION_PARENT_MISSING``,
``DERIVATION_CYCLE``, ``REVOKED_DEPENDENCY``); domain outcomes are returned
statuses, never exceptions. No hidden clock, randomness, network, database or
provider access; the candidate is a pure in-process structure with injected
operations only. The candidate mode carries an executable closure invariant:
a HIT can never be served from revoked ancestry (``CLOSURE_INVARIANT_VIOLATION``
would be raised if the structure were corrupted); the ablation intentionally
lacks this invariant (that absence IS the leak).

Version
-------
``CANDIDATE_VERSION = "1.0.0"``; ``CANDIDATE_ID =
"popets-revocation-complete-future-disclosure"``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

__all__ = [
    "ABLATION_ID",
    "CANDIDATE_ID",
    "CANDIDATE_VERSION",
    "CacheEntry",
    "CacheReadResult",
    "Dependency",
    "RevocationCompleteCache",
    "ablation_no_reverse_edges",
    "describe_mechanism",
    "run_candidate",
]

CANDIDATE_ID = "popets-revocation-complete-future-disclosure"
CANDIDATE_VERSION = "1.0.0"
ABLATION_ID = "popets-ablation-no-reverse-edges"

#: Read statuses returned by :meth:`RevocationCompleteCache.get`.
STATUS_HIT = "HIT"
STATUS_CACHE_MISS = "CACHE_MISS"
STATUS_REVOKED_ENTRY = "REVOKED_ENTRY"
STATUS_EPOCH_STALE = "EPOCH_STALE"
STATUS_PURPOSE_MISMATCH = "PURPOSE_MISMATCH"

#: Stable refusal reason codes (ValueError message prefixes).
REASON_KEY_MALFORMED = "KEY_MALFORMED"
REASON_VALUE_MALFORMED = "VALUE_MALFORMED"
REASON_DEPS_MALFORMED = "DEPS_MALFORMED"
REASON_SUBJECT_MALFORMED = "SUBJECT_MALFORMED"
REASON_PURPOSE_MALFORMED = "PURPOSE_MALFORMED"
REASON_EPOCH_MALFORMED = "EPOCH_MALFORMED"
REASON_DERIVATION_PARENT_MISSING = "DERIVATION_PARENT_MISSING"
REASON_DERIVATION_CYCLE = "DERIVATION_CYCLE"
REASON_REVOKED_DEPENDENCY = "REVOKED_DEPENDENCY"
REASON_CLOSURE_INVARIANT_VIOLATION = "CLOSURE_INVARIANT_VIOLATION"
REASON_WORKLOAD_MALFORMED = "WORKLOAD_MALFORMED"


# ---------------------------------------------------------------------------
# Typed input objects (JSON-serializable)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, order=True)
class Dependency:
    """One provenance label: the entry exists because of this consent scope.

    ``order=True`` makes dependencies deterministically sortable so every
    serialized record is reproducible without hidden iteration order.
    """

    subject: str
    purpose: str
    consent_epoch: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "purpose": self.purpose,
            "consent_epoch": self.consent_epoch,
        }

    @classmethod
    def from_input(cls, raw: Dependency | Mapping[str, Any] | Sequence[Any]) -> Dependency:
        """Normalize a Dependency, mapping, or ``(subject, purpose, epoch)`` triple."""
        if isinstance(raw, Dependency):
            return raw
        if isinstance(raw, Mapping):
            subject = raw.get("subject")
            purpose = raw.get("purpose")
            epoch = raw.get("consent_epoch", raw.get("epoch"))
            return cls(
                subject=_checked_subject(subject),
                purpose=_checked_purpose(purpose),
                consent_epoch=_checked_epoch(epoch),
            )
        if isinstance(raw, Sequence) and not isinstance(raw, str | bytes) and len(raw) == 3:
            return cls(
                subject=_checked_subject(raw[0]),
                purpose=_checked_purpose(raw[1]),
                consent_epoch=_checked_epoch(raw[2]),
            )
        raise ValueError(
            f"{REASON_DEPS_MALFORMED}: dependency must be a Dependency, mapping or "
            f"(subject, purpose, consent_epoch) triple, got {type(raw).__name__}"
        )


@dataclasses.dataclass(frozen=True)
class CacheEntry:
    """One cache line: value, declared dependency set, derivation parents, liveness."""

    key: str
    value: str
    deps: frozenset[Dependency]
    derived_from: frozenset[str]
    created_at_revocation_events: int

    def to_dict(self) -> dict[str, Any]:
        """Content-free view: byte length only, never the cached context itself."""
        return {
            "key": self.key,
            "value_bytes": len(self.value.encode("utf-8")),
            "deps": sorted(d.to_dict() for d in self.deps),
            "derived_from": sorted(self.derived_from),
            "created_at_revocation_events": self.created_at_revocation_events,
        }


@dataclasses.dataclass(frozen=True)
class CacheReadResult:
    """Result of one ``get`` dispatch; JSON-serializable, content-free."""

    key: str
    purpose: str
    epoch: int
    status: str
    served_from_revoked_ancestry: bool
    covering_deps: tuple[Dependency, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "purpose": self.purpose,
            "epoch": self.epoch,
            "status": self.status,
            "served_from_revoked_ancestry": self.served_from_revoked_ancestry,
            "covering_deps": sorted(d.to_dict() for d in self.covering_deps),
        }


# ---------------------------------------------------------------------------
# Input validation helpers (stable reason codes, explicit refusals)
# ---------------------------------------------------------------------------


def _checked_key(key: Any) -> str:
    if isinstance(key, bool) or not isinstance(key, str) or not key:
        raise ValueError(f"{REASON_KEY_MALFORMED}: key must be a non-empty string")
    return key


def _checked_value(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, str) or not value:
        raise ValueError(f"{REASON_VALUE_MALFORMED}: value must be a non-empty string")
    return value


def _checked_subject(subject: Any) -> str:
    if isinstance(subject, bool) or not isinstance(subject, str) or not subject:
        raise ValueError(f"{REASON_SUBJECT_MALFORMED}: subject must be a non-empty string")
    return subject


def _checked_purpose(purpose: Any) -> str:
    if isinstance(purpose, bool) or not isinstance(purpose, str) or not purpose:
        raise ValueError(f"{REASON_PURPOSE_MALFORMED}: purpose must be a non-empty string")
    return purpose


def _checked_epoch(epoch: Any) -> int:
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise ValueError(f"{REASON_EPOCH_MALFORMED}: epoch must be a non-negative integer")
    return epoch


def _checked_deps(deps: Any) -> frozenset[Dependency]:
    if isinstance(deps, str | bytes) or not isinstance(deps, Iterable):
        raise ValueError(
            f"{REASON_DEPS_MALFORMED}: deps must be a non-empty collection of dependencies"
        )
    parsed = frozenset(Dependency.from_input(d) for d in deps)
    if not parsed:
        raise ValueError(
            f"{REASON_DEPS_MALFORMED}: every cache entry must carry at least one "
            "(subject, purpose, consent_epoch) dependency"
        )
    return parsed


# ---------------------------------------------------------------------------
# The candidate cache
# ---------------------------------------------------------------------------


class RevocationCompleteCache:
    """Dependency-closure cache: revocation-complete future disclosure (design).

    Two enforcement modes:

    - ``enforce_reverse_edges=True`` (the CANDIDATE): ``revoke`` tombstones
      every entry whose dependency set intersects the revoked scope AND every
      transitively derived entry reached by following reverse derivation edges
      to closure. Under-declared derived artifacts (retry payloads, embedding
      pointers, fallback transports) are invalidated by ancestry even when
      their own labels name a different purpose/epoch.
    - ``enforce_reverse_edges=False`` (the ABLATION): only direct dependency
      intersection is invalidated; transitively derived entries whose recorded
      dependencies are stable remain servable — the declared leak surface the
      tests exercise to prove the mechanism.
    """

    def __init__(self, *, enforce_reverse_edges: bool = True, mode: str = "candidate") -> None:
        self.enforce_reverse_edges = enforce_reverse_edges
        self.mode = mode
        self._entries: dict[str, CacheEntry] = {}
        self._tombstoned: dict[str, bool] = {}
        self._children: dict[str, set[str]] = {}
        self._revoked_scopes: set[tuple[str, str, int]] = set()
        self._closure_keys: set[str] = set()
        self._revocation_log: list[dict[str, Any]] = []
        self._revocation_events = 0

    # -- put ----------------------------------------------------------------

    def put(
        self,
        key: str,
        value: str,
        deps: Iterable[Dependency | Mapping[str, Any] | Sequence[Any]],
        derived_from: Iterable[str] = (),
    ) -> CacheEntry:
        """Insert or overwrite an entry; refuse revoked context, fail closed."""
        checked_key = _checked_key(key)
        checked_value = _checked_value(value)
        checked_deps = _checked_deps(deps)
        parents = frozenset(_checked_key(p) for p in derived_from)
        for revoked in sorted(self._revoked_scopes):
            if revoked in {(d.subject, d.purpose, d.consent_epoch) for d in checked_deps}:
                raise ValueError(
                    f"{REASON_REVOKED_DEPENDENCY}: refusing to cache {checked_key!r}: "
                    f"dependency (subject={revoked[0]!r}, purpose={revoked[1]!r}, "
                    f"consent_epoch={revoked[2]}) is revoked"
                )
        for parent in sorted(parents):
            if parent == checked_key:
                raise ValueError(
                    f"{REASON_DERIVATION_CYCLE}: entry {checked_key!r} cannot derive from itself"
                )
            if parent not in self._entries:
                raise ValueError(
                    f"{REASON_DERIVATION_PARENT_MISSING}: derivation parent {parent!r} of "
                    f"{checked_key!r} is not in the cache; derivation edges must be real"
                )
            if self._tombstoned.get(parent, False):
                raise ValueError(
                    f"{REASON_REVOKED_DEPENDENCY}: refusing to cache {checked_key!r}: "
                    f"derivation parent {parent!r} is revoked"
                )
        entry = CacheEntry(
            key=checked_key,
            value=checked_value,
            deps=checked_deps,
            derived_from=parents,
            created_at_revocation_events=self._revocation_events,
        )
        self._drop_reverse_edges(checked_key)
        self._entries[checked_key] = entry
        self._tombstoned[checked_key] = False
        for parent in parents:
            self._children.setdefault(parent, set()).add(checked_key)
        return entry

    def _drop_reverse_edges(self, key: str) -> None:
        """Remove key's stale reverse edges before overwrite (child index rebuild)."""
        for parent, children in list(self._children.items()):
            children.discard(key)
            if not children:
                del self._children[parent]

    # -- get ----------------------------------------------------------------

    def get(self, key: str, purpose: str, epoch: int) -> CacheReadResult:
        """Reauthorize one dispatch at read time; fail closed, never guess.

        A HIT requires: entry exists, not tombstoned, and its dependency set
        covers the requesting ``(purpose, epoch)`` via at least one dependency.
        Cross-purpose reads (``PURPOSE_MISMATCH``) and superseded-epoch reads
        (``EPOCH_STALE``) are refused structurally.
        """
        checked_key = _checked_key(key)
        checked_purpose = _checked_purpose(purpose)
        checked_epoch = _checked_epoch(epoch)
        entry = self._entries.get(checked_key)
        if entry is None:
            return CacheReadResult(
                key=checked_key,
                purpose=checked_purpose,
                epoch=checked_epoch,
                status=STATUS_CACHE_MISS,
                served_from_revoked_ancestry=False,
                covering_deps=(),
            )
        if self._tombstoned.get(checked_key, False):
            return CacheReadResult(
                key=checked_key,
                purpose=checked_purpose,
                epoch=checked_epoch,
                status=STATUS_REVOKED_ENTRY,
                served_from_revoked_ancestry=checked_key in self._closure_keys,
                covering_deps=(),
            )
        same_purpose = [d for d in entry.deps if d.purpose == checked_purpose]
        if not same_purpose:
            return CacheReadResult(
                key=checked_key,
                purpose=checked_purpose,
                epoch=checked_epoch,
                status=STATUS_PURPOSE_MISMATCH,
                served_from_revoked_ancestry=False,
                covering_deps=(),
            )
        covering = tuple(sorted(d for d in same_purpose if d.consent_epoch == checked_epoch))
        if not covering:
            return CacheReadResult(
                key=checked_key,
                purpose=checked_purpose,
                epoch=checked_epoch,
                status=STATUS_EPOCH_STALE,
                served_from_revoked_ancestry=False,
                covering_deps=(),
            )
        ancestry_leak = checked_key in self._closure_keys
        if self.enforce_reverse_edges and ancestry_leak:
            # A HIT served from revoked ancestry in candidate mode means the
            # reverse-edge closure was corrupted; fail closed, never silently
            # serve (the ablation instead reports the leak on the read result).
            raise ValueError(
                f"{REASON_CLOSURE_INVARIANT_VIOLATION}: candidate served {checked_key!r} "
                "from revoked ancestry; reverse-edge closure is corrupted"
            )
        return CacheReadResult(
            key=checked_key,
            purpose=checked_purpose,
            epoch=checked_epoch,
            status=STATUS_HIT,
            served_from_revoked_ancestry=ancestry_leak,
            covering_deps=covering,
        )

    # -- revoke ---------------------------------------------------------------

    def revoke(self, subject: str, purpose: str, epoch: int) -> dict[str, Any]:
        """Revoke one consent scope; invalidate the dependency closure exactly.

        Direct invalidation: every live entry whose dependency set contains
        ``(subject, purpose, epoch)``. Transitive invalidation (candidate
        only): BFS over reverse derivation edges from the direct set to
        closure, tombstoning each derived descendant. Unaffected entries stay
        live — never a full flush. Idempotent per event; deterministic record.
        """
        checked_subject = _checked_subject(subject)
        checked_purpose = _checked_purpose(purpose)
        checked_epoch = _checked_epoch(epoch)
        scope = (checked_subject, checked_purpose, checked_epoch)
        direct = sorted(
            key
            for key, entry in self._entries.items()
            if any(
                d.subject == checked_subject
                and d.purpose == checked_purpose
                and d.consent_epoch == checked_epoch
                for d in entry.deps
            )
        )
        # Closure is always computed (audit surface); enforcement decides whether
        # the transitive set is tombstoned. The ablation detects but does not act.
        transitive = self._transitive_closure(direct)
        already_applied = scope in self._revoked_scopes
        invalidated = set(direct)
        if self.enforce_reverse_edges:
            invalidated |= transitive
        left_live = sorted(
            k for k in self._entries if not self._tombstoned.get(k, False) and k not in invalidated
        )
        if not already_applied:
            self._revoked_scopes.add(scope)
            for key in sorted(invalidated):
                self._tombstoned[key] = True
            self._closure_keys |= set(direct) | transitive
            record = {
                "event_index": self._revocation_events,
                "subject": checked_subject,
                "purpose": checked_purpose,
                "consent_epoch": checked_epoch,
                "direct_keys": direct,
                "transitive_keys": sorted(transitive),
                "invalidated_keys": sorted(invalidated),
                "left_live": left_live,
                "enforce_reverse_edges": self.enforce_reverse_edges,
                "applied": True,
            }
            self._revocation_events += 1
            self._revocation_log.append(record)
            return record
        return {
            "event_index": self._revocation_events - 1,
            "subject": checked_subject,
            "purpose": checked_purpose,
            "consent_epoch": checked_epoch,
            "direct_keys": direct,
            "transitive_keys": sorted(transitive),
            "invalidated_keys": [],
            "left_live": left_live,
            "enforce_reverse_edges": self.enforce_reverse_edges,
            "applied": False,
        }

    def _transitive_closure(self, direct: Sequence[str]) -> set[str]:
        """Reverse-edge BFS from ``direct`` to transitive derivation closure.

        Always computed (so the ablation can DETECT revoked ancestry for its
        leak report and the candidate can TOMBSTONE the closure); whether the
        transitive set is enforced is decided by the caller.
        """
        seen: set[str] = set()
        frontier = list(direct)
        while frontier:
            parent = frontier.pop()
            for child in sorted(self._children.get(parent, ())):
                if child in seen:
                    continue
                if self._tombstoned.get(child, False):
                    continue
                seen.add(child)
                frontier.append(child)
        seen -= set(direct)
        return seen

    # -- observability --------------------------------------------------------

    def is_live(self, key: str) -> bool:
        """Liveness probe for audits: entry exists and is not tombstoned."""
        return key in self._entries and not self._tombstoned.get(key, False)

    def revocation_log(self) -> tuple[dict[str, Any], ...]:
        """Deterministic, content-free revocation records (audit surface)."""
        return tuple(self._revocation_log)

    def describe_mechanism(self) -> dict[str, Any]:
        """JSON-serializable mechanism statement (candidate vs ablation)."""
        if self.enforce_reverse_edges:
            mechanism = (
                "Dependency-closure invalidation: every entry carries a "
                "(subject, purpose, consent_epoch) dependency set; revoke() "
                "tombstones entries whose deps intersect the revoked scope AND, "
                "via reverse derivation edges, every transitively derived entry "
                "to closure. Exact invalidation, never a full flush."
            )
            load_bearing = "reverse derivation edges (dependency closure)"
        else:
            mechanism = (
                "Ablation: direct dependency intersection only; transitively "
                "derived entries whose own labels are stable are NOT invalidated "
                "and remain servable — the declared post-revocation leak surface."
            )
            load_bearing = "none (reverse edges disabled; mechanism isolated away)"
        return {
            "candidate_id": CANDIDATE_ID if self.enforce_reverse_edges else ABLATION_ID,
            "version": CANDIDATE_VERSION,
            "mode": self.mode,
            "mechanism": mechanism,
            "load_bearing_mechanism": load_bearing,
            "enforce_reverse_edges": self.enforce_reverse_edges,
            "invalidation_kind": "dependency_closure"
            if self.enforce_reverse_edges
            else "direct_only",
            "entry_contract": "(subject, purpose, consent_epoch) dependency set per entry",
            "read_contract": {
                "statuses": [
                    STATUS_HIT,
                    STATUS_CACHE_MISS,
                    STATUS_REVOKED_ENTRY,
                    STATUS_EPOCH_STALE,
                    STATUS_PURPOSE_MISMATCH,
                ],
                "reauthorize_at_every_dispatch": True,
            },
            "guarantees": (
                "G1 direct: a revoked scope's own entries are refused (REVOKED_ENTRY).",
                "G2 transitive: every transitively derived entry is refused via "
                "reverse-edge closure even when its own labels are stable.",
                "G3 exactness: entries with no revoked dependency and no derivation "
                "path from an invalidated entry stay live (no full flush).",
                "G4 purpose boundary: a get under a purpose the entry does not carry "
                "is refused (PURPOSE_MISMATCH).",
                "G5 epoch boundary: a get under a superseded epoch is refused " "(EPOCH_STALE).",
                "G6 admission: put() refuses entries whose deps or derivation parents "
                "are already revoked (REVOKED_DEPENDENCY).",
            ),
            "non_guarantees": (
                "N1 OUT_OF_SCOPE_PAST: bytes already delivered to any external provider "
                "before revocation cannot be retracted by this cache.",
                "N2 model memorization: no erasure of provider-side model memory is "
                "claimed or implied.",
                "N3 design candidate only: this module encodes a mechanism and its "
                "executable invariants; it makes no empirical performance or leakage "
                "claims.",
            ),
            "entries": len(self._entries),
            "live_entries": sum(1 for k in self._entries if not self._tombstoned.get(k, False)),
            "revocation_events": self._revocation_events,
        }


def ablation_no_reverse_edges() -> RevocationCompleteCache:
    """Mechanism-isolation ablation: the candidate MINUS reverse-edge closure.

    Only direct dependency invalidation runs; transitively derived entries
    whose recorded dependencies are stable survive the revocation and can be
    re-disclosed to the model — the executable leak that proves reverse edges
    are the load-bearing mechanism of the candidate.
    """
    return RevocationCompleteCache(enforce_reverse_edges=False, mode="ablation_no_reverse_edges")


def describe_mechanism() -> dict[str, Any]:
    """Module-level mechanism statement for the candidate (default mode)."""
    return RevocationCompleteCache().describe_mechanism()


# ---------------------------------------------------------------------------
# Deterministic adapter: run_candidate(case, ctx) -> Outcome (task contract)
# ---------------------------------------------------------------------------

_OP_PUT = "put"
_OP_GET = "get"
_OP_REVOKE = "revoke"


def _dep_triples(raw: Any) -> list[list[Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{REASON_DEPS_MALFORMED}: deps must be a non-empty array")
    triples: list[list[Any]] = []
    for item in raw:
        if isinstance(item, Mapping):
            triples.append([item.get("subject"), item.get("purpose"), item.get("consent_epoch")])
        elif isinstance(item, Sequence) and not isinstance(item, str | bytes) and len(item) == 3:
            triples.append([item[0], item[1], item[2]])
        else:
            raise ValueError(f"{REASON_DEPS_MALFORMED}: each dep must be a triple or mapping")
    return triples


def _execute_op(cache: RevocationCompleteCache, op: Mapping[str, Any]) -> dict[str, Any]:
    kind = op.get("op")
    if kind == _OP_PUT:
        entry = cache.put(
            op.get("key"),
            op.get("value"),
            _dep_triples(op.get("deps")),
            derived_from=op.get("derived_from", ()) or (),
        )
        return {"op": _OP_PUT, "key": entry.key, "status": "OK"}
    if kind == _OP_GET:
        result = cache.get(op.get("key"), op.get("purpose"), op.get("epoch"))
        record = result.to_dict()
        record["op"] = _OP_GET
        return record
    if kind == _OP_REVOKE:
        record = cache.revoke(op.get("subject"), op.get("purpose"), op.get("epoch"))
        record["op"] = _OP_REVOKE
        return record
    raise ValueError(f"{REASON_WORKLOAD_MALFORMED}: unknown cache op {kind!r}")


def run_candidate(case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Run the candidate (or its ablation) over a deterministic ``cache_ops`` case.

    Case schema (JSON-serializable): ``{"case_id": str, "mode": "candidate" |
    "ablation", "cache_ops": [{"op": "put"|"get"|"revoke", ...}, ...]}``. Any
    op failure is an explicit refusal; malformed input fails closed with
    ``EXECUTION_ERROR`` and a stable reason code, never a silent safe
    rejection. Pair-level outcome is ``ADMIT`` iff at least one ``get``
    returned ``HIT`` (determined disclosure decisions were produced), else
    ``REJECT``; both are counted outcomes. ``leaks`` counts HITs served from
    revoked ancestry (structurally 0 for the candidate, >0 for the ablation
    on under-declared transitive entries). No empirical claim is attached.
    """
    del ctx  # no hidden randomness: the case fully determines the run
    if not isinstance(case, Mapping):
        return Outcome(
            "EXECUTION_ERROR", detail=f"{REASON_WORKLOAD_MALFORMED}: case must be an object"
        )
    ops = case.get("cache_ops")
    if not isinstance(ops, list) or not ops:
        return Outcome(
            "EXECUTION_ERROR",
            detail=f"{REASON_WORKLOAD_MALFORMED}: cache_ops must be a non-empty array",
        )
    mode = case.get("mode", "candidate")
    if mode == "ablation":
        cache = ablation_no_reverse_edges()
    elif mode == "candidate":
        cache = RevocationCompleteCache()
    else:
        return Outcome(
            "EXECUTION_ERROR",
            detail=f"{REASON_WORKLOAD_MALFORMED}: mode must be 'candidate' or 'ablation'",
        )
    records: list[dict[str, Any]] = []
    try:
        for index, op in enumerate(ops):
            if not isinstance(op, Mapping):
                raise ValueError(f"{REASON_WORKLOAD_MALFORMED}: op {index} must be an object")
            records.append(_execute_op(cache, op))
    except ValueError as exc:
        return Outcome("EXECUTION_ERROR", detail=f"op {len(records)}: {exc}")
    gets = [r for r in records if r["op"] == _OP_GET]
    hits = sum(1 for r in gets if r["status"] == STATUS_HIT)
    leaks = sum(1 for r in gets if r["status"] == STATUS_HIT and r["served_from_revoked_ancestry"])
    detail = {
        "candidate_id": CANDIDATE_ID if cache.enforce_reverse_edges else ABLATION_ID,
        "version": CANDIDATE_VERSION,
        "mode": mode,
        "op_count": len(records),
        "gets": len(gets),
        "hits": hits,
        "leaks": leaks,
        "leak_keys": sorted(r["key"] for r in gets if r["served_from_revoked_ancestry"]),
        "status_counts": {
            status: sum(1 for r in gets if r["status"] == status)
            for status in (
                STATUS_HIT,
                STATUS_CACHE_MISS,
                STATUS_REVOKED_ENTRY,
                STATUS_EPOCH_STALE,
                STATUS_PURPOSE_MISMATCH,
            )
        },
        "revocation_log": [dict(r) for r in cache.revocation_log()],
        "ops": records,
        "design_only": "no empirical claims; mechanism + executable invariants only",
    }
    observed = "ADMIT" if hits > 0 else "REJECT"
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        detail=json.dumps(detail, sort_keys=True),
    )
