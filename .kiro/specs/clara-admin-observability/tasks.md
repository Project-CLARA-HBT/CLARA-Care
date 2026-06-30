# Implementation Plan: CLARA Admin & Observability

## Overview

This plan converts the design into a set of additive, default-off, highly
parallelizable coding tasks across `services/api` (FastAPI/Python),
`services/ml` (FastAPI/Python), and `apps/web` (Next.js/TypeScript). It
**completes** the existing admin/observability scaffolding rather than rebuilding
it: every new capability is feature-flagged off, and flags-off behavior equals
the pre-feature baseline.

The plan is organized into ten epics that map to the design's component tracks
plus the safety-preservation regression suite and the quality gates. Shared
modules (percentiles, alert engine, admin audit, durable sink, tracing) are
built once in their own files so they can run in the same wave as unrelated
work; per-surface web integration tasks are split out so independent surfaces
can be polished in parallel.

- Epic 1 — Configuration, feature flags & migrations (additive, default-off)
- Epic 2 — RBAC audit & route-dependency lock (Requirement 1)
- Epic 3 — Knowledge ingestion controls & durable status (Requirements 2, 3)
- Epic 4 — RAG source registry governance (Requirement 4)
- Epic 5 — Metrics percentiles & ecosystem health (Requirement 5)
- Epic 6 — Distributed tracing / OpenTelemetry export (Requirement 6)
- Epic 7 — Durable observability store & analytics correctness (Requirements 7, 10)
- Epic 8 — Alert engine: evaluate, deliver, acknowledge (Requirement 8)
- Epic 9 — Admin-action audit trail (Requirement 9)
- Epic 10 — Web admin/observability surface completion + no-PII (Requirements 2.5, 5.6, 11)
- Epic 11 — Safety & flags-off regression suite (Requirements 11, 12)
- Epic 12 — Backend checkpoint
- Epic 13 — Final checkpoint

Testing follows the dual approach from the design: `hypothesis` (Python) and
`fast-check` (TypeScript). Property-test sub-tasks are marked optional with `*`,
labeled **[PBT]**, each is its own sub-task, and each cites its design Property
number and the requirement clause it validates. Tasks are scoped so that 12+ can
be dispatched to parallel subagents.

Testing prerequisites (set up as part of the first task that needs them, not as standalone tasks):
- Python: `hypothesis` is already used in `services/api/tests` and `services/ml/tests`; reuse it.
- Web: `fast-check` + the existing Vitest runner in `apps/web` are already configured; reuse them.

## Tasks

- [x] 1. Configuration, feature flags, and migrations
  - [x] 1.1 Add API feature flags and settings keys
    - In `services/api/src/clara_api/core/config.py`, add `admin_rag_ingestion_controls_enabled`, `admin_observability_percentiles_enabled`, `admin_observability_persistent_store_enabled`, `admin_observability_alerting_enabled`, `admin_observability_alert_webhook_url`, and `admin_audit_log_enabled`, all defaulting to off/empty (preserving baseline).
    - _Requirements: 12.1, 12.2_

  - [x] 1.2 Document all new flags and keys in `.env.example`
    - Add the API flags from 1.1 and confirm the existing ML `OTEL_EXPORT_ENABLED`/`OTEL_EXPORT_ENDPOINT`/`OTEL_EXPORT_TIMEOUT_SECONDS` keys are documented as the tracing switches; ensure no duplicate key definitions.
    - _Requirements: 12.3_

  - [x] 1.3 Add additive migrations for the new tables
    - Create a single Alembic migration adding `admin_audit_log`, `flow_event_archive`, and `alert_state` per the design data models, each with a downgrade. No destructive change to existing tables.
    - _Requirements: 9.1, 7.1, 8.4, 12.1_

  - [ ]* 1.4 **[PBT]** Write flags-off equivalence property test (hypothesis)
    - **Property 26: Flags-off equivalence**
    - **Validates: Requirements 12.2, 12.4**

- [x] 2. RBAC audit and route-dependency lock
  - [x] 2.1 Audit and normalize admin/observability role dependencies
    - Confirm every admin mutation route (`admin_rag.py` ingestion/eval/sources, plus new alert-ack and audit-read routes) uses `require_roles("admin")`, and the operational reads (`/system/metrics`, `/dependencies`, `/ecosystem`, `/sources`) use `require_roles("doctor")`. Fix any drift.
    - _Requirements: 1.1, 1.4, 1.5_

  - [ ]* 2.2 **[PBT]** Write property test for admin-mutation RBAC (hypothesis)
    - **Property 1: Admin mutations require the admin role**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 2.3 **[PBT]** Write property test for operational-endpoint RBAC (hypothesis)
    - **Property 2: Operational telemetry admits doctor and admin only**
    - **Validates: Requirements 1.4**

  - [ ]* 2.4 **[PBT]** Write route-table role-dependency test (hypothesis/pytest)
    - **Property 3: Every new admin/observability route has a role dependency**
    - **Validates: Requirements 1.5**

  - [ ]* 2.5 **[PBT]** Write property test for CSRF on cookie-auth admin mutations (hypothesis)
    - **Property 4: CSRF is enforced for cookie-authenticated admin mutations**
    - **Validates: Requirements 1.6**

- [ ] 3. Knowledge ingestion controls and durable status
  - [x] 3.1 Gate live ingestion controls and surface honest degradation
    - In `services/api/src/clara_api/api/v1/endpoints/admin_rag.py`, gate the ingestion/eval control path behind `admin_rag_ingestion_controls_enabled` (404 feature-disabled when off), and add an explicit `degraded` marker derived from the existing `fallback`/`ml_available` fail-soft fields so a successful ML response is never marked degraded.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 12.4_

  - [ ]* 3.2 **[PBT]** Write property test for ML-availability degraded marker (hypothesis)
    - **Property 5: ML availability determines the degraded marker**
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 3.3 **[PBT]** Write property test for the ingestion record cap (hypothesis)
    - **Property 6: A single ingestion run is bounded by the record cap**
    - **Validates: Requirements 3.5**

  - [x] 3.4 Surface degraded/retry state on the Knowledge Sources web page
    - In `apps/web/app/admin/knowledge-sources/page.tsx`, render an explicit "unavailable, retry" state when the ingestion/registry payload is `degraded`/`fallback`, keeping the four `AsyncSection` states and `sanitizeUpstreamError` for failures.
    - _Requirements: 2.4, 2.5, 3.3_

  - [ ]* 3.5 Write example test for knowledge-source endpoint contracts
    - Verify admin create/upload/list-documents/toggle-status return their documented shapes and persist status.
    - _Requirements: 2.1, 2.2_

- [x] 4. RAG source registry governance
  - [x] 4.1 Extend the source contract with license and attribution
    - In `admin_rag.py`, add `license_code` and `attribution` to the declared `SourceInfo` contract (already passed through `extra="allow"`) so they are first-class in the list response.
    - _Requirements: 4.1_

  - [x] 4.2 Render license/attribution in the registry UI
    - In `apps/web/app/admin/knowledge-sources/page.tsx`, display each source's `license_code` and `attribution` alongside the trust-tier/weight/enabled controls.
    - _Requirements: 4.5_

  - [ ]* 4.3 **[PBT]** Write property test for trust-tier band validation (hypothesis)
    - **Property 7: Trust tier accepts only the closed band {1,2,3,4}**
    - **Validates: Requirements 4.2**

  - [ ]* 4.4 **[PBT]** Write property test for non-negative weight validation (hypothesis)
    - **Property 8: Weight accepts only non-negative values**
    - **Validates: Requirements 4.3**

  - [ ]* 4.5 **[PBT]** Write property test for partial-update field isolation (hypothesis)
    - **Property 9: Partial source updates touch only provided fields**
    - **Validates: Requirements 4.4**

- [x] 5. Metrics percentiles and ecosystem health
  - [x] 5.1 Implement per-route latency percentiles
    - Add a bounded per-route latency sample ring and a `MetricsPercentiles.percentiles(route)` projection (reusing the monotonic `_percentile`), gated by `admin_observability_percentiles_enabled`; expose p50/p90/p99 alongside the existing average in the metrics surface (off → average-only baseline).
    - _Requirements: 5.1, 5.2, 12.2_

  - [ ]* 5.2 **[PBT]** Write property test for percentile monotonicity (hypothesis)
    - **Property 10: Latency percentiles are monotonic**
    - **Validates: Requirements 5.2, 5.3**

  - [x] 5.3 Extract the flow-event health classifier as a pure function
    - In `services/api/src/clara_api/api/v1/endpoints/system.py`, factor the `/ecosystem` flow-event `ok/degraded/down` decision (from latest-event age + count + error ratio) into a pure, unit-testable function without changing the surfaced behavior.
    - _Requirements: 5.4, 5.5_

  - [ ]* 5.4 **[PBT]** Write property test for flow-event health classification (hypothesis)
    - **Property 11: Flow-event health classification follows the staleness rule**
    - **Validates: Requirements 5.5**

  - [x] 5.5 Complete the Observability dashboard async states
    - In `apps/web/components/admin/admin-observability-panel.tsx`, ensure loading/empty/error/populated states are rendered and error states exclude stack traces (via `sanitizeUpstreamError`); surface the new per-route percentiles.
    - _Requirements: 5.6_

- [x] 6. Distributed tracing / OpenTelemetry export
  - [x] 6.1 Wire the OTEL tracer behind the existing config keys
    - Create `services/ml/src/clara_ml/observability/tracing.py` with `init_tracing(settings)` that returns a no-op unless `otel_export_enabled` and a non-empty `otel_export_endpoint` are set, and a `request_span(...)` context manager emitting a top-level span plus stage child spans, with all attributes passed through `strip_pii`. Initialize once at app startup.
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 6.2 Make export failures non-fatal
    - Ensure exporter init/flush/export errors are caught inside the tracing wrapper so a request is always served and the failure never reaches the response.
    - _Requirements: 6.5_

  - [ ]* 6.3 **[PBT]** Write property test for trace no-op when disabled/unconfigured (hypothesis)
    - **Property 12: Trace export is a no-op when disabled or unconfigured**
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 6.4 **[PBT]** Write property test for PII-free span attributes (hypothesis)
    - **Property 13: Span attributes contain no PII**
    - **Validates: Requirements 6.4**

  - [ ]* 6.5 Write example test for span emission and export-failure resilience
    - With a recording exporter assert a per-request span + stage children are emitted (6.1); with a failing exporter assert the request still completes (6.5).
    - _Requirements: 6.1, 6.5_

- [x] 7. Durable observability store and analytics correctness
  - [x] 7.1 Implement the opt-in durable flow-event sink
    - Create `FlowEventSink` (gated by `admin_observability_persistent_store_enabled`) that mirrors each appended Flow_Event as a `_project_pii_free`-projected `flow_event_archive` row and supports a `query(start, end)` read; the aggregator reads from the sink when enabled, else from the in-memory `FlowEventStore`.
    - _Requirements: 7.1, 7.2, 11.1_

  - [ ]* 7.2 **[PBT]** Write property test for durable-store toggle equivalence (hypothesis)
    - **Property 15: Durable store toggles without behavioral change**
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 7.3 **[PBT]** Write property test for analytics range windowing (hypothesis)
    - **Property 16: Analytics windowing includes only in-range data**
    - **Validates: Requirements 7.3, 7.4, 7.6**

  - [ ]* 7.4 **[PBT]** Write property test for blocked-claims counting (hypothesis)
    - **Property 23: Blocked CRITICAL claims are counted**
    - **Validates: Requirements 10.2**

  - [ ]* 7.5 Write example tests for analytics contracts and scribe-summary regression
    - Verify the Clinical_Analytics and Product_Analytics response shapes (10.1, 10.4), that Clinical is derived from the existing observability sources (10.3), non-admin → 403 (10.6), and that the existing scribe `/analytics/summary` remains intact (10.5).
    - _Requirements: 10.1, 10.3, 10.4, 10.5, 10.6_

- [x] 8. Alert engine: evaluate, deliver, acknowledge
  - [x] 8.1 Implement the alert engine and threshold rules
    - Create `services/api/src/clara_api/observability/alerts.py` with `Alert`, `AlertEngine.evaluate(...)` (ML unreachable/degraded, API 5xx warn/critical, flow stale/missing → stable id + bounded severity), `reconcile(...)` (firing/cleared transitions persisted to `alert_state`), and `acknowledge(alert_id)`, all gated by `admin_observability_alerting_enabled`.
    - _Requirements: 8.1, 8.4, 8.5_

  - [x] 8.2 Implement no-PII webhook delivery
    - Add `deliver(fired)` posting a `_project_pii_free` payload to `admin_observability_alert_webhook_url` only on a not-firing → firing transition; no URL configured → in-app only; delivery failures are swallowed and never propagated.
    - _Requirements: 8.2, 8.3, 8.6, 11.2_

  - [x] 8.3 Add the alert-acknowledge endpoint and wire the web control
    - Add an admin-gated `POST` acknowledge endpoint keyed by stable alert id and an acknowledge control on the Observability surface.
    - _Requirements: 8.4, 1.1_

  - [ ]* 8.4 **[PBT]** Write property test for stable, bounded alert production (hypothesis)
    - **Property 17: Threshold rules produce stable, bounded alerts**
    - **Validates: Requirements 8.1**

  - [ ]* 8.5 **[PBT]** Write property test for alert dedupe and single-fire delivery (hypothesis)
    - **Property 18: Alerts are deduplicated and fire delivery once per transition**
    - **Validates: Requirements 8.3, 8.5**

  - [ ]* 8.6 **[PBT]** Write property test for acknowledge state machine (hypothesis)
    - **Property 19: Acknowledged alerts are not re-presented until clear-and-refire**
    - **Validates: Requirements 8.4**

  - [ ]* 8.7 **[PBT]** Write property test for delivery-failure resilience (hypothesis)
    - **Property 20: Alert delivery failure never breaks the request**
    - **Validates: Requirements 8.6**

- [x] 9. Admin-action audit trail
  - [x] 9.1 Implement the append-only admin audit module
    - Create `services/api/src/clara_api/observability/admin_audit.py` with `record_admin_action(db, actor_ref, action, target, outcome, meta)` (insert-only, opaque actor ref, `_project_pii_free` meta) and `list_admin_actions(db)` (most-recent-first), gated by `admin_audit_log_enabled`. No update/delete path.
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 9.2 Instrument every admin mutation with an audit write
    - Call `record_admin_action(...)` from knowledge-source create/upload/document-status, RAG source update, ingestion/eval trigger, and alert acknowledge — recording both success and failure outcomes.
    - _Requirements: 9.1, 9.5_

  - [x] 9.3 Add the admin audit-read endpoint and web view
    - Add an `ADMIN_ROLE_DEP` read endpoint returning records most-recent-first and a simple admin audit list view.
    - _Requirements: 9.4_

  - [ ]* 9.4 **[PBT]** Write property test for one-audit-record-per-mutation (hypothesis)
    - **Property 21: Every admin mutation appends exactly one audit record**
    - **Validates: Requirements 9.1, 9.5**

  - [ ]* 9.5 **[PBT]** Write property test for append-only ordering (hypothesis)
    - **Property 22: The admin audit trail is append-only and ordered**
    - **Validates: Requirements 9.2, 9.4**

- [x] 10. Web admin/observability surface completion and no-PII
  - [x] 10.1 Lock admin-only detailed telemetry rails
    - Ensure detailed telemetry across admin surfaces is wrapped so it renders only for `admin` and is passed through the role-gated sanitizer (`sanitize_telemetry`/`strip_pii`); non-admin sees only the sanitized summary.
    - _Requirements: 11.4_

  - [x] 10.2 Confirm coarse, no-PII admin product events
    - Verify each Admin_Surface emits only its coarse `admin_*_viewed` event (surface/view/counts) via `lib/analytics/events.ts` and never passes PII props.
    - _Requirements: 11.5_

  - [ ]* 10.3 **[PBT]** Write property test for PII-free outward outputs (hypothesis)
    - **Property 24: Outward outputs contain no PII** (analytics aggregation, alert payload, audit meta, archived flow event)
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.5**

  - [ ]* 10.4 **[PBT]** Write property test for admin-only PII-stripped telemetry (hypothesis/fast-check)
    - **Property 25: Detailed telemetry is admin-only and PII-stripped**
    - **Validates: Requirements 11.4**

  - [ ]* 10.5 Write fast-check test for sanitized error strings on admin surfaces
    - Verify any raw upstream error rendered on the Knowledge Sources / Observability pages is sanitized (no codes/stack/URLs).
    - _Requirements: 2.4, 5.6_

- [x] 11. Safety and flags-off regression suite
  - [x] 11.1 Set up the safety-regression module and shared fixtures
    - Create a dedicated regression test module with shared fixtures for roles, cookie-vs-bearer auth, flag matrices, and adversarial-PII payloads, so the RBAC, no-PII, and flags-off invariants are locked across all tracks.
    - _Requirements: 11.1, 12.2_

  - [ ]* 11.2 Write the no-PII CI guard
    - Feed adversarial PII into analytics records, alert contexts, audit meta, and span attributes; assert every persisted/emitted projection drops it.
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ]* 11.3 Write the flags-off baseline-equivalence regression test
    - With all new flags off, assert the metrics shape, admin RAG responses, analytics shapes, and ecosystem alerts equal the pre-feature baseline, and that flag-disabled gated endpoints return the 404 feature-disabled shape.
    - _Requirements: 12.2, 12.4_

- [x] 12. Backend checkpoint — CLARA_API & CLARA_ML quality gates
  - Ensure `make lint` and the API and ML service test suites pass after the backend batches (Epics 1–9, 11). Ask the user if questions arise.
  - _Requirements: 12.5_

- [x] 13. Final checkpoint — full quality gates
  - Ensure `make lint`, the API/ML suites, and the web test suite all pass; confirm every new capability is default-off, the no-PII and RBAC invariants hold, and each property has its test. Ask the user if questions arise.
  - _Requirements: 11.1, 12.2, 12.5_

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP, but the Epic 11 safety/flags-off suite is strongly recommended and should not be skipped — it locks the RBAC, no-PII, and backward-compatibility invariants the rest of the work must preserve.
- Each task references specific requirement clauses for traceability; property-test (**[PBT]**) tasks additionally cite their design Property number (1–26).
- Property tests use `hypothesis` (Python) and `fast-check` (TypeScript), run ≥100 generated iterations, and are tagged `Feature: clara-admin-observability, Property {n}`.
- All new capabilities are additive and default-off; with every new flag off, request/response shapes and side effects equal the pre-feature baseline (Requirement 12.2).
- The observability/analytics layer extends the existing primitives (`APIMetricsStore`, `FlowEventStore`, `AnalyticsAggregator`, the role-gated `research_telemetry` sanitizer, the compliance redaction projection) — no duplicate collection path is introduced (Requirements 10.3, 11).
- All 26 design properties are covered: P1→2.2, P2→2.3, P3→2.4, P4→2.5, P5→3.2, P6→3.3, P7→4.3, P8→4.4, P9→4.5, P10→5.2, P11→5.4, P12→6.3, P13→6.4, P14→6.5/8.7, P15→7.2, P16→7.3, P17→8.4, P18→8.5, P19→8.6, P20→8.7, P21→9.4, P22→9.5, P23→7.4, P24→10.3, P25→10.4, P26→1.4/11.3.

## Task Dependency Graph

Same-file tasks are serialized into different waves to avoid write conflicts: `admin_rag.py` (3.1→4.1), `system.py` (5.3 isolated), and the Knowledge Sources web page (3.4→4.2). Shared modules (`tracing.py` 6.1, `alerts.py` 8.1, `admin_audit.py` 9.1, `FlowEventSink` 7.1, `MetricsPercentiles` 5.1) are built before the integration and instrumentation tasks (8.2/8.3, 9.2/9.3) that consume them. Property tests live in their own files and parallelize freely once their target module exists.

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3", "2.1", "5.1", "5.3", "6.1", "7.1", "8.1", "9.1", "11.1"] },
    { "id": 1, "tasks": ["1.2", "1.4", "2.2", "2.3", "2.4", "2.5", "3.1", "5.2", "5.4", "6.2", "6.3", "6.4", "7.2", "7.3", "7.4", "8.4", "8.5", "8.6", "8.7", "9.4", "9.5"] },
    { "id": 2, "tasks": ["3.2", "3.3", "3.4", "3.5", "4.1", "5.5", "6.5", "7.5", "8.2", "9.2", "10.1", "10.3", "10.4", "11.2", "11.3"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "4.5", "8.3", "9.3", "10.2", "10.5"] },
    { "id": 4, "tasks": ["12"] },
    { "id": 5, "tasks": ["13"] }
  ]
}
```
