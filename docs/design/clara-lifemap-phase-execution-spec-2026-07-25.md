# CLARA LifeMap — Detailed Phase Execution Specification

Status: implementation-ready delivery specification
Date: 2026-07-25
Parent specification:
[CLARA LifeMap — Consumer Health Platform Specification](./clara-lifemap-consumer-health-platform-spec-2026-07-25.md)
Audience: Product, Design, Web, API, ML, Data, Clinical Safety, Security, QA, SRE
Applies to: Phase 0 through Phase 5 of the CLARA LifeMap migration

## 1. Purpose

This document turns the LifeMap product direction into independently releasable,
testable implementation phases. It defines exactly what each phase must deliver,
which real data and service contracts it needs, what is deliberately excluded, and
which evidence is required before the next phase begins.

This is an execution contract, not an aspirational roadmap. A phase is not complete
because screens exist or a happy-path demo works. It is complete only when:

1. its vertical slices work with persisted production-shaped data;
2. authorization, consent, audit and deletion behavior are verified;
3. failure and degraded states are user-visible and safe;
4. automated and human safety gates pass;
5. telemetry proves that the release can be observed and reversed;
6. the named exit evidence has been recorded.

No feature covered by this specification may use fake, mock or randomly generated
health data in a production path. Synthetic fixtures remain required in isolated
tests and explicitly labeled demo environments.

## 2. Delivery strategy

### 2.1 Release sequence

```text
Phase 0: trustworthy platform contracts
    |
    v
Phase 1: Today + Capture + durable Episodes
    |
    v
Phase 2: Medicine Guardian + personal change detection + Replay
    |
    v
Phase 3: prepare for and close the loop around a real visit
    |
    v
Phase 4: consented family and caregiver coordination
    |
    v
Phase 5: living evidence + validated personalization
```

Phases are ordered by dependency, not marketing priority. Selected work packages
may be developed in parallel, but no dependent capability may be released before
its predecessor's exit gate passes.

### 2.2 Vertical-slice rule

Each phase must first deliver one thin, complete path through:

```text
user action
  -> web/mobile interaction
  -> authenticated API
  -> domain validation
  -> durable Postgres write
  -> outbox event
  -> projection/background processing
  -> read model
  -> visible result
  -> audit/telemetry
```

Only after that slice is stable should the team add more input types, intelligence
or visual polish.

### 2.3 Existing-system mapping

The implementation extends the current stack rather than starting a second
platform:

| Concern | Existing CLARA surface | LifeMap treatment |
|---|---|---|
| Consumer web | `apps/web`, Next.js | add `/today`, `/lifemap`, `/medicines`, `/visit`; retain `/chat` as contextual/full-page fallback |
| API gateway | `services/api`, FastAPI | add LifeMap routers and domain services under `/api/v1` |
| Durable data | PostgreSQL + Alembic | source of truth for profiles, events, episodes, tasks, grants and ledgers |
| Ephemeral coordination | Redis | cache, queues, rate limits and revocation acceleration; never sole durable health store |
| Medical intelligence | `services/ml` | add typed LifeMap orchestration and evaluation; preserve deterministic safety boundaries |
| PHR | existing PHR models/API | migrate to canonical HealthEvent/Observation projections without silently promoting old data |
| Medicines/DDI | CareGuard + DrugBank | migrate cabinet items to MedicationCourse; DrugBank remains mandatory authority for DDI conclusions |
| Scribe | existing Scribe workflows | link only with explicit visit consent and signed/draft status preservation |
| Research/evidence | existing Research/RAG | background evidence service; never allowed to starve interactive P0–P2 workloads |
| Auth/consent/audit | existing API modules | extend with object-level grants, purpose scope and immediate revocation |

### 2.4 Workstream ownership

Every phase names a directly responsible owner for each workstream:

- Product: scope, copy, acceptance and metric definition.
- Design: flows, states, accessibility and usability evidence.
- API: domain invariants, persistence, authorization, outbox and contracts.
- Web/Mobile: interaction, offline-safe drafts, state restoration and accessibility.
- ML: typed extraction/reasoning contracts, evaluation and fallback.
- Clinical Safety: hazard analysis, safety cases and release approval.
- Security/Privacy: threat model, consent, isolation, deletion and audit.
- Data: migrations, provenance, backfills and metric correctness.
- SRE: capacity classes, deployment, monitoring, rollback and incident runbooks.
- QA: contract, integration, E2E, adversarial and regression suites.

No owner may self-approve a high-severity clinical safety gate.

## 3. Cross-phase engineering contracts

### 3.1 Truth and provenance states

All health-bearing records must use one of these states:

| State | Meaning | May drive user-facing action? |
|---|---|---|
| `reported` | entered or spoken by the user/caregiver | yes, with attribution |
| `imported` | obtained from an external record/source | yes, with source and freshness |
| `extracted_draft` | machine-extracted but not confirmed | only safety triage; never shown as fact |
| `confirmed` | explicitly confirmed or authoritative source verified | yes |
| `inferred` | model/deterministic interpretation | only when visibly labeled and confidence-qualified |
| `superseded` | replaced by a later version | no new action; remains auditable |
| `disputed` | user or reviewer says it may be wrong | no irreversible action |

Promotion must be an explicit event. Updating a field must not erase its earlier
state, source or author.

### 3.2 Identity and authorization

- Every object belongs to one `profile_id`, not merely a login `user_id`.
- Every request resolves actor, active profile, role, purpose and consent.
- Object-level authorization is checked in the domain service and query scope.
- Background jobs carry a signed scope reference, not raw broad credentials.
- Switching profile invalidates cached Today and Episode views.
- Revocation prevents new reads and writes immediately; caches are purged
  asynchronously but cannot override the authoritative deny decision.

### 3.3 Idempotency and concurrency

- Every mutating public endpoint accepts `Idempotency-Key`.
- Mobile/web retries return the original result for the same actor, profile,
  operation and body digest.
- Versioned aggregates use optimistic concurrency through `version`.
- Conflicts return `409` with the latest safe representation.
- Outbox rows are written in the same database transaction as domain changes.
- Consumers deduplicate on `event_id`.

### 3.4 Decision Ledger

Every surfaced health recommendation, warning, prioritization or meaningful-change
card stores:

- `decision_id`;
- active profile and episode;
- triggering event IDs;
- confirmed facts used;
- reported facts used;
- inferences used and their confidence;
- rules/models/knowledge versions;
- evidence or DrugBank references when applicable;
- alternative action considered;
- safety checks;
- release disposition: released, simplified, deferred, abstained or escalated;
- generated-at and expires/review-after time.

The ledger stores structured rationale, not hidden chain-of-thought.

### 3.5 API envelope

Successful reads return:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_...",
    "profile_id": "prof_...",
    "generated_at": "2026-07-25T08:00:00Z",
    "freshness": "live"
  }
}
```

Errors return a stable machine code, safe localized message, request ID, retry
classification and optional recovery action. Raw provider, SQL or stack-trace text
must never reach the client.

### 3.6 Performance classes

| Class | Examples | Scheduling requirement |
|---|---|---|
| P0 | emergency triage, revoke, auth | reserved capacity; never waits on generative research |
| P1 | Today, medicine warning, active Episode update | dedicated interactive pool |
| P2 | capture confirmation, task completion, visit checklist | interactive pool with bounded queue |
| P3 | baseline recomputation, notification projection | background pool |
| P4 | deep research, corpus ingestion, bulk export | isolated batch pool |

### 3.7 Release environments

- Local: developer dependencies; synthetic fixtures only.
- CI: deterministic unit, property, contract and migration tests.
- Staging: production-shaped infrastructure and de-identified scenario corpus.
- Shadow: computation runs on real consented traffic but output is not released.
- Canary: limited eligible users with rollback flag and enhanced monitoring.
- General availability: only after exit gate sign-off.

## 4. Phase 0 — Trustworthy contracts and safety foundations

### 4.1 Outcome

Phase 0 creates the substrate on which consumer health memory can safely exist. It
has almost no new consumer marketing surface. Its user-visible outcome is that
sessions, permissions and confirmed health data behave consistently and remain
available under load.

### 4.2 In scope

- canonical profile, truth/provenance and source-reference contracts;
- HealthEvent, HealthEpisode, CareTask and DecisionLedger foundations;
- transactional outbox and idempotency;
- immediate session/share/grant revocation;
- interactive versus batch capacity isolation;
- audit taxonomy and non-PII operational telemetry;
- feature-flag and migration framework;
- compatibility adapters for PHR, Medicine Cabinet, Chat, Scribe and Research.

### 4.3 Out of scope

- new Today design;
- automatic episode creation;
- baseline or meaningful-change claims;
- Family Circle sharing;
- personalized treatment recommendations.

### 4.4 P0-WP1 — Canonical identity and profile boundary

Deliverables:

1. Introduce stable `profile_id` for the account owner's personal profile.
2. Backfill one owner profile for each existing eligible account.
3. Add `active_profile_id` to authenticated context, not to long-lived access-token
   claims that can become stale.
4. Create a central `ProfileScope` dependency for FastAPI endpoints.
5. Require query filters by active profile on all new LifeMap repositories.
6. Add a deny-by-default test helper for cross-profile access.

Acceptance:

- two profiles under one test actor cannot read each other's objects without an
  explicit active grant;
- changing active profile changes every scoped response;
- missing or invalid profile scope returns `403`, never a broader account view.

### 4.5 P0-WP2 — Canonical domain schema

Minimum tables:

```text
health_profiles
health_events
source_references
health_episodes
episode_event_links
care_tasks
decision_ledgers
domain_outbox
idempotency_records
access_grants
access_revocations
```

Key invariants:

- IDs are opaque and non-sequential at public boundaries.
- All health tables carry `profile_id`, `created_at`, `updated_at`, `version`.
- Health records use soft lifecycle states; hard deletion is controlled by the
  deletion workflow.
- `source_references` holds immutable digest, origin, author/actor, acquisition
  time and verification state.
- Episode-event links retain link reason and actor.
- Decision Ledgers are append-only.
- Outbox payloads use schema version and contain IDs, not unnecessary PHI.

Migration requirements:

- Alembic upgrade and downgrade must pass on a production-shaped copy.
- Backfill is resumable, chunked and reports counts/checksums.
- Deployment supports expand → dual-read/dual-write where required → backfill →
  verify → contract.
- No existing PHR or medicine row is silently marked `confirmed`.

### 4.6 P0-WP3 — State machines

HealthEpisode:

```text
draft -> active -> monitoring -> resolved
                  \-> handed_off
active/monitoring -> paused
paused -> active
any non-terminal -> cancelled
```

CareTask:

```text
proposed -> accepted -> in_progress -> completed
                    \-> skipped
                    \-> expired
proposed -> dismissed
```

Rules:

- transitions are explicit commands and audited;
- terminal states cannot be reopened in place; a follow-up Episode links to the
  predecessor;
- completion requires `completed_at` and actor;
- model output may propose but cannot accept or complete a task for the user.

### 4.7 P0-WP4 — Revocation and consent enforcement

Implement:

- session `jti` denylist accelerated through Redis;
- authoritative revocation record in Postgres;
- cache invalidation event;
- share/grant version checked on every protected request;
- refresh-token rotation and family-wide revoke;
- consent purpose and version attached to background jobs;
- abort checks before every external model/provider call.

SLO:

- new protected requests are denied immediately after committed revocation;
- already-running streaming responses stop at the next bounded authorization
  checkpoint, target ≤ 2 seconds;
- asynchronous cache purge target P95 ≤ 5 seconds.

### 4.8 P0-WP5 — Outbox and worker isolation

Implement:

- atomic domain write plus outbox insert;
- leased consumers with heartbeat;
- exponential retry with jitter and maximum attempts;
- dead-letter state with safe replay tooling;
- dedicated P0–P2 and P3–P4 queues;
- per-provider timeouts and circuit breakers;
- backpressure that rejects/degrades batch work before interactive work.

Required chaos test:

1. start a P4 Research saturation load;
2. revoke a session;
3. issue a P1 Episode read and P2 capture write;
4. prove the revocation and interactive SLO remain inside thresholds.

### 4.9 P0-WP6 — Compatibility layer

- PHR observations remain readable through an adapter into the canonical event
  representation.
- Medicine cabinet items are exposed as migration candidates, not active
  MedicationCourses.
- Existing chat history remains a document; it is not health truth.
- Scribe notes preserve draft/signed/addendum status.
- Research evidence preserves citation and retrieval provenance.

### 4.10 Phase 0 API contracts

```text
GET    /api/v1/profiles
POST   /api/v1/profiles/{profile_id}/activate
GET    /api/v1/profiles/{profile_id}/capabilities
POST   /api/v1/sessions/revoke
GET    /api/v1/lifemap/health
GET    /api/v1/lifemap/schema-version
```

These endpoints may be internal until Phase 1, but contract tests must run against
the deployed staging service.

### 4.11 Phase 0 test matrix

| Layer | Required tests |
|---|---|
| Unit/property | allowed state transitions, truth promotion, idempotency digest, authorization predicates |
| Migration | upgrade/downgrade, resume after interruption, backfill checksum, legacy reads |
| Integration | transaction + outbox atomicity, Redis loss, worker retry, token revoke |
| Security | IDOR, stale grant, replayed token, profile switch cache leak |
| Load | P4 saturation while P0–P2 operate |
| Recovery | dead-letter replay, worker crash after commit, duplicate delivery |

### 4.12 Phase 0 exit gate

All must be true:

- Clinical Safety, Security, Data and API approve schema/invariants.
- Zero cross-profile access in the authorization suite.
- Zero truth-state promotion without an auditable transition.
- Duplicate commands have exactly-once observable effects.
- Revocation SLO passes in staging under load.
- P0/P1 availability and latency remain within agreed service objectives during
  Research/Scribe saturation.
- Rollback rehearsal completes without health-data loss.

Exit evidence:

- schema decision record;
- migration rehearsal report;
- threat model;
- load/chaos report;
- signed safety-foundation checklist.

## 5. Phase 1 — Today, Universal Capture and Episode MVP

### 5.1 Outcome

After login, an ordinary user sees what matters today, can record a concern without
writing a sophisticated prompt, confirms what CLARA understood, and follows the
concern across sessions as a durable Health Episode.

### 5.2 Primary vertical slice

```text
Login
 -> Today
 -> "Tôi bị đau đầu từ sáng nay"
 -> emergency pre-check
 -> structured extraction draft
 -> user confirms/corrects
 -> HealthEvent is persisted
 -> user opens a new Episode
 -> CLARA asks one high-value follow-up question
 -> user accepts a follow-up task
 -> Today displays the task on next login
```

### 5.3 In scope

- `/today` authenticated landing page;
- Universal Capture for text and voice;
- emergency bypass before normal generation;
- extraction confirmation;
- manual Episode create/link/update;
- event timeline;
- care tasks and check-ins;
- episode-scoped contextual Chat;
- deterministic Today projection;
- initial notifications for accepted tasks;
- old Chat-to-Episode conversion.

### 5.4 Out of scope

- photo medicine recognition;
- automatic personal baseline claims;
- autonomous episode diagnosis;
- Family Circle;
- clinical treatment plan execution.

### 5.5 P1-WP1 — Navigation and Today shell

Routes:

```text
/today                 primary post-login destination
/lifemap               chronological health map
/lifemap/episodes/:id  episode workspace
/capture               full-page accessible capture fallback
/chat                  retained contextual/full-page fallback
```

Consumer navigation:

- Today;
- LifeMap;
- Medicines;
- Visit;
- Profile;
- central Capture action.

Today card order:

1. urgent deterministic safety item;
2. accepted task due or overdue;
3. active Episode check-in;
4. recently captured draft needing confirmation;
5. optional learning/evidence item.

Today must not become an infinite engagement feed. If nothing requires attention,
show a calm zero state and the Capture action.

Required UI states:

- first use;
- loading skeleton;
- no action today;
- offline/stale projection;
- partial service degradation;
- urgent safety state;
- draft awaiting confirmation;
- accessible keyboard/screen-reader flow;
- light and dark themes with WCAG-compliant contrast.

### 5.6 P1-WP2 — Universal Capture

Input types:

- text;
- voice recording/transcription;
- quick structured chips for symptom, measurement, medicine, document and note.

Pipeline:

```text
raw input
 -> local size/type validation
 -> deterministic emergency classifier
 -> emergency bypass if positive
 -> ASR when voice
 -> typed extraction
 -> provenance-preserving draft
 -> confirmation UI
 -> canonical event creation
```

Typed extraction output:

```json
{
  "capture_id": "cap_...",
  "language": "vi",
  "event_type": "symptom_report",
  "occurred_at": "2026-07-25T07:00:00+07:00",
  "fields": [
    {
      "path": "symptom.name",
      "value": "đau đầu",
      "source_span": "đau đầu",
      "confidence": 0.97
    }
  ],
  "missing_critical_fields": ["severity"],
  "safety_disposition": "normal_confirmation"
}
```

Constraints:

- no regex hint may be the primary semantic understanding method;
- deterministic rules remain permitted for safety, validation, unit conversion and
  policy enforcement;
- the raw source is retained according to consent and retention policy;
- unsupported values remain unknown rather than invented;
- user corrections train evaluation datasets only under explicit consent.

### 5.7 P1-WP3 — Confirmation experience

The user sees:

- what CLARA understood;
- exact uncertain fields;
- source attribution;
- edit/remove controls;
- what will be saved;
- whether it will be linked to an existing Episode.

Confirmation actions:

- Confirm;
- Edit;
- Save as personal note;
- Discard;
- Use only for this response without adding to LifeMap, where policy permits.

Acceptance:

- no `extracted_draft` appears in LifeMap as a confirmed fact;
- abandoning confirmation does not create a durable health fact;
- corrections create an audit delta without storing hidden model reasoning.

### 5.8 P1-WP4 — Episode MVP

Minimum fields:

- title in consumer language;
- reason/goal;
- start date;
- status;
- linked event IDs;
- current summary;
- open questions;
- accepted tasks;
- last meaningful update;
- safety state.

Capabilities:

- create manually from a confirmed event;
- link/unlink events;
- add a check-in;
- accept/dismiss/complete a task;
- resolve, pause or hand off;
- view episode history;
- ask a contextual question.

Automatic episode creation is prohibited in Phase 1. The system may suggest a link,
but the user confirms it.

### 5.9 P1-WP5 — Contextual Chat

Chat launched from an Episode receives an episode-scoped context bundle:

- confirmed and reported linked events;
- current tasks;
- recent Episode changes;
- relevant medication list;
- user language and explanation level;
- consented PHR facts;
- explicit exclusions and stale-data markers.

Chat must:

- identify whether it is answering, clarifying, explaining or planning;
- perform emergency pre-check;
- ask at most one high-value question at a time by default;
- produce an actionable next step;
- cite evidence for medical claims where evidence retrieval is invoked;
- write nothing into LifeMap until confirmation;
- store any released action in the Decision Ledger.

### 5.10 P1-WP6 — Today projection

Today is a deterministic projection over durable state. An LLM may simplify card
copy but may not choose card priority.

Projection input:

- active Episodes;
- accepted CareTasks;
- confirmation drafts;
- deterministic safety items;
- notification preferences and quiet hours.

Projection output:

```json
{
  "as_of": "2026-07-25T08:00:00Z",
  "cards": [
    {
      "card_id": "today_...",
      "type": "episode_check_in",
      "priority": 30,
      "title": "Cơn đau đầu hôm nay thế nào?",
      "action": {
        "kind": "open_episode_check_in",
        "target_id": "ep_..."
      },
      "reason_code": "CHECK_IN_DUE",
      "decision_id": "dec_..."
    }
  ]
}
```

### 5.11 Phase 1 API

```text
GET    /api/v1/today
POST   /api/v1/captures
GET    /api/v1/captures/{capture_id}
POST   /api/v1/captures/{capture_id}/confirm
POST   /api/v1/captures/{capture_id}/discard
GET    /api/v1/health-events
GET    /api/v1/health-events/{event_id}
POST   /api/v1/episodes
GET    /api/v1/episodes
GET    /api/v1/episodes/{episode_id}
POST   /api/v1/episodes/{episode_id}/events
DELETE /api/v1/episodes/{episode_id}/events/{event_id}
POST   /api/v1/episodes/{episode_id}/transitions
POST   /api/v1/episodes/{episode_id}/check-ins
POST   /api/v1/episodes/{episode_id}/chat
POST   /api/v1/care-tasks/{task_id}/transitions
POST   /api/v1/chat/{thread_id}/convert-to-episode
```

### 5.12 Phase 1 domain events

```text
CaptureReceived.v1
CaptureTranscribed.v1
CaptureDraftExtracted.v1
CaptureConfirmed.v1
HealthEventCreated.v1
EpisodeCreated.v1
EpisodeEventLinked.v1
EpisodeStateChanged.v1
EpisodeCheckInRecorded.v1
CareTaskProposed.v1
CareTaskAccepted.v1
CareTaskCompleted.v1
TodayProjectionInvalidated.v1
```

### 5.13 Phase 1 telemetry

Product:

- login-to-Today success;
- capture start → confirmed conversion;
- correction rate by field, language and input type;
- Episode created from capture;
- accepted task completion;
- repeated-question avoidance.

Safety:

- emergency sensitivity/specificity on release set;
- false reassurance;
- inference-as-fact violations;
- abandoned unsafe drafts;
- released action without Decision Ledger.

Reliability:

- Today P95;
- capture-to-draft P95;
- confirmation write error;
- outbox projection lag;
- ASR/LLM fallback and timeout.

Telemetry must not contain raw transcript, symptoms, medicine names or free text.

### 5.14 Phase 1 test matrix

Required E2E:

1. Vietnamese text symptom with correction and Episode creation.
2. English voice symptom with ASR correction.
3. Emergency phrase bypasses normal generation.
4. Ambiguous time remains uncertain.
5. User abandons draft; no confirmed event exists.
6. Duplicate confirmation retry creates one event.
7. Existing chat converts to Episode without promoting assistant text.
8. Today restores an accepted task after logout/login.
9. LLM down: confirmed LifeMap and deterministic Today still load.
10. Research load: Today, capture and Episode update remain functional.
11. Dark/light mode, mobile viewport and keyboard-only operation.
12. Cross-profile event URL is denied.

Human evaluation:

- at least the agreed Vietnamese consumer sample completes capture without
  coaching;
- users correctly identify fact versus CLARA interpretation;
- teach-back confirms understanding of the next step;
- urgent copy neither minimizes nor overstates risk.

### 5.15 Phase 1 rollout

1. Internal dogfood with synthetic/de-identified profiles.
2. Shadow extraction on consented capture; user sees manual entry only.
3. Canary Universal Capture confirmation.
4. Canary Today as optional landing.
5. Set Today as default for eligible users.
6. Keep server-side redirect back to legacy landing as rollback.

Rollback:

- disable `LIFEMAP_TODAY_ENABLED` and route login to the prior authenticated home;
- disable extraction while retaining manual confirmed capture;
- never delete already-confirmed events during rollback.

### 5.16 Phase 1 exit gate

- Scenario E2E 1–6 and 11–12 from the parent spec pass.
- No inference-as-fact critical defect in the release corpus.
- Emergency bypass meets Clinical Safety thresholds in Vietnamese and English.
- Consumer comprehension and task-completion thresholds pass.
- Today and Episode SLOs pass at expected peak load.
- Production canary shows no unexplained rise in support or safety escalation.

Exit evidence:

- usability report;
- clinical safety evaluation;
- E2E run and screenshots/video;
- canary metrics;
- rollback rehearsal.

## 6. Phase 2 — Medicine Guardian, personal baselines and Health Replay

### 6.1 Outcome

CLARA helps the user understand how medicines and health changes relate over time.
It can say what changed compared with the person's own prior measurements, show the
source of a DDI conclusion, and replay why a health item was surfaced.

### 6.2 Primary vertical slice

```text
User photographs/enters a medicine
 -> candidate ingredients are extracted
 -> user confirms exact product/ingredient/dose
 -> MedicationCourse is created
 -> DrugBank DDI check runs against active courses
 -> warning shows DrugBank provenance or unavailable state
 -> a later symptom is linked temporally, not causally asserted
 -> Health Replay shows the timeline and decision rationale
```

### 6.3 In scope

- MedicationCourse migration and reconciliation;
- text/photo medicine capture;
- ingredient and product normalization;
- DrugBank-only DDI conclusions;
- adherence and course changes;
- deterministic personal baselines;
- meaningful-change cards;
- next-best-question engine;
- Health Replay and Decision Ledger viewer;
- temporal relationship language with strict causal boundaries.

### 6.4 Out of scope

- prescribing;
- dose changes without clinician instruction;
- causal claims from temporal association;
- pharmacogenomic recommendations;
- individualized treatment-effect prediction.

### 6.5 P2-WP1 — MedicationCourse model

MedicationCourse captures:

- normalized active ingredient(s);
- display product and local alias;
- DrugBank identifier when resolved;
- strength, form, route, schedule;
- start/stop and status;
- indication as reported;
- prescriber/source;
- adherence observations;
- changes with reason and actor;
- reconciliation state.

Statuses:

```text
candidate -> reconciled -> active -> paused -> stopped
candidate/reconciled -> rejected
```

Migration:

- every existing MedicineItem becomes a reconciliation candidate;
- no candidate participates in DDI until identity is sufficiently resolved;
- users can merge duplicate candidates;
- original cabinet row and source remain traceable;
- migration reports resolved, ambiguous, rejected and unchanged counts.

### 6.6 P2-WP2 — Medicine capture and reconciliation

Photo path:

```text
image
 -> malware/type/size validation
 -> OCR
 -> package text extraction
 -> candidate product/ingredient lookup
 -> ranked alternatives
 -> user confirmation
 -> MedicationCourse
```

The LLM can interpret noisy OCR and map context, but it cannot invent a DrugBank ID.
Exact identifier resolution must be backed by the parsed DrugBank dataset and
curated alias mapping.

Required UX:

- front/back package photo guidance;
- editable strength/form/schedule;
- “I cannot find this medicine” path;
- visible unresolved status;
- duplicate warning;
- simple Vietnamese explanation of active ingredient versus brand name.

### 6.7 P2-WP3 — DrugBank DDI authority

Rules:

1. Every positive or negative DDI conclusion records DrugBank dataset version,
   participating DrugBank IDs, interaction record/reference and checked-at time.
2. Local rules, an LLM or web retrieval may not substitute for a DrugBank
   conclusion.
3. If DrugBank is unavailable, stale beyond policy or medicines are unresolved,
   return `unable_to_verify`, not “no interaction”.
4. The LLM may simplify the DrugBank description but must preserve severity,
   mechanism/management qualifiers and uncertainty.
5. Any conflict between generated copy and the structured result blocks release.

Structured result:

```json
{
  "status": "interaction_found",
  "pairs": [
    {
      "drugbank_ids": ["DB00001", "DB00002"],
      "severity": "major",
      "effect_summary": "...",
      "management_summary": "...",
      "source": {
        "name": "DrugBank",
        "dataset_version": "...",
        "interaction_id": "..."
      }
    }
  ],
  "checked_at": "2026-07-25T08:00:00Z"
}
```

### 6.8 P2-WP4 — Personal baseline engine

Eligible signals:

- repeated measurements with compatible units and method;
- symptom frequency/severity using stable confirmed scales;
- adherence patterns;
- selected task completion intervals.

Baseline calculation:

- deterministic and versioned;
- minimum observation count and time span per signal;
- robust statistics appropriate to distribution;
- explicit exclusion of known invalid/disputed readings;
- unit normalization with recorded conversion;
- recalculation on confirmation, correction or supersession;
- no population “normal” is presented as personal baseline.

Every meaningful-change result includes:

- observation window;
- baseline window;
- value and normalized unit;
- absolute and relative change;
- data sufficiency;
- quality exclusions;
- rule version;
- clinical significance status: unknown unless supported by a separate authority.

### 6.9 P2-WP5 — Next-best-question engine

Objective: ask the smallest number of questions that could materially change safety
or the next step.

Inputs:

- Episode goal;
- known/unknown critical fields;
- user burden budget;
- recent questions;
- medicine changes;
- safety hypotheses;
- answer impact model.

Process:

1. Generate candidate questions from typed missing information.
2. Estimate whether each possible answer changes safety/action disposition.
3. Remove questions already answered or outside consent.
4. Apply burden and readability constraints.
5. Ask the highest-value question, or ask none.

Hard rules:

- never delay an emergency response to ask a question;
- do not repeatedly ask a dismissed question without new reason;
- do not ask sensitive questions without explaining why;
- generated questions pass safety and consumer-language validation.

### 6.10 P2-WP6 — Health Replay

Replay is a user-readable reconstruction, not a model transcript.

Views:

- event timeline;
- “what changed” comparison;
- “why CLARA showed this”;
- medicine course changes;
- task and outcome history;
- corrections and superseded facts;
- evidence/DrugBank provenance.

The user can inspect each card's triggering facts and mark them wrong. A disputed
fact invalidates affected projections and schedules recomputation.

### 6.11 Phase 2 API

```text
GET    /api/v1/medication-courses
POST   /api/v1/medication-courses
POST   /api/v1/medication-courses/reconcile
POST   /api/v1/medication-courses/{id}/transitions
POST   /api/v1/medicine-captures
GET    /api/v1/medicine-captures/{id}/candidates
POST   /api/v1/medicine-captures/{id}/confirm
POST   /api/v1/medication-safety/check
GET    /api/v1/baselines
GET    /api/v1/baselines/{signal_key}
GET    /api/v1/episodes/{id}/replay
GET    /api/v1/decisions/{decision_id}
POST   /api/v1/decisions/{decision_id}/dispute
```

### 6.12 Phase 2 test matrix

- full parsed DrugBank pair fixture suite, including positive, negative,
  unresolved and unavailable states;
- generated explanation equivalence to structured DDI result;
- cabinet migration with duplicates and ambiguous brands;
- OCR/photo correction;
- unit conversion and incompatible-unit rejection;
- baseline golden reference parity;
- baseline recomputation after correction;
- temporal-order perturbation;
- no causal wording for correlation-only cases;
- next-best-question outcome-impact evaluation;
- Decision Ledger replay after model/version changes;
- accessibility of complex medicine warnings.

### 6.13 Phase 2 rollout

1. Run cabinet migration in report-only mode.
2. Open reconciliation to internal users.
3. Enable MedicationCourse reads, then writes.
4. Run DDI in shadow against active reconciled courses.
5. Enable provenance UI and warnings.
6. Run baselines in shadow for clinician review.
7. Enable low-risk descriptive changes.
8. Enable Health Replay.

Rollback:

- retain course records and disable projections/warnings independently;
- fall back to explicit `unable_to_verify` if DrugBank path is unhealthy;
- disable meaningful-change cards without hiding raw confirmed observations.

### 6.14 Phase 2 exit gate

- Every DDI conclusion is traceable to DrugBank; zero local-rule substitutions.
- `unable_to_verify` paths pass outage and unresolved-identity tests.
- Medication reconciliation accuracy and user correction targets pass.
- Baseline implementation matches the independent reference suite.
- Clinical reviewers approve temporal language and no-causality boundary.
- Replay reconstructs every released card from durable records and versioned logic.

Exit evidence:

- DrugBank provenance audit;
- migration reconciliation report;
- baseline validation report;
- temporal safety review;
- Medicine Guardian usability report.

## 7. Phase 3 — CLARA Visit

### 7.1 Outcome

The user arrives at a real appointment better prepared and leaves with confirmed,
understandable next steps. CLARA supports the visit loop without impersonating the
clinician or presenting an unsigned machine draft as medical instruction.

### 7.2 Primary vertical slice

```text
User creates an upcoming visit
 -> chooses concerns and Episode(s)
 -> answers a short adaptive intake
 -> reviews and approves Visit Pack
 -> shares/exports it
 -> optionally consents to Scribe
 -> draft note is produced
 -> clinician signs or user labels external document correctly
 -> user confirms extracted plan/tasks
 -> Today follows up on accepted tasks
```

### 7.3 In scope

- visit object and purpose;
- adaptive pre-visit intake;
- user-approved Visit Pack;
- time-limited share/export;
- consented Scribe linkage;
- draft/signed/addendum status;
- post-visit plan extraction and confirmation;
- visit-linked tasks and Episode updates;
- deletion and withdrawal workflow.

### 7.4 Out of scope

- replacing the clinician's EHR;
- automatic orders/prescriptions;
- automatic billing submission;
- presenting CLARA-generated differential diagnosis as clinician-authored;
- ambient recording without active consent.

### 7.5 P3-WP1 — Visit domain

Minimum model:

```text
Visit
VisitConcern
VisitPackVersion
VisitConsent
VisitShare
VisitDocument
VisitPlanDraft
VisitEpisodeLink
```

Visit states:

```text
planning -> ready -> in_progress -> awaiting_review -> completed
planning/ready -> cancelled
```

Visit Pack is immutable once shared. Edits create a new version and old share links
continue to reference only the version authorized at creation.

### 7.6 P3-WP2 — Adaptive intake

Inputs:

- selected Episode(s);
- medicines/allergies explicitly approved for the visit;
- recent meaningful changes;
- visit type and user's main goal;
- missing information likely to improve the appointment.

Output:

- one question at a time;
- visible progress based on value, not an arbitrary long form;
- skip and “I don't know” paths;
- reason for sensitive questions;
- final user review.

The intake stops when remaining questions are low-value or burden budget is reached.

### 7.7 P3-WP3 — Visit Pack

Sections:

1. What the user wants help with.
2. Episode timeline and meaningful changes.
3. Current reconciled medicines and allergies.
4. Questions the user wants to ask.
5. Measurements/documents the user selected.
6. Safety items that require review.
7. Provenance and last-updated indicators.

Rules:

- the user explicitly selects the data included;
- inferred content is labeled and excluded by default;
- no hidden profile data enters the export;
- generated summary links back to its source events;
- pack is available as accessible web view and PDF;
- share is time-limited, revocable and audited.

### 7.8 P3-WP4 — Scribe linkage

Before recording:

- show purpose, data flow, retention and participants;
- capture affirmative, visit-specific consent;
- provide visible recording state and stop control;
- re-check consent before upload/provider processing.

After recording:

- transcript and note have draft status;
- claims are grounded to transcript spans where possible;
- clinician signature state is separate from user confirmation;
- addenda never mutate a signed version;
- deletion follows consent and legal retention policy.

### 7.9 P3-WP5 — Post-visit closed loop

CLARA may extract candidate:

- medication changes;
- tests/referrals;
- follow-up timing;
- home monitoring;
- return precautions;
- questions left unresolved.

Before becoming active:

- show source document/span;
- distinguish clinician instruction from model interpretation;
- resolve conflicts with existing medication courses;
- require user confirmation or authorized clinician signature;
- create proposed CareTasks, not completed tasks;
- update linked Episode only after confirmation.

### 7.10 Phase 3 API

```text
POST   /api/v1/visits
GET    /api/v1/visits
GET    /api/v1/visits/{id}
POST   /api/v1/visits/{id}/concerns
POST   /api/v1/visits/{id}/intake/answers
POST   /api/v1/visits/{id}/pack
POST   /api/v1/visit-packs/{id}/approve
POST   /api/v1/visit-packs/{id}/shares
DELETE /api/v1/visit-packs/{id}/shares/{share_id}
POST   /api/v1/visits/{id}/scribe-consents
POST   /api/v1/visits/{id}/documents
POST   /api/v1/visits/{id}/plan/extract
POST   /api/v1/visits/{id}/plan/confirm
```

### 7.11 Phase 3 test matrix

- Visit Pack contains only explicitly selected data;
- Pack version does not change after share;
- revocation blocks an already-open share on next authorization check;
- Scribe cannot start without valid visit consent;
- stop/revoke interrupts processing;
- unsigned draft labeling across all views/exports;
- signed-note immutability and addendum behavior;
- post-visit extraction grounding;
- medication conflict confirmation;
- deletion and retention policy E2E;
- screen reader and print/PDF accessibility;
- low-bandwidth upload resume without duplicated note.

### 7.12 Phase 3 rollout

1. Internal Visit Pack without sharing.
2. Time-limited sharing canary.
3. Scribe linkage for controlled eligible visits.
4. Post-visit extraction in shadow.
5. User confirmation and task creation.
6. Broader rollout after usefulness and consent comprehension study.

### 7.13 Phase 3 exit gate

- Consent, withdrawal, revocation and deletion E2E pass.
- No unsigned content is presented as clinician-approved.
- Visit Pack selective-disclosure suite has zero leakage.
- Target users can prepare and share a useful pack without assistance.
- Post-visit users correctly distinguish instruction, extraction and inference.
- Follow-up tasks persist and close the Episode loop.

Exit evidence:

- consent-comprehension study;
- Visit Pack usefulness study;
- signed/draft safety audit;
- deletion drill;
- controlled rollout report.

## 8. Phase 4 — Family Circle

### 8.1 Outcome

A user can safely coordinate care with a trusted person without sharing an entire
account or exposing unrelated health history.

### 8.2 Primary vertical slice

```text
Profile owner invites caregiver
 -> selects one Episode and task permission
 -> caregiver accepts
 -> caregiver records a clearly attributed observation
 -> owner sees it as caregiver-reported
 -> caregiver completes an allowed task
 -> owner revokes access
 -> caregiver immediately loses access
 -> access log records the sequence
```

### 8.3 In scope

- dependent/caregiver profile relationships;
- granular object/action/purpose grants;
- profile switcher;
- caregiver-reported observations;
- delegated CareTask actions;
- scoped notifications;
- access log;
- immediate revoke;
- break-glass policy only if separately approved.

### 8.4 Out of scope

- shared passwords;
- implicit access to the whole LifeMap;
- caregiver confirmation of owner-reported facts without authority;
- legal guardianship determination by CLARA;
- invisible monitoring.

### 8.5 P4-WP1 — Grant model

A grant must include:

- grantor and grantee;
- target profile;
- object scope: Episode, medicine list, visit or task;
- allowed actions: view, add observation, complete task, share;
- purpose;
- start and expiry;
- grant version;
- status and revoke reason;
- legal/guardian basis when applicable.

Default:

- least privilege;
- short-lived invitation;
- no onward sharing;
- no access to raw chat or unrelated events;
- no ability to alter ownership or consent.

### 8.6 P4-WP2 — Profile switcher

The UI must make the active profile unmistakable:

- name/avatar and relationship in the header;
- distinct but accessible contextual accent;
- confirmation before sensitive writes after switching;
- no cached cards from the previous profile;
- return to own profile on logout/new device unless explicitly chosen.

### 8.7 P4-WP3 — Attributed collaboration

Caregiver contributions use `reported` state and include actor attribution. The
profile owner can:

- confirm;
- dispute;
- unlink from an Episode;
- restrict future contribution;
- view who saw or changed an item.

Conflicting observations remain separate records; the system does not silently
merge them.

### 8.8 P4-WP4 — Notifications

Notifications are derived from grants and task scope:

- content minimized on lock screens;
- no diagnosis/medicine name unless opted in;
- quiet hours and urgency policy;
- owner can see why the caregiver was notified;
- revocation cancels unsent notifications;
- delivery never proves that a caregiver acted.

### 8.9 P4-WP5 — Access log and revocation

The user-facing access log includes:

- who;
- which profile/object;
- action type;
- time;
- grant/purpose;
- success/denied;
- approximate device/session information where safe.

Revocation:

- increments grant version;
- writes authoritative deny;
- terminates related sessions/streams;
- invalidates shares and queued work;
- purges caches;
- records audit event;
- never deletes the historical access log.

### 8.10 Phase 4 API

```text
POST   /api/v1/family/invitations
POST   /api/v1/family/invitations/{token}/accept
GET    /api/v1/family/relationships
POST   /api/v1/access-grants
GET    /api/v1/access-grants
DELETE /api/v1/access-grants/{id}
GET    /api/v1/access-log
POST   /api/v1/profiles/{id}/caregiver-observations
POST   /api/v1/care-tasks/{id}/delegations
```

### 8.11 Phase 4 security test matrix

Required adversarial tests:

- enumerate IDs across profiles;
- reuse expired invitation;
- accept invitation as wrong account;
- widen object/action scope in request body;
- use stale access token after revoke;
- read cached Today after switching profile;
- receive notification after revoke;
- background job continues with stale grant;
- caregiver edits owner-authored observation;
- onward-share without permission;
- concurrent revoke and write;
- account recovery used to seize dependent profile.

Zero-tolerance result: no cross-profile data exposure.

### 8.12 Phase 4 rollout

1. Internal adult-to-adult Episode view-only sharing.
2. Add attributed caregiver observations.
3. Add task delegation.
4. Add dependent profiles only after jurisdiction/legal review.
5. Expand notification scope last.

Each capability has an independent flag and kill switch.

### 8.13 Phase 4 exit gate

- Object-level authorization and isolation suites have zero failures.
- Revocation SLO passes for API, streams, caches, shares, jobs and notifications.
- Threat model and privacy impact assessment are approved.
- Users understand exactly what they are sharing in usability testing.
- Access log is complete, readable and itself access-controlled.
- Support and recovery procedures handle invitation abuse and mistaken grants.

Exit evidence:

- penetration/authorization report;
- privacy impact assessment;
- revocation drill;
- sharing-comprehension study;
- incident runbook.

## 9. Phase 5 — Living evidence and validated personalization

### 9.1 Outcome

CLARA can explain when relevant medical evidence has changed, how it may or may not
apply to a user's confirmed context, and which questions or next steps are worth
discussing—without overstating certainty or claiming individualized treatment
effects.

### 9.2 Primary vertical slice

```text
Episode has a confirmed question
 -> evidence query is compiled
 -> guideline + primary study + review sources are retrieved separately
 -> evidence is normalized with PMID/DOI/NCT/design
 -> applicability constraints are compared with confirmed user context
 -> contradictions and uncertainty are surfaced
 -> consumer summary proposes a discussion/action
 -> evidence version and decision are recorded
 -> later material evidence change triggers a reviewable update
```

### 9.3 In scope

- episode-linked evidence questions;
- source-class-separated retrieval;
- guideline artifact registry;
- executable eligibility/recommendation logic where licensed and validated;
- trial applicability;
- contradiction detection;
- evidence freshness/change detection;
- calibrated consumer explanation;
- prospective validation;
- controlled claims and model release governance.

### 9.4 Out of scope

- autonomous diagnosis or prescribing;
- claims that a recommendation will improve an individual's outcome;
- replacing clinician judgment;
- silent use of unverified web summaries;
- using editorial content as equivalent to primary evidence.

### 9.5 P5-WP1 — Evidence question compiler

Compile a consumer concern into:

- population/context;
- intervention/exposure where relevant;
- comparator;
- outcomes;
- time horizon;
- study-design needs;
- guideline jurisdiction/date;
- exclusions;
- episode facts allowed for applicability.

The user sees the plain-language question and can correct it before deep Research
when correction could materially change retrieval.

### 9.6 P5-WP2 — Source-class-separated retrieval

Retrieve and label independently:

- clinical guidelines/consensus;
- primary randomized trials;
- other primary observational/diagnostic/prognostic studies;
- systematic reviews/meta-analyses;
- editorials/commentary.

Preferred primary registries:

- PubMed;
- Europe PMC;
- ClinicalTrials.gov where trial registration is relevant.

Every evidence record stores, when available:

- title;
- authors;
- publication date;
- source class and study design;
- PMID;
- DOI;
- NCT;
- journal/source;
- abstract/full-text availability;
- retrieval query and time;
- retraction/correction status;
- parsed population/intervention/outcome;
- limitations;
- licensing/usage metadata.

Editorials cannot satisfy a primary-evidence requirement.

### 9.7 P5-WP3 — Executable guideline artifacts

Represent guideline logic as versioned knowledge artifacts aligned where practical
with FHIR PlanDefinition/Library concepts:

- source guideline and exact section;
- jurisdiction and intended population;
- publication/review dates;
- eligibility conditions;
- exclusions;
- action options;
- strength/certainty;
- variables required;
- human-readable rationale;
- executable expression;
- tests and approver.

Generated conversions remain draft until dual clinical review and test-vector
approval.

### 9.8 P5-WP4 — Applicability engine

The engine compares study/guideline eligibility with confirmed context:

```text
matches
unknowns
mismatches
critical exclusions
freshness
```

Rules:

- missing context is `unknown`, not assumed;
- inferred traits do not satisfy a critical inclusion/exclusion criterion;
- applicability is distinct from efficacy;
- no single similarity score is shown without components;
- sensitive traits are used only with appropriate consent and necessity.

### 9.9 P5-WP5 — Contradiction and uncertainty

Contradiction detection operates on structured claims:

- same clinical question and outcome;
- compatible population/time horizon;
- direction and magnitude;
- source class;
- risk of bias/certainty;
- publication freshness.

Output separates:

- genuine conflicting findings;
- different populations;
- different outcomes/time horizons;
- older versus updated guidance;
- insufficient evidence.

Uncertainty dimensions:

- evidence certainty;
- applicability certainty;
- data freshness;
- extraction/retrieval confidence;
- model disagreement;
- missing critical personal context.

If uncertainty changes the safe next step, CLARA asks a question, defers, or
abstains.

### 9.10 P5-WP6 — Consumer renderer

Default response order:

1. What this may mean for you.
2. What is known from your confirmed information.
3. What remains uncertain.
4. The next safe action or discussion.
5. Why CLARA says this.
6. Optional evidence detail.

Doctor/researcher expansions expose:

- clinical reasoning;
- evidence matrix;
- study design;
- identifiers and provenance;
- contradictions;
- applicability table;
- reproducible query/version.

The default consumer view must remain readable without medical or statistical
training.

### 9.11 P5-WP7 — Living evidence updates

An update is eligible for notification only if:

- the source is verified and relevant to an active/monitored Episode;
- it materially changes prior certainty, safety or the next action;
- the prior and new evidence versions are recorded;
- the notification passes burden and safety rules.

No notification is sent for publication volume alone.

### 9.12 P5-WP8 — Release adjudication

Compare:

- strong single-agent baseline;
- proposed multi-agent pipeline;
- deterministic-only fallback where applicable.

Multi-agent output is released only when it improves predefined safety and quality
metrics without unacceptable latency, cost or variance. Otherwise it stays in
shadow.

Required metrics:

- harmful-action rate;
- unsupported-claim rate;
- citation entailment;
- source-class correctness;
- contradiction recall/precision;
- applicability correctness;
- calibration;
- consumer comprehension;
- latency and cost per safely completed Episode step.

### 9.13 Phase 5 API

```text
POST   /api/v1/episodes/{id}/evidence-questions
GET    /api/v1/evidence-questions/{id}
POST   /api/v1/evidence-questions/{id}/run
GET    /api/v1/evidence-runs/{id}
GET    /api/v1/evidence-runs/{id}/matrix
GET    /api/v1/evidence-runs/{id}/applicability
GET    /api/v1/evidence-runs/{id}/contradictions
POST   /api/v1/evidence-runs/{id}/subscribe
DELETE /api/v1/evidence-subscriptions/{id}
GET    /api/v1/guideline-artifacts/{id}
```

### 9.14 Phase 5 evaluation program

Offline suites:

- MedQA-style knowledge is diagnostic only, not sufficient;
- longitudinal Episode reasoning;
- temporal perturbation;
- evidence retrieval recall;
- citation entailment;
- study-design classification;
- retraction/correction handling;
- contradiction classification;
- applicability with missing variables;
- Vietnamese consumer comprehension;
- safe abstention and escalation.

Human review:

- independent clinician review;
- information-specialist review of retrieval/provenance;
- consumer teach-back;
- subgroup and language error analysis;
- blinded baseline comparison.

Prospective validation:

- begin with silent/shadow deployment;
- pre-register endpoints and failure thresholds;
- measure false-alarm and burden;
- stop on safety boundary breach;
- obtain applicable ethics, privacy and regulatory approvals;
- publish limitations with any performance claim.

### 9.15 Phase 5 rollout

1. Evidence pipeline offline evaluation.
2. Shadow on consented Episode questions.
3. Researcher/clinician-only evidence matrix.
4. Consumer explanation canary with review sampling.
5. Living-update subscription opt-in.
6. Prospective validation.
7. Claims expansion only after evidence and approval.

### 9.16 Phase 5 exit gate

- Source class, PMID/DOI/NCT and study design provenance meet target completeness.
- Citation entailment and unsupported-claim thresholds pass.
- Contradiction and applicability evaluations pass independent review.
- Consumer users correctly understand uncertainty and next action.
- Multi-agent pipeline beats the strong baseline on predeclared primary metrics or
  remains shadow-only.
- Prospective validation and required governance approve any expanded claim.

Exit evidence:

- model/evidence system card;
- blinded benchmark report;
- retrieval provenance audit;
- calibration report;
- consumer comprehension report;
- prospective protocol/results and claim register.

## 10. Cross-phase dependency matrix

| Capability | P0 | P1 | P2 | P3 | P4 | P5 |
|---|---:|---:|---:|---:|---:|---:|
| Profile boundary | Build | Use | Use | Use | Extend | Use |
| Truth/provenance | Build | Confirm capture | Medicine/source | Visit documents | Attribution | Evidence/applicability |
| Episode | Foundation | MVP | Temporal enrichment | Visit linkage | Shared scope | Evidence linkage |
| Decision Ledger | Foundation | Actions/Today | DDI/change/replay | Visit plan | Delegated actions | Evidence decisions |
| Revocation | Build | Sessions | Use | Shares/consent | Grants | Subscriptions |
| Outbox | Build | Today/tasks | Baseline/DDI | Visit workflow | Notifications | Evidence updates |
| DrugBank | Adapter | Existing safety | Full authority path | Reconciliation | Scoped view | Context only |
| Scribe | Adapter | No change | No change | Integrate | Scoped sharing | Evidence context only |
| Research/RAG | Isolate | Contextual use | Evidence for explanation | Visit questions | Scoped use | Full living evidence |

## 11. Feature-flag and rollback matrix

| Phase | Primary flags | Safe rollback behavior |
|---|---|---|
| P0 | infrastructure/config flags | retain schema; disable new writers/adapters |
| P1 | `LIFEMAP_TODAY`, `CAPTURE`, `EPISODES` | prior landing; manual records remain readable |
| P2 | `MEDICINE_GUARDIAN`, `BASELINES`, `REPLAY` | show confirmed raw data; DDI becomes unable-to-verify |
| P3 | `LIFEMAP_VISIT`, Scribe linkage subflags | preserve packs/notes; disable new workflows/shares |
| P4 | `FAMILY_CIRCLE`, notification subflags | revoke/deny remains available even if feature disabled |
| P5 | evidence/artifact/update flags | hide new generated advice; retain provenance and subscriptions off |

Safety controls, revoke endpoints and access to confirmed records are never placed
behind a kill switch that can make them unavailable.

## 12. Program-level quality gates

Every phase must pass:

### 12.1 Functional

- all named vertical slices pass against deployed staging;
- refresh and new login restore durable state;
- no production path depends on demo/mock data;
- empty, loading, error, retry and degraded states are covered.

### 12.2 Safety

- hazard log updated;
- emergency path regression passes;
- no unconfirmed inference is rendered as fact;
- safe abstention works when authority or context is missing;
- Clinical Safety signs the phase release.

### 12.3 Security/privacy

- authorization test matrix passes;
- consent and revocation checks cover background work;
- logs/metrics contain no raw health text;
- deletion/export impact is documented and tested;
- threat model delta is approved.

### 12.4 Reliability

- defined P50/P95/SLO targets pass at expected load;
- provider outage and partial dependency failure are exercised;
- queues are bounded and observable;
- rollback and forward-fix procedures are rehearsed.

### 12.5 UX/accessibility

- Vietnamese consumer task testing passes;
- mobile, keyboard, screen reader, zoom and theme coverage passes;
- copy avoids false certainty and unexplained medical jargon;
- users understand what is saved, inferred, shared and actionable.

## 13. Phase planning template

Before coding a phase, its delivery lead creates a signed phase brief containing:

```text
Phase:
Directly responsible owner:
Clinical Safety approver:
Security/Privacy approver:
Target cohort:
Vertical slice:
Included work packages:
Excluded work:
Schema migrations:
API version changes:
Model/rule versions:
Data migration/backfill:
Primary success metric:
Safety guardrail metrics:
SLOs:
Rollout stages:
Rollback trigger:
Exit evidence location:
Open risks:
```

Open high-severity risks block rollout; they cannot be accepted solely by Product or
Engineering.

## 14. Definition of program completion

The LifeMap program is complete only when all phase gates pass and:

1. login defaults to Today for eligible consumer users;
2. Capture, Episodes, tasks and Replay work across sessions with durable real data;
3. Medicine Guardian derives DDI conclusions exclusively from DrugBank;
4. Visit and Family flows enforce consent, provenance and object-level scope;
5. evidence updates are reviewable and calibrated;
6. Chat is a contextual interface, not the system of record;
7. confirmed records remain available during ML/retrieval outages;
8. every surfaced action is reproducible from a Decision Ledger;
9. deletion, export and revocation work across all new data;
10. no released multi-agent path underperforms the approved strong baseline on the
    predeclared safety/quality gate.
