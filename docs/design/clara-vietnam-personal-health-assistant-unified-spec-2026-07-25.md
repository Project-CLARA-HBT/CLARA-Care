# CLARA Viet Nam Personal Health Assistant

## Unified Product, UX, Clinical Safety and Technical Specification

Status: implementation-ready product specification  
Version: 1.1  
Date: 2026-07-25  
Primary market: Viet Nam  
Primary language: Vietnamese  
Companion decision report:
[Market Positioning Decision Report](../reports/clara-vietnam-market-positioning-decision-report-2026-07-25.md)

Implementation companions:

- [Wearable and Health Data Integration Technical Design](clara-wearable-health-integration-technical-design-2026-07-25.md)
- [Wearable and Health Data Implementation Task List](clara-wearable-health-integration-task-list-2026-07-25.md)

## 1. Product decision

CLARA is:

> **Trợ lý sức khỏe cá nhân và gia đình dành cho người Việt.**

It helps a person or family:

1. understand what changed;
2. understand what matters now;
3. choose a safe and feasible next step;
4. follow through until the outcome is known.

The user-facing category is a Personal and Family Health Assistant. The internal
operating model is a Personal Health Decision and Follow-through Network.

CLARA is not:

- a generic chatbot with a medical prompt;
- an autonomous doctor;
- an emergency service;
- a provider-owned patient portal;
- a universal health-score generator;
- a marketplace whose medical ranking is driven by commissions;
- a claim to contain every medical database;
- a simulated panel of real specialists.

## 2. Product outcomes

### 2.1 Consumer outcome

After using CLARA, a user should be able to say:

- I understand what this information means.
- I know what is important and what can wait.
- I know the next step and why it applies to me.
- I can share an accurate summary with my family or clinician.
- CLARA will help me remember and verify what happens next.

### 2.2 Clinical-safety outcome

CLARA must:

- identify emergency patterns before normal answer generation;
- avoid unsupported diagnosis or treatment;
- preserve uncertainty and missing context;
- distinguish personal facts, source facts, inference and recommendation;
- use DrugBank as the mandatory authority for DDI conclusions;
- escalate when safe personalization is not possible;
- never turn an affiliate or commercial signal into medical priority.

### 2.3 Business outcome

CLARA must create repeat value through resolved health work, not conversation
volume. It must be distributable through consumers, families, providers, labs,
employers, insurers and pharmacies without changing its clinical ranking policy.

## 3. Scope

### 3.1 In scope

- consumer and family onboarding;
- consented Huawei Health, Android Health Connect and Fitbit data connection;
- optional Wear OS companion capture when a watch-native use case is approved;
- health profile and consent;
- universal capture of text, images, PDFs, structured data and audio;
- Vietnamese medical-document extraction;
- longitudinal LifeMap;
- health episodes and follow-through;
- conversational Ask CLARA;
- medicines, reconciliation and DrugBank DDI;
- laboratory result interpretation and trends;
- pre-visit intake and Visit Pack;
- Scribe-assisted encounter capture;
- post-visit and post-discharge plan extraction;
- family/caregiver collaboration;
- local care-action discovery and handoff;
- CLARA Research for clinicians and researchers;
- structured Council review for complex cases;
- evidence, provenance and licensing governance;
- outcome collection and recommendation evaluation.

### 3.2 Out of scope for initial clinical release

- autonomous diagnosis;
- prescribing or changing a medicine;
- autonomous ordering of tests;
- replacing emergency dispatch;
- continuous remote patient monitoring represented as clinical surveillance;
- diagnostic interpretation of raw medical imaging;
- genetic risk interpretation;
- pediatric self-service without an authorized guardian;
- treatment-ranking based on commercial relationships;
- fully autonomous Council release;
- unlicensed reuse of restricted guideline or journal content.

### 3.3 No fake-data rule

Production functionality must not use mock, fabricated or synthetic clinical data
as if it were real.

- Demo data must be explicitly isolated and labeled.
- Production connectors must expose source and freshness.
- Missing external data must degrade honestly.
- Test fixtures are permitted only in automated tests and non-production demo
  tenants.
- No fallback may invent a provider, medicine, interaction, citation, result or
  completion event.

## 4. Users and modes

### 4.1 Consumer

Needs plain Vietnamese, low cognitive load, immediate meaning and one safe next
step.

Default information depth:

- short meaning;
- urgency;
- next step;
- key uncertainty;
- expandable evidence.

### 4.2 Caregiver

Needs attributed responsibility, profile boundaries, clear consent and simple
coordination.

The caregiver must always know:

- whose information is being viewed;
- what authority they have;
- what they may change;
- who will receive a notification;
- when access expires.

### 4.3 Clinician

Needs structured history, provenance, medication reconciliation, trends, red flags,
open questions and evidence—not consumer prose.

### 4.4 Researcher

Needs reproducible queries, PICO framing, study-design separation, evidence
matrices, identifiers, contradiction analysis and export.

### 4.5 System mode selection

Mode is explicit and account-scoped. The system may recommend a view, but it must
not infer professional status from vocabulary alone.

## 5. Product principles

### P-01 — Health is longitudinal

Every answer should use relevant confirmed history and clearly disclose which
history was used.

### P-02 — Ask less, understand more

Use documents and connectors before asking the user to re-enter information.
Request only context that can change urgency, safety or the next step.

### P-03 — Show change before detail

Default to meaningful deltas, unresolved work and the personal baseline. Do not
lead with a database dump.

### P-04 — Calm without false reassurance

Use direct, non-alarming language. Do not minimize red flags or manufacture
certainty to reduce anxiety.

### P-05 — One next step beats ten suggestions

Rank recommendations and release the smallest safe feasible action. Alternatives
remain expandable.

### P-06 — No action is a valid action

Observation, waiting for more information or abstention can be the correct output.

### P-07 — Every important recommendation expires

Recommendations require validity windows, invalidation conditions and
re-evaluation triggers.

### P-08 — Source authority is task-specific

A trial, guideline, drug database, regulatory label, patient record and wearable
signal are not interchangeable.

### P-09 — Family does not mean shared data

Household collaboration is grant-based, attributed and revocable.

### P-10 — Complexity must earn release

Multi-agent and advanced personalization are released only when they improve
task-specific outcomes over a simpler baseline.

## 6. Information architecture

### 6.1 Primary consumer navigation

Desktop:

1. **Hôm nay**
2. **Hỏi CLARA**
3. **Sức khỏe**
4. **Thuốc**
5. **Lịch & việc cần làm**

Persistent secondary access:

- Capture;
- family/profile switcher;
- notifications;
- account and privacy.

Mobile bottom navigation:

1. Hôm nay
2. Hỏi CLARA
3. Capture
4. Sức khỏe
5. Việc cần làm

Medicine is reachable from Hôm nay and Sức khỏe on mobile.

### 6.2 Professional navigation

Clinician/researcher workspaces add:

- Research;
- Cases;
- Scribe;
- Council;
- Evidence library.

Professional modules must not appear in consumer navigation by default.

### 6.3 Chat placement

Chat is not the default authenticated landing page. Successful login returns the
user to:

- the originally requested route; otherwise
- the last safe route; otherwise
- Hôm nay.

Chat uses the same LifeMap, Episode and Decision Ledger as every other surface.

## 7. Flagship experiences

### 7.1 Hôm nay

The home screen contains, in order:

1. **Có gì thay đổi?**
2. **Điều quan trọng lúc này**
3. **Bước tiếp theo**
4. **Gia đình cần bạn**
5. **Theo dõi gần đây**

It must not show an empty chat canvas as the main state.

Each card includes:

- person/profile;
- source and timestamp;
- importance;
- action or observation;
- expiry;
- dismiss/snooze;
- "Vì sao CLARA đề xuất?".

### 7.2 Getting started with Huawei Health and Google health ecosystems

The first-run experience must offer immediate value without forcing a chat or a
connector:

1. choose the person whose health will be supported;
2. choose one current goal, such as understanding results, managing medicines,
   tracking a concern or preparing for a visit;
3. optionally connect an available health source;
4. optionally capture a prescription, result or discharge document;
5. review what CLARA imported and what it can use;
6. land on Hôm nay with a useful, bounded first insight or an honest empty state.

Connector choices are capability-aware:

- **Health Connect** is the default Android aggregation path for compatible
  health and fitness apps;
- **Huawei Health** is offered when Huawei Health/HMS capability is available
  and CLARA has approved access to the required data types;
- **Fitbit** is a separate OAuth connector for Fitbit cloud history and for
  platforms where Health Connect is insufficient;
- **Wear OS Health Services** is not a history connector. It is used only by a
  CLARA watch module for approved real-time, passive or exercise experiences.

The product must never label these choices collectively as "Google Health" in a
way that hides which system, account and permissions are used.

Initial read-only data set:

- steps and activity;
- sleep sessions;
- heart rate and resting heart rate;
- weight and body measurements;
- blood pressure, blood glucose, oxygen saturation and temperature only where
  the platform, device, policy and intended use permit access.

Permissions are incremental and purpose-bound. CLARA asks only for the data
needed by the selected user-facing feature, explains the benefit before the
platform permission sheet, and allows:

- connect now;
- choose data types;
- continue without connecting;
- review last synchronization and source;
- pause synchronization;
- revoke access and delete imported data.

Imported wearable data is contextual signal, not a diagnosis. Before it can
affect a recommendation, CLARA must preserve the original source, device,
recording method, time zone, observed interval, synchronization time and
confidence/quality metadata. Material anomalies require corroboration or a safe
human follow-up path.

### 7.3 Universal Capture

Accepted inputs:

- camera/photo;
- PDF/document;
- pasted text;
- structured result;
- voice note;
- connected source.

Supported first-release artifact types:

- prescription;
- medicine package;
- laboratory result;
- visit note;
- discharge summary;
- referral;
- appointment instruction;
- self-observation.

Flow:

1. upload/capture;
2. malware and file validation;
3. OCR/ASR and document classification;
4. structured extraction;
5. identity and date resolution;
6. safety-critical reconciliation;
7. user confirmation only for uncertain/high-impact fields;
8. update LifeMap;
9. create or attach Episode;
10. show immediate meaning and next step.

### 7.4 Ask CLARA

The composer supports:

- free text;
- voice;
- image/document;
- "ask about this" from any object;
- profile selector;
- privacy/context indicator.

Every medical answer uses the following visible structure:

1. **Tóm tắt**
2. **Điều này có ý nghĩa gì với bạn**
3. **Bạn nên làm gì tiếp theo**
4. **Khi nào cần trợ giúp sớm**
5. **Điều CLARA chưa biết**
6. **Nguồn và cơ sở**

The response must show which personal facts were used and allow correction.

### 7.5 LifeMap

LifeMap is the confirmed longitudinal memory layer.

Views:

- summary;
- timeline;
- conditions and risks;
- results;
- medicines;
- visits;
- documents;
- goals and preferences;
- provenance and corrections.

LifeMap must never display an inferred diagnosis as a confirmed condition.

### 7.6 Health Episodes

An Episode is a bounded health concern or care obligation.

Examples:

- new prescription;
- abnormal laboratory result;
- respiratory symptoms;
- follow-up after discharge;
- medication side effect;
- vaccination;
- chronic-condition review.

Episode states:

```text
draft
  -> active
  -> awaiting_user
  -> awaiting_service
  -> observing
  -> resolved
  -> handed_off
  -> expired
  -> cancelled
```

Each Episode has:

- owner profile;
- concern and start time;
- authoritative inputs;
- facts and unknowns;
- urgency;
- recommendations;
- tasks and owners;
- expected outcome;
- escalation criteria;
- completion evidence;
- resolution summary.

### 7.7 Medicine Guardian

Capabilities:

- capture and normalize medicine identity;
- distinguish ingredient, strength, dosage form, brand and instructions;
- maintain start/stop status and reason;
- reconcile lists across prescription, user and record;
- track allergies and reported reactions;
- run pairwise and relevant multi-drug safety review;
- identify missing identity before DDI;
- support adherence context without punitive scoring;
- create a shareable medicine list.

DrugBank policy:

- DrugBank is mandatory for released DDI conclusions.
- Local rules, LLM inference, openFDA and labels cannot independently produce a
  "no interaction" or definitive interaction conclusion.
- If DrugBank is unavailable or either medicine is unresolved, the system returns
  `ddi_status=unknown` and never "safe".
- Every result includes DrugBank dataset version and resolved IDs.
- Regulatory labels may corroborate or add labeled warnings but remain separately
  sourced.

### 7.8 Results and Health Replay

For a result, CLARA must:

- identify analyte/test;
- preserve original value, unit, reference range, lab and timestamp;
- normalize only with a traceable conversion;
- compare with prior comparable results;
- separate population reference range from personal trend;
- identify critical values using source/lab rules where available;
- explain likely significance without diagnosing;
- recommend appropriate follow-up or abstain.

Health Replay shows:

- what changed;
- what interventions occurred;
- what happened afterward;
- which relationships are observations versus hypotheses.

Correlation must not be presented as causation.

### 7.9 CLARA Visit and Scribe

Before a visit:

- adaptive intake;
- episode timeline;
- medicine reconciliation;
- top concerns;
- user priorities;
- suggested questions;
- Visit Pack.

During a visit, with explicit consent:

- real audio capture;
- speaker-aware transcription;
- medical term normalization;
- structured note draft;
- action-item extraction.

After a visit:

- user/clinician review;
- medication changes;
- tests/referrals;
- warning signs;
- follow-up windows;
- Episode and tasks.

Scribe output is a draft until an authorized reviewer signs or confirms it.

### 7.10 Family Circle

Supported grants:

- view summary;
- view medicines;
- manage medicines;
- upload documents;
- manage appointments/tasks;
- receive urgent notifications;
- full guardian authority where legally appropriate.

Requirements:

- per-profile encryption context;
- explicit invitation and acceptance;
- profile switch indicator on every screen;
- attributed changes;
- access log visible to the subject/guardian;
- instant revocation;
- expiry and inactivity review;
- no hidden household inference.

### 7.11 Local Action Network

An action provider may be:

- hospital/clinic;
- physician service;
- laboratory;
- pharmacy;
- telehealth service;
- vaccination provider;
- emergency or public-health service;
- insurer/benefit channel.

Action records include:

- service identity and verification status;
- location and operating hours;
- capability;
- price or price status;
- insurance/eligibility;
- language/accessibility;
- booking mechanism;
- commercial relationship;
- last verification time;
- completion callback support.

Clinical ranking and commercial fulfillment are separate services.

### 7.12 CLARA Research

Research workflow:

1. question clarification;
2. PICO/PECO and scope compilation;
3. reproducible search strategy;
4. source-class-separated retrieval;
5. deduplication and retraction checks;
6. study-design classification;
7. extraction of population, intervention, comparator and outcomes;
8. risk-of-bias and applicability assessment;
9. contradiction map;
10. synthesis and evidence matrix;
11. provenance/export.

Required identifiers:

- PMID;
- DOI;
- NCT or registry ID;
- guideline organization/version;
- publication type and study design.

Guidelines, systematic reviews, primary trials and editorial/commentary must never
be silently blended into one evidence class.

### 7.13 CLARA Council

Council is a structured case-review workflow, not role-play.

Inputs:

- explicit clinical question;
- versioned case snapshot;
- medication safety artifact;
- evidence packet;
- missing-context list.

Independent review dimensions:

- clinical reasoning;
- medication safety;
- evidence/applicability;
- contradiction/alternative explanation;
- patient goals and feasibility;
- safety and escalation.

Output:

- agreements;
- material disagreements;
- missing decisive information;
- evidence per claim;
- uncertainty;
- recommended handoff.

Consumer release is limited to a plain-language summary unless a licensed
clinician reviews the full Council artifact.

## 8. Functional requirements

### 8.1 Identity and onboarding

- **FR-ID-001:** Users can create an account with verified email or phone.
- **FR-ID-002:** Authentication sessions persist securely across reloads and
  supported devices.
- **FR-ID-003:** Login returns to the requested or last safe route, not always
  Chat.
- **FR-ID-004:** Users choose consumer, caregiver or verified professional mode.
- **FR-ID-005:** The system creates one self profile and supports invited
  dependents.
- **FR-ID-006:** Emergency limitations, AI disclosure and privacy choices use
  plain Vietnamese.
- **FR-ID-007:** Dark/light/system theme applies to every authenticated route,
  including Chat and Research.
- **FR-ID-008:** Desktop navigation remains visible after login unless explicitly
  collapsed.

### 8.2 Context and truth

- **FR-CTX-001:** Every datum has source, observed time, ingestion time and truth
  state.
- **FR-CTX-002:** Truth states are `confirmed`, `source_asserted`,
  `user_reported`, `inferred`, `disputed`, `superseded` or `unknown`.
- **FR-CTX-003:** Inference cannot silently become confirmed.
- **FR-CTX-004:** Users can correct an item and see downstream affected outputs.
- **FR-CTX-005:** Context compilation is purpose-limited and logged.
- **FR-CTX-006:** Revoked connector data is excluded from new context immediately.

### 8.3 Capture

- **FR-CAP-001:** Capture supports image, PDF, text, audio and connector sources.
- **FR-CAP-002:** Each artifact exposes extraction confidence by field.
- **FR-CAP-003:** High-impact uncertain fields require confirmation.
- **FR-CAP-004:** Duplicate artifacts are detected without discarding provenance.
- **FR-CAP-005:** Unsupported artifacts degrade with a reason and retain the
  original if the user permits.
- **FR-CAP-006:** Capture returns a useful first result within the performance
  class or an asynchronous status.

### 8.4 Connected health and wearable data

- **FR-CON-001:** The app detects Health Connect, Huawei Health/HMS and supported
  watch capabilities before presenting a connector.
- **FR-CON-002:** Connecting a source is optional and cannot block account
  creation or access to manual/document workflows.
- **FR-CON-003:** The consent screen names the provider, data types, purpose,
  read/write direction, retention and revocation path.
- **FR-CON-004:** Initial integrations are read-only unless a separately approved
  feature requires write access.
- **FR-CON-005:** Each imported record preserves provider, upstream record ID,
  data origin, device, recording method, observed time/interval, time-zone offset,
  ingestion time and connector version where available.
- **FR-CON-006:** Synchronization is incremental, idempotent and safe to retry.
- **FR-CON-007:** Deduplication never merges non-equivalent records and preserves
  all contributing provenance.
- **FR-CON-008:** Aggregate metrics such as steps avoid double counting across
  origins and expose the selected-origin policy.
- **FR-CON-009:** Revocation stops new reads immediately; the user can separately
  delete previously imported records according to the disclosed retention policy.
- **FR-CON-010:** Missing permissions, stale sync, unsupported devices and vendor
  outages are visible and cannot be interpreted as normal health.
- **FR-CON-011:** Wearable observations cannot independently create a diagnosis,
  change a prescription or close an Episode.
- **FR-CON-012:** Connector data used by an answer or recommendation is listed in
  the Decision Ledger with freshness and purpose.
- **FR-CON-013:** Health Connect access complies with the current Play Console
  Health apps declaration and requests the minimum approved data types.
- **FR-CON-014:** Huawei data types requiring enterprise status or vendor approval
  remain disabled until access is contractually and technically confirmed.
- **FR-CON-015:** Fitbit uses Authorization Code with PKCE or the vendor-approved
  user authorization flow; client credentials never authorize access to a
  consumer's personal Fitbit data.
- **FR-CON-016:** Wear OS sensor collection is released only for a defined
  watch-native feature with battery, permission, accuracy and safety acceptance
  criteria.

### 8.5 Answers and recommendations

- **FR-ANS-001:** Emergency triage executes before the normal LLM pipeline.
- **FR-ANS-002:** Every released medical claim maps to a personal fact, source or
  explicitly labeled inference.
- **FR-ANS-003:** Recommendations include rationale, evidence basis, target,
  validity window and invalidation criteria.
- **FR-ANS-004:** The renderer adapts depth without changing the underlying
  conclusion.
- **FR-ANS-005:** Missing decisive context appears explicitly.
- **FR-ANS-006:** The system can abstain and provide a safe information-gathering
  or human-handoff step.
- **FR-ANS-007:** The user can ask why, inspect sources and correct context.

### 8.6 Episodes and actions

- **FR-EPI-001:** Important recommendations create or attach to an Episode.
- **FR-EPI-002:** Every action has owner, due/expected window and status.
- **FR-EPI-003:** A reminder is not completion.
- **FR-EPI-004:** Completion can be user-reported, partner-confirmed,
  clinician-confirmed, inferred-awaiting-confirmation or unknown.
- **FR-EPI-005:** Expired recommendations are not presented as current.
- **FR-EPI-006:** Safety-net criteria remain available while an Episode is active.
- **FR-EPI-007:** Resolution records the outcome and unresolved uncertainty.

### 8.7 Medicines

- **FR-MED-001:** Medicine identity must resolve before a definitive DDI check.
- **FR-MED-002:** Released DDI conclusions require DrugBank.
- **FR-MED-003:** An unavailable or stale mandatory source produces unknown, not
  safe.
- **FR-MED-004:** DrugBank version and IDs are auditable.
- **FR-MED-005:** Medication changes require attribution and effective time.
- **FR-MED-006:** Users can export a current medicine and allergy list.
- **FR-MED-007:** The system never instructs the user to start, stop or alter a
  prescription without an authorized clinician.

### 8.8 Family

- **FR-FAM-001:** Access is grant-based by profile and capability.
- **FR-FAM-002:** Every read/write is attributed and auditable.
- **FR-FAM-003:** Revocation takes effect immediately for new access.
- **FR-FAM-004:** Notifications respect profile-specific grants.
- **FR-FAM-005:** Switching profile is obvious and protected against accidental
  writes.

### 8.9 Research and Council

- **FR-RES-001:** Research preserves the reproducible query.
- **FR-RES-002:** Evidence classes remain separated.
- **FR-RES-003:** Retractions and corrections are checked before release.
- **FR-RES-004:** Claims preserve identifiers and study design.
- **FR-RES-005:** Applicability to the target population is explicit.
- **FR-CNL-001:** Council reviewers use the same versioned case snapshot.
- **FR-CNL-002:** Independent outputs are generated before synthesis.
- **FR-CNL-003:** Material disagreements cannot be hidden by consensus wording.
- **FR-CNL-004:** Council stays shadow-only until it beats the baseline.

## 9. Domain model

### 9.1 Core entities

```text
User
Profile
CareGrant
ConsentGrant
SourceConnection
ConnectorAuthorization
ConnectorSyncCursor
SourceArtifact
ClinicalFact
LifeMapEntry
HealthEpisode
EpisodeObservation
Recommendation
CareAction
ActionOutcome
MedicationCourse
MedicationIdentity
DrugInteractionAssessment
LabObservation
WearableObservation
WearableAggregate
Encounter
Transcript
VisitPack
EvidenceRecord
EvidenceClaim
ResearchRun
CouncilRun
DecisionLedgerEntry
ProviderService
CommercialRelationship
```

### 9.2 Provenance

Every derived object must reference:

- input artifact IDs;
- source version;
- extraction/model version;
- prompt/policy version where applicable;
- creator;
- timestamps;
- review state;
- supersession chain.

### 9.3 Recommendation contract

```json
{
  "id": "rec_...",
  "profile_id": "prof_...",
  "episode_id": "epi_...",
  "kind": "observe|self_care|contact_clinician|urgent_care|service_handoff",
  "summary": "string",
  "why_now": ["fact_or_claim_id"],
  "evidence_claim_ids": ["claim_..."],
  "assumptions": ["string"],
  "unknowns": ["string"],
  "alternatives": ["string"],
  "valid_from": "timestamp",
  "valid_until": "timestamp",
  "invalidate_when": ["condition"],
  "release_state": "draft|released|abstained|blocked|superseded",
  "review": {
    "type": "policy|clinical|user",
    "actor_id": "optional"
  }
}
```

### 9.4 Decision Ledger

The append-only Decision Ledger records:

- input snapshot;
- relevant context;
- routing decision;
- sources requested/used/unavailable;
- candidate recommendations;
- safety findings;
- contradictions;
- final release/abstention;
- user-visible output;
- later correction/outcome.

It supports audit, replay and evaluation without exposing hidden chain-of-thought.

## 10. AI and medical-answer harness

### 10.1 Pipeline

```text
Input
  -> identity/profile authorization
  -> emergency and crisis bypass
  -> artifact/intent classifier
  -> medical entity resolution
  -> purpose-limited context compiler
  -> question and task compiler
  -> authority/source router
  -> parallel retrieval and deterministic safety tools
  -> evidence normalization and contradiction graph
  -> candidate answer/recommendation generation
  -> independent safety, factuality, DDI and applicability checks
  -> release adjudicator
  -> audience renderer
  -> Episode/action update
  -> outcome collection and evaluation
```

### 10.2 Emergency bypass

The emergency path:

- uses a dedicated low-latency classifier plus deterministic critical patterns;
- does not wait for deep retrieval;
- produces immediate local emergency guidance;
- asks only questions that change immediate action;
- can continue optional context collection after the urgent instruction;
- logs false positives/negatives for clinical review.

Emergency guidance must use current Vietnamese emergency contacts and policy
content maintained as versioned configuration.

### 10.3 Context compiler

Inputs are selected by:

- profile authorization;
- user request;
- episode;
- recency;
- clinical relevance;
- truth state;
- source authority;
- purpose consent.

The compiled context contains:

- confirmed snapshot;
- disputed/unknown facts;
- medication and allergy safety floor;
- relevant trend deltas;
- user goals, constraints and preferences;
- recent care actions;
- provenance references.

It must never pass an entire record merely because it fits the context window.

### 10.4 Source router

Task-specific authority:

| Task | Mandatory/preferred authority |
|---|---|
| DDI conclusion | DrugBank |
| current medicine identity | resolved source + RxNorm/local mapping where applicable |
| labeled warning | official regulator label |
| guideline recommendation | current relevant guideline, localized to Viet Nam |
| research effectiveness | systematic review plus primary trials |
| current trial status | trial registry |
| personal result | original lab/provider artifact |
| personal medicine instruction | current prescription/authorized clinician |
| local service availability | verified partner/local action registry |

### 10.5 Evidence graph

Nodes:

- question;
- claim;
- source;
- population;
- intervention/exposure;
- comparator;
- outcome;
- recommendation;
- contradiction;
- applicability constraint.

Edges preserve:

- supports;
- contradicts;
- qualifies;
- updates;
- retracts;
- applies_to;
- derived_from.

The generator receives structured evidence objects, not an undifferentiated text
bundle.

### 10.6 Recommendation engine

Candidate generation considers:

- clinical appropriateness;
- urgency;
- evidence strength;
- personal applicability;
- contraindications;
- user goal;
- burden;
- access and cost;
- availability;
- prior failed/declined actions;
- notification receptivity.

Ranking order:

1. prevent serious harm;
2. satisfy authoritative care obligation;
3. obtain decisive missing information;
4. choose the smallest feasible beneficial action;
5. minimize burden and cost;
6. respect preference.

Commercial value is excluded from clinical ranking.

### 10.7 Safety critics

Independent checks:

- emergency/under-triage;
- medication identity and DrugBank DDI;
- unsupported claim;
- source mismatch;
- temporal staleness;
- contradiction omission;
- applicability gap;
- overdiagnosis/overtesting;
- unauthorized treatment;
- privacy/context leak;
- commercial conflict;
- audience misrendering.

Critical critics can block release. Noncritical findings can trigger revision or
visible uncertainty.

### 10.8 Multi-agent policy

Multi-agent execution is permitted for:

- independent evidence retrieval;
- contradiction analysis;
- complex medication review;
- professional Research;
- Council;
- adversarial safety review.

It is not required for simple tasks.

Release rule:

```text
multi_agent_enabled(task) =
  quality_gain_over_baseline >= approved_threshold
  AND critical_safety_not_worse
  AND latency_within_budget
  AND cost_within_budget
```

Otherwise it runs in shadow or is disabled.

### 10.9 Dynamic prompt engineering

Prompts are compiled from versioned components:

- intended use;
- task schema;
- audience;
- context manifest;
- authority policy;
- safety policy;
- output schema;
- locale;
- evidence packet.

No production prompt is assembled from uncontrolled user text as executable
instruction. Prompt and policy versions are recorded in the Decision Ledger.

### 10.10 Model routing

Use the lowest-cost model meeting the evaluated task threshold:

- deterministic code for identity, permissions, unit conversion and state
  transitions;
- small/fast models for classification and extraction where validated;
- strong single agent for normal synthesis;
- frontier reasoning for high-complexity evidence tasks;
- multi-agent only under the release rule.

Model fallback cannot remove mandatory safety tools or sources.

## 11. Knowledge Fabric

### 11.1 Source Registry

Fields:

- source ID and organization;
- domain and evidence class;
- access mechanism;
- license and permitted uses;
- display/quotation constraints;
- geographic applicability;
- update cadence and last successful refresh;
- source version;
- authority tier;
- known limitations;
- connector health.

### 11.2 Rights Ledger

Every stored text/chunk/object records:

- source license;
- acquisition method;
- allowed purposes;
- retention;
- redistribution/display policy;
- model-training permission;
- expiration/termination;
- legal review state.

Restricted content must not enter generic embeddings or model training merely
because a user can view it.

### 11.3 Initial source tiers

Tier 1:

- Vietnamese Ministry of Health and authorized national sources;
- original personal records;
- DrugBank for DDI;
- official regulatory labels;
- WHO guidelines;
- current relevant local guidelines.

Tier 2:

- systematic reviews;
- PubMed/Europe PMC indexed primary research;
- ClinicalTrials.gov and WHO ICTRP;
- licensed NICE/Cochrane content when available.

Tier 3:

- professional society guidance;
- high-quality secondary references.

Excluded as medical authority:

- search-result snippets;
- unattributed blogs;
- social-media claims;
- model memory alone;
- local regex rules as DDI conclusions.

## 12. Service architecture

### 12.1 Logical services

```text
Web/Mobile Clients
  -> Edge/API Gateway
  -> Identity & Consent Service
  -> Profile/Family Service
  -> Capture Service
  -> Connected Health Ingestion Service
  -> LifeMap Service
  -> Episode & Action Service
  -> Medicine Service
  -> Encounter/Scribe Service
  -> Research & Evidence Service
  -> Council Orchestrator
  -> Recommendation Orchestrator
  -> Local Action Network
  -> Notification Service
  -> Audit/Decision Ledger
```

Shared infrastructure:

- PostgreSQL for transactional records;
- object storage for encrypted artifacts;
- search index for authorized retrieval;
- vector index only for rights-cleared content;
- event bus/outbox;
- worker queues isolated by workload;
- model gateway;
- observability and evaluation store.

### 12.2 Tenant and profile isolation

- tenant and profile IDs are required on every protected object;
- row-level and application-level authorization;
- artifact encryption keys scoped appropriately;
- background jobs re-check authorization and consent;
- cache keys include tenant/profile/purpose;
- no cross-profile semantic retrieval.

### 12.3 API conventions

- `/v1/` versioned endpoints;
- OAuth2/OIDC sessions;
- idempotency key for mutations;
- cursor pagination;
- ETag/version for concurrency;
- consistent error envelope;
- request/correlation IDs;
- explicit asynchronous job resource.

### 12.4 Core APIs

```text
POST   /v1/captures
GET    /v1/captures/{id}
POST   /v1/captures/{id}/confirm

GET    /v1/connectors/capabilities
GET    /v1/connectors
POST   /v1/connectors/health-connect/imports
POST   /v1/connectors/huawei/imports
POST   /v1/connectors/fitbit/authorizations
GET    /v1/connectors/fitbit/callback
POST   /v1/connectors/{id}/sync
POST   /v1/connectors/{id}/pause
DELETE /v1/connectors/{id}
DELETE /v1/connectors/{id}/imported-data

GET    /v1/today
GET    /v1/profiles/{id}/lifemap
POST   /v1/profiles/{id}/corrections

POST   /v1/answers
GET    /v1/answers/{id}
POST   /v1/answers/{id}/feedback

POST   /v1/episodes
GET    /v1/episodes/{id}
POST   /v1/episodes/{id}/actions
POST   /v1/actions/{id}/outcomes

GET    /v1/medications
POST   /v1/medications/reconcile
POST   /v1/medications/ddi-assessments

POST   /v1/visits/intakes
POST   /v1/encounters
POST   /v1/encounters/{id}/audio
POST   /v1/encounters/{id}/finalize

POST   /v1/research/runs
GET    /v1/research/runs/{id}
POST   /v1/council/runs

POST   /v1/family/grants
DELETE /v1/family/grants/{id}
GET    /v1/access-log

GET    /v1/services/search
POST   /v1/service-handoffs
```

### 12.5 Domain events

```text
capture.received
capture.extracted
capture.confirmed
connector.authorization_granted
connector.authorization_revoked
connector.sync_started
connector.sync_completed
connector.sync_partial
connector.sync_failed
connector.data_deleted
wearable.observation_imported
wearable.aggregate_recomputed
lifemap.updated
episode.created
episode.state_changed
recommendation.released
recommendation.abstained
action.created
action.completed
action.expired
outcome.recorded
medicine.identity_resolved
drugbank.assessment_completed
drugbank.assessment_unavailable
emergency_path_triggered
encounter.transcribed
visit_pack.generated
research.completed
council.disagreement_detected
consent.revoked
source.stale
```

Events contain IDs and minimum metadata, not unnecessary sensitive payloads.

## 13. Reliability and degradation

### 13.1 Mandatory-source degradation

| Failure | Behavior |
|---|---|
| DrugBank unavailable | DDI unknown; block definitive conclusion |
| evidence retrieval unavailable | answer only stable low-risk information or abstain |
| personal connector unavailable | disclose missing context and freshness |
| connector permission revoked | stop reads; mark connection revoked; do not delete prior data without the user's separate instruction |
| synchronization cursor invalid | bounded reconciliation sync; never silently replace the full history |
| duplicate wearable origins | apply origin policy; preserve provenance; disclose aggregate source |
| device clock/time zone ambiguous | quarantine affected interval from trend and ask for correction when material |
| OCR confidence low | request confirmation; do not update critical facts |
| model timeout | return safe status/fallback, preserve job |
| local service stale | show unverified status; do not promise availability |
| notification failure | retry and surface status; never mark action complete |

### 13.2 SLOs

- authentication/session availability: 99.95%;
- critical safety path availability: 99.95%;
- read APIs: 99.9%;
- normal answer orchestration: 99.5%;
- RPO for transactional data: 5 minutes;
- RTO: 60 minutes;
- emergency first response p95: under 2 seconds;
- Today p95: under 1.5 seconds;
- normal first answer status p95: under 3 seconds;
- deep Research may be asynchronous with visible progress.

## 14. Privacy, security and trust

### 14.1 Consent

Consent is:

- purpose-specific;
- source-specific;
- profile-specific;
- revocable;
- versioned;
- understandable in Vietnamese.

### 14.2 User controls

Users can:

- view and correct LifeMap;
- see why context was used;
- disconnect a source;
- export data;
- delete data subject to lawful retention;
- manage health memory separately from ordinary chat;
- review family access;
- view significant access and recommendation decisions.

### 14.3 Security requirements

- encryption in transit and at rest;
- managed secrets and rotation;
- MFA for professional/high-risk access;
- least privilege;
- signed upload URLs and malware scanning;
- immutable audit records;
- rate limiting and abuse detection;
- secure prompt/tool boundaries;
- dependency and container scanning;
- incident response and breach workflow;
- regular penetration testing;
- backup restoration tests.

### 14.4 Prompt-injection controls

Captured documents and retrieved content are data, never instructions.

- tool permissions are server-side;
- retrieved text cannot expand tool access;
- URLs and actions use allowlisted schemes/domains where applicable;
- sensitive external actions require explicit confirmation;
- model output cannot directly mutate clinical state without schema and policy
  validation.

## 15. Regulatory and clinical governance

### 15.1 Intended-use registry

Every workflow records:

- intended user;
- intended purpose;
- supported population;
- clinical claim;
- decision consequence;
- human oversight;
- source requirements;
- known limitations;
- AI Law risk classification;
- medical-device assessment;
- evidence and validation;
- approved markets.

### 15.2 Release classes

| Class | Example | Release requirement |
|---|---|---|
| Informational | explain a medical term | policy and factual evaluation |
| Personalized informational | explain result using confirmed history | context, safety and applicability evaluation |
| Navigation | suggest appropriate care type | triage validation and local-service governance |
| Monitoring/recommendation | detect change and recommend follow-up | intended-use and medical-device review |
| Clinical decision support | professional recommendation | clinical governance and applicable regulation |

### 15.3 Clinical governance body

Required responsibilities:

- approve intended use;
- maintain safety policies;
- adjudicate incidents and disagreements;
- approve evaluation sets;
- review source authority;
- monitor subgroup performance;
- authorize rollout expansion;
- trigger recall/suspension.

### 15.4 Post-market monitoring

Track:

- under/over-triage;
- medication safety errors;
- unsupported claims;
- harmful delay;
- privacy incidents;
- subgroup disparity;
- clinician corrections;
- recommendation non-completion;
- user-reported harm or confusion;
- source staleness.

Serious incidents trigger immediate containment and applicable reporting.

## 16. UX and design system requirements

### 16.1 Visual direction

- calm, modern and consumer—not hospital software;
- light mode is the primary design quality baseline;
- dark mode is fully designed, not color-inverted;
- warm neutral surfaces with restrained health-status colors;
- no excessive gradients, glass panels or dashboard clutter;
- generous spacing and readable Vietnamese typography;
- clear focus, hover, pressed, loading, empty, error and disabled states.

### 16.2 Status colors

- red only for urgent/critical action;
- amber for timely attention;
- blue for information/action;
- green for confirmed completion, not general "safe";
- neutral gray for unknown/unverified.

Color is never the only status signal.

### 16.3 Accessibility

- WCAG 2.2 AA;
- keyboard-complete desktop flows;
- 44px minimum touch target;
- screen-reader labels and live regions;
- reduced motion;
- scalable text;
- plain-language alternatives;
- charts accompanied by text summaries.

### 16.4 Loading and errors

Long processes show stages:

- Đang đọc tài liệu;
- Đang đối chiếu thông tin;
- Đang kiểm tra an toàn;
- Đang tổng hợp bước tiếp theo.

Errors state:

- what failed;
- what was preserved;
- whether safety checking completed;
- what the user can do;
- retry/support path.

"Lỗi hệ thống nội bộ" alone is prohibited.

## 17. Measurement

### 17.1 North-star

**Safe Confirmed Episode Advancement Rate**

```text
episodes reaching a confirmed safe next state within expected window
/
eligible meaningful episodes
```

### 17.2 Consumer value

- next-step comprehension;
- meaningful-change comprehension;
- successful artifact capture;
- time to first useful result;
- repeated-history reduction;
- follow-up completion;
- family task completion;
- Visit Pack usefulness;
- calm/trust score without false reassurance.

### 17.3 Safety

- emergency sensitivity and specificity;
- harmful-answer rate;
- unsupported-claim rate;
- false DDI reassurance rate;
- medication identity resolution accuracy;
- stale recommendation exposure;
- critical context omission;
- privacy boundary violations;
- clinician override/correction.

### 17.4 Model and harness

- claim precision/recall;
- evidence entailment;
- citation correctness;
- source-class compliance;
- contradiction recall;
- calibrated abstention;
- applicability;
- single-agent versus multi-agent delta;
- latency and cost per successful Episode advancement.

### 17.5 Business

- activated households;
- active profiles per household;
- acquisition cost by channel;
- sponsor renewal;
- active-user cost;
- partner handoff completion;
- paid conversion;
- outcome-linked revenue.

## 18. Evaluation program

### 18.1 Offline suites

Required Vietnamese suites:

- emergency and crisis;
- common symptom and uncertainty;
- pregnancy/pediatric guardian safety;
- prescription OCR and identity;
- DrugBank DDI;
- lab units and trends;
- discharge follow-up;
- health misinformation;
- traditional/herbal medicine interactions;
- family privacy;
- adversarial prompt injection;
- evidence retrieval and contradiction.

### 18.2 Baselines

Compare:

- frontier general model with strong medical prompt;
- same model plus raw retrieval;
- CLARA single-agent harness;
- CLARA multi-agent harness;
- deterministic/structured workflow where applicable.

### 18.3 Real end-to-end evaluation

Use real, consented or properly de-identified artifacts and realistic service
integrations.

Evaluate:

- input capture;
- extracted facts;
- answer;
- recommendation;
- action creation;
- handoff;
- outcome;
- updated context.

A high answer score without a correct downstream state is not an E2E pass.

### 18.4 Prospective pilots

Pilot three verticals:

1. new/changed prescription;
2. abnormal laboratory result;
3. post-visit/discharge follow-up.

Require clinical oversight, incident monitoring and predeclared stop rules.

## 19. Delivery phases

### Phase 0 — Regulatory and trust foundation

Deliver:

- intended-use registry;
- profile/consent/grant model;
- truth and provenance model;
- Decision Ledger;
- source registry and rights ledger;
- emergency path;
- design-system/auth/navigation correction;
- production/no-fake-data controls.

Exit:

- login/session/navigation/theme E2E pass;
- consent revocation tests pass;
- emergency evaluation meets approved threshold;
- all initial workflows classified.

### Phase 1 — Personal Assistant shell and artifact-to-action MVP

Deliver:

- Hôm nay;
- Ask CLARA;
- Universal Capture;
- optional Getting Started connection to Health Connect or Huawei Health;
- Fitbit authorization and historical synchronization when direct cloud access is
  required;
- connector review, pause, revocation and imported-data deletion controls;
- LifeMap core;
- Episode core;
- Vietnamese prescription, lab and discharge capture;
- first answer/recommendation harness;
- explicit outcome tracking.

Exit:

- three beachhead flows operate end to end;
- at least Health Connect and Huawei Health pass device-based E2E with real
  consenting test accounts; Fitbit may remain feature-flagged until vendor review
  is approved;
- no connector permission is broader than its visible user benefit;
- duplicate-origin and time-zone fixtures pass without double counting;
- no mock production dependency;
- comprehension and extraction thresholds met;
- mandatory abstention works.

### Phase 2 — Medicine Guardian

Deliver:

- medication identity/reconciliation;
- licensed DrugBank production store;
- DDI API and UI;
- medicine course lifecycle;
- allergy/reaction capture;
- shareable medicine list;
- medication Episode.

Exit:

- full DrugBank readiness confirmed;
- no local-rule DDI conclusion;
- unresolved/unavailable cases never show safe;
- medicine E2E and safety suite pass.

### Phase 3 — Visits, Scribe and follow-through

Deliver:

- adaptive intake;
- Visit Pack;
- consented real-audio Scribe;
- structured note draft;
- medication/test/referral extraction;
- post-visit action and outcome loop.

Exit:

- real audio to reviewed note works;
- clinician usability threshold met;
- actions are not marked complete by generation;
- privacy and retention controls pass.

### Phase 4 — Family Circle

Deliver:

- invitations and grants;
- profile switcher;
- caregiver tasks;
- attributed notifications;
- access log and revocation;
- guardian policies.

Exit:

- cross-profile isolation tests pass;
- no notification leakage;
- caregiver comprehension threshold met.

### Phase 5 — Local Action Network

Deliver:

- verified service registry;
- provider/lab/pharmacy integrations;
- price/eligibility status;
- clinical ranking separated from fulfillment;
- handoff and completion callback;
- partner operational dashboard.

Exit:

- at least two real partner types;
- stale availability degrades safely;
- conflict audit passes;
- callback-confirmed outcomes work.

### Phase 6 — Research and evidence maturation

Deliver:

- reproducible Research workflow;
- evidence matrix;
- retraction and contradiction checks;
- rights-cleared source expansion;
- living evidence updates;
- professional export.

Exit:

- research benchmark beats general deep-research baseline on approved rubric;
- source licensing audit passes;
- evidence identifiers and classes are complete.

### Phase 7 — Council and validated personalization

Deliver:

- structured Council;
- independent reviewers;
- disagreement map;
- recommendation personalization using outcomes;
- JITAI-style timing with burden controls;
- shadow evaluation.

Exit:

- Council and multi-agent paths outperform baseline;
- subgroup safety is non-inferior;
- personalization demonstrates prospective value;
- clinical governance approves release.

## 20. Migration from current CLARA

### 20.1 Reuse

- authentication and API foundations after session/navigation verification;
- Chat transport and conversation storage;
- Research connectors and evidence schemas;
- DrugBank parsed artifact and ingestion pipeline;
- Scribe pipeline where real audio is supported;
- Council orchestration components after structured-dissent review;
- existing FHIR export and clinical schemas;
- observability and deployment infrastructure.

### 20.2 Replace or refactor

- chat-first authenticated landing;
- feature navigation that disappears after login;
- incomplete dark-mode surfaces;
- local-rule DDI authority;
- unstructured multi-agent role play;
- fake/demo data in production paths;
- generic internal error messages;
- recommendations without Episode/outcome state;
- citations not bound to claims;
- context assembled from uncontrolled conversation history.

### 20.3 Compatibility

- old Chat routes redirect without losing conversation IDs;
- existing records migrate with provenance;
- uncertain legacy facts become `source_asserted` or `unknown`, never confirmed by
  migration;
- old medicine records require identity reconciliation before new DDI conclusions;
- feature flags support progressive rollout and rollback.

## 21. Feature flags and rollback

Required flags:

```text
clara_today_enabled
clara_capture_enabled
clara_episode_enabled
clara_recommendations_enabled
clara_drugbank_required
clara_family_enabled
clara_action_network_enabled
clara_scribe_enabled
clara_research_v2_enabled
clara_council_shadow
clara_council_release
clara_multi_agent_shadow
clara_multi_agent_release
```

Rollback must preserve user data and ongoing safety obligations. Disabling a
feature cannot delete an active Episode or remove emergency guidance.

## 22. Definition of done

The program is complete only when:

- CLARA is visibly a Personal and Family Health Assistant, not a chat page;
- login, persistence, navbar/sidebar, light/dark mode and routing pass production
  E2E;
- real consumer artifact flows work without fake production data;
- LifeMap preserves provenance and correction;
- the three-question experience is consistent across surfaces;
- recommendations are bounded, explainable, expiring and outcome-linked;
- emergency bypass is fast and validated;
- DrugBank is mandatory and operational for DDI conclusions;
- medicines, results, Visit/Scribe and Family work end to end;
- Research separates evidence classes and preserves identifiers;
- Council exposes disagreement and remains gated by baseline comparison;
- local services are verified and commercial conflicts are disclosed;
- privacy, consent and family isolation pass security testing;
- regulatory intended use exists for every released workflow;
- offline, adversarial and real E2E evaluation reports are approved;
- monitoring, incident response, rollback and source-staleness alerts are live;
- no known critical safety, authentication, navigation or data-isolation defect
  remains open.

## 23. Final product copy

Primary:

> **CLARA — Trợ lý sức khỏe cá nhân và gia đình dành cho người Việt**

Supporting:

> CLARA giúp bạn hiểu sức khỏe theo thời gian, nhận ra điều quan trọng, chọn bước
> tiếp theo phù hợp và theo sát cho đến khi bạn biết kết quả.

Three-question language:

- **Có gì thay đổi?**
- **Điều gì quan trọng lúc này?**
- **Bước tiếp theo phù hợp nhất là gì?**

Trust language:

> CLARA cho bạn biết thông tin nào đến từ hồ sơ, thông tin nào từ bằng chứng y
> khoa, điều gì còn chưa chắc chắn và khi nào cần gặp người có chuyên môn.
