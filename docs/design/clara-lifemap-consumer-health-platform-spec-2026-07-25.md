# CLARA LifeMap — Consumer Health Platform Specification

Status: product and technical direction  
Date: 2026-07-25  
Audience: Product, Design, Clinical Safety, ML, API, Web, Mobile, Security, Data, SRE  
Supersedes: Chat-first product orientation  
Reuses: Medical Answer Harness, DrugBank CareGuard, Scribe, Research, authentication,
consent, evidence verification, and emergency routing

## 1. Executive decision

CLARA will no longer be designed primarily as a medical chatbot.

The primary product is **CLARA LifeMap**, a continuously updated, user-controlled
map of a person's health. The primary unit of work is a **Health Episode** with a
beginning, changing state, planned next steps, follow-up checkpoints, and an explicit
resolution or safe handoff. Chat remains available as a natural input and explanation
surface, but it is not the information architecture, system of record, or principal
value proposition.

The product promise is:

> CLARA remembers your health, notices meaningful changes, and helps you complete
> the next safe step.

Vietnamese product promise:

> CLARA ghi nhớ, giải thích và theo dõi sức khỏe của bạn xuyên suốt.

CLARA must be useful without requiring the user to know what prompt to write, what
medical terminology to use, or which product feature to open.

## 2. Why this direction is defensible

A well-prompted general LLM can summarize medical information, produce citations,
simulate several specialist roles, and ask follow-up questions. Those capabilities
are necessary but not a durable consumer product advantage.

CLARA's durable advantage must come from capabilities a single answer cannot
provide:

1. A consented, structured and longitudinal personal health state.
2. Separation of confirmed facts, reported observations, imported records, and
   model inferences.
3. Detection of changes relative to the user's own baseline.
4. Durable Health Episodes that remain open across days, visits, and new evidence.
5. Executable medication, safety, measurement, and follow-up workflows.
6. Closed-loop observation of whether the planned next step occurred and what
   happened afterward.
7. Reproducible explanations of why CLARA surfaced an item at a particular time.
8. Family and caregiver coordination with explicit, granular permissions.

Longitudinal clinical reasoning is not solved by simply adding more history to a
prompt. TIMER reports that time-aware instruction modeling improves completeness
and temporal reasoning over multi-visit records, supporting the need for a dedicated
temporal representation:

- [TIMER, npj Digital Medicine, 2025](https://www.nature.com/articles/s41746-025-01965-9)

FHIR provides standard representations for observations, medications, care plans,
tasks, knowledge artifacts, and auditable decision-support responses:

- [FHIR Clinical Reasoning and CDS](https://www.hl7.org/fhir/clinicalreasoning-cds-on-fhir.html)
- [FHIR PlanDefinition](https://hl7.org/fhir/plandefinition.html)
- [FHIR GuidanceResponse](https://fhir.hl7.org/fhir/guidanceresponse.html)
- [CDS Hooks](https://cds-hooks.hl7.org/2.0/)

The FDA's clinical decision-support guidance reinforces that the basis of a
recommendation must be reviewable rather than hidden behind persuasive generated
text:

- [FDA Clinical Decision Support Software guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software)

These references inform architecture and safety boundaries. They do not establish
that CLARA improves health outcomes; that requires prospective validation.

## 3. Product principles

### 3.1 Consumer-first

- Default copy targets an ordinary adult with no medical training.
- The first screen shows today's meaningful items, not system capabilities.
- The user should not need to select “Chat”, “RAG”, “Research mode”, or an agent.
- Medical depth is progressively disclosed.
- Doctor and researcher tools remain available, but they do not define the default
  navigation or consumer mental model.

### 3.2 Ask less, understand more

- Reuse confirmed information already available for the active purpose.
- Never ask the user to repeat a medication, allergy, or recent result that is
  already current and confirmed.
- Ask a clarification only when it can change urgency, medication safety, the next
  action, or the interpretation of a meaningful trend.
- Explain why a sensitive or seemingly unrelated question matters.

### 3.3 Track change, not just ranges

- Compare a new observation with both a clinical reference range and the user's
  personal baseline when enough data exist.
- Never call a baseline “normal” merely because it is typical for that user.
- Show the date window and data quality behind every trend.
- Distinguish a single outlier from a sustained change.

### 3.4 Close the loop

- Every recommended action has an owner, due window, status, and completion path.
- CLARA checks whether the action occurred and updates the episode.
- A Health Episode cannot silently disappear from recency ordering.
- Closure requires a recorded reason: resolved, clinician-reviewed, monitoring
  transitioned, user-dismissed, duplicate, or safety handoff.

### 3.5 Calm, not alarming

- Do not turn every abnormal value into a warning.
- Notifications require a documented trigger and expected user benefit.
- Severity language must reflect both risk and uncertainty.
- Emergency escalation is direct and fast; non-emergency uncertainty is explained
  without catastrophic framing.

### 3.6 Facts are not inferences

- Model inference can never overwrite a user-confirmed or imported fact.
- An inferred diagnosis is never saved as a diagnosis.
- The user can inspect, correct, confirm, or delete extracted information.
- Corrections create an audit event; they do not erase the historical reason for a
  prior system action.

## 4. Target audiences and product weighting

Product prioritization:

- 75% consumer and caregiver experience.
- 15% clinician handoff and visit continuity.
- 10% researcher/evidence tooling exposed through progressive disclosure.

Primary personas:

1. A generally healthy user trying to understand a new symptom or result.
2. A person managing one or more chronic conditions.
3. A person taking several medicines or supplements.
4. An adult coordinating care for a parent or child.
5. A user preparing for, attending, or following up after a clinical visit.

Secondary personas:

- Clinician receiving a user-approved Visit Pack.
- Researcher inspecting the evidence behind a LifeMap interpretation.

## 5. Flagship experiences

### 5.1 Today with CLARA

The authenticated home page is not a blank composer. It is a calm daily brief:

```text
Chào buổi sáng, Minh

2 việc đáng chú ý hôm nay

Chóng mặt sau khi đổi thuốc
Hãy đo huyết áp theo hướng dẫn trước 20:00.
[Bắt đầu đo] [Tôi đã làm] [Tại sao cần làm?]

Thuốc mới chưa rõ thời điểm sử dụng
Chụp nhãn thuốc để CLARA kiểm tra lịch dùng và tương tác.
[Chụp thuốc]

[Nói với CLARA] [Chụp kết quả] [Thêm thuốc]
```

Priority order:

1. Emergency or urgent active episode.
2. Medication-safety action.
3. Time-sensitive care task.
4. New meaningful change.
5. Follow-up check-in.
6. Optional health understanding.

The home page must not display empty medical dashboards or generic wellness advice
to create artificial activity.

### 5.2 Universal Capture

A central capture control accepts:

- voice or text;
- laboratory or imaging result photo/PDF;
- prescription or medicine package photo;
- discharge or visit document;
- a quick symptom check-in;
- home measurement;
- supported wearable import.

The flow is:

```text
Capture
→ classify artifact with an LLM into a typed schema
→ extract into a quarantine draft
→ normalize codes, units, dates and medicines
→ show a confirmation preview
→ obtain purpose-specific consent when needed
→ commit confirmed records
→ update affected episodes and tasks
```

Regex or keyword hints must not be used as the primary medical classifier. LLM
structured extraction handles semantic interpretation; deterministic parsers handle
dates, units, identifiers and safety invariants.

The preview must identify uncertainty:

```text
CLARA đọc được:

✓ Amlodipine 5 mg — có vẻ dùng mỗi sáng
? Ngày bắt đầu chưa rõ
? Dòng thứ hai trên toa chưa đọc chắc chắn

[Xác nhận] [Sửa] [Chụp lại]
```

### 5.3 LifeMap

LifeMap is a user-readable longitudinal health story, not a raw EHR.

It contains:

- active and resolved Health Episodes;
- medicines and their courses;
- symptoms and functional impact;
- measurements and trends;
- results and documents;
- visits and care transitions;
- user goals and care tasks;
- allergies and safety constraints;
- personal baselines with confidence and time windows.

Views:

- **Now:** current state and open decisions.
- **Timeline:** what changed and when.
- **Patterns:** repeated or sustained changes with uncertainty.
- **Documents:** original records and extracted facts.
- **Shared:** information currently visible to caregivers or clinicians.

Every timeline item shows provenance:

- “Bạn đã nhập”
- “Đọc từ kết quả xét nghiệm”
- “Đọc từ toa thuốc”
- “Được bác sĩ xác nhận”
- “CLARA suy luận — chưa xác nhận”

### 5.4 Health Episodes

A Health Episode groups related events around one user goal or health concern:

```text
Episode: Chóng mặt sau đổi thuốc
State: monitoring
Opened: 24/07/2026
Urgency: cần đánh giá sớm

What is known
✓ New medicine started 12 days ago
✓ Lower recent home blood pressure
✓ No reported chest pain

What is uncertain
○ Standing blood pressure
○ Heart rate
○ Hydration status

Next safe steps
1. Complete a guided measurement
2. Do not change the prescribed dose independently
3. Review at 20:00 or sooner if red flags appear
```

Episode states:

```text
draft
→ active
→ awaiting_information
→ monitoring
→ clinician_handoff
→ resolved
→ archived
```

An episode may move backward when new information changes the assessment. Every
transition has a reason and actor.

### 5.5 Health Replay

Health Replay answers “What changed?” using a temporal ledger:

- event ordering;
- before/after windows;
- missing intervals;
- medication-course changes;
- symptom onset and resolution;
- measurement trends;
- relevant care tasks;
- alternative explanations.

Output partitions:

1. **Observed sequence:** events supported by confirmed records.
2. **Possible relationship:** hypotheses generated from temporal and medical context.
3. **What would help distinguish them:** next-best information.
4. **What not to conclude:** explicit causal and diagnostic limits.

CLARA must not claim that temporal sequence proves causality.

### 5.6 Medicine Guardian

Medicine Guardian replaces the static medicine list.

For every medication course it stores:

- normalized ingredient and product;
- prescribed/reported dose, route and schedule;
- reason for use if known;
- prescriber/source;
- start, change and stop dates;
- adherence status only when explicitly reported;
- allergy, duplication and DrugBank DDI state;
- relevant monitoring tasks;
- supply/refill estimate when the user opts in;
- linked symptoms, results and episodes without asserting causality.

Consumer questions become one-tap actions:

- “Thuốc này dùng để làm gì?”
- “Tôi uống thuốc này khi nào?”
- “Có trùng hoạt chất không?”
- “Có tương tác với thuốc đang dùng không?”
- “Triệu chứng này bắt đầu sau thuốc nào?”
- “Tôi cần hỏi bác sĩ điều gì?”

DrugBank remains the mandatory authority for DDI conclusions. An unavailable
DrugBank lookup produces a visible no-conclusion state, never a local-rule
substitution presented as equivalent.

### 5.7 CLARA Visit

Before a visit:

- capture the user's top concern;
- generate a concise timeline;
- reconcile medicines and allergies;
- identify missing high-impact details;
- prepare questions in the user's words;
- produce a user-approved Visit Pack.

During a visit:

- optional Scribe only after explicit participant consent;
- display recording state continuously;
- allow immediate pause and deletion;
- treat generated notes as drafts.

After a visit:

- ingest the visit summary or prescription;
- translate instructions into plain language;
- create medication changes and care tasks only after confirmation;
- schedule follow-up checkpoints;
- explain what changed from the prior plan.

The Visit Pack has two views:

- consumer summary;
- clinician handoff with provenance and explicit “patient-reported” labeling.

### 5.8 Family Circle

Family Circle supports care coordination without creating silent surveillance.

Permission scopes:

- view today's tasks;
- view medications;
- view selected episodes;
- receive urgent safety notifications;
- add observations;
- upload documents;
- create a Visit Pack;
- never access;
- time-limited access.

Requirements:

- permission is granted per profile and per scope;
- high-sensitivity episodes can be excluded;
- every access is visible in an audit history;
- the supported person can revoke access;
- emergency sharing behavior is explicitly configured, not assumed;
- child/dependent relationships require jurisdiction-specific policy.

## 6. Information architecture

### 6.1 Consumer primary navigation

Desktop:

1. **Today**
2. **LifeMap**
3. **Medicines**
4. **Visit**
5. **Profile**

A persistent central action opens Universal Capture:

```text
[ Nói hoặc thêm thông tin ]
```

Mobile bottom navigation:

```text
Today | LifeMap | + | Medicines | Profile
```

Visit appears from Today, active Episodes and Profile. Family Circle is under the
profile switcher. Research is under “Explore evidence” and is not a primary
consumer navigation item.

### 6.2 Chat placement

Chat is available:

- as a bottom sheet from any LifeMap object;
- inside an Episode with episode context;
- inside Medicine Guardian with medication context;
- inside Visit before or after the encounter;
- as a full-page accessibility fallback.

The composer must display the context being used:

```text
Đang hỏi về: Chóng mặt sau đổi thuốc
Được phép dùng: thuốc hiện tại, huyết áp 14 ngày, xét nghiệm 30 ngày
[Xem hoặc thay đổi]
```

A message may create or update an episode only after a structured preview and
confirmation when it changes durable medical state.

### 6.3 Progressive medical depth

Layer 1 — consumer action:

- what this may mean;
- what to do now;
- what to monitor;
- when to seek care.

Layer 2 — “Why CLARA says this”:

- relevant personal facts;
- missing facts;
- medicine and measurement checks;
- uncertainty.

Layer 3 — evidence:

- guideline/trial source;
- population applicability;
- publication type;
- PMID, DOI or NCT when available;
- claim-level support.

## 7. Consumer copy and visual language

### 7.1 Voice

- calm, direct and respectful;
- short sentences;
- no “AI doctor” persona;
- no unnecessary medical terminology;
- no false reassurance;
- no legal disclaimer repeated after every paragraph;
- uncertainty expressed as a reason and next step.

Preferred:

> Kết quả này cao hơn mức thường thấy của bạn. Một lần đo chưa đủ để xác định xu
> hướng. CLARA đề nghị kiểm tra lại đúng điều kiện và đối chiếu với các triệu chứng
> hiện tại.

Avoid:

> Chỉ số bất thường nghiêm trọng có thể liên quan đến nhiều bệnh nguy hiểm. Hãy tham
> khảo ý kiến bác sĩ.

### 7.2 Visual system

- Light mode is the primary design target; dark mode has equivalent contrast and
  hierarchy.
- Warm neutral surfaces, restrained clinical color and generous whitespace.
- Red is reserved for urgent action; orange for time-sensitive review; blue/teal for
  information and progress.
- Do not use dense “hospital dashboard” layouts for consumers.
- Each screen has one dominant action.
- Timelines use plain-language event cards, not raw tables by default.
- Confidence is explained in words before showing a numerical value.
- Motion is limited and respects reduced-motion settings.
- WCAG 2.2 AA is the minimum acceptance level.

## 8. Functional requirements

### 8.1 Account and onboarding

`LIFE-001` A new user can enter the product without creating a medical profile.  
`LIFE-002` The product explains the benefit and scope of longitudinal memory before
requesting consent.  
`LIFE-003` Users choose whether to enable LifeMap, medication tracking, notifications,
family sharing and model processing separately.  
`LIFE-004` Onboarding asks only for information needed for the first useful
experience.  
`LIFE-005` The user can skip optional demographic or medical questions.  
`LIFE-006` Login restores the last active profile and Today view, not an empty Chat
page.

### 8.2 Capture and confirmation

`CAP-001` Text, voice, image and document ingestion produce a typed extraction draft.  
`CAP-002` Original files and extracted fields have separate retention controls.  
`CAP-003` Low-confidence fields are visibly marked and cannot silently enter
confirmed state.  
`CAP-004` Medicine name, strength, unit, route and schedule are confirmed
independently.  
`CAP-005` The user can correct an extraction before commit.  
`CAP-006` A correction creates a versioned audit event.  
`CAP-007` Medical semantic classification uses structured model output; deterministic
code validates schema, units, dates and safety constraints.

### 8.3 LifeMap

`MAP-001` All committed facts have provenance, effective time and truth status.  
`MAP-002` Users can inspect the source document for an imported fact.  
`MAP-003` Users can correct or revoke a fact without deleting unrelated history.  
`MAP-004` Personal baselines display the sample count, date window and confidence.  
`MAP-005` Trends distinguish measurement time from upload time.  
`MAP-006` Model inferences are never included in export as confirmed diagnoses.  
`MAP-007` Duplicate imports merge only after deterministic identity checks or user
confirmation.

### 8.4 Episodes

`EP-001` A user can create an episode explicitly or approve a suggested episode.  
`EP-002` Episode creation records the user goal in plain language.  
`EP-003` Episode state transitions are durable and replayable.  
`EP-004` An episode lists known, uncertain and conflicting information separately.  
`EP-005` Every next step has an owner, due window and completion state.  
`EP-006` A check-in updates the episode rather than starting an unrelated chat.  
`EP-007` An episode cannot be marked resolved by an LLM without a user-confirmed or
workflow-defined closure reason.  
`EP-008` Emergency escalation bypasses normal episode processing.  
`EP-009` A user can archive or dismiss an episode without being forced to accept a
model interpretation.

### 8.5 Notifications

`NOT-001` Every notification stores a trigger code and affected object.  
`NOT-002` Generic engagement notifications are prohibited.  
`NOT-003` Notifications are deduplicated and rate limited.  
`NOT-004` Emergency notifications are never used as a substitute for an immediate
on-screen escalation.  
`NOT-005` Users control categories, quiet hours and caregiver escalation.  
`NOT-006` A notification must link to the exact episode, task or medicine state.

### 8.6 Family Circle

`FAM-001` Access is deny-by-default.  
`FAM-002` Every grant has profile, scope, actor, start and optional expiry.  
`FAM-003` The supported user sees who accessed what and when.  
`FAM-004` Revocation blocks future access immediately and invalidates active shared
sessions.  
`FAM-005` Caregiver-entered observations are labeled with their author.  
`FAM-006` CLARA never merge facts across family profiles.

## 9. Domain model

### 9.1 Truth and provenance

```text
TruthStatus =
  reported
  | observed
  | imported
  | clinician_confirmed
  | model_inferred
  | disputed
  | superseded

ProvenanceActor =
  user
  | caregiver
  | clinician
  | document
  | connected_device
  | deterministic_tool
  | model
```

`model_inferred` is never automatically promoted. Promotion requires a user,
caregiver or clinician confirmation appropriate to the fact type.

### 9.2 Core records

```text
HealthEvent {
  event_id, profile_id, kind, effective_start, effective_end?,
  recorded_at, truth_status, provenance_actor, source_ref?,
  confidence?, payload, supersedes_event_id?, sensitivity,
  consent_scope, created_by, version
}

Observation {
  observation_id, event_id, code_system?, code?, display,
  value, unit?, reference_range?, body_site?, method?,
  interpretation?, observed_at, data_quality
}

MedicationCourse {
  course_id, profile_id, ingredient_id?, product_id?, display_name,
  strength?, dose?, route?, schedule?, indication?,
  start_at?, end_at?, status, prescriber_ref?, source_ref,
  truth_status, drugbank_resolution, version
}

SymptomRecord {
  symptom_id, profile_id, concept?, user_words,
  onset_at?, resolved_at?, severity?, pattern?, functional_impact?,
  associated_features[], absent_features[], truth_status, version
}

HealthEpisode {
  episode_id, profile_id, title, user_goal, state, urgency,
  opened_at, closed_at?, closure_reason?, primary_concern?,
  linked_event_ids[], linked_course_ids[], current_snapshot_id,
  owner, version
}

EpisodeSnapshot {
  snapshot_id, episode_id, created_at,
  known_facts[], uncertain_items[], contradictions[],
  hypotheses[], missing_information[], safety_state,
  next_step_ids[], model_manifest?, evidence_manifest?
}

CareTask {
  task_id, profile_id, episode_id?, kind, title, rationale,
  owner, due_start?, due_end?, status, completion_event_id?,
  escalation_policy?, source: user|clinician|workflow|clara,
  requires_confirmation, version
}

PersonalBaseline {
  baseline_id, profile_id, observation_code,
  period_start, period_end, sample_count, method,
  center?, dispersion?, trend?, confidence,
  excluded_event_ids[], generated_at, version
}

ConsentGrant {
  grant_id, profile_id, grantee?, purpose, scopes[],
  granted_at, expires_at?, revoked_at?, policy_version
}

DecisionLedger {
  decision_id, profile_id, episode_id?, generated_at,
  patient_snapshot_hash, knowledge_versions,
  tool_runs[], evidence_ids[], assumptions[],
  verification_findings[], release_action,
  model_manifest, prompt_protocol_version, replay_status
}
```

### 9.3 FHIR interoperability projection

The internal model remains optimized for CLARA, with tested projections:

- HealthEvent/Observation → FHIR Observation, Condition or DocumentReference.
- MedicationCourse → MedicationStatement/MedicationRequest.
- Episode → EpisodeOfCare/CarePlan depending on use.
- CareTask → Task/ServiceRequest.
- Visit Pack → Composition/Bundle.
- Executable workflow → PlanDefinition/ActivityDefinition.
- Decision Ledger output → GuidanceResponse plus Provenance.

FHIR projection is not allowed to erase CLARA truth status or consent metadata.

## 10. System architecture

```text
Web / Mobile / Voice / Upload
              │
              ▼
       Universal Capture API
              │
     ┌────────┴────────┐
     ▼                 ▼
Extraction Draft   Existing record/event
     │                 │
     ▼                 │
Confirmation & consent │
     └────────┬────────┘
              ▼
     Health Event Store
              │
   ┌──────────┼───────────┐
   ▼          ▼           ▼
Timeline   Medication   Baseline
Projector  Projector    Engine
   └──────────┬───────────┘
              ▼
       Episode Orchestrator
              │
   ┌──────────┼────────────┬────────────┐
   ▼          ▼            ▼            ▼
Risk Gate  CareGuard   Temporal     Evidence /
                       Reasoner      Knowledge
   └──────────┬────────────┴────────────┘
              ▼
      Next-step Planner
              │
              ▼
     Verification & Release
              │
     ┌────────┴─────────┐
     ▼                  ▼
Today projection   Decision Ledger
     │
     ▼
Notification / Visit / Episode UI
```

### 10.1 Service boundaries

1. **Profile service:** profile identity and family relationships.
2. **Consent service:** purpose-bound data and sharing authorization.
3. **Capture service:** uploads, extraction drafts and confirmation.
4. **Health event service:** append-oriented, versioned clinical event store.
5. **Terminology service:** medicines, units, observation codes and synonyms.
6. **Timeline projector:** materialized, user-readable chronology.
7. **Baseline engine:** deterministic statistical personal-baseline computation.
8. **Episode service:** state machine, snapshots and linked events.
9. **Care task service:** follow-up and completion lifecycle.
10. **Medication Guardian:** cabinet, courses, DrugBank and monitoring links.
11. **Medical harness:** context, retrieval, reasoning and answer artifacts.
12. **Notification service:** policy-governed, deduplicated delivery.
13. **Visit service:** Visit Pack, Scribe linkage and post-visit plan.
14. **Audit/Decision Ledger:** immutable run and action provenance.

The first implementation may share deployments, but these boundaries and contracts
must remain explicit.

## 11. Agent and harness design

Agents are bounded artifact-producing workers, not role-play personas.

### 11.1 Episode graph

```text
Episode Orchestrator
  1. Context Scope Agent
  2. Temporal State Agent
  3. Deterministic Risk Gate
  4. Medication Safety Agent
  5. Missing Information / Next-Best-Question Agent
  6. Evidence Applicability Agent when needed
  7. Next-Step Planner
  8. Adversarial Safety Verifier
  9. Consumer Explanation Renderer
 10. Release Adjudicator
```

Typed contracts:

```text
EpisodeRunRequest {
  run_id, profile_id, episode_id, trigger,
  allowed_context_scopes[], locale, jurisdiction,
  deadline_ms, client_capabilities
}

TemporalState {
  as_of, confirmed_events[], reported_events[],
  imported_events[], inferred_events[],
  medication_courses[], trend_summaries[],
  conflicts[], missing_intervals[], source_hashes[]
}

EpisodeAssessment {
  urgency, emergency, known_facts[], uncertain_items[],
  hypotheses[], evidence_for_against[],
  medication_findings[], missing_information[],
  prohibited_actions[], deterministic_floors[]
}

NextStepProposal {
  step_id, action_type, consumer_text, rationale,
  owner, due_window?, completion_contract,
  expected_information_gain?, affected_decisions[],
  escalation_policy?, source_refs[]
}

EpisodeRelease {
  action: release|release_with_warning|clarify|escalate|abstain,
  episode_patch?, task_proposals[], explanation,
  verification_findings[], decision_ledger_id
}
```

### 11.2 Authority rules

- Deterministic emergency and medication safety floors outrank model output.
- A model may propose an episode patch but cannot commit it directly.
- A model cannot create a confirmed diagnosis or clinician order.
- A deterministic calculator must expose inputs, version and result.
- A CareTask created from a clinician document must remain “pending confirmation”
  until the user confirms extraction accuracy.
- The Release Adjudicator is the only component that can publish user-visible next
  steps generated by the harness.
- Agent disagreement is a verifier input, not content shown as artificial
  “specialist debate”.

### 11.3 Context compilation

Context is episode-scoped and purpose-minimized:

```text
required current facts
+ relevant temporal window
+ active medications/allergies
+ linked observations/documents
+ unresolved prior questions
+ currently authorized family/visit context
- unrelated history
- expired consent scopes
- unconfirmed model inferences presented as facts
```

The UI must preview context scope for sensitive model requests.

## 12. Personal baseline engine

The baseline engine is deterministic and separate from the LLM.

Requirements:

- minimum sample count per observation type;
- configurable stability window;
- unit normalization before computation;
- detection and exclusion of obvious data-entry errors;
- no automatic exclusion of clinically abnormal values merely because they are
  inconvenient;
- confidence based on sample count, recency and dispersion;
- provenance for excluded samples;
- support for medication-course and episode annotations;
- no causal statement from correlation.

The LLM may explain a computed baseline but may not invent or recompute it.

## 13. Next-best-question engine

A question is allowed only if it can affect:

- emergency or urgency state;
- medication safety;
- distinction between active hypotheses;
- whether a care task is appropriate;
- interpretation of a trend;
- need for clinician handoff.

Every question record includes:

```text
question
reason_for_asking
decision_affected
possible_answer_effects
sensitivity
can_skip
```

Consumer presentation:

> CLARA hỏi điều này vì câu trả lời có thể thay đổi mức độ cần đi khám hôm nay.

The engine must avoid exhaustive history-taking when it does not alter the next safe
step.

## 14. Safety and regulatory boundaries

### 14.1 Consumer safety

CLARA may:

- explain health information;
- organize user-provided records;
- identify red flags;
- provide safe, general next steps;
- prepare questions and handoff summaries;
- support adherence to an already confirmed plan;
- check DrugBank-backed interactions.

CLARA must not:

- present itself as a doctor;
- establish a definitive diagnosis for a consumer;
- independently initiate, stop or titrate prescription medication;
- claim an unvalidated causal relationship;
- hide a failed tool lookup;
- treat a model inference as medical history;
- create urgency through engagement-oriented copy;
- provide false reassurance from incomplete data.

### 14.2 Emergency path

Emergency routing occurs before:

- deep retrieval;
- episode synthesis;
- evidence report generation;
- notification scheduling.

It returns:

- immediate action in the explicit UI language;
- concise red-flag rationale;
- optional preparation steps that do not delay care;
- a durable event indicating escalation was shown;
- no diagnosis claim.

### 14.3 Counterfactuals

Consumer counterfactual views are evidence-bound scenario comparisons, not
individual treatment-effect predictions unless a separately validated model and
governance process exists.

Allowed:

> Nếu thông tin X được xác nhận, hướng xử trí thường được cân nhắc khác ở điểm Y.

Prohibited:

> Nếu bạn dùng thuốc A, nguy cơ của bạn chắc chắn sẽ giảm 30%.

## 15. Privacy, security and user control

- LifeMap is opt-in and can be disabled without losing basic question answering.
- Model processing, longitudinal storage, notifications and Family Circle use
  separate consent purposes.
- Data is encrypted in transit and at rest.
- Sensitive fields use application-layer protection where supported.
- Access and refresh sessions must support immediate revocation.
- Deleting a profile invalidates all active sessions and shares.
- Exports distinguish user-reported, imported and inferred content.
- Users can delete an original file while retaining selected confirmed facts, or
  delete both.
- Family access uses deny-by-default authorization at every object read.
- Model providers receive only the minimum context required for the current task.
- No raw health content is written to application logs or metrics.
- Retention and deletion operations are auditable and idempotent.

## 16. API contracts

Illustrative endpoints:

```text
POST   /api/v1/capture/drafts
GET    /api/v1/capture/drafts/{draft_id}
PATCH  /api/v1/capture/drafts/{draft_id}
POST   /api/v1/capture/drafts/{draft_id}/confirm
DELETE /api/v1/capture/drafts/{draft_id}

GET    /api/v1/lifemap/today
GET    /api/v1/lifemap/timeline
GET    /api/v1/lifemap/events/{event_id}
PATCH  /api/v1/lifemap/events/{event_id}

POST   /api/v1/episodes
GET    /api/v1/episodes
GET    /api/v1/episodes/{episode_id}
POST   /api/v1/episodes/{episode_id}/check-ins
POST   /api/v1/episodes/{episode_id}/run
POST   /api/v1/episodes/{episode_id}/close
GET    /api/v1/episodes/{episode_id}/ledger

GET    /api/v1/care-tasks
POST   /api/v1/care-tasks/{task_id}/complete
POST   /api/v1/care-tasks/{task_id}/snooze

GET    /api/v1/medication-courses
POST   /api/v1/medication-courses
PATCH  /api/v1/medication-courses/{course_id}
POST   /api/v1/medication-courses/check

POST   /api/v1/visit-packs
GET    /api/v1/visit-packs/{pack_id}
POST   /api/v1/visit-packs/{pack_id}/share

GET    /api/v1/family/grants
POST   /api/v1/family/grants
DELETE /api/v1/family/grants/{grant_id}
GET    /api/v1/family/access-log
```

Mutation endpoints require CSRF protection for cookie sessions, idempotency keys and
object-level authorization.

### 16.1 Today projection

```text
TodayResponse {
  profile,
  generated_at,
  urgent_items[],
  medication_items[],
  due_tasks[],
  meaningful_changes[],
  check_ins[],
  optional_insights[],
  capture_actions[],
  degraded_state?
}
```

Each item contains:

```text
item_id, kind, title, explanation, severity,
primary_action, secondary_actions[],
source_object_ref, trigger_code, generated_at,
expires_at?, decision_ledger_ref?
```

## 17. Eventing and background processing

Domain events:

```text
capture.draft.created
capture.draft.confirmed
health_event.committed
health_event.corrected
medication_course.changed
drugbank.check.completed
episode.opened
episode.context_changed
episode.assessment.completed
episode.urgency_changed
episode.task_due
episode.checkin.received
episode.closed
baseline.updated
visit_pack.created
family.grant.changed
consent.revoked
```

Requirements:

- at-least-once delivery with idempotent consumers;
- durable outbox for database-originating events;
- deterministic event ordering per profile where required;
- no notification before the underlying transaction commits;
- explicit dead-letter and replay workflow;
- episode recalculation coalesces rapid updates;
- emergency response is synchronous and never waits for the event bus.

## 18. Reliability and degradation

Priority classes:

1. P0 emergency and medication safety.
2. P1 interactive capture, confirmation and Today.
3. P2 episode update and normal explanation.
4. P3 Visit Pack/Scribe generation.
5. P4 deep Research and background evidence watch.

Interactive Chat/LifeMap and batch Research/Scribe must use separate worker pools and
concurrency budgets. P4 work cannot consume the last P0–P2 capacity.

Degradation rules:

- Timeline and confirmed records remain available when LLM providers fail.
- DrugBank unavailability produces a typed DDI no-conclusion.
- Extraction failure preserves the original upload and asks for manual confirmation.
- Baseline computation failure hides the trend insight rather than fabricating it.
- NLI/verifier failure prevents decision-ready evidence claims but does not erase
  confirmed user data or care tasks.
- Notification failure is retried without duplicating tasks.

## 19. Metrics

### 19.1 North-star metric

**Safely resolved or handed-off Episodes per monthly active LifeMap user.**

An episode counts only when:

- the closure state and reason are recorded;
- required safety tasks are not unresolved;
- the user confirms resolution or a valid workflow handoff exists;
- no critical safety review later identifies harmful guidance.

### 19.2 Consumer value

- time from capture to first useful next step;
- percentage of captures requiring manual correction;
- episode follow-up completion;
- Visit Pack completion and user usefulness rating;
- medication-course reconciliation completeness;
- percentage of repeated questions avoided through confirmed context;
- user comprehension/teach-back success;
- Family Circle task coordination success.

### 19.3 Safety

- emergency recall and matched-control specificity;
- harmful-action rate;
- false reassurance rate;
- unnecessary alarm/escalation rate;
- critical medication finding recall;
- inference-presented-as-fact rate;
- incorrect profile/family data exposure: zero tolerance;
- action released without Decision Ledger: zero tolerance;
- immediate session/share revocation correctness.

### 19.4 Reliability

- P50/P95 Today latency;
- P50/P95 interactive episode update latency;
- capacity reserved for P0–P2;
- provider fallback and abstention rates;
- event processing lag;
- notification duplication;
- extraction and baseline retry rates;
- unresolved dead-letter count.

Engagement time, message count and notification opens are diagnostics, not success
metrics.

## 20. Evaluation

### 20.1 Offline

- temporal ordering and boundary adherence;
- fact/inference separation;
- episode linking precision and recall;
- medicine extraction and normalization;
- baseline correctness;
- next-best-question decision impact;
- emergency and medication safety;
- plain-language comprehension;
- family authorization;
- event replay equivalence.

### 20.2 Scenario E2E

Required scenarios:

1. New symptom with no history.
2. Symptom after a medication change.
3. Lab image followed by a repeat result.
4. Multiple medicines with positive DrugBank interaction.
5. DrugBank unavailable.
6. Emergency symptom in Vietnamese and English.
7. Scribe-assisted visit with consent and post-visit tasks.
8. Family caregiver adds an observation.
9. User corrects a wrongly extracted medicine.
10. User revokes Family Circle access during an active session.
11. LLM/NLI outage while Today and confirmed timeline remain functional.
12. Research load while an interactive episode receives a response.

### 20.3 Prospective validation

Before claims of improved outcomes:

- clinician-reviewed silent deployment;
- consumer usability and comprehension study;
- false-alarm burden measurement;
- prospective comparison of visit preparedness or task completion;
- ethics, privacy and regulatory review appropriate to intended use.

## 21. Migration from Chat-first CLARA

### 21.1 Reuse

- authentication, refresh and consent;
- medical answer harness and emergency path;
- DrugBank/CareGuard;
- medicine cabinet data after migration to medication courses;
- Scribe and signed notes;
- Research evidence records;
- citation, verification and Decision Ledger foundations;
- navigation shell and theme system.

### 21.2 Replace

- `/chat` as the post-login landing page;
- blank-composer home;
- conversation as the primary durable unit;
- role-first feature navigation for consumers;
- isolated medicine records without course history;
- generic chat history as medical memory;
- notification-free, non-durable follow-up prose.

### 21.3 Compatibility

- Existing chat threads remain readable.
- A user can explicitly convert a thread into an Episode.
- No legacy assistant claim is migrated as a confirmed fact.
- Existing medicine records enter a reconciliation draft before becoming active
  MedicationCourses.
- Existing consents are not broadened automatically.
- `/chat` remains as a redirectable accessibility/full-page surface during migration.

## 22. Delivery plan

### Phase 0 — contracts and safety foundations

- finalize truth/provenance model;
- implement immediate access-token and share revocation;
- create event outbox;
- define Episode and CareTask state machines;
- define Decision Ledger contract;
- separate interactive and batch capacity.

Exit gate:

- schema review by Product, Clinical Safety, Security and Data;
- property tests for truth promotion and authorization;
- P0/P1 traffic remains available under Research/Scribe load.

### Phase 1 — Today, Capture and Episode MVP

- Today home;
- universal text/voice capture;
- extraction confirmation;
- event timeline;
- manual Episode creation;
- care tasks and check-ins;
- episode-scoped Chat;
- existing medicine and emergency integration.

Exit gate:

- complete E2E for scenarios 1–6 and 11–12;
- no inference-as-fact violations;
- consumer usability test meets comprehension threshold.

### Phase 2 — Medicine Guardian and Health Replay

- medication-course migration;
- medicine photo capture;
- DrugBank status and provenance UI;
- personal baseline engine;
- temporal replay;
- next-best-question engine;
- meaningful-change cards.

Exit gate:

- medication reconciliation and DDI suite pass;
- baseline reference implementation parity;
- temporal clinician review gate pass.

### Phase 3 — CLARA Visit

- pre-visit intake;
- user-approved Visit Pack;
- Scribe linkage;
- post-visit extraction confirmation;
- care-plan tasks and follow-up.

Exit gate:

- consent and deletion E2E;
- no unsigned draft presented as clinician-approved;
- Visit Pack usefulness study.

### Phase 4 — Family Circle

- profile switcher;
- granular grants;
- caregiver observations;
- access log;
- scoped notifications;
- immediate revoke.

Exit gate:

- object-level authorization and cross-profile isolation tests;
- revocation takes effect within the defined SLO;
- privacy threat model approved.

### Phase 5 — Living evidence and validated personalization

- episode-linked evidence updates;
- guideline executable artifacts;
- trial applicability views;
- evidence change notifications;
- prospective validation.

No individualized treatment-effect or outcome-improvement claim is allowed before
the required independent validation.

## 23. Feature flags

```text
LIFEMAP_ENABLED
LIFEMAP_TODAY_ENABLED
LIFEMAP_CAPTURE_ENABLED
LIFEMAP_EPISODES_ENABLED
LIFEMAP_BASELINES_ENABLED
LIFEMAP_HEALTH_REPLAY_ENABLED
LIFEMAP_MEDICINE_GUARDIAN_ENABLED
LIFEMAP_VISIT_ENABLED
LIFEMAP_FAMILY_CIRCLE_ENABLED
LIFEMAP_NOTIFICATIONS_ENABLED
LIFEMAP_EXECUTABLE_GUIDELINES_ENABLED
```

Flags are independently reversible. Disabling an intelligence feature must not make
confirmed records inaccessible.

## 24. Definition of done

The product-direction migration is complete only when:

1. Login lands on Today, not Chat.
2. A user can capture information without composing a medical prompt.
3. Captured information is confirmed and stored with truth/provenance status.
4. A concern can persist as an Episode across sessions.
5. Follow-up tasks have durable completion states.
6. New information updates the existing Episode.
7. LifeMap clearly separates fact from inference.
8. Medicine Guardian uses DrugBank-only DDI conclusions.
9. Emergency behavior remains immediate and localized.
10. Interactive experiences remain functional during batch Research/Scribe load.
11. Family access is granular, audited and immediately revocable.
12. The user can inspect why a Today item exists.
13. Chat is a contextual interface to LifeMap rather than the system of record.
14. Consumer E2E, safety, accessibility and privacy gates pass.
15. No public clinical-outcome or benchmark-superiority claim exceeds validated
    evidence.

## 25. Product copy summary

Brand:

> CLARA remembers your health.

Consumer explanation:

> Thay vì bắt đầu lại mỗi lần bạn có một câu hỏi, CLARA giúp bạn ghi lại điều đã xảy
> ra, nhận ra những thay đổi đáng chú ý và theo dõi bước tiếp theo cho đến khi vấn đề
> được giải quyết hoặc chuyển giao an toàn.

Internal product rule:

> A message is temporary. A confirmed health event, episode, task and decision
> ledger are durable.

