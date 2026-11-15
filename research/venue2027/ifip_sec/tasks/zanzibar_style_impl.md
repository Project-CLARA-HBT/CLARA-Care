# IFIP_SEC-X06_zanzibar_style · Revision-aware authorization reference: directly callable consistency contract

> **Task:** `IFIP_SEC-X06_zanzibar_style` · **Phase:** `P03` · **Venue:** `ifip_sec` · **RQ:** `RQ1` (cost markers feed `RQ3`)
> **Paper:** *Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal Lineage*
> **Arm formalized here:** blueprint arm **B2** — "Zanzibar/OpenFGA with consistency token and
> fresh policy evaluation" (registry baseline `zanzibar-openfga`; literature matrix rows
> `zanzibar19` and `openfga`). It is the task contract
> **`check_with_revision(principal, resource, token) -> Verdict`** formalized as a **directly
> callable** consistency-aware authorization comparator over relation tuples and zookie-style
> consistency tokens.
> **Implementation:** `evaluation/venue2027/ifip_sec/consistency_token_adapter.py` (module
> version `CONSISTENCY_ADAPTER_VERSION = "1.0.0"`; wired additively into
> `evaluation/venue2027/ifip_sec/baselines.py` as arm `B2_INPROCESS_ZANZIBAR`, module version
> `1.0.0` → `1.1.0`), public operation `check_with_revision(...)` /
> `bind_consistency_checker(store)` and `ZanzibarStore.write/delete/issue_token/issue_token_at`.
> **Test driver:** `research/venue2027/ifip_sec/tests/test_x06_zanzibar_style.py`.
> **Status:** formalization + executable measurement on deterministic synthetic tuples only;
> no live workload, no PHI/PII, no network, no hidden clock, and no claim in this document is
> evidence of a real-system result.

---

## 1. Scope and role of the arm

This arm implements the X06 target contract from
`research/venue2027/VENUES/ifip_sec/TASKS/IFIP_SEC-X06_zanzibar_style.md`:

> **Exact target contract:** `check_with_revision(principal, resource, token) -> Verdict`.

It is the **strong relationship-consistency comparator** (blueprint arm B2), NOT the candidate
mechanism (delegated lineage transition verifier, arm B4) and NOT the pinned external
OpenFGA v1.22.1 server (registry row `B2_OPENFGA`, which stays `NOT_RUN_EXTERNAL` /
`BASELINE_UNAVAILABLE` per execution contract rule 8 — this in-process reference is never
substituted under that row's name). Its scientific role is to hold the consistency axis
constant while the candidate's replay-closure advantage is measured: the literature matrix
records that "a replayed receipt inside the stale-read window is still admitted consistently"
by Zanzibar-style semantics — this arm makes that boundary **executable and asserted**, not
argued.

- **Relation tuples** are an append-only changelog of
  `(object_id, relation, user)` writes and tombstone deletes, each stamped with a
  monotonically increasing per-store revision (the total tuple-change ordering of Zanzibar
  Sec. 2.3). Every successful `write`/`delete` advances the head revision by exactly one;
  a delete of a non-existent (or already tombstoned) tuple is a documented no-op that does
  NOT advance the revision, so change history is never fabricated.
- **Zookie-style consistency tokens** are HMAC-bound snapshot-version tokens
  `{v, store, revision, mac}` (base64url, canonical JSON): `issue_token()` captures the
  head revision (the `minimize_latency=false` strong-consistency option),
  `issue_token_at(revision)` captures an earlier committed revision (bounded-staleness
  read). A token claiming a revision the store never committed is refused both at issuance
  (`ConsistencyError TOKEN_REVISION_UNKNOWN`) and at verification
  (`REJECT TOKEN_REVISION_UNKNOWN`).
- **Relation-walk evaluation** expands namespace rewrite rules (`computed_userset`
  relation aliasing; `tuple_to_userset` hierarchy walks over visible `parent` tuples;
  a rule may be a single rewrite or a list = union of branches) over the tuple snapshot
  visible at the token revision, with union semantics
  (`PRESENT` > `REVOKED` > `ABSENT`) and a `(object, relation)` cycle guard plus a
  depth backstop.

## 2. Data model (as implemented; all objects JSON-serializable)

| Object | Fields | Meaning |
|---|---|---|
| `RelationTuple` | `object_id, relation, user, written_at, deleted_at` | one changelog tuple; `deleted_at=None` until tombstoned |
| `ZanzibarStore` | `store_id`, injected HMAC key (≥ 16 bytes), namespace, logical revision counter | single-process store; all I/O injected |
| Consistency token | `{v:1, store, revision, mac}` base64url | zookie v1: store id + snapshot revision, HMAC-SHA256 bound |
| `ConsistencyVerdict` | `allowed, reason_code, revision_evaluated, tuples_examined, nodes_visited, db_round_trips` | JSON-serializable decision + real evaluation counts |

Verdict reason-code vocabulary (stable uppercase, fail closed): `RELATION_PRESENT`,
`RELATION_ABSENT`, `RELATION_REVOKED` (decisions); `TOKEN_MISSING`, `TOKEN_UNPARSEABLE`,
`TOKEN_SIGNATURE_INVALID`, `TOKEN_STORE_MISMATCH`, `TOKEN_REVISION_UNKNOWN` (token faults →
REJECT verdicts, never exceptions miscounted as safe rejections). Caller wiring errors
(short key, non-string identifiers, malformed namespace rules, walk depth exceeded) raise
`ConsistencyError` — configuration faults, not decisions.

## 3. Consistency semantics: exact guarantee and declared staleness boundary

Let `R(t)` be the snapshot revision selected by token `t`, `head` the store's current
revision, and `visible(τ, R)` the predicate "tuple τ written at ≤ R and (tombstone absent
or tombstoned at > R)".

**Guarantee G1 (fresh / strong consistency — tested).** A token from `issue_token()` has
`R = head`; the check therefore sees every completed write in both directions:
- a relation **just granted** is `RELATION_PRESENT` (fresh-consistency read sees the
  just-granted relation — the required positive control), and
- a relation **just revoked** is `RELATION_REVOKED`: a replayed pre-revocation request
  presented with a **fresh** token is REJECTED.

**Boundary G2 (bounded staleness — tested, never hidden).** A token captured at revision
`R < head` evaluates the snapshot at exactly `R`: writes committed after `R` are invisible
in BOTH directions. Consequently a pre-revocation replay presented with a **pre-revocation**
token is ADMITTED (`RELATION_PRESENT`) inside the stale-read window — this is the published
Zanzibar bounded-staleness behaviour (the RQ1 measurement gap the candidate must beat) and
the task's required negative control, asserted as `allowed=True` on the stale token paired
with `allowed=False, reason_code=RELATION_REVOKED` on the fresh token for the identical
replay.

**No stronger claim is made.** Per the task falsification rule, if a properly scoped
Macaroon plus consistent authorization check is decision-equivalent on all attacks, this
arm's role is to *demonstrate* that equivalence, not to inflate B2. The arm carries no
purpose/consent-epoch vocabulary on tuples and no consume-once primitive — exactly the
documented Zanzibar limits (matrix row `zanzibar19`): consistency governs permission-tuple
evaluation only.

## 4. Cost model (RQ3 markers; real measured counts per verdict)

Every `check_with_revision` call records real evaluation counts in the verdict:
- `db_round_trips` — walk nodes evaluated (one simulated authorization-store read each),
  i.e. the authorization DB round trips a distributed deployment would pay;
- `tuples_examined` — candidate tuples scanned at the evaluated revision;
- `nodes_visited` — namespace rewrite nodes expanded (union branches and hierarchy hops);
- `zookie_bytes(token)` — serialized token size in bytes.

Unsupported constructs (marked honestly, per task step 1; NOT implemented here): distributed
changelog/index storage (the revision counter is single-process logical), `new_epoch`
per-user monotonic-read enforcement, userset user ids (`obj#relation` as user),
intersection/exclusion rewrite rules, lease-based consistency, and multi-tenant shard
routing. None of these are approximated or claimed.

## 5. Wiring and backwards compatibility

- `consistency_token_adapter.py` is NEW_PROPOSED as owned by the task; zero production
  secret/data access; pure functions over injected state (no hidden clock/randomness).
- `baselines.py` changes are purely additive: new import of the adapter symbols, new arm
  constant `BASELINE_B2_INPROCESS_ZANZIBAR = "B2_INPROCESS_ZANZIBAR"`, new registry
  `BaselineSpec` row (registry name `zanzibar-openfga`, `runnable_in_process=True`),
  thin case/ctx adapter `run_zanzibar_case` dispatched inside `run_baseline`, an `__all__`
  export list, and the docstring/version bump `1.0.0` → `1.1.0`. No pre-existing arm,
  registry row, reason code, or runner changed; `test_baselines.py` stays green (only the
  version-pin assertion widened to the documented additive range `("1.0.0", "1.1.0")`).
- Through the `run_baseline` path the arm consumes an injected `zanzibar_store`,
  `principal`, `resource`, `zookie` and optional `relation` from the case; a missing store
  or identity is a `BaselineError` wiring fault; a missing/invalid token is a first-class
  REJECT outcome.

## 6. Verification contract (`test_x06_zanzibar_style.py`)

The test module imports the **real** implementation
(`evaluation.venue2027.ifip_sec.baselines` re-exports of
`ZanzibarStore`/`check_with_revision`; no reimplementation, no monkeypatching of the
algorithm) and covers:

- **Fresh sees just-granted relation (G1 positive):** grant → `issue_token()` →
  `check_with_revision` returns `allowed=True / RELATION_PRESENT` at the grant revision
  with real counts (`db_round_trips ≥ 1`, `tuples_examined ≥ 1`).
- **Stale-consistency read does NOT see the just-granted relation (G2):** a token captured
  before the grant evaluates the earlier snapshot (`revision_evaluated < grant revision`)
  and returns `allowed=False / RELATION_ABSENT`.
- **Fresh rejects pre-revocation replay (G1 negative):** after `delete`, a fresh token
  yields `allowed=False / RELATION_REVOKED`; the identical pre-revocation request is
  **rejected only with the fresh consistency token** — the pre-revocation token, on the
  same store and replay, still returns `allowed=True` (the asserted staleness boundary).
- **Token-fault fail-closed:** missing, unparseable, tampered-MAC, wrong-store, and
  never-committed-revision tokens each produce REJECT verdicts with their stable codes
  (no exception miscounted as a safe rejection).
- **Relation-walk evaluation:** `computed_userset` (editor → viewer), `tuple_to_userset`
  hierarchy (folder.viewer → document.viewer), union of branches, cycle-safe self-parent.
- **Wiring via `run_baseline("B2_INPROCESS_ZANZIBAR", ...)`:** admit and reject paths
  through the baselines dispatcher; registry row present; external `B2_OPENFGA` row still
  `NOT_RUN_EXTERNAL`.
- **Real evaluation counts and determinism:** identical store/token reproduce byte-identical
  verdicts; `zookie_bytes` positive; counts strictly positive on real checks.

## 7. Evidence boundary

All counts asserted in the tests are computed from the executed adapter on deterministic
synthetic tuples inside the test run itself; this document pre-registers no observed value
beyond the structural invariants above. No latency/throughput number for real OpenFGA is
claimed here (that belongs to the pinned-binary arm `B2_OPENFGA`); token-size and
round-trip counts reported by this arm are its own measured outputs.
