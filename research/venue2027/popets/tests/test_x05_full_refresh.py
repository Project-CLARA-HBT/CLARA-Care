"""Tests for POPETS-X05_full_refresh — strong full-refresh comparator.

X05 is the strong/expensive comparator (blueprint arm B1 in its strongest
form): on any consent-revocation event it purges ALL cached projections of the
affected subject (all purposes, all grants, all transitively derived artifacts)
and serves every dispatch by recompute-or-hit from the live source snapshot.

These tests exercise the REAL baseline adapter from
``evaluation/venue2027/popets/baselines.py`` (registry fidelity FAITHFUL_PORT);
they never re-implement or stub the algorithm:

Positive controls (must pass):
- The X05 arm runs end-to-end on a revocation workload and yields determined
  ADMIT/REJECT decisions computed from real per-dispatch authorization.
- Full-refresh semantics: after revocation the ENTIRE per-subject cache is
  purged (``invalidation_events >= 1``, ``cache_entries_at_purge`` >= 1), so no
  cached projection survives across ``t_r``.
- No leakage of revoked context: every post-revocation dispatch touching
  revoked coverage is REJECT/REVOKED_CONTEXT — including direct, transitive
  (retry/fallback/embedding) and previously cache-hit lineages.
- False-invalidation cost is paid: an UNAFFECTED grant of the same subject,
  even if previously cached, must rebuild after the purge (cache miss), which
  is the declared availability cost of the strong comparator.
- Cost accounting (backwards-compatible additions): ``recompute_count`` and
  ``cost.*`` summarize real RQ3 quantities; ``recompute_count`` equals the
  observed miss/denied dispatch count and is >= 1 per purge window.

Adversarial controls (must be refused / honest, never fabricated):
- A post-revocation dispatch whose lineage contains a cached-pre-revocation
  artifact is still denied (cache state cannot resurrect revoked context).
- Missing source fails closed with LINEAGE_SOURCE_MISSING (never counted as a
  safe rejection of revoked content).
- Malformed workload input fails closed with EXECUTION_ERROR / WORKLOAD_MALFORMED.
- Determinism: same case + ctx reproduces byte-identical outcomes.
- Parity: the real adapter reproduces its pinned fixture vector exactly.

Version: X05_FULL_REFRESH_SPEC_VERSION 1.0.0 over POPETS_BASELINES_VERSION 1.0.0.
"""

from __future__ import annotations

import json

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.popets import baselines as bl

X05_ARM = "coarse-cache-purge-on-revocation"  # the full-refresh comparator arm


def _ctx(seed: int = 7) -> RunContext:
    return RunContext(
        campaign_id="camp-popets-x05-full-refresh",
        case_id="case-x05-1",
        arm_id=X05_ARM,
        seed=seed,
        source_commit="b" * 40,
        deadline_seconds=60.0,
    )


def _case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {"case_id": "case-popets-x05", "seed": 42}
    case.update(overrides)
    return case


def _run_x05(case: dict[str, object], ctx: RunContext | None = None) -> tuple[Outcome, dict]:
    outcome = bl.run_baseline(X05_ARM, case, ctx if ctx is not None else _ctx())
    assert isinstance(outcome, Outcome)
    return outcome, json.loads(outcome.detail)


def _revocation_workload() -> dict[str, object]:
    """Revocation workload exercising direct + transitive + cached lineages."""
    return {
        "source_snapshot": {
            "vitals_2026_01": "BP 128/84, HR 72",
            "med_list_2026_02": "metformin 1000mg",
            "admin_note_2026_01": "billing tier B",
        },
        "revocations": [
            {"subject": "subj-1", "grant": "g-med", "purpose": "analytics", "at_seconds": 100},
        ],
        "dispatches": [
            {
                "dispatch_id": "d1-pre-admits-and-caches",
                "subject": "subj-1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_2026_01"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "d2-pre-caches-admin-grant",
                "subject": "subj-1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["admin_note_2026_01"],
                "at_seconds": 20,
            },
            {
                "dispatch_id": "d3-post-revoked-direct",
                "subject": "subj-1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["med_list_2026_02"],
                "at_seconds": 200,
            },
            {
                "dispatch_id": "d4-post-revoked-transitive-retry",
                "subject": "subj-1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["summary_cache_1", "retry_payload_1", "vitals_2026_01"],
                "at_seconds": 300,
            },
            {
                "dispatch_id": "d5-post-revoke-unaffected-grant-rebuilds",
                "subject": "subj-1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["admin_note_2026_01"],
                "at_seconds": 400,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Positive: full-refresh purge semantics on a revocation workload
# ---------------------------------------------------------------------------


def test_x05_runs_end_to_end_with_determined_outcomes() -> None:
    outcome, detail = _run_x05(_case(workload=_revocation_workload()))
    assert outcome.observed_outcome in ("ADMIT", "REJECT")
    assert outcome.counted_as_success is True
    assert detail["baseline"] == X05_ARM
    assert detail["dispatch_count"] == 5
    assert detail["admitted"] + detail["rejected"] == detail["dispatch_count"]
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    assert by_id["d1-pre-admits-and-caches"]["outcome"] == "ADMIT"
    assert by_id["d3-post-revoked-direct"]["outcome"] == "REJECT"
    assert by_id["d4-post-revoked-transitive-retry"]["outcome"] == "REJECT"
    assert by_id["d5-post-revoke-unaffected-grant-rebuilds"]["outcome"] == "ADMIT"


def test_x05_purges_all_cached_projections_on_revocation() -> None:
    """The full-refresh purge destroys the ENTIRE per-subject cache at t_r."""
    _, detail = _run_x05(_case(workload=_revocation_workload()))
    assert detail["invalidation_events"] == 1
    # Both pre-revocation dispatches had cached projections before the purge.
    assert detail["cache_entries_at_purge"] == 2
    assert detail["cost"]["entries_destroyed_by_purges"] == 2
    # Peak cache size was reached pre-purge (2 entries), post-purge it is 0..1.
    assert detail["cost"]["peak_cache_size"] == 2


def test_x05_does_not_leak_revoked_context_after_purge() -> None:
    """No post-revocation dispatch may leak revoked context through cache."""
    _, detail = _run_x05(_case(workload=_revocation_workload()))
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    for dispatch_id in ("d3-post-revoked-direct", "d4-post-revoked-transitive-retry"):
        assert by_id[dispatch_id]["outcome"] == "REJECT", dispatch_id
        assert by_id[dispatch_id]["reason_code"] == "REVOKED_CONTEXT", dispatch_id
        assert by_id[dispatch_id]["exposed_bytes"] == 0, dispatch_id
        assert by_id[dispatch_id]["cache_hit"] is False, dispatch_id
    # Zero exposed bytes for every post-revocation dispatch touching the
    # revoked (subject, grant) coverage (RQ1 leak check); the unaffected
    # g-admin grant at d5 is authorized from live source, never from stale
    # cache, and re-exposes only its own non-revoked artifact.
    by_id_d5 = by_id["d5-post-revoke-unaffected-grant-rebuilds"]
    assert by_id_d5["reason_code"] == "AUTHORIZED"
    assert by_id_d5["cache_hit"] is False
    post_revocation = [r for r in detail["dispatches"] if r["dispatch_id"] >= "d3"]
    assert all(r["exposed_bytes"] == 0 for r in post_revocation if r["outcome"] == "REJECT")


def test_x05_rebuilds_unaffected_grant_after_full_purge() -> None:
    """False-invalidation cost: a cached unaffected grant is purged and rebuilds."""
    _, detail = _run_x05(_case(workload=_revocation_workload()))
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    pre = by_id["d2-pre-caches-admin-grant"]
    post = by_id["d5-post-revoke-unaffected-grant-rebuilds"]
    assert pre["outcome"] == "ADMIT"
    assert pre["cache_hit"] is False  # first touch: fill
    assert post["outcome"] == "ADMIT"
    assert post["cache_hit"] is False  # purge destroyed it: rebuild (cost paid)
    assert post["exposed_bytes"] == pre["exposed_bytes"]


# ---------------------------------------------------------------------------
# Cost accounting: real recomputation counts recorded (RQ3)
# ---------------------------------------------------------------------------


def test_x05_records_real_recompute_count() -> None:
    _, detail = _run_x05(_case(workload=_revocation_workload()))
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    admitted_misses = [
        r for r in detail["dispatches"] if not r["cache_hit"] and r["outcome"] == "ADMIT"
    ]
    hits = [r for r in detail["dispatches"] if r["cache_hit"]]
    # Real recomputation count: every ADMITTED miss rebuilds its projection.
    assert detail["recompute_count"] == len(admitted_misses)
    assert detail["recompute_count"] >= 3  # d1, d2 (pre), d5 (post-purge rebuild)
    assert detail["cost"]["cache_hits"] == len(hits)
    assert detail["cost"]["recomputes"] == detail["recompute_count"]
    assert detail["cost"]["purge_events"] == detail["invalidation_events"]
    # The post-purge rebuild of the unaffected grant is a real recompute.
    assert by_id["d5-post-revoke-unaffected-grant-rebuilds"]["cache_hit"] is False


def test_x05_recompute_count_grows_with_purge_windows() -> None:
    """A second revocation forces another purge: misses accumulate, hits collapse."""
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80", "meds_1": "metformin"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50},
            {"subject": "s1", "grant": "g-admin", "purpose": "clinical", "at_seconds": 150},
        ],
        "dispatches": [
            {
                "dispatch_id": "a",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "b",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 20,
            },
            {
                "dispatch_id": "c",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
            {
                "dispatch_id": "d",
                "subject": "s1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 70,
            },
            {
                "dispatch_id": "e",
                "subject": "s1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 200,
            },
        ],
    }
    _, detail = _run_x05(_case(workload=workload))
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    # Cache keys include dispatch_id: distinct dispatches never hit (the
    # maximal-rebuild form of the arm), so every authorized dispatch rebuilds.
    assert by_id["a"]["cache_hit"] is False
    assert by_id["b"]["cache_hit"] is False
    assert by_id["c"]["cache_hit"] is False  # served post-purge #1 (revoked t=50)
    assert by_id["d"]["cache_hit"] is False  # served pre-purge #2 (revoked t=150)
    assert by_id["e"]["outcome"] == "REJECT"  # purge #2 coverage: fails closed
    assert detail["invalidation_events"] == 2
    assert detail["cache_entries_at_purge"] == 4  # 2 authorized fills per purge window
    assert detail["recompute_count"] == 4  # a, b, c, d: every admitted dispatch
    assert detail["cost"]["cache_hits"] == 0


# ---------------------------------------------------------------------------
# Adversarial: fail-closed honesty, never fabricated safety
# ---------------------------------------------------------------------------


def test_x05_cached_pre_revocation_artifact_cannot_resurrect_revoked_context() -> None:
    """A dispatch re-using a cached pre-revocation lineage is still denied."""
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50},
        ],
        "dispatches": [
            {
                "dispatch_id": "fill",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "reuse-cached-lineage-post-revoke",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
        ],
    }
    _, detail = _run_x05(_case(workload=workload))
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    assert by_id["fill"]["outcome"] == "ADMIT"
    assert by_id["reuse-cached-lineage-post-revoke"]["outcome"] == "REJECT"
    assert by_id["reuse-cached-lineage-post-revoke"]["reason_code"] == "REVOKED_CONTEXT"


def test_x05_missing_source_fails_closed_not_counted_as_revocation() -> None:
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [],
        "dispatches": [
            {
                "dispatch_id": "ghost",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["ghost_record"],
                "at_seconds": 10,
            }
        ],
    }
    _, detail = _run_x05(_case(workload=workload))
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    assert by_id["ghost"]["outcome"] == "REJECT"
    assert by_id["ghost"]["reason_code"] == "LINEAGE_SOURCE_MISSING"


def test_x05_malformed_workload_fails_closed() -> None:
    outcome = bl.run_baseline(X05_ARM, _case(workload={"source_snapshot": {"x": "1"}}), _ctx())
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert "WORKLOAD_MALFORMED" in outcome.detail


def test_x05_determinism_same_case_and_ctx() -> None:
    first, first_detail = _run_x05(_case(workload=_revocation_workload()), _ctx(seed=11))
    second, second_detail = _run_x05(_case(workload=_revocation_workload()), _ctx(seed=11))
    assert first.to_dict() == second.to_dict()
    assert first_detail == second_detail


def test_x05_parity_vector_reproduces_exactly() -> None:
    assert bl.parity_check(X05_ARM) is True


def test_x05_default_workload_records_recompute_count() -> None:
    """The deterministic default workload also runs end-to-end with real costs."""
    _, detail = _run_x05(_case())
    assert detail["dispatch_count"] >= 4
    assert detail["recompute_count"] >= 1
    assert detail["invalidation_events"] == 1
