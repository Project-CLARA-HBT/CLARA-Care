# W5 Formal / Exhaustive Governance Assurance — Report

Workstream: **W5 formal/exhaustive assurance** (code + tests only; no git
commits, no remote execution, no CareGuard/SOICT/remote VPS).

Deliverable: a runnable, compact canonical model of the governance commit
contract, with machine-checked invariants and a bounded exhaustive enumerator.
The model is deliberately CLARA/GLHS-agnostic: it captures only the finite
coordinates a governed commit depends on (who, for what, against which
versions, under which authorization artifacts, with what outcome).

## Artifacts

| File | Purpose |
| --- | --- |
| `evaluation/formal_governance/model.py` | Canonical `State` model and vocabulary |
| `evaluation/formal_governance/transitions.py` | 13 deterministic transitions (`apply` + `Outcome`) |
| `evaluation/formal_governance/invariants.py` | Machine-checkable invariants I1–I11 |
| `evaluation/formal_governance/explore.py` | Bounded exhaustive BFS enumerator |
| `evaluation/formal_governance/tests/test_model.py` | Model + transition unit tests |
| `evaluation/formal_governance/tests/test_invariants.py` | Invariant checker tests (incl. adversarial) |
| `evaluation/formal_governance/tests/test_explore.py` | Enumerator tests (determinism, coverage, counterexamples) |

## Canonical state

`State` fields: `subject`, `actor`, `role`, `purpose`, `task`, `state_version`,
`policy_version`, `consent_version`, `consent_state`, `snapshot_id`,
`digest_valid`, `expiry`, `disclosed_evidence_set`, `proposal_base`,
`proposal_binding`, `proposal_evidence`, `proposal_actor/role/purpose/task`,
`proposal_policy_version`, `proposal_consent_version`, `origin`, `idempotency_key`,
`committed_keys`, `commit_status`.

Domain decisions that keep the reachable space finite and small:

- version coordinates saturate at `MAX_VERSION = 1` (invariants rely on
  *equality*, which saturation preserves — stale-version rejection is fully
  exercised with a two-value domain);
- evidence universe is `{e0, e1}` (4 subsets);
- expiry ∈ {alive, expired}; idempotency keys ∈ {`None`, `k0`};
- a disclosure issues one live snapshot at a time; unbound proposals carry no
  evidence (base-version-only path).

## Transitions

`issue_disclosure`, `create_proposal`, `advance_state`, `revoke_consent`,
`change_role`, `change_purpose`, `advance_policy`, `expire_snapshot`,
`corrupt_digest`, `replay_proposal`, `commit`, `retry`, `rollback`.

Every transition is a pure function returning an `Outcome {admitted, state,
reason, idempotent}`. A failed commit records `commit_status=rejected` without
touching canonical coordinates; a later `retry` re-runs the same admission
predicate, so a stale/governance-invalid proposal can never become an
unauthorized success. `commit`/`replay_proposal` with an already-applied
idempotency key are idempotent replays (one logical transition, no version
advance).

## Invariants (machine-checked)

| Id | Statement |
| --- | --- |
| I1 | no bound proposal commits with stale base state |
| I2 | no post-revocation commit |
| I3 | no wrong actor/role/purpose/task commit |
| I4 | no expired/tampered snapshot commit |
| I5 | no evidence outside the disclosed subset supports a bound commit |
| I6 | idempotent replay yields one logical transition |
| I7 | successful commit advances the version exactly once |
| I8 | rejected transition does not advance canonical state |
| I9 | admitted transition is reconstructable (deterministic re-apply) |
| I10 | current policy coordinate participates in admission |
| I11 | a clean valid proposal can commit in an admissible state (positive reachability) |

State invariants are checked on every reached state; transition invariants are
checked on every attempted transition, independently of the model's own
admission logic, so a deliberately weakened (mutated) model surfaces as a
recorded counterexample instead of being silently accepted. I1–I10 are also
unit-tested against synthetic adversarial outcomes (hand-built states + fake
successes), which is how the "no wrong actor/task commit" case is exercised
even though the enumerator's transition set never changes actor/task.

## Exploration results

Bounded exhaustive BFS from a clean initial state, deduplicating canonical
states and retaining minimal (shortest-path) counterexamples per invariant.

| Metric | depth 5 (default) | depth 6 (deep) |
| --- | ---: | ---: |
| Unique states | 21,361 | 69,342 |
| Distinct canonical coordinate tuples | 32 | 32 |
| Transitions explored | 90,432 | 378,602 |
| Admitted | 62,416 | 258,185 |
| Rejected | 28,016 | 120,417 |
| Admitted commits | 2,226 | 5,790 |
| Idempotent replays | 46 | 480 |
| **Violations** | **0** | **0** |
| Minimal counterexamples | none | none |
| I11 (clean commit reachable) | true | true |
| Runtime | 3.5 s | 16.6 s |
| Tool version | `w5-formal-assure-v1.0` | same |
| Source SHA | `67a1b6fe…99f7` | same |

Reproduce with `python -m evaluation.formal_governance.explore` (default depth)
or `explore(max_depth=6)`.

## Test results

Focused pytest over `evaluation/formal_governance/tests`:

```
59 passed in ~9 s
```

`ruff check evaluation/formal_governance` — clean (0 errors).

## Limitation statement

Bounded checking is not universal proof. The enumerator explores all reachable
states up to a fixed depth bound over finite, saturated coordinate domains
(single subject/actor/task, two roles/purposes, versions in {0,1}, two-item
evidence universe, one idempotency key). It therefore does not constitute a
formal proof for unbounded versions, arbitrary evidence sets, additional
subjects/actors, or interleavings longer than the depth bound. Within that
bounded universe, however, every reachable state satisfies all invariants and
every defined transition preserves them (0 violations, 0 counterexamples).
