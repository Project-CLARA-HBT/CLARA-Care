# COMPSAC-X05_silo_occ — implementation spec: Silo-style entity read-set OCC comparator

**Task:** `COMPSAC-X05_silo_occ` · **Phase:** `P03` · **Venue:** `compsac` · **Priority:** `P1`
**Paper:** Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes (**RQ2**)
**Contract source:** `research/venue2027/VENUES/compsac/TASKS/COMPSAC-X05_silo_occ.md`
**Task manifest signature:** `execute_occ(op,store)->Outcome`
**Module:** `evaluation/venue2027/compsac/silo_readset_port.py` (`SILO_READSET_PORT_VERSION = "1.0.0"`)
**Executed engine (REAL, reused — never forked):** `evaluation/venue2027/compsac/baselines.py`
(`COMPSAC_BASELINES_VERSION = "1.0.0"`, registry arm `silo-style-entity-readset-occ`, blueprint arm B1,
registry `fidelity: FAITHFUL_PORT`)
**Status:** implemented, tests green, proof emitted — this document is the engineering record, not a
results claim. No number herein is a scientific finding; campaign numbers must derive from
`artifacts/venue2027/compsac/<run_id>/manifest.json` after protocol freeze.

---

## 1. Objective

Deliver the strong algorithmic comparator for RQ2 (blueprint arm B1): **Silo-style per-entity
read-set OCC with commit-time validation**. Each clinical write operation records the version of
every entity it read; at commit the fence re-validates every recorded version against the CURRENT
store and installs the writes with `version + 1` only if the whole fence holds. The comparator's
scientific role is the *declared-read-set* boundary: validation covers EXACTLY the reads the
workload declares, so an omitted cross-resource semantic dependency (write skew) sails through,
while the candidate (B4, dependency-complete scope-local OCC) closes that window by deriving the
required edges. The differential with real abort counts is asserted by
`research/venue2027/compsac/tests/test_x05_silo_occ.py`.

### Explicit disclosure (task contract, recorded verbatim in the module docstring, the registry and §3)

**The comparator is a faithful PORT of the published Silo algorithm — NOT Silo source code.**
Pinned algorithmic source: Tu et al., "Speedy Transactions in Multicore In-Memory Databases",
SOSP 2013, DOI 10.1145/2517349.2522713, Sec. 3–4 (commit-time per-entity read/write-intent
validation, epoch-based version checks, writes install `version + 1`). No official Silo release
exists to pin as upstream source; the in-project reference implementation is the already-verified
B1 engine in `evaluation/venue2027/compsac/baselines.py` (`FAITHFUL_PORT`), which this module
executes through its public `run_baseline` entry point. No OCC decision logic is re-implemented,
simulated or weakened here; EXECUTION_CONTRACT rule 8 (never replace an unavailable baseline by a
toy under the same name) is satisfied by reuse, not substitution.

## 2. Formal model

Fix a clinical write operation `op` and a store snapshot `S` (entity → record with integer
`version ≥ 0`, optional `value`, optional live `consent_epoch`/`policy_epoch` bindings).

**Declared read set** `R(op)` = `declared_reads`; **declared write set** `W(op)` =
`declared_writes`. **Observed versions** `V_obs: R(op) → ℕ` = `read_versions` (what `op` saw at
start). **Current versions** `V_cur: dom(S) → ℕ` = store versions at commit time.

**Commit fence** (evaluate in order; first failure aborts with a stable reason code):

1. `∀ e ∈ R(op): e ∈ dom(S)` else `ENTITY_UNKNOWN`;
2. `∀ e ∈ R(op): V_obs(e) = V_cur(e)` else `READSET_VERSION_STALE` — the operation is
   **INVALIDATED: its writes are never installed** (no partial install; the store is untouched);
3. epoch bindings on `R(op) ∪ W(op)`: `op.consent_epoch` = live consent epoch where bound, else
   `CONSENT_EPOCH_STALE`; `op.policy_epoch` = live policy epoch where bound, else
   `POLICY_EPOCH_STALE`;
4. commit: `∀ e ∈ W(op): S[e] := {version: V_cur(e) + 1, value: write_values(e)}`.

**Guarantee (what a COMMIT certifies).** A committed `op`'s entire DECLARED read set was never
mutated between observation and commit by any already-committed concurrent operation: the declared
read fence held at commit. Under an independently labeled schedule in which every semantic
dependency of every operation appears in its declared read set, the protocol admits no
non-serializable interleaving over those reads (Silo's commit-time validation property, ported).

**Guarantee boundary (the scientific gap under study).** Validation covers exactly `R(op)`.
Entities absent from `R(op)` — including semantically REQUIRED dependencies the workload fails to
declare (the frozen operation schema's required edges: a `medication_prescribe` must read the
CURRENT `allergy_list`; an `allergy_update` must read the CURRENT `medication_order`) — are outside
the fence. Two concurrent operations whose declared read sets are disjoint from each other's write
sets BOTH commit even though each mutates an entity the other required: **omitted-dependency write
skew is ADMITTED by design**. B4 derives the required edges and rejects the second commit
(`REQUIRED_READ_EDGE_STALE` / `WRITE_EDGE_SUPERSEDED`). Neither arm produces forbidden commits;
the contrast is abort behavior on identical schedules (RQ1/RQ2).

**States and codes.** `COMMIT/OK`, `ABORT/{READSET_VERSION_STALE, ENTITY_UNKNOWN,
CONSENT_EPOCH_STALE, POLICY_EPOCH_STALE}` (engine codes, passed through), and fail-closed input
errors returned as `EXECUTION_ERROR` outcomes — `OP_MALFORMED`, `STORE_MALFORMED` (adapter) and
`SCHEDULE_MALFORMED` (engine) — never silently counted as safe rejections or successes.

**Typed objects.** `SiloOperation` — frozen dataclass (`tx_id`, `declared_reads`,
`declared_writes`, `read_versions`, `write_values`, `operation_type`, `consent_epoch`,
`policy_epoch`) with `to_dict()` producing the engine's JSON-serializable transaction mapping.
Unknown op keys are refused (`OP_MALFORMED`), never silently dropped. No hidden clock, randomness,
network or provider access: the snapshot fully determines the run.

## 3. Faithful-port mapping (published algorithm → B1 engine → this adapter)

| Silo (Tu et al. 2013, Sec. 3–4) | B1 engine (`baselines.py::_run_entity_readset_occ`) | X05 adapter (`silo_readset_port.py`) |
|---|---|---|
| transaction reads records, remembers `(record, version)` | `read_versions` / start-of-schedule observation | `op["read_versions"]` (explicit observed versions) |
| commit-time per-record validation fence | loop over validated reads, `READSET_VERSION_STALE` on divergence | step 2 above, unchanged |
| failed validation ⇒ transaction aborts, writes discarded | `ABORT` record, no install | pass-through (single-op schedule) |
| epoch/version bound checks at commit | `_tx_epoch_ok` consent/policy epochs | pass-through |
| writes install `version + 1` | `VersionedStore.install` | pass-through |
| validates reads + write intents of the transaction | declared read set only (no derived closure) | declared read set only |

The adapter adds only input normalization (`SiloOperation`/mapping coercion, store validation,
epoch-binding extraction from store records) and the single-transaction schedule envelope. It
reuses `REQUIRED_DEPENDENCIES`' *absence* from B1 deliberately: B1 must not derive closure — that
is the candidate's mechanism (B4), and adding it here would erase the scientific contrast.

## 4. Positive and adversarial vectors (defined before implementation)

Positive: **X05-P1** valid committed operation installs `version + 1` with `COMMIT/OK` (determined,
reproducible, JSON-serializable detail). **X05-P2** stale observed version (concurrent committed
write) aborts with `READSET_VERSION_STALE` and leaves the store untouched (writes invalidated).
**X05-P3** unknown read entity aborts with `ENTITY_UNKNOWN`. **X05-P4** stale consent/policy epoch
aborts with the epoch-specific code.

Adversarial: **X05-A1** the omitted-dependency write-skew schedule — both operations commit under
B1 (real abort counts recorded: `aborted_b1 = 0`) while B4 aborts the second (`aborted_b4 ≥ 1`)
on the same case and config. **X05-A2** explicit `read_versions` override as a tamper surface
(claiming an older version) is caught by the fence. **X05-A3** wiring errors (`OP_MALFORMED`,
`STORE_MALFORMED`) fail closed as `EXECUTION_ERROR`, never as aborts. **X05-A4** epoch/ABA cycle:
observed version equals current version but the epoch binding moved ⇒ abort (version equality
alone does not admit). **X05-A5** determinism: identical inputs ⇒ byte-identical outcomes.

## 5. Test and evidence contract

`research/venue2027/compsac/tests/test_x05_silo_occ.py` imports the REAL B1 baseline
(`evaluation.venue2027.compsac.baselines`, plus the `execute_occ` adapter) — never a stub — and:

- runs a read-set/commit schedule against `execute_occ`;
- asserts commit-time read-set version validation works: a stale read set aborts
  (`READSET_VERSION_STALE`) and the aborted operation's writes are NOT installed;
- asserts the write-skew differential: B1 ADMITS the omitted-dependency write skew that B4
  REJECTS (same case, same config; real `aborted` counts asserted from `run_baseline` detail);
- records real abort counts in assertions (no manufactured numbers).

`evaluation/venue2027/compsac/test_baselines.py` (25 pre-existing tests) must stay green: the
adapter is additive-only — no symbol in `baselines.py` is renamed, removed or re-typed.
Artifacts: this spec + test module + proof report
`research/venue2027/proof/COMPSAC-X05_silo_occ.json` (emitted via
`agent_protocol.build_report`, validated `ok: true`); the task manifest's
`artifacts/venue2027/compsac/<run_id>/silo_occ.json` belongs to the campaign runner
(`COMPSAC-runner`), not to this per-task commit.

## 6. What was changed

| File | Change | Backwards compatibility |
|---|---|---|
| `evaluation/venue2027/compsac/silo_readset_port.py` | NEW: `execute_occ(op, store) -> Outcome` adapter over the real B1 engine; `SiloOperation`, `PORT_DISCLOSURE`, fail-closed coercion | Additive-only; `baselines.py` untouched |
| `research/venue2027/compsac/tests/test_x05_silo_occ.py` | NEW: positive + adversarial vectors above | No shared fixture mutated |
| `research/venue2027/compsac/tasks/silo_occ_impl.md` | NEW: this spec | — |

No production path, secret or patient data touched; synthetic fixtures only; no hidden
clock/randomness/network; injected I/O only (a plain mapping store).
