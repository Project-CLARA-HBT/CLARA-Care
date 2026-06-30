# Requirements Document

## Introduction

This feature upgrades the CLARA-Care **Admin & Observability surface** to fully
functional, production-grade quality. It targets the existing admin control
tower (`apps/web/app/admin/*`, `apps/web/components/admin/*`), the admin/observability
API endpoints (`services/api/src/clara_api/api/v1/endpoints/{admin_rag,system,analytics}.py`),
the in-memory observability primitives (`APIMetricsStore`, `FlowEventStore`),
the declared-but-unused ML OpenTelemetry configuration, and the web analytics
layer (`apps/web/lib/analytics/*`).

The work closes the gap between the **shipped scaffolding** and a
**production-grade** admin plane across four concerns:

1. **Admin operations completeness** — knowledge-source management, RAG source
   registry governance, and knowledge ingestion controls that are RBAC-gated,
   durably backed, and surface real status instead of permanent fail-soft.
2. **Observability** — system health, error rates, per-route latency
   percentiles, dependency health, and distributed traces, backed by a durable
   store that honors a selectable date range beyond the current 1,000-event
   in-memory window.
3. **Operability** — threshold-based alerting with a delivery sink and
   acknowledge/dedupe state, plus an append-only, no-PII admin-action audit
   trail for every admin mutation.
4. **Analytics integrity** — Product_Analytics and Clinical_Analytics remain
   PII-free and correct over a selectable range, derived from existing
   observability rather than a duplicate collection path.

The work is **additive and feature-flagged**: with every new flag off, the
system behaves exactly as today. It preserves every existing safety invariant —
RBAC via `require_roles(...)`, no-PII telemetry, the role-gated research
telemetry sanitizer, and the consent/CSRF guards.

The existing surfaces (`/system/metrics`, `/system/ecosystem`,
`/system/analytics/*`, the knowledge-sources page, `admin_rag.py`) are
**extended and completed**, not duplicated.

## Glossary

- **CLARA_Web**: The Next.js web application (`apps/web`).
- **CLARA_API**: The FastAPI API gateway service (`services/api`) that owns auth, RBAC, proxying, metrics, and flow events.
- **CLARA_ML**: The FastAPI ML orchestration service (`services/ml`) that owns the RAG ingestion plane, the `kb_source_registry`, and the eval harness.
- **Admin_User**: A user whose role is `admin`. Under `require_roles(...)`, `admin` is granted implicit access to every guarded route.
- **Operational_User**: A user with role `doctor` who is permitted read access to operational telemetry surfaces today (`/system/metrics`, `/system/dependencies`, `/system/ecosystem`, `/system/sources`).
- **End_User**: A non-administrative user with role `normal`, `researcher`, or `doctor`.
- **Admin_Surface**: A page under `apps/web/app/admin/*`: Overview, Knowledge Sources, Answer Flow, Observability, Product Analytics, Clinical Analytics, RAG Eval, RAG Ingestion, RAG Sources, Source Hub, DSAR.
- **Knowledge_Source**: A persistent, user-authored corpus container (`KnowledgeSource`) with uploaded `KnowledgeSourceDocument` rows, managed through CLARA_API.
- **RAG_Source_Registry**: The `kb_source_registry` entries owned by CLARA_ML, governing each retrieval connector's `enabled` flag, `trust_tier` (1–4), `weight`, `license_code`, and `attribution`.
- **Ingestion_Job**: An admin-triggered ingestion run for one RAG_Source_Registry source, identified by a `job_id`, with a queryable status (`fetched`, `inserted`, `updated`, `skipped`, `degraded`, `errors`).
- **Observability_Store**: The runtime telemetry source: the `APIMetricsStore` snapshot (`requests_total`, `by_route`, `by_status`, `avg_latency_ms`) and the bounded in-memory `FlowEventStore` deque of flow events.
- **Flow_Event**: A `FlowEventStore` record carrying `source`, `user_id`, `role`, `intent`, `model_used`, a `timestamp`, and an `event` dict that includes `stage`/`status` (verification verdicts, `blocked`, `escalated`, `fallback`), `confidence`, and latency.
- **Trace**: A distributed-tracing span emitted by CLARA_ML when OpenTelemetry export is enabled, correlated by a request/trace identifier.
- **Alert**: A threshold-derived operational signal (e.g. ML unreachable, API 5xx ratio high, flow events stale) with a severity, a stable id, and an acknowledged state.
- **Alert_Sink**: An outbound delivery target (an HTTP webhook URL) that receives a no-PII alert payload when alerting is enabled and a sink is configured.
- **Admin_Audit_Record**: An append-only, no-PII record of an admin mutation (actor reference, action, target, timestamp, outcome).
- **Product_Analytics**: Internal usage analytics (active users, per-Surface usage, funnels, retention) served to Admin_Users.
- **Clinical_Analytics**: Quality and pipeline-health analytics (FIDES verdict distribution, DDI severity distribution, router confidence, fallback rate, per-tier latency percentiles, blocked-claims count) served to Admin_Users.
- **Telemetry**: Internal diagnostic data such as runtime mode, retrieval stack, source errors, verdicts, and trace metadata.
- **PII**: Personally Identifiable Information, including names, emails, free-text queries/answers, transcripts, drug lists, and patient content.
- **RBAC**: Role-Based Access Control enforced by CLARA_API via `require_roles(...)`.
- **Feature_Flag**: An additive, default-off configuration switch; when off, the corresponding behavior equals the pre-feature baseline.

## Requirements

### Requirement 1: RBAC-gated admin operations

**User Story:** As a security owner, I want every admin operation and observability surface gated by a consistent, documented role policy, so that no privileged control or telemetry leaks to an unauthorized caller.

#### Acceptance Criteria

1. THE CLARA_API SHALL gate every admin mutation endpoint (knowledge-source create/upload/document-status, RAG source update, ingestion trigger, eval trigger, alert acknowledge, audit read) behind `require_roles("admin")`.
2. IF a request to an admin mutation endpoint presents a non-admin role, THEN THE CLARA_API SHALL respond with HTTP 403.
3. IF a request to an admin or operational telemetry endpoint presents no valid token, THEN THE CLARA_API SHALL respond with HTTP 401.
4. WHERE an endpoint is documented as Operational_User-readable (`/system/metrics`, `/system/dependencies`, `/system/ecosystem`, `/system/sources`), THE CLARA_API SHALL admit `doctor` and `admin` roles and SHALL reject `normal` and `researcher` with HTTP 403.
5. THE CLARA_API SHALL NOT expose any new admin or observability endpoint without a role dependency.
6. WHEN a mutating admin request uses cookie authentication, THE CLARA_API SHALL continue to enforce CSRF protection.

### Requirement 2: Knowledge-source management completeness

**User Story:** As an Admin_User, I want complete control over knowledge sources and their documents, so that I can curate the corpus that grounds CLARA's answers.

#### Acceptance Criteria

1. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL allow creating a Knowledge_Source, uploading a document to it, and listing its documents.
2. WHEN an Admin_User toggles a document's active status, THE CLARA_API SHALL persist the new status and THE CLARA_Web SHALL reflect it without a full reload.
3. WHEN a Knowledge_Source has no documents, THE CLARA_Web SHALL render an explicit empty state rather than a blank panel.
4. WHEN a knowledge-source operation fails upstream, THE CLARA_Web SHALL render a sanitized, user-readable message that excludes raw error codes, stack traces, and internal URLs.
5. THE CLARA_Web SHALL render the Knowledge Sources page through the loading, empty, error, and populated async states for each asynchronously loaded section.

### Requirement 3: Knowledge ingestion controls and durable status

**User Story:** As an Admin_User, I want to trigger ingestion for a source and see its real status, so that I can manage corpus freshness instead of staring at a permanently degraded panel.

#### Acceptance Criteria

1. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL accept an Ingestion_Job trigger for a named RAG_Source_Registry source and return a `job_id`.
2. WHEN an Admin_User polls an Ingestion_Job by `job_id`, THE CLARA_API SHALL return its status counters (`fetched`, `inserted`, `updated`, `skipped`, `degraded`, `errors`).
3. IF CLARA_ML is unavailable when an ingestion control is invoked, THEN THE CLARA_API SHALL return a degraded payload explicitly flagged so THE CLARA_Web can show an "unavailable, retry" state rather than presenting stale success.
4. WHEN CLARA_ML returns a successful ingestion control response, THE CLARA_API SHALL NOT mark the payload as degraded or fallback.
5. THE CLARA_API SHALL bound a single admin-triggered ingestion run to the configured maximum record cap so a manual trigger cannot exhaust host resources.

### Requirement 4: RAG source registry governance

**User Story:** As an Admin_User, I want to govern each retrieval connector's authority and licensing, so that high-trust regulated sources outrank low-trust ones and attribution obligations stay visible.

#### Acceptance Criteria

1. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL list RAG_Source_Registry entries with their `enabled` flag, `trust_tier`, `weight`, `fetch_mode`, `license_code`, and `attribution`.
2. WHEN an Admin_User updates a source's `trust_tier`, THE CLARA_API SHALL accept only values in the closed band `{1, 2, 3, 4}` and SHALL reject out-of-band values with HTTP 422.
3. WHEN an Admin_User updates a source's `weight`, THE CLARA_API SHALL accept only values greater than or equal to zero.
4. WHEN an Admin_User submits a partial source update, THE CLARA_API SHALL apply only the explicitly provided fields and SHALL leave unspecified fields unchanged.
5. THE CLARA_Web SHALL display each source's `license_code` and `attribution` so attribution obligations are visible in the UI.

### Requirement 5: System health and observability dashboards

**User Story:** As an Operational_User, I want a system health dashboard showing error rates, latency percentiles, dependency health, and flow-event freshness, so that I can detect and triage incidents.

#### Acceptance Criteria

1. WHERE the requesting user holds the `doctor` or `admin` role, THE CLARA_API SHALL expose API request totals, status-code distribution, error rate, and 5xx server-error rate.
2. THE CLARA_API SHALL expose per-route latency percentiles (p50, p90, p99) in addition to the existing average latency.
3. WHEN computed for a fixed sample set, THE CLARA_API SHALL guarantee the latency percentiles are monotonically non-decreasing (p50 ≤ p90 ≤ p99).
4. THE CLARA_API SHALL report ML dependency reachability and health, and flow-event stream freshness (minutes since the latest event), through the ecosystem health surface.
5. WHEN the latest flow event is older than the staleness threshold or no flow events exist, THE CLARA_API SHALL mark the flow-event stream health as degraded or down accordingly.
6. WHEN an Operational_User opens the Observability dashboard, THE CLARA_Web SHALL render the loading, empty, error, and populated async states and SHALL exclude internal stack traces from any error state.

### Requirement 6: Distributed tracing and OpenTelemetry export

**User Story:** As an SRE, I want CLARA_ML to emit distributed traces when configured, so that I can follow a request across pipeline stages and locate latency.

#### Acceptance Criteria

1. WHERE OpenTelemetry export is enabled and an export endpoint is configured, THE CLARA_ML SHALL emit a Trace span for each top-level request with stage child spans.
2. WHERE OpenTelemetry export is disabled, THE CLARA_ML SHALL NOT initialize an exporter and SHALL behave exactly as today.
3. WHERE no export endpoint is configured, THE CLARA_ML SHALL operate normally with trace export disabled (graceful no-op).
4. THE CLARA_ML SHALL exclude PII from every span attribute, including names, emails, free-text queries/answers, transcripts, and drug lists.
5. IF the trace exporter is unavailable or errors, THEN THE CLARA_ML SHALL continue to serve the request and SHALL NOT propagate the export failure into the response.

### Requirement 7: Durable observability store and date-range correctness

**User Story:** As an Admin_User, I want analytics and observability to cover a selectable date range that survives restarts, so that the numbers are trustworthy beyond the last 1,000 in-memory events.

#### Acceptance Criteria

1. WHERE the durable observability store is enabled, THE CLARA_API SHALL persist Flow_Event records so they remain queryable across process restarts and beyond the in-memory `FlowEventStore` capacity.
2. WHERE the durable observability store is disabled, THE CLARA_API SHALL fall back to the existing in-memory `FlowEventStore` with no behavioral change.
3. WHEN an Admin_User requests analytics over a `from`/`to` range, THE CLARA_API SHALL include only data points whose timestamp falls within the inclusive range and SHALL exclude out-of-range data.
4. IF a requested range has `from` after `to`, THEN THE CLARA_API SHALL respond with HTTP 422.
5. WHEN a requested range omits `from`/`to`, THE CLARA_API SHALL default to the trailing configured window ending today (UTC).
6. WHEN a requested range contains no data, THE CLARA_API SHALL return the populated response shape with `has_data=false` to drive an explicit empty state.

### Requirement 8: Alerting hooks with delivery and acknowledge state

**User Story:** As an Operational_User, I want operational alerts delivered to a sink and acknowledgeable, so that incidents are noticed and tracked instead of recomputed and forgotten on every page load.

#### Acceptance Criteria

1. WHERE alerting is enabled, THE CLARA_API SHALL evaluate threshold rules (ML unreachable/degraded, API 5xx ratio above warn/critical, flow events stale or missing) and produce Alerts with a stable id and a severity of `info`, `warning`, or `critical`.
2. WHERE alerting is enabled and an Alert_Sink is configured, THE CLARA_API SHALL deliver a no-PII alert payload to the Alert_Sink when an alert transitions into a firing state.
3. WHERE alerting is enabled and no Alert_Sink is configured, THE CLARA_API SHALL evaluate and surface alerts in-app and SHALL NOT attempt outbound delivery (graceful no-op).
4. WHEN an Admin_User acknowledges an Alert by its stable id, THE CLARA_API SHALL persist the acknowledged state so the same alert is not re-presented as new until it clears and re-fires.
5. THE CLARA_API SHALL deduplicate Alerts by stable id within an evaluation window so a single persistent condition does not emit duplicate firing deliveries.
6. IF Alert_Sink delivery fails, THEN THE CLARA_API SHALL continue serving requests and SHALL NOT propagate the delivery failure into any user-facing response.

### Requirement 9: Admin-action audit trail

**User Story:** As a compliance owner, I want every admin mutation recorded in an append-only, no-PII audit trail, so that privileged changes are accountable and reviewable.

#### Acceptance Criteria

1. WHEN an Admin_User performs a mutation (knowledge-source create/upload/document-status, RAG source update, ingestion trigger, eval trigger, alert acknowledge), THE CLARA_API SHALL append one Admin_Audit_Record capturing an opaque actor reference, the action, the target identifier, a timestamp, and the outcome.
2. THE CLARA_API SHALL treat the admin audit trail as append-only: existing records are never updated or deleted by application code.
3. THE CLARA_API SHALL exclude PII from every Admin_Audit_Record, including names, emails, free-text content, and drug lists.
4. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL expose a read endpoint that lists Admin_Audit_Records ordered most-recent-first.
5. IF an admin mutation fails, THEN THE CLARA_API SHALL still append an Admin_Audit_Record recording the failed outcome.

### Requirement 10: Clinical and product analytics correctness

**User Story:** As an Admin_User, I want clinical-quality and product analytics derived correctly from existing observability, so that I can monitor verification health and adoption for the research report.

#### Acceptance Criteria

1. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL expose Clinical_Analytics covering FIDES verdict distribution, DDI severity distribution, router role/intent confidence buckets, fallback rate, per-tier latency percentiles, and a blocked-claims count.
2. WHEN a `CRITICAL` claim is blocked by FIDES verification, THE CLARA_API SHALL count the event in the Clinical_Analytics blocked-claims metric.
3. THE CLARA_API SHALL derive Clinical_Analytics from the existing Observability_Store (Flow_Event records and the metrics snapshot) rather than introducing a duplicate collection path.
4. WHERE the requesting user holds the `admin` role, THE CLARA_API SHALL expose Product_Analytics covering active users, per-Surface usage counts, conversion funnels, and retention.
5. THE CLARA_Web SHALL render Clinical_Analytics separately from the existing scribe analytics summary without removing the scribe summary.
6. IF a request to a Product_Analytics or Clinical_Analytics endpoint lacks the `admin` role, THEN THE CLARA_API SHALL respond with HTTP 403.

### Requirement 11: No-PII telemetry and analytics invariant

**User Story:** As a privacy officer, I want every admin, observability, alerting, audit, and analytics output to be free of PII, so that operating the platform never leaks patient or user data.

#### Acceptance Criteria

1. THE CLARA_API SHALL exclude PII from Product_Analytics and Clinical_Analytics aggregation outputs, including names, emails, free-text queries, and drug lists.
2. THE CLARA_API SHALL exclude PII from every Alert payload delivered to an Alert_Sink.
3. THE CLARA_API SHALL exclude PII from every Admin_Audit_Record.
4. WHERE an Admin_User views detailed telemetry, THE CLARA_Web SHALL pass it through the role-gated research-telemetry sanitizer so PHR/medicine-cabinet PII is stripped and detailed telemetry remains admin-only.
5. WHERE an Analytics_SDK event is emitted from an Admin_Surface, THE CLARA_Web SHALL include only coarse, non-identifying signals (surface name, view label, counts) and SHALL exclude PII.

### Requirement 12: Additive, default-off feature flags and backward compatibility

**User Story:** As a release manager, I want every new capability behind a default-off flag, so that the upgrade ships dark and can be enabled per environment without a redeploy of clinical code.

#### Acceptance Criteria

1. THE CLARA_Delivery SHALL introduce the new capabilities (tracing export, durable observability store, alerting, admin audit, live ingestion controls) behind Feature_Flags that default to off.
2. WHEN every new Feature_Flag is off, THE CLARA_API SHALL produce request/response shapes and side effects equal to the pre-feature baseline.
3. THE CLARA_Delivery SHALL document every new Feature_Flag and configuration key in `.env.example`.
4. WHERE a new endpoint is gated by a disabled Feature_Flag, THE CLARA_API SHALL return an explicit "feature disabled" shape (HTTP 404) rather than a partial or misleading success.
5. THE CLARA_API SHALL pass `make lint` and the API and ML service test suites after each batch of changes.
