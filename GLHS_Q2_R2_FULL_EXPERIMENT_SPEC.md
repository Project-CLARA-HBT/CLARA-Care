# GLHS Q2-R2 FULL EXPERIMENT PROGRAM SPECIFICATION

**Manuscript target:** *Exact Disclosure Binding for Persistent Writes in Longitudinal Health AI: The GLHS Governance Contract*  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Authoritative implementation branch for this specification:** `codex/commitloop-phase-a`  
**Pinned branch head audited for this specification:** `81f040d3e05905cc384239c5ae130f629e722d3e`  
**Branch-head timestamp:** 2026-08-27T03:30:33Z  
**Specification version:** `glhs-q2-r2-experiment-program.v1`  
**Prepared:** 2026-09-27  
**Primary field:** Health Informatics / Trustworthy Health AI / AI Systems & Data Governance  
**Publication objective:** Move the current manuscript from **Borderline** Q2 readiness toward a defensible **Weak Accept / Accept** evidence package without overclaiming clinical, cryptographic, or universal correctness.

---

## 0. Executive intent

This specification defines the complete engineering, experimental, statistical, reproducibility, and publication workflow required to address the remaining peer-review blockers for the GLHS manuscript.

It is intentionally designed around the **latest research/development branch**, not `main`. The audited branch already contains substantially more GLHS machinery and research infrastructure than the public default branch, including:

- exact snapshot and manifest digest validation;
- inference-context binding;
- entity-version partitions;
- persisted governance-policy epochs;
- consent-version coordinates;
- canonical lock ordering;
- a six-phase atomic OCC commit kernel;
- proposal dependency vectors and dependency-vector digests;
- anti-laundering / lineage checks for reviewed proposals;
- versioned canonical JSON with an RFC 8785 profile;
- an exact-binding matched ablation harness;
- clause ablation infrastructure;
- PostgreSQL TOCTOU executors and repetition protocols;
- DAG / Zipfian concurrency benchmarks;
- a public bounded formal-governance model with eleven invariants;
- standards-composed and systems comparator scaffolding;
- a 384-subject multi-model CommitLoop protocol/freeze/reproduction system;
- malformed-output audit tooling;
- evidence freeze, seal, validation, and release-gate infrastructure.

Therefore this program **does not rebuild GLHS from scratch**. It does three things:

1. **Synchronizes manuscript claims to the latest implementation.**
2. **Adds the few experiments still missing for novelty, generality, dependency completeness, and reproducibility.**
3. **Re-runs the claim-bearing evidence under one immutable journal-R2 protocol and release bundle.**

The scientific principle governing every workstream is:

> A result may enter the revised manuscript only if the exact implementation revision, protocol, raw observations, analysis code, and derived result are hash-bound in a sealed artifact, and the corresponding claim is explicitly permitted by the claim-to-evidence release gate.

No previous frozen artifact is overwritten. Historical results remain historical. All Q2-R2 evidence uses new run IDs and a new release namespace.

---

# 1. Publication blockers this program must close

The current manuscript is already strong in conceptual framing and claim restraint. The remaining Q2 blockers are empirical and reproducibility-related.

## 1.1 P0 blockers — mandatory before journal resubmission

The Q2-R2 release MUST close all of the following:

### B1. Binding-component minimality

The current matched ablation demonstrates that **exact disclosure binding as a package** matters relative to a no-exact-binding arm, but it does not determine which binding coordinates are necessary or whether a simpler mechanism enforces the same invariant.

Required evidence:

- component-wise binding ablation;
- factorial interaction analysis;
- controls demonstrating that stronger binding does not merely reject every proposal.

### B2. Alternative-design baseline

The manuscript must compare GLHS with at least one intentionally simpler mechanism capable of enforcing the same target property, e.g. an immutable disclosure/read-set token.

Required evidence:

- identical logical schedule corpus;
- identical current-state/current-governance checks;
- decision equivalence / disagreement characterization;
- representation/validation overhead characterization;
- no claim of superiority if the simpler baseline matches GLHS.

### B3. TOCTOU schedule diversity and root-cause closure

The historical 12-schedule suite is valuable but too small, and `TOCTOU-V2-05` / `TOCTOU-V2-09` show expected-versus-observed classification mismatches.

Required evidence:

- instrumented root-cause replay of both historical mismatches;
- broader generated/frozen schedule campaign;
- unique logical histories treated as scientific N;
- jitter repetitions treated only as implementation robustness probes;
- overlapping schedules classified using admissible outcome sets rather than forced serial labels.

### B4. Dependency completeness

The system validates declared dependency sets, but the manuscript does not yet demonstrate that required dependencies are derived or enforced completely.

Required evidence:

- schema/operation-derived dependency contract;
- omission mutation tests;
- multi-entity write-skew scenarios;
- fail-closed behavior when required dependencies are missing;
- controls proving no spurious rejection when the dependency set is complete.

### B5. Reproducibility and public run lineage

All headline runs must be independently reproducible from public code + sealed data/protocol artifacts.

Required evidence:

- exact Git revision;
- immutable protocol hashes;
- raw observations;
- environment manifest;
- analysis scripts;
- deterministic reproduction where applicable;
- artifact checksums;
- claim-to-evidence ledger;
- one release gate that refuses unsupported manuscript claims.

## 1.2 P1 blockers — strongly recommended for Weak Accept / Accept territory

### B6. Two-model replication of the large context study

The 384-subject experiment should not remain one-model-only.

### B7. Malformed-output decomposition

The 6.36% malformed-output aggregate must be stratified by context condition and error class, with a prespecified retry/repair sensitivity analysis.

### B8. Canonicalization conformance

The latest branch uses a versioned RFC 8785 profile, which must be reflected in both test vectors and manuscript wording.

### B9. Public formal-assurance artifact

The branch already exposes the bounded model. A new sealed run should make the full state model, invariants, bounds, and state/transition counts inspectable.

## 1.3 P2 enhancers — valuable but not required for the narrow systems claim

- richer production-like performance benchmarking;
- independent externally sourced longitudinal cases;
- clinician adjudication for model-utility endpoints;
- official third-party implementation comparisons where runnable assets exist.

These are publication strengtheners, not excuses to delay the P0 experiments.

---

# 2. Source-of-truth branch and code synchronization contract

## 2.1 Authoritative branch

All new work defined by this specification starts from:

```text
branch: codex/commitloop-phase-a
sha:    81f040d3e05905cc384239c5ae130f629e722d3e
```

A dedicated experiment branch SHOULD be cut from that exact SHA, e.g.:

```text
research/glhs-q2-r2-experiments
```

The Q2-R2 freeze must record the actual final execution SHA, which may be later than the audit SHA if implementation changes are required.

## 2.2 No mixing of historical and R2 evidence

The following historical artifacts remain immutable and must not be overwritten:

- `research/glhs_journal/binding_only_ablation/`
- `research/glhs_journal/concurrency_repetition_v1/`
- `research/glhs_journal/protocol_v2/`
- `research/glhs_journal/protocol_v2_r3_20260819_02/`
- `research/glhs_journal/malformed_audit_v1/`
- any sealed `artifacts/glhs-postgres-toctou/*`
- any CommitLoop v5 run previously exposed to results.

Every R2 experiment writes to a new directory.

## 2.3 Required paper/code synchronization audit

Before any new experiment execution, create:

```text
research/glhs_journal/q2_r2/paper_code_sync/
  implementation_contract.json
  manuscript_contract.json
  diff_report.md
  synchronization_decisions.json
  checksums.sha256
```

The audit MUST resolve at least these known branch/manuscript differences:

1. **Canonicalization:** latest branch defaults new writes to `clara.canonical-json.v2-rfc8785`; manuscript wording must not continue to describe only the old custom v1 profile.
2. **Formal assurance:** latest branch exposes `evaluation/formal_governance/{model,transitions,invariants,explore}.py`; manuscript must not claim the model is unavailable if this remains true at the final execution SHA.
3. **Inference binding:** latest branch includes `GlhsInferenceContextBinding` and anti-laundering/root-proposal logic; the paper's threat/model description must reflect the implemented path actually evaluated.
4. **Dependency vector:** latest branch has persisted proposal dependencies and a dependency-vector digest; the formal proposal tuple should align with the final implementation semantics.
5. **Commit kernel:** latest branch implements a six-phase atomic commit kernel with explicit lock hierarchy; Methods must describe the final evaluated path, not an older gateway-only path.

No experiment may become claim-bearing until `diff_report.md` has no unresolved **MATERIAL_TO_CLAIM** discrepancy.

---

# 3. Existing branch inventory: reuse, upgrade, or add

## 3.1 Production GLHS components to reuse

| Component | Latest-branch location | R2 role |
|---|---|---|
| THSS / snapshot validation | `services/api/src/clara_api/glhs/gateway.py` | production truth for snapshot semantics |
| Canonical JSON | `services/api/src/clara_api/glhs/canonical_json.py` | digest protocol and vectors |
| Atomic commit kernel | `services/api/src/clara_api/glhs/commit_kernel.py` | production transaction boundary |
| Clinical commitment gateway | `services/api/src/clara_api/glhs/commitment_gateway.py` | snapshot-bound / lineage admission |
| Exact evidence handling | `commitment_evidence.py` | provenance closure |
| Commitment THSS | `commitment_thss.py` | model-facing governed disclosure |
| Proposal lineage/reconciliation | `commitment_reconciliation.py` | anti-laundering tests |
| Lock hierarchy | `lock_hierarchy.py` | concurrency instrumentation |
| Predicate DSL | `predicate_dsl.py` | schema/operation dependency derivation candidates |
| Entity partitions | DB models + gateway/kernel | dependency completeness + concurrency |

## 3.2 Existing experiment packages to reuse directly

- `evaluation/glhs_binding_only_ablation/`
- `evaluation/contract_clause_ablation/`
- `evaluation/glhs_postgres_toctou/`
- `evaluation/formal_governance/`
- `evaluation/contention_analysis/`
- `evaluation/fullstack_benchmark/`
- `evaluation/property_assurance/`
- `evaluation/evidence_program/`
- `evaluation/commitloop/`
- `evaluation/comparator_studies/`
- `evaluation/external_validation/`
- `evaluation/model_adjudication/`

## 3.3 Existing infrastructure that must be upgraded rather than presented as new evidence

### Binding-only ablation

Keep the frozen historical two-arm experiment intact. Add a new **component-factorial** experiment under a new package. Do not mutate `schedules.json` or the old protocol.

### TOCTOU

Reuse the real PostgreSQL executor, governance writers, barriers, commit-order observers, jitter framework, DAG benchmark, and Zipfian benchmark. Add a new schedule generator and a new R2 freeze; do not relabel the 12 historical schedules.

### Formal governance

Reuse the public Python model but add a reproducibility manifest, explicit bounds, invariant-to-code mapping, and a sealed result.

### CommitLoop / model utility

Reuse cohort/freeze/reproduce machinery, but create a new R2 freeze if any prior v5 cohort or result has been unblinded. Do not append a second model to an already unblinded confirmatory freeze unless the original protocol explicitly allowed that model and no result-dependent changes occurred.

---

# 4. Unified Q2-R2 experiment architecture

Create a new top-level research namespace:

```text
research/glhs_journal/q2_r2/
  README.md
  program_manifest.json
  claim_to_evidence.csv
  statistics_plan.json
  publication_claims.yaml
  paper_code_sync/
  protocols/
    E01_binding_components/
    E02_minimal_baseline/
    E03_downgrade/
    E04_randomized_toctou/
    E05_toctou_root_cause/
    E06_dependency_completeness/
    E07_canonicalization/
    E08_formal_assurance/
    E09_concurrency/
    E10_fullstack/
    E11_model_replication/
    E12_malformed_sensitivity/
    E13_external_validation/
  release/
    release_manifest.json
    artifact-sha256.json
    reproduction_report.json
    manuscript_update_map.md
```

Runtime artifacts go outside the tracked research protocol tree:

```text
artifacts/glhs-q2-r2/<program-run-id>/
  E01_binding_components/
  E02_minimal_baseline/
  ...
  E13_external_validation/
  combined_analysis/
  release/
```

## 4.1 Program-run ID

Use a non-reusable identifier such as:

```text
GLHS-Q2-R2-20260927-R01
```

Any rerun caused by code/protocol changes gets `R02`, `R03`, etc. Never reuse a run ID.

## 4.2 Experiment artifact contract

Every experiment directory MUST contain:

```text
protocol.json
protocol.sha256
environment.json
code_manifest.json
raw/
derived/
validation.json
checksums.sha256
run_status.json
```

`run_status.json` allowed states:

- `NOT_RUN`
- `RUNNING_INCOMPLETE`
- `EXECUTED_UNSEALED`
- `EXECUTED_VALIDATION_FAILED`
- `SEALED_DESCRIPTIVE`
- `SEALED_CLAIM_ELIGIBLE`

Missing experiments are never encoded as zero failures.

## 4.3 Immutability rules

- A sealed raw file is never edited.
- Analysis is derived from raw artifacts into a separate directory.
- If analysis code changes, generate a new derived bundle and record both hashes.
- If protocol or implementation code changes, use a new experiment run ID.
- Provider/model outputs are immutable once collected.
- Human adjudication preserves original labels and stores adjudicated labels separately.

---

# 5. Global statistics plan

## 5.1 General principles

1. Deterministic conformance suites report exact numerator/denominator and coverage first.
2. Repeated timing perturbations of the same logical schedule are not independent scientific units.
3. Exact McNemar/sign tests are secondary summaries of paired schedule discordance, not population attack-frequency estimators.
4. Bootstrap units must match the scientific unit: logical schedule or subject, never API call when multiple calls belong to one subject.
5. Equivalence is claimed only when the complete confidence interval lies inside the prespecified margin.
6. Provider latency is causal only if run order/load is controlled; otherwise label it descriptive/associated.
7. No adaptive expansion after seeing confirmatory results unless the new run is explicitly labeled exploratory and frozen separately.

## 5.2 Multiple-comparison families

Predeclare separate Holm families:

- **F-BIND:** component-binding pairwise contrasts;
- **F-BASE:** GLHS vs minimal alternative baselines;
- **F-TOCTOU:** prespecified randomized schedule-family contrasts;
- **F-MODEL:** model-context condition comparisons within each model family.

Do not Holm-adjust across unrelated evidence classes.

## 5.3 Primary manuscript endpoints

### Software-governance primary

- invalid persistent-write acceptance per logical schedule;
- valid-control acceptance;
- forbidden commit occurrence;
- required-dependency omission acceptance;
- downgrade-path acceptance.

### Secondary systems

- false-stale rejection;
- true-stale rejection;
- deadlock / serialization failure;
- validation latency;
- throughput;
- lock-wait time.

### Model-context

- subject-level all-axes exact;
- malformed-output rate;
- critical omission;
- unsupported assertion;
- input tokens;
- output tokens;
- latency/cost descriptive endpoints.

---

# 6. E00 — paper/code synchronization and preflight

**Priority:** P0  
**Purpose:** ensure the final experiments test the system actually described by the revised paper.

## 6.1 Tasks

1. Freeze branch head and source hashes.
2. Inventory all production snapshot-bound write paths.
3. Inventory all model/AI-to-persistent-write routes.
4. Generate AST/static-call graph for GLHS commit entry points.
5. Compare implementation coordinates against manuscript equations.
6. Update proposed Methods wording in `manuscript_update_map.md`, but do not change reported results yet.
7. Run unit/integration baseline.

## 6.2 Required preflight tests

```bash
git status --porcelain
git rev-parse HEAD
make lint
make type-check
make test
```

Then run GLHS-specific suites:

```bash
PYTHONPATH=services/api/src:. services/api/.venv/bin/python -m pytest -q \
  services/api/tests/test_glhs* \
  evaluation/property_assurance \
  evaluation/formal_governance/tests \
  evaluation/glhs_binding_only_ablation/tests \
  evaluation/glhs_postgres_toctou/tests
```

## 6.3 Acceptance gate

`E00` passes only if:

- final execution SHA is recorded;
- worktree is clean at freeze;
- all claimed production paths are inventoried;
- no material paper/code discrepancy is unresolved;
- baseline tests pass or every unrelated pre-existing failure is documented and isolated.

---

# 7. E01 — component-wise exact-binding ablation

**Priority:** P0 / highest scientific priority  
**Reviewer question answered:** Which exact-binding components are necessary, sufficient, or redundant?

## 7.1 New package

Create:

```text
evaluation/glhs_binding_component_ablation/
  __init__.py
  README.md
  binding_mask.py
  build_schedules.py
  protocol.schema.json
  protocol.json
  schedules.json
  adapter.py
  postgres_runner.py
  observer.py
  analyze.py
  validate.py
  seal.py
  tests/
```

Do not modify the historical `glhs_binding_only_ablation` protocol.

## 7.2 Factorial arms

Use a 2³ factorial over the three core binding dimensions:

| Arm | Snapshot identity | Content/manifest digest | Evidence/provenance membership |
|---|---:|---:|---:|
| B000 | off | off | off |
| B100 | on | off | off |
| B010 | off | on | off |
| B001 | off | off | on |
| B110 | on | on | off |
| B101 | on | off | on |
| B011 | off | on | on |
| B111 | on | on | on |

The following are held constant in all arms:

- base state/version validation;
- actor/role/purpose/task checks;
- current policy validation;
- current consent validation;
- snapshot expiry check where the family is not explicitly testing expiry;
- DB lock ordering;
- idempotency;
- proposal lineage rules;
- ordinary provenance/audit.

This isolates the marginal and interaction contribution of identity, digest, and evidence-membership binding.

## 7.3 Component-discriminating attack families

Freeze at least these families:

1. **ID-SUB:** same current coordinates, substitute another valid snapshot ID with otherwise equivalent content.
2. **DIGEST-MUT:** same snapshot ID, mutate committed payload/manifest representation in the evaluation fixture so digest mismatch is the only distinguishing condition.
3. **EVIDENCE-OUTSIDE:** proposal provenance cites evidence absent from disclosed set while other coordinates remain valid.
4. **MIN-SET-SWAP:** substitute a less-minimized / differently minimized evidence set under matching state version.
5. **CROSS-SNAPSHOT-SAME-VERSION:** valid snapshots share state version but differ in governed disclosure.
6. **COORD-SUB:** actor/purpose/task coordinate substitution while current authorization is otherwise admissible.
7. **LINEAGE-ROOT-SUB:** reviewed/adapted child proposal points to a different root disclosure.
8. **EXPIRY-CONTROL:** expired disclosure; used primarily as a validity-control family rather than a component identifier.
9. **CLEAN:** legitimate proposal/control.

## 7.4 Sample design

Minimum confirmatory design:

- 32 unique adversarial logical schedules per attack family for the 7 binding-targeted families = 224;
- 32 expiry/control schedules;
- 96 clean controls distributed across realistic coordinate combinations;
- total unique schedules ≥352;
- each schedule executed across all eight component arms.

This produces ≥2,816 arm-schedule executions while preserving the logical schedule as the scientific unit.

A smaller development corpus may be used before freeze, but the confirmatory holdout must be generated with a distinct seed and sealed before execution.

## 7.5 Implementation rule

All ablation masks MUST exist under `evaluation/` only. Production code may expose validation primitives, but no production feature flag may disable individual security clauses.

`adapter.py` should call production validation primitives and selectively omit checks only in the evaluation adapter.

Add a static validator that scans `services/**` for forbidden research-only names such as:

```text
disable_exact_binding
binding_mask
skip_snapshot_digest
no_evidence_binding
component_ablation
```

## 7.6 Analysis

Primary output:

- exact invalid acceptance by family × arm;
- exact clean acceptance by arm;
- component necessity table;
- pairwise discordance versus B111;
- factorial main effects and interactions as descriptive schedule-level effects.

Do **not** claim real-world attack prevalence.

## 7.7 Acceptance criterion

E01 is claim-eligible only if:

- every planned schedule is present exactly once per arm;
- no production disable flag exists;
- all controls and mutations are mechanically validated;
- results are sealed before manuscript interpretation;
- analysis distinguishes “necessary for these families” from “globally minimal”.

---

# 8. E02 — minimal alternative-design baseline

**Priority:** P0  
**Reviewer question answered:** Could a simpler immutable token/read-set mechanism satisfy the same invariant?

## 8.1 New baseline: `MIN_READSET_TOKEN`

Create:

```text
evaluation/comparator_studies/minimal_readset_token/
  METHOD_CARD.md
  SOURCE_MAPPING.md
  DEVIATIONS.md
  schema.json
  token.py
  validator.py
  postgres_adapter.py
  tests/
```

The baseline is intentionally **not branded as a new system**. It is an experimental minimal construction.

## 8.2 Token schema

A token contains only the fields necessary to test a compact alternative:

```json
{
  "schema": "minimal-readset-token.v1",
  "profile_id": "...",
  "actor_id": "...",
  "actor_role": "...",
  "purpose": "...",
  "task": "...",
  "snapshot_id": "...",
  "snapshot_digest": "...",
  "evidence_commitment": "...",
  "state_dependencies": [
    {"key": "domain:semantic_key", "observed_version": 12}
  ],
  "policy_version": "...",
  "consent_version": "...",
  "expires_at": "..."
}
```

Canonical token bytes use the same final canonicalization profile as GLHS to avoid serialization being the confounder.

## 8.3 Optional signed variant

Add a secondary `HMAC_READSET_TOKEN` using an experiment-only server key to answer the “signed token” reviewer objection.

Do not use HMAC results to imply resistance to full server compromise. Its purpose is integrity/authentication across an untrusted transport, not protection when the trusted admission server itself is compromised.

## 8.4 Evaluation

Run the identical E01 schedule corpus against:

- GLHS B111 full binding;
- `MIN_READSET_TOKEN`;
- optional `HMAC_READSET_TOKEN`.

Keep current-state/current-governance revalidation identical.

Record:

- accept/reject decision;
- reason code;
- false acceptance;
- false rejection;
- serialized metadata bytes;
- validation CPU time;
- DB reads/writes;
- implementation code size as descriptive only, not scientific quality score.

## 8.5 Interpretation policy

Possible outcomes:

### If minimal baseline matches GLHS exactly

Allowed conclusion:

> The experiment suggests the Exact-Disclosure Admission Invariant does not require the complete GLHS representation; a compact read-set/disclosure token can enforce the same tested property. GLHS should therefore be understood as a health-governance realization of the invariant rather than its unique implementation.

This is scientifically valuable and improves honesty.

### If GLHS catches schedules the minimal baseline misses

The manuscript must identify the exact additional semantic coordinate responsible; do not claim generic superiority.

### If the baseline rejects more valid controls

Report the false-rejection tradeoff.

---

# 9. E03 — downgrade and lineage anti-laundering experiment

**Priority:** P0  
**Reviewer question answered:** Can a model-derived or THSS-derived proposal silently escape to a weaker admission path?

## 9.1 Route inventory

Build a static inventory of every call to:

- `propose_assertion`;
- commitment proposal creation;
- `apply_transition`;
- `execute_atomic_glhs_commit`;
- commitment review/adaptation;
- any route producing persistent state from AI/model output.

Output:

```text
route_inventory.json
route_inventory.md
```

Each entry records:

- module/function;
- origin types accepted;
- whether THSS can be consumed;
- required binding mode;
- root proposal handling;
- dependency source;
- persistence target.

## 9.2 Negative schedules

At minimum test:

1. `proposal_consumed_thss=true` with no snapshot binding.
2. Snapshot-bound parent → base-version-only child.
3. Snapshot-bound parent → reviewed proposal with changed snapshot.
4. Snapshot-bound parent → reviewed proposal with missing root lineage.
5. Root snapshot A → child claims snapshot B.
6. Model-originated generic assertion direct write.
7. Model output passed through a user-review adapter without preserving binding.
8. Cross-profile snapshot laundering.
9. Reuse of expired bound parent through a fresh child.
10. Dependency-vector override after proposal seal.

## 9.3 Primary endpoint

`downgrade_success = persistent state mutated through a path weaker than the strongest required binding semantics for the proposal lineage`.

Target for all frozen negative schedules: **0 downgrade successes**.

If any known legitimate workflow requires base-version-only semantics, it must be classified as **NON_THSS_ORIGIN** and mechanically prevented from accepting a THSS-origin lineage.

---

# 10. E04 — generated PostgreSQL governance/TOCTOU campaign

**Priority:** P0  
**Reviewer question answered:** Does commit-time revalidation remain safe beyond twelve hand-authored schedules?

## 10.1 New package

Create:

```text
evaluation/glhs_toctou_r2/
  grammar.py
  generator.py
  oracle.py
  schedule_schema.json
  freeze.py
  executor.py
  observer.py
  shrink.py
  analyze.py
  validate.py
  tests/
```

Reuse low-level primitives from `evaluation/glhs_postgres_toctou` rather than duplicating barriers, jitter, commit-order observation, or governance writers.

## 10.2 Schedule grammar

A logical schedule is composed from:

### Disclosure event

- compile THSS;
- persist inference binding;
- optionally create proposal.

### Governance/state writers

- consent revoke;
- consent regrant as a new event/version;
- actor role downgrade;
- actor role restoration;
- policy epoch advance;
- state entity update;
- evidence/source revocation;
- snapshot expiry boundary;
- dependency-partition update;
- compound governance + state change.

### Proposal/commit actions

- proposal before writer, commit after writer;
- proposal concurrent with writer;
- proposal after writer but based on pre-writer THSS;
- retry after safe abort;
- reviewed/adapted proposal;
- two simultaneous proposals sharing dependencies;
- disjoint proposal vs unrelated writer.

### Timing relation

Each pair is labeled as one of:

- `A_BEFORE_B` — barrier establishes strict order;
- `B_BEFORE_A`;
- `OVERLAP` — no serial order assumed;
- `CONTROL_NO_DRIFT`.

## 10.3 Oracle rules

For strictly ordered schedules, expected safety classification is deterministic.

For overlap schedules, freeze an **admissible outcome set** instead of forcing one ordering, e.g.:

```json
{
  "allowed": [
    "writer_commits_then_proposal_rejected",
    "proposal_commits_then_writer_commits"
  ],
  "forbidden": [
    "proposal_commits_after_observed_governance_change_using_stale_context"
  ]
}
```

This directly avoids repeating the historical V2-05/V2-09 classification problem.

## 10.4 Confirmatory corpus

Recommended minimum:

- 1,024 unique logical schedules in confirmatory holdout;
- balanced across major drift families;
- ≥25% compound/multi-coordinate schedules;
- ≥25% overlap schedules;
- ≥15% disjoint controls;
- distinct development and confirmatory seeds.

For each unique schedule:

- one primary deterministic/barrier execution;
- optional 5 jitter repetitions for robustness, clearly nested under the same logical schedule ID.

Scientific N = unique logical schedules.

## 10.5 Failure shrinking

If a generated schedule produces a forbidden outcome:

1. preserve the raw failing schedule;
2. run a deterministic shrinker to find a minimal reproducer;
3. never replace the original failure with the shrunk case;
4. classify as implementation bug, oracle bug, or observer ambiguity only after independent review of trace.

## 10.6 Recorded trace

Each execution records sanitized:

- run/schedule ID;
- process/thread/session IDs;
- PostgreSQL transaction IDs if available;
- barrier timestamps;
- lock acquisition sequence;
- observed policy/consent/state/dependency versions before and under lock;
- proposal/snapshot IDs hashed or opaque;
- validation reason;
- commit outcome;
- governance-writer outcome;
- happens-before relation;
- audit transition linkage;
- forbidden-commit boolean.

No patient-like text or secrets are written.

---

# 11. E05 — historical TOCTOU mismatch root-cause replay

**Priority:** P0  
**Target cases:** `TOCTOU-V2-05`, `TOCTOU-V2-09`

## 11.1 Rule

Do not edit or reinterpret the old sealed artifacts.

Create new replay IDs:

```text
GLHS-Q2-R2-E05-V2-05-REPLAY-01
GLHS-Q2-R2-E05-V2-09-REPLAY-01
```

## 11.2 Instrumentation

For each case capture:

- exact frozen old schedule semantics;
- latest-branch semantic mapping;
- transaction start/lock/validation/commit timestamps;
- lock graph;
- observed policy/consent/state values;
- old expected classification;
- new admissible-outcome classification;
- exact reason the historical expectation was too strict or implementation behavior changed.

Run at least 100 timing perturbations per case **descriptively**, not as 200 new independent schedules.

## 11.3 Required output

```text
root_cause.json
root_cause.md
trace_examples.jsonl
classification_reconciliation.md
```

The manuscript should say whether the mismatch came from:

- an oracle classification design error;
- observer ambiguity;
- changed implementation semantics;
- or a true implementation defect.

---

# 12. E06 — dependency-completeness contract and omission mutations

**Priority:** P0  
**Reviewer question answered:** How do we know `Deps(P)` contains everything the operation semantically depends upon?

## 12.1 Production design change

Create or formalize a central dependency contract, preferably:

```text
services/api/src/clara_api/glhs/dependency_contract.py
```

Conceptual API:

```python
@dataclass(frozen=True)
class OperationDependencyContract:
    operation_kind: str
    required_entity_reads: tuple[DependencyRule, ...]
    required_entity_writes: tuple[DependencyRule, ...]
    required_governance: tuple[DependencyRule, ...]
    required_evidence: tuple[DependencyRule, ...]


def derive_required_dependencies(operation: OperationDescriptor) -> tuple[DependencySpec, ...]: ...

def validate_dependency_completeness(
    *,
    required: Sequence[DependencySpec],
    declared: Sequence[DependencySpec],
) -> None: ...
```

## 12.2 Design principle

The LLM does not freely decide the safety-critical dependency set.

Preferred hierarchy:

1. operation schema derives required write target dependencies;
2. application service derives known read dependencies;
3. snapshot/provenance records contribute evidence dependencies;
4. governance policy contributes policy/consent dependencies;
5. model-provided references may **add** dependencies, never remove required dependencies.

## 12.3 Dependency closure modes

Support two production modes:

- `EXACT_REQUIRED`: declared must contain all required dependencies;
- `CONSERVATIVE_SUPERSET`: extra dependencies allowed; required subset must still be present.

Use `CONSERVATIVE_SUPERSET` as the default safety mode.

## 12.4 Mutation experiment

Create:

```text
evaluation/glhs_dependency_completeness/
  operation_catalog.json
  generate_cases.py
  mutate_dependencies.py
  postgres_runner.py
  analyze.py
  validate.py
  tests/
```

For every operation family:

- generate a complete dependency vector;
- create one mutant per required dependency omitted;
- create pairwise omission mutants;
- create stale-version mutants;
- create wrong-kind/wrong-key mutants;
- include complete controls and conservative-superset controls.

Operation families should include at least:

- single-entity medication update;
- medication update dependent on allergy/condition;
- conflict resolution across two assertions;
- multi-entity reconciliation;
- consent-sensitive proposal;
- policy-sensitive proposal;
- evidence-backed commitment;
- reviewed/adapted child proposal.

## 12.5 Write-skew scenarios

Construct classic write-skew style cases:

- proposal reads A and B, writes A, but B changes;
- proposal reads A and B, writes C, but A changes;
- two proposals each read both A/B and write disjoint targets;
- policy/consent dependency omitted while entity versions remain current.

A commit is forbidden if an omitted required dependency changes before admission.

## 12.6 Primary endpoints

- omission detection rate;
- forbidden commit rate under omission mutation;
- valid-control acceptance;
- conservative-superset false-stale rate.

The target is zero accepted mutants that violate the derived dependency contract.

---

# 13. E07 — canonicalization conformance and cross-runtime vectors

**Priority:** P1, but required for paper/code synchronization  
**Current latest-branch basis:** `clara.canonical-json.v2-rfc8785` for new writes.

## 13.1 Artifacts

Create:

```text
testdata/glhs/canonicalization/v2/
  vectors.json
  expected.json
  vectors.sha256
  README.md
```

## 13.2 Required vector categories

- ASCII key ordering;
- Unicode key ordering per final profile;
- escaped control characters;
- astral Unicode;
- lone-surrogate rejection;
- integers at I-JSON safe boundary;
- integer outside safe boundary rejection if required by implementation;
- decimal/float representation;
- exponent normalization;
- positive/negative zero;
- NaN/Infinity rejection;
- nested objects;
- arrays preserving order;
- datetimes after explicit UTC normalization;
- timezone-naive datetime rejection;
- sets/frozensets according to production rules;
- unsupported custom objects;
- empty structures.

## 13.3 Independent verification

Where feasible, verify JSON-native vectors against an independent RFC 8785 implementation in Node/JavaScript or another language.

Python-only pre-normalization extensions such as datetime handling must be clearly identified as **GLHS preprocessing semantics**, not part of RFC 8785 itself.

## 13.4 Migration compatibility

Test validation of historical snapshots created under:

- legacy Python profile;
- custom v1 profile;
- v2 RFC8785 profile.

New writes use the current profile; old rows remain verifiable under their recorded profile.

---

# 14. E08 — sealed bounded formal assurance

**Priority:** P1  
**Existing implementation:** `evaluation/formal_governance/`.

## 14.1 Goal

Turn the existing inspectable Python state model into a publication-grade bounded assurance artifact without claiming universal proof.

## 14.2 Required documentation

Add:

```text
evaluation/formal_governance/SPECIFICATION.md
evaluation/formal_governance/REFINEMENT_MAP.md
```

`SPECIFICATION.md` defines:

- state variables;
- value domains;
- transitions;
- actor cardinality bounds;
- evidence-universe bounds;
- version bounds;
- schedule depth;
- terminal states;
- fairness assumptions, if any.

`REFINEMENT_MAP.md` maps each model predicate to concrete production code.

## 14.3 Invariant mapping

At minimum map all 11 invariants. The published report should include:

| Invariant | Formal statement | Model checker | Production enforcement | Dynamic test |
|---|---|---|---|---|
| I1 | no stale-base bound commit | `invariants.py` | commit kernel | TOCTOU/property test |
| I2 | no post-revocation commit | ... | consent lock/revalidation | ... |
| I3 | no wrong coordinate | ... | proposal/snapshot checks | ... |
| I4 | no expired/tampered snapshot | ... | snapshot validation | ... |
| I5 | no undisclosed evidence | ... | exact dependency validation | ... |
| ... | ... | ... | ... | ... |

## 14.4 Confirmatory exploration

Run the current published bounds at minimum:

- depth 5;
- depth 6.

Run depth 7 only if computationally practical and if no model change is made in response to depth-5/6 results before re-freeze.

Record:

- unique states;
- transitions;
- violations per invariant;
- runtime/memory;
- exact source SHA;
- Python/platform;
- model file hashes.

## 14.5 Mutation validation

For each enforceable invariant, create at least one model mutation that should violate it and demonstrate that the checker catches the violation. This avoids a vacuous “zero violations” result caused by unreachable bad states or broken checks.

---

# 15. E09 — realistic concurrency and dependency-partition benchmark

**Priority:** P1  
**Reuse:** DAG benchmark, Zipfian benchmark, contention runner.

## 15.1 Purpose

Replace the simplistic synchronized `(W-1)/W` contention sanity check with a broader systems characterization.

## 15.2 Factors

### Concurrency

```text
1, 2, 4, 8, 16, 32, 64
```

128 may be included if the environment remains stable, but is not mandatory.

### Hot-key distribution

- uniform;
- Zipf θ = 0.8;
- Zipf θ = 1.1;
- Zipf θ = 1.4.

### Dependency overlap

```text
0%, 10%, 25%, 50%, 75%, 100%
```

### Multi-entity width

```text
1, 2, 4, 8 dependencies per operation
```

### Workload mix

- 90/10 read-like validation/write;
- 70/30;
- 50/50.

## 15.3 Compared strategies

Use production-realistic strategies only:

- profile-global version;
- entity-partitioned dependency OCC;
- if already implemented and stable, dependency-hybrid strategy.

Do not compare simulated third-party systems as if they were measured production implementations.

## 15.4 Metrics

- successful commits;
- true-stale aborts;
- false-stale aborts;
- serialization failures;
- deadlocks;
- retries;
- lock wait;
- p50/p95/p99 transaction latency;
- throughput;
- CPU/RSS;
- DB reads/writes.

## 15.5 Repetitions

Use ≥5 independent run repetitions per frozen workload cell after warm-up. Report across-run distribution; do not treat individual transactions as independent evidence of architecture-level superiority.

---

# 16. E10 — full-stack performance characterization

**Priority:** P2 unless performance remains prominent in the manuscript.

## 16.1 Existing service-layer benchmark

Keep current `evaluation/fullstack_benchmark/run_postgresql.py` as the service-layer measurement.

## 16.2 Add real HTTP boundary harness

Create:

```text
evaluation/fullstack_benchmark/run_http.py
```

Path:

```text
client → FastAPI HTTP → auth/scope → GLHS/THSS/GST → PostgreSQL → response/audit
```

## 16.3 Workload

After warm-up, collect sufficiently large samples, e.g.:

- at least 500 operations per operation class; or
- fixed steady-state windows with ≥5 independent repetitions.

Operations:

- compile strict THSS;
- create bound proposal;
- validate/commit proposal;
- stale proposal rejection;
- consent-revocation rejection;
- reconstruct current state;
- reconstruct governed decision;
- audit lookup;
- invalidate/rebuild.

## 16.4 Reporting

Report environment and capacity descriptively. Avoid claims such as “production-ready” unless deployment workload and SLOs are independently justified.

---

# 17. E11 — prospective two-model large context-utility replication

**Priority:** P1  
**Reviewer question answered:** Does the large-context result generalize beyond one model family?

## 17.1 Do not contaminate prior freezes

If the old 384-subject cohort/result has already been inspected, do not convert it into a new confirmatory two-model run by appending Gemini after the fact.

Create a new protocol version, e.g.:

```text
protocols/commitloop/v8-glhs-q2-r2/
```

Reuse the v5 freeze/reproduce architecture, not necessarily its exact cohort.

## 17.2 Models

Lock two genuinely distinct families:

- `claude-sonnet-4.6` or the exact provider-resolved equivalent available at freeze;
- `gemini-3.6-flash-high` or the exact provider-resolved equivalent available at freeze.

Returned model IDs must match the frozen allowed IDs. No fallback.

## 17.3 Minimal confirmatory comparison

For cost efficiency, the **primary** confirmatory grid may focus on:

- Strict THSS;
- full authorized history.

Secondary contexts may run only if budget permits and are frozen separately.

For N subjects and 2 models × 2 primary conditions:

```text
provider calls = N × 2 × 2
```

If N=384, primary-only = 1,536 calls.

If the full nine-context grid is retained:

```text
N × 2 × 9
```

At N=384 = 6,912 calls.

## 17.4 Sample-size design

Before freeze:

1. Use historical discordance/tie rate only for planning.
2. Compute required N for the prespecified ±2 percentage-point equivalence margin.
3. Freeze N before any provider calls.
4. If 384 is underpowered given tie structure, increase N prospectively rather than pretending 384 is adequate.

## 17.5 Request randomization

To reduce provider-load confounding:

- randomize subject order;
- randomize condition order within subject;
- interleave paired conditions;
- alternate models in bounded blocks;
- record wall-clock/provider region if exposed;
- record cache/request identifiers only if non-sensitive and permitted.

## 17.6 Primary endpoints

- subject-level all-axes exact;
- paired difference Strict THSS − full history;
- 95% subject-bootstrap CI;
- TOST/equivalence test for ±2 pp if powered and prespecified.

## 17.7 Secondary endpoints

- malformed rate by condition/model;
- input/output tokens;
- provider latency association;
- provider cost;
- per-axis accuracy;
- evidence fidelity.

## 17.8 Claim rule

A non-significant difference is never described as equivalence. Equivalence requires the entire confidence interval within the frozen margin and the prespecified equivalence procedure to pass.

---

# 18. E12 — malformed-output taxonomy and retry/repair sensitivity

**Priority:** P1  
**Reuse:** `research/glhs_journal/malformed_audit_v1/` taxonomy parser.

## 18.1 Prospective error taxonomy

At minimum:

- empty response;
- non-JSON response;
- truncated JSON;
- syntactically invalid JSON;
- schema-missing field;
- wrong enum/value type;
- extra prohibited field;
- provider refusal/policy block;
- provider transport error;
- wrong model/fallback;
- timeout;
- valid schema but semantically invalid prediction.

## 18.2 Primary scoring

Preserve intent-to-treat primary scoring:

> Any malformed output is a failure.

Do not repair primary results post hoc.

## 18.3 Prespecified sensitivity arms

For every malformed primary output, evaluate offline or in a separate prospective recovery ledger:

### R0 — no repair

Primary ITT result.

### R1 — deterministic local extraction/normalization

No model call. Only transformations defined before run.

### R2 — one identical-prompt same-model retry

Exactly one retry, same model, same prompt, same response schema.

### R3 — one constrained repair prompt

Optional and clearly secondary; frozen repair prompt, same model family.

## 18.4 Outputs

Report by model × context condition:

- malformed numerator/denominator;
- taxonomy counts;
- recovery rate R1/R2/R3;
- corrected task score only as sensitivity;
- whether the Strict-vs-full-history effect materially changes.

---

# 19. E13 — external / independent validation

**Priority:** P2 for the current narrow systems claim; P1 if submitting to a clinically oriented health-informatics journal.

## 19.1 External structured cohort

Reuse `evaluation/external_validation` only with lawful, curator-owned derived artifacts.

Allowed evidence classes:

- Synthea as external synthetic structural data;
- MIMIC Demo / MIMIC-on-FHIR derived deidentified tasks where permitted;
- separately curated real-EHR derived tasks when access/governance allows.

Never combine synthetic governance perturbations with real clinical ground truth under one headline score.

## 19.2 Independent human review

For clinical/task labels:

- two independent qualified annotators;
- one separate adjudicator;
- blinded system identity;
- frozen annotation guide;
- original labels preserved;
- disagreement and kappa reported;
- no model-as-clinician surrogate described as human validation.

## 19.3 Publication role

Use external validation to support transportability/construct validity, not to change the primary software-governance claim.

---

# 20. Comparator policy

## 20.1 Allowed comparator classes

### Class A — exact executable implementation

May be used numerically if:

- official implementation is runnable;
- version is pinned;
- task mapping is defensible;
- configuration is public;
- adapter code is published.

### Class B — mechanism-mapped comparator

May be used for semantic/property comparison if clearly labeled as a project implementation rather than faithful reproduction.

### Class C — reference-only literature

No numerical result. Used only in property matrix/related work.

## 20.2 Existing branch comparator assets

- standards-composed baseline: Class B;
- BTSA mapping: Class B;
- Vital Trace mapping if no official runnable implementation: Class B or C;
- GraphRAG only after official asset gate: Class A for retrieval questions, but not necessarily for the exact write-admission problem;
- simulated FHIR/MemTX/CommitGuard/etc. in `peer_transactional_baselines.py`: **simulation evidence only**, never headline “system X vs GLHS performance”.

## 20.3 New minimal baseline

`MIN_READSET_TOKEN` is intentionally Class B but is the strongest **novelty isolation** comparator because it is designed to satisfy the same invariant with minimal machinery.

---

# 21. Reproducibility, freeze, seal, and release design

## 21.1 Global program manifest

`program_manifest.json` must bind:

```json
{
  "schema_version": "glhs-q2-r2-program.v1",
  "status": "FROZEN",
  "git_sha": "...",
  "branch": "research/glhs-q2-r2-experiments",
  "base_audit_sha": "81f040d3e05905cc384239c5ae130f629e722d3e",
  "statistics_plan_sha256": "...",
  "publication_claims_sha256": "...",
  "experiments": {
    "E01": {"protocol_sha256": "..."},
    "E02": {"protocol_sha256": "..."}
  }
}
```

## 21.2 Environment manifest

Capture:

- OS/kernel;
- CPU model/count;
- RAM;
- Python version;
- dependency lock hashes;
- Docker image digests;
- PostgreSQL exact version;
- DB settings affecting isolation/locking;
- locale/timezone;
- provider/model manifest;
- network region if known;
- Git SHA;
- dirty-worktree status.

Never store credentials or DB URLs containing secrets.

## 21.3 Analysis isolation

All final statistical analysis should be reproducible with network disabled.

Pattern:

```bash
python -m evaluation.glhs_q2_r2.reproduce \
  --sealed-run artifacts/glhs-q2-r2/<run-id> \
  --output /tmp/glhs-r2-reproduction
```

The reproduction command should regenerate:

- tables;
- JSON statistics;
- CSV derived metrics;
- publication figures;
- manuscript-result macros;

from raw sealed artifacts only.

## 21.4 Release gate

Create:

```text
evaluation/evidence_program/glhs_q2_r2_release_gate.py
```

It refuses release if:

- a required P0 experiment is missing;
- any required artifact hash mismatches;
- a headline result was derived from `NOT_RUN` rows;
- a manuscript claim lacks claim-ledger evidence;
- the paper-code synchronization report has unresolved material mismatches;
- confirmatory model freeze was modified after provider calls;
- code SHA differs from the frozen execution SHA;
- raw output inventory is incomplete;
- production contains an evaluation-only binding disable flag;
- external evidence is mislabeled as clinical validation;
- historical artifacts are overwritten.

---

# 22. Claim-to-evidence ledger

Create `research/glhs_journal/q2_r2/claim_to_evidence.csv` with columns:

```text
claim_id,
claim_text,
claim_class,
experiment_id,
raw_artifact,
derived_artifact,
protocol_sha256,
code_sha,
status,
allowed_manuscript_section,
forbidden_extensions
```

Minimum claims:

- C-BIND-001: exact binding rejects frozen substitution schedules missed by matched current-state/governance validation.
- C-COMP-001: component contribution by identity/digest/evidence membership.
- C-MIN-001: comparison with minimal read-set token.
- C-DOWN-001: no downgrade success on inventoried THSS-origin write routes.
- C-TOC-001: no forbidden commit in frozen generated schedule campaign under evaluated boundary.
- C-DEP-001: required dependency omission mutations are rejected.
- C-CANON-001: current canonicalization vectors pass and historical profiles remain verifiable.
- C-FORM-001: zero invariant violations under explicitly stated bounded model.
- C-MODEL-001: paired Strict-vs-full context result for each model family.
- C-MAL-001: malformed-output rate stratified by model/condition.

Every claim has explicit forbidden extensions such as:

```text
clinical safety
regulatory compliance
arbitrary unbounded schedules
uncompromised-vs-compromised DB authenticity
universal model superiority
real-world attack prevalence
```

---

# 23. CI / GitHub Actions design

## 23.1 Fast PR gate

Add workflow:

```text
.github/workflows/glhs-q2-r2-smoke.yml
```

Runs:

- schema validation;
- static route inventory;
- no production ablation flag scan;
- canonicalization vectors;
- formal model unit tests at shallow depth;
- E01/E06 small deterministic smoke sets;
- release-gate unit tests;
- secret scan.

No provider calls. No long PostgreSQL campaign.

## 23.2 Manual evidence workflow

Add:

```text
.github/workflows/glhs-q2-r2-evidence.yml
```

`workflow_dispatch` only.

Inputs:

- experiment ID;
- run ID;
- frozen manifest SHA;
- container image digest;
- confirmatory flag.

Safety:

- never run against production DB;
- require explicit isolated DB attestation;
- provider experiments require exact model manifest and secret configured at runtime;
- upload raw artifacts without credentials;
- no overwrite of existing run ID.

## 23.3 Release workflow

A final manual release workflow only validates/seals; it does not silently rerun missing experiments.

---

# 24. Make targets

Add consistent targets:

```text
eval-glhs-q2-r2-preflight
eval-glhs-q2-r2-binding-components
eval-glhs-q2-r2-minimal-baseline
eval-glhs-q2-r2-downgrade
eval-glhs-q2-r2-toctou
eval-glhs-q2-r2-toctou-root-cause
eval-glhs-q2-r2-dependency-completeness
eval-glhs-q2-r2-canonicalization
eval-glhs-q2-r2-formal
eval-glhs-q2-r2-concurrency
eval-glhs-q2-r2-fullstack
eval-glhs-q2-r2-model-freeze
eval-glhs-q2-r2-model-run
eval-glhs-q2-r2-malformed
eval-glhs-q2-r2-reproduce
eval-glhs-q2-r2-release-gate
```

Every destructive/expensive target requires explicit parameters and fails closed.

---

# 25. Detailed work breakdown structure

## Phase A — convergence and freeze foundations

### A-001 Pin source branch/SHA

**Deliverable:** `paper_code_sync/implementation_contract.json`  
**Done when:** exact source SHA and relevant file hashes recorded.

### A-002 Complete paper/code diff

**Deliverable:** `diff_report.md`  
**Done when:** no unresolved material discrepancy.

### A-003 Create R2 program manifest schema

**Deliverable:** machine-validated JSON schema + tests.

### A-004 Create global statistics plan

**Deliverable:** frozen `statistics_plan.json`.

### A-005 Create claim ledger and publication claim policy

**Deliverable:** initial ledger with all claims `NOT_RUN`.

### A-006 Extend evidence-program release gate

**Deliverable:** fail-closed R2 gate + unit tests.

---

## Phase B — novelty/minimality experiments

### B-001 Implement evaluation-only binding mask
### B-002 Build component-discriminating schedule generator
### B-003 Validate schedule independence and controls
### B-004 Freeze E01 confirmatory corpus
### B-005 Run PostgreSQL E01
### B-006 Analyze/seal E01
### B-007 Implement minimal read-set token baseline
### B-008 Add optional HMAC baseline
### B-009 Run same frozen schedules against baselines
### B-010 Analyze equivalence/disagreement and overhead

**Phase-B gate:** manuscript novelty language cannot be finalized until E01/E02 are sealed.

---

## Phase C — downgrade and dependency completeness

### C-001 Generate persistence-route inventory
### C-002 Add static route-inventory regression test
### C-003 Freeze downgrade schedule set
### C-004 Run downgrade tests through real production entry points
### C-005 Implement `dependency_contract.py`
### C-006 Add operation dependency catalog
### C-007 Add completeness validation to proposal seal/admission
### C-008 Build dependency omission mutants
### C-009 Add multi-entity write-skew schedules
### C-010 Freeze E06 corpus
### C-011 Run/analyze/seal E06

**Phase-C gate:** zero unexplained downgrade success and zero accepted required-dependency omission mutants.

---

## Phase D — concurrency and TOCTOU

### D-001 Instrument historical V2-05/V2-09 replays
### D-002 Produce root-cause classification
### D-003 Implement schedule grammar/generator
### D-004 Implement admissible-outcome oracle
### D-005 Add shrinker and failure preservation
### D-006 Freeze 1,024-schedule confirmatory corpus
### D-007 Run PostgreSQL primary schedule pass
### D-008 Run nested jitter robustness pass
### D-009 Analyze/seal E04
### D-010 Run Zipfian/partial-overlap concurrency benchmark
### D-011 Analyze/seal E09

**Phase-D gate:** no unreviewed observer ambiguity; all forbidden outcomes investigated.

---

## Phase E — protocol/canonical/formal assurance

### E-001 Finalize RFC8785 canonicalization vectors
### E-002 Add independent cross-runtime verification
### E-003 Add legacy-profile compatibility tests
### E-004 Document formal state model and bounds
### E-005 Build invariant-to-production refinement map
### E-006 Add mutation checks for invariants
### E-007 Freeze formal run configuration
### E-008 Execute depth-5/depth-6 model exploration
### E-009 Seal result

---

## Phase F — model-context replication

### F-001 Decide primary-only vs full nine-context grid
### F-002 Conduct prospective power calculation
### F-003 Create new source-disjoint cohort
### F-004 Run offline zero-call construction validation
### F-005 Freeze cohort/protocol/model manifest before provider calls
### F-006 Probe exact model availability
### F-007 Execute interleaved two-model grid
### F-008 Validate complete call accounting
### F-009 Generate condition-stratified malformed taxonomy
### F-010 Run R1/R2/R3 sensitivity pipeline
### F-011 Reproduce derived stats with network disabled
### F-012 Seal model evidence

---

## Phase G — optional external/full-stack strengthening

### G-001 Run service-layer benchmark at final SHA
### G-002 Add HTTP full-stack benchmark
### G-003 Freeze lawful external structured cohort
### G-004 Run external structural tasks
### G-005 Collect independent human labels if available
### G-006 Adjudicate and seal

---

## Phase H — final publication bundle

### H-001 Execute global release gate
### H-002 Generate manuscript tables/figures automatically
### H-003 Generate exact manuscript result text/macros
### H-004 Update Methods/Results/Discussion/Limitations
### H-005 Re-run claim-to-evidence audit
### H-006 Reproduce all derived results from sealed raw inputs
### H-007 Create release archive

---

# 26. Execution order and stop/go gates

Use this strict order:

```text
E00 preflight
  ↓
E01 component ablation
  ↓
E02 minimal baseline
  ↓
E03 downgrade + E06 dependency completeness
  ↓
E05 historical mismatch root-cause
  ↓
E04 generated TOCTOU
  ↓
E07 canonicalization + E08 formal model
  ↓
E09 concurrency
  ↓
E11 two-model context study + E12 malformed sensitivity
  ↓
E10/E13 optional strengthening
  ↓
GLOBAL RELEASE GATE
  ↓
MANUSCRIPT UPDATE
```

## Stop/go rules

### STOP-1

If E01 shows one or more GLHS binding components add no discrimination on the frozen schedule set, do not hide this. Update the architecture/minimality discussion before E02.

### STOP-2

If the minimal baseline is fully equivalent, change novelty framing from “GLHS mechanism superiority” to “Exact-Disclosure Admission Invariant + health-governance realization”.

### STOP-3

If any downgrade succeeds, fix the production path, create a new final SHA, and restart all claim-bearing experiments whose behavior could be affected.

### STOP-4

If dependency omission can commit a stale/write-skew result, fix dependency derivation before running the broad TOCTOU campaign.

### STOP-5

If E04 produces a forbidden commit, preserve the run and investigate before any manuscript resubmission. A bug fix requires a new frozen run; the failure remains reported in development history.

### STOP-6

If the model run is incomplete or provider fallback occurs, the confirmatory grid is invalid. Do not fill missing cells with another model.

---

# 27. Manuscript integration policy

## 27.1 Abstract

Only include headline outcomes from `SEALED_CLAIM_ELIGIBLE` experiments.

Recommended abstract emphasis after successful R2:

1. exact-binding component/minimality result;
2. generated PostgreSQL governance-drift result;
3. dependency-completeness result;
4. model-context result as secondary.

Do not lead with performance latency.

## 27.2 Methods

Update to include:

- current RFC8785 canonicalization profile;
- dependency derivation contract;
- atomic commit-kernel phases;
- experiment units;
- generated TOCTOU grammar;
- minimal-baseline definition;
- formal-model bounds;
- model cohort freeze and request randomization.

## 27.3 Results

Recommended ordering:

1. E01 binding-component ablation;
2. E02 minimal baseline;
3. E03/E06 downgrade and dependency completeness;
4. E04/E05 TOCTOU;
5. E08 formal bounded assurance;
6. E09 concurrency;
7. E11/E12 context utility;
8. performance/external evidence if space permits.

## 27.4 Discussion

Explicitly answer:

- what property is novel;
- whether GLHS is minimal;
- whether a compact token achieves the same property;
- what dependency completeness assumes/enforces;
- what bounded concurrency evidence does and does not imply;
- what model evidence does and does not say about clinical quality.

---

# 28. Definition of Done for Q2-R2

The experiment program is complete only when all of the following hold:

## Implementation

- [ ] final source SHA frozen;
- [ ] exact snapshot binding production path matches manuscript formalism;
- [ ] dependency contract is enforced centrally;
- [ ] no production evaluation-only disable flag exists;
- [ ] all model/THSS-origin persistence routes preserve or prohibit binding lineage.

## P0 evidence

- [ ] E01 component ablation sealed;
- [ ] E02 minimal baseline sealed;
- [ ] E03 downgrade suite sealed;
- [ ] E04 broad TOCTOU campaign sealed;
- [ ] E05 historical mismatch root cause published;
- [ ] E06 dependency completeness sealed;
- [ ] all P0 artifacts publicly accessible or archived with stable identifiers.

## P1 evidence

- [ ] E07 canonicalization vectors pass;
- [ ] E08 formal assurance sealed;
- [ ] E11 two-model large replication sealed;
- [ ] E12 malformed output analysis sealed.

## Reproducibility

- [ ] every headline result reproducible from raw artifacts without network;
- [ ] exact code/protocol/environment hashes present;
- [ ] release gate passes;
- [ ] no manual spreadsheet/transcription is required for final tables;
- [ ] manuscript tables and figures are generated from sealed results.

## Scientific claim discipline

- [ ] no clinical-benefit claim;
- [ ] no regulatory-compliance claim;
- [ ] no universal schedule correctness claim;
- [ ] no compromised-store authenticity claim unless separately evaluated;
- [ ] no model superiority claim from non-equivalence/null results;
- [ ] no third-party system ranking from simulated comparators.

---

# 29. Proposed repository changes

## 29.1 New production file

```text
services/api/src/clara_api/glhs/dependency_contract.py
```

Only if the audit confirms dependency completeness is not already centrally enforced under another module.

## 29.2 New evaluation packages

```text
evaluation/glhs_binding_component_ablation/
evaluation/glhs_minimal_baseline/
evaluation/glhs_dependency_completeness/
evaluation/glhs_toctou_r2/
evaluation/glhs_q2_r2/
```

Avoid creating duplicates if an existing package can be cleanly extended without modifying a historical frozen protocol.

## 29.3 New research namespace

```text
research/glhs_journal/q2_r2/
```

## 29.4 New workflow files

```text
.github/workflows/glhs-q2-r2-smoke.yml
.github/workflows/glhs-q2-r2-evidence.yml
.github/workflows/glhs-q2-r2-release.yml
```

---

# 30. Example program commands

These commands are design targets; exact CLI flags should be implemented to match the final modules.

## Preflight

```bash
git checkout codex/commitloop-phase-a
git rev-parse HEAD
make lint
make type-check
make test
make eval-glhs-q2-r2-preflight
```

## Component ablation

```bash
export DATABASE_URL='postgresql+psycopg://.../glhs_q2_r2_e01'
export GLHS_Q2_R2_ISOLATED_RESEARCH=1
make eval-glhs-q2-r2-binding-components \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01 \
  GLHS_Q2_R2_OUTPUT=artifacts/glhs-q2-r2/GLHS-Q2-R2-20260927-R01/E01
```

## Minimal baseline

```bash
make eval-glhs-q2-r2-minimal-baseline \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01 \
  GLHS_Q2_R2_SCHEDULES=research/glhs_journal/q2_r2/protocols/E01_binding_components/schedules.json
```

## Dependency completeness

```bash
make eval-glhs-q2-r2-dependency-completeness \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01
```

## TOCTOU

```bash
make eval-glhs-q2-r2-toctou \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01 \
  DATABASE_URL='postgresql+psycopg://.../glhs_q2_r2_e04' \
  ALLOW_ISOLATED_EMPTY_DATABASE=true
```

## Formal assurance

```bash
make eval-glhs-q2-r2-formal \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01 \
  FORMAL_DEPTHS='5,6'
```

## Model freeze

```bash
make eval-glhs-q2-r2-model-freeze \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01 \
  MODEL_PROTOCOL=protocols/commitloop/v8-glhs-q2-r2
```

## Model run

```bash
make eval-glhs-q2-r2-model-run \
  GLHS_Q2_R2_RUN_ID=GLHS-Q2-R2-20260927-R01 \
  GLHS_Q2_R2_MODEL_FREEZE=/secure/glhs-q2-r2/model-freeze/freeze.json
```

## Offline reproduction

```bash
make eval-glhs-q2-r2-reproduce \
  GLHS_Q2_R2_RUN_DIR=artifacts/glhs-q2-r2/GLHS-Q2-R2-20260927-R01
```

## Release gate

```bash
make eval-glhs-q2-r2-release-gate \
  GLHS_Q2_R2_RUN_DIR=artifacts/glhs-q2-r2/GLHS-Q2-R2-20260927-R01
```

---

# 31. Expected final publication tables

Generate, never hand-edit, at least:

### Table R1 — component contribution

Rows = attack families; columns = B000…B111; cells = invalid accepted / N.

### Table R2 — minimal baseline

GLHS vs MIN_READSET_TOKEN decision agreement, false accepts, false rejects, metadata bytes, validation median.

### Table R3 — downgrade/dependency completeness

Schedule family, mutant count, accepted invalid, rejection reason coverage.

### Table R4 — generated TOCTOU

Family, unique schedules, forbidden commits, safe rejections, valid commits, ambiguous/overlap admissible outcomes.

### Table R5 — formal assurance

Depth, states, transitions, invariant violations, runtime, bounds.

### Table R6 — realistic concurrency

Distribution × overlap × strategy with false stale, true stale, throughput, p95.

### Table R7 — two-model context result

Model family, N, wins/losses/ties, effect, 95% CI, equivalence result, malformed rate, token volume.

### Table R8 — malformed sensitivity

Model × context, R0 malformed, R1 deterministic recovery, R2 retry recovery, R3 constrained-repair recovery.

---

# 32. Expected final publication figures

1. Exact-Disclosure Admission Invariant architecture.
2. Component-ablation rejection heatmap.
3. Minimal baseline agreement/disagreement diagram.
4. Generated TOCTOU schedule grammar / outcome classes.
5. Concurrency false-stale vs overlap curve.
6. Two-model Strict-vs-full paired effect plot.
7. Malformed-output taxonomy by condition.

Every figure must be generated from sealed derived artifacts.

---

# 33. Quality-control checklist for each experiment implementation PR

Every PR implementing an experiment must answer:

- What exact reviewer concern does this close?
- What is the scientific unit?
- Which variables are manipulated?
- Which variables are held constant?
- What is development vs confirmatory?
- Is the protocol frozen before confirmatory execution?
- Can the runner accidentally touch production?
- Can the result be manufactured by missing rows or NOT_RUN rows?
- Are raw observations immutable?
- Can the analysis be reproduced without network?
- Is every result traceable to exact source SHA?
- Is there any production safety-disable flag?
- Does the experiment compare semantics fairly?
- What claim is permitted if the result is positive?
- What claim is permitted if the result is null/negative?

A PR is incomplete if these questions are not answered in machine-readable metadata or README documentation.

---

# 34. Final scientific positioning after successful completion

If the P0/P1 program succeeds, the strongest defensible paper contribution becomes:

> GLHS operationalizes an Exact-Disclosure Admission Invariant for persistent longitudinal-health AI: an accepted model-derived write can be required to retain a verifiable dependency on the specific governed disclosure supplied during inference while current state and governance are independently revalidated at commit time. Component ablations identify which binding coordinates contribute to the tested substitution defenses; a compact alternative baseline tests whether the representation is minimal; generated PostgreSQL governance schedules evaluate the property beyond hand-authored cases; and schema-derived dependency validation addresses the completeness assumptions introduced by entity-partitioned concurrency.

This framing is stronger than claiming that GLHS invented provenance, transactions, bitemporality, consent, or concurrency control.

It is also robust to a result in which the minimal token baseline performs identically: in that case the scientific contribution is the **explicit invariant, its health-governance integration, and the empirical characterization of enforcement mechanisms**, not a claim that one data structure is uniquely necessary.

---

# 35. Recommended submission gate

Do **not** resubmit solely because the manuscript prose is polished.

The minimum evidence package that should trigger a new Q2 submission is:

```text
PASS E00 paper/code synchronization
PASS E01 component-wise binding ablation
PASS E02 minimal alternative baseline
PASS E03 downgrade-path inventory/test
PASS E04 broad generated PostgreSQL TOCTOU campaign
PASS E05 root-cause reconciliation for historical mismatches
PASS E06 dependency completeness / omission mutations
PASS global reproducibility/release gate
```

For a materially stronger submission, also require:

```text
PASS E07 canonicalization conformance
PASS E08 sealed bounded formal model
PASS E11 two-model large context replication
PASS E12 malformed-output stratification/sensitivity
```

E09/E10/E13 should be included when their results are clean and space/venue scope justify them, but they should not displace the core novelty and correctness evidence above.

---

# 36. Final note on the latest branch audit

This specification intentionally supersedes any plan based on `main`. The latest audited research/development branch already implements several mechanisms that the manuscript previously treated as limitations or future work. Consequently, the first step is not to reimplement exact binding, canonicalization, or formal assurance. The first step is to **synchronize the paper to the latest code, freeze the final production semantics, then run the missing experiments against those semantics**.

That distinction is essential: a journal reviewer should be able to check out one exact SHA, inspect the same binding/dependency/locking semantics described in Methods, execute the frozen protocols, and regenerate every headline table without relying on undocumented private code or manually transcribed results.
