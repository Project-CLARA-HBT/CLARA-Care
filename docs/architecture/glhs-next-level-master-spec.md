# GLHS Next-Level Master Specification

Status: **implementation-driving specification; no superiority claim**  
Scope: synthetic software evaluation until an independently adjudicated external
clinical protocol exists.  This document supersedes neither frozen V21 evidence
nor the external-data program; it consolidates their next engineering steps.

## 1. Evidence-grounded current state

| Capability | Current implementation evidence | Current verification | Remaining evidence gap |
| --- | --- | --- | --- |
| Canonical evidence and state | `GlhsEvidence`, `GlhsAssertion`, `GlhsTransition`, `GlhsStateVersion`; gateway-owned writes | API GLHS gateway/commitment tests | Database-level append-only prevention and PostgreSQL race/fault evidence |
| Bitemporal reconstruction | `reconstruct_state()` and `reconstruct_commitments()` filter valid and knowledge coordinates from transition ledgers | late-arrival and production-context regression tests | long-history/index scaling and malformed temporal interval recovery |
| Provenance and conflicts | assertion-evidence links, relations, persistent conflict rows and conflict IDs in manifests | gateway/BTSA/production-context tests | explicit unresolved-conflict selection semantics across domains |
| Governed disclosure | `compile_thss()` and `compile_commitment_thss()` materialize a signed, expiring manifest | manifest revalidation and strict-context tests | one executable ordering invariant shared by every THSS compiler |
| Read/write binding | proposal carries base version, snapshot ID/digest; commit revalidates scope, expiry, policy, consent and disclosed evidence after profile lock | commitment gateway tests | fault-injection and PostgreSQL concurrency proof |
| Derivative isolation | benchmark contexts are derivative and model proposals cannot directly commit | production context and proposal tests | static/write-path audit for cache/vector/model-output consumers |
| LLM benchmark | production strict context, sealed V21 development, global limit five, retry/error ledger | V21 validation/checksum; V22 explicitly incomplete | multi-family current-run development/validation and untouched final |
| Comparator fidelity | BTSA mechanism mapping, local baselines, pinned GraphRAG upstream contract | comparator tests; GraphRAG upstream CLI dry validation | executable GraphRAG needs a compatible embedding endpoint; paper reproductions remain unavailable otherwise |

The historical audit at `glhs-contract-baseline-audit.md` is informative but
partly stale: the current gateway now checks actor, consent basis, assertion
hashes and manifest digest during snapshot-bound commitment revalidation. It
must not be used as proof that these current gaps still exist.

## 2. Architectural invariants

All production changes must preserve these invariants.  Every invariant needs a
unit/integration test and a structural benchmark case before it can support an
empirical claim.

1. **Canonical-only truth.** Evidence pointers, assertion/transition ledgers
   and commitment versions are canonical; vector indexes, caches, prompts and
   model outputs are rebuildable derivatives.
2. **Append-only reconstruction.** A past state is reconstructed from immutable
   transition/version facts at `(valid_at, known_at)`, never from a mutable
   current projection alone.
3. **Provenance closure.** An active assertion or commitment transition carries
   source evidence; a manifest contains IDs and canonical hashes of disclosed
   assertions and provenance.
4. **Ordered THSS.** Every compiler applies and records, in this order:
   Authorization → temporal/lifecycle visibility → conflict treatment →
   relevance/freshness → minimization.  Later stages cannot reintroduce an
   excluded fact.
5. **Snapshot-bound model work.** A model-origin proposal references exact
   manifest ID/digest and base state version. Commit revalidates actor, purpose,
   policy, consent, expiry, digest and evidence subset after acquiring the
   profile-state lock.
6. **Fail closed.** Missing/tampered/expired/replayed/cross-profile manifests,
   stale versions, policy/consent drift and non-disclosed evidence reject before
   persistent transition.
7. **Serializable state advance.** Exactly one writer advances a profile state
   version; idempotent duplicate requests resolve deterministically.
8. **No benchmark branch.** Production code cannot inspect benchmark ID, split,
   seed, template family, gold state or scorer output.

## 3. Threat model and required controls

| Threat | Required control | Proof artifact |
| --- | --- | --- |
| Direct canonical mutation | database guard plus ORM/service guard | mutation-negative integration test on PostgreSQL |
| Snapshot substitution/tamper | canonical payload + envelope digest and live manifest lookup | tamper matrix / signed replay test |
| Stale or replayed model proposal | profile lock, idempotency request digest, post-lock revalidation | two-writer and replay test |
| Policy/consent change after read | re-resolve at commit, reject mismatch | policy/consent-drift test |
| Conflict collapse | retain pair and explicit resolution transition | unresolved-conflict reconstruction test |
| Over-redaction | required-fact coverage prior to minimization | disclosure utility/safety paired test |
| Context injection / unsupported assertion | evidence-only packet construction and schema validation | adversarial packet / unsupported-assertion metric |
| Derived-store authority leak | no writeback path from retrieval/cache/model to canonical tables | static path audit + integration test |
| Benchmark gaming | split firewall, freeze hashes, no final-label access, comparator cards | validator and source scan |

## 4. Comparator and fairness policy

Comparable arms use identical subject, task/question, visible source evidence,
model, decoding, response schema, score, timeout and stated context budget.
They must differ only in a real state/context mechanism.

| Arm | Fidelity | Eligibility |
| --- | --- | --- |
| GLHS + strict THSS | production API-owned GST/THSS path | primary system |
| GLHS ablations | production contexts with a single named mechanism removed | ablation only |
| Full authorized history | same visible source, no task minimization | strong disclosure comparator |
| Temporal BM25 | deterministic retrieval only, fixed top five | V7+ only; not a paper reproduction |
| BTSA | documented mechanism mapping | secondary; never claim faithful paper reproduction |
| LWW / naive RAG | fixed local baselines | secondary only |
| Microsoft GraphRAG | pinned upstream CLI, source and execution contract | only after completion + embedding probes + index/query ledger |

GraphRAG is an appropriate external retrieval comparator because its official
pipeline builds a graph knowledge model from text units, entities,
relationships, communities and reports; it must not be replaced by a local
heuristic. [Microsoft GraphRAG architecture](https://github.com/microsoft/graphrag/blob/main/docs/index/architecture.md)
and [CLI](https://microsoft.github.io/graphrag/cli/) define that execution
surface.  MedRAG/MIRAGE evaluates external-corpus medical QA, not governed
longitudinal state reconciliation, so it is task-mismatched rather than a
drop-in comparator. [MIRAGE](https://github.com/Teddy-XiongGZ/MIRAGE) and
[MedRAG](https://github.com/teddy-xionggz/medrag) document that scope.

## 5. Measurement and acceptance gates

Track by unique subject, model, condition, domain, history length, temporal
stratum and attack family:

- all-axes state accuracy; temporal/knowledge-time and conflict accuracy;
- critical omission, unsupported assertion, prohibited disclosure and
  authorized fact recall;
- stale-write acceptance (must be zero where required), legitimate rejection,
  replay/idempotency and attack success;
- disclosed bytes/tokens, p50/p95 latency, throughput, storage and governance
  overhead; terminal provider failures remain failures;
- paired subject-clustered risk difference/ratio, confidence interval, paired
  test and Holm correction for predeclared comparisons.

An improvement enters the candidate only when: its stated development failure
improves; invariant tests pass; no safety invariant regresses; no material
validation regression occurs; and the code has no benchmark-specific branch.

No final run is permitted until a candidate freeze contains implementation SHA,
locks/container digest, cohort/splits, builders, policies, prompts, schemas,
models, decoding, scorers, statistic code, comparator cards and all generated
input hashes. Final is run exactly once on the untouched final partition.

## 6. Prioritized implementation roadmap

| ID | Mechanism | Production change | Required proof |
| --- | --- | --- | --- |
| NL-01 | Canonical immutability | database-level UPDATE/DELETE guards for GLHS ledger/manifest rows, with narrow migration/admin exception policy | PostgreSQL direct SQL mutation rejection and replay preservation |
| NL-02 | THSS stage contract | shared ordered stage-trace validator for generic and commitment THSS | permutation/reintroduction negative tests |
| NL-03 | Temporal/conflict state | deterministic equal-time tie policy, interval boundary and unresolved-conflict representation | boundary/late-source/conflict regression suite |
| NL-04 | Proposal provenance | structured immutable model inference manifest FK/digest binding, not opaque text only | model-proposal tamper/replay tests |
| NL-05 | Production concurrency/fault | profile lock, transaction crash and outbox recovery under PostgreSQL | two-writer, injected-fault, recovery tests |
| NL-06 | Retrieval/context | task-aware temporal BM25 plus bounded provenance compression; no canonical writeback | context budget/retention/safety ablation |
| NL-07 | Performance | index/query plan and workload harness over history lengths | storage/latency/throughput artifact |
| NL-08 | Benchmark V7 | new subject-disjoint exploratory freeze with temporal-BM25; separate Gemini-only exploratory label if necessary | frozen validator, complete error ledger and failure analysis |

Implementation order is NL-02, NL-03, NL-05, NL-01, NL-04, NL-06, NL-07,
NL-08.  It deliberately starts with invariants and deterministic local evidence,
not provider calls.
