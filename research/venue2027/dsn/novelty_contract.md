# DSN 2027 · Novelty Contract (DSN-scope, phase P01)

> **Task:** `DSN-scope` · **Venue:** `dsn` · **Phase:** `P01` · **Contract version:** `1.0.0`
>
> **Status:** Prospective research design. This is a *design artifact*: it contains no experimental
> results, no measured numbers, and no claims about outcomes that have not yet been produced.
> Dependencies satisfied: `SH-claim_overlap` PASS, `SH-literature_hardening` PASS
> (proof reports under `research/venue2027/proof/`).
> Base SHA of this worktree: `7ebdbbf0740e87ffebe3538d6893a53eaccf2216`.

## 1. Paper title and target reader

**Paper title:** *Recoverable Safety Journals for Crash-Consistent AI-Mediated Health-State Mutations*

**Target reader:** Distributed-systems researchers and practitioners at DSN who design and operate
durable transactional storage, workflow engines, transactional-outbox infrastructure, and
fault-injection/oracle tooling (the Jepsen/Elle community), plus health-informatics platform
engineers who must persist AI-mediated clinical proposals, immutable decision lineage, and
asynchronous side-effect records without losing or duplicating an externally visible effect.
The paper is written for readers who will demand a real counterexample against a carefully
engineered outbox baseline before accepting a new mechanism.

## 2. Claim-to-prior-work falsification matrix

Citation IDs (`elle20`, `silo13`, `zanzibar19`, `ct9162`, `macaroons14`, `fhir5`) are drawn from
`research/venue2027/MANIFESTS/literature_registry.json`; registry study IDs
(`govred-rivf-2026`, `assurance-soict-2026`, `glhs-journal`, `fmc-2026`,
`bigdata-healthcare-2026`, `bigdata-ml-2026`, `careguard-vn`) are drawn from
`research/publication_registry.yaml`. The nine-study firewall alignment uses
`research/venue2027/_shared/publication_overlap_registry.yaml` (study `dsn`).

| Claim | Strongest competing explanation | Published prior work (real ids) | Why the claim survives | What WOULD falsify it |
|---|---|---|---|---|
| C1. Recoverability is a safety property of the *joint* clinical row, immutable decision receipt/lineage, and asynchronous side-effect record — not of a single database commit. | WAL + transactional outbox already guarantee crash-safe, exactly-once-forwarded writes at the database boundary; any residual disagreement is dismissed as application-level misuse of a solved primitive. | `elle20` (Elle/Jepsen, OSDI 2020 — black-box history checking covers transaction isolation, not AI decision-lineage receipts); `silo13` (SOSP 2013 — serializable CC inside one store, no cross-store joint-outcome semantics); `ct9162` (RFC 9162 — append-only integrity of a log, not reconciliation of three independent persistence boundaries); `glhs-journal` (co-versioned disclosure-to-commit governance; endpoint is commit correctness, not post-crash joint recoverability). | None of the cited works defines, measures, or checks a joint COMMITTED/REJECTED/INDETERMINATE outcome spanning row + receipt + side-effect record with an explicit INDETERMINATE terminal discipline. The claim is stated as a testable hypothesis with a designated adversarial experiment (RQ1), not as established fact. | A peer-reviewed system is shown to already specify and enforce the three-way joint outcome with INDETERMINATE semantics under crash windows and duplicate delivery; or the RQ1 search over 48 crash windows × 4 orderings × 3 schedules × 5 seeds (post-dedup) finds zero disagreements for B1, collapsing C1 to an application note. |
| C2. A reconciliation safety journal (versioned decision receipt checked against committed row, independent outbox receipt, and consent epoch) yields fewer joint-inconsistency outcomes than carefully engineered baselines, without unbounded ambiguity. | The observed disagreements are artifacts of a weak baseline: a fully correct B1 (PostgreSQL atomic write + transactional outbox + idempotent consumer) or B2 (durable workflow/saga with stable operation IDs) achieves identical invariants, so the journal adds only overhead. | B1 semantics per `elle20` oracle discipline and classic transactional-outbox practice; B2 per durable-execution/saga literature; authorization-side consistency context from `zanzibar19` (USENIX ATC 2019) and `macaroons14` (NDSS 2014) for caveat/epoch binding. | This claim is *conditionally* asserted: it is exactly what RQ1–RQ3 are designed to test, with B1 declared a mandatory full implementation (not a stub) under equal budget and pinned engine versions, and `NOT_RUN_EXTERNAL` status forbidding comparative claims when a baseline cannot run. | B1 (or B2) passes the Elle-compatible oracle with the same violation counts and equal/better RTO p99 and fsync cost — this is the pre-registered falsification rule; the superiority claim must then be discarded. |
| C3. An explicit INDETERMINATE outcome label — never promoted to a positive outcome while evidence is invalid or ambiguous — is necessary for safe user-visible behavior and auditable retry under consent revocation. | Retry-to-consistency arguments (idempotent consumer + dedup on operation ID) make the tri-state label unnecessary; an operator can just re-run reconciliation until the state settles. | `fhir5` (HL7 FHIR R5 — provenance/consent resource structure only, no crash-window outcome semantics); `ct9162` (log integrity without reconciliation semantics); `zanzibar19` (consistency-aware authorization checks, but not a durable joint-outcome label). | The tri-state label is defined as part of the recoverable-outcome function with a reconciliation *fraction* endpoint (eventual safe reconciliation) and a falsifiable competing hypothesis; it is a design claim under test, not a novelty assertion about existing engines. | A baseline exposing only COMMITTED/REJECTED is shown to satisfy the same idempotence/causal-order/invariant criteria under RQ2's at-least-once replay + concurrent revocation schedule, with no increase in phantom user-visible success or duplicate side effects. |
| C4. The study's evidence is independent of prior CLARA publications (no salami slicing). | The nine 2027 studies share one repository and background methods, so the DSN study could be dismissed as repackaged GLHS R4 / GovRed / GovMut evidence. | `govred-rivf-2026`, `assurance-soict-2026`, `glhs-journal`, `fmc-2026` (all registry-tagged `same-frozen-evidence` where extension is required); overlap registry study `dsn` declares endpoint `crash-consistency violation rate after fault injection` on `synthetic-dsn-2027` with `reuses_archive: []`. | Distinct endpoint (joint crash-window recoverability vs GLHS R4's governed disclosure-to-commit correctness vs COMPSAC's forbidden-commit rate under benign contention), independently frozen fault-injection design, and an explicit refusal to reuse frozen E15–E22 results as new evidence (Section 5). | Any dependency of a DSN claim on frozen E15–E22 numbers, GovRed schedules, or GovMut mutant scores would immediately falsify C4 and force reclassification as a joint/transfer manuscript. |

## 3. Research questions (exactly three, frozen for P01)

| RQ | Question (verbatim from blueprint) | Primary endpoint | Strongest competing baseline (blueprint arm) | Independent oracle | Statistical test | Falsification condition |
|---|---|---|---|---|---|---|
| RQ1 | Across crash cut points, are there executions where the clinical state, decision receipt, and outbox state disagree after bounded recovery? | Joint-inconsistency rate: orphan clinical writes / phantom user-visible success / unresolved outcomes per independent crash history (primary metric: orphan clinical writes per independent history). | **B1** — PostgreSQL atomic write + transactional outbox + idempotent consumer (strong practical baseline; must be implemented fully; B0 is only a weak control). | Jepsen/Elle-compatible history export (`elle20`) plus a deterministic SQL-state audit of the real PostgreSQL backend; anomaly witnesses manually reviewed by a reviewer who cannot reuse candidate code. | Exact two-sided test on paired binary joint-inconsistency outcomes across matched histories (McNemar test on discordant pairs), with case-clustered bootstrap CIs; risk-difference bounds reported for rare events. | Zero RQ1 events for B1 across the deduplicated 48×4×3×5 design with upper CI below the pre-registered minimum effect → C1/C2 discarded; study downgraded to an application paper. |
| RQ2 | Under at-least-once replay and concurrent consent revocation, does recovery preserve idempotence, causal order, and correct INDETERMINATE labels? | Duplicate externally visible side effects and causal-order violations per independent crash/revocation history, plus incorrect-INDETERMINATE-label rate. | **B2** — durable workflow/saga with compensation and stable operation IDs (strong operational baseline; engine and version pinned and recorded). | Same Elle-compatible oracle plus replay-specific invariant checkers (idempotence dedup ledger audit) run independently of the candidate implementation. | Paired-rate comparison of duplicate/causal-order violations per history under matched schedules (Wilcoxon signed-rank on paired per-history counts), with multiplicity control across the three RQ families. | B2 achieves zero duplicate effects, zero causal-order violations, and correct indeterminate handling at equal revocation-interleaving coverage → C3's necessity claim discarded. |
| RQ3 | What is the added durable-write, p99 latency and recovery-time cost compared with transactional outbox and durable workflow baselines? | Cost deltas: extra fsyncs per operation, RTO p50/p95/p99, and operation p99 latency at matched throughput, worker settings 1/2/4/8. | **B1** for durable-write/fsync and latency cost; **B2** for recovery-time cost (both arms run under equal budget and pinned versions). | Independent timing harness reading monotonic clocks and database fsync/replay counters; harness code excludes all candidate modules; benchmark protocol frozen before confirmatory runs. | Paired bootstrap over matched workload repetitions for p99/RTO contrasts, reporting CI's relative to pre-registered indifference margin derived from pilot variance (power computed post-pilot, not asserted from N). | A B1 (or B2) configuration attains the same invariants with equal or better recovery cost → per the pre-registered rule, the new-mechanism-superiority claim is discarded and negative equivalence is reported instead. |

RQ endpoints, contrasts, and minimum effects are frozen at protocol freeze (task `DSN-rq_registry`).
The confirmatory holdout stays inaccessible until that freeze. Baseline arms of the study, from
the blueprint's strong-baseline table: **B0** — DB transaction only + fire-and-forget side
effect (weak control); **B1** — PostgreSQL atomic write + transactional outbox + idempotent
consumer (strong practical baseline); **B2** — durable workflow/saga with compensation and
stable operation IDs (strong operational baseline); **B3** — proposed reconciliation safety
journal (candidate; no pre-existing performance assumed).

## 4. Scope statement and truly distinct endpoint

**Scope paragraph:** This study asks whether an explicitly journaled reconciliation layer can make
the *joint* outcome of a clinical row, an immutable AI-decision receipt, and an asynchronous
side-effect record recoverable and honest across crash windows, at-least-once duplicate delivery,
and concurrent consent revocation — and at what durable-write, latency, and recovery-time cost.
**The truly distinct endpoint versus historical GLHS R4** is: GLHS R4 measured governed
disclosure-to-proposal-to-commit *correctness under concurrency on a single database boundary*
(primary endpoint `governed_read_to_proposal_to_write_correctness`, registry id `glhs-journal`;
its historical E15–E19 backend attestation is `sqlite:///:memory:` and therefore cannot support
PostgreSQL crash-recovery claims), whereas this study measures **crash-window joint
recoverability — the crash-consistency violation rate after fault injection across three
independent persistence boundaries (row, receipt, side-effect record) on a real PostgreSQL
backend, including duplicate-delivery and consent-revocation interleavings and an explicit
INDETERMINATE terminal state**. Versus the other eight 2027 venues: COMPSAC measures
false-stale rejection and forbidden-commit rate under benign contention (no crash cut points,
no recovery), IFIP SEC measures cross-context replay admission of authorization receipts (a
verification-time prevention property, not a post-crash storage reconciliation property),
PoPETs measures post-revocation future-disclosure of cached AI context, PST measures forensic
reconstructability under audit minimization, ACNS is a bibliographic SoK of attestation evidence,
AIME measures clinical workflow task validity under changing consent/medication history,
SACMAT measures cross-engine temporal policy conformance, and DIMVA measures detection of
authorization-boundary probing campaigns — none of which scores orphaned durable effects,
phantom user-visible success, duplicate side effects, or RTO after crash injection.

## 5. Non-overlap declaration: shared context vs new independent evidence

**Shared context (background, cited, never counted as new evidence):**

- Repository infrastructure, GLHS append-only listener design, and background methods from
  `services/api/src/clara_api/glhs` — engineering substrate only.
- Parent GLHS E15–E22 results and the accepted HEALTHINF paper — **background and motivation
  only, per the blueprint's evidence contract.**
- Registry manuscripts `govred-rivf-2026`, `assurance-soict-2026`, `glhs-journal`,
  `fmc-2026`, `bigdata-healthcare-2026`, `bigdata-ml-2026`, `careguard-vn` — cited related work.
- The nine-study firewall artifacts: `publication_overlap_registry.yaml` (study `dsn`,
  endpoint `crash-consistency violation rate after fault injection`, dataset
  `synthetic-dsn-2027`, `reuses_archive: []`) and `study_claims.json`.

**New independent evidence to be produced by this study (none of it exists yet):**

- The fault-injection design: 48 crash windows × 4 commit/revocation orderings ×
  3 delivery schedules × 5 independent seeds (final N confirmed only after schedule
  deduplication), worker settings 1/2/4/8.
- Freshly generated `synthetic-dsn-2027` histories and their Elle-compatible exports.
- New B0/B1/B2 reference implementations with pinned versions, fidelity review, license review,
  and equal budget; `NOT_RUN_EXTERNAL` recorded transparently where a baseline cannot run.
- The recoverable-outcome function and reconciliation safety journal candidate (B3).

**Explicit refusal:** The frozen E15–E22 results are **not reused as new evidence** in any DSN
claim, table, figure, or statistical test. They may be cited as historical background with their
`sqlite:///:memory:` backend limitation stated. Any DSN result must derive mechanically from
`artifacts/venue2027/dsn/<run_id>/manifest.json` produced by this study's own runs. Per the
anti-salami gate, frozen E15–E22 data, GovRed results, and GovMut results cannot be counted as
any of the nine independent 2027 results.

## 6. Go/no-go decision

**Decision: GO** — conditional on the pre-registered falsification rules. The novelty gap is real
and testable (no cited prior work defines the joint tri-state recoverable outcome across row +
decision receipt + side-effect record under crash windows, duplicate delivery, and consent
revocation), the oracle (Jepsen/Elle-compatible export + deterministic SQL-state audit) is
independent of the candidate, and the strongest competing baseline B1 is declared a mandatory
full implementation, so a negative equivalence result remains a publishable, honest outcome.
The GO is withdrawn (→ NO-GO, venue transfer or joint-manuscript reclassification) if: (a) the
P02 prior-art audit (`DSN-prior`) surfaces a peer-reviewed system already enforcing the joint
tri-state semantics; (b) B1/B2 cannot be implemented faithfully with pinned real upstream sources
and equal budget; or (c) resource/deadline checks fail the `CLARA_2027_V3_EXECUTION_HANDBOOK`
gate for this venue.
