"""Tests for POPETS-X03_cache_control (purpose-bound cache control layer).

Positive controls (must pass):
- Purpose isolation: the same (subject, grant, lineage) context cached under
  purpose A is NOT served to a request under purpose B — the read refuses with
  ``PURPOSE_MISMATCH`` and the purposes occupy disjoint key spaces (separate
  entries, no shared hits).
- ``put``/``get`` round-trip per exact 4-tuple key; ``recompute_or_fetch``
  serves ``HIT`` on repeats and ``RECOMPUTED`` exactly once on first use.
- ``revoke(subject)`` clears ALL purposes (and grants and epochs) at once and
  the completeness assertion then passes; the epoch rotates exactly once per
  event and a repeat revocation is idempotent (removes nothing).

Adversarial controls (must be refused, never fabricated):
- A stale-epoch key is not served: after revocation the pre-rotation key
  (correct purpose, old epoch) refuses with ``EPOCH_STALE`` and empty context;
  a current-epoch key for the revoked subject refuses with ``REVOKED_SUBJECT``;
  ``put`` for the revoked subject raises fail-closed.
- ``assert_revocation_complete`` catches a forgotten key: manually re-installing
  a live entry for a revoked subject makes the assertion raise
  ``RevocationLeakError`` naming the surviving key, and the entry is then
  provably unservable through the public read path.
- Malformed keys/contexts/subjects fail closed with stable reason codes.
- A refused request never triggers recomputation (the injected callable must
  not be invoked), so no bytes are produced for a revoked subject.

Determinism: synthetic identifiers only; no network, no DB, no hidden clock or
randomness (all instants are injected logical seconds).
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.popets.cache_control import (
    CACHE_CONTROL_VERSION,
    REASON_ARTIFACTS_MALFORMED,
    REASON_CACHE_MISS,
    REASON_CONTEXT_MALFORMED,
    REASON_CREATED_AT_MALFORMED,
    REASON_EPOCH_STALE,
    REASON_HIT,
    REASON_KEY_EPOCH_STALE,
    REASON_KEY_MALFORMED,
    REASON_PURPOSE_MISMATCH,
    REASON_RECOMPUTE_MALFORMED,
    REASON_RECOMPUTED,
    REASON_REVOCATION_LEAK,
    REASON_REVOKED_SUBJECT,
    REASON_SUBJECT_MALFORMED,
    CacheControlError,
    CacheEntry,
    CacheKey,
    PurposeBoundCache,
    RevocationLeakError,
    assert_revocation_complete,
)

SUBJECT = "s1"
GRANT = "g-med"
CONTEXT = "BP 120/80; HR 72"


def _key(purpose: str = "clinical", epoch: int = 0, subject: str = SUBJECT) -> CacheKey:
    return CacheKey(subject=subject, grant=GRANT, purpose=purpose, consent_epoch=epoch)


def _populate_two_purposes(
    cache: PurposeBoundCache, purposes: tuple[str, str] = ("clinical", "analytics")
) -> dict[str, CacheEntry]:
    entries = {}
    for purpose in purposes:
        entries[purpose] = cache.put(
            _key(purpose),
            CONTEXT,
            source_artifacts=["vitals_1"],
            created_at_seconds=10,
        )
    return entries


# ---------------------------------------------------------------------------
# Positive: put/get round-trip and purpose isolation
# ---------------------------------------------------------------------------


def test_put_get_round_trip_per_exact_key() -> None:
    cache = PurposeBoundCache()
    entry = cache.put(_key(), CONTEXT, source_artifacts={"vitals_1"}, created_at_seconds=10)
    result = cache.get(_key())
    assert result.status == REASON_HIT
    assert result.context == CONTEXT
    assert result.entry is entry
    assert result.served is True
    # Serialized views are JSON-serializable and carry byte counts, not bytes.
    assert json.loads(json.dumps(entry.to_dict()))["context_bytes"] == len(CONTEXT.encode("utf-8"))
    assert "context" not in entry.to_dict()


def test_same_context_two_purposes_are_disjoint_key_spaces() -> None:
    """Purpose A's cached entry is unreachable from purpose B and vice versa."""
    cache = PurposeBoundCache()
    entries = _populate_two_purposes(cache)
    assert entries["clinical"].key != entries["analytics"].key
    assert cache.get(_key("clinical")).status == REASON_HIT
    assert cache.get(_key("analytics")).status == REASON_HIT
    assert cache.get(_key("clinical")).entry is entries["clinical"]
    assert cache.get(_key("analytics")).entry is entries["analytics"]
    # Each purpose sees exactly its own entry; the key space did not collapse.
    assert len(cache.live_keys(SUBJECT)) == 2
    assert {k.purpose for k in cache.live_keys(SUBJECT)} == {"clinical", "analytics"}


def test_explicit_requesting_purpose_isolation() -> None:
    """A request declaring purpose B cannot read the entry bound to purpose A."""
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    cross = cache.get(_key("clinical"), requesting_purpose="analytics")
    assert cross.status == REASON_PURPOSE_MISMATCH
    assert cross.context == ""
    assert cross.entry is None
    assert cross.served is False
    # The matching declaration still hits its own entry.
    same = cache.get(_key("clinical"), requesting_purpose="clinical")
    assert same.status == REASON_HIT and same.context == CONTEXT


def test_recompute_or_fetch_serves_hit_on_repeat_and_recomputes_once() -> None:
    cache = PurposeBoundCache()
    calls: list[CacheKey] = []

    def recompute(key: CacheKey) -> str:
        calls.append(key)
        return CONTEXT

    first = cache.recompute_or_fetch(_key("clinical"), recompute)
    assert first.status == REASON_RECOMPUTED
    assert first.context == CONTEXT
    assert first.entry is not None and first.entry.key.purpose == "clinical"
    second = cache.recompute_or_fetch(_key("clinical"), recompute)
    assert second.status == REASON_HIT
    assert calls == [_key("clinical")]
    # The other purpose still misses and pays its own recomputation.
    other = cache.recompute_or_fetch(_key("analytics"), recompute)
    assert other.status == REASON_RECOMPUTED
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# Positive + adversarial: whole-subject revocation across ALL purposes
# ---------------------------------------------------------------------------


def test_revocation_clears_all_purposes_and_rotates_epoch_once() -> None:
    cache = PurposeBoundCache()
    _populate_two_purposes(cache, ("clinical", "analytics", "billing"))
    report = cache.revoke(SUBJECT)
    assert report.removed_entry_count == 3
    assert report.removed_purposes == ("analytics", "billing", "clinical")
    assert report.epoch_before == 0 and report.epoch_after == 1
    assert cache.epoch_of(SUBJECT) == 1
    assert cache.live_keys(SUBJECT) == ()
    assert json.loads(json.dumps(report.to_dict()))["removed_entry_count"] == 3
    # Every purpose's entry is gone — provably, executably.
    completeness = assert_revocation_complete(cache, SUBJECT)
    assert completeness["complete"] is True
    assert completeness["live_entry_count"] == 0


def test_repeat_revocation_is_idempotent_and_still_rotates_once_per_event() -> None:
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    first = cache.revoke(SUBJECT)
    assert first.removed_entry_count == 2 and first.already_revoked is False
    second = cache.revoke(SUBJECT)
    assert second.removed_entry_count == 0
    assert second.already_revoked is True
    assert second.epoch_after == second.epoch_before + 1
    assert cache.epoch_of(SUBJECT) == 2
    assert_revocation_complete(cache, SUBJECT)


def test_other_subjects_and_grants_are_unaffected_by_a_revocation() -> None:
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    other = cache.put(
        CacheKey(subject="s2", grant=GRANT, purpose="clinical", consent_epoch=0),
        CONTEXT,
        created_at_seconds=11,
    )
    cross_grant = cache.put(
        CacheKey(subject=SUBJECT, grant="g-other", purpose="clinical", consent_epoch=0),
        CONTEXT,
        created_at_seconds=11,
    )
    cache.revoke(SUBJECT)
    # The same-named purpose under a different subject/grant stays live.
    assert cache.get(other.key).status == REASON_HIT
    assert cache.get(cross_grant.key).status == REASON_EPOCH_STALE  # same subject: rotated
    assert cache.get(other.key, requesting_purpose="clinical").context == CONTEXT


def test_post_revocation_dispatches_recompute_nothing_at_any_epoch() -> None:
    """Post-revocation, no dispatch recomputes for the subject under any key.

    Revocation is terminal in this layer: the tombstone refuses every read and
    write for the subject, so an authorized continuation requires a NEW grant
    scope outside this cache — never a re-keyed entry inside it.
    """
    cache = PurposeBoundCache()
    calls: list[CacheKey] = []

    def recompute(key: CacheKey) -> str:
        calls.append(key)
        return CONTEXT

    assert cache.recompute_or_fetch(_key("clinical"), recompute).status == REASON_RECOMPUTED
    cache.revoke(SUBJECT)
    # A pre-rotation dispatch replay is refused: the caller cannot present the
    # old epoch as current, and the refusal produces no bytes.
    replay = cache.get(_key("clinical"), requesting_purpose="clinical")
    assert replay.status == REASON_EPOCH_STALE
    assert replay.context == "" and replay.entry is None
    # Even a rotated-epoch key is refused for the tombstoned subject.
    fresh_attempt = cache.recompute_or_fetch(_key("clinical", epoch=1), recompute)
    assert fresh_attempt.status == REASON_REVOKED_SUBJECT
    assert fresh_attempt.context == "" and fresh_attempt.entry is None
    assert calls == [_key("clinical")]  # only the pre-revocation recompute ran


# ---------------------------------------------------------------------------
# Adversarial: stale-epoch key is not served; revoked subject fail-closed
# ---------------------------------------------------------------------------


def test_stale_epoch_key_is_not_served_after_revocation() -> None:
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    cache.revoke(SUBJECT)
    for purpose in ("clinical", "analytics"):
        stale = cache.get(_key(purpose, epoch=0), requesting_purpose=purpose)
        assert stale.status == REASON_EPOCH_STALE
        assert stale.context == ""
        assert stale.entry is None
        assert stale.served is False


def test_current_epoch_key_for_revoked_subject_is_refused_and_writes_fail_closed() -> None:
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    cache.revoke(SUBJECT)
    forged = cache.get(_key("clinical", epoch=1))
    assert forged.status == REASON_REVOKED_SUBJECT
    assert forged.context == ""
    with pytest.raises(CacheControlError) as excinfo:
        cache.put(_key("clinical", epoch=1), CONTEXT)
    assert excinfo.value.reason_code == REASON_REVOKED_SUBJECT
    with pytest.raises(CacheControlError) as excinfo_wild:
        cache.put(CacheKey(subject=SUBJECT, grant="g-any", purpose="*", consent_epoch=1), CONTEXT)
    assert excinfo_wild.value.reason_code == REASON_REVOKED_SUBJECT


def test_put_refuses_stale_epoch_write() -> None:
    cache = PurposeBoundCache()
    cache.put(
        CacheKey(subject="s2", grant=GRANT, purpose="clinical", consent_epoch=0),
        CONTEXT,
        created_at_seconds=11,
    )
    cache.revoke("s2")  # rotates s2's epoch to 1; s1 (untouched) stays at 0
    with pytest.raises(CacheControlError) as excinfo:
        cache.put(CacheKey(subject="s2", grant=GRANT, purpose="clinical", consent_epoch=0), CONTEXT)
    assert excinfo.value.reason_code == REASON_KEY_EPOCH_STALE


def test_assertion_catches_forgotten_key() -> None:
    """A manually surviving entry for a revoked subject fails the completeness proof."""
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    cache.revoke(SUBJECT)
    forgotten_key = CacheKey(subject=SUBJECT, grant=GRANT, purpose="billing", consent_epoch=0)
    cache._entries[forgotten_key] = CacheEntry(  # noqa: SLF001 — simulate a forgotten write
        key=forgotten_key,
        context=CONTEXT,
        source_artifacts=frozenset({"notes_1"}),
        created_at_seconds=12,
    )
    with pytest.raises(RevocationLeakError) as excinfo:
        assert_revocation_complete(cache, SUBJECT)
    assert excinfo.value.reason_code == REASON_REVOCATION_LEAK
    assert "billing" in str(excinfo.value)
    # And the forgotten entry is not servable through the public path either.
    assert cache.get(forgotten_key).status == REASON_EPOCH_STALE
    assert cache.get(forgotten_key).context == ""


def test_revocation_leak_error_is_a_value_error_subclass_with_stable_code() -> None:
    assert issubclass(RevocationLeakError, ValueError)
    assert issubclass(RevocationLeakError, CacheControlError)
    err = RevocationLeakError(REASON_REVOCATION_LEAK, "boom")
    assert err.reason_code == REASON_REVOCATION_LEAK


# ---------------------------------------------------------------------------
# Fail-closed input validation
# ---------------------------------------------------------------------------


def test_malformed_inputs_fail_closed_with_stable_reason_codes() -> None:
    cache = PurposeBoundCache()
    with pytest.raises(CacheControlError) as excinfo:
        CacheKey(subject="", grant=GRANT, purpose="clinical", consent_epoch=0)
    assert excinfo.value.reason_code == REASON_KEY_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_bool:
        CacheKey(subject=SUBJECT, grant=GRANT, purpose="clinical", consent_epoch=True)
    assert excinfo_bool.value.reason_code == REASON_KEY_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_neg:
        CacheKey(subject=SUBJECT, grant=GRANT, purpose="clinical", consent_epoch=-1)
    assert excinfo_neg.value.reason_code == REASON_KEY_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_ctx:
        cache.put(_key(), "")
    assert excinfo_ctx.value.reason_code == REASON_CONTEXT_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_art:
        cache.put(_key(), CONTEXT, source_artifacts=[""])
    assert excinfo_art.value.reason_code == REASON_ARTIFACTS_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_time:
        cache.put(_key(), CONTEXT, created_at_seconds=-5)
    assert excinfo_time.value.reason_code == REASON_CREATED_AT_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_subj:
        cache.revoke("")
    assert excinfo_subj.value.reason_code == REASON_SUBJECT_MALFORMED
    with pytest.raises(CacheControlError) as excinfo_rc:
        cache.recompute_or_fetch(_key("clinical"), lambda _k: "")
    assert excinfo_rc.value.reason_code == REASON_RECOMPUTE_MALFORMED


def test_read_path_refusals_never_raise_and_never_serve_bytes() -> None:
    cache = PurposeBoundCache()
    missing = cache.get(_key("clinical"))
    assert missing.status == REASON_CACHE_MISS and missing.context == ""
    bad_purpose = cache.get(_key("clinical"), requesting_purpose="")
    assert bad_purpose.status == REASON_KEY_MALFORMED and bad_purpose.context == ""
    non_key = cache.get("not-a-key")  # type: ignore[arg-type]
    assert non_key.status == REASON_KEY_MALFORMED and non_key.context == ""
    empty = PurposeBoundCache()
    empty.revoke("ghost")
    assert empty.get(
        CacheKey(subject="ghost", grant=GRANT, purpose="p", consent_epoch=1)
    ).status == (REASON_REVOKED_SUBJECT)


def test_refused_request_never_triggers_recomputation() -> None:
    """Recomputation is authorized work: a refused request must not invoke it."""
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    cache.revoke(SUBJECT)
    calls: list[CacheKey] = []

    def recompute(key: CacheKey) -> str:
        calls.append(key)
        return CONTEXT

    for status in (
        cache.recompute_or_fetch(_key("clinical", epoch=0), recompute).status,
        cache.recompute_or_fetch(_key("clinical", epoch=1), recompute).status,
        cache.recompute_or_fetch(
            _key("analytics", epoch=1), recompute, requesting_purpose="billing"
        ).status,
    ):
        assert status in (REASON_EPOCH_STALE, REASON_REVOKED_SUBJECT, REASON_PURPOSE_MISMATCH)
    assert calls == []


def test_version_and_snapshot_are_stable_and_serializable() -> None:
    cache = PurposeBoundCache()
    _populate_two_purposes(cache)
    cache.revoke(SUBJECT)
    snapshot = cache.snapshot()
    assert snapshot["version"] == CACHE_CONTROL_VERSION
    assert snapshot["invalidation_events"] == 1
    assert snapshot["revoked_subjects"] == [SUBJECT]
    assert snapshot["epochs"] == {SUBJECT: 1}
    assert json.loads(json.dumps(snapshot)) == snapshot
