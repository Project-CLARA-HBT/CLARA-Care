# Requirements — CLARA Product Experience Convergence

Status: implementation program. Safety, consent, provenance, RBAC, emergency,
FIDES, legal-guard, and no-PII telemetry invariants remain regression-locked.
Requirement-to-design, phase, and evidence mappings are recorded in
[`traceability.md`](traceability.md). A mapping does not imply completion.

## 1. Product objective

CLARA SHALL feel simple even when the underlying clinical workflow is complex.
Data entry and setup SHALL prefer a sequence of short, recoverable pages over a
single dense canvas. Read-only workspaces SHALL use progressive disclosure so
users can understand the primary result before opening detail. Light mode SHALL
be a first-class, modern, accessible theme on web and mobile.

“One page, one information” means one coherent decision or information group
per step. It does not mean forcing every field onto a separate network request,
splitting a natural chat exchange, or hiding safety-critical context.

## 2. Experience-wide requirements

### R1 — One primary job per page

1. Every route/screen SHALL declare one primary user job and one primary action.
2. Creation/setup flows with more than one logical information group SHALL use
   separate URL-addressable web steps and equivalent named mobile steps.
3. A step SHOULD contain at most one required decision group, one short
   explanation, and its validation feedback.
4. Safety-critical context MAY remain beside the decision it qualifies.
5. Secondary actions SHALL move to an overflow menu, detail drawer, or later
   step and SHALL NOT visually compete with the primary action.

### R2 — Guided-flow contract

1. Every guided flow SHALL show its name, current step, total or approximate
   progress, completed steps, and next outcome.
2. Back SHALL preserve entered data. Refresh, app backgrounding, and sign-in
   renewal SHALL restore a non-sensitive draft where policy permits.
3. Optional steps SHALL be clearly labeled and skippable.
4. Previously completed steps SHALL be reviewable without losing later data.
5. The final page SHALL summarize changes, provenance, consent implications,
   and the exact commit action.
6. Clinical/health mutations SHALL remain online-only unless a separately
   approved encrypted queue exists.

### R3 — Validation and recovery

1. Validate a step when the user chooses Next, not while they are still
   composing, except for harmless formatting hints.
2. Focus the first invalid field and provide a plain-language summary plus
   field-level error.
3. Never clear accepted input after a recoverable API, network, or auth error.
4. Destructive actions SHALL use a separate consequence/confirmation step.
5. Emergency content SHALL leave the ordinary flow immediately and present the
   existing emergency action without diagnostic reasoning.

### R4 — Setup center

1. Consumer setup SHALL cover account, profile basics, consent, data import,
   optional wearable connection, medicines, and family sharing as independent
   resumable steps.
2. Professional setup SHALL add role verification, Scribe consent/readiness,
   Council access, and workspace defaults.
3. Admin setup SHALL expose content-free readiness for API, ML, RAG corpus,
   immutable provider model, OCR/ASR, workers, migrations, backups, and flags.
4. Every unavailable feature SHALL explain why, what the user can do, what an
   administrator must do, and the safe fallback.
5. Setup SHALL never reveal secrets, internal keys, private paths, or raw
   upstream errors.

### R5 — Modern light mode

1. Light mode SHALL use a quiet neutral canvas, opaque readable surfaces,
   restrained blue/indigo brand accents, clear elevation, and minimal
   decorative glass.
2. Text, icons, borders, focus rings, statuses, charts, and disabled controls
   SHALL meet the repository contrast gates and WCAG 2.2 AA where applicable.
3. Surfaces SHALL use shared semantic tokens; feature pages SHALL NOT introduce
   hard-coded theme colors without an audited exception.
4. The visual hierarchy SHALL be recognizable without color alone.
5. Dark mode SHALL retain parity, but light mode SHALL be the reference theme
   for screenshots and acceptance review.
6. Phone, tablet, desktop, 200% web zoom, large mobile text, reduced motion,
   high contrast, keyboard, and screen reader SHALL remain supported.

### R6 — Navigation and information architecture

1. Primary navigation SHALL expose Today, LifeMap, Chat, Medicines, Visits,
   Family, and Profile/More according to role and capability.
2. Research SHALL remain integrated into Chat; legacy research URLs MAY redirect
   but SHALL NOT create a second primary experience.
3. Route titles and headings SHALL include guided-flow progress when relevant.
4. Users SHALL always have a visible safe exit that preserves or explicitly
   discards the draft.
5. Legacy routes SHALL be classified as redirect, compatibility adapter,
   shared component, or retired; no duplicate primary entry may remain.

## 3. Feature requirements

### R7 — Authentication and onboarding

Use separate steps for account identity, authentication method, role, profile
basics, measurements, consent, optional data connection, and review. Login
itself remains a focused single job. Password reset and verification use one
status/action per page.

### R8 — Today and LifeMap

Today SHALL lead with the next safe action and defer history/detail. LifeMap
SHALL separate overview, episode creation, goal, event capture, task creation,
Ask, source review, corrections/conflicts, summaries, and Replay. Capture SHALL
remain draft → extraction → field review → normalization → final confirmation.

### R9 — Medicines

Medicines SHALL use a coherent hub for cabinet, courses, and safety. Adding a
medicine SHALL separate source method, identity, strength/form, schedule,
provenance, normalization review, and confirmation. DDI SHALL separate medicine
selection, readiness, result, sources, and “what to do,” never presenting an
all-clear when evidence is unavailable.

### R10 — Visits, Family, PHR, and Living Evidence

- Visit preparation: visit basics → concerns → guided intake → documents →
  extracted-instruction review → pack selection → consent → share/review.
- Family: person/relationship → purpose → minimum data classes → actions →
  expiry → recipient → review; revocation gets its own consequence step.
- PHR: overview plus separate allergies, conditions, medicines, measurements,
  documents, provenance, correction, import/export, and verification flows.
- Evidence: question → structured scope → confirm → run → results → sources →
  applicability → subscription → notification preferences → review.

### R11 — Chat, RAG, Council, and Scribe

1. Chat SHALL remain conversational and uncluttered: composer and answer are
   primary; mode, source scope, attachments, and advanced controls use
   progressive disclosure.
2. Every medical RAG answer SHALL distinguish retrieved source, generated
   synthesis, uncertainty, conflict, and unavailable evidence.
3. RAG SHALL use stage-aware retrieval/generation verification and SHALL NOT
   assume that adding more context improves medical quality.
4. Council intake SHALL remain a multi-route wizard: case → evidence →
   specialists → consent/review → run → result sections.
5. Scribe SHALL separate session setup/consent, input method, recording/upload,
   transcript review, structured-note review, corrections, and export.

### R12 — Community, account, and administration

Community creation SHALL separate audience, content, safety review, and
publication. Account consent/data rights SHALL separate status, selection,
consequences, confirmation, and receipt. Admin features SHALL favor overview →
list → object detail → action configuration → review/run → result, with advanced
telemetry hidden until requested.

## 4. Research and AI requirements

### R13 — Evidence-governed Chat/RAG

1. Medical retrieval SHALL combine lexical and dense candidates only inside the
   authorized source/profile boundary, then rerank and enforce a relevance
   threshold.
2. Context size/top-k SHALL be tuned per use case against retrieval precision,
   recall, answer faithfulness, completeness, latency, and cost; “more chunks”
   is not a valid default.
3. Released claims SHALL carry exact citations and pass existence, entailment,
   temporal ordering, contradiction, profile isolation, legal guard, and FIDES
   checks where applicable.
4. The system SHALL abstain or use a deterministic safe fallback when evidence,
   provider identity, verification, or latency budget fails.
5. Vietnamese evaluation SHALL include a versioned native benchmark and human
   review; English-only quality SHALL NOT authorize Vietnamese release.
6. Models/providers SHALL use immutable allowlisted identities. “Newest” means
   newest version that passes the frozen CLARA use-case gate, not an
   automatically changing alias.
7. Every production use case SHALL have offline, adversarial, shadow, pilot,
   human-AI workflow, subgroup, rollback, and post-release evidence appropriate
   to its risk.
8. Query rewriting SHALL preserve the original query and SHALL be rejected
   when clinical entities, negation, temporality, dosage, or intent changes.
9. Conversation history SHALL be bounded and structured. Release evaluation
   SHALL include history-length, correction, contradiction, and topic-switch
   slices.
10. Automated judges SHALL be calibrated against blinded bilingual
    clinician-labelled data and SHALL NOT solely authorize a critical release.
11. Stage evaluation SHALL separately report retrieval, selected-context,
    claim/citation, generation, safety, human-workflow, subgroup, latency, and
    cost results with denominators and confidence intervals where applicable.

### R14 — Research freshness

1. The design bibliography SHALL record source date, study setting, population,
   limitations, and the exact CLARA decision it informs.
2. Owners SHALL review the evidence quarterly and before changing retrieval,
   model, prompt, evaluation, or safety policy.
3. New research SHALL create a change-control proposal; it SHALL NOT silently
   alter production behavior.
4. A benchmark result SHALL NOT be represented as clinical benefit. Health-
   decision influence SHALL require prospective evaluation proportional to the
   intended use, using DECIDE-AI and, for applicable trials, SPIRIT-AI and
   CONSORT-AI reporting.

## 5. Acceptance

Completion requires a route/screen inventory with an owner and disposition for
every active feature; shared guided-flow primitives; migrated priority flows;
modern light-mode token convergence; setup/readiness surfaces; responsive and
accessibility evidence; successful web/mobile builds and E2E; no weakened
safety invariant; and production deployment with rollback verification.
