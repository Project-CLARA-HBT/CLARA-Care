"""CLARA-Care 2027 POPETS task POPETS-X03_cache_control — purpose-bound cache control.

Purpose
-------
A purpose-bound cache control layer for the paper *Revocation-Complete Future
Disclosure for Cached Longitudinal AI Contexts*
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``). Cache lines are
typed entries keyed by the 4-tuple ``CacheKey(subject, grant, purpose,
consent_epoch)``, so every purpose (and every consent epoch) owns a disjoint key
space: cross-purpose reuse is structurally impossible, and the public API adds
an explicit refusal on top of key identity.

The layer's guarantee is revocation completeness: ``revoke(subject)`` drops
EVERY entry for the subject across ALL grants, purposes and epochs, tombstones
the subject, and rotates the consent epoch. After ``revoke(s)`` no context of
``s`` is ever served again through this layer, for any purpose, at any epoch —
and no new context for ``s`` can be installed (fail closed). The executable
proof is ``assert_revocation_complete(cache, subject)``, which scans the live
entry store and raises :class:`RevocationLeakError` if any entry for the
subject survives anywhere in the key space.

Allowed input
-------------
- ``CacheKey``: non-empty ``subject`` / ``grant`` / ``purpose`` strings and a
  non-negative integer ``consent_epoch`` (booleans refused).
- ``context``: a non-empty string (the cached projection bytes); the caller
  supplies ``source_artifacts`` and a logical ``created_at_seconds`` — the
  module has NO hidden clock, no randomness, no network, no I/O.
- ``recompute``: an injected callable ``CacheKey -> str`` used by
  :meth:`PurposeBoundCache.recompute_or_fetch` on a miss; it is invoked ONLY
  when the request is authorized to be served at all (never for a revoked
  subject, a stale epoch, or a purpose-mismatched request).
- ``revoke(subject)`` / ``assert_revocation_complete(cache, subject)``:
  non-empty subject strings; synthetic identifiers only, no PHI/PII.

Failure semantics (fail closed, stable uppercase reason codes — never an
unhandled exception mistaken for a safe rejection):
- Read path (``get``, ``recompute_or_fetch``) returns refusal statuses instead
  of raising: ``KEY_MALFORMED`` (malformed key/request), ``PURPOSE_MISMATCH``
  (requesting purpose differs from the key's purpose component),
  ``EPOCH_STALE`` (key not bound to the subject's current consent epoch),
  ``REVOKED_SUBJECT`` (tombstoned subject at the current epoch), ``CACHE_MISS``
  (nothing installed under the exact key). A refusal never returns context
  bytes.
- Write path (``put``, ``revoke``) raises :class:`CacheControlError` so a lost
  write can never be silently dropped: ``KEY_MALFORMED``,
  ``CONTEXT_MALFORMED``, ``ARTIFACTS_MALFORMED``, ``CREATED_AT_MALFORMED``,
  ``KEY_EPOCH_STALE``, ``REVOKED_SUBJECT``, ``SUBJECT_MALFORMED``,
  ``RECOMPUTE_MALFORMED``.
- ``assert_revocation_complete`` raises :class:`RevocationLeakError` (reason
  ``REVOCATION_LEAK``, a ``ValueError`` subclass) naming every surviving key if
  any live entry remains for the subject; otherwise it returns a JSON-
  serializable completeness report.

Guarantee boundary (threat model §10; POPETS-X02 semantics): this layer
governs *future* serving only. It never claims retraction of bytes already
delivered to an external provider, and it makes no claim of cryptographic
retroactive erasure.

Version
-------
``CACHE_CONTROL_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable
from typing import Any

__all__ = [
    "CACHE_CONTROL_VERSION",
    "CacheControlError",
    "CacheEntry",
    "CacheKey",
    "FetchResult",
    "InvalidationReport",
    "PurposeBoundCache",
    "REASON_CACHE_MISS",
    "REASON_CONTEXT_MALFORMED",
    "REASON_CREATED_AT_MALFORMED",
    "REASON_EPOCH_STALE",
    "REASON_HIT",
    "REASON_ARTIFACTS_MALFORMED",
    "REASON_KEY_EPOCH_STALE",
    "REASON_KEY_MALFORMED",
    "REASON_PURPOSE_MISMATCH",
    "REASON_RECOMPUTE_MALFORMED",
    "REASON_RECOMPUTED",
    "REASON_REVOCATION_LEAK",
    "REASON_REVOKED_SUBJECT",
    "REASON_SUBJECT_MALFORMED",
    "RevocationLeakError",
    "assert_revocation_complete",
]

CACHE_CONTROL_VERSION = "1.0.0"

#: Fetch/refusal status vocabulary (stable uppercase reason codes, fail closed).
REASON_HIT = "HIT"
REASON_RECOMPUTED = "RECOMPUTED"
REASON_CACHE_MISS = "CACHE_MISS"
REASON_PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
REASON_EPOCH_STALE = "EPOCH_STALE"
REASON_REVOKED_SUBJECT = "REVOKED_SUBJECT"
REASON_KEY_MALFORMED = "KEY_MALFORMED"

#: Write-path / audit reason codes (raised as CacheControlError).
REASON_KEY_EPOCH_STALE = "KEY_EPOCH_STALE"
REASON_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"
REASON_ARTIFACTS_MALFORMED = "ARTIFACTS_MALFORMED"
REASON_CREATED_AT_MALFORMED = "CREATED_AT_MALFORMED"
REASON_SUBJECT_MALFORMED = "SUBJECT_MALFORMED"
REASON_RECOMPUTE_MALFORMED = "RECOMPUTE_MALFORMED"
REASON_CACHE_MALFORMED = "CACHE_MALFORMED"
REASON_REVOCATION_LEAK = "REVOCATION_LEAK"

#: Statuses that authorize serving context bytes to the caller.
SERVING_STATUSES: tuple[str, ...] = (REASON_HIT, REASON_RECOMPUTED)


class CacheControlError(ValueError):
    """A fail-closed refusal on the write/audit path with a stable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


class RevocationLeakError(CacheControlError):
    """Raised by ``assert_revocation_complete`` when a live entry survived revocation."""


def _require_non_empty_str(value: Any, reason_code: str, what: str) -> None:
    if not isinstance(value, str) or not value:
        raise CacheControlError(reason_code, f"{what} must be a non-empty string")


# ---------------------------------------------------------------------------
# Typed input/output objects (JSON-serializable; context bytes never serialized)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CacheKey:
    """Purpose-bound cache key ``K = (subject, grant, purpose, consent_epoch)``.

    ``purpose`` and ``consent_epoch`` are first-class key components: two
    requests that differ in purpose or consent epoch can never alias the same
    entry, which is what makes purpose isolation structural rather than
    advisory.
    """

    subject: str
    grant: str
    purpose: str
    consent_epoch: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.subject, REASON_KEY_MALFORMED, "key.subject")
        _require_non_empty_str(self.grant, REASON_KEY_MALFORMED, "key.grant")
        _require_non_empty_str(self.purpose, REASON_KEY_MALFORMED, "key.purpose")
        if isinstance(self.consent_epoch, bool) or not isinstance(self.consent_epoch, int):
            raise CacheControlError(
                REASON_KEY_MALFORMED, "key.consent_epoch must be a non-negative integer"
            )
        if self.consent_epoch < 0:
            raise CacheControlError(
                REASON_KEY_MALFORMED, "key.consent_epoch must be a non-negative integer"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "grant": self.grant,
            "purpose": self.purpose,
            "consent_epoch": self.consent_epoch,
        }

    @classmethod
    def from_mapping(cls, raw: Any) -> CacheKey:
        if not isinstance(raw, dict) or set(raw) != {
            "subject",
            "grant",
            "purpose",
            "consent_epoch",
        }:
            raise CacheControlError(
                REASON_KEY_MALFORMED,
                "key mapping must have exactly subject/grant/purpose/consent_epoch",
            )
        return cls(
            subject=raw["subject"],
            grant=raw["grant"],
            purpose=raw["purpose"],
            consent_epoch=raw["consent_epoch"],
        )


@dataclasses.dataclass(frozen=True)
class CacheEntry:
    """One cached context projection bound to its exact 4-tuple key.

    The context string lives in memory only; ``to_dict`` (the serialized view
    used for audit/telemetry) carries the byte count, never the bytes — no
    cached clinical content may leak into aggregated detail.
    """

    key: CacheKey
    context: str
    source_artifacts: frozenset[str]
    created_at_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.key.subject,
            "grant": self.key.grant,
            "purpose": self.key.purpose,
            "consent_epoch": self.key.consent_epoch,
            "context_bytes": len(self.context.encode("utf-8")),
            "source_artifacts": sorted(self.source_artifacts),
            "created_at_seconds": self.created_at_seconds,
        }


@dataclasses.dataclass(frozen=True)
class FetchResult:
    """Outcome of a read: a stable status plus the served entry (or none).

    ``context`` is non-empty ONLY for serving statuses (``HIT``/``RECOMPUTED``);
    every refusal carries ``""`` so no bytes can cross a refusal boundary.
    """

    status: str
    context: str
    entry: CacheEntry | None

    @property
    def served(self) -> bool:
        return self.status in SERVING_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "context_bytes": len(self.context.encode("utf-8")),
            "entry": self.entry.to_dict() if self.entry is not None else None,
        }


@dataclasses.dataclass(frozen=True)
class InvalidationReport:
    """Audit record of one ``revoke(subject)`` invalidation event."""

    subject: str
    epoch_before: int
    epoch_after: int
    removed_entry_count: int
    removed_purposes: tuple[str, ...]
    removed_keys: tuple[dict[str, Any], ...]
    already_revoked: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "epoch_before": self.epoch_before,
            "epoch_after": self.epoch_after,
            "removed_entry_count": self.removed_entry_count,
            "removed_purposes": list(self.removed_purposes),
            "removed_keys": [dict(k) for k in self.removed_keys],
            "already_revoked": self.already_revoked,
        }


# ---------------------------------------------------------------------------
# Validation helpers (write path)
# ---------------------------------------------------------------------------


def _validate_source_artifacts(raw: Iterable[str] | frozenset[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, str | bytes) or not isinstance(raw, Iterable):
        raise CacheControlError(
            REASON_ARTIFACTS_MALFORMED, "source_artifacts must be an iterable of artifact ids"
        )
    items = tuple(raw)
    for item in items:
        _require_non_empty_str(item, REASON_ARTIFACTS_MALFORMED, "source artifact id")
    return frozenset(items)


def _validate_created_at_seconds(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CacheControlError(
            REASON_CREATED_AT_MALFORMED, "created_at_seconds must be a non-negative integer"
        )
    return value


# ---------------------------------------------------------------------------
# The purpose-bound cache
# ---------------------------------------------------------------------------


class PurposeBoundCache:
    """In-memory purpose-bound cache with whole-subject revocation semantics.

    State: ``_entries`` keyed by the exact 4-tuple, a per-subject consent epoch
    (rotated exactly once per revocation event), and a revocation tombstone set.
    All operations are pure/deterministic: the caller injects every logical
    instant and every recomputation; there is no hidden clock, randomness or I/O.
    """

    def __init__(self) -> None:
        self._entries: dict[CacheKey, CacheEntry] = {}
        self._epoch: dict[str, int] = {}
        self._revoked: set[str] = set()
        self._invalidation_events = 0

    # -- state queries ------------------------------------------------------

    def epoch_of(self, subject: str) -> int:
        """Current consent epoch of ``subject`` (0 until first rotation)."""
        return self._epoch.get(subject, 0)

    def is_revoked(self, subject: str) -> bool:
        return subject in self._revoked

    def live_keys(self, subject: str) -> tuple[CacheKey, ...]:
        """Every entry key currently installed for ``subject`` (any grant/purpose/epoch)."""
        return tuple(key for key in self._entries if key.subject == subject)

    def snapshot(self) -> dict[str, Any]:
        """JSON-serializable aggregate view (counts only; never context bytes)."""
        return {
            "version": CACHE_CONTROL_VERSION,
            "entries_total": len(self._entries),
            "invalidation_events": self._invalidation_events,
            "revoked_subjects": sorted(self._revoked),
            "epochs": dict(sorted(self._epoch.items())),
        }

    # -- write path (raises fail-closed CacheControlError) -------------------

    def put(
        self,
        key: CacheKey,
        context: str,
        *,
        source_artifacts: Iterable[str] | frozenset[str] | None = None,
        created_at_seconds: int = 0,
    ) -> CacheEntry:
        """Install ``context`` under the exact 4-tuple key.

        Refuses (raises) anything that would weaken the guarantee: a revoked
        subject may never receive a new entry at ANY epoch or purpose, and a
        write is only accepted at the subject's current consent epoch.
        """
        if not isinstance(key, CacheKey):
            raise CacheControlError(REASON_KEY_MALFORMED, "cache key must be a CacheKey")
        if not isinstance(context, str) or not context:
            raise CacheControlError(REASON_CONTEXT_MALFORMED, "context must be a non-empty string")
        artifacts = _validate_source_artifacts(source_artifacts)
        created_at = _validate_created_at_seconds(created_at_seconds)
        current = self.epoch_of(key.subject)
        if key.consent_epoch != current:
            raise CacheControlError(
                REASON_KEY_EPOCH_STALE,
                f"key epoch {key.consent_epoch} != current consent epoch {current} "
                f"for subject {key.subject!r}",
            )
        if key.subject in self._revoked:
            raise CacheControlError(
                REASON_REVOKED_SUBJECT,
                f"subject {key.subject!r} is revoked: no context may be cached for it "
                "at any purpose, grant or epoch",
            )
        entry = CacheEntry(
            key=key,
            context=context,
            source_artifacts=artifacts,
            created_at_seconds=created_at,
        )
        self._entries[key] = entry
        return entry

    def revoke(self, subject: str) -> InvalidationReport:
        """Invalidate EVERY entry for ``subject`` across all grants/purposes/epochs.

        Drops all matching entries, tombstones the subject and rotates the
        consent epoch exactly once per event. A repeat event is harmless (it
        removes nothing) but is still recorded for audit.
        """
        _require_non_empty_str(subject, REASON_SUBJECT_MALFORMED, "subject")
        epoch_before = self.epoch_of(subject)
        removed = [key for key in self._entries if key.subject == subject]
        removed_purposes = tuple(sorted({key.purpose for key in removed}))
        removed_keys = tuple(key.to_dict() for key in removed)
        for key in removed:
            del self._entries[key]
        already_revoked = subject in self._revoked
        self._revoked.add(subject)
        self._epoch[subject] = epoch_before + 1
        self._invalidation_events += 1
        return InvalidationReport(
            subject=subject,
            epoch_before=epoch_before,
            epoch_after=epoch_before + 1,
            removed_entry_count=len(removed),
            removed_purposes=removed_purposes,
            removed_keys=removed_keys,
            already_revoked=already_revoked,
        )

    # -- read path (returns refusal statuses; never raises for input state) --

    def get(self, key: CacheKey, *, requesting_purpose: str | None = None) -> FetchResult:
        """Fetch the entry bound to ``key`` — and nothing else.

        Refusal order (each step returns without serving any bytes):
        1. ``KEY_MALFORMED`` — non-CacheKey key or malformed requesting_purpose;
        2. ``EPOCH_STALE`` — the key is not bound to the subject's current
           consent epoch (covers every pre-rotation key after a revocation);
        3. ``REVOKED_SUBJECT`` — the tombstone: even a current-epoch key for a
           revoked subject is refused, so a forgotten entry can never be served;
        4. ``PURPOSE_MISMATCH`` — the requesting purpose differs from the key's
           purpose component (explicit cross-purpose read refusal);
        5. ``CACHE_MISS`` — no entry under the exact key.
        """
        if not isinstance(key, CacheKey):
            return FetchResult(REASON_KEY_MALFORMED, "", None)
        if requesting_purpose is not None and (
            not isinstance(requesting_purpose, str) or not requesting_purpose
        ):
            return FetchResult(REASON_KEY_MALFORMED, "", None)
        if key.consent_epoch != self.epoch_of(key.subject):
            return FetchResult(REASON_EPOCH_STALE, "", None)
        if key.subject in self._revoked:
            return FetchResult(REASON_REVOKED_SUBJECT, "", None)
        if requesting_purpose is not None and requesting_purpose != key.purpose:
            return FetchResult(REASON_PURPOSE_MISMATCH, "", None)
        entry = self._entries.get(key)
        if entry is None:
            return FetchResult(REASON_CACHE_MISS, "", None)
        return FetchResult(REASON_HIT, entry.context, entry)

    def recompute_or_fetch(
        self,
        key: CacheKey,
        recompute: Callable[[CacheKey], str],
        *,
        requesting_purpose: str | None = None,
    ) -> FetchResult:
        """Serve from cache or replace the stale line with authorized recomputation.

        The injected ``recompute`` callable is invoked ONLY after every refusal
        check passes (authorized purpose, current epoch, non-revoked subject);
        a refused request never triggers recomputation, so no bytes are
        produced for a revoked subject under any purpose. On a miss the fresh
        context is installed under the exact key and returned as ``RECOMPUTED``.
        """
        probe = self.get(key, requesting_purpose=requesting_purpose)
        if probe.status != REASON_CACHE_MISS:
            return probe
        if not callable(recompute):
            raise CacheControlError(REASON_RECOMPUTE_MALFORMED, "recompute must be callable")
        context = recompute(key)
        if not isinstance(context, str) or not context:
            raise CacheControlError(
                REASON_RECOMPUTE_MALFORMED,
                "recompute must return a non-empty context string; a cache must never "
                "invent or serve empty content",
            )
        entry = self.put(key, context)
        return FetchResult(REASON_RECOMPUTED, context, entry)


# ---------------------------------------------------------------------------
# Executable revocation-completeness proof
# ---------------------------------------------------------------------------


def assert_revocation_complete(cache: PurposeBoundCache, subject: str) -> dict[str, Any]:
    """Prove that NO live entry for ``subject`` remains anywhere in the cache.

    Scans the actual entry store (all grants, purposes and epochs) and raises
    :class:`RevocationLeakError` naming every surviving key if any entry for
    the subject is still installed — this is the completeness proof that turns
    "revoke" from a promise into a checked invariant. Returns a JSON-
    serializable report on success.
    """
    if not isinstance(cache, PurposeBoundCache):
        raise CacheControlError(REASON_CACHE_MALFORMED, "cache must be a PurposeBoundCache")
    _require_non_empty_str(subject, REASON_SUBJECT_MALFORMED, "subject")
    live = cache.live_keys(subject)
    if live:
        raise RevocationLeakError(
            REASON_REVOCATION_LEAK,
            f"{len(live)} live cache entry(ies) remain for subject {subject!r}: "
            f"{[key.to_dict() for key in live]}",
        )
    return {
        "complete": True,
        "subject": subject,
        "live_entry_count": 0,
        "subject_was_revoked": cache.is_revoked(subject),
        "version": CACHE_CONTROL_VERSION,
    }
