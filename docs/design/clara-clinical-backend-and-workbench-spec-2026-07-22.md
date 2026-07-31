# CLARA Clinical Backend and Evidence Workbench Specification

Status: implementation specification

Date: 2026-07-22

Scope: CLARA Scribe, AI Council, Medicine Manager/CareGuard, Chat/Research medical-answer harness

Implementation checkpoint (same date): the first production slice described in
section 14 is implemented and tested. Items still listed as future release gates
remain requirements, not claims about the deployed system.

## 1. Product decision

CLARA is not positioned as another empty chat box. Its primary product is a **longitudinal clinical evidence workbench**: a user starts or resumes a health case, brings records and medicines into a governed context, asks a question or starts a protocol, sees what CLARA checked, resolves missing information, and receives reusable artifacts with evidence and explicit safety state.

Chat is one input method inside the workbench. The durable product objects are:

- case: the bounded health question or care episode;
- patient context snapshot: consented demographics, conditions, allergies, medicines, observations, and provenance;
- evidence ledger: sources, versions, passages, retrieval scores, dates, conflicts, and claim links;
- clinical artifact: answer brief, comparison, medicine review, timeline, appointment brief, Council report, or Scribe note;
- task: a resumable protocol with typed stages and status;
- decision record: what was recommended, why, uncertainty, blocked claims, reviewer actions, and model/data versions;
- follow-up plan: questions, monitoring signals, reminders, and escalation triggers.

The differentiator from general chat products is inspectability and continuity. Every consequential result is a versioned artifact, not transient prose. A user can switch views without reprompting: answer, evidence map, contradiction table, medicine graph, timeline, data gaps, and clinician handoff.

## 2. Non-negotiable requirements

1. Production paths must never return fixtures, synthetic patients, demo payloads, or fabricated clinical facts.
2. A deterministic rule or extractive fallback is allowed only when it operates on real request data and is labeled with its actual engine and limitations.
3. Missing providers or evidence fail closed: `unknown`/`incomplete`, never a fabricated all-clear.
4. Clinical claims are generated only after retrieval and are linked to evidence spans or explicitly labeled as patient-reported/inferred.
5. Emergency detection runs before model generation and can bypass all slow stages.
6. No hidden chain-of-thought is exposed. CLARA exposes a concise structured rationale, decisive observations, evidence links, disagreements, and verification results.
7. Patient and clinician roles have separate permissions and presentation. Council and final Scribe signing are clinician-only.
8. Raw clinical content never enters general telemetry. Audit records remain owner-scoped and purpose-bound.
9. Every provider, dataset, prompt, model, terminology system, and policy has a recorded version.
10. A production feature is not “integrated” until readiness, provenance, expiry/version, and a real smoke result are observable.

## 3. As-built audit and gaps

### 3.1 Scribe

Already real:

- persisted sessions, transcripts, note versions, addenda, consent, audit, lifecycle, exports, and clinician RBAC;
- real audio upload and configured OpenAI-compatible audio transcription call;
- grounding, structured extraction, coding suggestions, WER/fairness metadata, and immutable review/signing foundations;
- SSE transport and template registry.

Gaps:

- Google Chirp-3 is now a real credentialed adapter, but production readiness
  still requires a deployment project, ADC/workload identity, an allowed
  recognizer and a smoke result.  Without those, it deliberately returns no
  transcript and the independent configured fallback must handle the request;
- “streaming” buffers the full upload and adapts a batch result;
- the template note endpoint constructs `NoteGenerator()` without an LLM, so it always uses an extractive deterministic fallback;
- the legacy SOAP generator invents generic assessments and plan language not directly supported by the transcript;
- audio blobs/jobs, chunk idempotency, provider request IDs, retention state, and retry leases are not durable first-class records;
- diarization, vocabulary adaptation, and code-switch normalization are not fully wired to a real provider;
- signing must require a grounding report and unresolved-item acknowledgement.

### 3.2 AI Council

Already real:

- persisted cases, immutable run history, owner isolation, streaming relay, oversight actions, disclosure, metrics, and safety fast paths;
- deterministic specialist rules, negation-aware red flags, conflict calculation, data-quality scoring, follow-up questions, and clinician review directive.

Gaps:

- the current “specialists” are rule functions, not independent model-backed clinical reviews;
- citations mostly point back to intake/rules, not external medical evidence;
- the neural scorer is fixed hand-authored weights in shadow mode, not a validated learned model;
- no shared case evidence packet, specialist evidence assignments, claim verification, or adjudicator stage;
- no durable stage attempts, leases, provider manifests, claim ledger, or reviewer disposition per claim;
- the output can look more authoritative than its evidence basis unless rule/model modes are prominent.

### 3.3 Medicine Manager and DrugBank

Verified on production on 2026-07-22:

- licensed DrugBank manifest version `drugbank-2026-07-03`;
- 17,430 drugs parsed;
- 1,428,193 DDI pairs;
- 59,934 dictionary records reported by the manifest;
- a 260,481,024-byte SQLite DDI index containing all 1,428,193 pairs;
- memory-safe pair lookup enabled by default;
- OpenFDA label/FAERS corroboration and a curated Vietnamese safety layer.

Integration status: **DDI pair lookup is integrated, but provenance and reproducibility are incomplete**.

- DrugBank alerts are currently emitted with `source=local_rules`; this must be corrected to `drugbank`.
- `source_used` and fallback semantics do not currently count DrugBank separately.
- the deployed artifact contains the final SQLite index and manifest, but not the 300 DDI shards or 43 dictionary shards named by the manifest; it cannot rebuild itself from the deployed artifact.
- the 59,934-entry DrugBank dictionary is not available to the runtime normalization path, limiting brand/synonym coverage.
- dataset readiness and pair count are not exposed through a protected operational endpoint.

### 3.4 Chat and Research

Already real:

- routed fast/deep/deep-beta modes, hybrid retrieval, scientific connectors, uploaded files, research jobs, citations, verification, workspace persistence, sharing, and safety policies.

Gaps:

- the dominant interaction remains conversation-first rather than case/artifact-first;
- context, evidence, claims, contradictions, decisions, and monitoring are not one durable normalized domain model;
- weak or missing evidence can still be hidden inside polished narrative;
- evaluation is broad but is not yet the deploy-authoritative manifest for every answer pipeline version.

## 4. Target architecture

```text
Web / mobile
  -> API policy boundary (auth, consent, RBAC, idempotency, ownership)
     -> durable workflow + outbox (Postgres)
        -> ML orchestration workers
           -> emergency/risk classifier
           -> context compiler
           -> governed retrieval + terminology + DrugBank
           -> typed planner
           -> specialist/note/answer generators
           -> claim verifier + safety adjudicator
        -> object storage (encrypted audio/source artifacts)
        -> evidence and artifact registry (Postgres + vector index)
        -> PII-safe metrics and owner-scoped audit
```

All long-running work uses persisted jobs with an idempotency key, lease owner, lease expiry, attempt count, bounded retry class, heartbeat, cancellation, and terminal manifest. The API never holds a database transaction open across provider calls.

## 5. Shared data model

### `clinical_cases`

`id`, `owner_user_id`, `case_type`, `title`, `status`, `risk_tier`, `purpose`, `context_version`, `created_at`, `updated_at`, `closed_at`.

### `clinical_context_snapshots`

Immutable JSON snapshot with per-field provenance. Stores only consented data required for the case. Each field has `value`, `source_kind`, `source_id`, `observed_at`, and `confidence`.

### `clinical_workflow_runs`

`id`, `case_id`, `protocol`, `protocol_version`, `status`, `idempotency_key`, `lease_owner`, `lease_expires_at`, `attempt`, `risk_tier`, `provider_manifest_json`, `started_at`, `finished_at`, `failure_class`.

### `clinical_stage_runs`

Append-only stage attempts: input digest, output artifact reference, status, timing, provider/model/dataset versions, retry class, and PII-free failure code.

### `evidence_records`

Normalized source metadata and immutable captured passage: source class, authority tier, publication/effective/review dates, jurisdiction, URL/identifier, checksum, retrieval method, and license.

### `clinical_claims`

Atomic claim text, claim class, criticality, source artifact, support links, contradiction links, verification verdict, verifier version, and release decision (`allow`, `revise`, `block`, `abstain`, `escalate`).

### `clinical_artifacts`

Versioned user-visible result with type, structured payload, rendered projection, verification summary, supersedes relation, review/sign status, and export checksum.

### `clinical_review_actions`

Append-only clinician acknowledgement, edit, override, reject, sign, addendum, and handoff records. Stores before/after artifact version references and reason code.

## 6. Scribe backend specification

### 6.1 Encounter workflow

`created -> consented -> recording/uploading -> transcribing -> transcript_review -> drafting -> verification -> clinician_review -> signed -> amended|exported`.

Only a clinician can move to `signed`. A signed version is immutable; changes create an addendum or a new superseding version.

### 6.2 Real audio pipeline

- encrypted object storage; Postgres stores object key, digest, MIME, byte count, duration, retention deadline, and consent basis;
- chunk upload with `encounter_id + chunk_index + sha256` uniqueness;
- server validates media by magic bytes and decodes with an isolated media worker;
- ASR provider adapter returns provider request ID, language, words/segments, timestamps, confidence, speaker, and degraded state;
- real provider choices: configured OpenAI-compatible Whisper/audio endpoint; Google STT V2 only when the actual client and credentials pass readiness;
- terminology hints are generated from the case medication/problem list but never rewrite the canonical transcript;
- transcript corrections are append-only edits with original span, replacement, actor, and reason.

### 6.3 Note generation

- compile reviewed transcript spans and selected template;
- model must return strict JSON matching the template;
- every sentence is decomposed into claims and aligned to transcript spans;
- unsupported clinical facts are removed, not softened;
- absent information renders as “not documented”, never as a normal finding;
- assessment/plan content is separated into `documented_by_clinician` versus `draft_suggestion`;
- medications, allergies, dose, and diagnoses require exact transcript/context provenance;
- coding is suggestion-only and cannot be exported as accepted without clinician action.

### 6.4 Scribe APIs

- `POST /scribe/encounters` with idempotency key;
- `POST /scribe/encounters/{id}/audio/chunks`;
- `POST /scribe/encounters/{id}/transcription-jobs`;
- `GET /scribe/encounters/{id}/events` (SSE from persisted events);
- `PATCH /scribe/encounters/{id}/transcript/spans/{span_id}`;
- `POST /scribe/encounters/{id}/note-jobs`;
- `GET /scribe/encounters/{id}/grounding`;
- `POST /scribe/encounters/{id}/review-actions`;
- `POST /scribe/encounters/{id}/sign`;
- `POST /scribe/encounters/{id}/addenda`;
- `GET /scribe/encounters/{id}/exports/{format}`.

### 6.5 Release gates

- no fabricated medication/allergy/dose/diagnosis in the grounded golden set;
- critical unsupported claim release rate = 0;
- transcript word error rate and medication-token error rate reported by Vietnamese/accent/noise slices;
- speaker attribution quality measured only where reference labels exist;
- note completeness, span support, clinician edit distance, time saved, and signing abandonment tracked;
- real-provider canary required; placeholder provider cannot report ready.

## 7. AI Council backend specification

### 7.1 Council is structured dissent, not model role-play

Each Council run begins with one immutable case packet and evidence packet. Specialists receive the same normalized facts plus specialty-specific evidence. They cannot see one another’s conclusions in round one.

Stages:

1. intake validation and missing-data questions;
2. emergency and medication safety gates;
3. evidence retrieval and freshness/authority filtering;
4. independent specialist assessments;
5. claim extraction and evidence verification;
6. deterministic conflict matrix;
7. adjudicator synthesis constrained to verified claims;
8. safety release gate;
9. clinician oversight and immutable run record.

### 7.2 Specialist contract

Strict JSON: specialty, relevant observations, hypotheses (not diagnoses), supporting evidence IDs, contradicting evidence IDs, missing decisive data, triage vote, confidence calibrated to data/evidence, and safe next information/action class. Unsupported claims are rejected before adjudication.

### 7.3 Conflict and consensus

Consensus is computed over atomic claims and action/triage categories—not prose similarity. The output exposes:

- agreements with supporting specialists and evidence;
- disagreements with the exact disputed claim and decisive missing data;
- minority position retained verbatim as structured fields;
- emergency floor that no majority vote can lower;
- medication safety floor supplied by CareGuard/DrugBank;
- confidence bounded by data quality and evidence coverage.

### 7.4 Council APIs

- `POST /council/cases/{id}/runs` returns durable run ID;
- `GET /council/runs/{id}` and `/events`;
- `GET /council/runs/{id}/evidence`;
- `GET /council/runs/{id}/claims`;
- `GET /council/runs/{id}/conflicts`;
- `POST /council/runs/{id}/oversight`;
- `POST /council/runs/{id}/rerun` with explicit changed context/evidence version.

### 7.5 Release gates

- red-flag sensitivity and negation specificity by language slice;
- critical DDI floor preservation = 100%;
- unsupported critical claim release = 0;
- citation entailment and evidence authority thresholds;
- conflict recall on adjudicated test cases;
- calibrated confidence (ECE/Brier) and abstention utility;
- clinician usefulness, unsafe influence, and override reason review.

## 8. Medicine Manager and DDI specification

### 8.1 Identity before interaction

Each medicine item has raw label, normalized ingredient(s), brand, strength, form, route, identifiers (DrugBank/RxCUI/ATC where licensed/available), match candidates, match confidence, confirmation state, provenance, and dataset version. DDI analysis is blocked with `identity_unconfirmed` when multiple plausible ingredients remain.

### 8.2 DrugBank artifact contract

- licensed source remains outside Git;
- deployment artifact contains `manifest.json`, `ddi_index.sqlite`, and `drug_alias_index.sqlite` (or a combined indexed DB);
- manifest records checksum, license reference, generation tool commit, source effective date, counts, and schema version;
- startup verifies checksum, schema, version, pair count, and read-only query;
- readiness returns `ready|degraded|unavailable`, counts, version, and age—never secret paths or licensed content;
- rebuild is an offline release job from the XML/parsed shards, never a request-time action;
- previous validated dataset remains available for atomic rollback.

### 8.3 DDI result

Per pair: normalized ingredients, source=`drugbank`, dataset version, severity, evidence level when available, mechanism/description, management text, references when licensed, corroborating label evidence, patient-specific amplifiers, and release state. OpenFDA/FAERS never independently proves causality; it corroborates or adds a labeled signal.

An empty match is `no_interaction_found_in_checked_sources`, with checked source versions and normalization coverage. It is not “safe to combine”.

### 8.4 Medicine lifecycle

Inventory, expiry, duplicate ingredient detection, allergy/cross-sensitivity, DDI, disease/lab contraindication, pregnancy/lactation warning, adherence/reminder, refill estimate, and clinician/pharmacist review. CLARA never changes dose or stops a prescribed medicine autonomously.

## 9. CLARA Evidence Workbench and answer harness

### 9.1 Entry choices that stand apart

Instead of only “Ask anything”, the home/workspace offers protocol starters:

- Understand a symptom safely;
- Review my medicines;
- Prepare for an appointment;
- Compare treatment evidence;
- Understand a lab/result;
- Build a health timeline;
- Check a claim or article;
- Start clinician Council;
- Document an encounter with Scribe.

Each starter defines its required context, retrieval policy, artifact schema, risk policy, and evaluation slice.

### 9.2 Answer package

Every completed workbench run returns:

- direct brief with calibrated language;
- “what CLARA checked” stage manifest;
- decisive facts and their provenance;
- evidence ledger with freshness and authority;
- claim-to-evidence map;
- contradiction/uncertainty panel;
- missing information that could change the answer;
- personalized medicine safety panel when applicable;
- next safe actions split into now / soon / discuss with clinician;
- reusable artifact and follow-up plan;
- model/data/policy version disclosure.

### 9.3 Context compiler

The compiler uses only purpose-consented case data. It builds typed sections with token budgets and provenance, resolves conflicts by recency/source authority without deleting dissent, and never silently pulls an entire PHR into a request.

### 9.4 Retrieval and verification

- query decomposition by claim class;
- source registries and allowlists by protocol/risk/jurisdiction;
- hybrid retrieval, deduplication, freshness handling, authority scoring, and reranking;
- claim-first generation from an answer plan;
- entailment/contradiction checks against captured passages;
- deterministic checks for dosage, DDI, numerical/unit, emergency, and legal-policy claims;
- block/revise/abstain/escalate release controller;
- cited answer cannot be released when a critical claim lacks direct support.

### 9.5 Longitudinal loop

After an artifact, the user can save selected facts, schedule monitoring, attach a new result, compare versions, create an appointment brief, or request clinician review. CLARA highlights what changed since the prior run and which conclusions became stale.

## 10. Security and compliance

- explicit consent for recording and cross-border model/ASR processing;
- field-level purpose minimization and owner isolation;
- encrypted object storage and database encryption controls;
- configurable raw-audio retention with verified deletion;
- anti-malware/media parser isolation;
- prompt-injection isolation for uploaded/source content;
- SSRF-safe retrieval;
- no licensed DrugBank payload exposed beyond contractually allowed derived display;
- immutable audit for signing, overrides, exports, dataset changes, and provider changes;
- incident kill switches per provider/protocol without disabling emergency routing.

## 11. Deployment sequence

1. Correct DrugBank provenance/readiness and package reproducible licensed artifacts.
2. Replace fabricated legacy Scribe SOAP behavior; wire real model generation and grounding release gate.
3. Add durable Scribe audio/job/stage records and real ASR readiness.
4. Add shared case/evidence/claim/artifact schema and workflow runner.
5. Run Council independent model assessments in shadow mode beside the rule safety baseline.
6. Add evidence verification/adjudication and clinician evaluation; then canary Council model output.
7. Move Chat/Research protocols onto shared cases/artifacts while keeping existing transport compatibility.
8. Enable the Evidence Workbench UI, longitudinal comparisons, and follow-up actions.

No stage advances solely because code exists. It advances when migrations, provider readiness, real integration smoke, safety evaluation, rollback, and monitoring are complete.

## 12. Definition of done

- no production route contains demo/fixture response generation;
- real provider/dataset readiness is machine-readable;
- migrations upgrade and downgrade cleanly;
- jobs are resumable/idempotent and do not duplicate clinical artifacts;
- all critical outputs have claim verification and safety release decisions;
- signed notes and Council runs are immutable with append-only oversight;
- DrugBank source/version is correct on every DrugBank-derived interaction;
- full backend, ML, web, migration, contract, safety, and real-provider smoke suites pass;
- deploy has dataset/model/policy manifests, dashboards, alerts, and tested rollback.

## 13. Primary references

- WHO, *Ethics and governance of artificial intelligence for health*: https://www.who.int/publications/i/item/9789240029200
- WHO, *Ethics and governance of artificial intelligence for health: guidance on large multi-modal models*: https://www.who.int/publications/i/item/9789240084759
- FDA, *Clinical Decision Support Software*, final guidance (January 2026): https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
- NIST, *AI RMF Generative AI Profile*: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- DrugBank Clinical API documentation, DDI and references: https://docs.drugbank.com/v1/
- Google Cloud Speech-to-Text Chirp 3 model and diarization availability: https://cloud.google.com/speech-to-text/docs/models/chirp-3
- MedRAG/MIRAGE: https://arxiv.org/abs/2406.04044

## 14. Implemented production slice

The following parts of this specification are implemented in the accompanying
change set without mock or demo production responses:

- additive `clinical_*` case, immutable context, workflow/stage, evidence,
  claim, artifact, and review tables plus the `20260722_0019` migration;
- owner-scoped `/clinical-workbench` APIs with required idempotency keys and a
  real execution adapter for clinical answer/evidence brief, medication review,
  Council review, and Scribe note protocols;
- execution lifecycle persistence (`queued -> running -> completed|failed`),
  evidence/claim ledger capture, artifact creation, and clinician-only
  sign/override actions;
- model-backed Scribe note generation with strict template coercion and an
  extractive no-invention degraded path; production sessions no longer depend
  on the heuristic legacy SOAP generator;
- sign-time grounding and unresolved-candidate gate when grounding is enabled;
- real Google Speech-to-Text V2 Chirp-3 adapter using configured project/ADC,
  with the existing real Whisper adapter as fallback and no fabricated ASR;
- licensed DrugBank SQLite readiness/version/count reporting, correct
  `source=drugbank` provenance, source attribution, and authenticated readiness;
- independent model-backed Council specialty reviews in governed shadow mode,
  stable case-fact citations, schema validation, fact-ID filtering, explicit
  failures, and deterministic divergence/safety adjudication metadata;
- `clinical_answer`, `medication_review`, and `evidence_brief` request modes;
  structured triage, evidence ledger, whole-answer support verdict,
  uncertainty, missing context, next action, and provenance package;
- a modern Chat evidence-workbench panel that exposes the package instead of
  hiding it in an opaque model response.

Not represented as complete by this slice: durable object storage/chunk leases
for raw Scribe audio, true incremental Google streaming, external evidence
retrieval per Council specialty, learned-model clinical validation, automatic
longitudinal monitoring, and a deployed DrugBank alias index. Those advance
only after the release gates in sections 6, 7, 8, and 12 pass.
