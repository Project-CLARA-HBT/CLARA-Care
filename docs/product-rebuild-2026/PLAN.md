# CLARA Care Product Rebuild — Implementation Plan

**Status:** executable migration plan  
**Date:** 2026-08-19  
**Strategy:** strangler rebuild with independently reversible slices  
**Primary rule:** do not start by restyling pages. First establish product IA, content contracts, bounded APIs and AI routing boundaries; then migrate experiences vertical-slice by vertical-slice.

---

## 1. Program objective

Deliver a consumer-first CLARA Care experience where ordinary users can:

- understand what matters today;
- ask health questions by text/voice/image/document without configuring AI modes;
- see one coherent health record/timeline with source/state clarity;
- manage medications safely;
- understand results and prepare for visits;
- add health information through multimodal review-first capture;
- control sharing, privacy and connected data;
- receive safe care-navigation guidance;
- use the product on web and mobile with accessible, plain-language UX.

The program must preserve or strengthen current authorization, consent, audit, provenance, GLHS and medication-safety guarantees.

---

## 2. Program principles

1. **Vertical slices over big-bang rewrite.** Each phase must produce a testable product increment.
2. **Safety invariants are migration gates.** Product simplification never weakens server checks.
3. **Hide complexity, do not delete capability blindly.** Internal modules can remain behind a simpler consumer projection.
4. **New AI is optional infrastructure.** UI migration must not depend on unofficial Gemini availability.
5. **No model promotion by reputation.** Every route is task-benchmarked.
6. **Real empty states beat fake content.** No synthetic dashboard filler.
7. **Vietnamese copy is product logic.** It receives review/tests, not last-minute translation.
8. **Compatibility is explicit.** Every old route/API has a disposition before removal.
9. **Measure comprehension and safety, not only clicks.**
10. **Rollback must remain possible at every rollout stage.**

---

## 3. Workstreams

### WS-A — Product/IA/content
Owns target mental model, information architecture, terminology, copy catalog, health-literacy checks and UX acceptance.

### WS-B — Web design system and shell
Owns tokens, shared components, route groups, shell decomposition, responsive/accessibility foundation.

### WS-C — Consumer API and data projection
Owns Home read model, unified Health projection, pagination, bounded writes, conflicts and notification metadata.

### WS-D — Ask and multimodal capture
Owns simplified Ask, attachments, intent planning, Universal Capture UI, candidate review and write proposals.

### WS-E — Model platform
Owns provider-neutral gateway, private Gemini adapters, task contracts, capability probes, model provenance and evaluations.

### WS-F — Care and medication
Owns medication convergence, lab/result explanation, visit preparation, after-visit actions and care navigation.

### WS-G — Connected health/mobile
Owns mobile IA parity, Health Connect connector, sync UX, permission flows and future HealthKit-compatible contracts.

### WS-H — Safety/security/quality
Owns GLHS/consent concurrency, security testing, accessibility, health literacy, performance, E2E, red-team and rollout gates.

---

## 4. Phase 0 — Freeze the baseline and define non-negotiables

### Goal
Create an indisputable implementation baseline before changing product architecture.

### Work

- record current `main` product baseline and `codex/commitloop-phase-a` research delta;
- snapshot route matrix, feature flags, API contracts and current production rollout assumptions;
- classify every web/mobile destination as consumer, professional, research, admin, compatibility or retirement candidate;
- record critical safety invariants and tests that must remain green;
- capture synthetic/no-PII screenshots of key current flows;
- establish top product metrics and event taxonomy;
- identify API/client minimum versions that must remain compatible;
- define feature-flag names and ownership.

### Exit gate

- route/capability inventory reviewed;
- safety invariant suite listed and runnable;
- no unidentified route will be removed by later work;
- baseline performance/bundle/accessibility evidence stored;
- rollback branch/artifact known.

---

## 5. Phase 1 — Foundations: design, content, shell and model boundary

### Goal
Build the reusable foundations that prevent the rebuild from becoming another set of page-specific implementations.

### WS-A deliverables

- consumer terminology dictionary VI/EN;
- banned/internal-first terminology list;
- controlled health-state labels;
- error/empty/loading copy patterns;
- health-literacy review checklist;
- content key naming convention.

### WS-B deliverables

- semantic design-token source;
- generated web/mobile tokens;
- common consumer primitives;
- route-group skeletons `(consumer)`, `(professional)`, `(admin)`;
- decomposed session/profile/preference/navigation boundaries;
- canonical new nav behind `consumer_shell_v2` flag.

### WS-C deliverables

- API v2 conventions: error envelope, cursor pagination, ETag/base version, idempotency, message keys;
- typed API client scaffolding;
- server-state query/cache conventions.

### WS-E deliverables

- refactor model policy from DeepSeek-specific pro/flash to provider-neutral route classes/capabilities;
- preserve existing approved provider adapter;
- add private unofficial Gemini adapter behind flags;
- synthetic capability probe;
- PII-safe model provenance object/event;
- no production task moved to Gemini yet.

### Exit gate

- old product still works;
- new shell can render synthetic fixtures at all target viewports;
- accessibility primitive tests pass;
- model gateway can resolve existing route and private Gemini aliases in non-production/synthetic mode;
- client cannot select arbitrary model/provider.

---

## 6. Phase 2 — Home vertical slice

### Goal
Replace module-launcher mental model with the daily health home.

### Backend

- implement `/api/v2/home` read model;
- return top action, today schedule, recent changes, alerts, integration state and profile metadata;
- use real data only;
- connect outbox invalidation.

### Web

- `/home` canonical route;
- Ask bar;
- top next-action card;
- recent changes;
- medication/visit/task schedule;
- real empty/error/loading states;
- active-profile clarity;
- legacy `/today` redirect/adaptation under flag.

### Mobile

- replace quick-action grid as primary Home composition;
- same conceptual order as web;
- native bottom navigation prototype;
- no privileged feature buffet in personal Home.

### Measurement

- home load success;
- first meaningful action time;
- action selection;
- backtracking;
- error vs empty-state correctness.

### Exit gate

- Home E2E passes on all supported viewports;
- no synthetic/fallback health data;
- critical alerts preserve severity/action;
- product can revert to old Home via flag.

---

## 7. Phase 3 — Unified Health and safe bounded writes

### Goal
Make PHR/LifeMap/medications/results/measurements/documents feel like one health record without unsafe schema collapse.

### Backend

- `/api/v2/health/summary`;
- paginated `/api/v2/health/timeline`;
- display projection state/provenance metadata;
- medication presentation resolver;
- conflict/review projection;
- bounded PHR subresource commands/PATCH;
- version/ETag conflict contract;
- derive/cache invalidation from outbox.

### Web

- `/health` overview;
- timeline with time/type filters;
- medication hub;
- results list/detail/trend;
- measurement views;
- document library;
- state/source badges;
- correction history;
- conflict review UI.

### Mobile

- Health tab with the same projection;
- detail screens optimized for touch;
- local pagination/caching without persisting PHI insecurely.

### Safety validation

- concurrency/lost-update tests on PostgreSQL;
- profile/grant revocation tests;
- current-vs-historical medication tests;
- no scanned medicine promoted to active state;
- correction/stale summary invalidation.

### Exit gate

- new consumer editing no longer depends on blind whole-record PUT;
- no silent lost updates under concurrency suite;
- current-state/provenance labels are correct across fixtures;
- legacy PHR/LifeMap/medicines routes remain safe redirects/adapters.

---

## 8. Phase 4 — Ask CLARA simplification and personal grounding

### Goal
Make AI interaction feel like one simple assistant while retaining rigorous internal routing.

### Backend/ML

- define consumer intent enum and risk policy;
- personal context builder with task-scoped GLHS/THSS selection;
- answer envelope with main message/actions/personal evidence/external sources/unknowns/safety/write proposals;
- route-level verifier for personal state and citations;
- consumer request no longer accepts raw execution mode/model provider;
- retain professional/research advanced controls in professional mode only.

### Web/mobile

- simple composer text/file/camera/voice affordances;
- source/context disclosure;
- “what CLARA knows/doesn't know” display;
- entry-context Ask from result/medication/visit/timeline;
- proposal cards for saveable health information;
- preserve conversation history and cancellation.

### Migration

- `/chat` redirects to `/ask` for consumer role while professional/research mode retains advanced workspace through an appropriate route/entry.

### Exit gate

- consumer user never needs Fast/Deep/Research selection;
- state utility/staleness/disclosure benchmarks meet locked thresholds;
- no hidden reasoning exposed;
- outage leaves record access intact;
- personal context usage is accurately disclosed.

---

## 9. Phase 5 — Multimodal “Add anything”

### Goal
Turn existing Universal Capture infrastructure into a flagship everyday workflow.

### Backend

- extend capture candidate schema for page/region and uncertainty reasons;
- image/PDF preprocessing pipeline;
- audio integration where appropriate;
- prompt-injection isolation;
- structured extraction through Model Gateway;
- normalization/duplicate/conflict checks;
- explicit GLHS-bound proposal commit.

### Model evaluation before live use

Build locked sets for:

- medication packages/prescriptions;
- lab reports;
- discharge/visit documents;
- vaccination/medical cards where supported;
- Vietnamese/English mixed documents;
- blur/rotation/glare/low-quality scans;
- malicious instructions embedded in documents.

Evaluate `gemini-3.6-flash-high` and `gemini-3.7-tiered` as private aliases per task alongside current approved baseline/fallback.

### UI

- one Add sheet from Home/Health;
- capture/upload progress;
- page preview;
- candidate review card;
- exact source highlight where possible;
- accept/edit/reject;
- safe partial success;
- no “AI saved automatically” behavior.

### Rollout

1. synthetic fixtures;
2. internal benign documents;
3. shadow extraction;
4. canary with explicit user review;
5. expand only after accuracy/safety gates.

### Exit gate

- extraction failure cannot lose source/draft;
- malformed output cannot reach commit;
- high-risk candidate fields require confirmation;
- prompt-injection tests pass;
- model route can be disabled without disabling manual entry.

---

## 10. Phase 6 — Medication, results and visit preparation intelligence

### Goal
Ship the high-value health workflows that turn longitudinal data into useful everyday actions.

### Medication

- unified current list + source states;
- scan-to-review;
- interaction explanation backed by authoritative tools;
- duplicate/conflict review;
- start/stop history;
- reminder/refill/expiry features only with real source dates.

### Results

- value/unit/reference range first;
- comparable trends;
- grounded plain-language explanation;
- clinician questions;
- no invented normal range or diagnosis.

### Visit preparation

- user goals/questions;
- longitudinal “what changed since last visit”;
- medication/allergy/current issue summary;
- source-aware generated questions;
- export/shareable handoff.

### After visit

- document/note upload;
- reviewable follow-up instructions/tasks;
- reviewable medication changes;
- source remains attached.

### Exit gate

- medication safety suite unchanged/stronger;
- result numerical fidelity tests pass;
- visit summary invalidates when source state changes;
- no AI-extracted treatment change commits without review.

---

## 11. Phase 7 — Care navigation

### Goal
Help users choose an appropriate next care setting without turning CLARA into an autonomous diagnostic product.

### Work

- define intended-use boundary;
- build deterministic emergency/red-flag floor;
- approved structured question set;
- acuity/care-setting logic;
- model wording layer only after safety result;
- clear reason/explanation;
- clinician handoff summary;
- local resource routing remains separate from clinical urgency.

### Evaluation

- clinician-authored/adjudicated cases;
- under-triage threshold is a hard release gate;
- over-triage measured separately;
- Vietnamese colloquial symptom descriptions;
- negation and timing;
- pediatric/pregnancy/high-risk scenarios either validated or explicitly routed out of scope;
- adversarial reassurance prompts.

### Exit gate

- generative model cannot lower deterministic minimum urgency;
- out-of-scope populations/use cases are explicitly handled;
- copy tells users what to do and when;
- no disease probability list as primary consumer answer.

---

## 12. Phase 8 — Connected health and device integration

### Goal
Reduce manual data entry and make CLARA longitudinally useful between visits.

### Android Health Connect

Start with explicitly approved categories:

- activity/steps;
- sleep;
- selected vitals;
- body measurements.

Work:

- native bridge/plugin if needed;
- feature availability checks;
- permission education and progressive request;
- sync on/off settings;
- background sync/checkpoints;
- dedupe and source identity;
- data quality/missingness;
- last sync state;
- trend display;
- deterministic trend calculations + optional AI explanation.

Medical Records/FHIR through Health Connect remains a separate experimental flag until API and store-policy readiness are confirmed.

### Future iOS

Implement the same canonical connector interface for HealthKit/Health Records without blocking Android-first delivery.

### Exit gate

- revoke permission stops sync correctly;
- no duplicate events on retry;
- device/source changes are visible;
- connected data is not labeled as clinician-confirmed;
- model explanation handles missingness and abstains appropriately.

---

## 13. Phase 9 — Privacy, sharing and account convergence

### Goal
Make trust controls understandable and easy to use.

### Work

- `/you` canonical account home;
- profile/emergency card;
- language/accessibility;
- notification controls;
- connected data sources;
- granular family sharing;
- consent and AI-use explanation;
- export/delete/data rights;
- access history where available;
- active devices/sessions when backend supports it.

### Sharing UX

- choose person;
- choose categories;
- state purpose/duration;
- preview exact categories;
- confirm;
- show active grants;
- revoke;
- verify cache/derived summary invalidation.

### Exit gate

- user can understand what is shared without reading legal text;
- revoke tests pass across direct read, caches and AI-derived views;
- privacy copy reviewed for accuracy.

---

## 14. Phase 10 — Professional mode convergence

### Goal
Preserve sophisticated clinician/research functions while removing them from consumer cognitive load.

### Clinician

- professional work home;
- explicit patient/case context;
- Ask CLARA professional output;
- Council integrated into case workflow;
- Scribe single consent -> capture -> draft -> review -> attest flow;
- evidence attached where appropriate.

### Research

- retain advanced query/retrieval/output controls in research mode;
- do not expose research modes to ordinary users;
- preserve reproducibility/export behavior.

### Admin

- remain operationally separate;
- no consumer bundle loading of admin telemetry.

### Exit gate

- privileged routes remain authorized correctly;
- personal/work context cannot be confused;
- clinician note state wording remains draft vs attested/signed;
- consumer navigation no longer contains professional feature names.

---

## 15. Phase 11 — Hardening and retirement

### Goal
Move from parallel surfaces to canonical rebuild and delete only proven dead compatibility debt.

### Hardening

- full WCAG 2.2 AA review;
- keyboard/screen-reader manual pass;
- Vietnamese/English copy parity;
- CDC Clear Communication scoring for selected high-risk materials;
- performance profiling and bundle reduction;
- real DB concurrency tests;
- security red-team for uploads/gateway/prompt injection;
- model drift/capability probe failure drills;
- rollback drill;
- backup/restore verification;
- support/runbook updates.

### Retirement criteria for each legacy route/component

Delete only when all are true:

1. canonical replacement has parity for supported users;
2. redirect/deep-link tests pass;
3. production traffic below agreed threshold for agreed observation window;
4. no old supported client still requires it;
5. rollback no longer depends on it or replacement artifact is retained;
6. import search shows no active dependency;
7. tests/build pass after removal.

---

## 16. Rollout plan

### UI rollout

- internal accounts;
- dogfood;
- 5% eligible consumer traffic;
- 25%;
- 50%;
- 100% after product/safety gates.

### Model rollout

Independent per task:

```text
configured -> capability-probed -> offline-evaluated -> shadow -> canary -> approved
```

A model can be rolled back without rolling back the UI.

### Stop conditions

Pause expansion if any of these occur:

- cross-profile/prohibited disclosure;
- dangerous under-triage regression;
- medication safety regression;
- stale/unauthorized write accepted;
- material increase in record-write conflicts/lost drafts;
- unexplained model version/capability drift;
- crash/error regression on top consumer flows;
- significant accessibility blocker;
- content mistranslation that changes safety meaning.

---

## 17. Dependency graph

```text
Baseline inventory
  ├─> Content/IA foundation ─> Consumer shell ─> Home
  ├─> API v2 conventions ────> Home read model ─> Home
  │                        └─> Bounded writes ─> Health
  ├─> Design system ─────────> Home/Health/Ask/Care/Mobile
  └─> Model Gateway ─────────> Ask ─> Multimodal ─> Result/Visit/Care AI

Health projection ─> Visit prep
Health projection ─> Ask My Health
Health projection ─> Connected-health trends
Universal Capture ─> Medication scan / documents / after-visit
GLHS concurrency hardening ─> every AI write proposal
```

Care navigation must not block the rest of the consumer rebuild; it can ship later behind its own gate.

---

## 18. Quality gates by phase

Every phase must pass:

- type/lint/unit tests;
- affected API contract tests;
- security/RBAC/profile tests;
- localization key parity;
- no-PII analytics checks;
- affected E2E;
- accessibility smoke;
- build/bundle gate;
- explicit rollback test/plan.

AI phases additionally pass:

- locked task evaluation;
- schema-valid rate threshold;
- safety verifier thresholds;
- adversarial prompt injection;
- Vietnamese cases;
- route capability probe;
- provenance correctness.

Data-write phases additionally pass:

- PostgreSQL integration/concurrency;
- stale base version;
- duplicate retry/idempotency;
- consent/authorization change between read and commit;
- audit reconstruction.

---

## 19. Metrics and decision reviews

### Product review dashboard

- first value completion;
- Home primary-action completion;
- Ask completion/error/cancel;
- capture upload -> reviewed -> saved funnel;
- medication review completion;
- result explanation open/useful feedback;
- visit-prep completion;
- share/revoke completion;
- navigation backtracking.

### Safety review dashboard

- stale proposal reject rate;
- unauthorized/revoked attempts blocked;
- emergency floor trigger count;
- under/over-triage evaluation;
- medication safety block outcomes;
- candidate edit/reject rates for critical fields;
- unsupported claim/verifier failure;
- cross-profile red-team status.

### Model review dashboard

- route/probe status;
- latency p50/p95;
- structured invalid rate;
- verifier/abstention rate;
- model/gateway version drift;
- cost where available;
- frozen eval score vs production-approved threshold.

---

## 20. Risk register

### R1 — Scope explosion
**Risk:** rebuilding every module simultaneously.  
**Mitigation:** consumer vertical slices; professional/admin after core consumer flows.

### R2 — UI simplification hides capability
**Risk:** users lose routes/features.  
**Mitigation:** route disposition matrix, redirects, contextual actions, professional mode, E2E parity.

### R3 — Database semantic collapse
**Risk:** one “Health” UI causes unsafe merged truth.  
**Mitigation:** projection layer with preserved source/state; no forced table merge.

### R4 — Unofficial model instability
**Risk:** gateway/model changes unexpectedly.  
**Mitigation:** adapter isolation, capability probes, pinned config, shadow/canary, per-task rollback.

### R5 — Multimodal extraction errors
**Risk:** OCR/VLM turns wrong text into medication/result values.  
**Mitigation:** schema validation, source highlight, critical-field confirmation, deterministic validation.

### R6 — Consumer AI over-trust
**Risk:** polished answer appears authoritative.  
**Mitigation:** main message + source/unknown state, no arbitrary confidence, care escalation, clear data provenance.

### R7 — Lost updates
**Risk:** current whole-record PHR writes overwrite concurrent changes.  
**Mitigation:** bounded writes + ETag/base version + conflict review.

### R8 — Notification burden
**Risk:** proactive companion becomes noisy.  
**Mitigation:** category preferences, bundling, quiet hours, no guilt/streak mechanics.

### R9 — Wearable overload
**Risk:** lots of data, little meaning.  
**Mitigation:** selected metrics, deterministic trends, missingness, no unsupported prediction.

### R10 — Consumer/professional context mix
**Risk:** clinician sees personal shell or acts on wrong profile.  
**Mitigation:** explicit mode/context, distinct route layout, active patient/profile banner, server authorization.

---

## 21. Implementation sequencing rule for Codex/agents

When autonomous coding agents execute this plan:

1. read `SPEC.md`, `REQUIREMENTS.md`, `TECH_DESIGN.md`, `PLAN.md`, `TASK_LIST.md` before editing;
2. inspect current code at task start; never assume paths/contracts are unchanged;
3. implement the smallest end-to-end slice that satisfies the task;
4. preserve existing safety tests and add missing regression tests before deleting compatibility code;
5. never hard-code unofficial model credentials/endpoints;
6. never invent production health content/metrics to satisfy screenshots;
7. never replace a failing real test with a mock merely to pass CI;
8. record deviations from these specs explicitly in the PR/implementation note;
9. do not rename research concepts in academic artifacts unless the task requires it; product language and research nomenclature can differ;
10. stop rollout, not implementation quality, when a new model is unavailable — deterministic/current approved paths remain valid.

