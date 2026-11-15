"""Tests for POPETS-candidate (revocation-complete future-disclosure cache).

Positive controls (mechanism works):
- Direct revocation: a revoked scope's own cached entry is refused on the next
  get (REVOKED_ENTRY), and other-scope entries stay live (exact invalidation,
  no full flush).
- Transitive-derived entry: a retry payload derived (via reverse edges) from a
  revoked summary is ALSO blocked after revoke, even though its own declared
  dependencies are stable — reverse-edge closure reaches it.

Adversarial controls (mechanism isolation + fail closed):
- Ablation LEAK: ablation_no_reverse_edges() serves the same transitive entry
  with served_from_revoked_ancestry=True after the same revocation — proving
  reverse edges (not dependency labels alone) are the load-bearing mechanism.
- Unknown purpose refused (PURPOSE_MISMATCH) and stale epoch refused
  (EPOCH_STALE) on both modes; determinism: identical op sequences reproduce
  byte-identical detail JSON.
- put() refuses revoked dependencies and revoked derivation parents
  (REVOKED_DEPENDENCY); self-derivation cycles and missing parents are
  refused; malformed inputs raise stable reason codes; run_candidate fails
  closed with EXECUTION_ERROR on malformed cases.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.popets.candidate import (
    ABLATION_ID,
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    Dependency,
    RevocationCompleteCache,
    ablation_no_reverse_edges,
    describe_mechanism,
    run_candidate,
)

SUBJECT = "subj-1"


def _dep(purpose: str, epoch: int = 0, subject: str = SUBJECT) -> Dependency:
    return Dependency(subject=subject, purpose=purpose, consent_epoch=epoch)


# ---------------------------------------------------------------------------
# Shared scenario builders (fixture knowledge externalized from the algorithm)
# ---------------------------------------------------------------------------


def _scenario() -> RevocationCompleteCache:
    """Direct summary + transitive retry payload + unaffected admin entry."""
    cache = RevocationCompleteCache()
    cache.put("summary_1", "BP 128/84, HR 72", deps=[_dep("analytics", 0)])
    # retry_payload_1 is DERIVED from summary_1: reverse edge summary_1 -> retry.
    cache.put(
        "retry_payload_1",
        "retry of summary_1",
        deps=[_dep("analytics", 0)],
        derived_from=["summary_1"],
    )
    # Unaffected scope: must survive the analytics revocation (exact invalidation).
    cache.put("admin_note_1", "billing tier B", deps=[_dep("admin", 0)])
    return cache


def _revoke_analytics(cache: RevocationCompleteCache) -> dict[str, object]:
    return cache.revoke(SUBJECT, "analytics", 0)


# ---------------------------------------------------------------------------
# Positive: direct revocation blocks re-disclosure
# ---------------------------------------------------------------------------


def test_direct_revocation_blocks_own_entry() -> None:
    cache = _scenario()
    assert cache.get("summary_1", "analytics", 0).status == "HIT"
    record = _revoke_analytics(cache)
    assert record["invalidated_keys"] == ["summary_1"] or "summary_1" in record["direct_keys"]
    read = cache.get("summary_1", "analytics", 0)
    assert read.status == "REVOKED_ENTRY"
    assert read.served_from_revoked_ancestry is True
    assert not cache.is_live("summary_1")


def test_exact_invalidation_unaffected_scope_stays_live() -> None:
    cache = _scenario()
    _revoke_analytics(cache)
    # No full flush: the admin-purpose entry has no revoked dependency and no
    # derivation path from the invalidated set, so it remains servable.
    read = cache.get("admin_note_1", "admin", 0)
    assert read.status == "HIT"
    assert read.served_from_revoked_ancestry is False
    assert cache.is_live("admin_note_1")
    record = cache.revocation_log()[0]
    assert record["left_live"] == ["admin_note_1"]
    assert sorted(record["invalidated_keys"]) == ["retry_payload_1", "summary_1"]


def test_transitive_derived_entry_also_blocked_by_reverse_edges() -> None:
    cache = _scenario()
    _revoke_analytics(cache)
    # retry_payload_1's own deps (analytics, 0) name the revoked scope here; a
    # second entry derived from the revoked summary with STABLE labels is the
    # strict test: only reverse edges can reach it.
    cache2 = RevocationCompleteCache()
    cache2.put("summary_1", "BP 128/84, HR 72", deps=[_dep("analytics", 0)])
    cache2.put("fallback_transport_1", "fb", deps=[_dep("admin", 0)], derived_from=["summary_1"])
    cache2.revoke(SUBJECT, "analytics", 0)
    direct = cache2.get("summary_1", "analytics", 0)
    assert direct.status == "REVOKED_ENTRY"
    transitive = cache2.get("fallback_transport_1", "admin", 0)
    assert transitive.status == "REVOKED_ENTRY"
    assert transitive.served_from_revoked_ancestry is True
    assert not cache2.is_live("fallback_transport_1")


def test_transitive_closure_follows_chain_to_depth() -> None:
    cache = RevocationCompleteCache()
    cache.put("a", "root", deps=[_dep("analytics", 0)])
    cache.put("b", "mid", deps=[_dep("admin", 0)], derived_from=["a"])
    cache.put("c", "leaf", deps=[_dep("admin", 0)], derived_from=["b"])
    record = cache.revoke(SUBJECT, "analytics", 0)
    assert record["direct_keys"] == ["a"]
    assert record["transitive_keys"] == ["b", "c"]
    for key in ("a", "b", "c"):
        assert cache.get(key, "admin", 0).status == "REVOKED_ENTRY"
        assert not cache.is_live(key)


def test_candidate_hit_after_revoke_raises_closure_invariant() -> None:
    cache = _scenario()
    _revoke_analytics(cache)
    cache._tombstoned["retry_payload_1"] = False  # simulate corrupted state
    with pytest.raises(ValueError, match="CLOSURE_INVARIANT_VIOLATION"):
        cache.get("retry_payload_1", "analytics", 0)


# ---------------------------------------------------------------------------
# Adversarial: ablation leaks the transitive entry (mechanism isolation)
# ---------------------------------------------------------------------------


def test_ablation_leaks_transitive_entry_proving_reverse_edges() -> None:
    """THE mechanism-isolation proof: without reverse edges the leak appears."""
    candidate_cache = _scenario()
    _revoke_analytics(candidate_cache)
    assert candidate_cache.get("retry_payload_1", "analytics", 0).status == "REVOKED_ENTRY"

    ablation = RevocationCompleteCache(enforce_reverse_edges=False, mode="ablation")
    ablation.put("summary_1", "BP 128/84, HR 72", deps=[_dep("analytics", 0)])
    # fallback_transport_1: derived from revoked ancestry, own labels STABLE.
    ablation.put("fallback_transport_1", "fb", deps=[_dep("admin", 0)], derived_from=["summary_1"])
    record = ablation.revoke(SUBJECT, "analytics", 0)
    # Direct invalidation only: the under-declared derived entry survives even
    # though the closure computation DETECTS it (detect-but-not-enforce).
    assert record["invalidated_keys"] == ["summary_1"]
    assert record["transitive_keys"] == ["fallback_transport_1"]
    assert "fallback_transport_1" in record["left_live"]
    leak = ablation.get("fallback_transport_1", "admin", 0)
    assert leak.status == "HIT"
    assert leak.served_from_revoked_ancestry is True
    # The leak is surfaced in run_candidate's aggregated detail as well.
    outcome = run_candidate(
        {
            "case_id": "ablation-leak",
            "mode": "ablation",
            "cache_ops": [
                {"op": "put", "key": "s", "value": "v", "deps": [[SUBJECT, "analytics", 0]]},
                {
                    "op": "put",
                    "key": "t",
                    "value": "tv",
                    "deps": [[SUBJECT, "admin", 0]],
                    "derived_from": ["s"],
                },
                {"op": "revoke", "subject": SUBJECT, "purpose": "analytics", "epoch": 0},
                {"op": "get", "key": "t", "purpose": "admin", "epoch": 0},
            ],
        },
        None,
    )
    detail = json.loads(outcome.detail)
    assert detail["candidate_id"] == ABLATION_ID
    assert detail["leaks"] >= 1
    assert "t" in detail["leak_keys"]


def test_candidate_mode_never_leaks_in_run_candidate() -> None:
    outcome = run_candidate(
        {
            "case_id": "candidate-no-leak",
            "mode": "candidate",
            "cache_ops": [
                {"op": "put", "key": "s", "value": "v", "deps": [[SUBJECT, "analytics", 0]]},
                {
                    "op": "put",
                    "key": "t",
                    "value": "tv",
                    "deps": [[SUBJECT, "admin", 0]],
                    "derived_from": ["s"],
                },
                {"op": "revoke", "subject": SUBJECT, "purpose": "analytics", "epoch": 0},
                {"op": "get", "key": "t", "purpose": "admin", "epoch": 0},
            ],
        },
        None,
    )
    detail = json.loads(outcome.detail)
    assert detail["candidate_id"] == CANDIDATE_ID
    assert detail["leaks"] == 0
    ops = detail["ops"]
    assert ops[-1]["status"] == "REVOKED_ENTRY"
    assert ops[-1]["served_from_revoked_ancestry"] is True


# ---------------------------------------------------------------------------
# Adversarial: purpose / epoch boundaries refused
# ---------------------------------------------------------------------------


def test_unknown_purpose_refused() -> None:
    for cache in (_scenario(), ablation_no_reverse_edges()):
        cache.put("x", "vx", deps=[_dep("clinical", 0)])
        read = cache.get("x", "not-a-purpose", 0)
        assert read.status == "PURPOSE_MISMATCH"
        assert read.served_from_revoked_ancestry is False


def test_stale_epoch_refused() -> None:
    for cache in (_scenario(), ablation_no_reverse_edges()):
        cache.put("x", "vx", deps=[_dep("clinical", 3)])
        read = cache.get("x", "clinical", 2)
        assert read.status == "EPOCH_STALE"
        assert read.served_from_revoked_ancestry is False
        assert cache.get("x", "clinical", 3).status == "HIT"


def test_put_refuses_revoked_dependency_and_revoked_parent() -> None:
    cache = _scenario()
    cache.revoke(SUBJECT, "analytics", 0)
    with pytest.raises(ValueError, match="REVOKED_DEPENDENCY"):
        cache.put("late_1", "v", deps=[_dep("analytics", 0)])
    with pytest.raises(ValueError, match="REVOKED_DEPENDENCY"):
        cache.put("late_2", "v", deps=[_dep("admin", 0)], derived_from=["summary_1"])


def test_put_refuses_missing_parent_and_self_cycle() -> None:
    cache = RevocationCompleteCache()
    with pytest.raises(ValueError, match="DERIVATION_PARENT_MISSING"):
        cache.put("x", "v", deps=[_dep("a", 0)], derived_from=["ghost"])
    with pytest.raises(ValueError, match="DERIVATION_CYCLE"):
        cache.put("x", "v", deps=[_dep("a", 0)], derived_from=["x"])


def test_malformed_inputs_raise_stable_reason_codes() -> None:
    cache = RevocationCompleteCache()
    with pytest.raises(ValueError, match="KEY_MALFORMED"):
        cache.put("", "v", deps=[_dep("a", 0)])
    with pytest.raises(ValueError, match="VALUE_MALFORMED"):
        cache.put("k", "", deps=[_dep("a", 0)])
    with pytest.raises(ValueError, match="DEPS_MALFORMED"):
        cache.put("k", "v", deps=[])
    with pytest.raises(ValueError, match="EPOCH_MALFORMED"):
        cache.get("k", "a", -1)
    with pytest.raises(ValueError, match="PURPOSE_MALFORMED"):
        cache.get("k", "", 0)
    with pytest.raises(ValueError, match="SUBJECT_MALFORMED"):
        cache.revoke("", "a", 0)


def test_revoke_idempotent_and_deterministic_record() -> None:
    cache = _scenario()
    first = _revoke_analytics(cache)
    second = _revoke_analytics(cache)
    assert first["applied"] is True
    assert second["applied"] is False
    assert second["invalidated_keys"] == []
    assert first["direct_keys"] == second["direct_keys"]
    assert first["transitive_keys"] == second["transitive_keys"]


def test_run_candidate_determinism() -> None:
    case = {
        "case_id": "determinism",
        "mode": "candidate",
        "cache_ops": [
            {"op": "put", "key": "s", "value": "v", "deps": [[SUBJECT, "analytics", 0]]},
            {
                "op": "put",
                "key": "t",
                "value": "tv",
                "deps": [[SUBJECT, "admin", 0]],
                "derived_from": ["s"],
            },
            {"op": "get", "key": "s", "purpose": "analytics", "epoch": 0},
            {"op": "revoke", "subject": SUBJECT, "purpose": "analytics", "epoch": 0},
            {"op": "get", "key": "s", "purpose": "analytics", "epoch": 0},
            {"op": "get", "key": "t", "purpose": "admin", "epoch": 0},
        ],
    }
    one = run_candidate(case, None)
    two = run_candidate(case, None)
    assert one.observed_outcome == two.observed_outcome == "ADMIT"
    assert one.detail == two.detail


def test_run_candidate_fail_closed_on_malformed_case() -> None:
    for bad in (
        "not-an-object",
        {"case_id": "x", "mode": "candidate", "cache_ops": []},
        {"case_id": "x", "mode": "warp", "cache_ops": [{"op": "get", "key": "k"}]},
        {"case_id": "x", "mode": "candidate", "cache_ops": [{"op": "teleport"}]},
        {
            "case_id": "x",
            "mode": "candidate",
            "cache_ops": [{"op": "put", "key": "k", "value": "v", "deps": []}],
        },
    ):
        outcome = run_candidate(bad, None)  # type: ignore[arg-type]
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.counted_as_success is False
        assert any(
            code in outcome.detail
            for code in (
                "WORKLOAD_MALFORMED",
                "DEPS_MALFORMED",
            )
        )


def test_describe_mechanism_flags_and_module_level() -> None:
    candidate_desc = RevocationCompleteCache().describe_mechanism()
    ablation_desc = ablation_no_reverse_edges().describe_mechanism()
    assert candidate_desc["candidate_id"] == CANDIDATE_ID
    assert candidate_desc["enforce_reverse_edges"] is True
    assert candidate_desc["invalidation_kind"] == "dependency_closure"
    assert ablation_desc["candidate_id"] == ABLATION_ID
    assert ablation_desc["enforce_reverse_edges"] is False
    assert ablation_desc["invalidation_kind"] == "direct_only"
    for desc in (candidate_desc, ablation_desc, describe_mechanism()):
        assert desc["version"] == CANDIDATE_VERSION
        assert desc["guarantees"] and desc["non_guarantees"]
        json.dumps(desc)  # JSON-serializable
