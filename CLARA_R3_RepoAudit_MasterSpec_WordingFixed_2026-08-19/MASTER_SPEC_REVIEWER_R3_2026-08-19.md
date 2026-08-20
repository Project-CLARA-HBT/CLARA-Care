# CLARA-Care Reviewer-R3 Completion Master Spec

**Target repository:** `Project-CLARA-HBT/CLARA-Care`  
**Target branch at audit time:** `codex/commitloop-phase-a`  
**Audit date:** 2026-08-19  
**Purpose:** close every technically feasible blocker in the strict R2 re-review without changing the research question, post-hoc tuning the benchmark, suppressing negative results, or relabeling historical frozen artifacts.

---

## 0. Non-negotiable scientific rules

1. **Do not change any existing research question to make the results easier to satisfy.**
2. **Do not tune gold labels, prompts, test strata, model choice, exclusion rules, denominators, or statistical tests after observing held-out results.**
3. **Do not overwrite any sealed run.** New implementation behavior requires a new code SHA, protocol/freeze ID, run ID, and seal.
4. Preserve the 384-subject null model-context result, GovRed final-003, GovMut W8 45-mutant study, and every previous negative/indeterminate result as historical evidence.
5. A new production safeguard may improve future results, but old results remain attached to the implementation that produced them.
6. Evaluation-only ablations must never become production feature flags or public insecure modes.
7. Scientific N is the prespecified logical unit: subject, logical schedule, mutant, product, or pair. Retries, seeds, repeated timings, model-condition cells, and concurrency repetitions do not inflate N.
8. Do not claim clinical effectiveness, regulatory compliance, universal concurrency correctness, or production cybersecurity unless independently demonstrated.
9. All paper updates must be generated from a claim-to-evidence registry; no paper may silently inherit an unrelated result.
10. Duplicate-publication guard: one frozen scientific study must have one primary archival submission unless a later venue version contains a material, separately frozen extension and explicitly discloses its relationship to the earlier work.

---

# 1. Current repository audit

Status legend: **DONE**, **PARTIAL**, **MISSING**, **EVIDENCE-MISMATCH**, **MANUAL-GATE**, **WORDING-ONLY**.

## 1.1 GLHS production architecture

| Item | Current state | Status | Required action |
|---|---|---:|---|
| Task-local commitment selection | `commitment_thss.py` now calls production selection and dependency closure | DONE | Regression-lock only |
| Conflict localization | task-relevant conflict set rather than whole-domain blocker | DONE | Regression-lock only |
| Fact-level coverage | target/predicate/dependency/authority/minimum evidence coverage exists | DONE | Regression-lock only |
| Evidence minimization | production minimal evidence selector exists | DONE | Regression-lock only |
| Freshness semantics | domain/versioned freshness module is wired instead of blanket clinical valid-time age | DONE | Regression-lock only |
| THSS expiry | bounded by authorization scope validity | DONE | Regression-lock only |
| Temporal commitment state | `state_effective_at` is separated from anchor time in current `CommitmentVersionInput` | DONE/PARTIAL | Audit migration/backward replay semantics |
| Complete lifecycle predicates | policy-derived lifecycle predicates are filled before validation | DONE/PARTIAL | Property tests + audit version stamping |
| Public commitment proposal route | requires snapshot ID/digest and uses bound constructor | DONE | Keep public path bound |
| Generic assertion downgrade lock | declared THSS-consumption cannot silently become base-only; model generic write fallback rejected | DONE/PARTIAL | Replace caller declaration with immutable inference provenance |
| Commitment internal base-only constructor | still exists and can represent a model-origin proposal when a model manifest reference is supplied | PARTIAL | Add provenance-sensitive lineage rule; do not delete legitimate manual base-only semantics |
| Human review provenance | copies binding mode/snapshot fields from model proposal, but no independently verified root inference-to-THSS lineage | PARTIAL | Add immutable lineage and anti-laundering invariant |
| Commit-time lineage enforcement | validates current proposal context but accepts explicit base-only reviewed proposals | PARTIAL | Re-resolve immutable lineage after row lock and require snapshot binding when root consumed THSS |

### Key interpretation

The remaining binding problem is **not** “the public API is unbound.” The public commitment route is already snapshot-bound. The gap is that the server does not yet possess an immutable, server-owned proof that a given downstream proposal lineage consumed THSS, so it cannot universally enforce:

`THSS consumed -> every derived model/review proposal remains snapshot-bound -> GST revalidates the same disclosure dependency`.

## 1.2 GLHS evidence and experiments

| Item | Current state | Status | Required action |
|---|---|---:|---|
| 7-step contract-clause ablation | developer-authored deterministic 16-case x 7-variant study exists | DONE, but not sufficient | Preserve as conformance/failure-localization evidence |
| Matched exact-binding-only causal ablation | no same-production two-arm study where only `id_H/d_H/E_H` dependency differs | MISSING | Build new evaluation-only paired PostgreSQL study |
| PostgreSQL TOCTOU v2 machinery | `executor_v2.py`, persisted governance writers, barrier, observer v2 exist | PARTIAL | Freeze and run/reconcile final evidence |
| Canonical GLHS evidence registry | current status still materializes a five-schedule run with one indeterminate outcome, while R2 manuscript cites a 12-schedule v2 result | EVIDENCE-MISMATCH | Locate/import/seal the 12-schedule artifact or revert paper to canonical evidence; never fabricate |
| Repeated concurrency robustness | no frozen repeated-jitter analysis for each logical schedule | MISSING | Repeat each frozen schedule under timing/interleaving perturbations without increasing N |
| 384-subject malformed-output analysis | main paper reports 220 fail-closed malformed outputs but no condition/task decomposition | MISSING | Offline post-hoc descriptive audit on immutable outputs; primary null result unchanged |
| Independent contract holdout | developer-authored contract cases only | MISSING/MANUAL-GATE | 20–30 independently specified cases after implementation freeze |

## 1.3 GovRed

| Item | Current state | Status | Required action |
|---|---|---:|---|
| Strict 30 residual interpretation | R2 text correctly calls them indeterminate, not confirmed violations | DONE in RIVF wording | Keep three-state semantics everywhere |
| BigData result-table label | still labels the original composite as invalid/stale acceptance | WORDING-ONLY | Fixed in local R3 wording package; repo manuscript must receive same change |
| Strong ordering instrumentation | current residual concurrency cannot be fully linearized | MISSING | Add DB transaction/commit-order evidence and repeated execution |
| Not Run accounting | family-arm matrix exists and exposes family-specific Not Run rows | DONE for disclosure | Implement feasible missing families; retain genuine unsupported rows with reasons |
| Conditional auditability | raw audit counts exist but eligible denominators are not final | PARTIAL | Define opportunity-specific denominators and rerun/report |
| Fresh confirmatory holdout | absent | MISSING/MANUAL-GATE | 30–60 new logical schedules, preferably independently authored |
| 02/08 publication overlap | same study and result | MAJOR PORTFOLIO GATE | choose one initial archival venue; second only after material extension |

## 1.4 GovMut

| Item | Current state | Status | Required action |
|---|---|---:|---|
| W8 45-mutant sealed study | complete and immutable | DONE | Never rescore/overwrite |
| 25 survivor audit | `mutation_adequacy_audit.md` maps all survivors and exposes severe commitment-gateway blind spots | PARTIAL | Add root-cause categories and actionability table |
| W9 holdout design | 11 new mutants already designed; execution explicitly NOT STARTED | PARTIAL | Extend protocol, review, freeze, execute as separate W9 study |
| Human non-equivalence review | W8/W9 protocol uses Gemini+Claude dual-model review | MISSING/MANUAL-GATE | independent human software review before W9 denominator; W8 stays dual-model historical evidence |
| M3 budget fairness | M3 is union of M0+M1+M2; no equal-budget efficiency study | MISSING | add new cost/equal-budget follow-up; do not reinterpret W8 as budget-fair |
| Secondary endpoint data | W8 machine-readable analysis already contains kill fraction, seed instability, first-kill timing; manuscript reports little of it | PARTIAL | build deterministic reporting renderer and publish available endpoints |
| Minimal shrunk sequence/generated transition metrics | promised in paper but may not exist uniformly in final artifact | PARTIAL | audit fields; report available metrics, otherwise narrow Methods or collect prospectively in W9 |
| 03/11 publication overlap | same frozen study | MAJOR PORTFOLIO GATE | choose one initial archival venue; second requires material extension |

## 1.5 CareGuard-VN

| Item | Current state | Status | Required action |
|---|---|---:|---|
| DDInter 2.0 | acquired, controlled manifest, 222,383-row inventory | DONE |
| RxNorm 2026-08-03 | acquired, controlled 6,183,895-record release | DONE |
| DailyMed current SPL confirmation | five-record prespecified subset acquired | DONE, small |
| Vietnam identity frame | no authorized/current DAV export | BLOCKER/MANUAL-GATE | obtain official current export/API delivery + permitted use |
| Statistics plan | draft exists; units and primary false-clear components defined | PARTIAL | freeze exact sample sizes/selection + precision target + risk-coverage grid |
| DAV mapping adjudication | workflow exists, but reviewer qualifications/agreement protocol not frozen | PARTIAL/MANUAL-GATE | two blinded reviewers preferred; frozen rubric and agreement metric |
| RxMap comparator | literature comparator named in manuscript, no executable feasibility artifact found | MISSING | asset/license/version feasibility gate before final freeze |
| Independent negative/reference subset | not established | MISSING/OPTIONAL | only use independently supported negatives; never infer negatives from DDInter absence |
| External run | not started | BLOCKER | no headline CareGuard result until source-set freeze passes |

## 1.6 FHIR application

| Item | Current state | Status | Required action |
|---|---|---:|---|
| Pinned HL7 validator | checksum-locked validator script exists | DONE/PARTIAL |
| Validator scope | script validates one R4 summary fixture | PARTIAL | batch R4 + STU3 supported fixtures and emit machine-readable manifest |
| Negative conformance | wrong subject, missing Patient, unsupported-resource and temporal/provenance cases not packaged as one formal study | PARTIAL/MISSING | create frozen interoperability test matrix |
| Source preservation | implemented/documented | PARTIAL evidence | quantify preservation/reconstruction accuracy |
| Live FHIR service workflow | not required and not claimed | OPTIONAL | local verified R4 server workflow only if cleanly implementable |
| administrative forms | signatures/milestone date require real humans/date | MANUAL-GATE | never invent |

## 1.7 Research registry / provenance

`publication_registry.yaml` is stale relative to later frozen results: it still labels GovRed/GovMut headline runs as NOT_RUN/development. The GLHS canonical status also does not currently reconcile the manuscript's 12-schedule result. This must be treated as a release blocker, not cosmetic documentation debt.

---

# 2. Requirements

## 2.1 Global requirements

### GR-01 Freeze integrity
Every new confirmatory study SHALL have a new immutable `freeze_id`, code revision, protocol hash, analysis-plan hash, environment manifest, raw-result inventory, and SHA-256 seal.

### GR-02 Historical immutability
No existing W8, GovRed final-003, 384-subject, 64-subject, v1 TOCTOU, or previous manuscript result SHALL be altered, deleted, reclassified in place, or attached to a newer implementation SHA.

### GR-03 No benchmark-aware production logic
`services/**` SHALL NOT import from `evaluation/**`, inspect benchmark case IDs, special-case research arms, or expose an insecure production flag for ablation.

### GR-04 Fail closed
Missing lineage, missing snapshot binding, ambiguous governance state, missing source roles, incomplete audit observation, or unknown concurrent ordering SHALL remain explicit failure/indeterminate states; they SHALL NOT become a success by default.

### GR-05 Claim registry
Each manuscript claim SHALL map to one and only one claim-eligible artifact/run or to a clearly labeled architectural statement.

## 2.2 GLHS mandatory binding requirements

### GLHS-B01 Immutable inference disclosure provenance
Whenever an API-owned model/inference process receives a THSS, the server SHALL persist an immutable inference-context binding that records at minimum:
- profile/subject identity;
- inference/model manifest identity;
- `consumed_thss=true`;
- THSS snapshot public ID;
- snapshot digest + manifest digest;
- base state version;
- policy version;
- consent version/basis;
- actor user ID + role;
- purpose + task;
- disclosed evidence IDs or their bound set digest;
- snapshot expiry;
- creation time;
- schema/canonicalization/digest versions.

The client SHALL NOT be authoritative for `consumed_thss`.

### GLHS-B02 Proposal lineage
Every model-derived commitment proposal SHALL reference its immutable inference binding. A reviewed/humanized proposal SHALL preserve `reviewed_proposal_id`, root model proposal, root inference binding, snapshot ID/digest, and binding requirement.

### GLHS-B03 Anti-laundering invariant
If any root inference in a proposal lineage consumed THSS, every descendant proposal SHALL have `context_binding_mode=snapshot_bound` and SHALL bind the same root snapshot unless an explicit new model inference with a newly issued THSS creates a new lineage.

Human review MAY change/approve/reject the proposed clinical transition but SHALL NOT erase or downgrade the provenance requirement.

### GLHS-B04 Legitimate manual base-only semantics
Base-version-only proposals MAY remain available for genuinely manual user/clinician workflows that have no model inference/THSS lineage and that satisfy ordinary policy. Do not delete this semantic merely to make the paper easier.

### GLHS-B05 Commit-time root revalidation
After acquiring the profile/state lock and before persistence, GST SHALL re-resolve the root inference binding from the database and validate the exact THSS dependency. It SHALL NOT trust proposal payload fields alone.

### GLHS-B06 DB defense-in-depth
Database constraints SHALL enforce binding-mode field consistency (snapshot fields required for snapshot-bound, absent for base-only) where portable. Server logic remains the authoritative semantic check.

### GLHS-B07 Retry/idempotency
Idempotent retries SHALL preserve the same lineage digest. Reuse of an idempotency key with changed lineage/snapshot/proposal content SHALL fail.

## 2.3 GLHS exact-binding ablation requirements

### GLHS-A01 Matched arms
Create exactly two principal experimental arms from the same current production validation primitives:
- **FULL_GOVERNANCE_NO_EXACT_BINDING:** state, current authorization, policy, consent, actor, role, purpose, task, DB locking, idempotency, ordinary provenance, and audit are preserved; only the persisted exact THSS identity/digest/evidence dependency is omitted.
- **GLHS_EXACT_BINDING:** identical plus exact THSS ID/digest/manifest/evidence-membership/expiry dependency.

### GLHS-A02 Evaluation-only isolation
The no-binding arm SHALL live under `evaluation/` and SHALL NOT be selectable through production HTTP, environment settings, tenant configuration, or runtime feature flags.

### GLHS-A03 Binding-specific cases
Primary adversarial cases SHALL hold current state/governance valid while changing only the disclosure dependency, e.g. wrong snapshot with same current coordinates, digest/payload substitution, undisclosed evidence substitution, expired disclosure with otherwise current state, or replacement by another valid snapshot from the same state version.

### GLHS-A04 Valid controls
Matched clean controls SHALL be included to prove exact binding does not simply reject every write.

### GLHS-A05 Suggested confirmatory size
Freeze 8 binding-specific families x 32 logical schedules = 256 adversarial schedules plus 64 valid controls = 320 logical schedules. Execute both arms (640 executions). The scientific unit is the logical schedule.

### GLHS-A06 Analysis
Primary: paired invalid-commit acceptance on the 256 adversarial schedules. Report numerator/denominator, paired absolute risk difference + 95% paired bootstrap or exact-compatible CI, discordant counts, and exact McNemar test. Report per-family results. Controls report valid-commit acceptance and rejection reason distribution.

No adaptive sample-size increase after result inspection.

## 2.4 GLHS concurrency requirements

### GLHS-C01 Canonical evidence reconciliation
Before manuscript release, determine whether the claimed 12-schedule v2 run exists as a byte-verifiable artifact. If yes, import its receipt/manifest/seal into the canonical research registry without overwriting v1. If not, remove the 12-schedule claim and run a new correctly frozen study.

### GLHS-C02 Repeated interleavings
For each logical schedule, run a prespecified number of timing repetitions (recommended 50) using randomized pre-barrier jitter and supported interleaving modes. These repetitions are robustness executions, not new scientific N.

### GLHS-C03 Transaction ordering
In the isolated PostgreSQL environment record transaction identifiers, backend PIDs, monotonic client trace, lock waits, and, where enabled, PostgreSQL commit timestamps (`track_commit_timestamp`) after transactions complete. If durable ordering still cannot be established, preserve `INDETERMINATE`.

### GLHS-C04 Operational outcomes
Deadlock, serialization failure and lock timeout are operational outcomes, never safety successes.

## 2.5 GLHS malformed-output audit

### GLHS-M01 Preserve primary
The sealed 384-subject primary comparison remains unchanged: malformed outputs are fail-closed errors under the original scoring.

### GLHS-M02 Offline descriptive audit
Without rerunning models, parse immutable raw results and report malformed count/rate by context condition, subject stratum/task where available, failure type, and paired Strict vs full-history malformed status.

### GLHS-M03 Sensitivity
Any alternative analysis (e.g. complete-case or parse-recoverable subset) SHALL be explicitly exploratory/post-hoc and SHALL NOT replace the original null endpoint.

## 2.6 Independent GLHS contract holdout

### GLHS-H01 Authorship independence
20–30 new contract cases should be written from the published contract specification by at least one person who did not author the original 16 cases or implement the target change. The author must not see system outcomes while writing expected behavior.

### GLHS-H02 Freeze
Case text, expected admissibility class, reason-code class, and rationale are frozen before execution. If independent authorship cannot be obtained, state that honestly; do not simulate it with an LLM and call it independent human authorship.

## 2.7 GovRed requirements

### GRD-01 Three-state primary interpretation
Final scientific tables SHALL distinguish `CONFIRMED_INVALID`, `INDETERMINATE`, and `CONFIRMED_SAFE_OR_REJECTED`. The historical binary non-safe composite may remain as a secondary frozen endpoint only.

### GRD-02 Resolve races when measurable
Instrument concurrency with persistent transaction/ordering evidence. Repeat with jitter. Only reclassify an indeterminate schedule when ordering is directly supported by the frozen observer contract.

### GRD-03 Not Run completion
For every family/arm currently Not Run, add a capability decision:
- `IMPLEMENTABLE_FAITHFULLY` -> implement and test before a new freeze;
- `TASK_OR_ARM_SEMANTICS_UNSUPPORTED` -> retain Not Run with technical reason;
- `REQUIRES_LLM_ATTACK_STUDY` -> keep outside the core authorization-drift endpoint rather than fake a model attack.

Do not force 100% execution by weakening semantics.

### GRD-04 Audit opportunity denominators
Define separate denominators for:
- rejected operations where a rejection decision record is required;
- committed operations requiring exact reconstruction;
- governance mutations requiring trace linkage.
Report completeness only within its eligible opportunity set.

### GRD-05 Fresh holdout
Freeze 30–60 new logical schedules after current results remain sealed, preferably independently authored. Report separately; do not merge into final-003.

### GRD-06 Publication routing
RIVF and BigData Healthcare SHALL NOT be submitted as two independent full papers from final-003 alone. Designate a primary paper; a later paper requires materially new frozen evidence such as resolved concurrency + holdout + additional backend/attack family.

## 2.8 GovMut requirements

### GMT-01 Preserve W8
W8 remains a 45-mutant historical study with M0/M1/M2/M3 = 16/4/6/20. Do not rescore it after test improvements.

### GMT-02 Human adjudication for W9
Before W9 denominator freeze, each candidate should receive independent human non-equivalence review, preferably two reviewers. Record qualification category, blind packet, disposition, agreement statistic, disagreement adjudication, and date. Strategy outcomes must remain hidden during review.

LLM dual review may remain as a separate auxiliary field.

### GMT-03 Extend W9 rather than invent another holdout
Use the existing 11-mutant W9 proposal as the starting point. Re-verify anchors at the final code SHA and add only independently justified mutants before freeze. W9 is a separate denominator and seal.

### GMT-04 Budget-fair follow-up
Add a second analysis where every strategy receives the same wall-clock budget per mutant. Determine the budget from an outcome-blind unmutated calibration on the frozen environment, then freeze it. Also report CPU/wall time, kills per minute, incremental unique kills, and incremental compute cost.

W8 raw mutation-score ranking must explicitly remain non-budget-normalized.

### GMT-05 Secondary endpoint renderer
Build an offline renderer from `final-analysis.json` that outputs:
- per-mutant kill status;
- kill fraction across deterministic seed streams;
- seed instability;
- first killing seed;
- time to first kill;
- family/layer/invariant mapping;
- unique kills;
- all-survive list;
- runtime totals where recoverable.
Do not rerun W8 merely to populate fields already present.

### GMT-06 Survivor analysis
Classify all 25 W8 all-survive mutants into prespecified engineering categories: generator reach, missing oracle, missing path/test target, budget exhaustion, replay/reconstruction blind spot, API layer absence, possible weak mutant, other-with-rationale. This is descriptive diagnosis, not retroactive equivalent-mutant exclusion.

### GMT-07 Publication routing
SOICT and IEEE BigData ML SHALL be treated as the same W8 study unless the second adds a material W9/equal-budget/human-review extension. Do not parallel-submit identical evidence as independent papers.

## 2.9 CareGuard requirements

### CG-01 Hard source gate
No final benchmark may run until an authorized, current Vietnam product identity frame is available and passes source-manifest validation.

### CG-02 Freeze sample selection before model/system outputs
After source mapping but before CareGuard result inspection, freeze exact:
- DAV product identity cases;
- natural/noisy variants and clustering relation;
- eligible positive DDI pairs;
- DailyMed confirmation cases;
- any independent negative/reference cases;
- development/test split;
- exclusions with reason codes.

Use all eligible cases or a prespecified stratified sample/cap; never stop based on observed performance.

### CG-03 Precision target
Record a precision objective before locked testing. A practical target is enough positive-reference cases that the 95% interval for a plausible 5–10% false-reassurance rate has approximately <=3 percentage-point half-width. If the available mapped population cannot meet that target, report the achieved precision rather than manufacturing additional pseudo-independent perturbations.

### CG-04 Primary denominator
Primary end-to-end false reassurance uses **all frozen externally positive cases** in the test set. Identity failure/ambiguity cannot disappear from the denominator. Conditional DDI false-clear among admissibly resolved identities is secondary decomposition.

### CG-05 Reviewer protocol
For ambiguous DAV→RxNorm mapping, freeze two-reviewer packet where feasible: reviewer background, blinding, rubric, labels, agreement statistic, and adjudication. If pharmacist/medication terminology expertise is unavailable, disclose qualifications exactly.

### CG-06 RxMap feasibility
Before final freeze, attempt a faithful pinned RxMap comparator subject to code/license/access. Record `DIRECTLY_EXECUTABLE`, `ASSET_GATED`, or `TASK_MISMATCH`; never emulate it with project-local heuristics and call that RxMap.

### CG-07 Negative reference
Do not infer negative interactions from DDInter absence. Add only independently supported negative/reference pairs if a defensible source/adjudication process exists; otherwise leave specificity as unsupported and focus on positive-case safety/risk-coverage.

## 2.10 FHIR requirements

### FHIR-01 Formal validator matrix
Extend the pinned validator workflow from one R4 fixture to a batch study of every supported exported/imported R4 and STU3 fixture. Emit per-file validator version, profile/version mode, exit status, messages, and payload hash.

### FHIR-02 Application-level negative matrix
Freeze cases for:
- missing Patient;
- multiple Patient where unsupported;
- wrong/cross-subject references;
- dangling references;
- unsupported resources;
- invalid temporal fields;
- provenance/source identity loss;
- duplicate/replayed bundle;
- STU3/R4 version mismatch.

### FHIR-03 Preservation endpoints
Report resource preservation accuracy, source-reference reconstruction, subject rejection accuracy, temporal mapping correctness, supported-resource acceptance, and unsupported behavior with numerator/denominator.

### FHIR-04 Live service optional
Only if cleanly feasible, use a pinned local R4 server (e.g. test HAPI deployment) to demonstrate create/read/search/export ingestion. Do not block the paper on SMART-on-FHIR/CDS Hooks if those are not part of the actual contribution.

### FHIR-05 Admin fields
Letter/signature/advisor/milestone date remain human administrative gates. Never fabricate them.

## 2.11 Registry and manuscript requirements

### REG-01 Evidence registry reconciliation
Update `research/publication_registry.yaml`, GLHS current evidence status, GovRed/GovMut readiness files, and claim ledgers to the actual frozen artifacts. Stale `NOT_RUN` entries must not remain after completed runs.

### REG-02 Parent-study identifiers
Add `parent_study_id`, `evidence_freeze_ids`, `publication_relationship`, and `overlap_status` for every manuscript. Explicitly link 02↔08 and 03↔11.

### REG-03 Canonical GLHS guarantee
Until mandatory lineage is implemented and tested, all papers use:
> On the evaluated snapshot-bound path, a proposal derived from THSS retains the exact disclosure binding through GST admission; universal provenance-sensitive retention across every internal review/adaptation path has not yet been established.

After implementation + tests, replace this with a stronger guarantee only for the new code freeze and new results.

### REG-04 Model-utility balance
Every GLHS abstract that mentions the 64-subject near-ceiling result must also state, within space constraints, that later model-context evidence was mixed / the 384-subject Strict-vs-full-history result was null and therefore no universal superiority is claimed.

---

# 3. Technical design

## 3.1 Immutable inference-to-THSS lineage

### Preferred data model

Inspect existing `MLInferenceManifest`/`AIContextManifest` before migration. If they already contain a stable one-to-one place for exact THSS coordinates, extend them. Otherwise add an immutable table conceptually equivalent to:

```text
GlhsInferenceContextBinding
- id / public_id
- profile_id
- inference_manifest_id                 UNIQUE or indexed
- consumed_thss                         bool
- source_snapshot_id                    nullable only when consumed_thss=false
- source_snapshot_digest
- source_manifest_digest
- base_state_version
- policy_version
- consent_version
- actor_user_id
- actor_role
- purpose
- task
- disclosed_evidence_ids_json OR evidence_set_digest
- snapshot_expires_at
- canonicalization_profile
- digest_algorithm
- binding_schema_version
- binding_digest
- created_at
```

Rows are append-only/immutable. The binding digest covers every security-relevant field.

### Creation boundary
The binding is created by API-owned code at the moment a model call/inference manifest is constructed from THSS, not by the model response and not by the browser/client.

### Proposal changes
Add `inference_context_binding_id` (or equivalent immutable reference) to `GlhsClinicalCommitmentProposal`. Include it in `_proposal_envelope()` and proposal digest.

`propose_bound_commitment_transition()`:
- for `origin=model`, require a valid inference binding;
- assert supplied snapshot matches binding exactly;
- never accept a client-provided inference binding for another profile/task/actor.

`propose_base_commitment_transition()`:
- reject `origin=model`;
- reject any `model_manifest_ref` or lineage whose binding says `consumed_thss=true`;
- continue to allow legitimate manual origins only under policy.

`review_model_commitment_proposal()`:
- resolve root binding before review;
- preserve the root binding reference;
- require reviewed proposal to remain `snapshot_bound`;
- copy current reviewer actor separately rather than overwriting root inference actor if those concepts differ. If the existing schema currently overloads actor fields, introduce explicit `inference_actor_*` vs `review_actor_*` rather than losing provenance.

`apply_commitment_transition()`:
1. validate proposal digest;
2. acquire profile row/state lock;
3. re-read root inference binding;
4. run `require_lineage_binding()`;
5. validate current state/governance;
6. validate exact root snapshot/manifest/evidence membership/expiry;
7. persist transition + audit in the same DB transaction.

### Anti-laundering traversal
For reviewed proposals, follow `reviewed_proposal_id` to the root. Enforce acyclic lineage and bounded depth. Recommended rule: review creates at most one human descendant of a model proposal; subsequent edits create explicit new proposal revisions but retain the root binding.

## 3.2 Validation split to support a clean ablation

Refactor existing validation into reusable **production-owned secure primitives** without weakening production:

```python
validate_current_governance_coordinates(...)
validate_exact_disclosure_dependency(...)
validate_bound_proposal_context(...):
    validate_current_governance_coordinates(...)
    validate_exact_disclosure_dependency(...)
```

The production function always calls both for THSS-derived lineages.

The evaluation-only no-binding adapter calls the same current-governance primitive but intentionally omits only `validate_exact_disclosure_dependency`. Never add `disable_binding` to production signatures.

Exact dependency includes:
- source snapshot ID;
- snapshot digest;
- manifest digest;
- payload/canonicalization integrity;
- snapshot expiry;
- disclosed evidence membership or exact set digest;
- root inference binding equality.

## 3.3 Binding-only evaluation package

Create:

```text
evaluation/glhs_binding_only_ablation/
  README.md
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
research/glhs_journal/binding_only_ablation/
  FREEZE.md
  claim_to_evidence.csv
  results/           # after execution only
  seal/              # after execution only
```

Do **not** reuse/overwrite `evaluation/contract_clause_ablation/`; that study answers a different incremental-conformance question.

### Primary schedule families
1. wrong snapshot ID but same profile/current versions;
2. wrong snapshot digest;
3. mutated snapshot payload with unchanged current state/governance;
4. evidence used by proposal but absent from disclosed set;
5. substitute another valid snapshot from same profile/state version;
6. expired original snapshot while state/policy/consent remain unchanged;
7. minimized evidence-set swap;
8. lineage-root/snapshot substitution after human review.

Controls preserve all fields and should commit.

## 3.4 Concurrency repetition and ordering

Build on current `executor_v2.py`, `barrier.py`, `governance_writers.py`, `observer_v2.py` rather than a new framework.

Add `repeat_manifest` with frozen:
- repetitions per logical schedule;
- jitter seed list;
- jitter range;
- interleaving modes;
- DB isolation level;
- lock/statement timeout;
- `track_commit_timestamp` availability;
- observer schema version.

Each repetition returns `schedule_id`, `repeat_id`, `txid`, backend PID, barrier timestamps, lock waits, writer commit metadata, proposal commit metadata, audit/reconstruction outcome, and ordering confidence/reason.

Analysis aggregates at logical-schedule level: a schedule is robust only if all valid repetitions satisfy the invariant; mixed classifications are reported, not majority-voted into safety.

## 3.5 GovRed ordering architecture

Where possible, enable `track_commit_timestamp=on` in the **isolated research PostgreSQL only** and retrieve commit timestamps after both transactions complete. This is instrumentation, not production logic. Preserve application monotonic trace and lock information as independent corroboration.

Do not classify by transaction ID numeric order alone; PostgreSQL transaction IDs indicate assignment order, not necessarily commit order.

If database-level order remains unknowable for a repetition, retain `INDETERMINATE`.

## 3.6 GovMut budget-fair runner

Do not alter W8. Create W9 or W10 follow-up runner with:
- fixed mutant corpus;
- fixed machine/container;
- identical per-mutant wall-clock budget `B` for each strategy;
- budget `B` determined from outcome-blind unmutated preflight/calibration only;
- process-level monotonic timing and resource usage;
- kill as soon as strategy detects the mutant, while unused budget is recorded rather than transferred.

Report both:
1. detection within equal budget;
2. full-suite cost-effectiveness using actual historical/follow-up runtime.

Because M3 is a union strategy, its raw score is expected to be weakly monotonic relative to its components. The novel question is incremental detection per additional cost and fault-family coverage.

## 3.7 CareGuard execution pipeline

After authorized DAV acquisition:

```text
DAV raw export
 -> hash-bound source manifest
 -> deterministic normalization
 -> DAV-to-RxNorm mapping candidates
 -> blinded mapping review/adjudication
 -> frozen identity ledger
 -> external DDInter positive mapping
 -> DailyMed confirmation linkage
 -> optional independent negative/reference subset
 -> frozen split + statistics plan + baselines
 -> Mode A raw identity pipeline
 -> Mode B oracle identity pipeline
 -> risk/coverage + error decomposition
 -> seal
```

Mode A and Mode B must share the same DDI engine, source set, eligible pairs, exclusions, release rule, and analysis; only the identity input differs.

## 3.8 FHIR conformance package

Create `evaluation/fhir_conformance/` with:
- fixture manifest;
- validator wrapper around pinned JAR;
- application-ingest runner;
- expected subject/reference outcome;
- source/provenance preservation comparator;
- temporal field comparator;
- JSON result schema;
- offline analysis + seal.

Separate **HL7 structural validator result** from **CLARA application semantic result**. A Bundle can be structurally valid yet violate the product's one-patient or reference-scope contract.

---

# 4. Detailed task list

## Workstream A — Baseline and release integrity

- **A-001** Record `git rev-parse HEAD`, dirty state, Python/Node/PostgreSQL versions, and current migration head.
- **A-002** Snapshot all current research registries and seals without modifying them.
- **A-003** Add a machine-readable `R3_BASELINE_AUDIT.json` mapping reviewer blocker -> repo path -> status.
- **A-004** Reconcile `publication_registry.yaml` stale NOT_RUN statuses with actual sealed GovRed/GovMut evidence.
- **A-005** Resolve GLHS five-schedule-vs-12-schedule evidence discrepancy. Search local/remote retained artifacts by run ID/hash. If v2 cannot be byte-verified, manuscript must not cite it as canonical evidence.
- **A-006** Add duplicate-publication registry fields and mark 02/08 + 03/11 as same-parent studies until material extension exists.

**Gate A:** no implementation run starts until old evidence identities are protected and the current code SHA is recorded.

## Workstream B — Mandatory THSS lineage

- **B-001** Inspect `MLInferenceManifest`, `AIContextManifest`, model call adapters and current proposal schema; document exact lineage gap.
- **B-002** Choose extend-existing-manifest vs `GlhsInferenceContextBinding`; write migration design.
- **B-003** Add immutable binding schema and canonical digest.
- **B-004** Create binding at API-owned THSS→model boundary.
- **B-005** Add immutable binding reference to model-derived commitment proposals.
- **B-006** Include binding reference in proposal envelope/digest/idempotency digest.
- **B-007** Change `propose_base_commitment_transition`: forbid model/THSS lineage; preserve manual user/clinician base-only path.
- **B-008** Change `propose_bound_commitment_transition`: resolve and compare root inference binding.
- **B-009** Change `review_model_commitment_proposal`: preserve root binding and forbid context-binding downgrade.
- **B-010** Change `apply_commitment_transition`: after profile lock, re-read root binding and exact snapshot before persistence.
- **B-011** Add lineage cycle/depth protection and explicit reason codes.
- **B-012** Add DB consistency constraints where safe/migratable.
- **B-013** Backward compatibility: old proposals without inference binding can be read/reconstructed but cannot be retroactively claimed as mandatory-bound evidence.
- **B-014** Add audit reconstruction fields showing root inference -> snapshot -> model proposal -> reviewed proposal -> transition.

### Required tests for B

- model THSS -> bound proposal PASS;
- model THSS -> base-only REJECT;
- model THSS -> human review -> base-only REJECT;
- model THSS -> review preserves snapshot PASS;
- wrong/missing snapshot ID REJECT;
- wrong/missing digest REJECT;
- undisclosed evidence REJECT;
- expired snapshot REJECT;
- state/policy/consent/actor/role/purpose/task drift REJECT;
- cross-profile binding REJECT;
- lineage digest tamper REJECT;
- idempotency reuse with changed lineage REJECT;
- direct model commit REJECT;
- purely manual user/clinician base-only proposal PASS when policy allows;
- restart/reload from PostgreSQL preserves enforcement;
- concurrent review/commit cannot strip lineage.

**Gate B:** no supported route can turn a persisted `consumed_thss=true` lineage into base-only admission.

## Workstream C — Validation refactor + exact-binding matched ablation

- **C-001** Extract current-governance validation primitive.
- **C-002** Extract exact-disclosure dependency primitive.
- **C-003** Keep production bound validator as composition of both.
- **C-004** Add import-boundary test: `services/**` cannot import `evaluation.glhs_binding_only_ablation`.
- **C-005** Implement two evaluation arms without production flag.
- **C-006** Author 8 binding-specific schedule families + clean controls.
- **C-007** Validate each schedule differs only in intended disclosure dependency.
- **C-008** Freeze 320 logical schedules and analysis before execution.
- **C-009** Run both arms through isolated PostgreSQL and real commitment admission path.
- **C-010** Generate paired per-family/aggregate analysis and valid-control analysis.
- **C-011** Seal raw results and claim-to-evidence table.

**Gate C:** arm diff inspection proves all non-binding governance checks are byte/functionally identical.

## Workstream D — GLHS TOCTOU and malformed-output completion

- **D-001** Finalize/verify v2 12-schedule protocol artifact identity.
- **D-002** Extend v2 executor with frozen repeat/jitter manifest.
- **D-003** Add transaction commit timestamp instrumentation where isolated DB permits.
- **D-004** Run recommended 50 repetitions per logical schedule, preserving N=12.
- **D-005** Report schedule-level robustness and every operational/indeterminate repeat.
- **D-006** Locate immutable 384-subject raw outputs and verify their seal/hash.
- **D-007** Build malformed-output taxonomy parser.
- **D-008** Report malformed rate by condition and available task/stratum.
- **D-009** Report paired Strict/full malformed contingency.
- **D-010** Add clearly post-hoc sensitivity analysis without modifying primary result.
- **D-011 MANUAL** Obtain 20–30 independently authored contract cases; freeze and execute after B code freeze.

## Workstream E — GovRed completion

- **E-001** Add `confirmed_invalid / indeterminate / confirmed_safe_or_rejected / operational_failure` as explicit final analysis schema.
- **E-002** Add stronger DB ordering evidence; never infer order from txid alone.
- **E-003** Re-execute concurrent family under frozen jitter/repetition protocol.
- **E-004** Create Not Run capability audit from existing family-arm matrix.
- **E-005** Implement feasible primary families currently Not Run, prioritizing policy-version and purpose/authorization drift using persisted writers already present.
- **E-006** Keep prompt-injection families separate unless an actual model-mediated security protocol is frozen; do not fake them with synthetic request labels.
- **E-007** Define audit opportunity schemas and conditional denominators.
- **E-008** Update observer to emit opportunity eligibility and audit status.
- **E-009 MANUAL** Freeze 30–60 independently authored confirmatory schedules.
- **E-010** Run a new GovRed freeze; do not alter final-003.
- **E-011** Decide primary archival venue. Mark the other paper as held/extension-only.

## Workstream F — GovMut completion

- **F-001** Preserve W8 artifacts read-only.
- **F-002** Build W8 secondary-endpoint renderer from existing `final-analysis.json`.
- **F-003** Produce complete 45 x strategy kill matrix + family/layer summary + runtime/seed stability tables.
- **F-004** Produce 25-survivor diagnostic table; no retroactive exclusions.
- **F-005** Extend W9 protocol to require human review before denominator freeze.
- **F-006 MANUAL** Obtain one or preferably two independent human software reviewers; blind strategy outcomes.
- **F-007** Re-verify 11 W9 mutant anchors at new code SHA after GLHS production changes.
- **F-008** Add/replace W9 mutants only if code changes invalidate existing anchors; document every change before outcomes.
- **F-009** Freeze W9 corpus, methods, seeds, budgets and analysis.
- **F-010** Execute W9 and seal separately.
- **F-011** Build outcome-blind timing calibration on unmutated environment.
- **F-012** Freeze equal wall-clock budget.
- **F-013** Run budget-fair M0–M3 comparison on W9 or a separately frozen follow-up corpus.
- **F-014** Report kills/minute, time-to-first-kill, incremental unique kills, and cost per incremental kill.
- **F-015** Decide primary GovMut archival venue; second requires extension evidence.

## Workstream G — CareGuard external completion

- **G-001 MANUAL** Obtain official/current authorized DAV export or API delivery; record rights/access provenance.
- **G-002** Run local-file-only acquisition manifest; verify all record hashes.
- **G-003** Normalize DAV fields deterministically and produce mapping candidates to frozen RxNorm release.
- **G-004** Freeze mapping review rubric and reviewer qualification fields.
- **G-005 MANUAL** Run blinded mapping review/adjudication.
- **G-006** Map DDInter positive pairs to accepted frozen identities.
- **G-007** Expand DailyMed confirmation subset if prespecified and feasible; never use it as a negative set.
- **G-008** Attempt faithful RxMap comparator with pinned asset/license; record feasibility before final freeze.
- **G-009** Search/construct only defensible independent negative/reference subset; otherwise mark specificity unsupported.
- **G-010** Freeze exact N, split, clustering, coverage grid, metrics, exclusions, source hashes and precision objective.
- **G-011** Run Mode A and Mode B without changing DDI engine/config.
- **G-012** Compute end-to-end false reassurance, conditional DDI false-clear, identity accuracy, abstention/clarification, risk-coverage and error decomposition.
- **G-013** Seal and then rewrite CareGuard Results/Discussion from observed data.

**Gate G:** no final-test execution until four-role source-set validation + statistics freeze passes.

## Workstream H — FHIR application evidence

- **H-001** Inventory exactly which R4/STU3 resource types and Bundle forms are claimed supported.
- **H-002** Extend pinned HL7 validator script to batch fixtures and JSON summary.
- **H-003** Add positive fixtures for each supported resource/version path.
- **H-004** Add negative application semantic fixtures: missing/multiple Patient, cross-subject refs, dangling refs, unsupported resource, temporal errors, version mismatch, replay/duplicate.
- **H-005** Measure source-resource and provenance preservation.
- **H-006** Measure temporal field mapping/reconstruction.
- **H-007** Freeze test manifest and run; seal results.
- **H-008 OPTIONAL** Verify one local live R4 server round trip if it does not require overclaiming SMART/CDS Hooks.
- **H-009 MANUAL** Fill support letter, signatures and exact milestone date.

## Workstream I — Manuscript and portfolio synchronization

- **I-001** Adopt one canonical GLHS guarantee across 01/04/05/07/09/10.
- **I-002** Mention the 384-subject null/mixed model-context evidence wherever the 64-subject positive result is foregrounded, subject to venue space.
- **I-003** Replace BigData GovRed “invalid/stale acceptance” label with original composite/three-state interpretation.
- **I-004** Remove raw cross-arm audit-count implication until opportunity denominators exist.
- **I-005** Make M3 superset/budget-fair limitation explicit in both GovMut manuscripts.
- **I-006** Add descriptive mutation-score CIs to BigData GovMut or remove unsupported CI promises.
- **I-007** Keep CareGuard marked RESULT-INCOMPLETE until G gate passes.
- **I-008** Update Results/Discussion only from new sealed artifacts.
- **I-009** Update publication registry and duplicate-overlap declarations.
- **I-010** Build English/original-language and Vietnamese companion PDFs for all papers.
- **I-011** Run LaTeX undefined-reference/citation scan, PDF preflight, render-first visual inspection, page-limit check and SHA-256 packaging.

---

# 5. Verification matrix

## Production gates

- API tests + GLHS targeted regression pass.
- migration upgrade/downgrade smoke pass where project policy supports downgrade.
- `ruff`, type-check and targeted pytest pass for changed Python surfaces.
- PostgreSQL integration tests exercise real locking, not only SQLite.
- no evaluation imports in production.
- no model-origin/base-only downgrade supported for THSS lineage.
- manual non-model workflows remain functional.

## Scientific gates

- every new study has a new freeze and seal;
- all denominators prespecified;
- all exclusions have reason codes;
- indeterminate remains indeterminate;
- no repeated execution inflates N;
- null/negative historical results remain visible;
- no paper uses an artifact whose hash/run ID is absent from the evidence registry.

## Publication gates

- 02 and 08 cannot both be “independent full-paper ready” from the same GovRed run;
- 03 and 11 cannot both be “independent full-paper ready” from W8 alone;
- 06 cannot lose RESULT-INCOMPLETE until external study is sealed;
- 09 administrative signatures remain manual;
- all GLHS derivatives must match the same guarantee wording at the code freeze they cite.

---

# 6. Recommended execution order

1. **Registry/evidence reconciliation first** (A), especially the 5-vs-12 GLHS TOCTOU discrepancy.
2. **Mandatory THSS lineage** (B).
3. **Matched exact-binding causal ablation** (C).
4. **GLHS concurrency repetition + malformed audit + independent holdout** (D).
5. **GovRed resolution/Not Run/audit/holdout** (E).
6. **GovMut W8 reporting + W9 human-reviewed holdout + budget fairness** (F).
7. **CareGuard source acquisition and external validation** (G); DAV access can proceed in parallel because it has a human/external dependency.
8. **FHIR formal conformance** (H) can proceed in parallel with G.
9. **Final manuscript sync, portfolio routing, PDF build** (I).

The critical path for the GLHS journal is A -> B -> C -> D -> I. CareGuard has an external data-access critical path independent of GLHS.

---

# 7. Definition of done by paper

## 01 GLHS Journal
Ready only when:
- mandatory lineage gate passes;
- matched binding-only ablation sealed;
- canonical TOCTOU evidence reconciled and repeated-interleaving analysis available;
- malformed-output decomposition reported;
- independent holdout completed if a real independent author is available, otherwise transparently retained as a limitation;
- all claims point to correct run IDs.

## 02/08 GovRed
Choose one first submission. Ready when:
- three-state table is primary;
- concurrency order instrumentation is maximally resolved without forced classification;
- feasible Not Run rows completed or justified;
- audit-eligible denominators reported;
- fresh holdout added for a strengthened extension.

## 03/11 GovMut
Choose one first submission. Ready when:
- W8 secondary/survivor analysis is reported;
- M3 non-budget-fair interpretation is explicit;
- new equal-budget/cost analysis exists for a stronger extension;
- W9 holdout is human-reviewed and separately sealed where feasible.

## 06 CareGuard
Ready only after an authorized Vietnam identity source, frozen mapping review, sample-size/precision freeze, RxMap feasibility disposition, and external Mode A/B run are sealed.

## 09 FHIR App
Ready when the formal validator/application matrix is sealed and all administrative human fields are complete. A live service workflow is a bonus, not a prerequisite unless claimed.

## 04/05/07/10
Ready when synchronized with final GLHS guarantee/evidence and not positioned as independent duplicate journal studies.

---

# 8. What must NOT be done

- Do not remove `base_version_only` globally if legitimate manual workflows need it.
- Do not add `disable_snapshot_binding=true` to production.
- Do not turn the old incremental clause simulator into “causal production evidence.”
- Do not call an LLM-authored case set an independently human-authored holdout.
- Do not convert 50 concurrency repetitions into N=600.
- Do not count Hypothesis seeds as independent mutants.
- Do not exclude the 220 malformed outputs from the primary 384-subject result.
- Do not use DDInter absence as a negative DDI label.
- Do not scrape DAV against repository policy merely to unblock the paper.
- Do not submit duplicate GovRed/GovMut papers to two venues from the same frozen evidence without material extension/disclosure.

