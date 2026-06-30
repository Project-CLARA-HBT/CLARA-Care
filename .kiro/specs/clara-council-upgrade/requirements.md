# Requirements Document

## Introduction

This feature upgrades CLARA-Care's **Council** surface — the multi-specialist AI
deliberation flow (`apps/web/app/council/*`, `apps/web/components/council/*`,
`services/api/.../endpoints/council.py`, `services/ml/.../agents/council*.py`,
`apps/mobile/.../council_screen.dart`) — from a working-but-partial flow to a
**fully functional, production-grade** capability.

Today the Council already does a great deal: a deterministic rule-based engine
(`run_council`) produces per-specialist assessments, negation-aware red-flag
detection, conflict detection, a weighted consensus, confidence and
data-quality scoring, citations, a reasoning timeline, escalation metadata, and
a shadow-mode neural risk score; an intake agent (`run_council_intake`) extracts
structured fields from a transcript or audio via DeepSeek with a heuristic
fallback; the API persists cases (`CouncilCase`) with owner isolation under
`require_roles("doctor")`; and a three-step web wizard (intake → specialists →
review) plus a landing/result/workspace set of pages renders the result.

But several seams stop it short of production-grade, and this spec targets
exactly those **real, observed gaps**:

1. **No streaming.** `POST /council/cases/{id}/run` proxies a single blocking
   call to `/v1/council/run`; the web "timeline" is reconstructed from the final
   result, not streamed. Chat already has `/v1/chat/stream` (SSE) and `/ws/stream`;
   Council has nothing equivalent.
2. **No run history.** Each run overwrites `result_json`/`raw_result_json` on the
   case; prior deliberations are lost and there is no audit trail of who ran what
   when.
3. **Human-oversight actions are non-functional stubs.** The landing page's
   "Mời bác sĩ phụ trách" (invite attending), "ghi đè" (override), and "tạm dừng"
   (pause) controls only call `setActionNotice(...)` in the browser — nothing is
   persisted, enforced, or auditable, even though the UI presents them as
   clinical governance actions.
4. **Server-side authorization is inconsistent.** All Council endpoints require
   the `doctor` role, yet the web grants override/pause to `admin` too
   (`canUseDoctorActions = role === "doctor" || role === "admin"`); there is no
   server-side authorization or audit for oversight actions.
5. **Thin error handling.** ML failures collapse to a generic `502`; there is no
   retry/timeout policy, no surfaced partial result, and intake DeepSeek failures
   degrade silently to the heuristic fallback without a user-visible label.
6. **No model/fallback disclosure on Council outputs.** The regulatory-compliance
   transparency-notice gate already lists `/council`, but Council responses carry
   no `ai_disclosure` (model family/version, fallback flag), unlike the
   compliance design for chat.
7. **Thin observability.** Only coarse `council_viewed` / `council_run` analytics
   exist; there are no per-stage flow events, latency, or error metrics for the
   deliberation pipeline.
8. **Mobile is not at parity.** `council_screen.dart` posts directly to
   `/api/v1/council/run` with free-text fields; it has no intake, no cases, no
   persistence, no workspace, and no oversight surfaces.

All new behavior in this feature is **additive, feature-flagged, and default-off**.
With every flag off, the Council behaves byte-for-byte as it does today: the same
endpoints, the same `run_council` output shape, the same wizard, the same
doctor-only gating, and the same deterministic safety behavior (negation-aware
red flags, emergency escalation, "review with a clinician" directive). Nothing in
this feature changes CLARA's positioning as **decision-support software, not a
medical device and not an EMR/EHR**, and it preserves every existing guardrail
(RBAC, owner isolation, no-PII telemetry, CSRF, the legal hard-guards, and the
existing compliance gates). Copy is Vietnamese-first with bilingual vi/en where a
term of art requires it.

## Glossary

- **Council**: The multi-specialist AI deliberation feature that takes a clinical case and produces specialist assessments, conflict detection, a consensus triage, and a final recommendation.
- **Council_ML**: The deterministic orchestration in `services/ml/src/clara_ml/agents/council.py` (`run_council`) and `council_intake.py` (`run_council_intake`).
- **Council_API**: The FastAPI surface in `services/api/src/clara_api/api/v1/endpoints/council.py`, including case CRUD and the ML proxy.
- **Council_Web**: The Next.js surfaces under `apps/web/app/council/*` and `apps/web/components/council/*`.
- **Council_Mobile**: The Flutter Council screen `apps/mobile/lib/screens/council_screen.dart`.
- **Case / CouncilCase**: The persisted, owner-isolated record (`council_cases` table) holding a case's transcript, intake, request payload, and latest result.
- **Run / CouncilRun**: A single execution of `run_council` against a case's request payload, producing one result snapshot at one point in time.
- **Intake**: The transcript/audio → structured-fields extraction step (`run_council_intake`), DeepSeek-backed with a heuristic fallback (`heuristic-fallback-v1`).
- **Specialist Assessment**: One specialist's deterministic output: `reasoning_log`, `key_findings`, `triage`, `recommendation`.
- **Triage**: One of `routine_follow_up`, `same_day_review`, `emergency_escalation` (scored 1/2/3 in `_TRIAGE_SCORE`).
- **Consensus**: The winning triage plus vote breakdown, support ratio, disagreement index, and dissent profile (`_build_consensus_metadata`).
- **Red flag**: A safety phrase match (negation-aware) that forces `emergency_escalation` and an immediate-referral action.
- **Neural risk (shadow)**: The `council-neural-shadow-v1` score that is computed only when enabled and never overrides deterministic triage (default disabled).
- **Deliberation stream**: An additive SSE event stream that emits each pipeline stage (intake-normalized → specialist-assessment → conflict-review → consensus → safety-gate → final) as it completes, plus a terminal result event.
- **Oversight Action**: A clinician/admin governance action recorded against a run: `handoff` (invite an attending specialty), `override` (record a human decision that differs from the AI), or `pause` (suspend automated conclusion pending review).
- **ai_disclosure**: The response-envelope block `{ model_family, model_version, is_fallback }` describing how a Council output was produced (additive; mirrors the compliance design).
- **Council_System**: Collective name for Council_ML + Council_API + Council_Web + Council_Mobile when a requirement spans tiers.
- **Feature flag**: A configuration switch that enables new Council behavior while defaulting to a state that preserves current behavior.
- **No-PII telemetry**: The existing invariant that metrics, flow events, and analytics exclude patient-identifiable content (symptoms, labs, transcript, history).

## Requirements

### Requirement 1: Streaming / Progressive Deliberation

**User Story:** As a doctor running a Council case, I want to watch the
deliberation progress stage-by-stage instead of staring at a blocked spinner, so
that I get early signal and can trust that a long run is making progress.

#### Acceptance Criteria

1. WHEN `COUNCIL_STREAMING_ENABLED` is on AND a doctor runs a case via the streaming endpoint, THE Council_System SHALL emit an ordered sequence of stage events (`intake_normalized`, `specialist_assessment`, `conflict_review`, `consensus_decision`, `safety_gate`, `final_recommendation`) followed by a terminal result event.
2. THE streaming endpoint SHALL produce a final result whose shape is equal to the existing non-streaming `/council/run` result (same keys, same value semantics).
3. WHERE `COUNCIL_STREAMING_ENABLED` is off, THE Council_System SHALL serve only the existing non-streaming run path and SHALL NOT expose the streaming endpoint.
4. IF the upstream stream fails or disconnects mid-deliberation, THE Council_System SHALL emit a terminal error event and SHALL NOT leave the case in a partially-updated persisted state.
5. THE streaming events SHALL contain only stage labels, counts, and non-identifying metadata, and SHALL NOT include raw transcript, symptom, lab, or history text beyond what the existing non-streaming result already returns.
6. THE streaming endpoint SHALL remain gated by the same authentication and `doctor` role authorization as the existing run endpoint.

### Requirement 2: Run History and Versioning

**User Story:** As a doctor, I want every Council run on a case preserved as an
immutable record, so that I can compare runs over time and an auditor can see
exactly what the system concluded and when.

#### Acceptance Criteria

1. WHEN `COUNCIL_RUN_HISTORY_ENABLED` is on AND a case is run, THE Council_System SHALL append a new immutable `CouncilRun` record capturing the request payload, the result snapshot, the model/version used, and the run timestamp.
2. THE Council_System SHALL preserve prior runs when a new run is executed, and SHALL NOT delete or mutate an existing `CouncilRun` record.
3. THE Council_System SHALL continue to expose the latest run as the case's current result so existing consumers are unaffected.
4. THE Council_System SHALL allow an authenticated owner to list the run history for a case they own, ordered most-recent-first.
5. THE Council_System SHALL enforce owner isolation on run history so a user can only read runs for cases they own.
6. WHERE `COUNCIL_RUN_HISTORY_ENABLED` is off, THE Council_System SHALL behave exactly as today (latest result overwrites the case; no history table writes).
7. THE run-history records SHALL store clinical payloads only within the same owner-isolated trust boundary as `CouncilCase`, and SHALL NOT introduce clinical content into any telemetry or analytics surface.

### Requirement 3: Human Oversight Actions (Handoff, Override, Pause)

**User Story:** As an attending clinician, I want my governance actions on a run
— inviting a specialty, overriding the AI conclusion, or pausing automated
conclusion — to be actually recorded and enforced, so that the human stays
accountable for the clinical decision.

#### Acceptance Criteria

1. WHEN `COUNCIL_OVERSIGHT_ENABLED` is on, THE Council_System SHALL persist each oversight action (`handoff`, `override`, `pause`) against the target run with the acting user reference, action type, free-text reason, and timestamp.
2. WHEN a run is in a `paused` oversight state, THE Council_System SHALL mark the case so that its final recommendation is presented as **not yet confirmed** pending human review.
3. WHEN an `override` action is recorded, THE Council_System SHALL retain the original AI recommendation alongside the human override and SHALL NOT discard the AI output.
4. THE Council_System SHALL make oversight history readable to the case owner and to authorized admin roles.
5. THE Council_System SHALL preserve the existing "review with a licensed clinician" directive on every Council output regardless of oversight state.
6. WHERE `COUNCIL_OVERSIGHT_ENABLED` is off, THE web oversight controls SHALL behave exactly as today (local notice only) and no oversight records SHALL be written.
7. THE oversight reason text SHALL be treated as owner-isolated case data and SHALL NOT be emitted to telemetry or analytics.

### Requirement 4: Role-Based Access and Server-Side Authorization

**User Story:** As a platform operator, I want Council access and oversight
actions authorized consistently on the server, so that the UI cannot grant a
capability the backend does not actually enforce.

#### Acceptance Criteria

1. THE Council_System SHALL keep all Council case and run endpoints behind authentication and `doctor`-role authorization, exactly as today.
2. WHERE oversight actions are exposed to `admin` in the web UI, THE Council_API SHALL authorize those same actions server-side for the roles permitted to perform them, and SHALL reject unauthorized roles with a 403.
3. THE Council_System SHALL enforce owner isolation on every case, run, and oversight read/write so a user cannot access another user's case data.
4. THE Council_System SHALL preserve CSRF protection on all cookie-authenticated mutating Council endpoints.
5. IF an oversight or run action is attempted by an unauthenticated caller, THE Council_System SHALL reject it with a 401 before any side effect.
6. THE server-side authorization decision SHALL be the single source of truth, and the web client SHALL surface a capability only when the server would permit it.

### Requirement 5: Resilient ML Orchestration and Error Handling

**User Story:** As a doctor, I want the Council to fail gracefully and tell me
what happened, so that a transient upstream hiccup neither corrupts my case nor
leaves me without actionable feedback.

#### Acceptance Criteria

1. WHEN `COUNCIL_RESILIENCE_ENABLED` is on AND an upstream ML call fails transiently, THE Council_API SHALL retry within a bounded policy (bounded attempts and timeout) before surfacing an error.
2. WHEN the ML service is unavailable after the bounded retries, THE Council_API SHALL return a descriptive, PII-free error and SHALL leave the case's persisted state unchanged.
3. WHEN intake extraction falls back to the heuristic path (`heuristic-fallback-v1`), THE Council_System SHALL label the intake result as a degraded/fallback extraction in a machine-readable and user-visible form.
4. THE Council_System SHALL preserve the existing input-validation behavior: a run with no symptoms, labs, medications, or history SHALL be rejected with a 400, and audio uploads SHALL keep the existing size (15MB) and content-type allow-list limits.
5. WHERE `COUNCIL_RESILIENCE_ENABLED` is off, THE Council_API SHALL preserve today's error behavior (single attempt; existing 400/413/415/502 mapping).
6. THE Council_System SHALL ensure that a failed or partial run never produces a case state that is presented to the user as a completed, confirmed result.

### Requirement 6: Model and Fallback Disclosure on Council Outputs

**User Story:** As a user reviewing a Council result, I want to know which model
produced it and whether it was a degraded fallback, so that I can calibrate my
trust and the product stays transparent and compliant.

#### Acceptance Criteria

1. WHEN `COUNCIL_MODEL_DISCLOSURE_ENABLED` is on, THE Council_System SHALL attach an `ai_disclosure` block (`model_family`, `model_version`, `is_fallback`) to Council intake and run outputs.
2. WHERE an intake was produced by the heuristic fallback, THE Council_System SHALL set `is_fallback = true` and label the result as degraded.
3. WHERE a run was produced by the deterministic rule engine, THE Council_System SHALL disclose the rule-engine model version (e.g. `rule_based_council_v2`) so the basis of the result is unambiguous.
4. THE Council_System SHALL surface the disclosure on the result/landing surfaces without exposing engineering-only telemetry to non-admin users.
5. WHERE `COUNCIL_MODEL_DISCLOSURE_ENABLED` is off, THE Council_System SHALL omit the `ai_disclosure` block and behave exactly as today.
6. THE disclosure SHALL be consistent with the existing regulatory-compliance model-disclosure semantics (fallback iff a degraded/local path produced the answer).

### Requirement 7: Observability and No-PII Telemetry

**User Story:** As an operator, I want per-stage Council metrics and error
signals without any patient data, so that I can monitor health and latency and
debug failures safely.

#### Acceptance Criteria

1. WHEN `COUNCIL_OBSERVABILITY_ENABLED` is on, THE Council_System SHALL emit a flow event per deliberation stage with stage name, duration, and outcome (success/error).
2. THE Council_System SHALL record run-level metrics (latency, specialist count, conflict count, emergency-triggered flag, fallback-used flag) without any clinical free text.
3. THE Council_System SHALL exclude transcript, symptom, lab, medication, and history content from every metric, flow event, log, and analytics payload.
4. THE Council_System SHALL preserve the existing coarse `council_viewed` / `council_run` analytics events and their no-PII guarantees.
5. WHERE `COUNCIL_OBSERVABILITY_ENABLED` is off, THE Council_System SHALL emit only the telemetry it emits today.
6. WHEN an error occurs in any stage, THE Council_System SHALL record a no-PII error event with the stage and an error class, never the offending input content.

### Requirement 8: Mobile Parity

**User Story:** As a doctor on mobile, I want the same case-based intake,
persistence, and result review the web offers, so that I can run a trustworthy
Council from my phone instead of a stripped-down form.

#### Acceptance Criteria

1. WHEN `COUNCIL_MOBILE_PARITY_ENABLED` is on AND the `council` feature is enabled for the user, THE Council_Mobile SHALL support creating a case, running intake, selecting specialists, running the Council, and viewing the persisted result.
2. THE Council_Mobile SHALL reuse the existing Council_API endpoints and SHALL NOT introduce a mobile-only result shape that diverges from the web.
3. THE Council_Mobile SHALL render the consensus, conflicts/divergence, final recommendation, and the "review with a clinician" directive consistent with the web.
4. THE Council_Mobile SHALL transmit only the non-PII specialist count in analytics, preserving the existing mobile no-PII analytics behavior.
5. WHERE `COUNCIL_MOBILE_PARITY_ENABLED` is off, THE Council_Mobile SHALL behave exactly as today (direct `/council/run` form), and the client SHALL gate the new surfaces on the feature-flags endpoint.
6. THE Council_Mobile SHALL enforce the same authentication and role expectations as the web for Council actions.

### Requirement 9: Guardrails, Back-Compatibility, and Privacy Preservation

**User Story:** As a platform operator, I want the Council upgrade to default
safely and never regress existing behavior, so that adoption carries no clinical
or operational risk.

#### Acceptance Criteria

1. THE Council_System SHALL gate all new behavior behind feature flags whose defaults preserve current behavior.
2. WHERE all Council upgrade flags are off, THE Council_System SHALL behave equivalently to the pre-feature system (same endpoints, same `run_council`/intake output shapes, same wizard, same gating).
3. THE Council_System SHALL preserve the deterministic safety behavior: negation-aware red-flag detection, emergency escalation forcing `emergency_escalation`, and the immediate-referral action on red flags.
4. THE Council_System SHALL keep the neural risk score in shadow mode by default and SHALL NOT let it override deterministic triage.
5. THE Council_System SHALL NOT introduce patient-identifiable content into any telemetry, log, or analytics surface.
6. THE Council_System SHALL preserve RBAC (`doctor` gating), owner isolation, and CSRF protection on all new and existing Council endpoints.
7. THE Council_System SHALL keep every new persistence change additive and reversible (new tables/columns only, with a reversible migration downgrade).
