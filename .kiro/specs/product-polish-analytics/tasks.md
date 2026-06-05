# Implementation Plan: Product Polish & Analytics

## Overview

This plan converts the design into a severity-ordered, highly parallelizable set of coding tasks across the polyglot monorepo: `apps/web` (Next.js/TypeScript), `services/api` (FastAPI/Python), `services/ml` (FastAPI/Python), and `apps/mobile` (Flutter/Dart).

The plan is organized into thirteen epics that map to the design's eight tracks plus the delivery deliverables, the analytics dashboards, and the safety-preservation regression suite. To maximize concurrency, **shared modules are built once and isolated to their own files** (so they can run in the same wave as unrelated work), and **per-surface integration tasks are split out** so independent surfaces (Chat, Research, CareGuard, Council, Scribe, Admin, Dashboard) can be polished by separate subagents in parallel.

- Epic 1 — Delivery deliverables & doc/config drift (Audit_Record, Competitive_Research_Report, CLAUDE.md, .env.example, data/docs/index.md)
- Epic 2 — Chat routing & timeout correctness (web dispatch, ML runtime-client reuse, timeout floor)
- Epic 3 — Error & telemetry sanitization (boundary sanitizer, role-gated TelemetryPanel, VN mode labels)
- Epic 4 — DDI output clarity (ML aggregation, web projection, two-medicine guard, VN risk-group localization)
- Epic 5 — Product & Clinical analytics API (aggregator, schemas, endpoints, RBAC, settings)
- Epic 6 — Analytics admin dashboards (web product + clinical pages, 4 async states)
- Epic 7 — Analytics SDK facade (web + mobile, consent/PII/pseudonymous guards)
- Epic 8 — UX modernization & accessibility (AsyncSection, design tokens, AA contrast, focus/labels)
- Epic 9 — Per-surface telemetry-strip + event-emit integration (Chat, Research, CareGuard, Council, Scribe, Admin)
- Epic 10 — Mobile persistent session & parity (PersistentSessionStore, parity screens)
- Epic 11 — Safety guardrail preservation regression suite
- Epic 12 — Backend checkpoint
- Epic 13 — Final checkpoint

Testing follows the dual approach from the design: `fast-check` (TypeScript), `hypothesis` (Python), and model/widget tests (Dart). Property-test sub-tasks are marked optional with `*`, each is its own sub-task, and each cites its design Property number and the requirement clause it validates. Every bug-fix task adds a regression test that fails pre-fix and passes post-fix (Requirement 1.3). Tasks are scoped so that 14+ can be dispatched to parallel subagents — see the Task Dependency Graph.

Testing prerequisites (set up as part of the first task that needs them, not as standalone tasks):
- Web: add a test runner (e.g., Vitest) + `fast-check` to `apps/web` devDependencies and a `test` script (use `--run` for single execution, not watch mode).
- Python: add `hypothesis` to the `dev` optional-dependencies in `services/api/pyproject.toml` and `services/ml/pyproject.toml`.
- Mobile: add `flutter_secure_storage` to `apps/mobile` dependencies; `flutter_test` is already present.

## Tasks

- [x] 1. Delivery deliverables and documentation/configuration drift correction
  - [x] 1.1 Produce the Audit_Record deliverable
    - Create `.kiro/specs/product-polish-analytics/audit-record.md` enumerating, per Surface (Chat, Research, SelfMed/CareGuard, Council, Scribe, Admin Control Tower, Dashboard, Mobile), the defects found with a `critical|high|medium|low` severity rank based on End_User impact.
    - Order this plan's fix tasks so that `critical`/`high` defects on a Surface precede `medium`/`low` on the same Surface.
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Produce the Competitive_Research_Report deliverable
    - Create `.kiro/specs/product-polish-analytics/competitive-research.md` covering products comparable to each major Surface, describing only general UX patterns/capabilities, excluding verbatim copyrighted text and proprietary assets, with an attribution link for every cited source.
    - Tag each pattern with the Surface(s) it informs (Chat fast-first/thinking state, Research progressive disclosure, CareGuard severity visualization, Council consensus/divergence layout, Scribe SOAP scaffolding, Admin analytics KPI/date-range conventions) so UX tasks (Epic 8) and dashboard tasks (Epic 6) can reference the originating pattern (Requirement 6.4).
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 1.3 Rewrite CLAUDE.md as an implemented monorepo
    - Update `CLAUDE.md` so the repository is described as an implemented polyglot monorepo (web/api/ml/mobile) rather than documentation-only; reflect the as-built service layout and commands.
    - _Requirements: 12.1_

  - [x] 1.4 De-duplicate and extend `.env.example`
    - Reduce every key defined more than once (including `DEEP_BETA_REPORT_MIN_WORDS`) to a single authoritative definition.
    - Add the new analytics keys from the design: `ANALYTICS_SDK_PROVIDER`, `ANALYTICS_SDK_KEY`, `ANALYTICS_SDK_HOST`, `NEXT_PUBLIC_ANALYTICS_SDK_PROVIDER`, `NEXT_PUBLIC_ANALYTICS_SDK_KEY`, `NEXT_PUBLIC_ANALYTICS_SDK_HOST`, `PRODUCT_ANALYTICS_ENABLED`, `CLINICAL_ANALYTICS_ENABLED`, `ANALYTICS_DEFAULT_RANGE_DAYS`.
    - _Requirements: 12.2, 12.4_

  - [x] 1.5 Fix `data/docs/index.md` path references
    - Update references so each resolves to an existing path in the current repository structure.
    - _Requirements: 12.3_

  - [ ]* 1.6 Write doc/config drift checks
    - Test: `.env.example` has no duplicate keys and contains all new analytics keys (12.2, 12.4); every path in `data/docs/index.md` resolves (12.3); `CLAUDE.md` describes an implemented monorepo (12.1).
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [ ] 2. Chat routing and timeout correctness
  - [x] 2.1 Implement web mode dispatch (TypeScript)
    - In `apps/web/lib/research.ts`, add `resolveChatTransport(mode)` mapping `fast → tier1_chat` and `deep`/`deep_beta → tier2_job` as a pure, exported function.
    - _Requirements: 2.1, 2.2_

  - [ ]* 2.2 Write property test for mode dispatch (fast-check)
    - **Property 1: Mode dispatch routes fast to tier1 and deep modes to tier2**
    - **Validates: Requirements 2.1, 2.2**

  - [x] 2.3 Wire chat page to the dispatch decision (TypeScript)
    - In `apps/web/app/chat/page.tsx`, call `resolveChatTransport` and invoke the tier1 `POST /chat` proxy for `fast`, only calling `executeResearchTier2Job()` when the result is `tier2_job`.
    - _Requirements: 2.1, 2.2_

  - [x] 2.4 Implement ML runtime-client reuse (Python)
    - In `services/ml/src/clara_ml/rag/pipeline.py` (and `main.py` wiring), add `resolve_llm_client(llm_runtime, settings)` that reuses the default DeepSeek client (preserving its longer timeout) when `LLM_DEEPSEEK_ONLY` is enabled and the supplied runtime matches the configured DeepSeek env; otherwise build an explicit runtime client.
    - _Requirements: 2.3_

  - [ ]* 2.5 Write property test for runtime-client reuse (hypothesis)
    - **Property 2: DeepSeek-only runtime reuses the default client without a shortened timeout**
    - **Validates: Requirements 2.3**

  - [x] 2.6 Implement API/ML timeout floor (Python)
    - In `services/api` (settings + `ml_proxy`/research path), add `assert_timeout_floor(api_timeout, ml_synthesis_timeout)` and a startup assertion ensuring `ml_service_timeout_seconds >= deepseek_timeout_seconds` and the sync-research path stays `>= ml_research_timeout_seconds` (600s floor).
    - _Requirements: 2.4_

  - [ ]* 2.7 Write property test for timeout floor (hypothesis)
    - **Property 3: API ML timeout is never below the ML synthesis timeout**
    - **Validates: Requirements 2.4**

  - [~] 2.8 Wire sanitized timeout retry message into chat surface (TypeScript)
    - In `apps/web/app/chat/page.tsx`, render a user-readable Vietnamese retry message via `sanitizeUpstreamError` (Epic 3) when the chat pipeline times out; exclude raw error codes and stack traces.
    - _Requirements: 2.5_

  - [ ]* 2.9 Write regression test for chat timeout message
    - Fails on pre-fix behavior (raw error/code surfaced), passes when the sanitized retry copy is shown (Requirement 1.3).
    - _Requirements: 2.5, 1.3_

- [x] 3. Error and telemetry sanitization (web boundary)
  - [x] 3.1 Implement the error/telemetry sanitizer functions (TypeScript)
    - In `apps/web/lib/user-facing-text.ts`, implement `sanitizeUpstreamError(raw)` (strips internal URLs, connector ids, HTTP status detail, stack traces → calm Vietnamese copy) and `stripTelemetryLabels(text)` (removes `research mode`, `retrieval`, `RAG mode`, `Fallback mode`, `Policy: Warn/Allow`).
    - _Requirements: 4.1, 4.2, 2.5_

  - [ ]* 3.2 Write property test for error sanitization (fast-check)
    - **Property 4: User-facing error messages are sanitized**
    - **Validates: Requirements 2.5, 4.2**

  - [ ]* 3.3 Write property test for telemetry label exclusion (fast-check)
    - **Property 10: Internal telemetry labels are excluded from end-user views**
    - **Validates: Requirements 4.1**

  - [x] 3.4 Implement Vietnamese mode labels (TypeScript)
    - In `apps/web/lib/user-facing-text.ts`, implement `toModeLabel(internalMode)` mapping internal modes to `Nhanh`/`Tư duy`/`Pro`/`Tự chọn`/`Đầy đủ`.
    - _Requirements: 4.4_

  - [ ]* 3.5 Write example test for mode-label mapping
    - Verify each internal mode maps to its Vietnamese End_User label.
    - _Requirements: 4.4_

  - [x] 3.6 Implement role-gated TelemetryPanel (TypeScript)
    - Create a `TelemetryPanel` wrapper component that renders detailed telemetry only when `role === "admin"` and renders the sanitized summary otherwise; visibility is a pure function of `(role, payload)`.
    - _Requirements: 4.3_

  - [ ]* 3.7 Write property test for telemetry panel visibility (fast-check)
    - **Property 11: Telemetry panel visibility equals admin role**
    - **Validates: Requirements 4.3**

- [ ] 4. DDI output clarity for non-expert users
  - [x] 4.1 Implement ML CareGuard severity aggregation + synthetic-alert fixes (Python)
    - In `services/ml/src/clara_ml/agents/careguard.py`: openFDA-only co-occurrence must not create a standalone synthetic alert (enrich a pre-existing local/RxNav alert only); any `drug_drug` alert ranked `medium` floors overall `risk.level >= medium` (genuine `low` preserved, `high`/`critical` unchanged).
    - _Requirements: 3.2, 3.3_

  - [ ]* 4.2 Write property test for openFDA-only evidence (hypothesis)
    - **Property 6: openFDA-only evidence never creates a standalone alert**
    - **Validates: Requirements 3.2**

  - [ ]* 4.3 Write property test for severity flooring (hypothesis)
    - **Property 7: A medium drug_drug alert floors the overall risk at medium**
    - **Validates: Requirements 3.3**

  - [x] 4.4 Implement ML connector-error suppression (Python)
    - In `services/ml/src/clara_ml/agents/careguard.py`, retain connector errors (e.g., `openfda http_400`) in metadata only when no alternative signal remains; when a valid signal exists, do not surface the connector error.
    - _Requirements: 3.6_

  - [x] 4.5 Implement web DDI end-user projection (TypeScript)
    - In `apps/web/lib/careguard.ts`, add `toDdiUserView(raw)` exposing only `{ riskLevel, alerts, recommendations, sources }` and dropping `mode`, `fallback`, and `source_errors`; hide connector errors when a valid signal remains.
    - _Requirements: 3.1, 3.6_

  - [ ]* 4.6 Write property test for DDI projection (fast-check)
    - **Property 5: DDI end-user projection excludes telemetry**
    - **Validates: Requirements 3.1**

  - [ ]* 4.7 Write property test for connector-error suppression (fast-check)
    - **Property 9: Connector errors are hidden while a valid signal remains**
    - **Validates: Requirements 3.6**

  - [~] 4.8 Implement the two-medicine guard (TypeScript)
    - In `apps/web/lib/careguard.ts`, add `requiresTwoMedicines(medicines)` and guard the careguard page (`apps/web/app/selfmed/ddi/page.tsx`) so `< 2` medicines shows a prompt to add at least two and does NOT call `/careguard/analyze`.
    - _Requirements: 3.5_

  - [ ]* 4.9 Write property test for two-medicine guard (fast-check)
    - **Property 8: DDI checks require at least two medicines**
    - **Validates: Requirements 3.5**

  - [x] 4.10 Implement Vietnamese risk-group messages and recommendations (TypeScript)
    - In `apps/web/lib/careguard.ts`, provide Vietnamese alert messages/recommendations for the common risk groups: bleeding, reduced clopidogrel efficacy, drowsiness/dizziness, hyperkalemia, and myopathy risk.
    - _Requirements: 3.4_

  - [ ]* 4.11 Write example test for DDI risk-group localization
    - Verify each common risk group maps to Vietnamese message + recommendation copy.
    - _Requirements: 3.4_

- [x] 5. Product and Clinical analytics API (FastAPI/Python)
  - [x] 5.1 Implement analytics Pydantic schemas
    - Create the response schemas (`ActiveUsersPoint`, `SurfaceUsage`, `FunnelStage`, `ProductAnalytics`, `VerdictDistribution`, `DdiSeverityDistribution`, `LatencyPercentiles`, `ClinicalAnalytics`) in the analytics module under `services/api/src/clara_api/api/v1/endpoints/`.
    - _Requirements: 7.1, 8.1_

  - [x] 5.2 Implement AnalyticsAggregator with PII-free projection and date windowing
    - Implement `AnalyticsAggregator` (`product_metrics`, `clinical_metrics`, `_within_range`, `_project_pii_free`). Product metrics read existing identity/usage tables; clinical metrics read `FlowEventStore`/`APIMetricsStore` + control-tower config — no new collection path (Requirement 8.2). `_project_pii_free` drops email/name/free-text query/drug lists/raw source_errors.
    - _Requirements: 7.4, 8.2, 11.5_

  - [ ]* 5.3 Write property test for windowing + percentile monotonicity (hypothesis)
    - **Property 12: Date-range windowing and percentile monotonicity**
    - **Validates: Requirements 7.3, 8.3**

  - [ ]* 5.4 Write property test for PII-free aggregation outputs (hypothesis)
    - **Property 13: Outward outputs contain no PII** (Product/Clinical aggregation)
    - **Validates: Requirements 7.4, 11.5**

  - [x] 5.5 Implement Product_Analytics endpoint (admin)
    - Add `GET /system/analytics/product?from=&to=` gated by `require_roles("admin")` returning active-user trend, per-Surface usage counts, funnels, retention, and `has_data`; 422 on invalid range, empty range returns populated shape with `has_data=false`.
    - _Requirements: 7.1, 7.2, 7.4_

  - [x] 5.6 Implement Clinical_Analytics endpoint (admin)
    - Add `GET /system/analytics/clinical?from=&to=` gated by `require_roles("admin")` returning FIDES verdict distribution (incl. blocked-claims count), DDI severity distribution, router confidence buckets, fallback rate, and per-tier latency percentiles derived from existing sources.
    - _Requirements: 8.1, 8.2, 8.4_

  - [ ]* 5.7 Write property test for blocked-claims counting (hypothesis)
    - **Property 15: Blocked CRITICAL claims are counted**
    - **Validates: Requirements 8.4**

  - [ ]* 5.8 Write RBAC contract test for analytics endpoints (hypothesis/pytest)
    - **Property 14: RBAC is enforced on protected endpoints** (both analytics endpoints: 403 for non-admin, authorized for admin)
    - **Validates: Requirements 7.2, 8.1**

  - [x] 5.9 Add analytics settings keys to API config
    - Wire `PRODUCT_ANALYTICS_ENABLED`, `CLINICAL_ANALYTICS_ENABLED`, `ANALYTICS_DEFAULT_RANGE_DAYS` into the API settings so endpoints honor them.
    - _Requirements: 12.4_

- [ ] 6. Analytics admin dashboards (Next.js/TypeScript)
  - [-] 6.1 Build the Product_Analytics dashboard page
    - Create `apps/web/app/admin/analytics/page.tsx` with a date-range picker, the four `AsyncSection` states, active-user trends, per-Surface adoption, and retention; render an explicit empty state when `has_data=false`.
    - _Requirements: 7.3, 7.5_

  - [-] 6.2 Build the Clinical_Analytics dashboard page
    - Create `apps/web/app/admin/analytics/clinical/page.tsx` rendering verification outcomes, DDI severity distribution, and latency percentiles for a selectable date range, kept separate from the existing scribe `/analytics/summary`.
    - _Requirements: 8.3, 8.5_

  - [ ]* 6.3 Write regression test that scribe summary remains intact
    - Verify the new Clinical page does not remove or replace the existing scribe analytics summary.
    - _Requirements: 8.5_

- [x] 7. Analytics SDK facade (web + mobile)
  - [x] 7.1 Implement the web Analytics facade (TypeScript)
    - In `apps/web/lib/analytics/index.ts`, implement `AnalyticsTransport` adapters and `AnalyticsClient` that is a safe no-op without credentials, suppresses all transmission without consent, strips PII from every payload, and identifies users by an opaque deterministic `pseudonymousId`. Include `stripPii` and `pseudonymousId` helpers.
    - _Requirements: 9.1, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 7.2 Write property test for consent suppression (fast-check)
    - **Property 16: Analytics transmission is suppressed without consent**
    - **Validates: Requirements 9.3**

  - [ ]* 7.3 Write property test for safe no-op without credentials (fast-check)
    - **Property 17: Analytics is a safe no-op without credentials**
    - **Validates: Requirements 9.5**

  - [ ]* 7.4 Write property test for pseudonymous identity (fast-check)
    - **Property 18: Users are identified by an opaque pseudonymous id**
    - **Validates: Requirements 9.6**

  - [ ]* 7.5 Write property test for PII-free SDK payloads (fast-check)
    - **Property 13: Outward outputs contain no PII** (Analytics_SDK event payloads)
    - **Validates: Requirements 9.4**

  - [x] 7.6 Implement the mobile Analytics facade (Dart)
    - In `apps/mobile/lib/core/analytics.dart`, mirror the init/identify/capture contract with the same no-op-when-unconfigured, consent suppression, and PII-strip rules; identify by pseudonymous id.
    - _Requirements: 9.2, 9.4_

  - [ ]* 7.7 Write Dart test for mobile analytics consent/no-op + PII strip
    - Verify no transmission without credentials/consent and that PII keys are stripped from payloads.
    - _Requirements: 9.2, 9.4_

- [ ] 8. UX modernization and accessibility (Next.js/TypeScript)
  - [x] 8.1 Implement the shared AsyncSection component
    - Create an `AsyncSection<T>` component rendering exactly one of `loading | empty | error | populated` from a discriminated union; error messages are pre-sanitized.
    - _Requirements: 5.2_

  - [ ]* 8.2 Write property test for async state exclusivity (fast-check)
    - **Property 21: Async sections render exactly one state**
    - **Validates: Requirements 5.2**

  - [-] 8.3 Adjust token pairs to meet AA contrast
    - Tune token values (light/dark) in `apps/web/styles/globals.css` so foreground/background pairs used together meet WCAG 2.1 AA ratios.
    - _Requirements: 5.3_

  - [ ]* 8.4 Write property test for AA contrast (fast-check)
    - **Property 22: Used color token pairs meet AA contrast**
    - **Validates: Requirements 5.3**

  - [-] 8.5 Audit surfaces and replace hardcoded styles with design tokens
    - Replace hardcoded color/spacing/radius/typography values with the existing `--text-*`, `--surface-*`, `--shell-border*`, `--brand-*`, `--radius-*` tokens across Chat, Research, SelfMed, CareGuard, Council, Scribe, Dashboard, and Admin surfaces.
    - _Requirements: 5.1_

  - [-] 8.6 Add visible focus indicators, logical tab order, and Vietnamese labels
    - Define visible focus styles once via tokens and apply to interactive controls; ensure logical tab order; use Vietnamese task-oriented primary-action labels consistent with `/huong-dan`.
    - _Requirements: 5.4, 5.5_

- [ ] 9. Per-surface telemetry-strip + product-event integration (Next.js/TypeScript)
  - [-] 9.1 Integrate Chat surface
    - In `apps/web/app/chat/page.tsx`, apply `stripTelemetryLabels`/`toModeLabel`, wrap detailed telemetry in `TelemetryPanel`, and emit named Chat product events via the consent/PII-guarded analytics client.
    - _Requirements: 4.1, 4.4, 9.1_

  - [-] 9.2 Integrate Research surface
    - In `apps/web/app/research/`, apply `stripTelemetryLabels`/`toModeLabel`, wrap detailed telemetry in `TelemetryPanel`, and emit named Research product events.
    - _Requirements: 4.1, 4.4, 9.1_

  - [-] 9.3 Integrate SelfMed/CareGuard surface
    - In `apps/web/app/selfmed/` (incl. `ddi/page.tsx`) and `apps/web/app/careguard/page.tsx`, render only the `toDdiUserView` projection, wrap detailed telemetry in `TelemetryPanel`, and emit named CareGuard product events.
    - _Requirements: 4.1, 9.1_

  - [-] 9.4 Integrate Council surface
    - In `apps/web/app/council/`, apply `stripTelemetryLabels`, wrap detailed telemetry in `TelemetryPanel`, and emit named Council product events.
    - _Requirements: 4.1, 9.1_

  - [-] 9.5 Integrate Scribe surface
    - In `apps/web/app/scribe/`, apply `stripTelemetryLabels`, wrap detailed telemetry in `TelemetryPanel`, and emit named Scribe product events.
    - _Requirements: 4.1, 9.1_

  - [-] 9.6 Integrate Admin surfaces
    - In `apps/web/app/admin/`, ensure detailed telemetry panels remain admin-only via `TelemetryPanel` and emit named Admin product events on the new analytics dashboards.
    - _Requirements: 4.3, 9.1_

- [x] 10. Mobile persistent session and parity (Flutter/Dart)
  - [x] 10.1 Implement PersistentSessionStore
    - Add `flutter_secure_storage` and replace the in-memory store in `apps/mobile/lib/core/session_store.dart` with `PersistentSessionStore extends ChangeNotifier` exposing `hydrate()`, `setSession(...)`, `clear()`, `isAuthenticated`, `isExpired`, preserving the existing API so screens are unaffected.
    - _Requirements: 10.1, 10.2, 10.3, 10.5_

  - [x] 10.2 Wire launch hydrate flow and sign-out clear
    - On launch (`apps/mobile/lib/app.dart`/`main.dart`) call `hydrate()`: restore the authenticated session if valid; clear the store and route to login if expired/invalid. Sign-out calls `clear()`.
    - _Requirements: 10.2, 10.3, 10.5_

  - [ ]* 10.3 Write Dart test for session persist/restore/clear
    - **Property 19: Session persists and restores across restart, and clears on sign-out**
    - **Validates: Requirements 10.1, 10.2, 10.5**

  - [ ]* 10.4 Write Dart test for expired/invalid token handling
    - **Property 20: Expired or invalid stored tokens clear the store and route to login**
    - **Validates: Requirements 10.3**

  - [x] 10.5 Bring parity screens to functional parity
    - Bring login, dashboard, research, careguard, and council screens (`apps/mobile/lib/screens/`) to functional parity with their web counterparts within mobile-supported actions, reusing existing `ApiClient` methods.
    - _Requirements: 10.4_

  - [ ]* 10.6 Write Dart widget test for parity screens
    - Verify each parity screen renders its core supported actions.
    - _Requirements: 10.4_

- [ ] 11. Safety guardrail preservation regression suite
  - [-] 11.1 Set up the safety regression test module and shared fixtures
    - Create a dedicated safety-regression test module (API/ML) with shared fixtures for roles, consent state, cookie vs bearer auth, emergency keywords, and CRITICAL-claim payloads, so the guardrail invariants below are locked across all tracks.
    - _Requirements: 11.1_

  - [ ]* 11.2 Write property test for RBAC enforcement (hypothesis)
    - **Property 14: RBAC is enforced on protected endpoints** (every endpoint that required a role before this feature)
    - **Validates: Requirements 11.1**

  - [ ]* 11.3 Write property test for consent gate
    - **Property 23: Consent gate precedes medical content**
    - **Validates: Requirements 11.2**

  - [ ]* 11.4 Write property test for emergency fast-path (hypothesis)
    - **Property 24: Emergency symptoms trigger escalation without diagnostic reasoning**
    - **Validates: Requirements 11.3**

  - [ ]* 11.5 Write property test for CRITICAL-claim blocking (hypothesis)
    - **Property 25: Failed CRITICAL claims are blocked**
    - **Validates: Requirements 11.4**

  - [ ]* 11.6 Write property test for CSRF enforcement (hypothesis)
    - **Property 26: CSRF is enforced for cookie-authenticated mutations**
    - **Validates: Requirements 11.6**

  - [ ]* 11.7 Write property test for PII exclusion across outputs (hypothesis)
    - **Property 13: Outward outputs contain no PII** (system metrics, flow events, aggregation outputs)
    - **Validates: Requirements 11.5**

- [~] 12. Backend checkpoint - CLARA_API & CLARA_ML quality gates
  - Ensure `make lint` and the API and ML service test suites pass after the backend batches (Epics 2, 4, 5, 11). Ask the user if questions arise.
  - _Requirements: 1.4, 1.5_

- [~] 13. Final checkpoint - full quality gates
  - Ensure `make lint`, the API/ML suites, the web test suite, and the mobile tests all pass; confirm the Audit_Record fix ordering held and each fix has its regression test. Ask the user if questions arise.
  - _Requirements: 1.3, 1.4, 1.5_

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP, but the Epic 11 safety-preservation suite is strongly recommended and should not be skipped — it locks the medical-safety and privacy invariants the rest of the work must preserve.
- Each task references specific requirement clauses for traceability; property-test tasks additionally cite their design Property number (1–26).
- Property tests use `fast-check` (TypeScript), `hypothesis` (Python), and model/widget tests (Dart), running ≥100 generated iterations and tagged `Feature: product-polish-analytics, Property {n}`.
- The analytics layer extends existing observability (`APIMetricsStore`, `FlowEventStore`, control-tower config, DB models) — no duplicate collection path is introduced (Requirement 8.2).
- UX improvements implemented from the Competitive_Research_Report (task 1.2) reference the originating pattern entry (Requirement 6.4).
- Parallelism: shared modules (sanitizer 3.1/3.4, DDI projection 4.5, analytics facade 7.1, AsyncSection 8.1, aggregator 5.1/5.2) are built before the per-surface integration tasks (Epic 9) and dashboards (Epic 6) that consume them. The per-surface integration tasks (9.1–9.6) write to distinct surface directories and run concurrently. Property tests live in their own files and never collide with implementation files, so they parallelize freely once their target module exists.
- All 26 design properties are covered: P1→2.2, P2→2.5, P3→2.7, P4→3.2, P5→4.6, P6→4.2, P7→4.3, P8→4.9, P9→4.7, P10→3.3, P11→3.7, P12→5.3, P13→5.4/7.5/11.7, P14→5.8/11.2, P15→5.7, P16→7.2, P17→7.3, P18→7.4, P19→10.3, P20→10.4, P21→8.2, P22→8.4, P23→11.3, P24→11.4, P25→11.5, P26→11.6.

## Task Dependency Graph

Same-file tasks are serialized into different waves to avoid write conflicts: `user-facing-text.ts` (3.1→3.4), ML `careguard.py` (4.1→4.4), web `careguard.ts` (4.5→4.10→4.8), analytics endpoints (5.5→5.6), `globals.css` (8.3→8.6), and `chat/page.tsx` (2.3→2.8→9.1). The cross-surface token audit (8.5) is isolated in its own wave so it never collides with the per-surface integration tasks (Epic 9) or the chat-page edits.

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5", "2.1", "2.4", "2.6", "3.1", "3.6", "4.1", "4.5", "5.1", "7.1", "7.6", "8.1", "8.3", "10.1", "11.1"] },
    { "id": 1, "tasks": ["1.6", "2.2", "2.3", "2.5", "2.7", "3.2", "3.3", "3.4", "3.7", "4.2", "4.3", "4.4", "4.6", "4.7", "4.10", "5.2", "5.9", "7.2", "7.3", "7.4", "7.5", "7.7", "8.2", "8.4", "10.2", "10.3", "10.4", "10.5", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7"] },
    { "id": 2, "tasks": ["2.8", "3.5", "4.8", "4.11", "5.3", "5.4", "5.5", "8.6", "10.6"] },
    { "id": 3, "tasks": ["2.9", "4.9", "5.6", "8.5"] },
    { "id": 4, "tasks": ["5.7", "5.8", "6.1", "6.2"] },
    { "id": 5, "tasks": ["6.3", "9.1", "9.2", "9.3", "9.4", "9.5", "9.6"] }
  ]
}
```
