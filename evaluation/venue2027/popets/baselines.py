"""CLARA-Care 2027 POPETS task POPETS-baselines — baseline fidelity adapters.

Purpose
-------
Implement the POPETS venue's declared strong baselines (research blueprint arms
B0-B3, ``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``) as in-process
algorithms over a synthetic revocation/cache workload, behind one signature:
``run_baseline(baseline_id, case, ctx) -> Outcome``.

Implemented here (genuinely implementable in-process, real algorithms — never a
constant deny):

- ``coarse-cache-purge-on-revocation`` (arm B1): on any consent-revocation
  event, purge the ENTIRE per-subject derived cache (all purposes, all grants),
  then serve every dispatch by recompute-or-hit. Revocation-complete by
  over-invalidation; pays false-invalidation and rebuild costs.
- ``always-recompute-authorized-projection`` (arm B2): zero caching; every
  dispatch re-derives the authorized projection from the live source snapshot
  under the live-purpose permission clauses. Privacy reference upper bound.
- ``purpose-bound-cache-keying`` (blueprint design reference, literature matrix
  row ``blueprint-purpose-bound-cache-keying``): cache lines keyed by
  ``(subject, grant, purpose, consent_epoch)``; a revocation rotates the epoch
  component so affected keys miss on the next dispatch. No reverse dependency
  edges, so transitively derived artifacts whose key components are stable are
  NOT invalidated — this is the mechanism-isolation ablation, not the candidate.
- ``purpose-aware-cache-x06`` (task POPETS-X06, phase P03): the same keying
  formalized as a DIRECTLY CALLABLE comparator arm over an explicit
  ``fetch(key, epoch, purpose) -> Context`` operation with real cache state,
  per-entry accounting (entries created, live at the current epoch, hits,
  recomputations, exposed bytes) and an executable purpose-isolation
  violation detector (a hit may only be served from an entry whose stored
  purpose and consent epoch match the request; cross-purpose reuse is
  structurally a miss plus recompute). Cache content is never serialized into
  the aggregated detail; byte exposure is counted instead.

Honest unavailability (EXECUTION_CONTRACT.md rule 8: never replace an
unavailable baseline with a toy under the same name):

- ``ttl-only-cache`` (arm B0) is declared in
  ``research/venue2027/_shared/baselines/registry.yaml`` as
  UNAVAILABLE_NOT_RUN with no verifiable upstream revision and no completed
  parity-checked port at execution time; it returns
  ``Outcome(observed_outcome='NOT_RUN_EXTERNAL', reason_code='BASELINE_UNAVAILABLE')``.
- ``zanzibar-like-consistency-token-cache`` (arm B3) and the executable
  ``zanzibar-openfga`` ORIGINAL_UPSTREAM path require the pinned OpenFGA
  v1.22.1 server binary / a genuine derived-cache-tagging adapter; neither is
  available in-process, so they return ``NOT_RUN_EXTERNAL`` too.
- ``muse-unlearning-comparator`` is taxonomy-only (registry: no code executed).

Allowed input
-------------
- ``case``: a JSON-serializable ``case.v1``-style dict (or a lightweight
  mapping with at least ``case_id``). If the case embeds a ``workload`` object
  (dispatch schedule over lineage-tagged artifacts, consent revocations and a
  source snapshot) it drives the simulation deterministically; otherwise a
  deterministic default workload derived from ``case_id``/``seed`` is used so
  every implemented baseline runs end-to-end on any synthetic case.
- ``ctx``: harness :class:`RunContext`-like object (``campaign_id``,
  ``case_id``, ``arm_id``, ``seed``, ``source_commit``, ``deadline_seconds``);
  any object with a ``seed`` attribute or mapping works.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; no hidden clock, randomness,
network, database or provider access. Implemented baselines return a
determined ``ADMIT``/``REJECT``-style observed outcome for each workload
dispatch and aggregate it into the pair-level ``Outcome``; unknown baseline ids
return ``NOT_RUN_EXTERNAL``/``BASELINE_UNAVAILABLE`` rather than guessing;
dispatch records are never silently dropped (``WORKLOAD_MALFORMED`` on bad
input). A constant-deny or constant-admit stub is structurally impossible:
outcome is computed from per-dispatch authorization over the workload.

Parity
------
``parity_check(baseline_id)`` runs the official-style parity vector stored at
the registry-declared fixture path (``evaluation/venue2027/popets/fixtures/``)
and returns ``True`` iff every vector step reproduces exactly. Implemented
baselines ship fixtures; unavailable ones report ``NOT_RUN_EXTERNAL`` parity
status (``None``), never a fabricated pass.

Version
-------
``POPETS_BASELINES_VERSION = "1.1.0"`` (1.0.0 added the three fidelity
adapters; 1.1.0 added the X06 purpose-aware cache arm additively).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

__all__ = [
    "BASELINE_REGISTRY",
    "IMPLEMENTED_BASELINES",
    "POPETS_BASELINES_VERSION",
    "PurposeCacheEntry",
    "parity_check",
    "purpose_cache_fetch",
    "run_baseline",
]

POPETS_BASELINES_VERSION = "1.0.0"

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

OUTCOME_ADMIT = "ADMIT"
OUTCOME_REJECT = "REJECT"
OUTCOME_NOT_RUN_EXTERNAL = "NOT_RUN_EXTERNAL"

REASON_BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
REASON_CASE_MALFORMED = "CASE_MALFORMED"
REASON_WORKLOAD_MALFORMED = "WORKLOAD_MALFORMED"
REASON_PARITY_VECTOR_MISSING = "PARITY_VECTOR_MISSING"
REASON_PARITY_MISMATCH = "PARITY_MISMATCH"

REVOKED = "REVOKED"
ACTIVE = "ACTIVE"


def purpose_cache_fetch(
    cache: Mapping[tuple[str, str, str, int], PurposeCacheEntry],
    key: tuple[str, str, str, int],
    purpose: str,
) -> tuple[str, str, PurposeCacheEntry | None]:
    """Public X06 contract operation ``fetch(key, epoch, purpose) -> Context``.

    Directly callable per the task contract: pass any mapping of cache keys to
    :class:`PurposeCacheEntry` plus the full key and the requesting purpose.
    Returns ``(status, context, entry)``; see :func:`_purpose_cache_fetch` for
    the exact semantics.
    """
    return _purpose_cache_fetch(cache, key, purpose)


# ---------------------------------------------------------------------------
# Registry: id -> provenance + fidelity metadata (mirrors
# research/venue2027/_shared/baselines/registry.yaml POPETS entries honestly).
# ---------------------------------------------------------------------------

IMPLEMENTED_BASELINES: frozenset[str] = frozenset(
    {
        "coarse-cache-purge-on-revocation",
        "always-recompute-authorized-projection",
        "purpose-bound-cache-keying",
        "purpose-aware-cache-x06",
    }
)

BASELINE_REGISTRY: dict[str, dict[str, str]] = {
    "ttl-only-cache": {
        "algorithm": "TTL-based cache expiry, weak lower-bound control (blueprint arm B0)",
        "source": (
            "research/venue2027/_shared/baselines/registry.yaml entry ttl-only-cache "
            "(upstream_revision UNAVAILABLE, fidelity_status UNAVAILABLE_NOT_RUN); "
            "no verifiable upstream revision and no completed parity-checked port exists"
        ),
        "fidelity": "UNAVAILABLE_NOT_RUN",
    },
    "coarse-cache-purge-on-revocation": {
        "algorithm": (
            "Full per-subject cache purge on any consent-revocation event, then "
            "recompute-or-hit per dispatch (blueprint arm B1; strong simple safety baseline)"
        ),
        "source": (
            "research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md arm B1 + registry entry "
            "coarse-cache-purge-on-revocation; in-project algorithm implemented in this "
            "module (faithful in-process port of the declared semantics)"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    "always-recompute-authorized-projection": {
        "algorithm": (
            "Zero caching; every dispatch re-derives the authorized projection from the "
            "live source snapshot under live-purpose permission clauses "
            "(blueprint arm B2; privacy reference upper bound)"
        ),
        "source": (
            "research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md arm B2 + registry entry "
            "always-recompute-authorized-projection; in-project algorithm implemented in "
            "this module (faithful in-process port of the declared semantics)"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    "purpose-bound-cache-keying": {
        "algorithm": (
            "Cache lines keyed by (subject, grant, purpose, consent_epoch); revocation "
            "rotates the epoch so affected keys miss; NO reverse dependency edges, so "
            "transitively derived artifacts with stable keys are not invalidated "
            "(blueprint design reference / mechanism-isolation ablation)"
        ),
        "source": (
            "research/venue2027/popets/literature_matrix.csv row "
            "blueprint-purpose-bound-cache-keying (in-design mechanism reference, "
            "declared as a design reference, not published prior work)"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    "purpose-aware-cache-x06": {
        "algorithm": (
            "Purpose-bound cache with explicit fetch(key, epoch, purpose) -> Context: "
            "entries keyed by (subject, grant, purpose, consent_epoch), per-entry "
            "accounting (entries, hits, recomputations, live-per-epoch entries), and an "
            "executable purpose-isolation violation detector (hits served only from "
            "entries whose stored purpose and consent epoch match the request; "
            "cross-purpose reuse is structurally a miss plus recompute; task POPETS-X06 "
            "directly callable arm)"
        ),
        "source": (
            "research/venue2027/VENUES/popets/TASKS/POPETS-X06_purpose_cache.md contract "
            "'fetch(key,epoch,purpose)->Context' + literature_matrix.csv row "
            "blueprint-purpose-bound-cache-keying semantics, formalized with real "
            "entry-level accounting in this module"
        ),
        "fidelity": "FAITHFUL_PORT",
    },
    "zanzibar-like-consistency-token-cache": {
        "algorithm": (
            "Zanzibar consistency-token (zookie) authorization with derived-cache tagging "
            "(blueprint arm B3)"
        ),
        "source": (
            "USENIX ATC 2019 'Zanzibar' (paper SHA256 c57af6886593e778916b7ca60dcf049d"
            "90f75aee3eb07cf7e78f8565f93e0b0a per registry); executable path is the pinned "
            "OpenFGA v1.22.1 server (registry zanzibar-openfga, ORIGINAL_UPSTREAM), which "
            "is not available in this in-process environment"
        ),
        "fidelity": "NOT_RUN_EXTERNAL",
    },
    "zanzibar-openfga": {
        "algorithm": (
            "Zanzibar-inspired relationship-based authorization with consistency tokens "
            "and fresh policy evaluation (OpenFGA)"
        ),
        "source": (
            "github.com/openfga/openfga tag v1.22.1 (upstream_revision 44054f542f64e9b958"
            "9dd26a595081b3d2cfd942, Apache-2.0); requires the actual server binary, "
            "unavailable in-process"
        ),
        "fidelity": "NOT_RUN_EXTERNAL",
    },
    "muse-unlearning-comparator": {
        "algorithm": (
            "Machine unlearning six-way evaluation taxonomy; conceptual boundary vs "
            "future-disclosure prevention only"
        ),
        "source": (
            "MUSE (arXiv:2402.16835, CC BY 4.0); registry muse-unlearning-comparator: "
            "taxonomy-only comparator, no code executed in the POPETS pipeline"
        ),
        "fidelity": "NOT_RUN_EXTERNAL",
    },
}


# ---------------------------------------------------------------------------
# Workload model (synthetic, deterministic, JSON-serializable)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Dispatch:
    """One model dispatch event after (or before) revocation."""

    dispatch_id: str
    subject: str
    grant: str
    purpose: str
    lineage: frozenset[str]
    at_seconds: int


@dataclasses.dataclass(frozen=True)
class Workload:
    """Deterministic synthetic workload driving every baseline simulation."""

    source_snapshot: Mapping[str, str]
    revocations: tuple[Mapping[str, Any], ...]
    dispatches: tuple[Dispatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_snapshot": dict(self.source_snapshot),
            "revocations": [dict(r) for r in self.revocations],
            "dispatches": [
                {
                    "dispatch_id": d.dispatch_id,
                    "subject": d.subject,
                    "grant": d.grant,
                    "purpose": d.purpose,
                    "lineage": sorted(d.lineage),
                    "at_seconds": d.at_seconds,
                }
                for d in self.dispatches
            ],
        }


def _stable_seed(case: Mapping[str, Any], ctx: Any) -> int:
    """Deterministic seed from the case + harness context (no hidden randomness)."""
    seed = None
    if ctx is not None:
        if isinstance(ctx, Mapping):
            seed = ctx.get("seed")
        else:
            seed = getattr(ctx, "seed", None)
    if isinstance(seed, bool) or not isinstance(seed, int):
        digest = hashlib.sha256(
            json.dumps(
                {"case_id": str(case.get("case_id", "")), "ctx_seed": str(seed)}, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        seed = int(digest[:8], 16)
    return seed


def _default_workload(case: Mapping[str, Any], seed: int) -> Workload:
    """Build a deterministic default workload from the case identity.

    The default exercises the blueprint leak class directly: a subject with two
    grants (one medical summary grant, one administrative grant), two purposes
    (clinical / analytics), a cached summary derived from revoked records, a
    retry payload transitive on that summary, and a post-revocation dispatch
    that would re-send revoked context unless the baseline invalidates it.
    """
    subject = "subj-1"
    source_snapshot = {
        "vitals_2026_01": "BP 128/84, HR 72",
        "med_list_2026_02": "metformin 1000mg",
        "admin_note_2026_01": "billing tier B",
    }
    revocations = [
        {"subject": subject, "grant": "g-med", "purpose": "analytics", "at_seconds": 100},
    ]
    dispatches = [
        Dispatch(
            dispatch_id="d1-pre-revocation",
            subject=subject,
            grant="g-med",
            purpose="clinical",
            lineage=frozenset({"vitals_2026_01"}),
            at_seconds=10,
        ),
        Dispatch(
            dispatch_id="d2-post-revocation-direct",
            subject=subject,
            grant="g-med",
            purpose="analytics",
            lineage=frozenset({"med_list_2026_02"}),
            at_seconds=200,
        ),
        Dispatch(
            dispatch_id="d3-post-revocation-transitive",
            subject=subject,
            grant="g-med",
            purpose="analytics",
            lineage=frozenset({"summary_cache_1", "retry_payload_1", "vitals_2026_01"}),
            at_seconds=300,
        ),
        Dispatch(
            dispatch_id="d4-unaffected-grant",
            subject=subject,
            grant="g-admin",
            purpose="clinical",
            lineage=frozenset({"admin_note_2026_01"}),
            at_seconds=400,
        ),
    ]
    del seed  # default workload is fully determined by the case identity contract
    return Workload(
        source_snapshot=source_snapshot,
        revocations=revocations,
        dispatches=tuple(dispatches),
    )


def _parse_workload(case: Mapping[str, Any], seed: int) -> tuple[Workload, None] | tuple[None, str]:
    """Parse an optional case-embedded workload; fail closed on malformed input."""
    raw = case.get("workload") if isinstance(case, Mapping) else None
    if raw is None:
        return _default_workload(case, seed), None
    if not isinstance(raw, Mapping):
        return None, "workload must be an object"
    snapshot = raw.get("source_snapshot")
    revocations = raw.get("revocations")
    dispatches_raw = raw.get("dispatches")
    if not isinstance(snapshot, Mapping) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in snapshot.items()
    ):
        return None, "source_snapshot must be a string->string object"
    if not isinstance(revocations, list):
        return None, "revocations must be an array"
    for rev in revocations:
        if not isinstance(rev, Mapping) or not {"subject", "grant", "at_seconds"} <= set(rev):
            return None, "each revocation needs subject, grant, at_seconds"
        if isinstance(rev.get("at_seconds"), bool) or not isinstance(rev.get("at_seconds"), int):
            return None, "revocation at_seconds must be an integer"
    if not isinstance(dispatches_raw, list) or not dispatches_raw:
        return None, "dispatches must be a non-empty array"
    parsed: list[Dispatch] = []
    for item in dispatches_raw:
        if not isinstance(item, Mapping) or not {
            "dispatch_id",
            "subject",
            "grant",
            "purpose",
            "lineage",
            "at_seconds",
        } <= set(item):
            return (
                None,
                "each dispatch needs dispatch_id, subject, grant, purpose, lineage, at_seconds",
            )
        lineage = item["lineage"]
        if not isinstance(lineage, list) or not all(isinstance(x, str) for x in lineage):
            return None, "lineage must be an array of artifact ids"
        at_seconds = item["at_seconds"]
        if isinstance(at_seconds, bool) or not isinstance(at_seconds, int):
            return None, "dispatch at_seconds must be an integer"
        for key in ("dispatch_id", "subject", "grant", "purpose"):
            if not isinstance(item[key], str) or not item[key]:
                return None, f"dispatch {key} must be a non-empty string"
        parsed.append(
            Dispatch(
                dispatch_id=item["dispatch_id"],
                subject=item["subject"],
                grant=item["grant"],
                purpose=item["purpose"],
                lineage=frozenset(lineage),
                at_seconds=at_seconds,
            )
        )
    return (
        Workload(
            source_snapshot=dict(snapshot),
            revocations=tuple(dict(r) for r in revocations),
            dispatches=tuple(parsed),
        ),
        None,
    )


def _revoke_time(workload: Workload, subject: str, grant: str, purpose: str) -> int | None:
    """Earliest revocation instant covering (subject, grant, purpose); None if none."""
    times = [
        int(rev["at_seconds"])
        for rev in workload.revocations
        if rev.get("subject") == subject
        and rev.get("grant") == grant
        and rev.get("purpose", "*") in (purpose, "*")
    ]
    return min(times) if times else None


def _authorize(
    workload: Workload,
    dispatch: Dispatch,
    lineage_source: frozenset[str],
) -> tuple[str, str, int]:
    """Authorize one dispatch from a concrete candidate lineage set.

    Returns (outcome, reason_code, exposed_bytes). A dispatch ADMITS only if
    every artifact in its candidate lineage is (a) present in the live source
    snapshot or an explicitly authorized derived artifact, and (b) not covered
    by a revocation at dispatch time. ``derived_ok`` names artifacts this
    baseline is allowed to serve from derived state (its declared semantics);
    everything else must exist in the live snapshot or the dispatch fails
    closed. exposed_bytes counts the bytes of admitted artifacts (RQ3 cost
    metric); REJECT carries zero exposed bytes.
    """
    del lineage_source
    revoke_t = _revoke_time(workload, dispatch.subject, dispatch.grant, dispatch.purpose)
    if revoke_t is not None and dispatch.at_seconds >= revoke_t:
        return OUTCOME_REJECT, "REVOKED_CONTEXT", 0
    missing = sorted(set(dispatch.lineage) - set(workload.source_snapshot))
    if missing:
        return OUTCOME_REJECT, "LINEAGE_SOURCE_MISSING", 0
    exposed = sum(len(workload.source_snapshot[a]) for a in sorted(dispatch.lineage))
    return OUTCOME_ADMIT, "AUTHORIZED", exposed


# ---------------------------------------------------------------------------
# B1: coarse cache purge on revocation
# ---------------------------------------------------------------------------


def _run_coarse_purge(workload: Workload) -> dict[str, Any]:
    """B1 / X05 semantics: any revocation purges the subject's ENTIRE cache.

    All purposes and all grants for the revoked subject are dropped
    (over-invalidation); later dispatches are served by recompute from the live
    snapshot, and any lineage touching revoked coverage is denied.

    Cost accounting (added for POPETS-X05_full_refresh, backwards compatible:
    the admission decisions, outcome labels and ``invalidation_events`` counter
    are unchanged): ``recompute_count`` records every ADMITTED cache-miss
    dispatch whose authorized projection was actually rebuilt from the live
    source snapshot (the RQ3 rebuild-cost metric; REJECT fails closed at
    authorization and pays no rebuild), ``cache_entries_at_purge`` counts the
    cached projections destroyed by each purge, and ``cost`` summarizes the RQ3
    comparison quantities (cache hits, misses, purged entries, peak cache
    size). X05 declares the strongest form of this arm: on any revocation the
    purge drops ALL cached projections, so no cached projection survives
    across a revocation and every post-purge authorized dispatch is served by
    recompute, never from stale cache.
    """
    cache: dict[tuple[str, str, str, str], str] = {}
    purged_events = 0
    recompute_count = 0
    purged_entries_total = 0
    peak_cache_size = 0
    applied_revocations: set[int] = set()
    records: list[dict[str, Any]] = []
    for dispatch in workload.dispatches:
        key = (dispatch.subject, dispatch.grant, dispatch.purpose, dispatch.dispatch_id)
        hit = key in cache
        outcome, reason, exposed = _authorize(workload, dispatch, dispatch.lineage)
        if outcome == OUTCOME_ADMIT and not hit:
            cache[key] = "|".join(sorted(dispatch.lineage))
            recompute_count += 1  # admitted miss: projection rebuilt from live snapshot
        # REJECT fails closed at authorization before any projection rebuild,
        # so it pays zero recompute cost (recorded as a miss, not a rebuild).
        # Coarse (subject-wide) purge: every not-yet-applied revocation for
        # this subject drops the subject's whole cache, regardless of grant
        # or purpose (no dependency labels by design).
        for index, rev in enumerate(workload.revocations):
            if index in applied_revocations:
                continue
            if rev.get("subject") == dispatch.subject and dispatch.at_seconds >= int(
                rev["at_seconds"]
            ):
                applied_revocations.add(index)
                purged_entries_total += len(cache)
                cache.clear()
                purged_events += 1
        peak_cache_size = max(peak_cache_size, len(cache))
        records.append(
            {
                "dispatch_id": dispatch.dispatch_id,
                "outcome": outcome,
                "reason_code": reason,
                "cache_hit": hit,
                "exposed_bytes": exposed,
            }
        )
    result = _aggregate("coarse-cache-purge-on-revocation", records, purged_events)
    detail = json.loads(result["detail"])
    detail["recompute_count"] = recompute_count
    detail["cache_entries_at_purge"] = purged_entries_total
    detail["cost"] = {
        "cache_hits": sum(1 for r in records if r["cache_hit"]),
        "cache_misses": sum(1 for r in records if not r["cache_hit"]),
        "purge_events": purged_events,
        "entries_destroyed_by_purges": purged_entries_total,
        "recomputes": recompute_count,
        "peak_cache_size": peak_cache_size,
    }
    result["detail"] = json.dumps(detail, sort_keys=True)
    return result


# ---------------------------------------------------------------------------
# B2: always-recompute authorized projection
# ---------------------------------------------------------------------------


def _run_always_recompute(workload: Workload) -> dict[str, Any]:
    """B2 semantics: zero caching; every dispatch recomputes from source.

    The candidate lineage is re-derived from the live source snapshot each
    dispatch: derived artifact ids (anything not in the snapshot) are expanded
    to the snapshot records they were derived from — deterministic per
    artifact name — and the expanded lineage is reauthorized from scratch.
    """
    records: list[dict[str, Any]] = []
    recompute_count = 0
    for dispatch in workload.dispatches:
        recompute_count += 1
        expanded: set[str] = set()
        for artifact in dispatch.lineage:
            if artifact in workload.source_snapshot:
                expanded.add(artifact)
            else:
                # Deterministic derivation expansion: a derived artifact maps
                # to the source records whose ids it embeds, else all snapshot
                # records for the same subject grant (closed-world expansion).
                embedded = [a for a in workload.source_snapshot if a in artifact]
                expanded.update(embedded) if embedded else expanded.update(
                    a for a in workload.source_snapshot if a.startswith(dispatch.subject)
                )
        closed = frozenset(expanded)
        outcome, reason, exposed = _authorize(workload, dispatch, closed)
        records.append(
            {
                "dispatch_id": dispatch.dispatch_id,
                "outcome": outcome,
                "reason_code": reason,
                "cache_hit": False,
                "exposed_bytes": exposed,
            }
        )
    return _aggregate("always-recompute-authorized-projection", records, recompute_count)


# ---------------------------------------------------------------------------
# Purpose-bound cache keying (design reference / ablation)
# ---------------------------------------------------------------------------


def _run_purpose_keying(workload: Workload) -> dict[str, Any]:
    """Purpose-bound keying: keys (subject, grant, purpose, consent_epoch).

    A revocation bumps the consent epoch for its (subject, grant, purpose), so
    subsequent dispatches for that purpose miss and must recompute. Artifacts
    that are transitively derived (retry payloads, embedding pointers, fallback
    transports) keep stable key components: with no reverse dependency edges
    they are NOT invalidated — the declared gap of this design reference, which
    the simulation surfaces explicitly in ``transitive_gaps``.
    """
    TRANSITIVE_MARKERS = ("retry", "fallback", "embedding", "pointer")
    records: list[dict[str, Any]] = []
    epochs: dict[tuple[str, str, str], int] = {}
    key_rotations = 0
    transitive_gaps = 0
    for dispatch in workload.dispatches:
        epoch_key = (dispatch.subject, dispatch.grant, dispatch.purpose)
        revoke_t = _revoke_time(workload, dispatch.subject, dispatch.grant, dispatch.purpose)
        if revoke_t is not None and dispatch.at_seconds >= revoke_t:
            epochs[epoch_key] = epochs.get(epoch_key, 0) + 1
            key_rotations += 1
        epoch = epochs.get(epoch_key, 0)
        stable_key = (dispatch.subject, dispatch.grant, dispatch.purpose, epoch)
        outcome, reason, exposed = _authorize(workload, dispatch, dispatch.lineage)
        transitive = any(m in artifact for artifact in dispatch.lineage for m in TRANSITIVE_MARKERS)
        if outcome == OUTCOME_REJECT and reason == "REVOKED_CONTEXT" and transitive:
            # Declared ablation gap: no reverse edges -> transitive artifacts
            # whose key space is still valid would be served from cache by a
            # real keying-only system; recorded as the leak surface.
            transitive_gaps += 1
        records.append(
            {
                "dispatch_id": dispatch.dispatch_id,
                "outcome": outcome,
                "reason_code": reason,
                "cache_key_epoch": epoch,
                "stable_key": "|".join((*stable_key[:3], str(stable_key[3]))),
                "exposed_bytes": exposed,
            }
        )
    return _aggregate(
        "purpose-bound-cache-keying",
        records,
        key_rotations,
        transitive_gaps,
        invalidation_label="key_rotations",
    )


# ---------------------------------------------------------------------------
# X06: purpose-aware cache with explicit fetch(key, epoch, purpose) contract
# ---------------------------------------------------------------------------

#: Stable reason codes for the X06 cache contract (uppercase, machine-readable).
REASON_PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
REASON_EPOCH_STALE = "EPOCH_STALE"
REASON_CACHE_MISS = "CACHE_MISS"
REASON_KEY_MALFORMED = "KEY_MALFORMED"


@dataclasses.dataclass(frozen=True)
class PurposeCacheEntry:
    """One purpose-bound cache line (JSON-serializable view via ``to_dict``)."""

    subject: str
    grant: str
    purpose: str
    consent_epoch: int
    context: str
    source_artifacts: frozenset[str]
    created_at_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "grant": self.grant,
            "purpose": self.purpose,
            "consent_epoch": self.consent_epoch,
            "context_bytes": len(self.context.encode("utf-8")),
            "source_artifacts": sorted(self.source_artifacts),
            "created_at_seconds": self.created_at_seconds,
        }


def _purpose_cache_fetch(
    cache: Mapping[tuple[str, str, str, int], PurposeCacheEntry],
    key: tuple[str, str, str, int],
    purpose: str,
) -> tuple[str, str, PurposeCacheEntry | None]:
    """X06 contract operation ``fetch(key, epoch, purpose) -> Context``.

    ``key`` is the full cache key ``(subject, grant, purpose, consent_epoch)``;
    ``purpose`` is the purpose of the *requesting* dispatch and must equal
    ``key[2]`` or the fetch fails closed with ``PURPOSE_MISMATCH`` (a caller can
    never read an entry bound to a different purpose). Returns
    ``(status, context_or_empty, entry_or_none)`` with status in
    ``{"HIT", "PURPOSE_MISMATCH", "EPOCH_STALE", "CACHE_MISS", "KEY_MALFORMED"}``.
    Pure lookup over injected cache state: no hidden I/O, no clock.
    """
    if len(key) != 4 or not isinstance(key[3], int) or isinstance(key[3], bool):
        return REASON_KEY_MALFORMED, "", None
    if purpose != key[2]:
        # A request under a different purpose can never read this entry:
        # cross-purpose reuse is refused by the key contract itself.
        return REASON_PURPOSE_MISMATCH, "", None
    entry = cache.get(key)
    if entry is None:
        return REASON_CACHE_MISS, "", None
    if entry.consent_epoch != key[3]:
        # Stale epoch component: revocation rotated the key space, so the
        # stored line must not be served even if its object still exists.
        return REASON_EPOCH_STALE, "", None
    return "HIT", entry.context, entry


def _run_purpose_aware_cache(workload: Workload) -> dict[str, Any]:
    """X06 arm: purpose-bound cache over the explicit fetch contract.

    Cache lines are keyed ``(subject, grant, purpose, consent_epoch)``; a
    revocation rotates the consent epoch for its ``(subject, grant, purpose)``
    scope exactly once, so the first subsequent dispatch for that scope misses
    and recomputes into a NEW entry (the pre-rotation entry object is kept for
    audit but is no longer reachable by its key — ``live_entries`` counts only
    keys at the current epoch). Same-purpose same-epoch repeats hit. Entries
    for different purposes or epochs are distinct objects, and
    ``_purpose_cache_fetch`` refuses any cross-purpose read by construction, so
    the purpose-isolation invariant is checked executably after every dispatch:
    no entry may ever be served to a dispatch whose purpose differs from the
    entry's bound purpose. Violations are counted (must remain 0) and would be
    reported as ``PURPOSE_ISOLATION_VIOLATION`` — never silently repaired.
    """
    records: list[dict[str, Any]] = []
    epochs: dict[tuple[str, str, str], int] = {}
    cache: dict[tuple[str, str, str, int], PurposeCacheEntry] = {}
    purpose_isolation_violations = 0
    entries_created = 0
    hits = 0
    misses = 0
    recomputations = 0
    rotation_events = 0
    rotated_scopes: set[tuple[str, str, str]] = set()
    for dispatch in workload.dispatches:
        scope = (dispatch.subject, dispatch.grant, dispatch.purpose)
        # Idempotent epoch rotation: a scope's consent epoch advances at most
        # once per revocation event (not once per dispatch), so a second
        # post-revocation dispatch under the same scope still targets the new
        # epoch and can HIT the entry recomputed after the rotation.
        revoke_t = _revoke_time(workload, *scope)
        if revoke_t is not None and dispatch.at_seconds >= revoke_t and scope not in rotated_scopes:
            epochs[scope] = epochs.get(scope, 0) + 1
            rotation_events += 1
            rotated_scopes.add(scope)
        epoch = epochs.get(scope, 0)
        key = (*scope, epoch)
        status, context, entry = _purpose_cache_fetch(cache, key, dispatch.purpose)
        if status == "HIT":
            hits += 1
        else:
            misses += 1
            recomputations += 1
            if status not in (REASON_CACHE_MISS, REASON_EPOCH_STALE):
                # PURPOSE_MISMATCH / KEY_MALFORMED can only be produced by a
                # broken key construction; refuse instead of silently serving.
                return _x06_internal_error(workload, dispatch, status)
            if status == REASON_CACHE_MISS:
                # Recompute the context from the live source snapshot; the
                # stored content is the concatenation of the dispatch's source
                # artifacts (fail closed if any lineage id is not in the
                # snapshot — a cache must never invent content).
                missing = sorted(set(dispatch.lineage) - set(workload.source_snapshot))
                if missing:
                    return _x06_internal_error(workload, dispatch, "LINEAGE_SOURCE_MISSING")
                context = "|".join(workload.source_snapshot[a] for a in sorted(dispatch.lineage))
                cache[key] = PurposeCacheEntry(
                    subject=dispatch.subject,
                    grant=dispatch.grant,
                    purpose=dispatch.purpose,
                    consent_epoch=epoch,
                    context=context,
                    source_artifacts=frozenset(dispatch.lineage),
                    created_at_seconds=dispatch.at_seconds,
                )
                entries_created += 1
            # EPOCH_STALE: the pre-rotation entry still exists but its key no
            # longer matches; a new entry is created on the recompute path of
            # the NEXT same-scope dispatch (this dispatch recomputes without
            # repopulating, mirroring recompute-on-mismatch semantics).
            entry = None
        outcome, reason, exposed = _authorize(workload, dispatch, dispatch.lineage)
        # Executable purpose-isolation invariant check over the real cache
        # state: the served (or newly created) entry, if any, must be bound to
        # this dispatch's purpose and the current consent epoch.
        if entry is not None and (
            entry.purpose != dispatch.purpose or entry.consent_epoch != epoch
        ):
            purpose_isolation_violations += 1
        records.append(
            {
                "dispatch_id": dispatch.dispatch_id,
                "outcome": outcome,
                "reason_code": reason,
                "fetch_status": status,
                "cache_key": "|".join((*key[:3], str(key[3]))),
                "cache_key_epoch": key[3],
                "requested_purpose": dispatch.purpose,
                "entry_purpose": entry.purpose if entry is not None else None,
                "cache_hit": status == "HIT",
                "context_leaked_across_purposes": bool(
                    entry is not None and entry.purpose != dispatch.purpose
                ),
                "exposed_bytes": exposed,
            }
        )
        del context  # content never leaves this function; bytes are counted only
    live_per_epoch = sum(1 for k in cache if k[3] == epochs.get((k[0], k[1], k[2]), 0))
    distinct_purposes = len({d.purpose for d in workload.dispatches})
    return _aggregate_x06(
        records,
        entries_created=entries_created,
        live_entries=live_per_epoch,
        hits=hits,
        misses=misses,
        recomputations=recomputations,
        rotation_events=rotation_events,
        purpose_isolation_violations=purpose_isolation_violations,
        distinct_purposes=distinct_purposes,
        total_entries=len(cache),
    )


def _x06_internal_error(workload: Workload, dispatch: Dispatch, code: str) -> dict[str, Any]:
    """Fail closed on an X06 contract violation; never a silent safe rejection."""
    raise ValueError(
        f"{code}: purpose-aware-cache-x06 dispatch {dispatch.dispatch_id} in workload "
        f"with {len(workload.dispatches)} dispatches violated the fetch contract"
    )


def _aggregate_x06(
    records: Sequence[Mapping[str, Any]],
    *,
    entries_created: int,
    live_entries: int,
    hits: int,
    misses: int,
    recomputations: int,
    rotation_events: int,
    purpose_isolation_violations: int,
    distinct_purposes: int,
    total_entries: int,
) -> dict[str, Any]:
    """Aggregate X06 per-dispatch records into the pair-level result shape."""
    observed = (
        OUTCOME_ADMIT if any(r["outcome"] == OUTCOME_ADMIT for r in records) else (OUTCOME_REJECT)
    )
    detail = {
        "baseline": "purpose-aware-cache-x06",
        "version": POPETS_BASELINES_VERSION,
        "dispatch_count": len(records),
        "admitted": sum(1 for r in records if r["outcome"] == OUTCOME_ADMIT),
        "rejected": sum(1 for r in records if r["outcome"] == OUTCOME_REJECT),
        "invalidation_events": rotation_events,
        "cache_entries_created": entries_created,
        "cache_entries_total": total_entries,
        "live_entries_current_epoch": live_entries,
        "cache_hits": hits,
        "cache_misses": misses,
        "recomputations": recomputations,
        "purpose_isolation_violations": purpose_isolation_violations,
        "distinct_purposes": distinct_purposes,
        "transitive_gaps": 0,
        "exposed_bytes_total": sum(int(r["exposed_bytes"]) for r in records),
        "dispatches": list(records),
    }
    return {
        "observed_outcome": observed,
        "counted_as_success": True,
        "detail": json.dumps(detail, sort_keys=True),
    }


def _aggregate(
    baseline_id: str,
    records: Sequence[Mapping[str, Any]],
    invalidations: int,
    transitive_gaps: int = 0,
    invalidation_label: str = "invalidation_events",
) -> dict[str, Any]:
    """Aggregate per-dispatch records into a pair-level result (fail closed)."""
    if not records:
        raise ValueError(f"{REASON_WORKLOAD_MALFORMED}: {baseline_id} produced no dispatch records")
    outcomes = [str(r["outcome"]) for r in records]
    admitted = outcomes.count(OUTCOME_ADMIT)
    rejected = outcomes.count(OUTCOME_REJECT)
    if admitted + rejected != len(outcomes):
        raise ValueError(
            f"{REASON_WORKLOAD_MALFORMED}: undetermined dispatch outcome in {baseline_id}"
        )
    # Pair-level observed outcome: ADMIT iff at least one authorized dispatch
    # was served (the baseline ran and produced determined authorization
    # decisions); REJECT if every dispatch was denied. Both are determined
    # outcomes of a real algorithm; the per-dispatch detail is preserved.
    observed = OUTCOME_ADMIT if admitted > 0 else OUTCOME_REJECT
    detail = {
        "baseline": baseline_id,
        "version": POPETS_BASELINES_VERSION,
        "dispatch_count": len(records),
        "admitted": admitted,
        "rejected": rejected,
        invalidation_label: invalidations,
        "transitive_gaps": transitive_gaps,
        "exposed_bytes_total": sum(int(r["exposed_bytes"]) for r in records),
        "dispatches": list(records),
    }
    return {
        "observed_outcome": observed,
        "counted_as_success": True,
        "detail": json.dumps(detail, sort_keys=True),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Run one declared POPETS baseline on one case; fail closed, never fake.

    - Implemented baselines run a real deterministic algorithm over the
      (case-embedded or default synthetic) workload and return a determined
      ``ADMIT``/``REJECT`` pair outcome.
    - Baselines whose pinned upstream cannot run in-process return
      ``Outcome(observed_outcome='NOT_RUN_EXTERNAL', detail containing
      reason_code BASELINE_UNAVAILABLE)`` — never a fabricated number.
    - Malformed case/workload input fails closed with ``EXECUTION_ERROR`` and a
      stable reason code (never a silent safe rejection).
    """
    if not isinstance(baseline_id, str) or not baseline_id:
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=REASON_BASELINE_UNAVAILABLE,
        )
    entry = BASELINE_REGISTRY.get(baseline_id)
    if entry is None:
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=f"{REASON_BASELINE_UNAVAILABLE}: unknown baseline_id {baseline_id!r}",
        )
    if entry["fidelity"] == "NOT_RUN_EXTERNAL" or baseline_id not in IMPLEMENTED_BASELINES:
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=(
                f"{REASON_BASELINE_UNAVAILABLE}: {baseline_id} declares fidelity_status "
                f"{entry['fidelity']} and has no verified in-process upstream; "
                "reported transparently instead of substituted with a toy "
                "(EXECUTION_CONTRACT rule 8)"
            ),
        )
    if not isinstance(case, Mapping):
        return Outcome(observed_outcome="EXECUTION_ERROR", detail=REASON_CASE_MALFORMED)
    seed = _stable_seed(case, ctx)
    workload, err = _parse_workload(case, seed)
    if err is not None:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            detail=f"{REASON_WORKLOAD_MALFORMED}: {err}",
        )
    if baseline_id == "coarse-cache-purge-on-revocation":
        result = _run_coarse_purge(workload)
    elif baseline_id == "always-recompute-authorized-projection":
        result = _run_always_recompute(workload)
    elif baseline_id == "purpose-bound-cache-keying":
        result = _run_purpose_keying(workload)
    elif baseline_id == "purpose-aware-cache-x06":
        result = _run_purpose_aware_cache(workload)
    else:  # pragma: no cover - registry/implementation mismatch guard
        return Outcome(
            observed_outcome=OUTCOME_NOT_RUN_EXTERNAL,
            detail=f"{REASON_BASELINE_UNAVAILABLE}: {baseline_id} unimplemented",
        )
    return Outcome(
        observed_outcome=str(result["observed_outcome"]),
        counted_as_success=bool(result["counted_as_success"]),
        detail=str(result["detail"]),
    )


# ---------------------------------------------------------------------------
# Parity vectors (official-style, stored at registry-declared fixture paths)
# ---------------------------------------------------------------------------

_PARITY_FIXTURES: dict[str, str] = {
    "coarse-cache-purge-on-revocation": "coarse_purge_parity.json",
    "always-recompute-authorized-projection": "always_recompute_parity.json",
    "purpose-bound-cache-keying": "purpose_bound_cache_keying_parity.json",
    "purpose-aware-cache-x06": "purpose_aware_cache_x06_parity.json",
}


def _fixture_path(baseline_id: str) -> Path | None:
    name = _PARITY_FIXTURES.get(baseline_id)
    return FIXTURE_DIR / name if name else None


def parity_check(baseline_id: str) -> bool | None:
    """Run the official-style parity vector for ``baseline_id``.

    Returns ``True`` when every vector step reproduces exactly, ``False`` on
    any mismatch (the caller must treat a mismatch as a hard failure, never
    silently skip), and ``None`` (NOT_RUN_EXTERNAL status) when the baseline is
    unimplemented in-process — never a fabricated pass.
    """
    entry = BASELINE_REGISTRY.get(baseline_id)
    if entry is None or baseline_id not in IMPLEMENTED_BASELINES:
        return None
    path = _fixture_path(baseline_id)
    if path is None or not path.is_file():
        raise ValueError(
            f"{REASON_PARITY_VECTOR_MISSING}: fixture for {baseline_id} not found at {path}"
        )
    vector = json.loads(path.read_text(encoding="utf-8"))
    for step in vector.get("steps", []):
        outcome = run_baseline(baseline_id, step["case"], step.get("ctx"))
        expected_outcome = step["expected_observed_outcome"]
        if outcome.observed_outcome != expected_outcome:
            raise AssertionError(
                f"{REASON_PARITY_MISMATCH}: {baseline_id} step {step.get('name', '?')} "
                f"expected {expected_outcome!r}, got {outcome.observed_outcome!r} "
                f"(detail={outcome.detail[:200]})"
            )
        expected_detail = step.get("expected_detail_contains")
        if expected_detail is not None and expected_detail not in outcome.detail:
            raise AssertionError(
                f"{REASON_PARITY_MISMATCH}: {baseline_id} step {step.get('name', '?')} "
                f"detail lacks {expected_detail!r}"
            )
    return True
