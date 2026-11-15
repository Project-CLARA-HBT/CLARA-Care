# COMPSAC-X06_coarse_occ — implementation spec: global profile-version OCC comparator

**Task:** `COMPSAC-X06_coarse_occ` · **Phase:** `P03` · **Venue:** `compsac` · **Status:** IMPLEMENTED (this worktree)
**Contract source:** `research/venue2027/VENUES/compsac/TASKS/COMPSAC-X06_coarse_occ.md`
**Baseline fidelity adapter (real, reused — never re-implemented here):** `evaluation/venue2027/compsac/baselines.py`, arm `global-profile-version-occ` (blueprint **B0**, `COMPSAC_BASELINES_VERSION = "1.0.0"`, registry fidelity `FAITHFUL_PORT`)

## 1. What the B0 arm is

B0 is the **common coarse implementation** (blueprint strong-baseline arm B0): optimistic
concurrency control whose commit-time validation scope is the **WHOLE clinical profile**.
Every transaction snapshots one coarse profile epoch at start; at commit that epoch must
be **unchanged**, otherwise the transaction aborts with `GLOBAL_PROFILE_STALE`. Because
the epoch is shared by all entities, **any concurrent committed write anywhere in the
profile invalidates every in-flight transaction** — the widest possible validation scope,
which **upper-bounds the false-stale rejection rate** and is the reference point of RQ1:
*compared with globally versioned OCC, does a dependency-complete read set reduce
unnecessary aborts without increasing forbidden commits?*

## 2. Formal model

Fix a schedule `W = (E, τ, T)` where `E` is the entity set of ONE clinical profile, `τ`
maps every `e ∈ E` to a version, and `T = (t_1, …, t_n)` is the concurrent write schedule
with `t_i = (id_i, R_i, W_i, v_i)` (declared reads, declared writes, observed versions;
all transactions begin at the same snapshot per the shared harness interleaving
convention, with consent epoch `c_i` and policy epoch `p_i`).

**State.** One coarse profile counter `G` over the whole profile (equivalently: the full
version vector `τ` treated as a single validation unit — a genuine single-counter
implementation carries exactly this state, and "the counter moved" ⟺ "any entity version
moved").

**Transition relation** (transactions commit in schedule order; commit of `t_i`):

1. `stale(t_i) := ∃e ∈ E: τ_now(e) ≠ v_start(e)` — checked over the **FULL entity
   space** `E`, never a max-version proxy. (`max_e τ(e)` is NOT a faithful counter: an
   unrelated edit to a lower-versioned entity moves the real counter but not the max.)
2. If `stale(t_i)` → **ABORT / `GLOBAL_PROFILE_STALE`** (fail closed, no writes install).
3. Else, for every `w ∈ W_i` with a bound epoch: consent/policy epoch mismatch →
   **ABORT / `CONSENT_EPOCH_STALE` | `POLICY_EPOCH_STALE`**.
4. Else **COMMIT**: install each `w ∈ W_i` at `τ(w)+1` and advance the profile epoch.
5. Unknown write/read target → **ABORT / `ENTITY_UNKNOWN`**; malformed schedule →
   `EXECUTION_ERROR / SCHEDULE_MALFORMED` (never silently a safe rejection).

**Guarantee (no lost updates, by over-validation).** Two transactions writing the same
entity cannot both commit: the second observes a moved epoch and aborts. Serializability
of the committed history follows trivially — B0 commits only runs that are equivalent to
fully serial execution (at most one transaction per profile-epoch window).

**False-stale cost (the measured quantity of this task).** Define the oracle-classified
false-stale set

> `FS(W) = { t_i : outcome(t_i) = ABORT ∧ reason = GLOBAL_PROFILE_STALE ∧ W_i ∩ ⋃_{j<i, COMMIT} W_j = ∅ }`

i.e. aborts whose write target is **disjoint from every previously committed write** —
no read/write or write/write conflict existed, only the shared epoch moved. On a
profile with `n` concurrent unrelated-entity writes, `|FS| = n − 1` exactly: the first
commit advances the counter and every subsequent in-flight transaction is refused
although nothing it touched changed. This is the avoidable-rejection mass B1 (Silo-style
entity read-set OCC) and B4 (dependency-complete scope-local OCC) eliminate on the same
schedule, and it is what RQ1's "unnecessary aborts" denominators are computed from.

Scope: same-profile concurrent writes only; cross-profile contention is outside B0's
declared validation scope (the profile IS the lock domain).

## 3. What was implemented (one commit, this worktree)

1. **`evaluation/venue2027/compsac/baselines.py` — backwards-compatible fidelity fix to
   B0's commit-time validation** (no signature, outcome label or reason-code change):
   `_run_global_profile_occ` validated the profile epoch through a **max-version proxy**
   (`initial_global < max(current versions)`), which is NOT a faithful single coarse
   counter — an unrelated commit to an entity at or below the current max (e.g. an empty
   `care_plan` register at v0 while `medication_order` sits at v1) moved the real
   counter but not the max, so a concurrent transaction was wrongly ADMITTED. Replaced
   with the exact counter semantics: the profile epoch moved iff the current version
   map differs **anywhere** from the start snapshot (`store.current_version_map() !=
   initial_versions`). Same `Outcome` shape, same `GLOBAL_PROFILE_STALE` code, same
   aggregation; the 25 pre-existing `evaluation/venue2027/compsac/test_baselines.py`
   tests stay green.
2. **`research/venue2027/compsac/tests/test_x06_coarse_occ.py` (NEW)** — exercises the
   REAL adapter via `run_baseline(bl.B0_GLOBAL_PROFILE, case, ctx)` (no fork, no stub):
   concurrent writes to DIFFERENT entities of the SAME profile (n = 6, disjoint targets,
   private per-transaction journals as declared reads), asserting (a) the first commit
   aborts every later transaction with `GLOBAL_PROFILE_STALE`, (b) the REAL false-stale
   count is computed by an **independent classifier** inside the test (not read from B0's
   internals) and equals `n − 1 = 5`, (c) the same schedule under B1 and B4 commits all
   6 transactions with zero aborts (the false-stale differential of RQ1, same case, same
   seed, equal config), (d) X06-CASE-07 coarse-counter fidelity: an unrelated edit to a
   LOWER-versioned entity aborts an in-flight transaction (regression pin for the max()
   proxy defect fixed above), (e) X06-CASE-06 honest accounting: a same-entity
   write-write collision is a genuine abort and the independent classifier counts ZERO
   false-stale for that schedule, (f) single-writer control (no aborts), plus
   fail-closed adversarial controls (malformed schedule → `EXECUTION_ERROR` /
   `SCHEDULE_MALFORMED`; byte-identical determinism; equal-config discipline; spec
   version pin `X06_COARSE_OCC_SPEC_VERSION = "1.0.0"` over
   `COMPSAC_BASELINES_VERSION = "1.0.0"`).

## 4. Measured result (real, deterministic, from the test run)

On the X06 unrelated-edit schedule (6 workers, disjoint same-profile write targets):

| Arm | committed | aborted | false-stale (independent classifier) |
|---|---|---|---|
| B0 `global-profile-version-occ` | 1 | 5 | **5** (all aborts false-stale) |
| B1 `silo-style-entity-readset-occ` | 6 | 0 | 0 |
| B4 `dependency-complete-scope-local-occ` | 6 | 0 | 0 |

`forbidden_commits = 0` in every arm. The false-stale cost of the global-profile
comparator is exactly `n − 1 = 5` avoidable rejections on this schedule; the
dependency-scoped arms pay none. This is the B0-side evidence for RQ1.

## 5. Baseline parity and independence

- The test imports the REAL baseline module
  (`evaluation/venue2027/compsac/baselines.py`) and calls its public
  `run_baseline` entry point; the false-stale classifier is derived from the declared
  schedule plus the adapter's per-transaction outcome records only — it never consults
  B0's internal counters, so a labeled-but-false count cannot pass.
- `evaluation/venue2027/compsac/test_baselines.py` (25 tests) remains green
  (backwards-compatible change only).
- All arms run the identical schedule, case id and seed (equal-config discipline).
