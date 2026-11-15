# POPETS-X06_purpose_cache · Purpose-aware cache arm: directly callable fetch contract

> **Task:** `POPETS-X06_purpose_cache` · **Phase:** `P03` · **Venue:** `popets` · **RQ:** `RQ3`
> **Paper:** *Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts*
> **Arm formalized here:** `purpose-aware-cache-x06` (registry entry in
> `evaluation/venue2027/popets/baselines.py::BASELINE_REGISTRY`, fidelity `FAITHFUL_PORT`).
> It is the task contract `fetch(key, epoch, purpose) -> Context` formalized as a **directly
> callable** comparator arm with a real entry-level cache, per-entry cost accounting and an
> executable purpose-isolation violation detector. The sibling design reference
> `purpose-bound-cache-keying` (mechanism-isolation ablation, literature matrix row
> `blueprint-purpose-bound-cache-keying`) remains unchanged and keeps its own parity vector.
> **Implementation:** `evaluation/venue2027/popets/baselines.py` (module version
> `POPETS_BASELINES_VERSION = "1.1.0"`; the X06 arm is purely additive over 1.0.0), entry point
> `run_baseline("purpose-aware-cache-x06", case, ctx) -> Outcome`, public contract operation
> `purpose_cache_fetch(cache, key, purpose) -> (status, context, entry)`.
> **Test driver:** `research/venue2027/popets/tests/test_x06_purpose_cache.py`.
> **Status:** formalization + executable measurement on deterministic synthetic workloads only;
> no live workload, no PHI/PII, no network, no hidden clock, and no claim in this document is
> evidence of a real-system result.

---

## 1. Scope and role of the arm

This arm implements the X06 target contract from
`research/venue2027/VENUES/popets/TASKS/POPETS-X06_purpose_cache.md`:

> **Exact target contract:** `fetch(key, epoch, purpose) -> Context`.

It is **not the candidate mechanism** (candidate = transitive provenance-label invalidation
closure, blueprint arm B4) and **not** the keying-only ablation reference
(`purpose-bound-cache-keying`, unchanged). It is the task's own formalization of that keying
design as a directly callable arm so the purpose-isolation invariant and the real cache-entry /
recomputation counts can be asserted against executable cache state, not just derived keys:

- Cache lines are **typed entries** (`PurposeCacheEntry`) keyed by the 4-tuple
  `K = (subject, grant, purpose, consent_epoch)`, each storing the derived context, its source
  artifact ids and its creation instant.
- The public operation `purpose_cache_fetch(cache, key, purpose)` is the contract's `fetch`:
  a request whose purpose differs from `key[2]` is refused with `PURPOSE_MISMATCH` — a caller
  can never read an entry bound to a different purpose, independent of key collision.
- A revocation for `(subject, grant, purpose)` rotates the consent epoch **exactly once**
  (idempotent rotation per revocation event), so post-revocation dispatches for that scope miss
  and recompute; a repeat dispatch under the new epoch can HIT the entry recomputed after the
  rotation (recompute-on-mismatch semantics, not purge-on-mismatch).
- Per-dispatch records and the aggregate carry real measured accounting:
  `cache_entries_created`, `cache_entries_total`, `live_entries_current_epoch`, `cache_hits`,
  `cache_misses`, `recomputations`, `invalidation_events` (epoch rotations),
  `purpose_isolation_violations` (must remain 0), `exposed_bytes_total` — the RQ3 cost markers.

## 2. Data model (as implemented; all objects JSON-serializable)

Input: a `case.v1`-style mapping whose optional `workload` object carries the same synthetic
schema used by every implemented POPETS arm (shared `_parse_workload`, fail closed
`WORKLOAD_MALFORMED` on malformed input):

| Field | Type | Meaning |
|---|---|---|
| `source_snapshot` | `map<string,string>` | live authorized source records (artifact id → content) |
| `revocations` | `array<{subject, grant, purpose?, at_seconds}>` | revocation instants; `purpose` omitted = wildcard `*` |
| `dispatches` | non-empty `array<{dispatch_id, subject, grant, purpose, lineage[], at_seconds}>` | ordered dispatch schedule; `lineage` = candidate artifact ids |

Cache entry (`PurposeCacheEntry.to_dict()`): `subject`, `grant`, `purpose`, `consent_epoch`,
`context_bytes` (byte count only — the context string itself is never serialized into the
aggregated detail), `source_artifacts`, `created_at_seconds`.

`fetch` status vocabulary (stable uppercase reason codes, fail closed):
`HIT`, `CACHE_MISS`, `EPOCH_STALE`, `PURPOSE_MISMATCH`, `KEY_MALFORMED`.

## 3. State transition relation (per dispatch, in schedule order)

Let `E[(s,g,p)] ∈ ℕ` be the consent epoch (initially 0), `C` the entry store keyed by
`(s, g, p, E)`, and `d = (id, s, g, p, L, t)` a dispatch.

1. **Epoch rotation (idempotent).** If `t_r(s,g,p)` exists and `t ≥ t_r` and this scope has not
   yet observed that revocation, `E[(s,g,p)] ← E[(s,g,p)] + 1` and `invalidation_events + 1`.
   The rotation is scoped to the affected triple only (other purposes/grants keep serving) and
   happens once per revocation event — a second post-revocation dispatch targets the new epoch
   and can hit the recomputed entry (contrast with B1's whole-subject purge).
2. **Key derivation + contract fetch.** `K ← (s, g, p, E[(s,g,p)])`;
   `(status, context, entry) ← purpose_cache_fetch(C, K, p)`. The fetch refuses
   `PURPOSE_MISMATCH` when the requested purpose differs from `K[2]` — cross-purpose reuse is
   refused by the contract itself, before any hit is possible.
3. **Hit accounting.** `status = HIT` ⇒ `cache_hits + 1` and the entry's context is served.
4. **Miss / stale accounting.** Otherwise `cache_misses + 1`, `recomputations + 1`:
   - `CACHE_MISS`: recompute the context from the live snapshot (`missing` lineage ⇒ fail closed
     `LINEAGE_SOURCE_MISSING` — a cache must never invent content), install a new entry at
     `(s,g,p,E)`, `cache_entries_created + 1`.
   - `EPOCH_STALE`: the pre-rotation entry object still exists (kept for audit) but is not
     served and not overwritten; this dispatch recomputes without repopulating.
   - `PURPOSE_MISMATCH` / `KEY_MALFORMED` from the internal key construction is impossible by
     construction and fails the run hard (`ValueError`, never a silent safe rejection).
5. **Authorization (independent of the cache; fail closed).** REJECT `REVOKED_CONTEXT` if
   `t ≥ t_r(s,g,p)`; REJECT `LINEAGE_SOURCE_MISSING` if any artifact of `L` is absent from the
   live snapshot; else ADMIT. Authorization never reads `C`: the key space selects which cached
   projection *could* be served, but the dispatch decision is recomputed from live policy.
6. **Purpose-isolation invariant (executable).** For the entry actually served (if any):
   `entry.purpose == p` and `entry.consent_epoch == E[(s,g,p)]` must hold, else
   `purpose_isolation_violations + 1`. Per-dispatch records also carry
   `context_leaked_across_purposes` (must be `False` for every dispatch). Violations are
   counted, never silently repaired.

**Why the invariant holds structurally:** entries for different purposes live under different
keys (`p` is a key component) *and* the fetch refuses any request whose purpose differs from the
key's purpose component; entries from superseded epochs are unreachable because the epoch
component of the key moved. Isolation is therefore checked executably over real cache state, not
merely argued from key strings.

## 4. Isolation guarantee, declared limit, and cost model

**Guarantee (measured in the tests).** For a workload where the same context (same subject,
grant, lineage, schedule times) is requested under two different purposes:
- each purpose's first use misses and recomputes (no cross-purpose reuse of the identical
  cached lineage);
- the run creates **separate cache entries** — one per purpose key space
  (`cache_entries_created == 2` on the canonical fixture), `live_entries_current_epoch == 2`;
- a repeat dispatch under the same purpose hits **its own** entry (`cache_hits ≥ 1`,
  `recomputations == cache_misses`), never the other purpose's;
- `purpose_isolation_violations == 0` and no `context_leaked_across_purposes == True` record
  exists — the no-leakage assertion runs over every dispatch of every run.

**Limit (declared, not hidden).** Purpose/epoch keying isolates the key space but has no
reverse dependency edges: a transitively derived artifact (retry payload, fallback transport,
embedding pointer) whose key components are stable is not invalidated by keying alone. The X06
arm denies such dispatches only because per-dispatch authorization re-checks revocation
coverage; the arm must never be presented as revocation-complete by itself (that is the B4
closure's claim, tested against the keying-only ablation).

**Cost model (RQ3 markers, real measured counts per run).**
`cache_hits + cache_misses == dispatch_count` (every dispatch pays exactly one);
`recomputations == cache_misses`; `cache_entries_total ≥ cache_entries_created` counts superseded
epoch entries kept for audit; `live_entries_current_epoch` counts keys at each scope's current
epoch; `invalidation_events` counts epoch rotations (scoped, idempotent); `exposed_bytes_total`
counts admitted-artifact bytes (0 contribution from REJECTs); `distinct_purposes` records the
purpose fanout of the schedule.

**Backwards compatibility.** All changes to `baselines.py` are additive: three new private
functions + one public fetch helper + one dataclass, a new registry/implemented-baselines
entry, a new parity fixture, and a docstring/version bump (`1.0.0` → `1.1.0`). The three
pre-existing arms, their parity vectors, the `_aggregate` schema, and every pre-existing test
expectation are unchanged; `test_baselines.py` passes unmodified (37 passed).

## 5. Verification contract (`test_x06_purpose_cache.py`)

The test module imports the **real** arm
(`evaluation.venue2027.popets.baselines.run_baseline` / `purpose_cache_fetch`; no
reimplementation, no monkeypatching of the algorithm) and covers:

- **Positive:** the same context under two different purposes produces separate cache entries
  with real measured counts (`cache_entries_created == 2`, `live_entries_current_epoch == 2`,
  `cache_hits + cache_misses == dispatch_count`, same-purpose repeat is a genuine `HIT` served
  from that purpose's own entry).
- **Direct fetch contract:** `purpose_cache_fetch` returns `HIT` for the matching key/purpose;
  `PURPOSE_MISMATCH` when the requesting purpose differs from the key's purpose component
  (adversarial: cross-purpose read attempt refused); `CACHE_MISS` on an absent key;
  `EPOCH_STALE` when a superseded-epoch entry object is looked up under the old epoch;
  `KEY_MALFORMED` on a malformed key tuple.
- **Adversarial / isolation:** post-revocation dispatches under the revoked purpose miss
  (`EPOCH_STALE` on the first, `CACHE_MISS` + recompute after), get a fresh entry at the new
  epoch (`live_entries_current_epoch == 2`, superseded entry kept for audit:
  `cache_entries_total == 3`), recomputations equal misses, and the pre-revocation entry can
  never be served again; zero `purpose_isolation_violations` and zero
  `context_leaked_across_purposes` records across all runs; per-dispatch `cache_key` embeds the
  dispatch's own purpose and the counts assert no cross-purpose reuse (`cache_hits` only from
  same-purpose repeats).
- **Parity:** `parity_check("purpose-aware-cache-x06") is True` on the new fixture, and all four
  implemented baselines' parity vectors reproduce (`IMPLEMENTED_BASELINES` parametrized).
- **Fail-closed:** malformed workloads under the X06 arm return
  `EXECUTION_ERROR`/`WORKLOAD_MALFORMED`; determinism: the same case + ctx reproduce identical
  outcomes byte-for-byte.

## 6. Evidence boundary

All counts asserted in the tests are computed from the executed arm on synthetic deterministic
workloads inside the test run itself; this document pre-registers no observed value beyond the
structural invariants above. No claim of retroactive erasure of already-delivered content is
made anywhere; the arm's measurement concerns post-revocation *future* dispatches only.
