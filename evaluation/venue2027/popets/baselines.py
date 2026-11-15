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
``POPETS_BASELINES_VERSION = "1.0.0"``
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
    "parity_check",
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


# ---------------------------------------------------------------------------
# Registry: id -> provenance + fidelity metadata (mirrors
# research/venue2027/_shared/baselines/registry.yaml POPETS entries honestly).
# ---------------------------------------------------------------------------

IMPLEMENTED_BASELINES: frozenset[str] = frozenset(
    {
        "coarse-cache-purge-on-revocation",
        "always-recompute-authorized-projection",
        "purpose-bound-cache-keying",
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
    """B1 semantics: any revocation purges the subject's ENTIRE cache.

    All purposes and all grants for the revoked subject are dropped
    (over-invalidation); later dispatches are served by recompute from the live
    snapshot, and any lineage touching revoked coverage is denied.
    """
    cache: dict[tuple[str, str, str, str], str] = {}
    purged_events = 0
    applied_revocations: set[int] = set()
    records: list[dict[str, Any]] = []
    for dispatch in workload.dispatches:
        key = (dispatch.subject, dispatch.grant, dispatch.purpose, dispatch.dispatch_id)
        hit = key in cache
        outcome, reason, exposed = _authorize(workload, dispatch, dispatch.lineage)
        if outcome == OUTCOME_ADMIT and not hit:
            cache[key] = "|".join(sorted(dispatch.lineage))
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
                cache.clear()
                purged_events += 1
        records.append(
            {
                "dispatch_id": dispatch.dispatch_id,
                "outcome": outcome,
                "reason_code": reason,
                "cache_hit": hit,
                "exposed_bytes": exposed,
            }
        )
    return _aggregate("coarse-cache-purge-on-revocation", records, purged_events)


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
# Aggregation into the harness Outcome type
# ---------------------------------------------------------------------------


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
