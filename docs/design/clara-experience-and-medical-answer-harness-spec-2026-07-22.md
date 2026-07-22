# CLARA Experience and Medical Answer Harness Specification

Status: implementation and delivery plan

Date: 2026-07-22

Owners: Product, Clinical Safety, Web, API, ML, Data/Evaluation, Security

## 1. Executive intent

CLARA must become two things at once:

1. A modern, calm care workspace that makes the next safe action obvious.
2. A measurable medical-answer system whose quality comes from engineered evidence, verification, and release gates—not from prompt confidence.

The experience redesign and answer-quality program share one rule: expose the state that matters to the user while keeping implementation detail out of the primary view. A patient should see urgency, uncertainty, sources, and next steps. A clinician or auditor may progressively disclose retrieval, verification, and provenance.

CLARA remains an information and decision-support product. It must not present itself as a physician, silently personalize dosage, or convert model confidence into clinical certainty.

## 2. External basis

This specification applies the following primary guidance and research:

- [WHO ethics and governance of AI for health](https://www.who.int/publications/i/item/9789240037403): autonomy, safety, transparency, accountability, inclusiveness, and sustainability.
- [WHO guidance for large multi-modal models in health](https://www.who.int/news/item/18-01-2024-who-releases-ai-ethics-and-governance-guidance-for-large-multi-modal-models): well-defined tasks, post-release auditing, stakeholder participation, and impact assessment.
- [FDA Clinical Decision Support Software guidance](https://www.fda.gov/media/162880/download): preserve the basis for recommendations so a health professional can independently review it.
- [NIST Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence): govern, map, measure, and manage risks throughout the lifecycle.
- [NIST AI Resource Center](https://airc.nist.gov/): testing, evaluation, verification, and validation practices.
- [MedRAG/MIRAGE](https://arxiv.org/abs/2402.13178): medical RAG benefits from diverse corpora/retrievers and must measure retrieval configuration, not only final-answer accuracy.

## 3. Product outcomes and success measures

### Experience outcomes

- A new user identifies the primary action on every core page within five seconds.
- Mobile and desktop share one information architecture and state vocabulary.
- Safety alerts are distinguishable from routine notices without relying on color.
- The shell supports 320 px reflow, 200% text zoom, keyboard-only operation, dark mode, and reduced motion.
- Common tasks require fewer context switches: ask, review evidence, save/share, and continue.

### Answer outcomes

- Emergency recall is at least 99.5% on a clinically reviewed red-flag set; false negatives are release blocking.
- Legal/prescribing hard-guard recall is at least 99% on adversarial Vietnamese and English prompts.
- Citation entailment is at least 95% for critical claims and 90% overall.
- Citation coverage is at least 95% for externally verifiable medical claims.
- Unsupported critical claims are zero in the release set.
- Retrieval recall@20 is at least 90% for gold evidence on supported tasks.
- Medication identity normalization exceeds 98% exact ingredient mapping on the Vietnamese medication test set.
- P95 time-to-first-useful-token remains under 3 seconds for Fast and under 8 seconds for Deep, excluding declared long-running research jobs.
- Every answer exposes source recency, limitations, and an appropriate next action.

These are deployment gates, not aspirational dashboard metrics.

## 4. Experience architecture

### 4.1 Global shell

Desktop uses three stable layers:

- Navigation rail: product destinations, grouped by care, medication, research, clinical, and administration.
- Command bar: current page context, Ask CLARA action, help, theme/language, and account identity.
- Content canvas: page header, alerts/next action, primary work region, and optional contextual rail.

The rail collapses to icons but preserves tooltips and accessible names. Settings and account actions are not mixed with product navigation. The selected destination uses an indicator, filled icon, foreground weight, and background—not color alone.

Mobile uses a compact command bar, a modal full-navigation drawer, and no more than four bottom destinations. The bottom navigation must not cover content or duplicate every drawer destination.

### 4.2 Page contract

Every authenticated route follows:

1. Context: eyebrow/breadcrumb, title, short purpose, last-updated or scope when relevant.
2. Action: one primary action, then secondary actions in a menu/toolbar.
3. Attention: urgent/needs-attention messages before routine summaries.
4. Work: task content in one dominant surface; secondary detail in tabs, accordion, or rail.
5. Provenance: sources, status, responsible system/person, and update time.

### 4.3 Core route target states

#### Dashboard

Replace decorative telemetry with a daily care brief: needs attention, recent activity, medicine state, saved research, and role-appropriate shortcuts. Operational runtime data stays admin-only.

#### Chat

Use one conversation canvas. Mode selection explains Fast, Deep, and Deep Beta in terms of time, evidence, and verification. Advanced retrieval settings live behind progressive disclosure. Each answer renders: direct answer, safety/uncertainty, actionable next steps, evidence, and expandable reasoning trace.

#### Research

Use a research brief rather than a larger chat box: question, population/intervention/comparator/outcome extraction where applicable, date/language/source constraints, protocol preview, progress, evidence table, synthesis, contradictions, and export.

#### PHR and medication

Lead with completeness and next action. Editing uses sections and review states. Medicine identity, active ingredient, route, strength, and provenance remain distinct fields. Safety checks show why the alert applies and what to do next.

#### Council and Scribe

Use guided stages with a persistent case header. Council makes consensus and disagreement explicit. Scribe separates recording, transcript, structured note, clinician verification, and export; unverified content cannot appear completed.

#### Administration

Use filterable tables, exception queues, and contextual drawers. Destructive configuration is isolated and requires confirmation with consequences.

## 5. UI system

### Light theme

Light mode is the reference theme. It uses a cool-neutral canvas, white working surfaces, deep ink typography, a single cobalt brand family, subtle lavender for research accents, and semantic status colors only for genuine state. The layout may use a very low-contrast atmospheric gradient behind the shell, but cards remain opaque and readable.

### Geometry and density

- 4 px base grid; 12/16 px control padding; 24/32 px page grouping.
- 44 px minimum interactive target.
- 8–12 px component radii; 14–18 px large workspace radii.
- One low shadow level for cards, one medium for menus, one high for dialogs.
- Default desktop content width 1440 px; prose remains at 72 characters.

### Typography

Segoe UI Variable/Segoe UI/native system. Body 14–16 px, meaningful captions at least 12 px, page titles 28–32 px. Use semibold rather than extra-bold for hierarchy. Vietnamese diacritics must render without clipping.

### States

Every data surface implements loading, empty, error, stale, offline, forbidden, partial, and completed states. Partial upstream failure names the unavailable capability without exposing raw errors. User input persists across recoverable failures.

## 6. Medical answer architecture

### 6.1 Request contract and risk classification

Normalize each request into:

- actor/role and consent state;
- language and locale;
- intent and task class;
- clinical risk tier: emergency, high, moderate, informational;
- entities: symptoms, duration, age band, sex/pregnancy when volunteered, conditions, medicines, ingredients, allergies, labs, and units;
- time sensitivity and required source recency;
- ambiguity/missing-critical-context list;
- prohibited action flags.

Emergency detection and legal hard guards run before retrieval or generation. High-risk ambiguity triggers a concise clarification or safe escalation, not invented context.

### 6.2 Task-specific protocols

Do not use one universal RAG prompt. Route to explicit protocols:

- symptom information and triage education;
- medication identity and interaction;
- lab/result explanation;
- guideline/evidence question;
- research synthesis;
- clinical documentation;
- council decision support;
- administrative/non-medical.

Each protocol declares allowed outputs, required evidence classes, critical claims, minimum context, escalation rules, and evaluation suite.

### 6.3 Evidence acquisition

Create a governed evidence registry with source class, jurisdiction, specialty, document type, version, publication/update date, retraction/correction status, license, acquisition hash, parser version, and review status.

Source priority is task dependent:

1. Vietnamese Ministry of Health and applicable local regulation/guidance.
2. International/national guidelines and regulator labels.
3. Systematic reviews and evidence syntheses.
4. Primary peer-reviewed studies.
5. Trusted drug terminologies/databases.
6. General web sources only when the task permits and provenance is explicit.

Retrieval combines lexical, dense, medical-entity, citation-graph, and metadata filters. Query expansion includes Vietnamese/English synonyms, ingredient/brand mappings, abbreviations, and spelling variants. Retrieve broadly, then rerank for task relevance, authority, recency, population match, and contradiction coverage.

### 6.4 Context engineering

The context builder must:

- deduplicate near-identical passages and mirrored documents;
- preserve section headings, tables, units, eligibility criteria, and source dates;
- group evidence by sub-question rather than concatenate by score;
- include supporting and conflicting evidence;
- reserve explicit space for safety policy and user context;
- enforce per-source and total token budgets;
- mitigate lost-in-the-middle by placing protocol, critical evidence, and answer contract at stable positions;
- label untrusted retrieved text and prevent it from becoming instructions.

### 6.5 Structured generation

Generation produces an internal typed answer plan before prose:

- direct answer;
- risk/escalation status;
- atomic claims with claim type and criticality;
- citation candidates per claim;
- uncertainty and missing context;
- recommended next actions;
- disallowed-content check;
- user-facing reading level and language.

The renderer turns only a validated plan into patient or professional prose. The final response separates known, uncertain, and action sections.

### 6.6 Verification and release policy

Verification is claim based:

1. Extract atomic factual and recommendation claims.
2. Check citation presence and source authority.
3. Verify entailment/contradiction against the cited passage.
4. Validate medication names, doses/units, ranges, and temporal statements deterministically where possible.
5. Run cross-source contradiction and guideline-jurisdiction checks.
6. Run emergency, prescribing, privacy, and prompt-injection policies again.
7. Compute a decision, not merely a score: allow, revise, ask, abstain, or escalate.

Any unsupported critical claim blocks the answer. Revision gets one bounded attempt with failure reasons; repeated failure produces a safe abstention with useful next steps.

## 7. Harness engineering

### 7.1 Scenario model

Use versioned JSONL/YAML cases containing input, role, locale, task, risk tier, supplied context, expected route, required/forbidden concepts, gold evidence identifiers, expected citations, allowed uncertainty, and clinical reviewer metadata.

Test families:

- emergency and crisis red flags;
- adversarial prescribing/diagnosis/dosage requests;
- common Vietnamese consumer questions;
- pregnancy, pediatric, geriatric, renal/hepatic, allergy, and polypharmacy risk slices;
- medication brand/ingredient ambiguity and OCR noise;
- guideline conflicts and outdated evidence;
- insufficient-context questions;
- prompt injection in user text and retrieved documents;
- citation laundering and non-entailing citations;
- graceful degradation for every upstream dependency;
- multilingual and health-literacy variants;
- long conversations with contradictory prior turns.

### 7.2 Component evaluation

Measure independently:

- router intent/risk recall and calibration;
- entity extraction and normalization;
- retrieval recall@k, precision@k, nDCG, authority, recency, and diversity;
- reranker pairwise preference and population match;
- claim segmentation;
- citation coverage, correctness, entailment, and source quality;
- contradiction detection;
- deterministic medication/unit validators;
- safety policy precision/recall;
- latency, availability, and cost per stage.

An end-to-end score cannot hide a failed component.

### 7.3 End-to-end evaluation

Run deterministic checks first, then model graders with blinded pairwise rubrics, then mandatory human clinical review for high-risk release sets. LLM judges never have sole authority over safety gates.

Score axes: clinical correctness, harmfulness, completeness, relevance, uncertainty calibration, actionability, citation quality, readability, cultural/linguistic fit, and policy compliance. Report mean, worst slice, and confidence interval. A release fails on a critical slice even if the average improves.

### 7.4 Continuous hard-negative loop

Mine only de-identified production signals: abstentions, revisions, low citation coverage, conflicting sources, repeated queries, user corrections, and clinician flags. Cluster by failure mode, create reviewed cases, reproduce against the pinned system, fix the responsible component, and keep the case permanently in regression.

### 7.5 Reproducibility

Every run pins code commit, prompt/protocol version, model/provider/version, decoding parameters, corpus snapshot, index build, retriever/reranker versions, feature flags, and evaluator version. Store stage artifacts with PII-safe redaction and retention controls.

## 8. Online observability and quality control

Record PII-free stage events: route, risk tier, protocol, retrieval counts/source classes, citation/verification decision, fallback class, latency, token/cost bands, and abstention/escalation reason. Never record raw query, patient name, medicine list, or free-text answer in general telemetry.

Dashboards show safety first: emergency routing, critical claim blocks, citation failures, stale-source usage, fallback rate, dependency degradation, and slice drift. Alert on rate changes, not only outages.

Use shadow evaluation for new retrievers, rerankers, prompts, and models. Promotion sequence: offline component gate, offline E2E gate, clinical review, shadow, small canary, monitored expansion, full release. Maintain one-command rollback of protocol/model/index versions.

## 9. Security and privacy

- Treat retrieved content as untrusted data; isolate it from system instructions.
- Enforce least-privilege connectors and per-source allowlists.
- Encrypt stored clinical artifacts and audit access.
- Redact PII before external provider calls when the task allows; block disallowed transfers.
- Separate user-facing provenance from internal debug traces.
- Threat-model membership inference, prompt injection, citation spoofing, data poisoning, insecure file parsing, and cross-tenant leakage.

## 10. Delivery roadmap

### Phase 0 — Baseline and governance (1–2 weeks)

- Freeze current corpus/index/protocol/model manifests.
- Establish clinical safety owner and release sign-off.
- Build the risk taxonomy, claim schema, and 300-case critical safety set.
- Capture current component and E2E baseline.

### Phase 1 — Retrieval and provenance (2–4 weeks)

- Govern source registry and document versions.
- Add task-specific retrieval, authority/recency filters, contradiction retrieval, and ingredient normalization.
- Ship retrieval/citation component dashboards and gates.

### Phase 2 — Structured answer and verification (3–5 weeks)

- Implement typed answer plans and atomic claims.
- Add entailment, contradiction, unit/medication, and critical-claim blockers.
- Render calibrated uncertainty and actionable next steps.

### Phase 3 — Harness and continuous evaluation (2–4 weeks)

- Expand to at least 2,000 reviewed cases and explicit risk slices.
- Add adversarial, degradation, long-conversation, and prompt-injection suites.
- Add blinded pairwise and clinician review workflows.

### Phase 4 — Adaptive research workflow (3–6 weeks)

- Add protocol preview, query decomposition, evidence tables, contradiction synthesis, and living-source refresh.
- Calibrate Fast/Deep/Deep Beta routing by complexity and risk.
- Introduce shadow/canary promotion for component changes.

## 11. Definition of done

- The redesigned shell and critical workflows pass browser tests at mobile and desktop sizes.
- All existing unit, accessibility, contrast, type/build, and backend suites pass.
- The medical harness runs from a pinned manifest and produces component, slice, and E2E reports.
- Critical safety thresholds pass with clinical sign-off.
- No unsupported critical claim reaches the user in the release set.
- Production has PII-safe quality telemetry, canary controls, and a tested rollback.
- Documentation states supported use cases, unsupported use cases, evidence freshness, limitations, and incident ownership.
