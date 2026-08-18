"""Domain-versioned freshness clocks for GLHS evidence and commitments (P9).

Freshness semantics
-------------------
A clinical fact carries several clocks.  The freshness clock resolves them in
fixed precedence:

1. ``source_observation_time`` (``observed_at``) - when the source was observed.
2. ``knowledge_time`` (``known_at``) - when the fact became known to CLARA.
3. ``last_verification_time`` (``verification_at``) - last explicit verification.
   ``GlhsEvidence`` has no such column, so this tier falls back to ``known_at``
   as the recorded verification proxy.
4. ``clinical_valid_time`` (``valid_from``) - the clinical validity anchor,
   used ONLY as a last resort.

An old clinical ``valid_from`` NEVER alone marks evidence stale when a fresher
observation or knowledge clock exists: the freshest available clock governs.

``FRESHNESS_CLOCK_VERSION`` versions the resolution rule set so a policy change
is distinguishable in audit output without changing snapshot digests.

Purity (P12)
------------
This module is a pure function of its input: it never reads or writes a
database session and never mutates the evidence-like value it inspects.
Canonical health state is written only by
``clara_api.glhs.commitment_gateway.apply_commitment_transition``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.risk import DOMAIN_POLICIES

FRESHNESS_CLOCK_VERSION = "glhs.freshness.v1"


class FreshnessClock(StrEnum):
    """Domain-versioned freshness clock identifiers, in resolution order."""

    SOURCE_OBSERVATION_TIME = "source_observation_time"
    KNOWLEDGE_TIME = "knowledge_time"
    LAST_VERIFICATION_TIME = "last_verification_time"
    CLINICAL_VALID_TIME = "clinical_valid_time"


def _value(evidence_like: Any, name: str) -> Any:
    if isinstance(evidence_like, Mapping):
        return evidence_like.get(name)
    return getattr(evidence_like, name, None)


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def resolve_freshness_clock(evidence_like: Any) -> tuple[FreshnessClock, datetime]:
    """Resolve the freshest available clock and its value.

    ``evidence_like`` may be a ``GlhsEvidence``/``HealthSourceReference`` ORM
    row, a reconstructed commitment dict, or any object/dict exposing
    ``observed_at`` / ``known_at`` / ``verification_at`` / ``valid_from``.
    """

    observed = _as_utc(_value(evidence_like, "observed_at"))
    if observed is not None:
        return FreshnessClock.SOURCE_OBSERVATION_TIME, observed
    known = _as_utc(_value(evidence_like, "known_at"))
    if known is not None:
        return FreshnessClock.KNOWLEDGE_TIME, known
    verified = _as_utc(_value(evidence_like, "verification_at"))
    if verified is not None:
        return FreshnessClock.LAST_VERIFICATION_TIME, verified
    # GlhsEvidence has no verification_at column; a recorded knowledge clock is
    # the closest verification proxy when one exists.
    if known is not None:
        return FreshnessClock.LAST_VERIFICATION_TIME, known
    valid = _as_utc(_value(evidence_like, "valid_from"))
    if valid is not None:
        return FreshnessClock.CLINICAL_VALID_TIME, valid
    raise GlhsInvariantError("evidence_freshness_time_unavailable")


@dataclass(frozen=True)
class FreshnessResult:
    fresh: bool
    freshness_clock: str
    clock_value: datetime
    max_age: timedelta
    stale_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "fresh": self.fresh,
            "freshness_clock": self.freshness_clock,
            "clock_value": self.clock_value.isoformat(),
            "max_age_seconds": int(self.max_age.total_seconds()),
            "stale_reason": self.stale_reason,
        }


def compute_freshness(
    evidence_like: Any, *, policy: Any, cutoff: datetime
) -> FreshnessResult:
    """Compute freshness of one evidence-like value under a domain policy.

    ``policy`` carries the domain ``max_age`` (``clara_api.glhs.risk``
    ``DOMAIN_POLICIES``).  ``cutoff`` is the point the fact must still be fresh
    at (the snapshot's valid-time cutoff, mirroring generic THSS ``as_of``).
    """

    clock, clock_value = resolve_freshness_clock(evidence_like)
    cutoff_utc = (
        cutoff.replace(tzinfo=UTC) if cutoff.tzinfo is None else cutoff.astimezone(UTC)
    )
    age = cutoff_utc - clock_value
    stale = age > policy.max_age
    stale_reason: str | None = None
    if stale:
        stale_reason = (
            f"clock={clock.value} value={clock_value.isoformat()} older than "
            f"max_age={int(policy.max_age.total_seconds() // 86400)}d at "
            f"cutoff={cutoff_utc.isoformat()}"
        )
    return FreshnessResult(
        fresh=not stale,
        freshness_clock=clock.value,
        clock_value=clock_value,
        max_age=policy.max_age,
        stale_reason=stale_reason,
    )


def freshness_for_commitment(
    item: Mapping[str, Any], *, cutoff: datetime | None = None
) -> FreshnessResult:
    """Compute freshness for one reconstructed commitment-visible item.

    The reconstructed commitment product state exposes its knowledge clock as
    ``anchor_known_time`` and its clinical validity anchor as
    ``anchor_valid_time``; both are accepted here.  Domain max-ages come from
    ``clara_api.glhs.risk.DOMAIN_POLICIES`` (medications 90d, allergies 365d,
    conditions 180d, observations 30d).  A fresh observation/knowledge clock
    keeps the commitment fresh even when the clinical anchor is old.
    """

    domain = _value(item, "domain")
    policy = DOMAIN_POLICIES.get(str(domain))
    if policy is None:
        raise GlhsInvariantError("commitment_freshness_domain_unknown")
    anchor_known = _value(item, "anchor_known_time")
    anchor_valid = _value(item, "anchor_valid_time")
    normalized: dict[str, object] = {
        "observed_at": _value(item, "observed_at"),
        "known_at": (
            anchor_known if anchor_known is not None else _value(item, "known_at")
        ),
        "verification_at": _value(item, "verification_at"),
        "valid_from": (
            anchor_valid if anchor_valid is not None else _value(item, "valid_from")
        ),
    }
    return compute_freshness(
        normalized,
        policy=policy,
        cutoff=cutoff if cutoff is not None else datetime.now(UTC),
    )
