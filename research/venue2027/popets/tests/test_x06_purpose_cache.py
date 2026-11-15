"""POPETS-X06_purpose_cache — purpose-aware cache arm isolation and cost tests.

Purpose
-------
Drive the REAL X06 arm ``purpose-aware-cache-x06``
(``evaluation/venue2027/popets/baselines.py::run_baseline``, module
``POPETS_BASELINES_VERSION = "1.1.0"``; the task contract
``fetch(key, epoch, purpose) -> Context`` formalized as a directly callable
comparator arm) with the SAME context (same subject, grant, lineage and
schedule times) requested under TWO DIFFERENT purposes, and assert:

- separate cache entries: the run creates one entry per purpose key space
  (``cache_entries_created == 2``, ``live_entries_current_epoch == 2``) and
  every per-dispatch ``cache_key`` embeds the dispatch's own purpose;
- NO cross-purpose reuse / leakage: the second purpose's first use misses even
  though the first purpose already cached identical lineage, hits occur only
  on same-purpose same-epoch repeats, ``purpose_isolation_violations == 0``
  and no ``context_leaked_across_purposes`` record exists in any run;
- measured real entry/recomputation counts: ``cache_hits + cache_misses ==
  dispatch_count``, ``recomputations == cache_misses``, and post-revocation
  epoch rotation produces a fresh entry at the new epoch while the superseded
  pre-rotation entry can never be served again.

The public contract operation ``purpose_cache_fetch`` (``fetch(key, epoch,
purpose) -> Context``) is exercised directly, including the adversarial
cross-purpose read attempt which must be refused with ``PURPOSE_MISMATCH``.

The X06 arm is additive over POPETS baselines 1.0.0: the three pre-existing
arms' parity vectors and the full pre-existing suite must stay green.

Allowed input
-------------
Synthetic deterministic workloads embedded in ``case.v1``-style dicts only; the
shared-harness ``RunContext`` supplies campaign identity and seed. No network,
no database, no hidden clock or randomness.

Failure semantics
-----------------
Fail closed: malformed workloads must surface ``EXECUTION_ERROR`` with the
stable reason code ``WORKLOAD_MALFORMED``; a run that drops a dispatch record,
emits an undetermined outcome, or violates the purpose-isolation invariant
fails the assertions below rather than being counted as a safe rejection.

Version: 1.0.0
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.popets import baselines as bl

BASELINE_ID = "purpose-aware-cache-x06"


def _ctx(seed: int = 42) -> RunContext:
    return RunContext(
        campaign_id="camp-popets-x06-purpose-cache",
        case_id="case-x06-isolation",
        arm_id=BASELINE_ID,
        seed=seed,
        source_commit="b" * 40,
        deadline_seconds=60.0,
    )


def _shared_workload(
    purpose_a: str = "clinical", purpose_b: str = "analytics"
) -> dict[str, object]:
    """One shared context requested under two purposes.

    Both purpose variants run the identical (subject, grant, lineage, time)
    schedule; only the ``purpose`` label differs. The schedule per purpose:

    - ``first``  (t=10, pre-revocation): first use -> CACHE_MISS, recompute,
      install the purpose's own entry.
    - ``repeat`` (t=20, pre-revocation): same key space -> fetch HIT (a real
      cache hit the cost model must observe).
    - ``post_revocation`` (t=60, after the purpose-B revocation at t=50):
      authorization denies with REVOKED_CONTEXT for purpose B; purpose A is
      unaffected and still served from its un-rotated entry. Purpose B's
      post-revocation dispatch pays the rotation (miss + recompute).
    """

    def dispatches(purpose: str) -> list[dict[str, object]]:
        return [
            {
                "dispatch_id": f"first[{purpose}]",
                "subject": "s1",
                "grant": "g-med",
                "purpose": purpose,
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": f"repeat[{purpose}]",
                "subject": "s1",
                "grant": "g-med",
                "purpose": purpose,
                "lineage": ["vitals_1"],
                "at_seconds": 20,
            },
            {
                "dispatch_id": f"post_revocation[{purpose}]",
                "subject": "s1",
                "grant": "g-med",
                "purpose": purpose,
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
        ]

    return {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [
            {
                "subject": "s1",
                "grant": "g-med",
                "purpose": purpose_b,
                "at_seconds": 50,
            }
        ],
        "dispatches": dispatches(purpose_a) + dispatches(purpose_b),
    }


def _run(workload: dict[str, object], ctx: RunContext | None = None) -> tuple[Outcome, dict]:
    outcome = bl.run_baseline(
        BASELINE_ID, {"case_id": "case-x06", "workload": workload}, ctx or _ctx()
    )
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT")
    assert outcome.counted_as_success is True
    return outcome, json.loads(outcome.detail)


def _assert_purpose_isolation(detail: dict) -> None:
    """Executable invariant over the real per-dispatch records of a run."""
    assert detail["purpose_isolation_violations"] == 0
    assert all(r["context_leaked_across_purposes"] is False for r in detail["dispatches"])
    for record in detail["dispatches"]:
        assert record["entry_purpose"] in (None, record["requested_purpose"]), record
        assert f"|{record['requested_purpose']}|" in record["cache_key"], record
    assert detail["cache_hits"] + detail["cache_misses"] == detail["dispatch_count"]
    assert detail["recomputations"] == detail["cache_misses"]


# ---------------------------------------------------------------------------
# Positive: separate entries per purpose, real measured hit/recompute counts
# ---------------------------------------------------------------------------


def test_same_context_two_purposes_produce_separate_cache_entries() -> None:
    """The identical schedule under two purposes must not share one cache entry.

    Purpose A runs first and installs its entry; purpose B's first dispatch has
    the SAME subject, grant, lineage and time window yet must still miss (its
    key space differs), pay its own recomputation, and create a second entry.
    """
    outcome, detail = _run(_shared_workload())
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    first_a = by_id["first[clinical]"]
    first_b = by_id["first[analytics]"]
    # Separate key spaces: purpose is a component of every emitted cache key.
    assert "|clinical|" in first_a["cache_key"]
    assert "|analytics|" in first_b["cache_key"]
    assert first_a["cache_key"] != first_b["cache_key"]
    assert first_a["cache_key_epoch"] == first_b["cache_key_epoch"] == 0
    # Purpose B's first use does NOT ride on purpose A's identical cached entry.
    assert first_a["fetch_status"] == "CACHE_MISS"
    assert first_b["fetch_status"] == "CACHE_MISS"
    # Two separate entries, both live at the current (epoch-0) state.
    assert detail["cache_entries_created"] >= 2
    assert detail["live_entries_current_epoch"] == 2
    assert detail["distinct_purposes"] == 2
    # Real, measured recomputation: each purpose paid its own first-use miss.
    assert detail["recomputations"] >= 2
    _assert_purpose_isolation(detail)


def test_repeat_dispatch_same_purpose_is_a_real_cache_hit() -> None:
    """A repeat dispatch under the SAME purpose hits that purpose's own entry."""
    outcome, detail = _run(_shared_workload())
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    repeat_a = by_id["repeat[clinical]"]
    repeat_b = by_id["repeat[analytics]"]
    assert repeat_a["fetch_status"] == "HIT"
    assert repeat_a["cache_hit"] is True
    assert repeat_a["entry_purpose"] == "clinical"
    assert repeat_b["fetch_status"] == "HIT"
    assert repeat_b["cache_hit"] is True
    assert repeat_b["entry_purpose"] == "analytics"
    assert detail["cache_hits"] >= 2
    # Every HIT is a same-purpose same-epoch repeat of a populated key space
    # (never a cross-purpose or cross-epoch serve): clinical repeats under
    # epoch 0 (first use, same-epoch repeat, unaffected post-revocation
    # dispatch) and the analytics same-epoch repeat.
    hit_records = [r for r in detail["dispatches"] if r["fetch_status"] == "HIT"]
    assert {r["dispatch_id"] for r in hit_records} == {
        "repeat[clinical]",
        "post_revocation[clinical]",
        "repeat[analytics]",
    }
    for record in hit_records:
        expected_epoch = (
            1
            if "analytics" in record["dispatch_id"] and record["dispatch_id"].startswith("post")
            else 0
        )
        assert record["cache_key_epoch"] == expected_epoch, record
    _assert_purpose_isolation(detail)


def test_cost_accounting_reconciles_exactly() -> None:
    """Every dispatch pays exactly one of {hit, miss}; counters are consistent."""
    outcome, detail = _run(_shared_workload())
    assert detail["cache_hits"] + detail["cache_misses"] == detail["dispatch_count"]
    assert detail["recomputations"] == detail["cache_misses"]
    assert detail["cache_entries_created"] <= detail["dispatch_count"]
    assert detail["cache_entries_total"] >= detail["cache_entries_created"]
    # Admitted dispatches expose the artifact bytes; the REJECT exposes none.
    assert detail["exposed_bytes_total"] == detail["admitted"] * len("BP 120/80")
    _assert_purpose_isolation(detail)


# ---------------------------------------------------------------------------
# Adversarial: NO cross-purpose leakage under a shared context
# ---------------------------------------------------------------------------


def test_no_cross_purpose_leakage_and_no_cross_purpose_hits() -> None:
    """Hits may only come from same-purpose repeats; first use always misses.

    The identical lineage cached under purpose A is unreachable from purpose B:
    every first-use dispatch under any purpose reports CACHE_MISS, and the only
    HIT records are the same-purpose repeats.
    """
    outcome, detail = _run(_shared_workload())
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    for dispatch_id, record in by_id.items():
        if dispatch_id.startswith("first") or (
            dispatch_id.startswith("post") and "analytics" in dispatch_id
        ):
            assert record["fetch_status"] != "HIT", (dispatch_id, record)
            assert record["cache_hit"] is False, (dispatch_id, record)
    hit_purposes = {
        record["requested_purpose"]
        for record in detail["dispatches"]
        if record["fetch_status"] == "HIT"
    }
    # Only same-purpose records hit; no dispatch was served another's entry.
    assert hit_purposes <= {"clinical", "analytics"}
    _assert_purpose_isolation(detail)


def test_post_revocation_isolation_is_scoped_to_affected_purpose_only() -> None:
    """The revocation rotates ONLY purpose B's epoch; purpose A keeps serving.

    Cross-purpose leakage check from both directions: B's post-revocation
    dispatch is denied with a rotated epoch, while A's identical-schedule
    dispatch at the same instant is ADMITTED under its un-rotated epoch —
    proving the key rotation (and the denial) never crossed purposes.
    """
    outcome, detail = _run(_shared_workload())
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    post_a = by_id["post_revocation[clinical]"]
    post_b = by_id["post_revocation[analytics]"]
    assert post_b["outcome"] == "REJECT"
    assert post_b["reason_code"] == "REVOKED_CONTEXT"
    assert post_b["exposed_bytes"] == 0
    assert post_b["cache_key_epoch"] == 1  # rotated for the revoked purpose
    assert post_b["fetch_status"] == "CACHE_MISS"  # old entry is unreachable
    # Same instant, same lineage, other purpose: NOT rotated, NOT denied.
    assert post_a["outcome"] == "ADMIT"
    assert post_a["cache_key_epoch"] == 0
    assert detail["invalidation_events"] == 1
    _assert_purpose_isolation(detail)


def test_epoch_rotation_creates_fresh_entry_superseded_entry_unreachable() -> None:
    """Post-rotation the scope recomputes into a NEW entry at the new epoch.

    Adversarial TTL/epoch-wrap style control: the pre-rotation entry object is
    kept for audit (cache_entries_total grows) but is no longer live (it is not
    counted in live_entries_current_epoch) and its context can never be served
    again — the second post-revocation dispatch hits the NEW entry only.
    """
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "clinical", "at_seconds": 50}
        ],
        "dispatches": [
            {
                "dispatch_id": "pre",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "post_1",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
            {
                "dispatch_id": "post_2",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 70,
            },
            {
                "dispatch_id": "post_3",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 80,
            },
        ],
    }
    outcome, detail = _run(workload)
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    # Exactly one epoch rotation (idempotent per revocation event).
    assert detail["invalidation_events"] == 1
    assert by_id["pre"]["cache_key_epoch"] == 0
    assert by_id["post_1"]["cache_key_epoch"] == 1
    assert by_id["post_2"]["cache_key_epoch"] == 1
    assert by_id["post_3"]["cache_key_epoch"] == 1
    # post_1 misses (stale key space), recomputes, installs the new entry;
    # post_2 and post_3 hit the NEW entry — never the superseded one.
    assert by_id["post_1"]["fetch_status"] == "CACHE_MISS"
    assert by_id["post_2"]["fetch_status"] == "HIT"
    assert by_id["post_3"]["fetch_status"] == "HIT"
    assert by_id["post_2"]["cache_key"].endswith("|1")
    # Superseded entry kept for audit but not live at the current epoch.
    assert detail["cache_entries_created"] == 2
    assert detail["cache_entries_total"] == 2
    assert detail["live_entries_current_epoch"] == 1
    _assert_purpose_isolation(detail)


# ---------------------------------------------------------------------------
# Direct fetch contract: fetch(key, epoch, purpose) -> Context
# ---------------------------------------------------------------------------


def _seeded_cache() -> dict[tuple[str, str, str, int], bl.PurposeCacheEntry]:
    entry = bl.PurposeCacheEntry(
        subject="s1",
        grant="g-med",
        purpose="clinical",
        consent_epoch=0,
        context="BP 120/80",
        source_artifacts=frozenset({"vitals_1"}),
        created_at_seconds=10,
    )
    return {("s1", "g-med", "clinical", 0): entry}


def test_fetch_direct_contract_hit_on_matching_key_and_purpose() -> None:
    cache = _seeded_cache()
    status, context, entry = bl.purpose_cache_fetch(
        cache, ("s1", "g-med", "clinical", 0), "clinical"
    )
    assert status == "HIT"
    assert context == "BP 120/80"
    assert entry is not None and entry.purpose == "clinical"


def test_fetch_refuses_cross_purpose_read_attempt() -> None:
    """Adversarial: a request under a different purpose can never read the entry."""
    cache = _seeded_cache()
    status, context, entry = bl.purpose_cache_fetch(
        cache, ("s1", "g-med", "clinical", 0), "analytics"
    )
    assert status == bl.REASON_PURPOSE_MISMATCH
    assert context == ""  # no context bytes cross the purpose boundary
    assert entry is None


def test_fetch_stale_epoch_is_not_served() -> None:
    """A superseded-epoch entry is never served under a rotated epoch key.

    ``EPOCH_STALE`` is the declared status when a cached object still exists
    under a stale consent epoch; with the key-moved-only simulation the
    rotated key space is simply empty (the caller must recompute). Both
    outcomes refuse to serve the stale context bytes.
    """
    cache = _seeded_cache()
    status, context, entry = bl.purpose_cache_fetch(
        cache, ("s1", "g-med", "clinical", 1), "clinical"
    )
    assert status in (bl.REASON_EPOCH_STALE, bl.REASON_CACHE_MISS)
    assert context == ""
    assert entry is None


def test_fetch_missing_key_is_cache_miss_and_bad_key_fails_closed() -> None:
    cache = _seeded_cache()
    status, context, entry = bl.purpose_cache_fetch(
        cache, ("s1", "g-med", "clinical", 3), "clinical"
    )
    assert status == bl.REASON_CACHE_MISS
    assert context == "" and entry is None
    status, _, _ = bl.purpose_cache_fetch(cache, ("s1", "g-med", "clinical"), "clinical")  # type: ignore[arg-type]
    assert status == bl.REASON_KEY_MALFORMED
    status, _, _ = bl.purpose_cache_fetch(cache, ("s1", "g-med", "clinical", True), "clinical")
    assert status == bl.REASON_KEY_MALFORMED


# ---------------------------------------------------------------------------
# Suite health: parity, determinism, fail-closed, registry honesty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", sorted(bl.IMPLEMENTED_BASELINES))
def test_parity_vectors_reproduce_for_all_implemented_baselines(baseline_id: str) -> None:
    """The X06 addition is additive-only: every parity vector still reproduces."""
    assert bl.parity_check(baseline_id) is True


def test_determinism_same_case_and_ctx() -> None:
    workload = _shared_workload()
    first = bl.run_baseline(
        BASELINE_ID, {"case_id": "case-x06", "workload": workload}, _ctx(seed=11)
    )
    second = bl.run_baseline(
        BASELINE_ID, {"case_id": "case-x06", "workload": workload}, _ctx(seed=11)
    )
    assert first.to_dict() == second.to_dict()


def test_malformed_workload_under_x06_fails_closed() -> None:
    outcome = bl.run_baseline(
        BASELINE_ID,
        {"case_id": "case-x06-bad", "workload": {"source_snapshot": {"x": "1"}, "dispatches": []}},
        _ctx(),
    )
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert "WORKLOAD_MALFORMED" in outcome.detail


def test_missing_lineage_source_fails_closed_never_invents_context() -> None:
    """A cache must never invent content for artifacts absent from the snapshot."""
    bad = _shared_workload()
    bad["dispatches"] = [  # type: ignore[assignment]
        {
            "dispatch_id": "ghost",
            "subject": "s1",
            "grant": "g-med",
            "purpose": "clinical",
            "lineage": ["artifact_not_in_snapshot"],
            "at_seconds": 10,
        }
    ]
    with pytest.raises(ValueError, match="LINEAGE_SOURCE_MISSING"):
        bl.run_baseline(BASELINE_ID, {"case_id": "case-x06-ghost", "workload": bad}, _ctx())


def test_registry_honesty_for_x06_entry() -> None:
    entry = bl.BASELINE_REGISTRY[BASELINE_ID]
    assert entry["fidelity"] == "FAITHFUL_PORT"
    assert "POPETS-X06" in entry["source"] or "POPETS-X06" in entry["algorithm"]
    assert BASELINE_ID in bl.IMPLEMENTED_BASELINES
