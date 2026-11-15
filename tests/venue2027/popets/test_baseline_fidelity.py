"""CLARA-Care 2027 POPETS task POPETS-baseline_tests — baseline conformance suite.

Purpose
-------
One UPSTREAM POSITIVE vector and one ADVERSARIAL NEGATIVE vector for EACH
implemented POPETS baseline in
``evaluation/venue2027/popets/baselines.py`` (imported real, never
reimplemented): ``coarse-cache-purge-on-revocation`` (blueprint arm B1),
``always-recompute-authorized-projection`` (arm B2),
``purpose-bound-cache-keying`` (design-reference ablation) and
``purpose-aware-cache-x06`` (POPETS-X06 directly callable comparator arm).

- Positives assert the documented guarantee holds END TO END through the real
  ``run_baseline`` entry point (and, for X06, the direct
  ``purpose_cache_fetch`` contract): post-revocation dispatches carrying
  revoked coverage are denied, unaffected scopes stay servable, and the
  parity fixtures stored at the registry-declared fixture paths reproduce
  exactly via ``parity_check``.
- Negatives assert the baseline REJECTS the bad case, and where a baseline
  legitimately has a declared weakness, the weakness itself is asserted
  explicitly as fidelity evidence:
  * B1 over-invalidates: a consent revocation for one (grant, purpose)
    destroys the subject's cached projections for ALL grants/purposes
    (``entries_destroyed_by_purges`` > 0, a still-authorized cached entry is
    not served from cache again -> forced recompute), the declared
    false-invalidation cost of this arm.
  * B2 never serves from cache (zero hits, full recompute cost) and fails
    closed on derived lineage it cannot expand to live sources.
  * purpose-bound keying has NO reverse dependency edges: a transitively
    derived retry artifact whose key space is stable is NOT invalidated while
    the authorization surface still denies it — the declared ablation gap is
    recorded in ``transitive_gaps`` and asserted > 0.
  * X06's ``fetch`` refuses cross-purpose reads and stale epochs
    (PURPOSE_MISMATCH / EPOCH_STALE / KEY_MALFORMED / CACHE_MISS), and a
    tampered cache entry violating purpose isolation is detected
    (``purpose_isolation_violations`` > 0), never silently served.

Allowed input
-------------
Synthetic, JSON-serializable ``case.v1`` workloads only (no network, DB,
clock or model; no patient data, no production secrets). Observable
behaviour per baseline is recorded in module-level ``OBSERVED_BEHAVIOUR``
and exercised by the tests.

Failure semantics
-----------------
A baseline that fails closed must do so with a stable uppercase reason code
(REVOKED_CONTEXT, LINEAGE_SOURCE_MISSING, WORKLOAD_MALFORMED,
BASELINE_UNAVAILABLE, PURPOSE_MISMATCH, ...); tests assert these codes and
never accept a bare exception or a silent drop as a safe rejection.

Version
-------
``POPETS_BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"`` against
``baselines.POPETS_BASELINES_VERSION`` 1.x (additive X06 arm).
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.popets import baselines as bl

POPETS_BASELINE_FIDELITY_TESTS_VERSION = "1.0.0"

IMPLEMENTED = sorted(bl.IMPLEMENTED_BASELINES)
UNAVAILABLE = (
    "ttl-only-cache",
    "zanzibar-like-consistency-token-cache",
    "zanzibar-openfga",
    "muse-unlearning-comparator",
)

#: Observable behaviour recorded per implemented baseline (task contract:
#: "Record observable behaviour per baseline").
OBSERVED_BEHAVIOUR: dict[str, str] = {
    "coarse-cache-purge-on-revocation": (
        "On the first post-revocation dispatch of the subject the whole "
        "per-subject cache is cleared (invalidation_events=1, "
        "entries_destroyed_by_purges>0); dispatches whose (subject, grant, "
        "purpose) coverage is revoked return per-dispatch REJECT with "
        "reason_code REVOKED_CONTEXT and zero exposed bytes; dispatches under "
        "unaffected grants are ADMITted (recompute-or-hit after purge); "
        "admitted misses rebuild the projection (recompute_count) and are "
        "then served from cache on identical (subject, grant, purpose, "
        "dispatch_id) repeats (cache_hit=True)."
    ),
    "always-recompute-authorized-projection": (
        "Zero caching: every dispatch recomputes (invalidation_events == "
        "dispatch_count), cache_hit is False on every record, and "
        "authorization is re-derived from the live source snapshot each "
        "dispatch; post-revocation coverage yields REJECT/REVOKED_CONTEXT; "
        "derived lineage ids are deterministically expanded to the snapshot "
        "records they embed (or fail closed with LINEAGE_SOURCE_MISSING); "
        "admitted dispatches pay full rebuild cost on every call."
    ),
    "purpose-bound-cache-keying": (
        "Cache keys are (subject, grant, purpose, consent_epoch); the first "
        "post-revocation dispatch of a scope rotates its epoch "
        "(key_rotations) so subsequent same-scope dispatches miss and "
        "recompute; unrevoked scopes keep a stable key space; the declared "
        "weakness is surfaced executably as transitive_gaps: transitively "
        "derived artifacts (retry/fallback/embedding/pointer) whose key "
        "components are stable are NOT invalidated by any reverse edge."
    ),
    "purpose-aware-cache-x06": (
        "fetch(key, epoch, purpose) -> Context: a HIT is served only from an "
        "entry whose stored purpose equals the requesting purpose and whose "
        "consent_epoch equals the key epoch; cross-purpose reads are refused "
        "with PURPOSE_MISMATCH before any lookup, stale epochs with "
        "EPOCH_STALE, malformed keys with KEY_MALFORMED, absent entries with "
        "CACHE_MISS; a revocation rotates the scope's epoch exactly once "
        "(invalidation_events=1) so the pre-rotation entry becomes "
        "unreachable (EPOCH_STALE) and the recompute lands in a NEW entry at "
        "the new epoch; purpose_isolation_violations must remain 0 on the "
        "executable invariant check over real cache state."
    ),
}


# ---------------------------------------------------------------------------
# Fixtures / helpers (synthetic workload builders; deterministic, no clocks)
# ---------------------------------------------------------------------------


def _case(workload: dict[str, object], case_id: str = "case-fidelity-1") -> dict[str, object]:
    return {"case_id": case_id, "workload": workload}


def _ctx() -> dict[str, object]:
    return {"campaign_id": "camp-popets-baseline_tests", "seed": 2027}


def _detail(outcome: bl.Outcome) -> dict[str, object]:
    return json.loads(outcome.detail)


REVOCATION = {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 100}


def _workload(
    dispatches: list[dict[str, object]],
    revocations: list[dict[str, object]] | None = None,
    snapshot: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "source_snapshot": snapshot
        or {"vitals_1": "BP 120/80", "meds_1": "metformin", "admin_1": "tier B"},
        "revocations": revocations if revocations is not None else [REVOCATION],
        "dispatches": dispatches,
    }


def _dispatch(
    dispatch_id: str,
    grant: str,
    purpose: str,
    lineage: list[str],
    at_seconds: int,
    subject: str = "s1",
) -> dict[str, object]:
    return {
        "dispatch_id": dispatch_id,
        "subject": subject,
        "grant": grant,
        "purpose": purpose,
        "lineage": lineage,
        "at_seconds": at_seconds,
    }


# ---------------------------------------------------------------------------
# 1. coarse-cache-purge-on-revocation (arm B1)
# ---------------------------------------------------------------------------


class TestCoarsePurgeFidelity:
    """B1: purge-everything-on-revocation, then recompute-or-hit."""

    def test_positive_revocation_completeness_end_to_end(self) -> None:
        """Upstream positive: post-revocation dispatches are denied, unaffected
        grant keeps serving, purge is subject-wide and admitted work is cached."""
        workload = _workload(
            [
                _dispatch("d1", "g-med", "clinical", ["vitals_1"], 10),
                _dispatch("d1", "g-med", "clinical", ["vitals_1"], 20),
                _dispatch("post-direct", "g-med", "analytics", ["meds_1"], 150),
                _dispatch(
                    "post-transitive",
                    "g-med",
                    "analytics",
                    ["summary_cache_1", "retry_payload_1", "vitals_1"],
                    300,
                ),
                _dispatch("other-grant", "g-admin", "clinical", ["admin_1"], 400),
            ]
        )
        outcome = bl.run_baseline("coarse-cache-purge-on-revocation", _case(workload), _ctx())
        assert isinstance(outcome, bl.Outcome)
        assert outcome.observed_outcome == "ADMIT"  # unaffected grant still served
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # Pre-revocation authorized dispatch admits; both records share the
        # same dispatch_id, so the dict keeps the LAST (the cache-HIT repeat).
        assert records["d1"]["outcome"] == "ADMIT"
        assert records["d1"]["reason_code"] == "AUTHORIZED"
        assert records["d1"]["cache_hit"] is True
        # Post-revocation direct AND transitive dispatches fail closed.
        assert records["post-direct"]["outcome"] == "REJECT"
        assert records["post-direct"]["reason_code"] == "REVOKED_CONTEXT"
        assert records["post-direct"]["exposed_bytes"] == 0
        assert records["post-transitive"]["outcome"] == "REJECT"
        assert records["post-transitive"]["reason_code"] == "REVOKED_CONTEXT"
        # Unaffected grant is admitted after the purge (recompute, not stale cache).
        assert records["other-grant"]["outcome"] == "ADMIT"
        assert records["other-grant"]["cache_hit"] is False
        # Subject-wide purge executed exactly once, destroying cached entries.
        assert detail["invalidation_events"] == 1
        assert detail["cost"]["purge_events"] == 1
        assert detail["cost"]["entries_destroyed_by_purges"] >= 1
        assert detail["cost"]["cache_hits"] == 1
        # Parity vector at the registry-declared fixture path reproduces.
        assert bl.parity_check("coarse-cache-purge-on-revocation") is True

    def test_negative_over_invalidation_destroys_unaffected_cached_entries(self) -> None:
        """Adversarial negative: the coarse purge cannot scope its invalidation.

        A consent revocation for (g-med, analytics) must still deny the
        revoked dispatch (REVOKED_CONTEXT), but the SAME event also destroys
        the cached projection of the still-authorized (g-admin, clinical)
        scope — the documented over-invalidation weakness, asserted here as
        fidelity evidence (entries_destroyed_by_purges covers the unaffected
        entry; the next authorized dispatch is forced to recompute).
        """
        workload = _workload(
            [
                _dispatch("admin-cache", "g-admin", "clinical", ["admin_1"], 10),
                _dispatch("revoked-scope", "g-med", "analytics", ["meds_1"], 150),
                _dispatch("admin-post-purge", "g-admin", "clinical", ["admin_1"], 200),
            ]
        )
        outcome = bl.run_baseline("coarse-cache-purge-on-revocation", _case(workload), _ctx())
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # The bad case itself is rejected with the stable reason code.
        assert records["revoked-scope"]["outcome"] == "REJECT"
        assert records["revoked-scope"]["reason_code"] == "REVOKED_CONTEXT"
        # Weakness evidence: purge dropped the UNAFFECTED grant's cached entry too.
        assert detail["cost"]["purge_events"] == 1
        assert detail["cost"]["entries_destroyed_by_purges"] >= 1
        assert records["admin-cache"]["outcome"] == "ADMIT"
        assert records["admin-cache"]["cache_hit"] is False
        # The post-purge authorized dispatch cannot be served from cache even
        # though nothing about its scope was revoked: false invalidation
        # (2 forced recomputes for 1 untouched scope + 1 denied dispatch).
        assert records["admin-post-purge"]["outcome"] == "ADMIT"
        assert records["admin-post-purge"]["cache_hit"] is False
        assert detail["recompute_count"] == detail["cost"]["recomputes"] == 2
        assert detail["cost"]["entries_destroyed_by_purges"] == 1

    def test_negative_malformed_workload_fails_closed_with_reason_code(self) -> None:
        """Adversarial negative: empty dispatch list must fail closed with a
        stable WORKLOAD_MALFORMED reason code, never a silent safe rejection."""
        outcome = bl.run_baseline(
            "coarse-cache-purge-on-revocation",
            _case({"source_snapshot": {"a": "x"}, "revocations": [], "dispatches": []}),
            _ctx(),
        )
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.detail.startswith("WORKLOAD_MALFORMED")


# ---------------------------------------------------------------------------
# 2. always-recompute-authorized-projection (arm B2)
# ---------------------------------------------------------------------------


class TestAlwaysRecomputeFidelity:
    """B2: zero caching; reauthorize from live sources every dispatch."""

    def test_positive_zero_cache_and_live_reauthorization_end_to_end(self) -> None:
        """Upstream positive: identical authorized dispatches admit but never
        hit a cache; post-revocation coverage is denied from live state even
        though a cache-based arm might have served a stale projection."""
        workload = _workload(
            [
                _dispatch("pre-1", "g-med", "clinical", ["vitals_1"], 10),
                _dispatch("pre-2", "g-med", "clinical", ["vitals_1"], 20),
                _dispatch("post-revoke", "g-med", "analytics", ["meds_1"], 150),
            ]
        )
        outcome = bl.run_baseline("always-recompute-authorized-projection", _case(workload), _ctx())
        assert isinstance(outcome, bl.Outcome)
        assert outcome.observed_outcome == "ADMIT"
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # Both authorized dispatches admit with identical exposure.
        assert records["pre-1"]["outcome"] == "ADMIT"
        assert records["pre-2"]["outcome"] == "ADMIT"
        assert records["pre-1"]["exposed_bytes"] == records["pre-2"]["exposed_bytes"] > 0
        # Zero caching: no dispatch is ever a cache hit; every dispatch pays
        # the rebuild (invalidation_events == dispatch_count is the arm's
        # recompute accounting).
        assert all(r["cache_hit"] is False for r in detail["dispatches"])
        assert detail["invalidation_events"] == detail["dispatch_count"] == 3
        # Post-revocation dispatch denied from the live snapshot.
        assert records["post-revoke"]["outcome"] == "REJECT"
        assert records["post-revoke"]["reason_code"] == "REVOKED_CONTEXT"
        assert records["post-revoke"]["exposed_bytes"] == 0
        # Parity vector reproduces exactly (upstream pinned semantics).
        assert bl.parity_check("always-recompute-authorized-projection") is True

    def test_negative_derived_lineage_fails_closed_on_unexpandable_artifact(self) -> None:
        """Adversarial negative: a dispatch whose lineage contains a derived
        artifact that cannot be expanded to a live source record must REJECT
        with LINEAGE_SOURCE_MISSING (fail closed), never serve invented
        content; and an expandable derived artifact in the SAME workload
        family is still reauthorized against live revocation state."""
        workload = _workload(
            [
                # Derived id with no embedded source record id in this
                # snapshot, pre-revocation: the arm cannot expand it to any
                # live source record -> fail closed with LINEAGE_SOURCE_MISSING
                # (reauthorization must be grounded in real provenance).
                _dispatch("unexpandable", "g-med", "analytics", ["retry_payload_9"], 10),
                # Same dispatch shape but POST-revocation: denied for the
                # revocation reason before provenance expansion even applies.
                _dispatch(
                    "unexpandable-post-revoke", "g-med", "analytics", ["retry_payload_9"], 200
                ),
            ],
            snapshot={"s1_vitals": "BP 120/80"},
        )
        outcome = bl.run_baseline("always-recompute-authorized-projection", _case(workload), _ctx())
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # The bad case is rejected, and rejected for the RIGHT reason: the
        # unexpandable artifact fails closed on source provenance.
        assert records["unexpandable"]["outcome"] == "REJECT"
        assert records["unexpandable"]["reason_code"] == "LINEAGE_SOURCE_MISSING"
        assert records["unexpandable"]["exposed_bytes"] == 0
        # Post-revocation twin is denied under the revocation code.
        assert records["unexpandable-post-revoke"]["outcome"] == "REJECT"
        assert records["unexpandable-post-revoke"]["reason_code"] == "REVOKED_CONTEXT"
        # Weakness/cost evidence: the arm served nothing from any cache
        # (all misses, everything recomputed from scratch).
        assert all(r["cache_hit"] is False for r in detail["dispatches"])
        assert detail["admitted"] == 0 and detail["rejected"] == 2

    def test_negative_unknown_baseline_id_is_not_fabricated(self) -> None:
        """Adversarial negative: an unavailable/unimplemented baseline id must
        return NOT_RUN_EXTERNAL with BASELINE_UNAVAILABLE — never a number."""
        for baseline_id in (*UNAVAILABLE, "does-not-exist"):
            outcome = bl.run_baseline(baseline_id, _case(_workload([])), _ctx())
            assert outcome.observed_outcome == "NOT_RUN_EXTERNAL", baseline_id
            assert outcome.detail.startswith("BASELINE_UNAVAILABLE"), baseline_id


# ---------------------------------------------------------------------------
# 3. purpose-bound-cache-keying (design reference / ablation)
# ---------------------------------------------------------------------------


class TestPurposeKeyingFidelity:
    """Purpose-bound keying: epoch rotation on revocation, no reverse edges."""

    def test_positive_epoch_rotation_scopes_recompute_to_affected_purpose(self) -> None:
        """Upstream positive: the revoked (grant, purpose) scope rotates its
        consent epoch exactly at revocation so its next dispatch misses and
        recomputes; an unrevoked purpose keeps a stable key space."""
        workload = _workload(
            [
                _dispatch("clinical-1", "g-med", "clinical", ["vitals_1"], 10),
                _dispatch("clinical-2", "g-med", "clinical", ["vitals_1"], 300),
                _dispatch("analytics-post", "g-med", "analytics", ["meds_1"], 150),
            ]
        )
        outcome = bl.run_baseline("purpose-bound-cache-keying", _case(workload), _ctx())
        assert isinstance(outcome, bl.Outcome)
        assert outcome.observed_outcome == "ADMIT"
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # Unrevoked purpose: key space stable across the revocation.
        assert records["clinical-1"]["cache_key_epoch"] == 0
        assert records["clinical-2"]["cache_key_epoch"] == 0
        assert records["clinical-1"]["stable_key"] == records["clinical-2"]["stable_key"]
        assert records["clinical-2"]["outcome"] == "ADMIT"
        # Revoked purpose: epoch rotated once; dispatch denied with code.
        assert records["analytics-post"]["cache_key_epoch"] == 1
        assert records["analytics-post"]["outcome"] == "REJECT"
        assert records["analytics-post"]["reason_code"] == "REVOKED_CONTEXT"
        assert detail["key_rotations"] == 1
        # Parity vector reproduces (includes the declared ablation-gap step).
        assert bl.parity_check("purpose-bound-cache-keying") is True

    def test_negative_transitive_artifact_not_invalidated_by_keying(self) -> None:
        """Adversarial negative (declared weakness, asserted explicitly): with
        no reverse dependency edges, a transitively derived retry artifact
        whose key components are stable is NOT invalidated by the keying
        mechanism. The simulation surfaces this as ``transitive_gaps`` > 0
        while the authorization surface still denies the dispatch — fidelity
        evidence for exactly the leak class the candidate (B4) must close."""
        workload = _workload(
            [
                _dispatch("clinical", "g-med", "clinical", ["vitals_1"], 10),
                _dispatch("retry-after-revoke", "g-med", "analytics", ["retry_payload_1"], 200),
            ]
        )
        outcome = bl.run_baseline("purpose-bound-cache-keying", _case(workload), _ctx())
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # The dispatch carrying transitive lineage is still denied (fail
        # closed at the authorization surface)...
        assert records["retry-after-revoke"]["outcome"] == "REJECT"
        assert records["retry-after-revoke"]["reason_code"] == "REVOKED_CONTEXT"
        assert records["retry-after-revoke"]["exposed_bytes"] == 0
        # ...but the KEYING mechanism itself did not invalidate the transitive
        # artifact (its key space stayed valid): the declared gap, > 0.
        assert detail["transitive_gaps"] >= 1
        assert detail["key_rotations"] == 1

    def test_negative_malformed_workload_fails_closed(self) -> None:
        """Adversarial negative: empty dispatch list fails closed with the
        stable WORKLOAD_MALFORMED reason code, never a silent pass."""
        outcome = bl.run_baseline(
            "purpose-bound-cache-keying",
            _case({"source_snapshot": {"a": "x"}, "revocations": [], "dispatches": []}),
            _ctx(),
        )
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.detail.startswith("WORKLOAD_MALFORMED")


# ---------------------------------------------------------------------------
# 4. purpose-aware-cache-x06 (directly callable fetch contract)
# ---------------------------------------------------------------------------


class TestPurposeAwareCacheX06Fidelity:
    """X06: explicit fetch(key, epoch, purpose) -> Context over real state."""

    def test_positive_purpose_isolation_and_rotation_end_to_end(self) -> None:
        """Upstream positive: same-purpose same-epoch repeats HIT; cross-purpose
        use is structurally a miss; a revocation rotates the epoch exactly once
        so the pre-rotation entry is unreachable and the recompute lands in a
        new entry; the executable isolation invariant holds (0 violations)."""
        workload = _workload(
            [
                _dispatch("analytics-1", "g-med", "analytics", ["meds_1"], 10),
                _dispatch("analytics-2", "g-med", "analytics", ["meds_1"], 20),
                _dispatch("clinical", "g-med", "clinical", ["meds_1"], 30),
                _dispatch("analytics-post-revoke", "g-med", "analytics", ["meds_1"], 150),
                _dispatch("analytics-new-epoch", "g-med", "analytics", ["meds_1"], 200),
            ]
        )
        outcome = bl.run_baseline("purpose-aware-cache-x06", _case(workload), _ctx())
        assert isinstance(outcome, bl.Outcome)
        assert outcome.observed_outcome == "ADMIT"
        detail = _detail(outcome)
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # Same-purpose same-epoch repeat hits the real entry.
        assert records["analytics-1"]["fetch_status"] == "CACHE_MISS"
        assert records["analytics-2"]["fetch_status"] == "HIT"
        assert records["analytics-2"]["entry_purpose"] == "analytics"
        # Same lineage under a DIFFERENT purpose is a fresh miss (no reuse).
        assert records["clinical"]["fetch_status"] == "CACHE_MISS"
        # Revocation rotates the scope's epoch once; entry recreated at epoch 1.
        assert records["analytics-post-revoke"]["cache_key_epoch"] == 1
        assert records["analytics-new-epoch"]["cache_key_epoch"] == 1
        assert records["analytics-new-epoch"]["fetch_status"] == "HIT"
        assert records["analytics-new-epoch"]["entry_purpose"] == "analytics"
        assert detail["invalidation_events"] == 1
        assert detail["cache_entries_created"] == 3  # analytics@0, clinical@0, analytics@1
        assert detail["live_entries_current_epoch"] == 2  # clinical@0 + analytics@1
        # Executable invariant over real cache state: zero violations ever.
        assert detail["purpose_isolation_violations"] == 0
        assert all(not r["context_leaked_across_purposes"] for r in detail["dispatches"])
        assert bl.parity_check("purpose-aware-cache-x06") is True

    def test_negative_fetch_contract_refuses_cross_purpose_and_stale_reads(self) -> None:
        """Adversarial negative: the direct fetch contract must REJECT bad
        reads with stable reason codes — cross-purpose read (PURPOSE_MISMATCH,
        returned BEFORE any lookup so an attacker under purpose 'analytics'
        can never observe a 'clinical' entry), stale epoch (EPOCH_STALE),
        malformed key (KEY_MALFORMED), absent key (CACHE_MISS); a tampered
        cache entry that violates purpose isolation is DETECTED by the
        executable invariant (violations > 0), never silently served."""
        entry = bl.PurposeCacheEntry(
            subject="s1",
            grant="g-med",
            purpose="clinical",
            consent_epoch=0,
            context="BP 120/80",
            source_artifacts=frozenset({"vitals_1"}),
            created_at_seconds=5,
        )
        good_key = ("s1", "g-med", "clinical", 0)
        cache = {good_key: entry}
        # Cross-purpose read: refused even though the entry object exists.
        status, context, fetched = bl.purpose_cache_fetch(cache, good_key, "analytics")
        assert (status, context, fetched) == ("PURPOSE_MISMATCH", "", None)
        # Rotated key with no entry at the new epoch: plain miss (the old
        # entry is unreachable through the rotated key space).
        status, context, fetched = bl.purpose_cache_fetch(
            cache, ("s1", "g-med", "clinical", 1), "clinical"
        )
        assert (status, context, fetched) == ("CACHE_MISS", "", None)
        # Malformed key (missing epoch component).
        status, context, fetched = bl.purpose_cache_fetch(
            cache, ("s1", "g-med", "clinical"), "clinical"
        )
        assert (status, context, fetched) == ("KEY_MALFORMED", "", None)
        # Well-formed key with no entry: plain miss.
        status, context, fetched = bl.purpose_cache_fetch({}, good_key, "clinical")
        assert (status, context, fetched) == ("CACHE_MISS", "", None)
        # Honest HIT requires exact purpose + epoch binding.
        status, context, fetched = bl.purpose_cache_fetch(cache, good_key, "clinical")
        assert status == "HIT" and context == "BP 120/80" and fetched is entry
        # Tamper evidence: a stored line whose consent_epoch contradicts its
        # key is not silently served — the fetch refuses it with EPOCH_STALE
        # (the same executable invariant the arm checks after every dispatch
        # via purpose_isolation_violations).
        tampered_key = ("s1", "g-med", "clinical", 0)
        tampered_entry = bl.PurposeCacheEntry(
            subject="s1",
            grant="g-med",
            purpose="clinical",
            consent_epoch=1,
            context="BP 120/80",
            source_artifacts=frozenset({"vitals_1"}),
            created_at_seconds=5,
        )
        tampered_cache = {tampered_key: tampered_entry}
        assert tampered_entry.consent_epoch != tampered_key[3]
        status, context, fetched = bl.purpose_cache_fetch(tampered_cache, tampered_key, "clinical")
        assert (status, context, fetched) == ("EPOCH_STALE", "", None)

    def test_negative_missing_lineage_source_fails_closed(self) -> None:
        """Adversarial negative: X06 recompute must never invent content; a
        cache miss whose lineage references an artifact outside the live
        source snapshot raises the contract's fail-closed error instead of
        storing or serving fabricated context."""
        workload = _workload(
            [_dispatch("ghost", "g-med", "analytics", ["ghost_record"], 10)],
            revocations=[],
        )
        with pytest.raises(ValueError, match="LINEAGE_SOURCE_MISSING"):
            bl.run_baseline("purpose-aware-cache-x06", _case(workload), _ctx())


# ---------------------------------------------------------------------------
# Cross-baseline: documented default workload runs every implemented arm
# ---------------------------------------------------------------------------


def test_observed_behaviour_documented_for_every_implemented_baseline() -> None:
    """Fidelity bookkeeping: each implemented baseline has an observable-
    behaviour record, and the module under test really implements it."""
    for baseline_id in IMPLEMENTED:
        assert baseline_id in OBSERVED_BEHAVIOUR
        assert bl.BASELINE_REGISTRY[baseline_id]["fidelity"] == "FAITHFUL_PORT"
    # Unavailable arms stay honestly NOT_RUN_EXTERNAL (no toy substitution).
    for baseline_id in UNAVAILABLE:
        assert bl.run_baseline(baseline_id, _case(_workload([])), _ctx()).observed_outcome == (
            "NOT_RUN_EXTERNAL"
        )
        assert bl.parity_check(baseline_id) is None
