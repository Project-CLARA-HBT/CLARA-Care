# Requirements — CLARA LifeMap Production Convergence

Status: proposed implementation specification
Date: 2026-07-28
Owners: Product, Clinical Safety, API, ML, Web, Mobile, Security
Companion documents: [design.md](design.md), [tasks.md](tasks.md),
[ai-capability-analysis.md](ai-capability-analysis.md)

## 1. Purpose

LifeMap is CLARA's longitudinal, user-controlled health memory and care-loop
layer. It turns confirmed observations, medication courses, visit information,
goals, and user-accepted tasks into a coherent view of:

- what the person is tracking;
- what changed and why CLARA believes it changed;
- what is still uncertain or awaiting confirmation;
- what the person chose to do next; and
- what may be shared, with whom, for what purpose, and for how long.

This specification converges the existing LifeMap implementation with the
product vision in:

- `docs/design/clara-lifemap-consumer-health-platform-spec-2026-07-25.md`; and
- `docs/design/clara-lifemap-phase-execution-spec-2026-07-25.md`.

It does not create a second LifeMap. It defines the missing production contracts,
migrations, release gates, and retirement work needed to make the current system
safe, durable, interoperable, and complete.

## 2. Product position and intended use

LifeMap is a personal organization, reflection, and care-preparation product. It
is not an electronic health record, a diagnostic system, a prescriber, or an
autonomous clinical decision-maker. It may summarize and explain evidence, flag
possible medication-safety concerns, and help a user prepare questions, but it
must not diagnose, prescribe, select a personal dose, or imply causation from a
correlation.

The initial intended users are:

1. Vietnamese consumers managing their own health information;
2. explicitly authorized family caregivers operating within a narrow grant;
3. clinicians receiving a user-approved, purpose-bound summary; and
4. CLARA operators performing audited support and safety review.

Any future regulated clinical use requires a separate intended-use assessment,
clinical evaluation, quality-management decision, and jurisdiction review. The
January 2026 FDA CDS guidance explicitly distinguishes qualifying
professional-facing non-device CDS from patient/caregiver software; LifeMap must
not assume that a consumer disclaimer alone resolves classification.

## 3. Current-state baseline

The following are implementation facts as of 2026-07-28 and define the starting
point for this plan:

| Area | Present | Production gap |
| --- | --- | --- |
| Events, episodes, tasks, Today | API, web, and mobile basics | Caller can create an event as `confirmed`; truth transitions and source lineage are not enforced |
| Profile ownership | One `PhrProfile` resolved from the user | No explicit active `ProfileScope`; public sequential IDs remain observable |
| Outbox | Table and optional in-process relay | Disabled by default; no lease, heartbeat, retry schedule, dead-letter queue, or worker isolation |
| Baselines | Median over recent wearable aggregates | No unit normalization, eligibility/exclusion rules, dispersion, recomputation lineage, or meaningful-change contract |
| Next-best question | Flagged endpoint and typed catalogue | No complete consent, burden-budget, dismissal, or answer-to-event workflow |
| Replay and decision ledger | API primitives exist | No complete consumer UI, correction propagation, or downstream invalidation |
| Medication courses | Basic profile-scoped course | Missing normalized ingredient/form/route, reconciliation, adherence, and change history |
| Visits | Visit and pack scaffolding | Grounded instruction extraction deliberately returns `extraction_unavailable` |
| Family | Relationships, grants, notifications, access log | Client parity and purpose/time/data enforcement need completion |
| Living Evidence | Question, confirmation, run, subscription records | Applicability is `not_assessed`; no scheduler or material-change adjudication |
| Web/mobile | Main LifeMap/Today CRUD | No unified capture, baseline/change, replay/correction, or evidence feedback loop |
| AI/ML platform | DeepSeek, hybrid RAG, embeddings, GraphRAG seams, FIDES, OCR/ASR, evaluation harnesses | No LifeMap model registry, dataset/feature lineage, signed artifacts, OOD/drift pipeline, or governed training runtime |
| Council “neural” score | Shadow-only fixed-weight feed-forward calculation | Hand-authored constants, not a trained or clinically validated neural model; naming overstates maturity |

This baseline is descriptive, not an acceptance of current unsafe or incomplete
behavior.

## 4. Research and standards basis

The design uses the following authoritative sources as constraints:

- [WHO SMART Guidelines](https://www.who.int/teams/digital-health-and-innovation/smart-guidelines)
  and [Digital Adaptation Kits](https://www.who.int/publications/m/item/who-digital-accelerator-kits):
  workflows, core data needs, decision logic, indicators, and functional
  requirements should be explicit, machine-testable artifacts.
- [HL7 FHIR R4](https://hl7.org/fhir/R4/) resources for CarePlan, Goal, Task,
  Observation, QuestionnaireResponse, Provenance, Consent, AuditEvent, and
  DocumentReference.
- [HL7 International Patient Summary 2.0.1](https://www.hl7.org/fhir/uv/ips/en/):
  an R4-based, minimal, purpose-specific summary with strong provenance and
  terminology requirements. An IPS is informative and must not be executed as an
  order.
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) and its
  Generative AI Profile: govern, map, measure, and manage risks across the full
  lifecycle.
- [WHO ethics and governance of AI for health](https://www.who.int/publications/i/item/9789240029200)
  and the joint regulator
  [Good Machine Learning Practice principles](https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles):
  protect autonomy, evaluate the human-AI team, use representative data,
  communicate limitations, and monitor deployed models.
- [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378),
  [DECIDE-AI](https://www.nature.com/articles/s41591-022-01772-9), and
  [CONSORT-AI](https://www.nature.com/articles/s41591-020-1034-x):
  prediction models and live AI interventions require transparent development,
  error analysis, and prospective human-AI evaluation proportional to impact.
- [FDA Clinical Decision Support Software Guidance, January 2026](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software):
  intended use and the target user materially affect software-function analysis.
- [Vietnam Law 91/2025/QH15 on Personal Data Protection](https://vbpl.moj.gov.vn/phuyen/Pages/vbpq-vanbanlienquan.aspx?ItemID=179252&Keyword=),
  effective 2026-01-01, plus applicable implementing instruments.
- [EU AI Act, Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=en)
  as a forward-compatible governance reference where CLARA is offered in the EU.

Standards references are architectural guidance, not a claim of certification,
regulatory clearance, or legal compliance. Counsel and the clinical safety owner
must approve jurisdiction-specific release decisions.

## 5. Definitions

- **ProfileScope**: the explicit health profile on whose data an operation acts.
  It is distinct from the authenticated account.
- **Canonical event**: an append-only LifeMap fact or assertion with time,
  provenance, truth state, and revision lineage.
- **Draft**: machine- or user-extracted content that has not become a confirmed
  health fact.
- **Truth state**: `draft`, `user_reported`, `confirmed`, `disputed`,
  `superseded`, `invalidated`, or `entered_in_error`.
- **Episode**: a user-named, non-diagnostic journey that groups relevant events,
  goals, questions, decisions, and tasks.
- **Care task**: a proposed action that affects Today only after the user accepts
  it.
- **Projection**: a reproducible read model derived from canonical records.
- **Replay**: a chronological explanation of what changed, what source supports
  it, and which rules/models produced the interpretation.
- **Meaningful change**: a configured, statistically supported deviation from a
  personal baseline. It is not, by itself, a clinical abnormality.
- **Source span**: an immutable pointer to the exact document page, region, time
  range, or text offsets supporting an extracted candidate.
- **Material evidence change**: a reviewed evidence update that may change the
  wording, confidence, applicability, or action of an existing answer.

## 6. Functional requirements

### R1 — Scope, transparency, and user control

1. LifeMap SHALL describe itself as a personal health organization and
   care-preparation tool, not a diagnosis or treatment plan.
2. Every AI-generated interpretation SHALL identify that it is AI-assisted,
   distinguish source fact from inference, expose uncertainty, and offer a
   correction path.
3. The user SHALL be able to view why an item appears in LifeMap or Today.
4. LifeMap SHALL NOT create, accept, complete, share, or delete a care task on
   behalf of the user without the corresponding explicit action.
5. A feature whose validated source, policy, or model dependency is unavailable
   SHALL fail closed or show a sanitized unavailable state; it SHALL NOT invent
   content.

### R2 — ProfileScope and tenant isolation

1. Every health command and query SHALL resolve an explicit server-authorized
   `ProfileScope`.
2. Account identity SHALL NOT be treated as proof of access to every profile
   associated with that account.
3. Consumer self-access, caregiver access, clinician share access, and operator
   support access SHALL use distinct policies and audit purposes.
4. Public API identifiers SHALL be opaque UUIDv7, ULID, or equivalently
   non-enumerable values. Sequential database keys SHALL never leave the service.
5. Repository queries SHALL require `profile_id` in addition to object identity;
   cross-profile object references SHALL be rejected.
6. Tests SHALL prove non-interference between two profiles for every new command,
   query, export, share, and background job.

### R3 — Truth, revision, and provenance

1. Machine extraction SHALL only create `draft` candidates.
2. A client SHALL NOT set `confirmed` directly during generic event creation.
3. Truth changes SHALL occur through typed commands with an allowed-transition
   matrix, actor, reason, timestamp, policy version, and idempotency key.
4. Correction SHALL append a new revision and supersede the prior revision; it
   SHALL NOT silently overwrite source history.
5. Disputed and invalidated facts SHALL be excluded from active clinical
   projections while remaining visible in authorized audit/replay views.
6. Every canonical record SHALL contain source type, source identity, author or
   device, observed/effective time, recorded time, confidence where applicable,
   and a stable revision lineage.
7. Derived outputs SHALL record input revision IDs, rule-set version, model
   identity, prompt/template version where used, and generation time.

### R4 — Universal Capture

1. Capture SHALL accept typed text, guided form data, document/image input,
   supported wearable data, and an explicit import source.
2. Acute-symptom/emergency classification SHALL execute before non-emergency
   extraction or longitudinal reasoning. Emergency handling SHALL not wait for
   LifeMap persistence.
3. Capture SHALL create a review session containing source-linked candidate
   fields, confidence, missing critical fields, and a plain-language explanation.
4. The review UI SHALL let the user edit, reject, or confirm each safety-relevant
   candidate before it becomes canonical.
5. Low-confidence medication identity, dose, route, allergy, pregnancy, and
   emergency-relevant fields SHALL require explicit manual confirmation.
6. Duplicate detection SHALL suggest a match but SHALL NOT merge records
   automatically when identity is ambiguous.
7. Capture SHALL support abandon/resume and SHALL expire unconfirmed sensitive
   drafts under a configured retention policy.

### R5 — Episodes, goals, decisions, and tasks

1. An episode SHALL be user-created or user-confirmed and SHALL use a neutral
   title rather than an inferred diagnosis.
2. Events SHALL be linked to episodes through a many-to-many, revision-aware
   relation; the canonical event SHALL not be duplicated.
3. Goals SHALL be optional, user-owned, measurable when possible, and
   independently editable.
4. CLARA MAY propose a task, but only `accepted` tasks SHALL appear in Today.
5. Task state transitions SHALL be:
   `proposed -> accepted -> in_progress -> completed|cancelled|expired`, with
   explicit rejection from `proposed`.
6. Every transition SHALL be idempotent and append an action record.
7. Urgent presentation SHALL never imply a diagnosis and SHALL link to the
   safety disposition that produced it.

### R6 — Today

1. Today SHALL be a projection of accepted, due, non-superseded tasks plus
   pending confirmations and user-visible safety follow-ups.
2. Today SHALL be reproducible from canonical records and versioned projection
   rules.
3. Today SHALL never contain a machine-proposed but unaccepted action.
4. Completing a task SHALL not assert a clinical outcome; outcome capture, when
   offered, SHALL be a separate user-confirmed event.
5. Empty, loading, stale, offline, partial, and dependency-unavailable states
   SHALL be explicit.

### R7 — Personal baselines and meaningful change

1. Each supported signal SHALL have a versioned definition containing canonical
   units, valid ranges, minimum sample count, minimum time span, aggregation,
   exclusion rules, and eligible source classes.
2. Baselines SHALL use robust statistics (at minimum median and a dispersion
   measure such as MAD or quantiles), not a single unqualified average.
3. Unit conversion and timezone/day-boundary normalization SHALL occur before
   baseline computation.
4. Data recorded during configured exclusion windows (for example, obvious
   sensor invalidity or insufficient wear) SHALL not influence the baseline and
   SHALL retain the exclusion reason.
5. A meaningful-change signal SHALL include magnitude, duration, data
   sufficiency, confidence, comparison window, rule version, and caveats.
6. A signal SHALL be described as a personal-pattern change, never automatically
   as disease, deterioration, or treatment effect.
7. Corrections, deletions, source revocations, and late data SHALL trigger
   deterministic recomputation or invalidation.
8. Population reference ranges MAY be shown only as a separately sourced and
   labeled layer; they SHALL NOT be conflated with personal baselines.

### R8 — Next-best question

1. The engine SHALL choose only from a versioned, clinician-reviewed question
   catalogue with explicit purpose, episode class, answer schema, sensitivity,
   and impact weight.
2. It SHALL ask at most one question at a time and SHALL respect a configurable
   burden budget, cooldown, prior dismissal, and do-not-ask preference.
3. It SHALL ask only when the answer can change a safety disposition, projection,
   explanation, or next action.
4. Sensitive questions SHALL require the applicable consent and a
   plain-language rationale before collection.
5. The answer SHALL enter the capture/truth workflow; it SHALL NOT become a
   confirmed fact merely because the form was submitted.
6. Emergency handling SHALL always outrank information-gain optimization.
7. The first production release SHALL be deterministic and rule-based. Learned
   ranking requires a separately approved evaluation and rollback plan.

### R9 — Medication Guardian convergence

1. A medication course SHALL support normalized ingredient, product text, form,
   route, schedule text, start/end or ongoing state, indication as user-reported,
   source, prescriber where known, and reconciliation status.
2. Original label text and normalized coding SHALL both be retained.
3. Medication edits SHALL append reconciliation/change records.
4. OCR and document extraction SHALL remain drafts until identity and critical
   fields are confirmed.
5. DDI/dose/contraindication claims classified `CRITICAL` SHALL pass FIDES
   verification or be blocked.
6. LifeMap SHALL not recommend starting, stopping, substituting, or changing the
   dose of a medication.
7. Adherence tracking SHALL be opt-in and SHALL distinguish “recorded as taken”
   from inferred adherence.

### R10 — Replay, correction, and dispute

1. Replay SHALL show events, source provenance, decisions, accepted actions, and
   corrections in chronological order.
2. Derived interpretations SHALL expose their input facts and rule/model version
   in a consumer-safe explanation.
3. Correcting or invalidating an input SHALL mark affected projections,
   baselines, questions, Visit Packs, and evidence applicability as stale until
   recomputed.
4. A user SHALL be able to dispute a decision or interpretation without deleting
   the underlying source.
5. Dispute resolution SHALL append a resolution record and preserve both views.
6. Replay exports SHALL honor the same consent, profile, purpose, and redaction
   rules as the live UI.

### R11 — Visit closed loop

1. A visit SHALL support preparation, concerns, questionnaire answers, documents,
   extraction review, confirmed instructions, follow-up tasks, and a Visit Pack.
2. Every extracted instruction SHALL contain an exact source span and confidence.
3. Without a source span, the instruction SHALL remain unavailable and SHALL not
   create a task.
4. The user SHALL approve a Visit Pack before sharing it.
5. An IPS-like summary SHALL be informative; receiving systems SHALL not execute
   it as an order.
6. Expired, revoked, corrected, or superseded documents SHALL invalidate
   dependent pack sections.

### R12 — Family Circle and sharing

1. Family access SHALL be deny-by-default and governed by a versioned grant that
   names grantee, profile, permitted data classes, permitted actions, purpose,
   start, expiry, and revocation state.
2. A relationship alone SHALL confer no health-data access.
3. Revocation SHALL affect new reads immediately and terminate active share
   sessions/tokens within the documented revocation SLO.
4. The owner SHALL see an understandable access log and receive configured
   notifications for sensitive access or changes.
5. Family members SHALL not confirm clinical facts for an adult owner unless an
   explicit policy permits that action and the UI identifies the acting person.
6. Invitations and share links SHALL be single-purpose, short-lived,
   non-enumerable, and stored as hashes.

### R13 — Living Evidence

1. Evidence questions SHALL be user-confirmed before research starts.
2. Retrieval SHALL separate guideline, systematic-review, trial, and other source
   classes and preserve citations.
3. Applicability SHALL be computed only from validated eligibility rules and
   confirmed profile facts; otherwise it SHALL remain `not_assessed`.
4. Contradictory evidence SHALL be represented explicitly, not averaged into
   false certainty.
5. Subscriptions SHALL run on a durable scheduler with source checkpoints,
   deduplication, and material-change adjudication.
6. A consumer notification SHALL be sent only after the material-change policy
   accepts the update and a safety-reviewed answer projection is available.
7. Evidence SHALL inform questions and discussion; it SHALL not silently mutate
   medication courses, diagnoses, goals, or tasks.

### R14 — Interoperability

1. CLARA SHALL keep its internal canonical model and expose a separate FHIR R4
   projection; database tables SHALL not be a raw FHIR persistence layer.
2. The projection SHALL map, as applicable, to Patient, Observation,
   AllergyIntolerance, Condition, MedicationStatement/MedicationRequest,
   CarePlan, Goal, Task, QuestionnaireResponse, DocumentReference, Provenance,
   Consent, and AuditEvent.
3. Patient summaries SHALL target the current HL7 IPS R4 package selected and
   pinned by the implementation.
4. Exports SHALL use UCUM units and documented terminology mappings; original
   local/user text SHALL remain available where coding is absent or uncertain.
5. Exported Bundles SHALL pass the pinned validator and CLARA profile tests.
6. Import SHALL always create provenance-bearing drafts unless the source and
   trust policy explicitly authorize a stronger state.
7. Unsupported modifiers, unknown critical codes, and ambiguous patient identity
   SHALL fail closed.

### R15 — Privacy, consent, retention, and data rights

1. Health data SHALL be classified as sensitive and minimized by purpose.
2. Consent SHALL be versioned, granular, revocable, and independently recorded
   for personalization, connected sources, family sharing, evidence monitoring,
   and research use.
3. Revocation SHALL stop future processing that relies on that consent and
   invalidate relevant tokens/jobs; legally required retention SHALL be
   documented separately.
4. Retention SHALL be defined per canonical fact, source binary, unconfirmed
   draft, audit record, derived projection, and backup.
5. Access, correction, export, deletion/restriction, and consent history SHALL be
   available through the existing data-rights workflow.
6. Cross-border processing SHALL not launch until the privacy owner records the
   applicable assessment and transfer mechanism.
7. Production telemetry SHALL never include names, emails, free text, document
   content, drug lists, raw wearable series, or stable public share tokens.

### R16 — Security and abuse resistance

1. Existing authentication, RBAC, CSRF, rate-limit, and internal-service-key
   controls SHALL remain enforced.
2. Every read and mutation SHALL enforce object-level profile authorization.
3. Source files SHALL be malware-scanned, content-sniffed, size-limited, and
   isolated from direct execution.
4. Prompt inputs from documents, webpages, and user imports SHALL be treated as
   untrusted data, never system instructions.
5. Share and invitation secrets SHALL be hashed at rest, redacted from logs, and
   protected against replay.
6. Security-relevant actions SHALL produce an immutable, authorized AuditEvent-
   compatible record with actor, purpose, outcome, and affected entity.
7. Threat models SHALL cover confused deputy, IDOR, prompt injection, cross-
   profile contamination, poisoned evidence, stale-consent jobs, and export
   leakage.

### R17 — Reliability and event delivery

1. Each successful state-changing transaction SHALL atomically write its
   canonical data and outbox event.
2. Outbox delivery SHALL use a dedicated worker with lease ownership, heartbeat,
   bounded attempts, exponential backoff with jitter, and dead-letter state.
3. Consumers SHALL be idempotent; delivery SHALL be at-least-once.
4. An idempotency key SHALL be scoped to actor, profile, operation, and request
   digest, and SHALL return the original result for a valid retry.
5. API processes SHALL not own long-running relay, evidence, extraction, or
   recomputation loops in production.
6. Worker lag, retry age, dead letters, stale projections, and dependency health
   SHALL be observable without PII.
7. Degraded reads SHALL expose freshness and partiality; unsafe writes SHALL fail
   closed.

### R18 — AI and clinical safety

1. The emergency fast path SHALL run before longitudinal reasoning.
2. Legal hard-guards against diagnosis, prescribing, and personal dosing SHALL
   apply to every LifeMap generation path.
3. ML SHALL propose drafts and explanations; it SHALL not directly commit
   confirmed facts, consent, access grants, task acceptance, or task completion.
4. Critical medication claims SHALL remain FIDES-blocking.
5. Every prompt/template/model/rule release SHALL be versioned, evaluated, and
   reversible.
6. Safety evaluation SHALL include Vietnamese/English emergency cases,
   negation, temporal ambiguity, pediatric/pregnancy cases, medication label
   ambiguity, prompt injection, and correction propagation.
7. A clinical safety owner SHALL approve the hazard log and release evidence for
   each safety-affecting work package.

### R19 — Web, mobile, accessibility, and offline behavior

1. Web and mobile SHALL expose the same core states and truth labels even when
   layouts differ.
2. Both clients SHALL support capture review, baseline/change explanation,
   next-question rationale, replay/correction, visit review, sharing controls,
   and evidence status before general availability.
3. All interactive controls SHALL meet WCAG 2.2 AA-aligned contrast, keyboard,
   focus, semantics, target-size, text-scaling, reduced-motion, and screen-reader
   requirements.
4. Offline mode SHALL cache only encrypted, least-necessary read projections.
5. Offline mutations SHALL be disabled by default. Any future queued mutation
   requires a per-command conflict, consent-age, expiry, and replay policy.
6. Clients SHALL show stale timestamps and never present cached safety status as
   current after its validity window.

### R20 — Observability and service levels

1. Metrics SHALL use pseudonymous or aggregate dimensions only.
2. Distributed traces SHALL carry request/operation IDs but no health content.
3. The production targets are:
   - core LifeMap read availability: at least 99.9% monthly;
   - p95 Today read latency: at most 500 ms excluding cold deployment;
   - p95 accepted command latency: at most 800 ms excluding file processing;
   - 99% of outbox events first-attempted within 60 seconds;
   - revocation effective for new API reads immediately and cached/share access
     within 60 seconds;
   - zero confirmed facts created directly by ML.
4. Safety, authorization, cross-profile, consent, and dead-letter alerts SHALL
   have named owners and response runbooks.
5. SLOs SHALL be measured in staging before pilot and in production before broad
   rollout; targets may only change through documented approval.

### R21 — Migration and backward compatibility

1. Existing routes SHALL remain additive-compatible during migration or return a
   documented versioned response.
2. Legacy numeric IDs SHALL be translated server-side while clients migrate to
   opaque IDs; they SHALL not appear in new client contracts.
3. Existing `confirmed` events SHALL be backfilled with explicit provenance
   confidence and marked `legacy_import` when the original confirmation actor
   cannot be proven.
4. Projection rebuilds SHALL be repeatable, resumable, and shadow-compared before
   cutover.
5. Every migration SHALL include a restore or forward-fix plan and reconciliation
   queries.
6. Legacy mobile roots and duplicate feature surfaces SHALL be removed only after
   replacement parity, telemetry, rollback window, and shared-component rehoming.

### R22 — Evaluation, governance, and release

1. Each release SHALL have a requirement-to-test traceability report.
2. Required evaluation dimensions are safety, extraction accuracy, provenance
   completeness, confirmation burden, baseline false-alert rate, question value,
   correction propagation, interoperability validation, accessibility, privacy,
   security, reliability, and user comprehension.
3. Offline datasets SHALL be de-identified or synthetic and governed; production
   free text SHALL not be copied into test fixtures.
4. Pilot rollout SHALL use feature flags, allowlisted cohorts, kill switches,
   shadow computation where possible, and explicit stop criteria.
5. No feature SHALL become default-on while a P0/P1 safety, authorization,
   privacy, data-loss, or provenance defect is open.
6. Product, clinical safety, privacy, security, and engineering owners SHALL sign
   the general-availability checklist.

### R23 — Grounded Ask My LifeMap assistant

1. LifeMap SHALL offer an AI-assisted query experience over the active,
   authorized ProfileScope for timeline lookup, comparison, preparation,
   missingness, and explanation.
2. Profile authorization and data-class filtering SHALL occur before semantic
   retrieval; embeddings or model similarity SHALL never expand the authorized
   scope.
3. Every factual answer claim SHALL cite one or more exact event revisions,
   source spans, decisions, tasks, or approved evidence records.
4. The assistant SHALL distinguish user report, device measurement, source-
   document statement, and CLARA-derived interpretation.
5. It SHALL expose unknown, conflicting, stale, disputed, and insufficient
   information rather than resolving ambiguity silently.
6. Unsupported claims SHALL be removed or cause abstention before release.
7. The assistant SHALL provide only safe organizational actions such as view,
   correct, confirm, export, or prepare a clinician question; it SHALL NOT
   diagnose, prescribe, dose, or autonomously alter LifeMap.
8. Answers SHALL record model, prompt/template, retrieval index, policy, and
   exact input revision versions without exposing private model chain-of-thought.

### R24 — AI timeline summaries and digests

1. LifeMap SHALL support source-grounded event, day, episode, visit-preparation,
   weekly, and monthly summaries where they reduce user effort.
2. A summary SHALL be a derived projection with exact input revision links and
   deterministic invalidation after correction, deletion, dispute, consent
   change, or source revocation.
3. Generated summaries SHALL preserve temporal order, truth state, attribution,
   uncertainty, and contradictions.
4. Summaries SHALL NOT convert symptoms into diagnoses, association into
   causation, user goals into clinician orders, or absent evidence into facts.
5. A deterministic template fallback SHALL remain available when the LLM,
   verifier, or retrieval dependency is unavailable.
6. Caregiver and clinician summaries SHALL be generated only after purpose and
   data-class filtering, and SHALL cite only content visible under that grant.

### R25 — Multimodal AI capture

1. Capture SHALL route supported text, voice, medication-label, and visit-
   document inputs through modality-appropriate OCR, ASR, layout, vision-
   language, and entity-extraction components.
2. Every model path SHALL return the common typed candidate/provenance contract;
   free-form model output SHALL not become canonical data.
3. Audio candidates SHALL retain timestamped transcript spans; document/image
   candidates SHALL retain page/region or text offsets.
4. Each field SHALL carry model identity, confidence, source span, and missing/
   ambiguous status.
5. Diagnostic interpretation of medical images SHALL remain unsupported unless
   separately specified, clinically evaluated, and approved.
6. A model unavailable or below threshold SHALL degrade to OCR/ASR/manual entry
   without inventing a result.
7. Evaluation SHALL measure critical-field recall and precision separately from
   overall extraction accuracy.

### R26 — Semantic normalization, entity resolution, and health graph

1. LifeMap SHALL use an ensemble of exact dictionaries, Vietnamese normalization,
   embeddings, terminology/knowledge-graph constraints, and optional reranking
   to generate coding and duplicate candidates.
2. The original user/source text SHALL always be retained beside any normalized
   identifier.
3. Each mapping SHALL expose candidate set, confidence/calibration, terminology
   and dataset version, and mapping method.
4. Ambiguous medication, allergy, diagnosis/condition, route, strength, or unit
   mappings SHALL require confirmation and SHALL NOT be hidden behind a single
   model score.
5. Entity resolution SHALL be reversible and SHALL append mapping revisions.
6. Automatic low-risk coding, if introduced, SHALL have a validated high-
   precision threshold, monitoring, and simple undo.
7. Graph edges SHALL carry source and version; graph traversal SHALL never create
   a clinical fact.

### R27 — Contradiction, duplicate, and missingness intelligence

1. LifeMap SHALL detect rule-defined conflicts and MAY use NLI/LLM models to
   propose additional contradiction or duplicate pairs.
2. The model SHALL NOT choose which conflicting fact is true, delete a duplicate,
   or invalidate a revision automatically.
3. Each proposed conflict SHALL cite both sides, relevant time overlap, rule/model
   version, and a plain-language reason.
4. Missingness detection SHALL be schema- and episode-aware and distinguish
   unknown, not asked, not applicable, withheld, and source unavailable.
5. Safety-critical conflicts SHALL be routed to explicit user or authorized
   clinical review before affected derived outputs are treated as current.
6. Evaluation SHALL include negation, temporality, medication start/stop,
   translations, copied-document duplication, and intentionally conflicting
   sources.

### R28 — Personalized pattern discovery and forecasting

1. The deterministic robust baseline SHALL remain the production champion until
   a challenger materially outperforms it on clinical-safety, false-alert,
   calibration, robustness, and human-factors gates.
2. Classical ML, autoencoders, temporal convolutional networks, Transformers, and
   time-series foundation models MAY run as versioned challengers.
3. Every model SHALL be compared with robust statistical and classical baselines;
   architecture novelty SHALL not count as product value.
4. Training/evaluation splits SHALL prevent leakage across user, household,
   source, overlapping window, device, site, and future time.
5. User-facing pattern outputs SHALL provide sufficiency, window, magnitude,
   uncertainty, OOD/abstention state, model version, and the data classes used.
6. Descriptive relationship discovery SHALL report effect size, uncertainty,
   paired-data coverage, multiplicity handling, and known confounders, and SHALL
   use non-causal language.
7. Initial forecasts SHALL be limited to low-risk wellness or organizational
   targets and SHALL run shadow-only before pilot.
8. Disease onset, deterioration, hospitalization, treatment response, medication
   effect, and emergency predictions SHALL remain research-only pending a
   separate intended-use, regulatory, dataset, and prospective-validation
   program.
9. A model SHALL abstain on insufficient, shifted, unsupported, or revoked-source
   data; the LLM SHALL not fill missing numeric time-series values by reasoning.

### R29 — Adaptive question, task, and engagement intelligence

1. Learned models MAY rank only questions and suggestions already permitted by
   the deterministic safety, consent, burden, and scope policy.
2. Learned ranking SHALL NOT create a new medical question, downgrade emergency
   handling, propose a prohibited action, or accept/complete a task.
3. The optimization objective SHALL include information value, user-reported
   usefulness, burden, dismissal, and safety; clicks or completion alone SHALL
   not be used as a proxy for health benefit.
4. The release sequence SHALL be supervised learning-to-rank, offline policy
   evaluation, shadow, bounded pilot, and only then optional contextual-bandit
   exploration.
5. Exploration SHALL have a fixed safe action set, probability floor/ceiling,
   daily/weekly burden limits, stop rules, consent, and an unlearned fallback.
6. Engagement models MAY offer fewer reminders, timing changes, pause, or smaller
   user-defined steps; they SHALL NOT shame, manipulate vulnerability, conceal
   instructions, or increase pressure to maximize engagement.
7. Corrections, dismissals, revoked consent, and do-not-ask preferences SHALL
   update eligibility immediately and training data according to policy.

### R30 — Personalized evidence and eligibility intelligence

1. AI MAY extract PICO, guideline conditions, trial eligibility concepts, and
   evidence relationships into typed, source-cited candidates.
2. Applicability and eligibility SHALL use explicit validated rules and confirmed
   facts; model inference alone SHALL not establish a sensitive eligibility fact.
3. The UI SHALL show matched, unmatched, and unknown criteria separately.
4. A trial or guideline result SHALL be presented as a possible match for review,
   not enrollment eligibility, diagnosis, or treatment recommendation.
5. Evidence synthesis SHALL separate source class, detect contradiction and
   supersession, and expose citation validity and retrieval date.
6. AI-generated clinician-discussion questions MAY be offered only after safety
   and evidence verification.
7. Evidence intelligence SHALL not mutate canonical facts, medication courses,
   or accepted tasks.

### R31 — ML lifecycle, model registry, and learning governance

1. Every AI/ML capability SHALL have a stable use-case ID, risk class, owner,
   intended users, allowed inputs/outputs, forbidden uses, champion/fallback,
   metrics, and release state.
2. Every training/evaluation dataset SHALL have an immutable version, checksum,
   datasheet, purpose/consent, population/device/time description, label
   provenance, split policy, missingness, subgroup profile, and deletion lineage.
3. Every trained artifact SHALL have a reproducible run manifest, signed
   checksum, source commit, environment, feature schema, hyperparameters/seeds,
   split identities, results, limitations, and model card.
4. A component SHALL be called “trained neural/ML” only when it loads a trained
   artifact produced by that governed process. Fixed hand-authored weights SHALL
   be labeled heuristic.
5. Promotion SHALL follow:
   `research -> offline -> red-team -> shadow -> pilot -> challenger -> champion`.
6. Online self-updating models SHALL be prohibited. Each learned update SHALL be
   an immutable, evaluated, approved version with rollback.
7. Prediction models SHALL report calibration, discrimination, uncertainty/
   coverage where appropriate, abstention, OOD, subgroup/worst-slice, missingness,
   shift, latency, and human-AI team performance.
8. LLM/RAG systems SHALL report citation precision/completeness, entailment,
   temporal grounding, contradiction, unsupported claims, prompt-injection
   resistance, abstention, safety, Vietnamese quality, latency, and cost.
9. Drift monitoring SHALL cover input schema, source/device/population, label/
   outcome where observable, embeddings/retrieval, calibration, output, safety,
   subgroup, and dependency/provider changes.
10. User corrections SHALL enter evaluation or training datasets only under the
    applicable consent and de-identification policy; production conversations
    SHALL NOT become implicit training data.
11. Synthetic data SHALL be labeled, versioned, kept out of real-world outcome
    estimates, and SHALL NOT contaminate held-out evaluation.
12. Any user-facing health-decision model SHALL undergo proportional live human-
    AI evaluation; prospective trials SHALL use the applicable DECIDE-AI,
    SPIRIT-AI, CONSORT-AI, and regulatory reporting expectations.

## 7. Explicit non-goals

- autonomous diagnosis, triage disposition beyond the existing emergency
  fast-path, prescribing, or personal-dose selection;
- autonomous acceptance/completion of tasks or health facts;
- replacement of a clinician's source EHR or medication reconciliation;
- unrestricted family access or relationship-implied access;
- causal claims from wearable correlations;
- automatic execution of an IPS, Visit Pack, or external CarePlan;
- general-purpose FHIR server behavior beyond the documented projection/export
  capability;
- learned question ranking in the first production release; and
- presentation of heuristic fixed weights as a trained neural network;
- online self-learning from production health data;
- autonomous agent access to unrestricted longitudinal memory;
- disease/deterioration or treatment-effect forecasting under the current
  intended use;
- diagnostic interpretation of uploaded medical images;
- digital twins, causal treatment recommendation, or federated learning outside
  a separately approved research program; and
- deletion of shared legacy screens before their behavior is rehomed and tested.

## 8. Release definition

LifeMap Production Convergence is complete only when:

1. all R1–R31 acceptance criteria are either implemented or explicitly deferred
   in an approved scope revision;
2. the canonical truth/provenance and ProfileScope foundations are live;
3. the durable worker/outbox path is production-enabled;
4. web and mobile expose the complete review/replay/correction loop;
5. Visit extraction and Living Evidence no longer claim completion while their
   grounded dependencies are unavailable;
6. FHIR/IPS exports validate against pinned packages;
7. the evaluation scorecard and hazard log meet their gates; and
8. legacy surfaces are retired or intentionally classified as shared components
   with a named owner.
9. released AI outputs are authorized before retrieval, source-cited,
   versioned, abstention-capable, and invalidated by upstream correction;
10. every learned artifact and dataset is reproducible through governed
    manifests, and heuristic components are labeled honestly; and
11. shadow/research AI—especially forecasts, adaptive policies, clinical risk,
    causal models, digital twins, and federated learning—is not represented as a
    released capability.
