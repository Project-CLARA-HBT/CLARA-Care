# SACMAT 2027 · Novelty Contract — SACMAT-scope (Phase P01)

> **Task:** `SACMAT-scope` · **Venue:** `sacmat` · **Phase:** `P01` · **Status:** signed scope register
> **Paper:** PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines
> **Contract signature:** `design_scope() -> NoveltyRegister` (typed register assembled by this document; downstream consumers: `SACMAT-rq_registry`, `SACMAT-threat`, `SACMAT-prior`, `SACMAT-overlap`)
> **Evidence status:** PROSPECTIVE / NOT RUN. This document is a scientific scoping contract. It contains no
> experimental results; all numbers cited from prior work are either registry identifiers or declared plans.
> **Input dependencies (verified present at base SHA `7ebdbbf0740e87ffebe3538d6893a53eaccf2216`):**
> `research/venue2027/_shared/publication_overlap_registry.yaml` (SH-claim_overlap PASS),
> `research/venue2027/_shared/literature_validity_ledger.csv` (SH-literature_hardening PASS),
> `research/publication_registry.yaml`, `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`,
> `research/venue2027/CONTEXT/PREVIOUS_RQ_REGISTER.md`, `research/venue2027/GATES/ANTI_SALAMI_REVIEW.md`.

## 0. Title and target reader

**Title.** PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous Policy Engines.

**Target reader.** Primary: SACMAT attendees who build or operate authorization policy engines and policy
tooling (Cedar/OpenFGA/OPA/XACML maintainers, policy-engine testing researchers, security-tooling
reviewers). Secondary: health-AI platform engineers who must show that delegated consent and
purpose-bound access behave identically across engine versions and engines, and compliance reviewers who
need portable evidence rather than engine-specific unit tests. Not the target reader: clinical staff,
ML benchmark readers, or database-concurrency researchers.

**One-paragraph scope.** PolicyTrace defines a *history-sensitive conformance property* for delegated
consent and purpose-bound access: two policy engines that agree on isolated single requests may still
disagree once grant→revoke→regrant, delegation expiry, purpose narrowing and replay are ordered in a
history. The study builds a portable four-valued decision oracle
(PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE), a deterministic trace-level metamorphic test generator, and
adapters that replay the same history into Cedar, OpenFGA and OPA; conformance failures are adjudicated
by the executable reference semantics plus independent human review of semantically non-equivalent
mutants. The contribution is a conformance corpus and testing method — it is not a health-AI governance
protocol, not a mutation-adequacy benchmark of testing strategies, and not a concurrency or replay
attack study.

## 1. Claim-to-prior-work falsification matrix

Each row takes one candidate claim of this paper and names the real prior work that could falsify it
(i.e., already owns the claim), what the prior work actually establishes, the distinguishing observation
this study must produce, and the refusal condition. Prior-work identifiers are from
`research/venue2027/MANIFESTS/literature_registry.json` and the verified
`research/venue2027/_shared/literature_validity_ledger.csv`; every named source must be re-verified
against the primary source before submission (current classification is design-time, not proof).

| # | Candidate claim | Prior work (id / real citation) | What prior work establishes | Distinguishing observation required | Refusal condition (claim withdrawn if) |
|---|---|---|---|---|---|
| C1 | Trace-level metamorphic tests expose authorization faults invisible to static policy-structure coverage | `xacml18` — Xu et al., "Automated Coverage-Based Testing of XACML Policies", ACM SACMAT 2018, https://doi.org/10.1145/3205977.3205979 | MC/DC-driven request generation and mutation-adequacy scoring for static XACML policy structures (single-request, no ordered history) | A fault family that survives matched MC/DC coverage at equal oracle budget but is witnessed by an ordered history (e.g., revocation-before-replay) with a minimal failing trace | If MC/DC-guided generation at equal budget kills the same mutant set, C1 is surrendered and only a tool report remains |
| C2 | History-sensitive conformance corpus for delegated consent fills the gap left by static policy benchmarks | `xacbench20` — "XACBench: a XACML policy benchmark", Soft Computing 2020, https://doi.org/10.1007/s00500-020-04925-5 | Standard policy benchmark profiles and evaluation for static XACML policies; no delegation timelines, no cross-engine replay | Corpus units are `(policy history, request)` pairs with revocation/redelegation/replay ordering, scored by cross-engine decision parity, not benchmark profile pass-rate | If XACBench-style profile tests reproduce the same divergence classes without histories, C2 is not novel and the corpus is published as an incremental dataset |
| C3 | Cross-engine conformance divergence (Cedar/OpenFGA/OPA) is measurable with a portable oracle despite heterogeneous semantics | `zanzibar19` — Pang et al., "Zanzibar: Google's Consistent, Global Authorization System", USENIX ATC 2019, https://www.usenix.org/conference/atc19/presentation/pang; `cedar`; `openfga` | Zanzibar defines consistency-aware authorization (zookies, permission re-evaluation after relation changes); Cedar and OpenFGA are executable engines with documented expressivity limits | Divergence measured at identical histories and request attributes across ≥2 real engine versions, with untranslatable constructs labeled INDETERMINATE by the oracle — not a consistency model, not an engine proposal | If disagreement disappears once histories are trivially linearizable, or if no real engine executes the corpus, C3 collapses to a paper mapping and the Dataset/Tool claim is refused |
| C4 | Ordered-history faults are distinct from single-request semantic gaps | `nistabac` — NIST SP 800-162 (ABAC definition and considerations, updated 2019) | Formal ABAC vocabulary and attributes; no history sensitivity, no testing method | Fault taxonomy keyed on temporal precedence (F01–F05 in SPEC §3) with per-class witnesses absent from any static single-request corpus | If the fault taxonomy is reproducible from single-request tests, the "temporal" modifier is withdrawn |
| C5 | A stateful but non-metamorphic generator is not sufficient | property-based history generator without temporal metamorphs (baseline B3; declared in blueprint, implementation pinned before runs) | Random/stateful history generation can hit ordered faults by chance | Pairwise comparison at equal oracle-call budget showing metamorphs detect strictly more distinct fault classes with minimal witness length advantage | If B3 parity holds, the metamorphic mechanism claim is falsified |
| C6 | Mutation testing of governance faults is a different question than engine conformance | GovMut (`assurance-soict-2026`, sealed W8 45-mutant corpus, `research/publication_registry.yaml`) | Mutation scores of established testing strategies against sequence-sensitive governance faults in a stateful health-AI store | PolicyTrace endpoint is cross-engine decision parity on new synthetic policy-delegation histories; GovMut's 45 mutants and scores are never inputs or comparanda | Any reuse of W8 mutant scores or corpora as SACMAT evidence (see §3) |
| C7 | Replay-attack prevention and stale-commit governance are different endpoints | GLHS R4 (`glhs-journal`), GovRed (`govred-rivf-2026`), replay-admission design (IFIP SEC 2027 study) | Disclosure-to-commit governance correctness, stale-commit acceptance, replay admission rates | SACMAT's endpoint is conformance divergence detection rate across engines on synthetic histories; no commit/admission outcome is measured | Any claim that PolicyTrace measures replay acceptance or stale commits |
| C8 | Purpose-scoped delegation testing is not covered by existing capability systems' own test suites | `cedar`, `openfga`, `opa` upstream test suites | Engine-native test suites validate engine-internal semantics, not a shared history corpus across engines | Same-history parity failures between engines under identical encodings, with root causes attributed to semantic mismatch | If upstream suites already encode the shared corpus classes, C8 reduces to engineering integration work |

**Strongest competing explanation (must be defeated, not strawmanned).** "Temporal faults are an
artifact of under-specified encodings, not engine divergence: a sufficiently careful single-engine
policy author never encounters them." This is tested by encoding the *same* history corpus under each
engine's documented best practice and measuring residual disagreement; if disagreement vanishes under
expert encoding, the competing explanation wins and the paper reports portability limits instead of a
fault-detection claim.

## 2. Exactly three research questions (frozen scope)

Each RQ states: primary endpoint, strongest competing baseline, independent oracle, statistical test,
and falsification condition. Units are independent `(policy history, request)` pairs; never
per-retry pseudo-replication. Estimand details, contrast selection from pilot, and denominators are
frozen by the downstream task `SACMAT-rq_registry` (`rq_and_estimands.yaml`); this section fixes the
question-level contract only.

### RQ1 — Temporal fault coverage

**Question.** Which distinct trace-level policy errors are undetected by static rule/decision coverage
but exposed by temporal metamorphic tests?

- **Primary endpoint.** Count of distinct trace-level fault families (F01–F05 classes: expired delegate
  role, inheritance conflict, revoke-then-regrant ordering, nested-purpose mismatch, emergency override
  without approval obligation) detected by temporal metamorphic generation beyond matched static
  decision coverage, per independently designed mutant family.
- **Strongest competing baseline.** B1: MC/DC-inspired XACML policy testing (Xu et al., SACMAT 2018,
  `xacml18`) at equal oracle-call budget — the strongest published coverage-based generator; B0 (uniform
  random requests) is the weak reference only.
- **Independent oracle.** Executable declarative reference semantics maintained separately from all
  candidate code (oracle never imports the generator), plus independent human review of semantically
  non-equivalent mutants; undecided cases are labeled `INDETERMINATE`, never silently resolved.
- **Statistical test.** Paired comparison of per-family detection indicators across generation methods
  on the same mutant corpus; McNemar's test on discordant mutant pairs for the binary detected/not
  outcome, with family-clustered bootstrap confidence intervals for the risk difference; multiplicity
  controlled across the three RQs (primary = RQ2 endpoint, others Holm-corrected secondaries).
- **Falsification condition.** If MC/DC-guided generation at equal oracle budget detects the same
  fault families, RQ1 yields a negative result: no novel coverage claim is made and the result is
  published transparently as such.

### RQ2 — Mutation-testing efficiency at equal budget

**Question.** How many executable mutants representing revocation, delegation, purpose and temporal
precedence are killed by comparable budgets for random, MC/DC-inspired and PolicyTrace generation?

- **Primary endpoint.** Mutation score (killed / total non-equivalent mutants, 50 independently
  designed mutants + reserved fresh holdout mutant families) at a fixed, pre-registered oracle-call
  budget, with minimal failure trace length as the co-primary witness measure.
- **Strongest competing baseline.** B3: property-based history generator without temporal metamorphs at
  the identical oracle-call budget (strongest stateful alternative), with B1 as the strongest
  coverage-based alternative and B2 (XACBench policy profile–driven synthetic tests) as the benchmark
  baseline; B0 (uniform random authorization requests) is the weak reference. All baselines use pinned
  upstream sources, fidelity vectors and equal permissions/compute; `NOT_RUN_EXTERNAL` is the
  transparent status if a baseline cannot be executed, and precludes comparative claims for that arm.
- **Independent oracle.** Same executable reference semantics as RQ1; mutant ground truth (equivalent /
  non-equivalent / indeterminate) is authored by reviewers without access to candidate implementation
  outputs.
- **Statistical test.** Paired mutation-score comparison across arms on the shared mutant set; Wilcoxon
  signed-rank over per-family paired scores with cluster bootstrap over mutant families; primary
  estimand is the paired score difference PolicyTrace minus B3 at equal budget.
- **Falsification condition.** If PolicyTrace does not outperform B3 and B1 at equal oracle-call
  budget, the novel fault-detection claim is withdrawn in full; the paper reports the null result and
  portability limits transparently. Frozen holdout may not be opened before protocol freeze.

### RQ3 — Cross-engine semantics

**Question.** Across Cedar, OpenFGA and OPA, which semantics are faithfully expressible, and where do
adapters necessarily diverge?

- **Primary endpoint.** Policy-engine disagreement rate on identical `(policy history, request)` units:
  fraction of units where encoded engines return non-parity decisions (including
  INDETERMINATE/untranslatable labeling), reported by semantic construct class.
- **Strongest competing baseline.** Static policy diff / single-engine testing (the
  `publication_overlap_registry.yaml` sacmat baselines): the competing explanation predicts that
  static-structure comparison plus per-engine tests explains all observed divergence without replaying
  shared histories.
- **Independent oracle.** The portable four-valued reference oracle (PERMIT/DENY/NOT_APPLICABLE/
  INDETERMINATE) defined from the declarative semantics document, not from any engine's behavior;
  untranslatable constructs are pre-labeled, never scored as engine bugs.
- **Statistical test.** Disagreement rate per construct class with Wilson score intervals; paired
  engine-vs-engine parity compared via exact McNemar on discordant units; CIs clustered on independent
  histories.
- **Falsification condition.** If residual cross-engine disagreement is zero under best-practice
  encodings, or if disagreement is fully explained by static policy diff, RQ3 reports zero-divergence
  and the conformance corpus is positioned as a tool-only contribution (Dataset/Tool track), never as a
  fault-detection claim.

## 3. Non-overlap and distinct contribution

### 3.1 The truly distinct endpoint

The distinct primary endpoint of this study is the **delegation conformance divergence detection rate**:
cross-engine decision non-parity on identical ordered `(policy history, request)` units, detected by
temporal metamorphic tests at equal oracle budget. No prior CLARA study measures this endpoint:

| Study (registry id) | Its primary endpoint | Why it is not this endpoint |
|---|---|---|
| `glhs-journal` (GLHS R4) | governed read→proposal→write correctness (stale-commit/disclosure binding) | measures commit-binding correctness of one governed system, not decision parity across policy engines |
| `govred-rivf-2026` | unauthorized or stale commit acceptance and prohibited disclosure | mutation-after-disclosure commit acceptance; no cross-engine history replay |
| `assurance-soict-2026` (GovMut) | mutation score of testing strategies on a fixed health-AI governance fault corpus | measures testing-strategy adequacy on one system's faults; not engine-vs-engine conformance |
| IFIP SEC 2027 study | replay acceptance rate across purpose/delegation lineage | prevention/attack admission endpoint on receipts; not testing-method fault detection or engine portability |
| AIME 2027 study | unsafe clinical action rate under consent/medication changes | clinical-content workflow safety, not authorization semantics |
| COMPSAC 2027 study | forbidden commit rate under dependency-complete schedules | database concurrency admission, not policy-engine decision parity |
| HEALTHINF #97 (accepted) | governance protocol evidence (background) | cited as background only; no claim or number is inherited |

### 3.2 GovMut differentiation (mutation-testing adequacy vs conformance testing)

GovMut (`assurance-soict-2026`, sealed W8 45-mutant study) asks: *which established testing strategies
detect which governance faults in one stateful health-AI system?* Its scientific object is a mutant
corpus and a comparison of testing strategies' adequacy scores. PolicyTrace asks a different question:
*do heterogeneous policy engines agree when the same delegated-consent history is replayed into each?*
Its scientific object is a portable history corpus, a four-valued reference oracle, and cross-engine
parity. Concretely:

1. **Different unit of analysis.** GovMut: mutant × testing strategy on a single governed store.
   PolicyTrace: `(policy history, request)` × engine encoding, across Cedar/OpenFGA/OPA.
2. **Different direction of inference.** GovMut infers test-suite adequacy (fault detection).
   PolicyTrace infers semantic conformance/portability (decision parity), with fault detection only as
   the RQ1/RQ2 mechanism against *new* mutants designed for this study.
3. **No corpus transfer.** GovMut's 45 W8 mutants, its sealed scores, and the GLHS R4 E15–E22 corpus
   are not inputs, baselines, or comparanda anywhere in this study (see §3.3). New mutants are designed
   independently against the F01–F05 temporal fault families with fresh holdout families reserved.
4. **Anti-salami pair control.** Per `GATES/ANTI_SALAMI_REVIEW.md`, the SACMAT–GovMut pair is the
   declared "authorization semantics vs mutation-testing adequacy" split; this document is the
   venue-side signing of that split. If a future reviewer cannot defend the distinction, SACMAT is
   converted to a Dataset/Tool-track tool paper or merged, never repackaged.

### 3.3 Archive refusal — frozen E15–E22 are not new evidence

**Refusal.** The frozen GLHS R4 E15–E22 experimental outcomes (and the accepted HEALTHINF paper built on
them) are *background context only*. They are not, and will never be presented as, new SACMAT evidence:

- No E15–E22 number, table, figure, or derived statistic may appear in any SACMAT manuscript, corpus,
  or artifact as a fresh result.
- Historical E15–E19 backend attestation is `sqlite:///:memory:`; those runs never validate any
  PostgreSQL claim, and PolicyTrace makes no database-backend claims at all.
- The study population is new synthetic policy-delegation histories generated under a frozen protocol —
  explicitly *not* GovMut's 45 mutants and *not* the GLHS R4 E15 corpus (SPEC §4).
- Any draft sentence that reads a frozen E15–E22 outcome as support for an SACMAT claim is a
  forbidden-commit violation to be caught by `SACMAT-overlap` audit, per SH-claim_overlap's
  `ARCHIVE_REUSE_AS_NEW` gate.

### 3.4 Prior-manuscript disclosure

Closest published/accepted/in-registry works are disclosed here and must be cited in the manuscript:
GLHS R4 (`glhs-journal`, journal revision), GovRed (`govred-rivf-2026`), GovMut
(`assurance-soict-2026`), the accepted HEALTHINF #97 work, plus external prior art `xacml18`,
`xacbench20`, `zanzibar19`, `cedar`, `openfga`, `opa`, `nistabac`. Registry statuses are preserved as
recorded (2026-08-19 registry; re-audit at submission per `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`
publication-status rule); no acceptance or proceedings date is asserted or guessed here.

## 4. Falsification matrix against the five-part distinction test

Per `CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md` and `GATES/ANTI_SALAMI_REVIEW.md`:

1. **Different precise research question.** Conformance of delegated-consent *histories* across policy
   engines — not commit governance (GLHS/GovRed), not testing-strategy adequacy (GovMut), not replay
   prevention (IFIP), not clinical workflow (AIME). ✔
2. **Different primary endpoint.** Cross-engine delegation conformance divergence detection rate on
   ordered histories; none of the nine studies or four registry studies uses this endpoint. ✔
3. **Independently frozen evaluation design.** New synthetic history corpus, new 50-mutant set with
   reserved holdout families, pre-registered budgets and oracle; freeze precedes any scoring. ✔
4. **Material new contribution.** Portable four-valued oracle, trace-level metamorphic generation,
   Cedar/OpenFGA/OPA conformance adapters — none exists in the registry studies. ✔
5. **Candid citation of closest prior work.** §1 matrix and §3.4 name and link every closest source. ✔

## 5. Risks, stop conditions, and decision

**Stop and revise if** (from TASKS/SACMAT-scope.md §4, binding here): oracle/fixture imports candidate
code; a baseline is unfaithful to declared semantics or lacks budget/permission parity; holdout opened
before freeze; output selectively dropped; a real-engine claim made without executing the real engine
(naming Cedar/OpenFGA/OPA is not executing them); an UNKNOWN/INDETERMINATE outcome counted as a safe
decision.

**Feasibility risk (recorded, unresolved):** SACMAT Dataset/Tool track is likely the better initial
target than a main-track claim; this requires actually executing external engines, which is planned but
NOT_RUN. If external engine execution proves infeasible, the fallback is a transparent
`NOT_RUN_EXTERNAL` tool paper without comparative claims.

**Strongest competing explanation** (defeated only by §1's expert-encoding experiment): temporal faults
are encoding artifacts, not engine divergence.

## Decision

**Decision: GO** — conditional on the falsification rules above. The GO covers scoping and
protocol-level work only (RQ freeze, corpus and oracle design, baseline pinning, external-engine
integration). The novel fault-detection claim is **not** pre-approved: it survives only if PolicyTrace
outperforms B1 and B3 at equal oracle-call budget on the frozen corpus; otherwise the negative result
and portability limits are published transparently, and frozen E15–E22/GovMut evidence remains
background, never new SACMAT evidence.

---

*Signed as the SACMAT P01 scope register by the SACMAT-scope agent, 2026-11-15, at base SHA
`7ebdbbf0740e87ffebe3538d6893a53eaccf2216`. Downstream consumers: `SACMAT-rq_registry`,
`SACMAT-threat`, `SACMAT-prior`, `SACMAT-overlap`.*
