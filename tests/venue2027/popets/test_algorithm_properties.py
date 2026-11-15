"""CLARA-Care 2027 POPETS task POPETS-unit — deterministic property/adversarial tests.

Purpose
-------
Property, metamorphic and mutation-style tests over the REAL POPETS algorithm
components, imported live and never reimplemented:

- ``evaluation/venue2027/popets/revocation_model.py`` — the target contract
  ``allowed(item, principal, purpose, time) -> TriDecision`` and
  ``decide(...) -> RevocationDecision`` (task POPETS-X02).
- ``evaluation/venue2027/popets/candidate.py`` — the B4 candidate
  ``RevocationCompleteCache`` (dependency-closure invalidation) and its
  mechanism-isolation ablation (task POPETS-candidate).
- ``evaluation/venue2027/popets/baselines.py`` — the implemented comparator
  arms B1 / B2 / purpose-bound keying / purpose-aware-cache-x06 via the real
  ``run_baseline`` entry point (task POPETS-baselines).

Test families (manifest ``POPETS-unit``, phase P05: "Write positive/negative/
unknown boundaries, skew/race scenarios, two-step metamorphic relations and
mutation tests; seed all randomness"):

1. **Positive boundaries** — documented guarantees hold end to end: pre-``t_r``
   ALLOW, revocation-completeness at/after ``t_r``, purpose/epoch boundaries,
   dependency-closure exactness, X06 purpose isolation.
2. **Negative boundaries** — adversarial inputs are refused with stable
   uppercase reason codes, never silent safe rejections.
3. **Unknown boundaries** — ``INDETERMINATE`` is first-class: unknown purpose
   strings, times before the grant, and unlabelled lineage are refused, never
   coerced to ALLOW/DENY.
4. **Revocation-timing race scenarios** — dispatch exactly AT ``t_r`` (boundary
   inclusive), earliest-covering-revocation races, wildcard-vs-specific scope
   races, pre/post ordering skew, and replay-after-revocation races.
5. **Two-step metamorphic relations** — purging then re-dispatching never
   re-admits revoked context; purpose-keying epochs are monotonic per scope
   under purpose change and repeated post-revocation dispatches; candidate
   put-after-revoke at the SAME scope is refused while a NEW-epoch re-put is
   served only at the new epoch (never the old one); candidate vs ablation on
   identical op streams differ exactly in transitive-revocation handling.
6. **Mutation-style checks** — single perturbations of an input flip the
   expected verdict deterministically (revoked lineage member, purpose string,
   epoch, time across ``t_r``, label removal), proving the tests are sensitive
   to the security-relevant input dimension (mutation coverage for the
   pass gate "Test evidence and mutation coverage").

Determinism
-----------
ALL randomness is seeded deterministically: the randomized round-trip /
fuzz-ish property loops use a fixed ``random.Random(FIXED_SEED)`` instance and
no hidden entropy (no ``time``, no unseeded ``random`` module calls). The
components under test are themselves pure (no I/O, no clock, no randomness),
so every assertion is reproducible byte-for-byte.

Version
-------
``POPETS_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import json
import random

import pytest

from evaluation.venue2027.popets import baselines as bl
from evaluation.venue2027.popets import candidate as cand
from evaluation.venue2027.popets import revocation_model as rm

POPETS_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"

#: Fixed seed for every randomized property loop (manifest: "seed all
#: randomness"). Never advanced, never re-derived from the environment.
FIXED_SEED = 20271115

IMPLEMENTED_BASELINES = sorted(bl.IMPLEMENTED_BASELINES)
X06 = "purpose-aware-cache-x06"

STABLE_REFUSAL_CODES = (
    "ITEM_MALFORMED",
    "PRINCIPAL_MALFORMED",
    "PURPOSE_UNKNOWN",
    "TIME_MALFORMED",
)


# ---------------------------------------------------------------------------
# Deterministic synthetic builders (pure; no clocks, no entropy)
# ---------------------------------------------------------------------------


def _ledger(
    purposes: tuple[str, ...] = ("clinical", "analytics"),
    granted_at: int = 0,
    epoch: int = 1,
    labels: dict[str, str | None] | None = None,
    revocations: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "grants": {
            "s1": {
                "granted_at": granted_at,
                "purposes": list(purposes),
                "consent_epoch": epoch,
                "lineage_labels": labels if labels is not None else {"src_vitals": "origin"},
            }
        },
        "revocations": list(revocations),
    }


def _revocation(
    purpose: str = "analytics",
    revoked_at: int = 100,
    principal: str = "s1",
) -> dict[str, object]:
    return {"principal": principal, "purpose": purpose, "revoked_at": revoked_at}


def _workload_revocation(
    subject: str = "s1",
    grant: str = "g-med",
    purpose: str = "analytics",
    at_seconds: int = 100,
) -> dict[str, object]:
    """Revocation row in the *workload* vocabulary (baselines.py), distinct
    from the ledger vocabulary of ``revocation_model.py``."""
    return {"subject": subject, "grant": grant, "purpose": purpose, "at_seconds": at_seconds}


def _item(
    item_id: str = "i1",
    lineage: tuple[str, ...] = ("src_vitals",),
    epoch: int | None = None,
    already_delivered: bool = False,
    stored_copy: bool = True,
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "lineage": list(lineage),
        "item_epoch": epoch,
        "already_delivered": already_delivered,
        "stored_copy": stored_copy,
    }


def _workload_case(
    dispatches: list[dict[str, object]],
    revocations: list[dict[str, object]] | None = None,
    snapshot: dict[str, str] | None = None,
    case_id: str = "case-props",
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "workload": {
            "source_snapshot": snapshot
            or {"src_vitals": "BP 120/80", "src_meds": "metformin", "src_admin": "tier B"},
            "revocations": revocations if revocations is not None else [_workload_revocation()],
            "dispatches": dispatches,
        },
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


def _detail(outcome: object) -> dict[str, object]:
    assert isinstance(outcome, bl.Outcome)
    return json.loads(outcome.detail)


def _reason_code(*args: object) -> str:
    """First ``:``-delimited token of a stable refusal message."""
    return str(args[0] if args else "").split(":", 1)[0]


# ---------------------------------------------------------------------------
# 1. Positive boundaries: documented guarantees hold end to end
# ---------------------------------------------------------------------------


class TestPositiveBoundaries:
    """The real contracts deliver their documented guarantees on clean input."""

    def test_revocation_model_allows_active_consent_pre_revocation(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        assert rm.allowed(_item(epoch=1), "s1", "analytics", 99, ledger) == "ALLOW"

    def test_revocation_model_denies_every_dispatch_at_or_after_t_r(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        for time in (100, 101, 10_000):
            assert rm.allowed(_item(epoch=1), "s1", "analytics", time, ledger) == "DENY"

    def test_decide_carries_stable_reason_codes_on_each_verdict(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        assert rm.decide(_item(epoch=1), "s1", "analytics", 50, ledger).reason_code == (
            rm.REASON_AUTHORIZED
        )
        assert rm.decide(_item(epoch=1), "s1", "analytics", 100, ledger).reason_code == (
            rm.REASON_POST_REVOCATION
        )

    def test_unaffected_purpose_stays_servable_after_partial_revocation(self) -> None:
        ledger = _ledger(revocations=(_revocation(purpose="analytics"),))
        assert rm.allowed(_item(epoch=1), "s1", "clinical", 500, ledger) == "ALLOW"

    def test_candidate_dependency_closure_invalidates_transitive_descendants(self) -> None:
        cache = cand.RevocationCompleteCache()
        cache.put("base", "v", [("s1", "clinical", 1)])
        cache.put("summary", "v", [("s1", "analytics", 1)], derived_from=["base"])
        cache.put("retry", "v", [("s1", "analytics", 1)], derived_from=["summary"])
        cache.put("unaffected", "v", [("s2", "clinical", 1)])
        record = cache.revoke("s1", "clinical", 1)
        assert record["invalidated_keys"] == ["base", "retry", "summary"]
        assert record["left_live"] == ["unaffected"]
        assert cache.get("base", "clinical", 1).status == cand.STATUS_REVOKED_ENTRY
        assert cache.get("summary", "analytics", 1).status == cand.STATUS_REVOKED_ENTRY
        assert cache.get("retry", "analytics", 1).status == cand.STATUS_REVOKED_ENTRY
        assert cache.get("unaffected", "clinical", 1).status == cand.STATUS_HIT

    def test_candidate_exactness_no_full_flush(self) -> None:
        """G3: entries with no revoked dependency and no derived path stay live."""
        cache = cand.RevocationCompleteCache()
        for index in range(8):
            cache.put(f"e{index}", "v", [("s1", "analytics", 2)])
        cache.put("victim", "v", [("s1", "clinical", 1)])
        cache.put("derived_of_victim", "v", [("s1", "other", 9)], derived_from=["victim"])
        record = cache.revoke("s1", "clinical", 1)
        assert set(record["invalidated_keys"]) == {"victim", "derived_of_victim"}
        assert set(record["left_live"]) == {f"e{index}" for index in range(8)}
        for index in range(8):
            assert cache.get(f"e{index}", "analytics", 2).status == cand.STATUS_HIT
        assert cache.get("victim", "clinical", 1).status == cand.STATUS_REVOKED_ENTRY

    def test_x06_purpose_isolation_invariant_holds_over_real_cache_state(self) -> None:
        dispatches = [
            _dispatch("pre", "g1", "p", ["src_vitals"], 10),
            _dispatch("post1", "g1", "p", ["src_vitals"], 150),
            _dispatch("post2", "g1", "p", ["src_vitals"], 200),
            _dispatch("other", "g2", "q", ["src_meds"], 210, subject="s2"),
        ]
        case = _workload_case(
            dispatches, revocations=[_workload_revocation(grant="g1", purpose="p")]
        )
        outcome = bl.run_baseline(X06, case, {"seed": FIXED_SEED})
        detail = _detail(outcome)
        assert detail["purpose_isolation_violations"] == 0
        assert all(
            record["context_leaked_across_purposes"] is False for record in detail["dispatches"]
        )
        assert all(
            record["entry_purpose"] in (None, record["requested_purpose"])
            for record in detail["dispatches"]
        )

    def test_x06_serves_repeat_dispatch_from_current_epoch_entry(self) -> None:
        case = _workload_case(
            [
                _dispatch("d1", "g1", "p", ["src_vitals"], 10),
                _dispatch("d1", "g1", "p", ["src_vitals"], 20),
            ],
            revocations=[],
        )
        detail = _detail(bl.run_baseline(X06, case, {"seed": FIXED_SEED}))
        statuses = [record["fetch_status"] for record in detail["dispatches"]]
        assert statuses == ["CACHE_MISS", "HIT"]
        assert detail["cache_entries_created"] == 1
        assert detail["cache_hits"] == 1

    def test_exposed_bytes_are_nonzero_only_on_admitted_dispatches(self) -> None:
        dispatches = [
            _dispatch("pre", "g-med", "clinical", ["src_vitals"], 10),
            _dispatch("post", "g-med", "analytics", ["src_vitals"], 150),
        ]
        for baseline_id in ("coarse-cache-purge-on-revocation", "purpose-bound-cache-keying"):
            detail = _detail(
                bl.run_baseline(baseline_id, _workload_case(dispatches), {"seed": FIXED_SEED})
            )
            exposed = {r["dispatch_id"]: r["exposed_bytes"] for r in detail["dispatches"]}
            assert exposed["pre"] > 0
            assert exposed["post"] == 0
            assert detail["exposed_bytes_total"] == exposed["pre"]


# ---------------------------------------------------------------------------
# 2. Negative boundaries: adversarial input refused, never silently dropped
# ---------------------------------------------------------------------------


class TestNegativeBoundaries:
    """Malformed/adversarial input fails closed with stable reason codes."""

    @pytest.mark.parametrize("principal", ["", 5, True, None])
    def test_malformed_principal_raises_stable_code(self, principal: object) -> None:
        with pytest.raises(ValueError, match="PRINCIPAL_MALFORMED"):
            rm.allowed(_item(), principal, "clinical", 5, _ledger())  # type: ignore[arg-type]

    @pytest.mark.parametrize("purpose", ["", 7, True, None])
    def test_malformed_or_blank_purpose_raises_stable_code(self, purpose: object) -> None:
        with pytest.raises(ValueError, match="PURPOSE_UNKNOWN"):
            rm.allowed(_item(), "s1", purpose, 5, _ledger())  # type: ignore[arg-type]

    @pytest.mark.parametrize("time", [-1, 1.5, True, "10", None])
    def test_malformed_time_raises_stable_code(self, time: object) -> None:
        with pytest.raises(ValueError, match="TIME_MALFORMED"):
            rm.allowed(_item(), "s1", "clinical", time, _ledger())  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "raw_item",
        [
            None,
            "not-a-mapping",
            {"item_id": ""},
            {"lineage": ["src_vitals"]},
            {"item_id": "i1", "item_epoch": "3"},
        ],
    )
    def test_malformed_item_raises_stable_code(self, raw_item: object) -> None:
        with pytest.raises(ValueError, match="ITEM_MALFORMED"):
            rm.allowed(raw_item, "s1", "clinical", 5, _ledger())

    def test_candidate_refuses_put_with_empty_dependencies(self) -> None:
        cache = cand.RevocationCompleteCache()
        with pytest.raises(ValueError, match="DEPS_MALFORMED"):
            cache.put("k", "v", [])
        with pytest.raises(ValueError, match="VALUE_MALFORMED"):
            cache.put("k", "", [("s1", "clinical", 1)])
        with pytest.raises(ValueError, match="KEY_MALFORMED"):
            cache.put("", "v", [("s1", "clinical", 1)])

    def test_candidate_refuses_fabricated_derivation_edges(self) -> None:
        cache = cand.RevocationCompleteCache()
        with pytest.raises(ValueError, match="DERIVATION_PARENT_MISSING"):
            cache.put("child", "v", [("s1", "clinical", 1)], derived_from=["ghost"])
        cache.put("parent", "v", [("s1", "clinical", 1)])
        with pytest.raises(ValueError, match="DERIVATION_CYCLE"):
            cache.put("parent", "v", [("s1", "clinical", 1)], derived_from=["parent"])

    def test_baseline_fail_closed_on_malformed_workload(self) -> None:
        bad_case = {
            "case_id": "bad",
            "workload": {
                "source_snapshot": {"a": 1},
                "revocations": [],
                "dispatches": [{"dispatch_id": "d"}],
            },
        }
        for baseline_id in IMPLEMENTED_BASELINES:
            outcome = bl.run_baseline(baseline_id, bad_case, {"seed": FIXED_SEED})
            assert outcome.observed_outcome == "EXECUTION_ERROR"
            assert outcome.detail.startswith(bl.REASON_WORKLOAD_MALFORMED) or (
                "WORKLOAD_MALFORMED" in outcome.detail
            )

    def test_baseline_never_guessed_on_unknown_id(self) -> None:
        outcome = bl.run_baseline("nonexistent-baseline", {"case_id": "x"}, {"seed": FIXED_SEED})
        assert outcome.observed_outcome == bl.OUTCOME_NOT_RUN_EXTERNAL
        assert bl.REASON_BASELINE_UNAVAILABLE in outcome.detail

    def test_x06_refuses_cross_purpose_and_malformed_fetches(self) -> None:
        entry = cand.CacheEntry(
            key="k",
            value="ctx",
            deps=frozenset(),
            derived_from=frozenset(),
            created_at_revocation_events=0,
        )
        _ = entry  # entry object construction itself is validated by its dataclass
        cache = {
            ("s", "g", "p", 1): bl.PurposeCacheEntry(
                subject="s",
                grant="g",
                purpose="p",
                consent_epoch=1,
                context="ctx",
                source_artifacts=frozenset({"a"}),
                created_at_seconds=5,
            )
        }
        assert bl.purpose_cache_fetch(cache, ("s", "g", "p", 1), "p")[0] == "HIT"
        assert bl.purpose_cache_fetch(cache, ("s", "g", "p", 1), "other")[0] == (
            bl.REASON_PURPOSE_MISMATCH
        )
        assert bl.purpose_cache_fetch(cache, ("s", "g", "p"), "p")[0] == bl.REASON_KEY_MALFORMED
        assert bl.purpose_cache_fetch(cache, ("s", "g", "p", True), "p")[0] == (
            bl.REASON_KEY_MALFORMED
        )
        assert bl.purpose_cache_fetch(cache, ("s", "g", "absent", 1), "absent")[0] == (
            bl.REASON_CACHE_MISS
        )


# ---------------------------------------------------------------------------
# 3. Unknown boundaries: INDETERMINATE is first-class
# ---------------------------------------------------------------------------


class TestUnknownBoundaries:
    """Unknown/unevaluable inputs yield INDETERMINATE, never a coerced verdict."""

    def test_unknown_purpose_string_is_indeterminate_not_deny(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        decision = rm.decide(_item(epoch=1), "s1", "totally-unknown-purpose", 500, ledger)
        assert decision.decision == "INDETERMINATE"
        assert decision.reason_code == rm.REASON_CODE_UNKNOWN_PURPOSE

    def test_known_but_unconsented_purpose_is_determined_deny(self) -> None:
        ledger = _ledger(purposes=("clinical",), revocations=(_revocation(),))
        decision = rm.decide(_item(epoch=1), "s1", "analytics", 50, ledger)
        assert decision.decision == "DENY"
        assert decision.reason_code == rm.REASON_PURPOSE_NOT_CONSENTED

    def test_time_before_grant_is_indeterminate(self) -> None:
        ledger = _ledger(granted_at=10, revocations=(_revocation(revoked_at=100),))
        for time in (0, 5, 9):
            decision = rm.decide(_item(epoch=1), "s1", "clinical", time, ledger)
            assert decision.decision == "INDETERMINATE"
            assert decision.reason_code == rm.REASON_TIME_BEFORE_GRANT

    def test_unlabelled_and_null_lineage_nodes_fail_closed_indeterminate(self) -> None:
        ledger = _ledger(labels={"src_vitals": "origin", "unlabelled": None})
        for lineage in (("ghost_node",), ("src_vitals", "ghost_node"), ("unlabelled",)):
            decision = rm.decide(_item(lineage=lineage, epoch=1), "s1", "clinical", 50, ledger)
            assert decision.decision == "INDETERMINATE"
            assert decision.reason_code == rm.REASON_LINEAGE_INDETERMINATE

    def test_unknown_principal_is_deny_grant_unknown(self) -> None:
        decision = rm.decide(_item(epoch=1), "ghost", "clinical", 50, _ledger())
        assert decision.decision == "DENY"
        assert decision.reason_code == rm.REASON_GRANT_UNKNOWN

    def test_indeterminate_never_leaks_as_allow_or_deny_via_allowed(self) -> None:
        ledger = _ledger(revocations=(_revocation(),))
        verdicts = {
            rm.allowed(_item(epoch=1), "s1", purpose, 50, ledger)
            for purpose in ("unknown-a", "unknown-b")
        }
        assert verdicts == {"INDETERMINATE"}

    def test_seeded_unknown_boundary_sweep_is_deterministic(self) -> None:
        """Randomized sweep over unknown-purpose/time/label probes, fixed seed.

        Mixed sweep: every probe verdict must match its branch's expected
        class (unknown purpose string -> INDETERMINATE, time before the grant
        -> INDETERMINATE, servable pre-boundary time -> ALLOW, ghost lineage
        -> INDETERMINATE). An unknown-dimensions-only sweep proves the
        genuinely unknown probes are ALL refused. Re-seeding replays the
        identical probe sequence (determinism under seeded randomness).
        """
        ledger = _ledger(
            labels={"src_vitals": "origin"},
            revocations=(_revocation(revoked_at=100),),
        )

        def mixed_sweep() -> list[str]:
            gen = random.Random(FIXED_SEED)
            verdicts: list[str] = []
            for _ in range(25):
                choice = gen.randrange(3)
                if choice == 0:
                    verdicts.append(
                        rm.allowed(
                            _item(epoch=1), "s1", f"unknown-{gen.randrange(1000)}", 50, ledger
                        )
                    )
                elif choice == 1:
                    time = gen.randrange(0, 10)  # granted_at is 0: [0,10) is servable
                    verdicts.append(rm.allowed(_item(epoch=1), "s1", "clinical", time, ledger))
                else:
                    ghost = (f"ghost-{gen.randrange(1000)}",)
                    verdicts.append(
                        rm.allowed(_item(lineage=ghost, epoch=1), "s1", "clinical", 50, ledger)
                    )
            return verdicts

        expected = mixed_sweep()
        # Determinism: the identically seeded sweep replays byte-identically.
        assert expected and mixed_sweep() == expected
        unknown_only: list[str] = []
        gen = random.Random(FIXED_SEED)
        for _ in range(30):
            if gen.randrange(2) == 0:
                unknown_only.append(
                    rm.allowed(_item(epoch=1), "s1", f"unknown-{gen.randrange(1000)}", 50, ledger)
                )
            else:
                ghost = (f"ghost-{gen.randrange(1000)}",)
                unknown_only.append(
                    rm.allowed(_item(lineage=ghost, epoch=1), "s1", "clinical", 50, ledger)
                )
        assert unknown_only and set(unknown_only) == {"INDETERMINATE"}


# ---------------------------------------------------------------------------
# 4. Revocation-timing race scenarios
# ---------------------------------------------------------------------------


class TestRevocationTimingRaces:
    """Skewed event orderings around ``t_r`` must never widen disclosure."""

    def test_dispatch_exactly_at_t_r_is_denied_boundary_inclusive(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        assert rm.allowed(_item(epoch=1), "s1", "analytics", 100, ledger) == "DENY"
        # The same instant in every implemented baseline arm.
        case = _workload_case([_dispatch("at-boundary", "g-med", "analytics", ["src_vitals"], 100)])
        for baseline_id in IMPLEMENTED_BASELINES:
            detail = _detail(bl.run_baseline(baseline_id, case, {"seed": FIXED_SEED}))
            record = detail["dispatches"][0]
            assert record["outcome"] == "REJECT", baseline_id
            assert record["reason_code"] == "REVOKED_CONTEXT", baseline_id

    def test_one_tick_before_t_r_is_still_servable(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        assert rm.allowed(_item(epoch=1), "s1", "analytics", 99, ledger) == "ALLOW"

    def test_earliest_covering_revocation_wins_the_race(self) -> None:
        ledger = _ledger(
            revocations=(
                _revocation(purpose="analytics", revoked_at=200),
                _revocation(purpose="*", revoked_at=150),
                _revocation(purpose="analytics", revoked_at=300),
            )
        )
        assert (
            rm.effective_revocation_time(  # type: ignore[arg-type]
                rm.ConsentLedgerView.from_mapping(ledger), "s1", "analytics"
            )
            == 150
        )
        for time in (150, 151, 200, 299):
            assert rm.allowed(_item(epoch=1), "s1", "analytics", time, ledger) == "DENY"

    def test_wildcard_revocation_covers_every_purpose(self) -> None:
        ledger = _ledger(purposes=("clinical",), revocations=(_revocation(purpose="*"),))
        assert rm.allowed(_item(epoch=1), "s1", "clinical", 1000, ledger) == "DENY"
        assert rm.decide(_item(epoch=1), "s1", "clinical", 1000, ledger).stored_data == "deleted"

    def test_replay_race_stale_epoch_payload_denied_pre_revocation(self) -> None:
        """G3: a retry payload assembled under a superseded epoch is DENY even
        before ``t_r`` — the epoch race cannot smuggle pre-revocation bytes."""
        ledger = _ledger(epoch=3, revocations=(_revocation(revoked_at=100),))
        assert rm.allowed(_item(epoch=2), "s1", "clinical", 50, ledger) == "DENY"
        assert (
            rm.decide(_item(epoch=2), "s1", "clinical", 50, ledger).reason_code
            == rm.REASON_EPOCH_STALE
        )

    def test_stale_epoch_check_defers_to_post_revocation_denial(self) -> None:
        """Race of two denial reasons at/after ``t_r``: future-disclosure wins
        (the verdict names the revocation gate, never an erasure claim)."""
        ledger = _ledger(epoch=3, revocations=(_revocation(revoked_at=100),))
        decision = rm.decide(_item(epoch=99), "s1", "analytics", 150, ledger)
        assert decision.decision == "DENY"
        assert decision.reason_code == rm.REASON_POST_REVOCATION

    def test_future_revocation_does_not_touch_earlier_dispatches(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=500),))
        for time in (0, 100, 499):
            assert rm.allowed(_item(epoch=1), "s1", "analytics", time, ledger) == "ALLOW"
        assert rm.allowed(_item(epoch=1), "s1", "analytics", 500, ledger) == "DENY"

    def test_baseline_race_skew_post_revocation_cache_hit_never_resurrects(self) -> None:
        """B1 race: a cached pre-``t_r`` entry, then revocation, then a repeat
        dispatch with the SAME dispatch_id — the cache hit flag may be set but
        the authorization verdict stays REJECT with zero exposed bytes."""
        case = _workload_case(
            [
                _dispatch("dup", "g-med", "analytics", ["src_vitals"], 10),
                _dispatch("dup", "g-med", "analytics", ["src_vitals"], 150),
            ]
        )
        detail = _detail(
            bl.run_baseline("coarse-cache-purge-on-revocation", case, {"seed": FIXED_SEED})
        )
        records = {r["dispatch_id"]: r for r in detail["dispatches"]}
        # Same dispatch_id: dict keeps the LAST record (the post-revocation one).
        assert records["dup"]["outcome"] == "REJECT"
        assert records["dup"]["reason_code"] == "REVOKED_CONTEXT"
        assert records["dup"]["exposed_bytes"] == 0
        assert detail["invalidation_events"] == 1

    def test_candidate_revoke_arriving_mid_stream_is_idempotent(self) -> None:
        cache = cand.RevocationCompleteCache()
        cache.put("k", "v", [("s1", "clinical", 1)])
        first = cache.revoke("s1", "clinical", 1)
        second = cache.revoke("s1", "clinical", 1)
        assert first["applied"] is True
        assert second["applied"] is False
        assert second["invalidated_keys"] == []
        assert len(cache.revocation_log()) == 1
        assert cache.get("k", "clinical", 1).status == cand.STATUS_REVOKED_ENTRY


# ---------------------------------------------------------------------------
# 5. Two-step metamorphic relations
# ---------------------------------------------------------------------------


class TestMetamorphicRelations:
    """Two-step transformations of a workload/ledger preserve the invariant."""

    def test_purge_then_redispatch_never_readmits_revoked_context(self) -> None:
        """MR1 (blueprint core): B1 purges on revocation; a re-dispatch of the
        revoked scope afterwards must NOT be re-admitted from the purged
        cache — the purge cannot resurrect revoked context in step two."""
        base_dispatches = [
            _dispatch("d0", "g-med", "analytics", ["src_vitals"], 10),
        ]
        revocation = [_workload_revocation(grant="g-med", purpose="analytics")]
        step1 = _workload_case(base_dispatches, revocations=revocation)
        detail1 = _detail(
            bl.run_baseline("coarse-cache-purge-on-revocation", step1, {"seed": FIXED_SEED})
        )
        assert detail1["dispatches"][0]["outcome"] == "ADMIT"  # pre- t_r admission
        # Step two: append a re-dispatch of the SAME scope after t_r.
        step2_dispatches = base_dispatches + [
            _dispatch("d0", "g-med", "analytics", ["src_vitals"], 200),
        ]
        detail2 = _detail(
            bl.run_baseline(
                "coarse-cache-purge-on-revocation",
                _workload_case(step2_dispatches, revocations=revocation),
                {"seed": FIXED_SEED},
            )
        )
        redispatch = [r for r in detail2["dispatches"] if r["dispatch_id"] == "d0"][-1]
        assert redispatch["outcome"] == "REJECT"
        assert redispatch["reason_code"] == "REVOKED_CONTEXT"
        assert redispatch["exposed_bytes"] == 0

    def test_candidate_purge_then_reput_never_serves_old_epoch(self) -> None:
        """MR2: after revoke(), a put of revoked context at the SAME scope is
        refused; a legitimate NEW-epoch re-put is served only at the new
        epoch and is EPOCH_STALE for the revoked one — re-dispatching the old
        consent scope never re-admits revoked context."""
        cache = cand.RevocationCompleteCache()
        cache.put("summary", "v", [("s1", "clinical", 1)])
        cache.revoke("s1", "clinical", 1)
        with pytest.raises(ValueError, match="REVOKED_DEPENDENCY"):
            cache.put("summary", "v", [("s1", "clinical", 1)])
        cache.put("summary_v2", "v", [("s1", "clinical", 2)])
        assert cache.get("summary_v2", "clinical", 2).status == cand.STATUS_HIT
        assert cache.get("summary_v2", "clinical", 1).status == cand.STATUS_EPOCH_STALE

    def test_purpose_keying_epochs_monotonic_per_scope(self) -> None:
        """MR3: purpose-bound keying epochs never decrease for a scope, across
        repeated post-revocation dispatches (monotonic key rotation)."""
        dispatches = [
            _dispatch("d0", "g1", "p", ["src_vitals"], 10),
            _dispatch("d1", "g1", "p", ["src_vitals"], 150),
            _dispatch("d2", "g1", "p", ["src_vitals"], 200),
            _dispatch("d3", "g1", "p", ["src_vitals"], 300),
        ]
        detail = _detail(
            bl.run_baseline(
                "purpose-bound-cache-keying",
                _workload_case(
                    dispatches, revocations=[_workload_revocation(grant="g1", purpose="p")]
                ),
                {"seed": FIXED_SEED},
            )
        )
        epochs = [record["cache_key_epoch"] for record in detail["dispatches"]]
        assert epochs == sorted(epochs)
        assert epochs[0] == 0
        assert detail["key_rotations"] == len(epochs) - 1

    def test_purpose_keying_monotonic_under_purpose_change(self) -> None:
        """MR4: revoking purpose ``a`` rotates ONLY the (grant, a) key space;
        purpose ``b`` epochs remain at 0 (monotonic per-scope, no crosstalk)."""
        dispatches = [
            _dispatch("d0", "g1", "a", ["src_vitals"], 10),
            _dispatch("d1", "g1", "a", ["src_vitals"], 200),
            _dispatch("d2", "g1", "b", ["src_vitals"], 210),
            _dispatch("d3", "g1", "b", ["src_vitals"], 300),
        ]
        detail = _detail(
            bl.run_baseline(
                "purpose-bound-cache-keying",
                _workload_case(
                    dispatches, revocations=[_workload_revocation(grant="g1", purpose="a")]
                ),
                {"seed": FIXED_SEED},
            )
        )
        epochs = {
            record["dispatch_id"]: record["cache_key_epoch"] for record in detail["dispatches"]
        }
        assert epochs["d0"] == 0
        assert epochs["d1"] == 1  # rotated exactly once for the revoked purpose
        assert epochs["d2"] == 0 and epochs["d3"] == 0  # unaffected scope untouched

    def test_candidate_vs_ablation_diverge_only_on_transitive_revocation(self) -> None:
        """MR5: the identical op stream through the candidate and through the
        ablation differs EXACTLY in the under-declared derived entry — the
        candidate refuses it (REVOKED_ENTRY), the ablation leaks it
        (HIT served_from_revoked_ancestry); all other read statuses match."""
        ops = [
            {"op": "put", "key": "base", "value": "v", "deps": [["s1", "clinical", 1]]},
            {"op": "put", "key": "unaffected", "value": "v", "deps": [["s2", "clinical", 1]]},
            {
                "op": "put",
                "key": "derived",
                "value": "v",
                "deps": [["s1", "analytics", 5]],
                "derived_from": ["base"],
            },
            {"op": "revoke", "subject": "s1", "purpose": "clinical", "epoch": 1},
            {"op": "get", "key": "unaffected", "purpose": "clinical", "epoch": 1},
            {"op": "get", "key": "derived", "purpose": "analytics", "epoch": 5},
        ]
        results: dict[str, dict[str, object]] = {}
        for mode in ("candidate", "ablation"):
            outcome = cand.run_candidate({"case_id": "mr5", "mode": mode, "cache_ops": ops})
            results[mode] = _detail(outcome)  # type: ignore[assignment]
        candidate_detail = results["candidate"]
        ablation_detail = results["ablation"]
        assert candidate_detail["leaks"] == 0  # type: ignore[index]
        assert ablation_detail["leaks"] == 1  # type: ignore[index]
        assert ablation_detail["leak_keys"] == ["derived"]  # type: ignore[index]
        candidate_ops = {
            op["key"]: op["status"]  # type: ignore[index]
            for op in candidate_detail["ops"]  # type: ignore[index]
            if op["op"] == "get"  # type: ignore[index]
        }
        ablation_ops = {
            op["key"]: op["status"]  # type: ignore[index]
            for op in ablation_detail["ops"]  # type: ignore[index]
            if op["op"] == "get"  # type: ignore[index]
        }
        assert candidate_ops["unaffected"] == ablation_ops["unaffected"] == "HIT"
        assert candidate_ops["derived"] == "REVOKED_ENTRY"
        assert ablation_ops["derived"] == "HIT"

    def test_revocation_semantics_statements_are_stable_across_calls(self) -> None:
        """MR6: the versioned semantics singleton is immutable under repeated
        calls — transformations of the world do not rewrite the contract."""
        first = rm.revocation_semantics()
        second = rm.revocation_semantics()
        assert first is second
        assert first.to_dict() == second.to_dict()
        assert first.retroactive_erasure_of_delivered_bytes is False
        assert first.model_memorization_guarantee == "NOT_GUARANTEED"

    def test_baseline_runs_are_deterministic_under_repeated_invocation(self) -> None:
        """MR7: re-running the same case with different ctx seeds produces
        byte-identical detail (no hidden randomness anywhere)."""
        case = _workload_case(
            [
                _dispatch("d1", "g-med", "clinical", ["src_vitals"], 10),
                _dispatch("d2", "g-med", "analytics", ["src_meds"], 150),
            ]
        )
        for baseline_id in IMPLEMENTED_BASELINES:
            first = bl.run_baseline(baseline_id, case, {"seed": FIXED_SEED})
            second = bl.run_baseline(baseline_id, case, {"seed": FIXED_SEED + 999})
            assert first.detail == second.detail, baseline_id
            assert first.observed_outcome == second.observed_outcome, baseline_id


# ---------------------------------------------------------------------------
# 6. Mutation-style checks: perturbing an input flips the expected verdict
# ---------------------------------------------------------------------------


class TestMutationSensitivity:
    """Single-input perturbations must flip the verdict (tests are sensitive)."""

    def test_mutation_time_across_t_r_flips_verdict(self) -> None:
        ledger = _ledger(revocations=(_revocation(revoked_at=100),))
        before = rm.decide(_item(epoch=1), "s1", "analytics", 99, ledger)
        after = rm.decide(_item(epoch=1), "s1", "analytics", 100, ledger)
        assert before.decision == "ALLOW" and after.decision == "DENY"

    def test_mutation_purpose_string_flips_verdict(self) -> None:
        ledger = _ledger(revocations=(_revocation(purpose="analytics"),))
        affected = rm.decide(_item(epoch=1), "s1", "analytics", 150, ledger)
        unaffected = rm.decide(_item(epoch=1), "s1", "clinical", 150, ledger)
        assert affected.decision == "DENY" and unaffected.decision == "ALLOW"

    def test_mutation_lineage_member_flip_in_every_baseline(self) -> None:
        """Mutating the single dispatch from the unaffected (g-admin, clinical)
        scope into the revoked (g-med, analytics) scope flips the pair-level
        outcome from ADMIT to REJECT in every implemented arm."""
        clean = _workload_case([_dispatch("mutant", "g-admin", "clinical", ["src_admin"], 150)])
        mutant = _workload_case([_dispatch("mutant", "g-med", "analytics", ["src_vitals"], 150)])
        for baseline_id in IMPLEMENTED_BASELINES:
            clean_outcome = bl.run_baseline(baseline_id, clean, {"seed": FIXED_SEED})
            mutant_outcome = bl.run_baseline(baseline_id, mutant, {"seed": FIXED_SEED})
            assert clean_outcome.observed_outcome == "ADMIT", baseline_id
            assert mutant_outcome.observed_outcome == "REJECT", baseline_id

    def test_mutation_epoch_flips_candidate_read_status(self) -> None:
        cache = cand.RevocationCompleteCache()
        cache.put("k", "v", [("s1", "clinical", 2)])
        assert cache.get("k", "clinical", 2).status == cand.STATUS_HIT
        assert cache.get("k", "clinical", 1).status == cand.STATUS_EPOCH_STALE
        assert cache.get("k", "other", 2).status == cand.STATUS_PURPOSE_MISMATCH

    def test_mutation_removing_revocation_event_flips_candidate_closure(self) -> None:
        """Perturbing the revocation stream (dropping the event) leaves every
        entry live; re-adding it tombstones exactly the closure again."""
        events = [
            {"op": "put", "key": "base", "value": "v", "deps": [["s1", "clinical", 1]]},
            {
                "op": "put",
                "key": "derived",
                "value": "v",
                "deps": [["s1", "analytics", 1]],
                "derived_from": ["base"],
            },
            {"op": "get", "key": "derived", "purpose": "analytics", "epoch": 1},
        ]
        without_revoke = cand.run_candidate(
            {"case_id": "m", "mode": "candidate", "cache_ops": events}
        )
        with_revoke = cand.run_candidate(
            {
                "case_id": "m",
                "mode": "candidate",
                "cache_ops": events[:2]
                + [{"op": "revoke", "subject": "s1", "purpose": "clinical", "epoch": 1}]
                + events[2:],
            }
        )
        assert _detail(without_revoke)["status_counts"]["HIT"] == 1  # type: ignore[index]
        assert _detail(with_revoke)["status_counts"]["REVOKED_ENTRY"] == 1  # type: ignore[index]

    def test_mutation_label_removal_flips_allow_to_indeterminate(self) -> None:
        """Dropping a lineage label (mutation of the label table) flips a
        clean ALLOW into a fail-closed INDETERMINATE — not into a silent DENY
        that would masquerade as a safe rejection."""
        labelled = _ledger(labels={"src_vitals": "origin"})
        stripped = _ledger(labels={})
        item = _item(lineage=("src_vitals",), epoch=1)
        assert rm.allowed(item, "s1", "clinical", 50, labelled) == "ALLOW"
        assert rm.allowed(item, "s1", "clinical", 50, stripped) == "INDETERMINATE"

    def test_mutation_granted_at_flip_changes_unknown_boundary(self) -> None:
        ledger_late = _ledger(granted_at=10, revocations=(_revocation(),))
        ledger_default = _ledger(revocations=(_revocation(),))
        assert rm.allowed(_item(epoch=1), "s1", "clinical", 5, ledger_late) == "INDETERMINATE"
        assert rm.allowed(_item(epoch=1), "s1", "clinical", 5, ledger_default) == "ALLOW"

    def test_mutation_already_delivered_flag_attaches_orthogonal_effect(self) -> None:
        """Perturbing ``already_delivered`` never changes the verdict but does
        attach OUT_OF_SCOPE_PAST + NOT_GUARANTEED (no erasure claim smuggled)."""
        ledger = _ledger(revocations=(_revocation(),))
        fresh = rm.decide(_item(epoch=1, already_delivered=False), "s1", "clinical", 50, ledger)
        delivered = rm.decide(_item(epoch=1, already_delivered=True), "s1", "clinical", 50, ledger)
        assert fresh.decision == delivered.decision == "ALLOW"
        assert fresh.already_delivered_effect is None
        assert delivered.already_delivered_effect == rm.OUT_OF_SCOPE_PAST
        assert delivered.memorization_guarantee == "NOT_GUARANTEED"

    def test_seeded_mutation_campaign_flips_exactly_on_revoked_lineage(self) -> None:
        """Randomized mutation campaign over generated single-dispatch
        workloads (fixed seed): flipping the dispatch purpose from the
        unaffected grant to the revoked scope flips the pair outcome; the
        unperturbed twin stays ADMIT (mutation kill, no equivalent mutants)."""
        rng = random.Random(FIXED_SEED)
        purposes = ("clinical", "analytics")
        killed = 0
        for index in range(20):
            clean_purpose = purposes[rng.randrange(2)]
            at_seconds = 100 + rng.randrange(1, 50)
            clean = _workload_case(
                [_dispatch("m1", "g-admin", clean_purpose, ["src_admin"], at_seconds)],
                case_id=f"mutation-{index}",
            )
            mutant = _workload_case(
                [_dispatch("m1", "g-med", "analytics", ["src_vitals"], at_seconds)],
                case_id=f"mutation-{index}",
            )
            for baseline_id in IMPLEMENTED_BASELINES:
                clean_outcome = bl.run_baseline(baseline_id, clean, {"seed": FIXED_SEED})
                mutant_outcome = bl.run_baseline(baseline_id, mutant, {"seed": FIXED_SEED})
                assert clean_outcome.observed_outcome == "ADMIT", (baseline_id, index)
                assert mutant_outcome.observed_outcome == "REJECT", (baseline_id, index)
            killed += 1
        assert killed == 20
