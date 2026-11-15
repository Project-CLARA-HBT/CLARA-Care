# POPETS-X05_full_refresh — implementation spec: strong/expensive full-refresh comparator

**Task:** `POPETS-X05_full_refresh` · **Phase:** `P03` · **Venue:** `popets` · **Status:** IMPLEMENTED (this worktree)
**Contract source:** `research/venue2027/VENUES/popets/TASKS/POPETS-X05_full_refresh.md`
**Baseline fidelity adapters (real, reused — never re-implemented here):** `evaluation/venue2027/popets/baselines.py` (`POPETS_BASELINES_VERSION = "1.0.0"`)

## 1. What the X05 arm is

X05 is the **strong/expensive comparator** for RQ2/RQ3: on **any** consent-revocation
event it **purges ALL cached projections** of the affected subject — every purpose,
every grant, every transitively derived artifact (prompt segments, cached summaries,
embedding pointers, retry payloads, fallback transports) — and thereafter serves each
dispatch **only by recompute-or-hit from the live source snapshot** under live-purpose
permission clauses. This is blueprint arm **B1 in its strongest form**
(`coarse-cache-purge-on-revocation`), pushed to the safety limit:

- **Revocation-complete by over-invalidation.** Because the purge is unconditional and
  subject-wide, no cached projection derived from pre-revocation state can survive past
  `t_r`; there is no key space (no epoch, no TTL) under which a stale entry could be
  re-served. A dispatch after `t_r` either (a) is authorized against the live snapshot
  and rebuilt, or (b) fails closed.
- **It is the safety ceiling of cache-based designs** — the strongest possible cache
  invalidation policy — but it pays for safety with availability/cost: authorized
  context for *unaffected* grants and purposes is destroyed too (false invalidation),
  and every post-purge authorized dispatch must rebuild from source.

## 2. Formal model

Fix a workload `W = (S, R, D)` where `S` is the live source snapshot
(`artifact_id -> bytes`), `R` is the set of revocation events
`(subject, grant, purpose, t_r)`, and `D = (d_1, …, d_n)` is the dispatch schedule with
`d_i = (dispatch_id, subject, grant, purpose, lineage(d_i), t_i)`.

**State.** A single cache `C: K -> lineage-projection`, keyed by
`(subject, grant, purpose, dispatch_id)`; no epochs, no TTL.

**Transition relation** (evaluated per dispatch `d_i` in schedule order):

1. `hit(d_i) := key(d_i) ∈ C` where `key(d_i) = (subject_i, grant_i, purpose_i, dispatch_id_i)`.
2. **Authorize** against the live snapshot (never against cache state):
   `auth(d_i) = REJECT/REVOKED_CONTEXT` if `∃(s,g,p,t_r) ∈ R: s = subject_i ∧ g = grant_i ∧ (p = purpose_i ∨ p = *) ∧ t_i ≥ t_r`;
   `REJECT/LINEAGE_SOURCE_MISSING` if `lineage(d_i) ⊄ dom(S)`; else `ADMIT` with
   `exposed_bytes = Σ_{a ∈ lineage(d_i)} |S[a]|`.
3. **Fill on admitted miss:** `ADMIT ∧ ¬hit ⇒ C[key] := lineage(d_i)`.
4. **Full-refresh on revocation:** for every `r ∈ R` with `r.subject = subject_i` and
   `t_i ≥ r.t_r` not yet applied: `C := ∅` (purge **ALL** cached projections of the
   subject, all purposes, all grants, no dependency labels by design), and the event is
   counted once.

**Guarantee (revocation-complete future disclosure bound).** For every dispatch
`d_i` with `t_i ≥ t_r` for some covering revocation, `auth(d_i) = REJECT` regardless of
cache state: the purge empties the entire cache at or before the first post-revocation
dispatch, and authorization re-derives admissibility from the live snapshot only. Hence
no post-revocation dispatch can leak revoked context **through cache reuse** — the leak
class of RQ1 — at the price of full-rebuild availability cost (RQ3).
Scope: post-revocation *future* dispatches only; no claim of retroactive erasure of
content already delivered to external providers (blueprint §8).

## 3. Cost model (RQ3 quantities, all recorded in the Outcome detail)

Per run, `coarse-cache-purge-on-revocation` reports (added backwards-compatibly;
`invalidation_events`, per-dispatch outcomes and reason codes are unchanged):

| Metric | Meaning | Expected regime |
|---|---|---|
| `recompute_count` | dispatches served by recompute (miss or denied; the rebuild-cost denominator) | ≥ 1 per purge window |
| `invalidation_events` | full cache purges performed | 1 per applied revocation |
| `cache_entries_at_purge` | cached projections destroyed by purges (false-invalidation mass) | grows with lineage density |
| `cost.cache_hits` / `cost.cache_misses` | hit vs rebuild dispatches | hits collapse to 0 around each `t_r` |
| `cost.entries_destroyed_by_purges` | total projections dropped | ≥ `cache_entries_at_purge` contribution |
| `cost.peak_cache_size` | max cached projections held | bounded by pre-purge working set |
| `exposed_bytes_total` | authorized attribute-exposure bytes | parity with B2 on identical lineages |

**Guarantees vs cost:** zero leakage through cache with false-invalidation and rebuild
costs linear in the number of purges × working-set size. Against the candidate
(B4, transitive provenance-label invalidation) X05 bounds the *availability* cost of the
safety-first alternative: if X05's costs are negligible on the factorial lineage-density
grid, the trade-off claim dies and novelty narrows to an engineering trade-off
(blueprint falsification rule).

## 4. Execution contract in this repository

- The comparator is **executed through the real adapter**
  `evaluation/venue2027/popets/baselines.py::run_baseline("coarse-cache-purge-on-revocation", case, ctx) -> Outcome`
  (registry `fidelity: FAITHFUL_PORT`); X05 does **not** fork a second implementation.
- Deterministic: no hidden clock/randomness/network; the case-embedded `workload`
  (or the deterministic default workload) fully determines the run.
- Fails closed with stable reason codes (`REVOKED_CONTEXT`,
  `LINEAGE_SOURCE_MISSING`, `WORKLOAD_MALFORMED`, `CASE_MALFORMED`); dispatch records
  are never silently dropped.
- Parity: `parity_check("coarse-cache-purge-on-revocation")` reproduces the pinned
  fixture vector `evaluation/venue2027/popets/fixtures/coarse_purge_parity.json` exactly.
- Tests: `research/venue2027/popets/tests/test_x05_full_refresh.py` imports the real
  baseline, runs a revocation workload, asserts full-purge behavior (no leakage of
  revoked context, all cached projections purged), and records the real
  `recompute_count`.

## 5. Version

`X05_FULL_REFRESH_SPEC_VERSION = "1.0.0"`; implemented on top of
`POPETS_BASELINES_VERSION = "1.0.0"` with additive-only detail fields.
