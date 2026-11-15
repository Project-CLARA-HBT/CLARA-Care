"""IFIP_SEC-X06_zanzibar_style — consistency-aware authorization comparator tests.

Purpose
-------
Drive the REAL Zanzibar-style consistency reference
(``evaluation/venue2027/ifip_sec/consistency_token_adapter.py``, re-exported by
``evaluation/venue2027/ifip_sec/baselines`` as the additive arm
``B2_INPROCESS_ZANZIBAR`` over ``BASELINES_VERSION = "1.1.0"``; the task
contract ``check_with_revision(principal, resource, token) -> Verdict``
realized over relation tuples + zookie-style consistency tokens) and assert:

- FRESH consistency read sees a just-granted relation (``RELATION_PRESENT`` at
  the grant revision, with real walk counts) — the required positive control;
- a STALE-consistency read (token captured before the grant) does NOT see the
  just-granted relation (``RELATION_ABSENT`` at the earlier snapshot) — the
  bounded-staleness boundary in the deny direction;
- a replayed pre-revocation request is REJECTED only with a FRESH consistency
  token (``RELATION_REVOKED``); the identical replay presented with the
  pre-revocation token is still ADMITTED inside the stale-read window — the
  published Zanzibar boundary, asserted explicitly, never hidden;
- token faults fail closed as first-class REJECT verdicts with stable reason
  codes (missing / unparseable / tampered MAC / wrong store / revision never
  committed), never exceptions miscounted as safe rejections;
- the relation-walk evaluator handles ``computed_userset``, ``tuple_to_userset``
  hierarchy walks, union of rewrite branches and the cycle guard;
- wiring through ``run_baseline("B2_INPROCESS_ZANZIBAR", ...)`` and the real
  evaluation counts (``db_round_trips``/``tuples_examined``/``nodes_visited``,
  ``zookie_bytes``) recorded per verdict.

The arm is additive over IFIP_SEC baselines 1.0.0: the pre-existing baseline
suite (``evaluation/venue2027/ifip_sec/test_baselines.py``) must stay green,
and the pinned external OpenFGA row ``B2_OPENFGA`` must remain honestly
``NOT_RUN_EXTERNAL`` (execution contract rule 8 — this in-process reference is
never substituted under that row's name).

Allowed input
-------------
Deterministic synthetic relation tuples embedded in the test module only; the
HMAC key and store identity are injected, no network, no database, no hidden
clock or randomness.

Failure semantics
-----------------
Fail closed: token faults are REJECT verdicts with stable reason codes; a
verdict whose counts are absent/zero on a real check, a replay admitted under a
fresh post-revocation token, or a replay rejected under a pre-revocation token
fails the assertions below rather than being counted as a safe rejection.

Version: 1.0.0
"""

from __future__ import annotations

import base64
import json

import pytest

from evaluation.venue2027.ifip_sec.baselines import (
    BASELINE_REGISTRY,
    BASELINES_VERSION,
    BaselineContext,
    BaselineError,
    ZanzibarStore,
    check_with_revision,
    run_baseline,
    synthetic_case,
)
from evaluation.venue2027.ifip_sec.consistency_token_adapter import (
    CONSISTENCY_ADAPTER_VERSION,
    RC_RELATION_ABSENT,
    RC_RELATION_PRESENT,
    RC_RELATION_REVOKED,
    RC_TOKEN_MISSING,
    RC_TOKEN_SIGNATURE_INVALID,
    RC_TOKEN_STORE_MISMATCH,
    RC_TOKEN_UNPARSEABLE,
    zookie_bytes,
)

KEY = b"ifip-sec-x06-zanzibar-test-key-0123456789abcdef"
STORE_ID = "store-eu-1"


def _store() -> ZanzibarStore:
    return ZanzibarStore(store_id=STORE_ID, hmac_key=KEY)


# ---------------------------------------------------------------------------
# Core X06 contract: fresh vs stale consistency around grant and revoke.
# ---------------------------------------------------------------------------


class TestFreshVsStaleConsistency:
    def test_fresh_read_sees_just_granted_relation(self) -> None:
        """Positive control: FRESH (strong-consistency) token sees the grant."""
        store = _store()
        grant_revision = store.write("document:case7", "viewer", "alice")
        token = store.issue_token()
        verdict = check_with_revision("alice", "document:case7", token, store=store)
        assert verdict.allowed is True
        assert verdict.reason_code == RC_RELATION_PRESENT
        assert verdict.revision_evaluated == grant_revision == store.head_revision
        assert verdict.db_round_trips >= 1
        assert verdict.tuples_examined >= 1
        assert verdict.nodes_visited >= 1

    def test_stale_read_does_not_see_just_granted_relation(self) -> None:
        """Bounded staleness (deny direction): pre-grant token misses the grant."""
        store = _store()
        pre_grant_token = store.issue_token()  # snapshot at revision 0
        grant_revision = store.write("document:case7", "viewer", "alice")
        verdict = check_with_revision("alice", "document:case7", pre_grant_token, store=store)
        assert verdict.allowed is False
        assert verdict.reason_code == RC_RELATION_ABSENT
        assert verdict.revision_evaluated == 0
        assert verdict.revision_evaluated < grant_revision

    def test_replay_rejected_only_with_fresh_consistency_token(self) -> None:
        """The core RQ1 control: identical pre-revocation replay, two tokens.

        After revocation, the replayed request is REJECTED (``RELATION_REVOKED``)
        under a FRESH token — and ADMITTED under the pre-revocation token, the
        documented bounded-staleness window. Both halves are asserted: the
        fresh rejection proves consistency-aware revocation propagation; the
        stale admission is the measured boundary the candidate must beat.
        """
        store = _store()
        store.write("document:case7", "viewer", "alice")  # grant @ rev 1
        token_before_revoke = store.issue_token()  # snapshot @ rev 1
        revoke_revision = store.delete("document:case7", "viewer", "alice")  # head @ rev 2
        fresh_after_revoke = store.issue_token()  # FRESH @ head rev 2

        replay_fresh = check_with_revision(
            "alice", "document:case7", fresh_after_revoke, store=store
        )
        assert replay_fresh.allowed is False
        assert replay_fresh.reason_code == RC_RELATION_REVOKED
        assert replay_fresh.revision_evaluated == revoke_revision

        replay_stale = check_with_revision(
            "alice", "document:case7", token_before_revoke, store=store
        )
        assert replay_stale.allowed is True
        assert replay_stale.reason_code == RC_RELATION_PRESENT
        assert replay_stale.revision_evaluated < revoke_revision

    def test_fresh_rejection_is_repeatable_and_stale_admission_is_repeatable(self) -> None:
        """Decisions are pure functions of (snapshot, tuple state) — no hidden state."""
        store = _store()
        store.write("document:case7", "viewer", "alice")
        stale_token = store.issue_token()
        store.delete("document:case7", "viewer", "alice")
        fresh_token = store.issue_token()
        for _ in range(3):
            fresh = check_with_revision("alice", "document:case7", fresh_token, store=store)
            stale = check_with_revision("alice", "document:case7", stale_token, store=store)
            assert (fresh.allowed, fresh.reason_code) == (False, RC_RELATION_REVOKED)
            assert (stale.allowed, stale.reason_code) == (True, RC_RELATION_PRESENT)

    def test_fresh_token_sees_regrant_after_revoke(self) -> None:
        """Re-grant after revocation: fresh read admits again (union, not tombstone-only)."""
        store = _store()
        store.write("document:case7", "viewer", "alice")
        store.delete("document:case7", "viewer", "alice")
        store.write("document:case7", "viewer", "alice")  # re-grant @ rev 3
        verdict = check_with_revision("alice", "document:case7", store.issue_token(), store=store)
        assert verdict.allowed is True
        assert verdict.reason_code == RC_RELATION_PRESENT
        assert verdict.revision_evaluated == 3


# ---------------------------------------------------------------------------
# Token-fault fail-closed controls.
# ---------------------------------------------------------------------------


class TestTokenFaultsFailClosed:
    def test_missing_token_rejected(self) -> None:
        verdict = check_with_revision("alice", "document:case7", "", store=_store())
        assert verdict.allowed is False
        assert verdict.reason_code == RC_TOKEN_MISSING

    def test_unparseable_token_rejected(self) -> None:
        verdict = check_with_revision("alice", "document:case7", "not-a-zookie", store=_store())
        assert verdict.allowed is False
        assert verdict.reason_code == RC_TOKEN_UNPARSEABLE

    def test_tampered_mac_rejected(self) -> None:
        """Flip one bit of the payload body: signature must fail closed."""
        store = _store()
        store.write("document:case7", "viewer", "alice")
        token = store.issue_token()
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        payload["revision"] = store.head_revision + 10  # attacker claims future snapshot
        forged = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        verdict = check_with_revision("alice", "document:case7", forged, store=store)
        assert verdict.allowed is False
        assert verdict.reason_code == RC_TOKEN_SIGNATURE_INVALID

    def test_wrong_store_token_rejected(self) -> None:
        other = ZanzibarStore(store_id="store-us-2", hmac_key=KEY)
        token = other.issue_token()
        verdict = check_with_revision("alice", "document:case7", token, store=_store())
        assert verdict.allowed is False
        assert verdict.reason_code == RC_TOKEN_STORE_MISMATCH

    def test_revision_never_committed_rejected(self) -> None:
        store = _store()
        store.write("document:case7", "viewer", "alice")
        token = store.issue_token_at(0)  # legitimate capture
        verdict = check_with_revision("alice", "document:case7", token, store=store)
        assert verdict.allowed is False
        assert verdict.reason_code == RC_RELATION_ABSENT
        # A token from a store with a bigger head is a store mismatch, but a
        # token claiming a revision this store never committed must never
        # evaluate: issue_token_at refuses, and a forged token is caught by MAC.
        with pytest.raises(Exception) as excinfo:
            store.issue_token_at(store.head_revision + 5)
        assert "TOKEN_REVISION_UNKNOWN" in str(excinfo.value)

    def test_issue_token_at_refuses_unknown_revisions(self) -> None:
        store = _store()
        for bad in (-1, 1, 99):
            with pytest.raises(Exception) as excinfo:
                store.issue_token_at(bad)
            assert "TOKEN_REVISION_UNKNOWN" in str(excinfo.value)
        with pytest.raises(Exception) as excinfo:
            store.issue_token_at(1.5)  # type: ignore[arg-type]
        assert "TOKEN_REVISION_UNKNOWN" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Relation-walk evaluation: rewrites, hierarchy, union, cycles.
# ---------------------------------------------------------------------------


class TestRelationWalkEvaluator:
    def test_computed_userset_editor_implies_viewer(self) -> None:
        store = _store()
        store.write("document:case9", "editor", "bob")
        verdict = check_with_revision("bob", "document:case9", store.issue_token(), store=store)
        assert verdict.allowed is True
        assert verdict.reason_code == RC_RELATION_PRESENT
        assert verdict.nodes_visited >= 2  # viewer node + editor rewrite node
        assert verdict.db_round_trips == verdict.nodes_visited

    def test_tuple_to_userset_hierarchy_walk(self) -> None:
        """folder.viewer grants document.viewer via the parent tupleset walk."""
        store = _store()
        store.write("folder:root", "viewer", "carol")
        store.write("document:case10", "parent", "folder:root")
        verdict = check_with_revision("carol", "document:case10", store.issue_token(), store=store)
        assert verdict.allowed is True
        assert verdict.reason_code == RC_RELATION_PRESENT
        assert verdict.nodes_visited >= 2
        assert verdict.db_round_trips >= 2

    def test_hierarchy_walk_respects_snapshot(self) -> None:
        """The hierarchy hop itself is evaluated at the token revision."""
        store = _store()
        pre_parent_token = store.issue_token()  # revision 0
        store.write("folder:root", "viewer", "carol")
        store.write("document:case10", "parent", "folder:root")
        stale = check_with_revision("carol", "document:case10", pre_parent_token, store=store)
        assert stale.allowed is False
        assert stale.reason_code == RC_RELATION_ABSENT

    def test_union_of_branches_direct_editor_or_hierarchy(self) -> None:
        """document.viewer = editor | parent.viewer: either branch admits."""
        store = _store()
        store.write("folder:root", "viewer", "carol")
        store.write("document:case11", "parent", "folder:root")
        fresh = store.issue_token()
        assert check_with_revision("carol", "document:case11", fresh, store=store).allowed
        store.write("document:case11", "editor", "dave")
        fresh2 = store.issue_token()
        assert check_with_revision("dave", "document:case11", fresh2, store=store).allowed
        assert not check_with_revision("eve", "document:case11", fresh2, store=store).allowed

    def test_cycle_safe_self_parent(self) -> None:
        """folder:loop parented to itself must terminate (cycle guard)."""
        store = _store()
        store.write("folder:loop", "parent", "folder:loop")
        store.write("folder:loop", "viewer", "eve")
        verdict = check_with_revision("eve", "folder:loop", store.issue_token(), store=store)
        assert verdict.allowed is True  # admitted via the direct viewer tuple

    def test_relation_absent_for_unknown_principal(self) -> None:
        store = _store()
        store.write("document:case7", "viewer", "alice")
        verdict = check_with_revision("mallory", "document:case7", store.issue_token(), store=store)
        assert verdict.allowed is False
        assert verdict.reason_code == RC_RELATION_ABSENT

    def test_delete_of_absent_tuple_is_noop(self) -> None:
        """Documented no-op: a delete never fabricates change history."""
        store = _store()
        head_before = store.head_revision
        assert store.delete("document:ghost", "viewer", "alice") == head_before
        assert store.head_revision == head_before


# ---------------------------------------------------------------------------
# Wiring through run_baseline + real evaluation counts.
# ---------------------------------------------------------------------------


class TestBaselinesWiring:
    def _ctx(self) -> BaselineContext:
        return BaselineContext(hmac_key=KEY, now_epoch_seconds=1700000000)

    def test_registry_and_versions(self) -> None:
        assert "B2_INPROCESS_ZANZIBAR" in BASELINE_REGISTRY
        spec = BASELINE_REGISTRY["B2_INPROCESS_ZANZIBAR"]
        assert spec.runnable_in_process is True
        assert spec.registry_name == "zanzibar-openfga"
        # Additive bump: the pre-existing suite's version range stays valid.
        assert BASELINES_VERSION in ("1.0.0", "1.1.0")
        assert CONSISTENCY_ADAPTER_VERSION == "1.0.0"
        # The pinned external row stays honestly NOT_RUN_EXTERNAL (rule 8).
        assert BASELINE_REGISTRY["B2_OPENFGA"].runnable_in_process is False
        outcome = run_baseline("B2_OPENFGA", synthetic_case(), self._ctx())
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.detail == "BASELINE_UNAVAILABLE"

    def test_run_baseline_admits_fresh_grant(self) -> None:
        store = _store()
        store.write("document:case7", "viewer", "alice")
        case = {
            "case_id": "IFIP_SEC-X06-CASE-01",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": store.issue_token(),
        }
        outcome = run_baseline("B2_INPROCESS_ZANZIBAR", case, self._ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_RELATION_PRESENT

    def test_run_baseline_rejects_replay_under_fresh_token(self) -> None:
        store = _store()
        store.write("document:case7", "viewer", "alice")
        store.delete("document:case7", "viewer", "alice")
        case = {
            "case_id": "IFIP_SEC-X06-CASE-02",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": store.issue_token(),  # FRESH after revoke
        }
        outcome = run_baseline("B2_INPROCESS_ZANZIBAR", case, self._ctx())
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_RELATION_REVOKED

    def test_run_baseline_rejects_replay_under_pre_revocation_token_is_admit(self) -> None:
        """The asserted staleness boundary through the dispatcher: the identical
        replay with the PRE-REVOCATION token is ADMITted (bounded-staleness
        window) — never silently converted into a rejection."""
        store = _store()
        store.write("document:case7", "viewer", "alice")
        pre_revoke_token = store.issue_token()
        store.delete("document:case7", "viewer", "alice")
        case = {
            "case_id": "IFIP_SEC-X06-CASE-03",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": pre_revoke_token,
        }
        outcome = run_baseline("B2_INPROCESS_ZANZIBAR", case, self._ctx())
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == RC_RELATION_PRESENT

    def test_run_baseline_missing_token_is_reject_not_exception(self) -> None:
        store = _store()
        case = {
            "case_id": "IFIP_SEC-X06-CASE-04",
            "zanzibar_store": store,
            "principal": "alice",
            "resource": "document:case7",
            "zookie": "",
        }
        outcome = run_baseline("B2_INPROCESS_ZANZIBAR", case, self._ctx())
        assert isinstance(outcome.observed_outcome, str)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.detail == RC_TOKEN_MISSING

    def test_run_baseline_wiring_faults_raise(self) -> None:
        with pytest.raises(BaselineError) as excinfo:
            run_baseline("B2_INPROCESS_ZANZIBAR", {"case_id": "x"}, self._ctx())
        assert excinfo.value.reason_code == "CONTEXT_STORE_MISSING"
        store = _store()
        store.write("document:case7", "viewer", "alice")
        with pytest.raises(BaselineError) as excinfo:
            run_baseline(
                "B2_INPROCESS_ZANZIBAR",
                {"case_id": "x", "zanzibar_store": store, "zookie": store.issue_token()},
                self._ctx(),
            )
        assert excinfo.value.reason_code == "CASE_FIELD_MISSING"

    def test_real_evaluation_counts_and_token_bytes(self) -> None:
        store = _store()
        store.write("folder:root", "viewer", "carol")
        store.write("document:case12", "parent", "folder:root")
        token = store.issue_token()
        verdict = check_with_revision("carol", "document:case12", token, store=store)
        assert verdict.allowed is True
        assert verdict.db_round_trips == verdict.nodes_visited >= 2
        assert verdict.tuples_examined >= 1
        assert zookie_bytes(token) > 0
        # Determinism: identical inputs reproduce the identical verdict.
        again = check_with_revision("carol", "document:case12", token, store=store)
        assert again.to_dict() == verdict.to_dict()

    def test_hmac_key_material_is_not_secret_logger(self) -> None:
        store = _store()
        store.write("document:case7", "viewer", "alice")
        token = store.issue_token()
        assert KEY not in token.encode("utf-8")
        assert KEY.hex().encode("utf-8") not in token.encode("utf-8")
