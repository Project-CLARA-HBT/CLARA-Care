# Implementation Plan — CLARA LifeMap Production Convergence

Status: active — foundation implementation and repository validation in progress
Requirements: [requirements.md](requirements.md)
Technical design: [design.md](design.md)
AI portfolio: [ai-capability-analysis.md](ai-capability-analysis.md)
Verified milestone status:
[implementation-status-2026-07-28.md](implementation-status-2026-07-28.md)

## 1. Execution rules

- Safety and profile isolation precede feature expansion.
- Every task links to requirements, tests, flag, migration, and rollback where
  applicable.
- Keep all new behavior dark until its phase exit gate passes.
- A checked task means code, tests, docs, migration, and observability are
  complete; code alone is not complete.
- Start with the closest tests, then run the repository-required wider gates.
- Do not delete legacy code merely because a new route exists. Rehome shared
  behavior, observe traffic, keep a rollback window, then retire.
- Phases 15–19 are the AI expansion track. Registry and grounded-AI work may
  begin after Phases 1–3; time-series/adaptive work depends on canonical data and
  may run alongside later domain phases. Their numbering does not require waiting
  for all legacy retirement in Phase 14.

## 2. Workstream ownership

| Workstream | Accountable owner |
| --- | --- |
| Intended use, hazards, question/baseline rules | Clinical Safety |
| Consent, retention, Vietnam/EU assessments | Privacy/Legal |
| Canonical model, commands, workers, APIs | API |
| Extraction, synthesis, evaluations | ML |
| Web experience | Web |
| Mobile experience and offline policy | Mobile |
| Threat model, artifact handling, abuse testing | Security |
| SLOs, deployment, recovery | Platform/SRE |
| Release scorecard and user research | Product/Quality |

## Phase 0 — Baseline, scope, and safety contracts

- [ ] 0.1 Approve intended-use, prohibited-use, actor, and jurisdiction statement;
  record whether any planned function needs regulated-software review.
  _R1, R18, R22_
- [x] 0.2 Convert the current-state table into a checked inventory of API routes,
  tables, flags, worker loops, web/mobile surfaces, and tests; identify owner and
  production usage for each. _R21_
- [ ] 0.3 Create the LifeMap hazard log covering emergency delay, incorrect fact,
  medication harm, cross-profile access, stale consent, misleading change,
  unsupported visit extraction, and evidence misapplication. _R18, R22_
- [ ] 0.4 Define the privacy inventory, purposes, data classes, retention draft,
  controller/processor roles, transfer map, and DSAR impact for Law
  91/2025/QH15; open EU assessment if in launch scope. _R15_
- [x] 0.5 Create the requirement-to-test traceability template and GA scorecard.
  _R22_
- [x] 0.6 Add all V2 flags to API config and mobile/web capability responses,
  default OFF, with configuration tests. _R22_
- [ ] 0.7 Capture existing test baselines honestly: API, ML, web, mobile,
  migrations, docs, and end-to-end. Create issues for pre-existing failures.
  _R22_

Exit gate: intended use and hazard owners approved; baseline is reproducible;
flags are dark; no implementation status is overstated.

## Phase 1 — ProfileScope, opaque IDs, and authorization

- [x] 1.1 Add migration for profile public IDs and status/version fields; backfill
  in bounded, resumable batches with uniqueness/reconciliation queries.
  _R2, R21_
- [x] 1.2 Implement `ProfileScope` and `ProfileAccessPolicy` under
  `services/api/src/clara_api/lifemap/`; cover self, caregiver grant, clinician
  share, admin/support-denied-by-default. _R2, R12, R16_
- [x] 1.3 Refactor LifeMap repositories/endpoints to require resolved scope for
  every object query; add two-profile non-interference tests per route. _R2_
- [x] 1.4 Introduce public-ID serializers/resolvers and stop returning numeric
  identifiers in V2 contracts. _R2, R21_
- [x] 1.5 Extend family/share authorization with explicit purpose, data classes,
  actions, expiry, and immediate revocation fan-out. _R12, R15_
- [x] 1.6 Add object-level AuditEvent-compatible records for reads, exports,
  changes, shares, revocations, and support access. _R12, R16_
- [x] 1.7 Threat-model and test IDOR, enumeration, confused deputy, token replay,
  expired grant, and cross-profile background jobs. _R16_

Exit gate: automated tests show no cross-profile access; V2 exposes opaque IDs;
revocation and auditing meet the defined policy.

## Phase 2 — Truth, provenance, commands, and idempotency

- [x] 2.1 Add `HealthSourceReference`, event revisions, action histories,
  decision-input links, and projection dependencies via additive migrations.
  _R3, R5, R10_
- [x] 2.2 Implement the truth-state and task-state transition matrices as pure
  domain functions with exhaustive/property tests. _R3, R5_
- [x] 2.3 Implement the command pipeline: scope, CSRF, digest, idempotency,
  optimistic concurrency, transaction, audit, and outbox. _R3, R17_
- [x] 2.4 Remove client authority to set `confirmed` on generic event creation;
  current endpoint becomes a compatibility adapter that creates a safe state.
  _R3, R21_
- [x] 2.5 Implement typed confirm, correct, dispute, invalidate, and resolve
  commands plus stable error codes. _R3, R10_
- [x] 2.6 Backfill current facts with explicit legacy provenance and actor
  certainty; produce counts for confirmed, user-reported, ambiguous, and invalid.
  _R21_
- [x] 2.7 Add invariants: terminal revisions immutable, one active revision,
  source checksum stable, idempotency key/digest conflict, and canonical+outbox
  atomicity. _R3, R17_

Exit gate: no V2 path can create confirmed truth without an authorized typed
transition; correction history and idempotency are regression-locked.

## Phase 3 — Durable outbox and worker runtime

- [x] 3.1 Extend `LifeMapOutboxEvent` with lease, attempt, availability,
  delivery, and dead-letter fields; add indexes for claim and lag queries. _R17_
- [x] 3.2 Build the Postgres `SKIP LOCKED` claim/heartbeat/complete/retry/dead-
  letter repository with concurrent-worker tests. _R17_
- [x] 3.3 Create a separately deployable LifeMap worker entry point and health
  endpoints; disable production use of API lifespan relay. _R17_
- [x] 3.4 Define typed events and minimum-data payload schemas for fact, episode,
  task, consent, correction, and invalidation changes. _R17_
- [x] 3.5 Make every consumer idempotent; test duplicate, reorder, worker crash,
  expired lease, partial dependency outage, and replay. _R17_
- [x] 3.6 Add no-PII metrics/dashboards/alerts for lag, lease, retry, oldest event,
  dead letters, job duration, and stale projection age. _R17, R20_
- [x] 3.7 Add audited admin dead-letter inspect/replay/resolve operations with no
  raw PHI in primary lists. _R16, R17_
- [x] 3.8 Run soak and recovery tests; document worker scaling and incident
  runbooks. _R17, R20_

Exit gate: worker failure cannot lose a committed event; duplicate delivery is
safe; API processes host no production long-running LifeMap loops.

## Phase 4 — Universal Capture

- [x] 4.1 Add capture session/artifact/candidate/review tables and encrypted
  object-storage abstraction. _R4, R15, R16_
- [x] 4.2 Implement upload limits, media sniffing, malware scanning, checksums,
  short-lived URLs, and draft expiry/deletion. _R4, R16_
- [x] 4.3 Add capture V2 APIs and job workflow; run emergency fast-path before
  persistence-dependent extraction. _R4, R18_
- [x] 4.4 Define versioned typed extraction schemas for text, medication label,
  visit document, guided answer, and supported imported observation. _R4_
- [ ] 4.5 Implement ML/OCR extraction as candidates with per-field confidence,
  exact source spans, missing critical fields, and prompt-injection defenses.
  _R4, R16, R18_
- [x] 4.6 Implement duplicate suggestions without ambiguous auto-merge. _R4_
- [ ] 4.7 Build web capture review: edit/reject/confirm, source preview, low-
  confidence warnings, abandon/resume, accessible states. _R4, R19_
- [ ] 4.8 Build equivalent Flutter review, using online-only mutations and stale/
  offline labels. _R4, R19_
- [ ] 4.9 Evaluate field-level precision/recall, critical-field miss rate, wrong-
  medication rate, source-span validity, emergency latency, and confirmation
  burden in Vietnamese and English. _R18, R22_

Exit gate: ML creates zero confirmed facts; all safety-relevant extracted fields
have review and source provenance; emergency response is not delayed.

## Phase 5 — Episodes, Today, Replay, and correction propagation

- [x] 5.1 Add revision-aware episode-event links, goal revisions, task actions,
  and decision inputs. _R5_
- [x] 5.2 Implement V2 episode/goal/task commands and deterministic Today
  projection. _R5, R6_
- [ ] 5.3 Implement projection dependencies and invalidation traversal for
  correction, deletion, consent/source revocation, and late data. _R10_
- [x] 5.4 Implement revision-aware Replay query with consumer-safe `why`,
  provenance, rule/model version, and stale state. _R10_
- [ ] 5.5 Implement user dispute and resolution workflow with authorized
  operator/clinical review queue where needed. _R10_
- [ ] 5.6 Add web Today/LifeMap/Replay/correction/dispute flows. _R5, R6, R10,
  R19_
- [ ] 5.7 Add equivalent mobile flows; remove any duplicate LifeMap surface only
  after route parity and rollback checks. _R19, R21_
- [ ] 5.8 Property-test that Today contains only accepted eligible tasks and that
  correction reaches every dependent projection. _R6, R10_

Exit gate: a user can trace and correct the history end-to-end; stale derived
outputs cannot masquerade as current.

## Phase 6 — Baselines and next-best question

- [ ] 6.1 Clinical/data review selects initial signals, canonical units, valid
  ranges, source eligibility, exclusions, sample/span minimums, and change rules.
  _R7, R22_
- [x] 6.2 Implement the versioned baseline registry and snapshot/input/change
  tables. _R7_
- [x] 6.3 Implement deterministic normalization, robust statistics, sufficiency,
  persistence, late-data handling, and correction recomputation. _R7_
- [ ] 6.4 Shadow-run baseline V2 against historical/synthetic data; measure false
  alert, data insufficiency, stability, and subgroup performance. _R7, R22_
- [ ] 6.5 Clinical review creates the initial typed question catalogue, rationale,
  sensitivity, answer schemas, and impact mappings. _R8_
- [x] 6.6 Implement deterministic eligibility/ranking, burden budget, cooldown,
  dismissal, do-not-ask, and consent checks. _R8_
- [x] 6.7 Route answers through Capture/truth; never direct-confirm. _R3, R8_
- [x] 6.8 Build web/mobile baseline explanations and one-question UI with clear
  “personal change, not diagnosis” copy. _R7, R8, R19_
- [ ] 6.9 Run comprehension and usefulness pilot; set alert/question stop
  thresholds before enabling beyond allowlist. _R22_

Exit gate: algorithms are versioned and reproducible; false-alert and burden
gates pass; outputs never imply clinical abnormality or diagnosis.

## Phase 7 — Medication Guardian convergence

- [x] 7.1 Add medication normalization, route/form, reconciliation status,
  source, and append-only course-change schema. _R9_
- [x] 7.2 Migrate current medication courses, preserving original text and
  marking unresolved normalization as unknown. _R9, R21_
- [ ] 7.3 Make OCR/import results Capture drafts and require critical-field
  confirmation. _R4, R9_
- [x] 7.4 Ensure DDI analysis uses current confirmed courses by default; label
  hypothetical inputs separately. _R9_
- [x] 7.5 Regression-lock FIDES blocking, consent, emergency, and
  no-start/stop/substitute/dose language across API, ML, web, and mobile. _R9,
  R18_
- [x] 7.6 Converge list/cabinet/safety into one Medicines hub on both clients;
  rehome shared OCR/DDI components. _R9, R19_
- [ ] 7.7 Retire duplicate primary medication routes only after telemetry and
  redirect/rollback window. _R21_

Exit gate: medication history is revision/provenance-aware; unsafe claims remain
blocked; one coherent client entry exists.

## Phase 8 — Grounded Visit closed loop

- [x] 8.1 Extend document/extraction candidate schema with exact page/region/text
  spans and review state. _R11_
- [x] 8.2 Implement typed visit-document extraction with instruction
  classification, confidence, and fail-closed unknowns. _R11, R18_
- [ ] 8.3 Replace the permanent `extraction_unavailable` placeholder only when
  grounded extraction passes the source-span and safety evaluation. _R11_
- [x] 8.4 Build review/confirm flow; only confirmed clinician instructions can
  propose follow-up tasks. _R3, R5, R11_
- [x] 8.5 Make Visit Pack sections revision-aware, invalidatable, user-approved,
  purpose-bound, and revocable. _R10, R11, R12_
- [x] 8.6 Complete web/mobile visit lifecycle: documents, candidate review, pack
  approval, share, expiry/revocation. _R11, R19_
- [ ] 8.7 Evaluate instruction accuracy, unsupported-instruction rate, span
  validity, task leakage, and user comprehension. _R22_

Exit gate: no source span means no instruction/task; packs are explicitly
approved and invalidate on source correction/revocation.

## Phase 9 — Family Circle hardening

- [ ] 9.1 Migrate grants to explicit data classes, actions, purpose, start,
  expiry, and revocation; do not infer access from relationship. _R12_
- [ ] 9.2 Implement immediate API denial and sub-60-second cache/token/session/job
  revocation. _R12, R20_
- [ ] 9.3 Hash invitation/share secrets, add replay prevention, and test token
  leakage/redaction. _R12, R16_
- [ ] 9.4 Complete owner-facing access log, sensitive-access notifications, and
  grant review/renewal UI on web/mobile. _R12, R19_
- [ ] 9.5 Define and implement minor/legal-representative policy only after
  privacy/legal approval; otherwise keep unsupported. _R12_
- [ ] 9.6 Run authorization matrix and adversarial tests for every data class and
  action. _R2, R12, R16_

Exit gate: relationship never equals access; revocation SLO and access-log
comprehension pass.

## Phase 10 — Living Evidence completion

- [ ] 10.1 Define validated applicability-rule format and required confirmed
  profile inputs per supported question class. _R13_
- [ ] 10.2 Separate retrieval source classes and preserve stable citation/source
  identities and checkpoints. _R13_
- [ ] 10.3 Implement contradiction and material-change assessment with
  rule/model versions and review status. _R13, R18_
- [ ] 10.4 Implement leased subscription scheduler, retry/dead-letter, dedupe,
  checkpoint, consent/grant re-check, and cancellation. _R13, R17_
- [ ] 10.5 Gate consumer notification on accepted material change and a safe
  answer projection. _R13_
- [ ] 10.6 Show `not_assessed` honestly when eligibility rules or confirmed facts
  are unavailable; never infer private facts to force applicability. _R13_
- [ ] 10.7 Add web/mobile subscription, evidence-change, contradiction, and
  notification-preference flows. _R13, R19_
- [ ] 10.8 Evaluate citation validity, contradiction sensitivity, applicability
  precision, notification usefulness, and stale-evidence failure modes. _R22_

Exit gate: subscriptions execute durably; notification means a reviewed material
change, not merely “new search results exist.”

## Phase 11 — FHIR R4 / IPS interoperability

- [ ] 11.1 Approve terminology/licensing strategy and pin FHIR R4 validator,
  IPS package, UCUM, and supported code systems. _R14_
- [ ] 11.2 Implement pure mapping layer for Patient, Observation, allergy,
  condition, medication, CarePlan, Goal, Task, QuestionnaireResponse,
  DocumentReference, Provenance, Consent, and AuditEvent. _R14_
- [ ] 11.3 Implement authorized, purpose-bound IPS summary export with redaction
  and minimum-necessary selection. _R12, R14, R15_
- [ ] 11.4 Validate every fixture and generated Bundle; fail closed on modifier,
  patient identity, critical coding, or profile errors. _R14_
- [ ] 11.5 Implement import as provenance-bearing Capture drafts; define trusted-
  source policy separately. _R3, R4, R14_
- [ ] 11.6 Add conformance statement, mapping documentation, golden fixtures,
  round-trip semantic tests, and version-upgrade procedure. _R14_
- [ ] 11.7 Security-test parser limits, references, external URLs, narrative,
  unknown extensions, and malicious Bundles. _R16_

Exit gate: all claimed-conformant exports validate against pinned packages;
imports cannot bypass confirmation or profile authorization.

## Phase 12 — Client convergence, accessibility, and offline policy

- [ ] 12.1 Define one state vocabulary and API capability model for web/mobile:
  draft, awaiting review, confirmed, disputed, stale, unavailable, and offline.
  _R19_
- [ ] 12.2 Complete responsive web flows for all V2 modules and add keyboard/
  focus/screen-reader/contrast/text-scale/reduced-motion tests. _R19_
- [ ] 12.3 Complete Flutter flows and phone/tablet/text-scale/screen-reader/
  reduced-motion tests. _R19_
- [ ] 12.4 Implement encrypted least-necessary read cache, freshness indicators,
  and online-only mutation guards; document that queued health mutations remain
  unsupported. _R19_
- [x] 12.5 Resolve existing mobile analyzer/test debt touched by the unified
  paths; do not hide pre-existing failures or lower gates. _R22_
- [ ] 12.6 Run Vietnamese/English usability testing for truth labels, baseline
  change, provenance, correction, sharing, and evidence uncertainty. _R22_

Exit gate: core behavior is semantically equivalent across clients; accessibility
and offline/stale behavior meet their gates.

## Phase 13 — Privacy, security, reliability, and recovery certification

- [ ] 13.1 Complete threat model and penetration tests across API, artifacts,
  workers, shares, FHIR, ML prompt injection, and evidence ingestion. _R16_
- [ ] 13.2 Exercise access/correction/export/delete/restrict and consent
  revocation through primary, projection, object storage, worker, cache, and
  backup paths. _R15_
- [ ] 13.3 Verify telemetry schemas and sample production-like traces contain no
  PII/PHI. _R15, R20_
- [ ] 13.4 Load/soak test command, Today, worker, baseline, extraction, evidence,
  and export paths against SLOs. _R20_
- [ ] 13.5 Run backup restore and projection rebuild drills; reconcile canonical,
  outbox, consent/grant, and audit state. _R17, R20_
- [ ] 13.6 Complete privacy/legal, security, clinical safety, and operational
  runbooks/sign-offs. _R22_

Exit gate: no open P0/P1; SLO, restore, revocation, DSAR, threat, and no-PII
evidence is signed.

## Phase 14 — Migration, rollout, and legacy retirement

- [ ] 14.1 Shadow-build V2 projections and compare counts/content/freshness with
  current routes; investigate every unexplained delta. _R21_
- [ ] 14.2 Migrate web then mobile to V2 opaque-ID contracts behind independent
  flags; preserve compatible adapters. _R21_
- [ ] 14.3 Roll out internal -> allowlisted pilot -> percentage cohorts with
  daily safety/reliability review and named kill-switch owner. _R22_
- [ ] 14.4 Publish migration dashboards for numeric-ID adapter use, legacy route
  traffic, projection mismatch, old mobile-root selection, and duplicate
  navigation usage. _R21_
- [ ] 14.5 Rehome still-shared Chat/Scribe/DDI/OCR/PHR/consent components into
  maintained feature modules with their tests. _R21_
- [ ] 14.6 Remove in-process relay and direct-confirm semantics after all writers
  migrate and rollback window expires. _R17, R21_
- [ ] 14.7 Remove duplicate web/mobile feature entries and old root branches
  after parity, zero/accepted traffic threshold, and approved rollback expiry.
  _R21_
- [ ] 14.8 Update old specs/readmes to mark historical phases accurately and
  point to this convergence status. _R21_
- [ ] 14.9 Run final repository-wide validation, migration rehearsal, docs check,
  e2e smoke on real devices, and production readiness review. _R22_

Exit gate: general-availability scorecard signed; rollback tested; remaining
legacy code is either removed or explicitly documented as a shared maintained
component.

## Phase 15 — ML foundation and truthful model inventory

- [ ] 15.1 Register every existing ML/LLM capability, provider, embedding model,
  reranker, NLI path, OCR/ASR component, Council scorer, fallback, dataset, and
  release flag with intended/forbidden use and owner. _R31_
- [x] 15.2 Reclassify `council-neural-shadow-v1` as a fixed-weight heuristic in
  API/UI/docs/telemetry until a governed trained artifact exists; preserve
  shadow containment. _R18, R31_
- [ ] 15.3 Define and migrate registry/manifests for datasets, feature schemas,
  training runs, artifacts, evaluations, deployments, inference, drift, and
  feedback. _R31_
- [ ] 15.4 Implement signed artifact storage/loading, immutable provider model
  resolution, champion/challenger/fallback selection, and fail-closed signature
  checks. _R31_
- [ ] 15.5 Create datasheet, model-card, evaluation-report, use-case, and change-
  control templates; validate completeness in CI. _R31_
- [ ] 15.6 Build audited purpose/consent-filtered dataset snapshots outside OLTP;
  enforce person/household/site/time splits before window generation. _R15,
  R31_
- [ ] 15.7 Select a separate locked offline training image/package; keep PyTorch,
  scikit-learn/boosting, notebooks, and training credentials out of the online
  ML service unless required for inference. _R16, R31_
- [ ] 15.8 Implement no-PII ML metrics and private input-lineage manifests;
  verify exact revisions never enter logs/traces. _R15, R20, R31_
- [ ] 15.9 Add drift, OOD, calibration, artifact, provider-alias, and model-
  fallback runbooks with pause/rollback behavior and no auto-retraining. _R31_

Exit gate: all deployed “models” are truthfully classified and versioned;
datasets/artifacts are reproducible; no learned model can silently update or load
an unsigned artifact.

## Phase 16 — Grounded LifeMap intelligence

- [ ] 16.1 Implement `AIUseCaseDefinition` and private `AIContextManifest`;
  authorization, purpose, consent, data-class, and time/episode filters compile
  before ML context. _R2, R15, R23, R31_
- [ ] 16.2 Build a profile-partitioned, revision-aware temporal retrieval index
  with lexical/dense/time/graph search and hard filtered candidate sets. _R23,
  R26_
- [ ] 16.3 Implement Ask My LifeMap typed intents and answer schema with evidence
  table, exact citations, unknown/conflict/stale fields, disclosure, and
  abstention. _R23_
- [ ] 16.4 Add citation existence, entailment, temporal-order, contradiction,
  profile-scope, legal-guard, and FIDES verification before answer release.
  _R18, R23_
- [ ] 16.5 Build hierarchical event/day/episode/week/visit summaries from
  structured child claims, dependency links, and deterministic fallback. _R10,
  R24_
- [ ] 16.6 Implement consent-filtered caregiver/clinician digest generation;
  test withheld categories and revocation invalidation. _R12, R24_
- [ ] 16.7 Create the model-neutral multimodal extractor interface and adapters
  for current OCR, ASR, document layout, DeepSeek extraction, and optional VLM
  candidate generation. _R4, R25_
- [ ] 16.8 Validate multimodal typed output, checksums, page/region/timestamps,
  units, confidence, missing fields, prompt injection, and degraded fallback.
  _R16, R25_
- [ ] 16.9 Implement entity-resolution ensemble: Vietnamese normalization,
  exact/alias dictionary, dense candidates, graph constraints, optional
  reranking, calibration, ambiguity, and mapping revisions. _R26_
- [ ] 16.10 Implement rule-first contradiction/duplicate/missingness findings
  with bounded NLI/LLM proposals and human resolution workflow. _R27_
- [ ] 16.11 Build web/mobile Ask, summary, citation/source, multimodal review,
  normalization candidate, and conflict-review experiences. _R19, R23, R24,
  R25, R26, R27_
- [ ] 16.12 Evaluate claim citation, temporal accuracy, cross-profile isolation,
  unsupported claims, abstention, summary faithfulness, field-level extraction,
  entity top-k/precision, contradiction recall, Vietnamese quality, latency, and
  cost. _R22, R23, R24, R25, R26, R27, R31_

Exit gate: every released AI statement is scoped, source-cited, verified,
reversible, and safely degradable; multimodal AI still creates drafts only.

## Phase 17 — Personalized pattern and time-series ML

- [ ] 17.1 Approve each candidate target, label, permitted output, sample/event
  requirement, subgroup, horizon, evaluation split, and clinical/regulatory risk
  before dataset creation. _R28, R31_
- [ ] 17.2 Implement versioned feature snapshots with normalization, source/
  device/timezone, missingness masks, input watermark, and revision lineage.
  _R28, R31_
- [ ] 17.3 Build engineered coverage, robust statistics, trend, seasonality,
  variability/entropy, missingness, and task-history features. _R28_
- [ ] 17.4 Implement champion/challenger bake-off: deterministic, regularized
  linear/logistic/survival, tree/boosting, isolation/one-class, then neural
  sequence/foundation models where justified. _R28, R31_
- [ ] 17.5 Audit every windowed dataset for user, household, source, overlapping
  window, device, site, and future-time leakage. _R28, R31_
- [ ] 17.6 Add calibrated probabilities/intervals, conformal outputs where their
  assumptions pass, ensemble disagreement, sufficiency, OOD, and abstention.
  _R28, R31_
- [ ] 17.7 Implement deterministic pattern-relationship discovery with coverage,
  effect size, uncertainty, multiplicity/discovery-confirmation control, known
  confounders, and constrained non-causal LLM explanation. _R28_
- [ ] 17.8 Run anomaly challengers shadow-only; measure false alerts/user-week,
  lead time, stability, calibration, worst slices, missingness/device shift,
  latency, cost, and comparison with robust baseline. _R28, R31_
- [ ] 17.9 Run only approved low-risk wellness/organizational forecasts in
  shadow; hard-reject disease, deterioration, treatment, medication-effect, and
  emergency targets in the use-case registry. _R18, R28_
- [ ] 17.10 Conduct user/clinical review of pattern-change, relationship, and
  forecast explanations before any pilot. _R22, R28_

Exit gate: a complex model cannot advance unless it materially beats the simple
champion and safely abstains; clinical prediction remains research-only.

## Phase 18 — Adaptive and evidence intelligence

- [ ] 18.1 Define explicit utility labels for questions using information value,
  safety impact, user usefulness, burden, and dismissal—not click/answer rate
  alone. _R29, R31_
- [ ] 18.2 Implement learned scoring only over the deterministic eligible
  question set; assert it cannot generate text, modify eligibility, or affect
  emergency routing. _R8, R18, R29_
- [ ] 18.3 Add supervised ranking, propensity logging, offline policy evaluation,
  deterministic fallback, and shadow comparison. _R29_
- [ ] 18.4 Specify a bounded contextual-bandit pilot protocol with safe action
  set, exploration bounds, consent, burden ceilings, cohort, sample size,
  monitoring, and stop criteria; do not activate without approval. _R29, R31_
- [ ] 18.5 Build friction features/model with only reduce/change-time/pause/
  smaller-user-step/help actions and a hard notification-pressure ceiling.
  _R29_
- [ ] 18.6 Implement source-spanned PICO, guideline-condition, and trial-
  criterion extraction into reviewable candidates. _R13, R30_
- [ ] 18.7 Implement validated rule comparison against confirmed facts with
  separate match, mismatch, and unknown results; model inference cannot fill
  eligibility facts. _R30_
- [ ] 18.8 Add evidence contradiction/supersession, citation validation,
  possible-match wording, clinician-discussion questions, and safe abstention.
  _R13, R18, R30_
- [ ] 18.9 Evaluate ranking utility/burden/safety, off-policy uncertainty,
  friction fairness, eligibility precision, unknown calibration, citation
  quality, and user comprehension. _R22, R29, R30, R31_

Exit gate: learned personalization is contained by deterministic policy;
evidence matching never becomes diagnosis, eligibility confirmation, or
treatment advice.

## Phase 19 — AI evaluation, prospective validation, and research track

- [ ] 19.1 Expand the medical harness with longitudinal, temporal, multimodal,
  correction, contradiction, missingness, wearable-shift, OOD, and adaptive-
  policy golden sets in Vietnamese and English. _R18, R31_
- [ ] 19.2 Use LLMs to generate labeled synthetic red-team candidates, then
  human-review, deduplicate, version, and keep them separate from real-world
  outcome estimates and held-out sets. _R31_
- [ ] 19.3 Produce per-use-case datasheet, model card, TRIPOD+AI-aligned report
  where predictive, hazard analysis, human-AI workflow, error analysis, subgroup
  results, and rollback evidence. _R22, R31_
- [ ] 19.4 Run offline -> red-team -> shadow -> allowlisted pilot promotion with
  immutable manifests and owner approval at every transition. _R31_
- [ ] 19.5 For any AI feature that influences live health decisions, define and
  run proportional DECIDE-AI-style early clinical evaluation; use
  SPIRIT-AI/CONSORT-AI for prospective trials when applicable. _R22, R31_
- [ ] 19.6 Keep disease/deterioration prediction, individual treatment effects,
  digital twins, raw-waveform foundation models, federated/split learning, and
  continuous learning in separately approved research projects. _R28, R31_
- [ ] 19.7 If federated learning is researched, threat-model gradient leakage,
  non-IID bias, poisoning, secure aggregation, differential privacy, withdrawal/
  deletion, device energy, and reproducibility before any user device trial.
  _R15, R16, R31_
- [ ] 19.8 Add post-pilot drift, correction/override, abstention, adverse-event,
  provider change, and recall monitoring with predefined stop thresholds.
  _R20, R31_

Exit gate: each promoted AI capability has reproducible evidence for its exact
human-AI use case; high-risk research cannot leak into production through a
generic model or feature flag.

## 3. Mandatory validation matrix

After API/Python changes:

```bash
make lint
make type-check
make test
make docs-check
```

After ML/model changes:

```bash
cd services/ml
pytest -q
ruff check .
mypy --ignore-missing-imports src
```

Every trained or provider-backed release additionally runs its immutable
use-case evaluation suite, model/dataset manifest validation, safety harness,
subgroup/calibration report, shadow comparison, and artifact-signature check.
There is no single generic accuracy threshold that substitutes for these gates.

After web changes:

```bash
cd apps/web
npm run lint
npm run test
npm run build
npm run test:e2e
```

After mobile changes:

```bash
cd apps/mobile
flutter analyze
flutter test
flutter build apk --release \
  --dart-define=CLARA_API_BASE_URL=https://theclaracare.com
```

Database/worker gates:

- upgrade from the latest production-like snapshot;
- downgrade only where the migration is declared reversible, otherwise rehearse
  forward-fix/restore;
- reconcile row counts, public IDs, active revisions, outbox obligations, and
  profile isolation;
- crash workers during each job class and prove lease recovery/idempotency;
- restore backup and rebuild all projections with pinned rule versions.

## 4. Definition of done for every task

A task is done only when:

1. requirement and hazard references are recorded;
2. implementation and migration are reviewed;
3. positive, negative, authorization, consent, and failure-mode tests pass;
4. no-PII observability and alerts exist where operationally relevant;
5. user-visible copy is reviewed in Vietnamese and English where applicable;
6. accessibility behavior is tested for client work;
7. feature flag, rollback, and data reconciliation are documented;
8. security/privacy/clinical approval is captured when the task changes their
   risk; and
9. status documentation reflects what was actually verified.
