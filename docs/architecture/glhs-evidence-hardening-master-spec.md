# CLARA-Care GLHS — Evidence Hardening & External Validation Master Specification

Repository: `https://github.com/Project-CLARA-HBT/CLARA-Care`

Primary specification:
`docs/architecture/glhs-evidence-hardening-master-spec.md`

Status ledger:
`docs/architecture/glhs-evidence-hardening-status.md`

Top-level reproducibility index:
`REPRODUCIBILITY.md`

## 0. Mission

Upgrade the evidence base for the Governed Longitudinal Health State (GLHS) from primarily developer-authored structural/conformance evidence into a layered, externally grounded systems evaluation.

This program is **not a redesign of GLHS**.

Preserve the established architecture:

`Evidence -> GST -> GLHS -> THSS -> AI/projection -> governed proposal -> GST`

and the central contribution:

> GLHS is a co-versioned read–write governance contract that binds the governed longitudinal state disclosed to an AI to the state/governance context against which any resulting persistent proposal is allowed to commit.

The program must establish, where evidence permits:

1. mechanism correctness beyond the developer-authored oracle;
2. exact incremental value of read→write snapshot binding beyond ordinary temporal resolution and optimistic concurrency;
3. cross-schema and cross-dataset portability;
4. large-scale operational behavior;
5. behavior on open real-world health datasets;
6. downstream THSS utility;
7. governance/adversarial robustness;
8. clean-source reproducibility;
9. independently adjudicated clinical evidence only when genuinely available.

Synthetic scale, external raw data, clinician adjudication and clinical validation are different evidence classes and must never be conflated.

---

# 1. Non-negotiable continuation rules

Before editing or executing experiments:

1. Read:
   - `AGENTS.md`
   - `CLAUDE.md`
   - root `README.md`
   - current ExecPlan
   - GLHS/GST/THSS architecture docs
   - structural evaluation docs
   - CommitLoop evaluation docs
   - existing reproducibility/freeze manifests
   - this specification
   - current status ledger.

2. Inspect:
   - current HEAD;
   - branch;
   - working-tree dirty state;
   - current evaluated SHA(s);
   - benchmark artifacts already frozen.

3. Reuse production GLHS primitives. Do not create a parallel patient-state architecture merely for evaluation.

4. Do not alter production semantics to improve benchmark scores.

5. A genuine correctness fix is allowed only when:
   - documented;
   - tested;
   - benchmark implications recorded;
   - any affected frozen protocol receives a new version and complete rerun.

6. Never delete or overwrite prior frozen evidence. New evaluations must coexist with existing evidence lineage.

7. Do not fabricate:
   - dataset availability;
   - lawful access;
   - patient counts;
   - labels;
   - clinician independence;
   - provider outputs;
   - model versions;
   - commands;
   - successful tests;
   - measurements.

8. Missing external prerequisites must fail closed as:
   - `NOT_RUN`;
   - `BLOCKED_EXTERNAL`;
   - or another explicit status.

9. Continue every independent gate even when another external gate is blocked.

10. Repository-facing naming must remain publication-target agnostic. Do not use `q1`, `q2`, `journal_upgrade`, etc. in active benchmark, dataset, artifact or protocol identifiers.

---

# 2. Evidence hierarchy

## Tier A — Independently adjudicated external evidence

Highest-value evidence:

- subject-disjoint external real-health-data cohort;
- frozen task protocol;
- labels created independently of GLHS development;
- qualified human annotation where clinical judgement is required;
- adjudication and disagreements recorded;
- sealed oracle before final comparative execution.

This tier is required before using terms such as:

- independently adjudicated clinical validation;
- independently established clinical-state accuracy.

If qualified reviewers do not exist, keep this tier blocked. Code or model output cannot self-attest independence.

## Tier B — External real-data structural evidence

Open real-world data may support externally grounded structural evaluation even without clinical adjudication.

Current target sources:

- Diabetes 130-US Hospitals;
- MEPS longitudinal/event public-use files;
- eICU Collaborative Research Database Demo;
- other genuinely open, lawful, subject-level longitudinal datasets discovered later.

Allowed claims include:

- external real-data execution;
- cross-dataset structural consistency;
- state reconstruction on real longitudinal records;
- external representation portability.

Do **not** automatically call this clinical validation.

## Tier C — Large-scale external systems evidence

Target archives:

- CMS DE-SynPUF OMOP — approximately 2.3M beneficiaries/persons;
- SyntheticMass — 1M synthetic longitudinal records, preferably FHIR representation;
- Synthea OMOP — approximately 2.8M synthetic persons if acquired.

These support:

- archive-scale execution;
- cross-schema portability;
- throughput;
- storage;
- reconstruction cost;
- THSS compilation cost;
- GST operational cost;
- replay determinism.

They do not become clinical ground truth because of scale.

## Tier D — Comparative mechanism evidence

Required systems/comparators:

- GLHS-full;
- Zhao-style BTSA;
- TPR;
- GLHS-no-GST;
- AUTH-FULL / no-task-minimization;
- standards-composed strong baseline;
- LWW;
- Naive RAG.

Weak baselines remain secondary.

## Tier E — Downstream model utility

Use frozen task instances and identical reasoner settings to compare context conditions.

## Tier F — Operational/adversarial assurance

Exercise real API/database/governance boundaries.

## Tier G — Formal/property assurance

Executable invariants strengthen confidence but do not substitute for external evaluation.

---

# 3. Dataset registry and reproducible data layer

Create or maintain:

```text
datasets/
  registry.yaml
  manifests/
  licenses/
  raw/                 # gitignored
  normalized/          # normally gitignored
  adapters/
scripts/data/
  list_sources.py
  fetch.py
  verify.py
  inspect.py
  normalize.py
  freeze_manifest.py
```

Raw external data must not be committed.

Each registry entry must include where applicable:

```yaml
id:
display_name:
provider:
canonical_source:
mirror_source:
download_method:
license:
access_class:
evidence_class:
synthetic:
schema:
version:
release_date:
acquired_at:
raw_path:
normalized_path:
expected_files:
checksum_manifest:
subject_identifier:
encounter_identifier:
valid_time_fields:
knowledge_time_fields:
provenance_fields:
clinical_domains:
known_limitations:
```

Never infer a missing temporal coordinate. Preserve unknown temporal precision explicitly.

---

# 4. Initial dataset program

## D1 — CMS DE-SynPUF OMOP

Status at program start: locally downloaded according to user/operator report; verify locally before recording as available.

Target scale: full approximately 2.3M population archive.

Role:

- large-scale external systems validation;
- OMOP portability;
- longitudinal claims replay;
- operational benchmarking.

Measure at minimum:

- persons processed;
- source rows/events;
- state transitions;
- histories reconstructed;
- snapshot compilations;
- failures;
- wall-clock;
- cases/persons per second;
- CPU;
- peak RSS;
- disk reads/writes where feasible;
- generated-state/storage amplification.

Do not call this clinical validation.

## D2 — SyntheticMass FHIR

Status at program start: locally downloaded according to user/operator report; verify locally.

Target scale: full 1M synthetic patient archive.

Role:

- large-scale FHIR portability;
- cross-representation evaluation relative to OMOP;
- deterministic replay;
- full-stack throughput.

Preserve original FHIR resource identities and provenance where available.

## D3 — Synthea OMOP

Target: full approximately 2.8M public OMOP archive if disk/network permit.

Role:

- additional OMOP-scale replication;
- separate archive execution;
- sensitivity to source-generation/distribution differences.

Because it belongs to the Synthea family, do not present it as an independent clinical cohort from SyntheticMass.

## D4 — Diabetes 130-US Hospitals

Target: full public dataset.

Evidence class: real external tabular encounter data.

Role:

- cross-institution real-data structural evaluation;
- repeated-patient encounter reconstruction;
- diagnoses;
- medication transitions;
- utilization history;
- task-bounded state projection.

Do not invent intra-encounter event timestamps unavailable in the source.

## D5 — MEPS

Target: public longitudinal/person + event files needed for defined tasks, preferably multiple consecutive release years/panels when reproducibly manageable.

Evidence class: real external longitudinal survey/healthcare-event data.

Potential domains:

- conditions;
- inpatient;
- emergency;
- outpatient;
- prescribed medicine;
- utilization.

Preserve survey/event semantics. Do not present MEPS as EHR data if it is not.

## D6 — eICU-CRD Demo

Target: full openly accessible demo.

Evidence class: real multi-hospital clinical data.

Role:

- temporal clinical execution;
- repeated observations;
- diagnosis/treatment evolution;
- multi-hospital external structural evidence.

Use only legitimately open demo data unless credentialed access is actually obtained.

## D7 — Synthea Coherent

Target: public multimodal archive where useful.

Role:

- multimodal source isolation;
- purpose-bounded disclosure;
- FHIR + linked modalities;
- testing whether unrelated modalities remain excluded from task-minimum context.

Scale is secondary.

---

# 5. Dataset acceptance gates

A dataset cannot enter headline results until:

1. canonical source is recorded;
2. license/access status is documented;
3. raw archive verification completes;
4. checksum manifest exists;
5. extraction/normalization is reproducible;
6. patient/subject key semantics are understood;
7. temporal fields are documented;
8. missingness/duplication behavior is characterized;
9. cohort manifest is frozen;
10. data leakage from development cohorts is assessed where relevant.

Failure to satisfy a gate must remain explicit.

---

# 6. Common longitudinal evidence representation

Implement adapters that map source data into a **common evaluation interface**, not a replacement production state model.

The normalized interface must preserve:

- source dataset;
- source subject;
- source record/resource ID;
- encounter ID if available;
- evidence type;
- domain;
- original value;
- normalized value if used;
- valid/event time;
- recorded/knowledge time if available;
- temporal precision;
- estimated-time flag;
- source provenance;
- source schema;
- original payload pointer/hash;
- uncertainty/missingness.

Never convert a missing knowledge timestamp into a fabricated event/knowledge distinction.

Keep raw-source IDs sufficient for exact reconstruction.

---

# 7. Formal contract hardening

The paper/code formalization must clearly distinguish:

## 7.1 Base-bound proposal

A proposal that declares the canonical state version it observed:

\[
R_b = \langle u,e,a,p,v_b,\rho\rangle
\]

Required admissibility includes:

\[
R_b.u = S.u
\]

\[
R_b.v_b = S.version
\]

current authorization and policy/consent checks, plus state invariants.

## 7.2 Snapshot-bound proposal

A proposal explicitly bound to the THSS disclosure artifact:

\[
R_s =
\langle
u,e,a,p,v_b,sid,d,\rho
\rangle
\]

with manifest:

\[
M =
\langle
sid,u,q,a,p,v_s,v_\pi,v_c,I,d,\tau_{exp},...
\rangle
\]

The bound commit must enforce where applicable:

\[
R_s.v_b=M.v_s=S.version
\]

\[
R_s.u=M.u=S.u
\]

\[
R_s.a=M.a
\]

\[
R_s.p=M.p
\]

plus:

- snapshot exists;
- snapshot not expired;
- digest matches;
- current authorization permits commit;
- policy/consent changes are reevaluated;
- proposal/state invariants hold.

## 7.3 Atomicity

Check and transition must be atomic.

A successful operation is conceptually:

\[
S_v \xrightarrow[\text{atomic commit}]{R} S_{v+1}
\]

A concurrent modification between validation and persistence must not allow a stale proposal to commit.

## 7.4 Bitemporal snapshot semantics

THSS formalization must explicitly preserve valid-time and knowledge-time semantics or formally state which coordinate is fixed for a given task.

## 7.5 Digest reproducibility

Snapshot digest metadata must record enough information for later reconstruction:

- hash algorithm;
- canonicalization profile/version;
- payload schema version;
- payload digest.

Treat an unkeyed digest as a consistency/audit fingerprint, not sender authentication.

These repairs should preserve existing behavior unless a real correctness defect is identified.

---

# 8. Closest-prior-work and standards-composed comparators

## 8.1 BTSA

Maintain a faithful Zhao-style bitemporal state arbitration comparator including where supported:

- valid time;
- knowledge time;
- SUPPORT;
- REFINE;
- SUPERSEDE;
- BRANCH-CONFLICT;
- non-destructive history;
- explicit conflicts.

Do not weaken it to favor GLHS.

## 8.2 TPR

Maintain the strong temporal/provenance resolver used in prior structural work.

GLHS should not claim better temporal arbitration when it ties BTSA/TPR on temporal/conflict cases.

## 8.3 Standards-composed strong baseline

Add a comparator representing the strongest realistic alternative composition:

**temporal/provenance state resolution
+ optimistic base-version write enforcement
+ authorization
+ provenance/audit metadata**

The exact implementation may use project-local abstractions, but must faithfully implement these capabilities.

Its purpose is to answer:

> What does exact THSS→GST disclosure binding add beyond ordinary temporal state resolution plus optimistic concurrency and governance metadata?

## 8.4 Required clause ablations

At minimum compare:

1. temporal resolver only;
2. + authorization;
3. + base-version check;
4. + current authorization recheck;
5. + source snapshot ID;
6. + snapshot payload digest;
7. + expiry enforcement;
8. + complete GLHS snapshot-bound contract.

Use mechanism-specific challenge families rather than only pooled accuracy.

---

# 9. Snapshot-binding-specific challenge suite

Create a new sealed suite that specifically distinguishes base-version protection from co-versioned disclosure binding.

Required scenarios:

### State-version failures
- direct AI write;
- stale base version;
- two concurrent proposals from same version;
- write after unrelated profile update.

### Governance drift with unchanged patient-state version
- consent revoked after inference;
- purpose no longer allowed;
- role/actor permission changed;
- data-class grant changed.

### Snapshot identity failures
- correct base version but wrong snapshot;
- snapshot from another task;
- snapshot from another purpose;
- snapshot from another actor;
- snapshot from another subject/profile;
- expired snapshot;
- payload altered with stale digest;
- digest substituted;
- snapshot identifier replayed.

### Derived-state/cache failures
- revoked category remains in cache;
- old projection reused;
- index survives revocation incorrectly.

### Bypass attacks
- model attempts direct canonical mutation;
- prompt injection requests bypass;
- uploaded evidence contains malicious instructions;
- candidate tries to self-promote into confirmed state.

Pre-freeze all scenario-generation rules.

Report mechanism-localized exact counts.

---

# 10. Concurrency and false-stale evaluation

The current profile-wide state version is intentionally conservative. Quantify the cost.

Compare where implementable without redesigning production semantics:

- current global/profile state version behavior;
- simulated resource/domain-granular conflict oracle for analysis only;
- dependency-overlap classification.

Measure:

- total stale rejections;
- true conflicting stale rejections;
- unrelated/false-stale rejections;
- retries;
- successful commits;
- human/review escalation if applicable;
- throughput impact;
- P50/P95/P99 commit latency.

Do not silently replace production version semantics. Alternative granularity may remain an analytical comparator.

---

# 11. External structural evaluation protocol

For each accepted external dataset:

1. freeze cohort before headline execution;
2. define task/domain mapping;
3. define what can be directly source-derived;
4. do not invent labels requiring medical judgement;
5. separate natural source observations from synthetic perturbations;
6. if perturbations are introduced, label results explicitly as:
   **source-derived external structural execution**;
7. preserve natural results separately from perturbation results.

Prefer at least three domains when source fields permit:

- medications;
- diagnoses/problems;
- laboratory/observations;
- encounters/utilization;
- allergies/adverse reactions where genuinely present.

Report results by dataset and domain.

Do not hide heterogeneous results in one pooled denominator.

---

# 12. Independent adjudication program

Create:

```text
evaluation/independent_adjudication/
protocol/
annotations/
adjudication/
manifests/
```

Before annotation freeze:

- select subject-disjoint cohort;
- freeze task definitions;
- freeze annotation guide;
- freeze exclusion rules;
- specify required reviewer qualifications;
- define disagreement-resolution procedure.

Where feasible use at least two independent reviewers for the key subset.

Record:

- independent labels;
- disagreements;
- adjudicated labels;
- reviewer role/qualification attestation;
- timestamps/version;
- inter-rater statistics when methodologically appropriate.

Do not generate clinician labels with an LLM and call them independent clinical labels.

If qualified humans are unavailable, keep this entire evidence tier `BLOCKED_EXTERNAL`.

---

# 13. THSS downstream utility

Create:

`evaluation/downstream_utility/`

Context conditions:

1. full authorized longitudinal context;
2. Naive RAG;
3. TPR/BTSA state context;
4. standards-composed baseline context where meaningful;
5. AUTH-FULL;
6. THSS loose;
7. THSS default;
8. THSS strict.

Use identical task instances and model settings across context conditions.

Prefer at least two distinct model families.

Freeze:

- exact provider/model IDs;
- model release/version where available;
- prompts;
- system instructions;
- output schema;
- decoding parameters;
- context budget;
- retrieval configuration;
- scorer;
- retry/error policy;
- test family;
- multiplicity plan.

Measure:

- task correctness;
- critical omission;
- unsupported assertion;
- conflict-handling correctness;
- evidence fidelity;
- unnecessary authorized disclosure;
- prohibited disclosure;
- input tokens;
- output tokens;
- latency;
- provider cost where available;
- completion/error/fallback rate.

The primary question is:

> Does THSS reduce unnecessary authorized disclosure while preserving downstream task utility?

Critical-fact recall alone is not utility.

---

# 14. Adversarial governance evaluation

Create:

`evaluation/governance_adversarial/`

Exercise real application boundaries whenever feasible.

Required attack classes:

- cross-subject/profile access;
- stale THSS replay;
- consent revocation;
- role escalation;
- purpose mismatch;
- snapshot substitution;
- digest mismatch;
- expiry;
- concurrent stale commit;
- cache/index revocation failure;
- prompt GST bypass;
- prompt injection in evidence;
- malicious evidence requesting unrelated disclosure;
- derived projection surviving revocation.

Measure exact:

- attempted attacks;
- blocked attacks;
- unauthorized disclosures;
- successful bypasses;
- stale commits;
- wrong-profile exposure;
- revocation failures;
- audit completeness.

Never summarize this as “GLHS is secure.”

---

# 15. Full-stack operational benchmark

Create:

`evaluation/fullstack_benchmark/`

Exercise the actual production path:

`PostgreSQL -> GST -> GLHS -> THSS -> API`

plus relevant cache/index/projection infrastructure.

Evaluate across:

- history depth;
- subject count;
- evidence density;
- concurrent readers;
- concurrent writers;
- snapshot sizes;
- policy/consent changes.

Measure:

- P50/P95/P99 evidence-ingest latency;
- P50/P95/P99 state reconstruction;
- P50/P95/P99 THSS compilation;
- P50/P95/P99 GST commit;
- throughput;
- DB reads/writes;
- transition write amplification;
- storage amplification;
- projection invalidation/rebuild time;
- revocation propagation;
- CPU;
- peak RSS;
- disk usage;
- errors;
- retries.

For every full archive run record:

- dataset/version;
- exact source SHA;
- machine/hardware;
- OS;
- DB version;
- Python/runtime;
- worker/process count;
- wall clock;
- subjects;
- records/events;
- operations;
- throughput;
- failures;
- peak resource usage.

A large patient count without runtime/resource measurements is not scalability evidence.

---

# 16. Cross-schema portability evaluation

The core portability comparison should include where available:

- OMOP:
  - DE-SynPUF;
  - Synthea OMOP;
- FHIR:
  - SyntheticMass;
  - eICU/MIMIC-derived standardized representations only if lawfully available;
- event/tabular:
  - Diabetes-130;
  - MEPS;
  - eICU Demo;
- multimodal:
  - Synthea Coherent.

Normalize only what is required for the evaluation interface.

Report:

- adapter coverage;
- unsupported source fields;
- temporal precision retained/lost;
- provenance retained/lost;
- mapping errors;
- ingestion failures;
- domain coverage;
- invariant failures.

Do not claim universal representation independence from a finite set of adapters.

---

# 17. Formal/property assurance

Create:

`evaluation/property_assurance/`

Required executable properties include:

1. stale base version cannot commit;
2. successful commit increments canonical version exactly as specified;
3. compare-and-transition is atomic;
4. direct model canonical mutation is rejected;
5. supersession preserves historical reconstruction;
6. active meaningful assertions have evidence ancestry;
7. comparable-authority contradiction does not silently collapse;
8. repeated identical evidence is idempotent;
9. revoked data class cannot appear in a newly authorized snapshot;
10. wrong-profile snapshot cannot bind to a proposal;
11. wrong actor/purpose binding fails;
12. expired snapshot fails;
13. digest mismatch fails;
14. current authorization change can invalidate persistence;
15. derived-store loss cannot destroy canonical GLHS;
16. cache/index rebuild cannot resurrect revoked canonical access;
17. bitemporal replay produces expected state at frozen cutoffs.

Use property-based and/or state-machine testing.

Record:

- seed;
- generated sequence;
- minimal counterexample;
- environment;
- source SHA.

---

# 18. Statistical plan

## Developer-authored structural suites

Treat primarily as conformance/mechanism evidence.

Report:

- exact n/N;
- discordance localization;
- descriptive effect sizes.

If inferential intervals/tests are retained, explicitly state that they quantify repeatability inside the authored suite and are not population-level clinical inference.

## External real-data evaluation

Primary clustering unit:

**patient/subject**, not derived case.

Predeclare:

- primary endpoints;
- secondary endpoints;
- dataset/domain strata;
- comparison family.

Report:

- n/N;
- absolute paired differences;
- confidence intervals;
- exact tests where appropriate;
- subject-cluster bootstrap or another justified subject-aware method.

Do not pool heterogeneous datasets/tasks into a misleading single headline number.

## Model-mediated evaluation

Model×comparator comparison families must be predeclared.

Control multiplicity where appropriate.

Retain all negative and parity findings.

Nonsignificance is not equivalence.

## Independent adjudication

Use agreement statistics only when their assumptions fit the annotation design.

---

# 19. Power and replication planning

Do not reuse the earlier assumption that a fixed number of enrolled subjects will automatically provide enough non-tied pairs.

For paired endpoints:

1. estimate tie/non-tie rate from prior frozen data only;
2. specify desired detectable paired effect;
3. specify alpha/multiplicity family;
4. calculate enrolled N from expected non-tie rate;
5. freeze target before opening the confirmatory cohort.

If achieved non-ties miss the target, report the study as underpowered for that comparison rather than retuning.

---

# 20. Anti-circularity / freeze gates

Before each headline evaluation freeze:

- dataset version;
- cohort manifest;
- split manifest;
- normalization/adapters;
- perturbation rules if any;
- task manifest;
- annotation guide;
- adjudicated oracle where applicable;
- domain policy;
- comparator versions;
- THSS policy;
- model IDs/settings;
- prompts;
- endpoints;
- statistical plan;
- analysis code revision.

After freeze:

- no label-driven policy editing;
- no comparator weakening;
- no same-cohort prompt tuning;
- no undocumented case deletion;
- no silent fallback models;
- no changing exclusions after seeing outcome.

Any benchmark-affecting change requires:

- new protocol version;
- new freeze;
- complete rerun of affected comparisons.

---

# 21. Reproducibility artifacts

Use:

`artifacts/evidence-program/<run-id>/`

Each completed run should include where applicable:

```text
environment.json
source_freeze.json
dataset_manifest.json
cohort_manifest.json
split_manifest.json
normalization_manifest.json
domain_policy_manifest.json
annotation_manifest.json
adjudication_manifest.json
oracle_manifest.json
comparator_manifest.json
model_manifest.json
protocol_manifest.json
cases.csv
per_run.csv
system_outputs.csv
human_labels.csv
adjudicated_labels.csv
domain_results.csv
thss_utility.csv
snapshot_binding_results.csv
concurrency_results.csv
adversarial_results.csv
human_review.csv
fullstack_metrics.csv
statistical_results.csv
error_analysis.csv
report.md
SHA256SUMS
```

`REPRODUCIBILITY.md` must provide a short path:

**paper claim
→ table/figure
→ frozen artifact
→ protocol
→ dataset/cohort
→ command
→ source SHA
→ environment**

Sensitive/licensed/raw datasets must never be committed merely to improve reproducibility.

---

# 22. Status ledger

Maintain:

`docs/architecture/glhs-evidence-hardening-status.md`

For every workstream record:

- `NOT_STARTED`
- `IN_PROGRESS`
- `PASS`
- `FAIL`
- `NOT_RUN`
- `BLOCKED_EXTERNAL`

plus:

- last source SHA;
- protocol version;
- artifact path;
- command;
- result summary;
- blocker;
- next executable action.

Never mark a gate complete based on intended work.

---

# 23. Execution order

## Gate 0 — Establish clean baseline

- inspect repository;
- preserve existing frozen evidence;
- pass relevant existing tests;
- identify current clean evaluated SHA;
- create/update ExecPlan and status ledger.

## Gate 1 — Data foundation

- register DE-SynPUF and SyntheticMass local archives;
- verify checksums/content;
- acquire/verify remaining zero-credential datasets;
- build reproducible adapters;
- freeze dataset manifests.

## Gate 2 — Formal and comparator hardening

- repair specification inconsistencies;
- validate BTSA/TPR;
- implement standards-composed comparator;
- implement clause ablations;
- freeze comparator versions.

## Gate 3 — Snapshot-binding evaluation

- freeze adversarial mechanism suite;
- execute all comparator/ablation conditions;
- localize failure classes.

## Gate 4 — Large-scale archive execution

Run full feasible archives:

- DE-SynPUF OMOP 2.3M;
- SyntheticMass FHIR 1M;
- Synthea OMOP 2.8M if acquired.

Record full operational metrics.

## Gate 5 — Open real-data evaluation

Run:

- Diabetes-130;
- MEPS;
- eICU Demo;

using frozen source-derived task protocols.

Do not fabricate clinical gold.

## Gate 6 — THSS utility

Execute frozen >=2-model context comparison if provider access exists.

## Gate 7 — Concurrency/full-stack/adversarial

Exercise actual application boundaries and production database path.

## Gate 8 — Independent adjudication

Run only when qualified humans and lawful real data are genuinely available.

If not, retain handoff package and `BLOCKED_EXTERNAL`.

## Gate 9 — Property/state-machine assurance

Run exhaustive/fuzzed invariant testing appropriate to implementation constraints.

## Gate 10 — Final freeze

- clean working tree;
- create final evaluation SHA/tag;
- regenerate affected results against that exact revision;
- validate every artifact/hash.

## Gate 11 — Manuscript integration

Do not merely append dataset counts.

Rewrite evidence narrative around:

1. co-versioned read/write problem;
2. precise novelty versus temporal/standards primitives;
3. structural mechanism evidence;
4. snapshot-binding incremental value;
5. external real-data evidence;
6. cross-schema portability;
7. archive-scale systems results;
8. downstream utility;
9. operational/adversarial evidence;
10. independent adjudication if actually completed;
11. limitations.

---

# 24. Claim taxonomy

Use only claims supported by the corresponding evidence.

### Allowed from frozen developer suite

- software conformance;
- mechanism localization;
- deterministic policy behavior.

### Allowed from DE-SynPUF/Synthea/SyntheticMass

- large-scale synthetic/external archive execution;
- cross-schema systems portability;
- operational scalability;
- deterministic replay.

### Allowed from Diabetes/MEPS/eICU Demo without independent clinical labels

- real-data external execution;
- source-derived structural evaluation;
- external representation/domain portability.

### Allowed from model utility experiment

- downstream model behavior under tested models/tasks/settings.

### Allowed only after real independent adjudication

- independently adjudicated clinical-state performance.

Never claim from current evidence alone:

- clinical safety;
- improved outcomes;
- universal privacy;
- universal correctness;
- universal model benefit;
- clinical deployment readiness;
- superiority over all state-aware architectures.

---

# 25. Required manuscript wording discipline

Keep statements such as:

> GLHS builds on established bitemporality, provenance, consent, versioning, retrieval and optimistic concurrency.

The novelty claim should remain:

> The contribution is their AI-specific coupling at the read–write boundary: the governed task snapshot is an explicit auditable artifact, and a persistent proposal can be checked against both its observed base-state version and, when snapshot-bound, the exact disclosure context from which it was produced.

Do not describe ordinary stale-write prevention itself as novel.

Do not describe synthetic millions as “large-scale clinical validation.”

Preferred scale wording:

> full-archive synthetic/external structural and operational execution

or:

> large-scale cross-schema systems evaluation.

---

# 26. Definition of Done

The **executable evidence-hardening program** is complete only when:

1. existing frozen GLHS/CommitLoop evidence remains intact;
2. all newly used datasets have lawful-source and checksum manifests;
3. DE-SynPUF 2.3M and SyntheticMass 1M are verified and reproducibly ingestible;
4. additional selected zero-credential datasets are either completed or honestly marked blocked/not-run;
5. normalized adapters preserve source provenance and temporal semantics;
6. BTSA and TPR remain faithful strong comparators;
7. a standards-composed version-aware/governed baseline exists;
8. clause ablations distinguish base-version safety from exact snapshot binding;
9. snapshot-specific governance attacks are executed;
10. contract formalization is internally consistent;
11. atomic stale-write behavior is tested;
12. cross-schema evaluation covers at least OMOP and FHIR;
13. real-data structural execution covers at least one genuinely real external source;
14. archive-scale runs include wall-clock/resource metrics;
15. THSS utility is measured when model access exists, rather than inferred from label retention alone;
16. concurrency and false-stale burden are quantified;
17. property/state-machine invariants pass or failures remain visible;
18. benchmark-defining protocols/manifests are frozen and hashed;
19. final results are tied to a clean source SHA/tag;
20. all final figures/tables derive from machine-readable frozen artifacts;
21. `REPRODUCIBILITY.md` links every major manuscript claim to evidence;
22. negative/parity results are retained;
23. no external/human evidence is simulated.

The **independent clinical-validation tier** is complete only if, additionally:

24. lawful real-health-data subjects are subject-disjoint from development;
25. the protocol was sealed before evaluation;
26. qualified independent reviewers supplied required labels;
27. disagreements and adjudication are documented;
28. analysis uses the frozen adjudicated oracle.

If items 24–28 are unavailable, do not block the systems evidence program and do not fabricate them. Keep that tier explicitly incomplete.

---

# 27. Final handoff

At completion return:

1. starting SHA and final SHA/tag;
2. starting/final dirty state;
3. changed files;
4. preserved frozen evidence;
5. datasets acquired/verified/not-run;
6. exact population/event counts actually processed;
7. normalization/adapters implemented;
8. comparator and ablation matrix;
9. formal-contract changes;
10. commands/tests with PASS/FAIL/NOT_RUN counts;
11. snapshot-binding results;
12. external real-data results;
13. full-archive systems metrics;
14. concurrency/false-stale results;
15. adversarial results;
16. downstream-model results if executed;
17. independent-adjudication status;
18. artifact paths and hashes;
19. supported manuscript claims;
20. explicitly unsupported claims;
21. remaining external blockers.

Do not return only a plan. Execute every currently executable gate and leave externally impossible gates as precise, reproducible handoffs.
