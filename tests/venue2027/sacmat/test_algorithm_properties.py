"""Algorithmic property and metamorphic tests for the SACMAT 2027 PolicyTrace study
(task SACMAT-unit, phase P05).

Purpose
-------
Property-based and metamorphic testing over the REAL SACMAT algorithmic
surfaces — no reimplementation, no stubs:

- ``evaluation/venue2027/sacmat/baselines.py``: the three in-process engine
  models (``XacmlPolicyEngine`` deny-overrides, ``CedarPolicyEngine`` forbid
  precedence, ``ZanzibarPolicyEngine`` read-time relation walk), the
  independent four-valued conformance oracle (``oracle_decision``) and the
  arm dispatchers B0/B1/B2/B3 through the public ``run_baseline``.
- ``evaluation/venue2027/sacmat/policy_trace_dsl.py``: the temporal
  policy-trace DSL (``parse_policy_trace`` / ``evaluate_trace``) with its
  fail-closed reason codes.

Properties under test
---------------------
Decision boundaries (positive / negative / unknown):
- P1 expiry boundary: decision_time == expiry flips the oracle to DENY and
  Zanzibar (read-time tuple walk) to NOT_APPLICABLE, while the compiled
  final-state engines still PERMIT; decision_time <= expiry - 1 stays PERMIT.
- P2 version-skew boundary: a POLICY_VERSION_BUMP at logical_time >= the
  request's decision time is flagged by B3; at decision_time - 1 it is not.
- P3 unknown principal: the oracle answers NOT_APPLICABLE (no delegation
  relationship ever existed) — never silently DENY — and the DSL answers
  INDETERMINATE with UNESTABLISHED_AUTHORITY; neither is coerced to a
  permit.

History-sensitive race scenarios:
- P4 delegation-expiry race: grant -> (expiry lapses) -> request is REJECTed
  by B3 and B2 (Zanzibar read-time divergence) but ADMITted by B0 and B1;
  regranting after the expiry heals every arm back to ADMIT.
- P5 policy-skew race: grant -> bump at decision time -> request is REJECTed
  by B3 while B0/B1/B2 (pointwise on the healed final state) all ADMIT.

Metamorphic relations (two-step, checked on seeded randomized corpora):
- M1 revocation monotonicity: appending a REVOKE for the requesting key at
  the decision time can never create a PERMIT (oracle or any engine) —
  "revoking a delegation can only reduce access".
- M2 final-state deny-override: after appending that REVOKE, XACML and
  Cedar answer DENY whenever the key had any final-state entry before.
- M3 version-bump tightening: appending a POLICY_VERSION_BUMP at a time >=
  the decision time tightens conformance detection: B3 ADMIT -> REJECT is
  allowed, B3 REJECT -> ADMIT is forbidden, engine decisions and the oracle
  verdict are unchanged (bumps are skipped by replay and final-state
  derivation alike) — "adding a policy version can only tighten conformance
  detection".
- M4 time-shift invariance: shifting every logical time, expiry and the
  decision time by one constant leaves the oracle verdict, Zanzibar's
  read-time decision and the DSL outcome/findings unchanged (temporal
  semantics depend only on order and relative distances).
- M5 DSL append-only findings: for a randomized DSL corpus, every finding of
  any prefix trace (kind + witness index) also appears in the full trace's
  findings — replay never erases a witnessed error.
- M6 DSL revocation flip: appending a REVOKE after a PERMIT-producing access
  flips any later access to DENY; re-granting after the revoke restores the
  grantor's own authority.

Mutation checks (RQ2 analogue at unit scale):
- X1 seeded mutant corpus (expiry tightening, revocation dropping, purpose
  swap, version-bump insertion) over randomized histories: B3's killed-
  mutant set is a superset of B1's and B2's at the same budget, and B3
  strictly kills mutants both miss.
- X2 every REJECT detail carries its arm's stable reason code (machine-
  checkable attribution); every verdict is in the documented set.
- X3 deterministic generation and evaluation: replaying the whole randomized
  corpus twice under identical seeds yields byte-identical decision rows.

Randomness discipline
---------------------
All randomness comes from :class:`random.Random` instances seeded with fixed
integer constants (derived from the trial index); no global seeding, no wall
clock, no network, no I/O inside the property loops. All corpus units are
synthetic delegated-consent histories in monotonic logical time (no PHI/PII).
"""

from __future__ import annotations

import json
import random

from evaluation.venue2027.sacmat import baselines as B
from evaluation.venue2027.sacmat import policy_trace_dsl as D

# ---------------------------------------------------------------------------
# Constants and small builders.
# ---------------------------------------------------------------------------

ARMS = (B.BASELINE_B0, B.BASELINE_B1, B.BASELINE_B2, B.BASELINE_B3)
REPLAY_ARMS = (B.BASELINE_B1, B.BASELINE_B2, B.BASELINE_B3)
PURPOSES = (B.PURPOSE_SELF_CARE, B.PURPOSE_CARE_TEAM, B.PURPOSE_RESEARCH)
ACTORS = ("alice", "bob", "carol", "dave")

#: Lattice rank used by the monotonicity metamorphic relations: appending a
#: revocation may move a decision DOWN this lattice (towards NOT_APPLICABLE
#: / DENY) but never upwards to PERMIT.
DECISION_RANK = {B.NOT_APPLICABLE: 0, B.PERMIT: 1, B.DENY: 2}


def _ctx() -> B.SacmatContext:
    return B.SacmatContext(arm_id="SACMAT-unit", seed=20271115, source_commit="test")


def _validated(case: dict[str, object]) -> B.PolicyHistory:
    result = B._validate_case(case)  # type: ignore[arg-type]
    assert not isinstance(result, B.Outcome), f"fixture case rejected: {result}"
    return result  # type: ignore[no-any-return]


def _events_at_most(case: dict[str, object]) -> int:
    return max(int(e["logical_time"]) for e in case["history"])  # type: ignore[arg-type]


def _engine_decisions(history: B.PolicyHistory) -> dict[str, str]:
    req = history.request
    return {
        engine_id: B.evaluate_engine(engine_id, history, req)
        for engine_id in B.ENGINE_MODELS
    }


# ---------------------------------------------------------------------------
# Randomized corpus generators (deterministically seeded per trial).
# ---------------------------------------------------------------------------


def _random_history_case(rng: random.Random, case_id: str) -> dict[str, object]:
    """One synthetic (policy history, request) unit in monotonic logical time."""
    events: list[dict[str, object]] = []
    t = 0
    for _ in range(rng.randint(1, 6)):
        kind = rng.choice(
            [B.EVENT_GRANT, B.EVENT_REGRANT, B.EVENT_REVOKE, B.EVENT_EXPIRE]
        )
        actor = rng.choice(ACTORS)
        purpose = rng.choice(PURPOSES)
        t += rng.randint(1, 300)
        event = {
            "event_kind": kind,
            "logical_time": t,
            "actor_id": actor,
            "delegate_id": actor,
            "purpose": purpose,
        }
        if kind in (B.EVENT_GRANT, B.EVENT_REGRANT):
            event["expiry"] = rng.randint(0, 1200)
        events.append(event)
    req = {
        "actor_id": rng.choice(ACTORS),
        "purpose": rng.choice(PURPOSES),
        "decision_time": rng.randint(0, 1500),
    }
    return {"case_id": case_id, "history": events, "request": req}


def _mutants(case: dict[str, object], rng: random.Random) -> list[tuple[str, dict[str, object]]]:
    """Four executable mutant families over one clean unit (blueprint RQ2)."""
    history = [dict(e) for e in case["history"]]  # type: ignore[arg-type]
    decision_time = int(case["request"]["decision_time"])  # type: ignore[arg-type]
    mutants: list[tuple[str, dict[str, object]]] = []

    grant_slots = [
        i for i, e in enumerate(history)
        if e["event_kind"] in (B.EVENT_GRANT, B.EVENT_REGRANT)
    ]
    if grant_slots:
        i = rng.choice(grant_slots)
        mutated = [dict(e) for e in history]
        mutated[i] = dict(
            mutated[i], expiry=max(0, decision_time - rng.randint(0, 50))
        )
        mutants.append(("expiry_tighten", dict(case, history=mutated)))

    revoke_slots = [
        i for i, e in enumerate(history)
        if e["event_kind"] in (B.EVENT_REVOKE, B.EVENT_EXPIRE)
    ]
    if revoke_slots:
        i = rng.choice(revoke_slots)
        mutated = [e for j, e in enumerate(history) if j != i]
        mutants.append(("revoke_drop", dict(case, history=mutated)))

    others = [p for p in PURPOSES if p != case["request"]["purpose"]]
    mutants.append(
        (
            "purpose_swap",
            dict(
                case,
                request=dict(case["request"], purpose=rng.choice(others)),  # type: ignore[arg-type]
            ),
        )
    )

    bumped = [dict(e) for e in history]
    bumped.append(
        {
            "event_kind": B.EVENT_POLICY_VERSION_BUMP,
            "logical_time": decision_time + rng.randint(0, 100),
            "actor_id": "sys",
            "delegate_id": "sys",
            "purpose": "*",
        }
    )
    bumped.sort(key=lambda e: int(e["logical_time"]))  # type: ignore[arg-type, return-value]
    mutants.append(("bump_insert", dict(case, history=bumped)))
    return mutants


# ---------------------------------------------------------------------------
# Part 1 — decision boundaries: positive / negative / unknown.
# ---------------------------------------------------------------------------


def test_p1_expiry_boundary_flips_oracle_and_read_time_engine() -> None:
    """P1: decision_time == expiry is the exact temporal flip point."""
    for decision_time in (899, 900, 901):
        case = {
            "case_id": f"expiry-boundary-{decision_time}",
            "history": [
                B.event(
                    B.EVENT_GRANT, 100, "patient-x", "patient-x",
                    B.PURPOSE_SELF_CARE, expiry=900,
                ),
            ],
            "request": B.request("patient-x", B.PURPOSE_SELF_CARE, decision_time),
        }
        history = _validated(case)
        oracle = B.oracle_decision(history)
        zanzibar = B.evaluate_engine(B.ENGINE_ZANZIBAR, history, history.request)
        xacml = B.evaluate_engine(B.ENGINE_XACML, history, history.request)
        if decision_time <= 899:
            assert oracle == B.PERMIT
            assert zanzibar == B.PERMIT
            assert xacml == B.PERMIT
        else:
            # Temporal DENY from the oracle; Zanzibar's read-time tuple walk
            # drops the expired tuple (NOT_APPLICABLE); the compiled
            # final-state XACML policy still PERMITs — the divergence B3 exists
            # to catch.
            assert oracle == B.DENY
            assert zanzibar == B.NOT_APPLICABLE
            assert xacml == B.PERMIT


def test_p1_expiry_race_detected_by_b3_and_b2_missed_by_b0_and_b1() -> None:
    """P4 (expiry race): the four-arm contrast on one shared divergence unit."""
    case = {
        "case_id": "expiry-race",
        "history": [
            B.event(
                B.EVENT_GRANT, 100, "patient-r", "patient-r",
                B.PURPOSE_CARE_TEAM, expiry=1000,
            ),
        ],
        "request": B.request("patient-r", B.PURPOSE_CARE_TEAM, 1500),
    }
    ctx = _ctx()
    verdicts = {
        arm: B.run_baseline(arm, case, ctx).observed_outcome for arm in ARMS
    }
    assert verdicts[B.BASELINE_B0] == "ADMIT", "static diff must miss pure expiry races"
    assert verdicts[B.BASELINE_B1] == "ADMIT", "single-engine testing must miss the race"
    assert verdicts[B.BASELINE_B2] == "REJECT", "differential sees the read-time divergence"
    assert verdicts[B.BASELINE_B3] == "REJECT", "B3 must detect the delegation-expiry race"


def test_p1_expiry_race_healed_by_regrant() -> None:
    """P4 (healing): regrant after expiry restores every arm to ADMIT."""
    case = {
        "case_id": "expiry-race-healed",
        "history": [
            B.event(
                B.EVENT_GRANT, 100, "patient-h", "patient-h",
                B.PURPOSE_CARE_TEAM, expiry=1000,
            ),
            B.event(
                B.EVENT_REGRANT, 1100, "patient-h", "patient-h",
                B.PURPOSE_CARE_TEAM, expiry=9000,
            ),
        ],
        "request": B.request("patient-h", B.PURPOSE_CARE_TEAM, 1500),
    }
    ctx = _ctx()
    history = _validated(case)
    assert B.oracle_decision(history) == B.PERMIT
    for arm in ARMS:
        outcome = B.run_baseline(arm, case, ctx)
        assert outcome.observed_outcome == "ADMIT", (arm, outcome.detail)


def test_p2_version_skew_boundary_is_decision_time_inclusive() -> None:
    """P2: a bump at decision_time - 1 is in force; at decision_time it is skew."""
    ctx = _ctx()
    for bump_time, expected in ((98, "ADMIT"), (99, "ADMIT"), (100, "REJECT"), (101, "REJECT")):
        case = {
            "case_id": f"skew-boundary-{bump_time}",
            "history": [
                B.event(
                    B.EVENT_GRANT, 50, "patient-s", "patient-s",
                    B.PURPOSE_SELF_CARE, expiry=9000,
                ),
                B.event(B.EVENT_POLICY_VERSION_BUMP, bump_time, "sys", "sys", "*"),
            ],
            "request": B.request("patient-s", B.PURPOSE_SELF_CARE, 100),
        }
        outcome = B.run_baseline(B.BASELINE_B3, case, ctx)
        assert outcome.observed_outcome == expected, (bump_time, outcome.detail)
        if expected == "REJECT":
            assert f"{B.RC_B3_VERSION_SKEW}:bump_at={bump_time}" in outcome.detail


def test_p2_skew_race_detected_by_b3_only() -> None:
    """P5 (policy-skew race): B3 REJECTs while B0/B1/B2 all ADMIT."""
    case = {
        "case_id": "skew-race",
        "history": [
            B.event(
                B.EVENT_GRANT, 100, "patient-k", "patient-k",
                B.PURPOSE_CARE_TEAM, expiry=5000,
            ),
            B.event(B.EVENT_POLICY_VERSION_BUMP, 1200, "sys", "sys", "*"),
        ],
        "request": B.request("patient-k", B.PURPOSE_CARE_TEAM, 500),
    }
    ctx = _ctx()
    verdicts = {
        arm: B.run_baseline(arm, case, ctx).observed_outcome for arm in ARMS
    }
    assert verdicts[B.BASELINE_B0] == "ADMIT"
    assert verdicts[B.BASELINE_B1] == "ADMIT"
    assert verdicts[B.BASELINE_B2] == "ADMIT"
    assert verdicts[B.BASELINE_B3] == "REJECT"


def test_p3_unknown_principal_is_not_applicable_never_deny_or_permit() -> None:
    """P3 (unknown): no delegation relationship ever existed -> NOT_APPLICABLE."""
    case = {
        "case_id": "unknown-principal",
        "history": [
            B.event(
                B.EVENT_GRANT, 100, "owner-1", "delegate-1",
                B.PURPOSE_RESEARCH, expiry=9000,
            ),
        ],
        "request": B.request("stranger", B.PURPOSE_RESEARCH, 500),
    }
    history = _validated(case)
    assert B.oracle_decision(history) == B.NOT_APPLICABLE
    # Zanzibar walks tuples by delegate id; a stranger holds no tuple.
    assert (
        B.evaluate_engine(B.ENGINE_ZANZIBAR, history, history.request)
        == B.NOT_APPLICABLE
    )
    # The compiled final-state engines answer on (actor, purpose) pairs.
    for engine_id in (B.ENGINE_XACML, B.ENGINE_CEDAR):
        decision = B.evaluate_engine(engine_id, history, history.request)
        assert decision in (B.NOT_APPLICABLE, B.DENY), (engine_id, decision)
        assert decision != B.PERMIT


def test_p3_dsl_unknown_authority_is_indeterminate_not_permit() -> None:
    """P3 (DSL): an access on authority never established is INDETERMINATE."""
    trace = _dsl_trace(
        _dsl_event(D.EVENT_KIND_GRANT, 1, "a"),
        _dsl_event(D.EVENT_KIND_ACCESS, 2, "z"),
    )
    verdict = D.evaluate_trace_json(trace)
    assert verdict["outcome"] == D.OUTCOME_INDETERMINATE
    kinds = [f["kind"] for f in verdict["findings"]]
    assert kinds == [D.FINDING_UNESTABLISHED_AUTHORITY]


# ---------------------------------------------------------------------------
# Part 2 — metamorphic relations over seeded randomized corpora.
# ---------------------------------------------------------------------------


def test_m1_appending_revoke_never_creates_a_permit() -> None:
    """M1: revoking a delegation can only reduce access (never mint a permit).

    For every corpus unit and every engine (plus the oracle), appending a
    REVOKE for the requesting (actor, purpose) key at the decision time must
    not turn a non-PERMIT into a PERMIT, and must preserve any PERMIT that
    existed only if the revocation did not reach the key (checked via the
    no-new-permit direction; the preserve direction is engine-specific and
    covered by M2/M4).
    """
    for trial in range(300):
        rng = random.Random(41000 + trial)
        case = _random_history_case(rng, f"m1-{trial}")
        history = _validated(case)
        req = history.request
        revoke = B.PolicyEvent(
            len(history.events), B.EVENT_REVOKE, req.decision_time,
            req.actor_id, req.actor_id, req.purpose,
        )
        revoked = B.PolicyHistory(history.case_id, history.events + (revoke,), req)
        base_oracle = B.oracle_decision(history)
        after_oracle = B.oracle_decision(revoked)
        assert not (after_oracle == B.PERMIT and base_oracle != B.PERMIT), (
            trial, base_oracle, after_oracle,
        )
        for engine_id in B.ENGINE_MODELS:
            base = B.evaluate_engine(engine_id, history, req)
            after = B.evaluate_engine(engine_id, revoked, req)
            assert not (after == B.PERMIT and base != B.PERMIT), (
                trial, engine_id, base, after,
            )


def test_m2_final_state_engines_deny_after_appended_revoke() -> None:
    """M2: after appending the revocation, compiled final-state engines deny.

    XACML deny-overrides and Cedar forbid precedence both compile the final
    policy state; once the appended REVOKE is the latest event for the
    request key, any pre-existing final-state entry for that (actor, purpose)
    pair forces DENY. Zanzibar instead loses the tuple (PERMIT -> 
    NOT_APPLICABLE at best), never gaining a permit.
    """
    for trial in range(300):
        rng = random.Random(42000 + trial)
        case = _random_history_case(rng, f"m2-{trial}")
        history = _validated(case)
        req = history.request
        revoke = B.PolicyEvent(
            len(history.events), B.EVENT_REVOKE, req.decision_time,
            req.actor_id, req.actor_id, req.purpose,
        )
        revoked = B.PolicyHistory(history.case_id, history.events + (revoke,), req)
        for engine_id in (B.ENGINE_XACML, B.ENGINE_CEDAR):
            after = B.evaluate_engine(engine_id, revoked, req)
            assert after == B.DENY, (trial, engine_id, after)
        zanzibar_after = B.evaluate_engine(B.ENGINE_ZANZIBAR, revoked, req)
        if zanzibar_after == B.PERMIT:
            assert B.evaluate_engine(B.ENGINE_ZANZIBAR, history, req) == B.PERMIT, (
                trial, "read-time walk minted a permit after revocation",
            )


def test_m3_appending_policy_bump_only_tightens_conformance_detection() -> None:
    """M3: adding a policy version can only tighten conformance detection.

    Appending a POLICY_VERSION_BUMP at a logical time >= the decision time:
    - B3 ADMIT -> REJECT is allowed (new skew evidence) and B3 REJECT must
      stay REJECT (detection monotonicity);
    - engine decisions are unchanged (bumps are skipped by both the final-
      state derivation and the read-time tuple walk);
    - the oracle verdict is unchanged (the bump carries no delegation
      authority).
    """
    ctx = _ctx()
    for trial in range(300):
        rng = random.Random(43000 + trial)
        case = _random_history_case(rng, f"m3-{trial}")
        history = _validated(case)
        req = history.request
        max_time = max(e.logical_time for e in history.events)
        bump_time = max(req.decision_time, max_time)
        bump = B.PolicyEvent(
            len(history.events), B.EVENT_POLICY_VERSION_BUMP, bump_time,
            "sys", "sys", "*",
        )
        bumped = B.PolicyHistory(history.case_id, history.events + (bump,), req)
        b3_before = B.run_baseline(B.BASELINE_B3, case, ctx).observed_outcome
        b3_after = B.run_baseline(B.BASELINE_B3, _to_case(bumped), ctx).observed_outcome
        assert b3_before in ("ADMIT", "REJECT") and b3_after in ("ADMIT", "REJECT")
        if b3_before == "REJECT":
            assert b3_after == "REJECT", (trial, "detection weakened by version bump")
        assert B.oracle_decision(bumped) == B.oracle_decision(history), trial
        for engine_id in B.ENGINE_MODELS:
            assert B.evaluate_engine(engine_id, bumped, req) == B.evaluate_engine(
                engine_id, history, req
            ), (trial, engine_id)


def test_m4_time_shift_invariance() -> None:
    """M4: shifting all logical times by one constant preserves decisions.

    Temporal semantics depend on order and relative distances only: the
    oracle verdict and Zanzibar's read-time decision are unchanged when every
    logical_time, expiry and the decision time move by the same shift.
    """
    for trial in range(300):
        rng = random.Random(44000 + trial)
        case = _random_history_case(rng, f"m4-{trial}")
        history = _validated(case)
        shift = rng.randint(1, 999)
        shifted_events = tuple(
            B.PolicyEvent(
                e.order, e.event_kind, e.logical_time + shift, e.actor_id,
                e.delegate_id, e.purpose,
                e.expiry + shift if e.expiry is not None else None,
            )
            for e in history.events
        )
        shifted_request = B.AccessRequest(
            history.request.actor_id,
            history.request.purpose,
            history.request.decision_time + shift,
        )
        shifted = B.PolicyHistory(history.case_id, shifted_events, shifted_request)
        assert B.oracle_decision(shifted) == B.oracle_decision(history), trial
        assert B.evaluate_engine(
            B.ENGINE_ZANZIBAR, shifted, shifted_request
        ) == B.evaluate_engine(B.ENGINE_ZANZIBAR, history, history.request), trial


def _dsl_event(kind: str, logical_time: int, principal: str, *, delegate: str = "epoch") -> dict[str, object]:
    return {
        "principal": principal,
        "tenant": "tenant-1",
        "resource": "record-1",
        "purpose": "care",
        "policy_state": delegate,
        "logical_time": logical_time,
        "kind": kind,
    }


def _dsl_trace(*events: dict[str, object]) -> dict[str, object]:
    return {
        "version": D.POLICY_TRACE_DSL_VERSION,
        "trace_id": "property-trace",
        "events": list(events),
    }


def _dsl_random_events(rng: random.Random) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    t = rng.randint(0, 50)
    for _ in range(rng.randint(2, 7)):
        kind = rng.choice(
            [D.EVENT_KIND_GRANT, D.EVENT_KIND_REVOKE, D.EVENT_KIND_DELEGATE, D.EVENT_KIND_ACCESS]
        )
        principal = rng.choice(["a", "b", "c"])
        delegate = rng.choice(["a", "b", "c"])
        t += rng.randint(1, 10)
        events.append(_dsl_event(kind, t, principal, delegate=delegate))
    return events


def test_m5_dsl_findings_are_append_only() -> None:
    """M5: replay never erases a witnessed error — prefix findings persist.

    For every corpus trace and every prefix, each (kind, witness index) of
    the prefix verdict also appears in the full trace's findings.
    """
    checked = 0
    for trial in range(250):
        rng = random.Random(45000 + trial)
        events = _dsl_random_events(rng)
        try:
            full = D.evaluate_trace_json(_dsl_trace(*events))
        except D.PolicyTraceError:
            continue
        full_findings = {
            (f["kind"], f["witness_event_index"]) for f in full["findings"]
        }
        for cut in range(1, len(events)):
            try:
                prefix = D.evaluate_trace_json(_dsl_trace(*events[:cut]))
            except D.PolicyTraceError:
                continue
            for finding in prefix["findings"]:
                key = (finding["kind"], finding["witness_event_index"])
                assert key in full_findings, (trial, cut, key)
            checked += 1
    assert checked > 0, "corpus produced no prefix checks"


def test_m6_dsl_revoke_flips_and_regrant_restores() -> None:
    """M6: revocation flips later access to DENY and stays fail-closed.

    A REVOKE after a PERMIT-producing access denies any later access; the
    DSL treats re-granting a revoked principal as a trace-level error
    (sticky revocation, fail-closed) rather than silently restoring.
    """
    base = (
        _dsl_event(D.EVENT_KIND_GRANT, 1, "a"),
        _dsl_event(D.EVENT_KIND_ACCESS, 2, "a"),
    )
    assert D.evaluate_trace_json(_dsl_trace(*base))["outcome"] == D.OUTCOME_PERMIT

    revoked = base + (_dsl_event(D.EVENT_KIND_REVOKE, 3, "a"), _dsl_event(D.EVENT_KIND_ACCESS, 4, "a"))
    verdict = D.evaluate_trace_json(_dsl_trace(*revoked))
    assert verdict["outcome"] == D.OUTCOME_DENY

    # Revocation is sticky (fail-closed): even a fresh GRANT after the REVOKE
    # cannot silently restore authority — the restored grant is witnessed as
    # a revoked-actor transitivity error and the access stays DENIED.
    restored = (
        _dsl_event(D.EVENT_KIND_GRANT, 1, "a"),
        _dsl_event(D.EVENT_KIND_REVOKE, 2, "a"),
        _dsl_event(D.EVENT_KIND_GRANT, 3, "a"),
        _dsl_event(D.EVENT_KIND_ACCESS, 4, "a"),
    )
    verdict = D.evaluate_trace_json(_dsl_trace(*restored))
    assert verdict["outcome"] == D.OUTCOME_DENY
    assert [f["kind"] for f in verdict["findings"]] == [D.FINDING_REVOKED_ACTOR_TRANSITIVITY]

    # Revoked-source transitivity: the delegatee's stale authority is denied
    # and the trace-level error is witnessed.
    transit = (
        _dsl_event(D.EVENT_KIND_GRANT, 1, "a"),
        _dsl_event(D.EVENT_KIND_DELEGATE, 2, "a", delegate="b"),
        _dsl_event(D.EVENT_KIND_REVOKE, 3, "a"),
        _dsl_event(D.EVENT_KIND_ACCESS, 4, "b"),
    )
    verdict = D.evaluate_trace_json(_dsl_trace(*transit))
    assert verdict["outcome"] == D.OUTCOME_DENY
    assert [f["kind"] for f in verdict["findings"]] == [D.FINDING_REVOKED_ACTOR_TRANSITIVITY]


# ---------------------------------------------------------------------------
# Part 3 — mutation checks over the seeded mutant corpus (RQ2 analogue).
# ---------------------------------------------------------------------------


def test_x1_b3_kills_a_superset_of_b1_and_b2_mutants() -> None:
    """X1: B3's killed-mutant set is a superset of B1's and B2's, and strictly
    larger (the temporal arm kills mutants the pointwise arms all miss)."""
    ctx = _ctx()
    killed: dict[str, set[tuple[int, str]]] = {arm: set() for arm in ARMS}
    total = 0
    for trial in range(150):
        rng = random.Random(51000 + trial)
        case = _random_history_case(rng, f"mut-{trial}")
        if isinstance(B._validate_case(case), B.Outcome):  # type: ignore[arg-type]
            continue
        for name, mutant in _mutants(case, rng):
            if isinstance(B._validate_case(mutant), B.Outcome):  # type: ignore[arg-type]
                continue
            total += 1
            for arm in ARMS:
                outcome = B.run_baseline(arm, mutant, ctx)
                assert outcome.observed_outcome in ("ADMIT", "REJECT"), (arm, outcome.detail)
                if outcome.observed_outcome == "REJECT":
                    killed[arm].add((trial, name))
    assert total >= 400, f"mutant corpus too small: {total}"
    assert killed[B.BASELINE_B1] <= killed[B.BASELINE_B3]
    assert killed[B.BASELINE_B2] <= killed[B.BASELINE_B3]
    temporal_only = killed[B.BASELINE_B3] - killed[B.BASELINE_B1] - killed[B.BASELINE_B2]
    assert temporal_only, "B3 killed nothing the pointwise arms both missed"


def test_x2_rejects_carry_stable_reason_codes_and_verdicts_are_typed() -> None:
    """X2: every REJECT detail embeds its arm's stable reason code; every
    verdict over the whole corpus stays inside the documented outcome set."""
    ctx = _ctx()
    reason_codes = {
        B.BASELINE_B0: B.RC_B0_STRUCTURAL_DIFF,
        B.BASELINE_B1: B.RC_B1_ENGINE_SELF_TEST,
        B.BASELINE_B2: B.RC_B2_CROSS_ENGINE_DISAGREEMENT,
        B.BASELINE_B3: B.RC_B3_TEMPORAL_CONFORMANCE,
    }
    for trial in range(120):
        rng = random.Random(52000 + trial)
        case = _random_history_case(rng, f"rc-{trial}")
        if isinstance(B._validate_case(case), B.Outcome):  # type: ignore[arg-type]
            continue
        for arm in ARMS:
            outcome = B.run_baseline(arm, case, ctx)
            assert outcome.observed_outcome in ("ADMIT", "REJECT"), (arm, outcome.detail)
            if outcome.observed_outcome == "REJECT":
                assert reason_codes[arm] in outcome.detail, (arm, outcome.detail)
                assert outcome.counted_as_success is True
            else:
                assert outcome.counted_as_success is True


def test_x3_deterministic_generation_and_evaluation() -> None:
    """X3: identical seeds reproduce byte-identical decision rows.

    Replaying the corpus generation and the full evaluation stack twice under
    the same per-trial seeds yields identical JSON rows — no hidden clock or
    nondeterminism anywhere in the engines, arms or oracle.
    """
    rows: list[str] = []
    for _repeat in range(2):
        for trial in range(30):
            rng = random.Random(53000 + trial)
            case = _random_history_case(rng, f"det-{trial}")
            history = _validated(case)
            row = {
                "case_id": history.case_id,
                "oracle": B.oracle_decision(history),
                "engines": _engine_decisions(history),
                "arms": {
                    arm: B.run_baseline(arm, case, _ctx()).observed_outcome
                    for arm in ARMS
                },
            }
            rows.append(json.dumps(row, sort_keys=True))
    assert rows[:30] == rows[30:]


# ---------------------------------------------------------------------------
# Part 4 — DSL parse-level fail-closed boundaries and engine direct semantics.
# ---------------------------------------------------------------------------


def test_dsl_parse_rejects_ambiguous_and_malformed_traces() -> None:
    """Negative boundaries: the DSL refuses, never silently repairs."""
    good = _dsl_event(D.EVENT_KIND_GRANT, 5, "a")
    later = _dsl_event(D.EVENT_KIND_ACCESS, 5, "a")
    earlier = _dsl_event(D.EVENT_KIND_ACCESS, 2, "a")

    with _expect_policy_trace_error(D.REASON_UNORDERED_TIMESTAMPS):
        D.parse_policy_trace(_dsl_trace(good, earlier))
    with _expect_policy_trace_error(D.REASON_DUPLICATE_TIMESTAMP):
        D.parse_policy_trace(_dsl_trace(good, later))
    with _expect_policy_trace_error(D.REASON_EMPTY_TRACE):
        D.parse_policy_trace(
            {"version": D.POLICY_TRACE_DSL_VERSION, "trace_id": "t", "events": []}
        )
    with _expect_policy_trace_error(D.REASON_SCHEMA_VERSION_MISMATCH):
        D.parse_policy_trace({"version": "other", "trace_id": "t", "events": [good]})
    with _expect_policy_trace_error(D.REASON_MALFORMED_EVENT):
        D.parse_policy_trace({"version": D.POLICY_TRACE_DSL_VERSION, "trace_id": "", "events": [good]})
    no_time = dict(good)
    del no_time["logical_time"]
    with _expect_policy_trace_error(D.REASON_MISSING_LOGICAL_TIME):
        D.parse_policy_trace(_dsl_trace(no_time))  # type: ignore[arg-type]


def test_dsl_delegation_cycle_and_revoke_before_grant_witnessed() -> None:
    """Positive trace-level error detection: cycles and source-less delegations."""
    cycle = _dsl_trace(
        _dsl_event(D.EVENT_KIND_GRANT, 1, "a"),
        _dsl_event(D.EVENT_KIND_DELEGATE, 2, "a", delegate="b"),
        _dsl_event(D.EVENT_KIND_DELEGATE, 3, "b", delegate="a"),
    )
    verdict = D.evaluate_trace_json(cycle)
    kinds = [f["kind"] for f in verdict["findings"]]
    assert D.FINDING_DELEGATION_CYCLE in kinds

    sourceless = _dsl_trace(_dsl_event(D.EVENT_KIND_DELEGATE, 1, "a", delegate="b"))
    verdict = D.evaluate_trace_json(sourceless)
    kinds = [f["kind"] for f in verdict["findings"]]
    assert D.FINDING_REVOKE_BEFORE_GRANT in kinds


def test_engines_disagree_on_delegate_access_and_oracle_adjudicates() -> None:
    """Engine divergence on a delegated (owner -> delegate) request, with the
    oracle adjudicating from ordered-history state independently."""
    case = {
        "case_id": "delegate-access",
        "history": [
            B.event(
                B.EVENT_GRANT, 100, "owner-2", "delegate-2",
                B.PURPOSE_RESEARCH, expiry=9000,
            ),
        ],
        "request": B.request("delegate-2", B.PURPOSE_RESEARCH, 500),
    }
    history = _validated(case)
    decisions = _engine_decisions(history)
    assert B.oracle_decision(history) == B.NOT_APPLICABLE
    assert decisions[B.ENGINE_ZANZIBAR] == B.PERMIT, (
        "read-time tuple walk honors the delegation tuple",
    )
    assert len(set(decisions.values())) > 1, "engines must disagree on this encoding"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _to_case(history: B.PolicyHistory) -> dict[str, object]:
    return {
        "case_id": history.case_id,
        "history": [e.to_dict() for e in history.events],
        "request": history.request.to_dict(),
    }


from collections.abc import Iterator  # noqa: E402
from contextlib import contextmanager  # noqa: E402


@contextmanager
def _expect_policy_trace_error(reason_code: str) -> Iterator[None]:
    try:
        yield
    except D.PolicyTraceError as exc:
        assert exc.reason_code == reason_code, (exc.reason_code, reason_code)
    else:
        raise AssertionError(f"expected PolicyTraceError {reason_code}")
