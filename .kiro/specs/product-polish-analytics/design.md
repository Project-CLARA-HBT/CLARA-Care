# Design Document

## Overview

This design brings CLARA-Care to flagship quality across its polyglot monorepo (Next.js web `CLARA_Web`, FastAPI gateway `CLARA_API`, FastAPI ML `CLARA_ML`, Flutter `CLARA_Mobile`) while introducing a three-part analytics layer, without weakening any existing safety guardrail.

The work decomposes into five tracks that share a small set of cross-cutting primitives:

1. **Audit-driven bug fixing** — a structured `Audit_Record` and competitive-research deliverable feed a severity-ordered task plan; each fix is locked with a regression test (the team already follows this pattern in `context.md`).
2. **Correctness fixes** — chat routing/timeout alignment, DDI output sanitization and severity aggregation, and telemetry gating by role.
3. **Analytics layer** — `Product_Analytics` (usage), `Clinical_Analytics` (derived from existing observability), and a third-party `Analytics_SDK` abstraction with consent + PII guards.
4. **UX modernization** — a shared design-token system, the four async states (loading/empty/error/populated), and AA contrast.
5. **Mobile parity** — a persistent `Session_Store` with restore/clear lifecycle and per-screen parity.

The guiding principle is **extend, do not duplicate**. The analytics layer reuses the existing `APIMetricsStore`, `FlowEventStore`, control-tower config, and DB models rather than adding a parallel collection path. All new endpoints reuse `require_roles(...)`, the consent service, and the CSRF middleware that already protect the platform.

### Key as-built facts this design builds on

- **RBAC**: `require_roles(*roles)` in `services/api/src/clara_api/core/rbac.py` already grants `admin` implicit access to any guarded route and returns HTTP 403 otherwise.
- **Metrics**: `APIMetricsStore` (`core/metrics.py`) is an in-process snapshot of `requests_total`, `by_route`, `by_status`, `avg_latency_ms`.
- **Flow events**: `FlowEventStore` (`core/flow_event_store.py`) is a bounded in-memory deque of records carrying `source`, `user_id`, `role`, `intent`, `model_used`, and an `event` dict that includes `stage`/`status` (verification verdicts, `blocked`, `escalated`) and `policy_action`.
- **ML signals**: `services/ml/src/clara_ml/main.py` emits flow events with `status` values such as `blocked`, `escalated`, `completed`, and verification verdicts; `routing.py` produces role/intent/`confidence`.
- **Consent**: `UserConsent` + `/auth/consent-status` and `/auth/consent` already implement versioned medical consent; `SelfMedConsentGate` is the reusable gate pattern.
- **Timeouts**: API `ml_service_timeout_seconds=60` / `ml_research_timeout_seconds=300` (with a 600s sync floor already added); ML `deepseek_timeout_seconds=45`.
- **Design tokens**: `apps/web/styles/globals.css` already defines `--text-*`, `--surface-*`, `--shell-border*`, `--brand-*`, `--radius-*` for light/dark.
- **Mobile**: `SessionStore` is an in-memory `ChangeNotifier`; `ApiClient` already wires login/research/careguard/council/system endpoints.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              CLARA_Web (Next.js)                          │
│  Surfaces: chat │ research │ selfmed/careguard │ council │ scribe │ admin │
│                                                                          │
│  ┌──────────────┐  ┌────────────────────┐  ┌─────────────────────────┐   │
│  │ design tokens │  │ telemetry gate      │  │ analytics client        │   │
│  │ (globals.css) │  │ (role-aware view)   │  │ (consent + PII guard)   │   │
│  └──────────────┘  └────────────────────┘  └───────────┬─────────────┘   │
│  ┌──────────────────────────┐  ┌─────────────────────┐ │                  │
│  │ mode dispatch            │  │ error sanitizer     │ │  Analytics_SDK   │
│  │ fast→tier1 / deep→tier2  │  │ (user-readable)     │ │  (PostHog/GA/... )│
│  └──────────────────────────┘  └─────────────────────┘ │                  │
└───────────────────────────────────┬────────────────────┴──────────────────┘
                                     │ /api/v1/*  (cookie+bearer, CSRF, RBAC)
┌────────────────────────────────────▼─────────────────────────────────────┐
│                              CLARA_API (FastAPI)                            │
│  auth/RBAC/consent · chat proxy · research jobs · careguard · council ·     │
│  scribe · system(metrics/observability/flow-events)                         │
│                                                                            │
│  ┌─────────────────────────── NEW: analytics module ────────────────────┐ │
│  │  /system/analytics/product    (admin)  ── reads usage DB + metrics    │ │
│  │  /system/analytics/clinical   (admin)  ── reads flow events + metrics │ │
│  │  AnalyticsAggregator (PII-free projection, date-range windowing)      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  reuses: APIMetricsStore · FlowEventStore · ControlTowerConfig · DB models  │
└───────────────────────────────────┬────────────────────────────────────────┘
                                     │ internal (X-ML-Internal-Key)
┌────────────────────────────────────▼─────────────────────────────────────┐
│                              CLARA_ML (FastAPI)                             │
│  router (role/intent/confidence) · RAG pipeline · research_tier2 ·          │
│  careguard (DDI) · council · scribe · FIDES verification                    │
│  fixes: runtime-client reuse (deepseek-only) · DDI synthetic-alert/severity │
│  guardrails preserved: emergency fast-path · CRITICAL block                 │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                          CLARA_Mobile (Flutter)                           │
│  PersistentSessionStore (secure storage) · parity screens · Analytics_SDK │
└────────────────────────────────────────────────────────────────────────┘
```

### Design principles

- **Single source of truth for telemetry.** `Clinical_Analytics` derives every signal from `FlowEventStore`, `APIMetricsStore`, and control-tower config. No new ingestion path is added (Requirement 8.2).
- **Privacy by projection.** All outward-facing aggregations are produced by a projection step that emits counts/distributions/percentiles only — never raw query text or drug lists (Requirements 7.4, 9.4, 11.5).
- **Guardrails are invariants, not features.** Emergency fast-path, CRITICAL-claim blocking, RBAC, consent gating, and CSRF are treated as regression-locked invariants the new work must preserve (Requirement 11).
- **Sanitize at the boundary.** A single web-side error/telemetry sanitizer governs every user-facing string so internal jargon and stack traces never reach `End_User` views (Requirements 2.5, 4.1, 4.2).

## Components and Interfaces

### 1. Chat routing and timeout correctness (Requirement 2)

**Web mode dispatch (`apps/web/lib/research.ts` + chat page).** A pure dispatch function maps the selected mode to a transport:

```typescript
type ResearchExecutionMode = "fast" | "deep" | "deep_beta";
type ChatTransport = "tier1_chat" | "tier2_job";

// fast → POST /chat (tier1); deep/deep_beta → research tier2 job pipeline
function resolveChatTransport(mode: ResearchExecutionMode): ChatTransport {
  return mode === "fast" ? "tier1_chat" : "tier2_job";
}
```

The chat page calls `resolveChatTransport` and only invokes `executeResearchTier2Job()` when the result is `tier2_job`; `fast` calls the tier1 `POST /chat` proxy directly. This makes the routing decision a small, testable unit (the fix already landed per `context.md`; this design locks it behind a property over the mode enum).

**ML runtime-client reuse (`services/ml/src/clara_ml/rag/pipeline.py` + `main.py`).** Resolve the LLM runtime so that when `LLM_DEEPSEEK_ONLY` is enabled and the supplied `llm_runtime` matches the configured DeepSeek env, the pipeline **reuses the default client** (preserving its longer timeout) instead of constructing a runtime client capped at `min(deepseek_timeout, 18s)`:

```python
def resolve_llm_client(llm_runtime: dict | None, settings) -> LlmClient:
    if settings.llm_deepseek_only and _matches_configured_deepseek_env(llm_runtime, settings):
        return get_default_deepseek_client()        # keeps default (longer) timeout
    if llm_runtime:
        return DeepSeekClient.from_runtime(llm_runtime)  # explicit runtime override
    return get_default_deepseek_client()
```

**Timeout alignment.** The API ML request timeout must be `>= ` the ML synthesis timeout for the same request class. Concretely: chat/tier1 uses `ml_service_timeout_seconds` and that must be `>= deepseek_timeout_seconds`; the sync research path already enforces a 600s floor `>= ml_research_timeout_seconds`. We add a small invariant helper and a startup/test assertion:

```python
def assert_timeout_floor(api_timeout: float, ml_synthesis_timeout: float) -> None:
    assert api_timeout >= ml_synthesis_timeout, "API ML timeout below ML synthesis timeout"
```

**User-readable timeout message.** When the chat pipeline times out, the web layer renders a sanitized retry message through the shared error sanitizer (below) — no raw codes/stack traces.

### 2. Error and telemetry sanitization (Requirements 2.5, 4.1, 4.2, 4.3, 4.4)

A single web module `apps/web/lib/user-facing-text.ts` owns the boundary:

```typescript
const TELEMETRY_LABEL_BLOCKLIST = [
  "research mode", "retrieval", "rag mode", "fallback mode", "policy: warn", "policy: allow",
];
const MODE_LABELS: Record<string, string> = {
  fast: "Nhanh", deep: "Tư duy", deep_beta: "Pro", auto: "Tự chọn", full: "Đầy đủ",
};

// Removes internal URLs, connector ids, HTTP status detail, stack traces.
function sanitizeUpstreamError(raw: string): string;       // → "Hệ thống đang bận, vui lòng thử lại."
// Strips blocklisted telemetry labels from any user-facing string.
function stripTelemetryLabels(text: string): string;
// Maps internal mode → Vietnamese label.
function toModeLabel(internalMode: string): string;
```

**Role-gated telemetry panels.** A `TelemetryPanel` wrapper renders detailed telemetry only when `role === "admin"`; non-admin roles get the sanitized summary. Visibility is a pure function of `(role, payload)`.

### 3. DDI output clarity (Requirement 3)

**Web view-model (`apps/web/lib/careguard.ts`).** A projection turns the raw CareGuard payload into an `End_User` view that exposes only `{ riskLevel, alerts, recommendations, sources }` and drops `mode`, `fallback`, and `source_errors`:

```typescript
type DdiUserView = {
  riskLevel: "low" | "medium" | "high" | "critical";
  alerts: { messageVi: string; severity: string }[];
  recommendations: string[];   // Vietnamese, risk-group aware
  sources: { label: string; url?: string }[];
};
function toDdiUserView(raw: CareguardAnalysis): DdiUserView;       // excludes telemetry
function requiresTwoMedicines(medicines: string[]): boolean;       // < 2 → prompt, no call
```

The page guards the analysis call: when fewer than two medicines are supplied it shows a prompt and does **not** call `/careguard/analyze` (Requirement 3.5).

**ML aggregation (`services/ml/src/clara_ml/agents/careguard.py`).** Two invariants (already regression-locked in `tests/test_careguard_agent.py`, formalized here):

- openFDA-only co-occurrence never produces a standalone synthetic alert; it only enriches a pre-existing local/RxNav alert (Requirement 3.2).
- Severity aggregation: any `drug_drug` alert ranked `medium` forces overall `risk.level >= medium`; genuine `low` is preserved; `high`/`critical` unchanged (Requirement 3.3).

**Connector-error suppression.** When at least one valid signal remains, connector errors such as `openfda http_400` are hidden from the user view and retained only in metadata when no alternative signal exists (Requirement 3.6).

### 4. Analytics data model and endpoints (Requirements 7, 8)

All analytics endpoints live in a new module `services/api/src/clara_api/api/v1/endpoints/system.py` neighborhood (router prefix `/system/analytics`) and are gated by `require_roles("admin")`.

#### Endpoints

| Method & Path | Role | Purpose |
|---|---|---|
| `GET /system/analytics/product?from=&to=` | admin | Active users, per-Surface usage counts, conversion funnels, retention |
| `GET /system/analytics/clinical?from=&to=` | admin | FIDES verdict distribution, DDI severity distribution, router confidence, fallback rate, per-tier latency percentiles, blocked-claims count |

`from`/`to` are ISO dates defining a selectable range. RBAC returns 403 for any non-admin role (reusing `require_roles`).

#### Sourcing (no duplicate collection — Requirement 8.2)

- **Product_Analytics** aggregates from existing DB models: `User.last_login_at` (active users), `Query`/`SessionModel` (per-Surface usage and funnels via the existing dashboard pattern in `system.py`), `MedicineCabinet`/`CouncilCase`/`ScribeSession` counts. It reads the same tables the dashboard snapshot already reads.
- **Clinical_Analytics** aggregates from `FlowEventStore.list_events(...)` (verdicts, `blocked`, `escalated`, `policy_action`, `confidence`, per-stage status) and `APIMetricsStore.snapshot()` (latency), plus control-tower config. No new event sink is introduced.

#### Aggregator

```python
class AnalyticsAggregator:
    def product_metrics(self, db, *, start: date, end: date) -> ProductAnalytics: ...
    def clinical_metrics(self, db, flow_events, metrics, *, start: date, end: date) -> ClinicalAnalytics: ...

    @staticmethod
    def _within_range(ts: datetime, start: date, end: date) -> bool: ...
    @staticmethod
    def _project_pii_free(record: dict) -> dict:  # drop raw query text, drug lists, names, emails
        ...
```

#### Response schemas (Pydantic)

```python
class ActiveUsersPoint(BaseModel):
    date: date
    active_users: int

class SurfaceUsage(BaseModel):
    surface: str          # chat|research|selfmed|careguard|council|scribe|admin|dashboard
    count: int

class FunnelStage(BaseModel):
    stage: str
    count: int

class ProductAnalytics(BaseModel):
    generated_at: datetime
    range: tuple[date, date]
    active_user_trend: list[ActiveUsersPoint]
    surface_usage: list[SurfaceUsage]
    funnels: list[FunnelStage]
    retention: list[dict]            # cohort → retained counts (no PII)
    has_data: bool                   # drives the empty-state (7.5)

class VerdictDistribution(BaseModel):
    verified: int
    partially_verified: int
    contested: int
    unsupported: int
    blocked_claims: int              # CRITICAL claims blocked by FIDES (8.4)

class DdiSeverityDistribution(BaseModel):
    low: int
    medium: int
    high: int
    critical: int

class LatencyPercentiles(BaseModel):
    tier: str                        # tier1|tier2_deep|tier2_deep_beta|council
    p50_ms: float
    p90_ms: float
    p99_ms: float

class ClinicalAnalytics(BaseModel):
    generated_at: datetime
    range: tuple[date, date]
    verdicts: VerdictDistribution
    ddi_severity: DdiSeverityDistribution
    router_confidence: dict          # role/intent confidence buckets
    fallback_rate_pct: float
    latency: list[LatencyPercentiles]
    has_data: bool
```

#### Web dashboards (Requirements 7.3, 8.3, 8.5)

Two new admin pages under the control tower: `apps/web/app/admin/analytics/page.tsx` (product) and `apps/web/app/admin/analytics/clinical/page.tsx`. Both consume a date-range picker, render the four async states, and present the metrics. The Clinical page is **separate** from the existing scribe `/analytics/summary` (which remains untouched).

### 5. Third-party Analytics SDK abstraction (Requirement 9)

A provider-agnostic facade keeps the SDK choice (PostHog / Google Analytics / Plausible) swappable and enforces consent + PII rules in one place.

**Web (`apps/web/lib/analytics/index.ts`):**

```typescript
type AnalyticsEvent = { name: string; props?: Record<string, Primitive> };

interface AnalyticsTransport {           // adapter per provider
  init(config: AnalyticsConfig): void;
  identify(distinctId: string): void;
  capture(event: AnalyticsEvent): void;
}

class AnalyticsClient {
  // No-op when credentials absent (9.5). Suppresses all transmission when
  // consent not granted (9.3). Strips PII from every payload (9.4).
  // Identifies users by opaque pseudonymous id only (9.6).
  capture(event: AnalyticsEvent): void {
    if (!this.configured) return;                 // 9.5 safe no-op
    if (!this.consentGranted) return;             // 9.3 suppress
    this.transport.capture(stripPii(event));      // 9.4
  }
  identify(user: SessionUser): void {
    if (!this.configured || !this.consentGranted) return;
    this.transport.identify(pseudonymousId(user)); // 9.6 opaque, deterministic
  }
}

function stripPii(event: AnalyticsEvent): AnalyticsEvent;     // drop name/email/query/drug fields
function pseudonymousId(user: SessionUser): string;          // stable hash, never email/name
```

- `pseudonymousId` is a deterministic one-way hash of a stable user key (e.g., `user_id`) — same user → same id, and the id never equals or contains email/name.
- `stripPii` removes a denylist of PII keys and any free-text query/drug-list fields before transmission.
- Consent is read from the existing consent surface; analytics consent is suppressed by default until granted.

**Mobile (`apps/mobile/lib/core/analytics.dart`):** the same facade contract (init/identify/capture) with the same no-op-when-unconfigured and consent/PII rules, emitting named events for primary screens.

### 6. UX design-token system and async states (Requirement 5)

**Tokens.** `globals.css` already defines the token set. This track (a) audits surfaces for hardcoded color/spacing/radius values and replaces them with the existing `--text-*`, `--surface-*`, `--shell-border*`, `--brand-*`, `--radius-*` tokens, and (b) ensures the foreground/background token pairs meet AA contrast. Where a used pair fails, the token value is adjusted (light/dark) until the computed ratio passes.

**Async states.** A shared `AsyncSection` component renders exactly one of loading / empty / error / populated based on a discriminated union, so every primary surface gets consistent, mutually exclusive states:

```typescript
type AsyncState<T> =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "error"; message: string }   // message already sanitized
  | { kind: "populated"; data: T };
```

**Keyboard/focus and labels.** Visible focus styles are defined once via tokens and applied to interactive controls; primary-action labels use the Vietnamese task-oriented vocabulary from the guidance page (`/huong-dan`).

**Where competitive research informs UX patterns (Requirement 6).** The `Competitive_Research_Report` (section 8) feeds concrete, general UX patterns into this track — patterns only, never proprietary assets or verbatim copy. Each adopted pattern is traced back to its report entry in the task plan (Requirement 6.4). Per-surface mapping of where findings are expected to apply:

- **Chat** — fast-first answer affordance, streaming/typing affordance, and a calm "thinking" state instead of a long spinner (reinforces the Fast_Mode routing fix in section 1); message retry/regenerate affordance for the sanitized timeout case.
- **Research** — progressive disclosure of the long pipeline (collapsed stage timeline by default), `Tư duy`/`Pro` mode pickers framed by outcome rather than internal tier names, and clear empty/seed states for knowledge sources.
- **SelfMed/CareGuard** — risk-severity visualization conventions (color + label + plain-language summary), "add at least two medicines" guided empty state (Requirement 3.5), and source/citation chips rather than raw connector identifiers.
- **Council** — multi-specialist result layout patterns (consensus vs. divergence grouping) and intake stepper conventions.
- **Scribe** — SOAP section scaffolding and record/transcribe state patterns.
- **Admin analytics** — dashboard date-range + KPI-card + distribution-chart conventions that the new Product/Clinical pages (section 4) adopt for the four async states.

These are design inputs for the implementation plan; the report itself is produced by `CLARA_Delivery` and gated for copyright compliance before any pattern is adopted.

### 7. Mobile persistent session and parity (Requirement 10)

**Persistent store (`apps/mobile/lib/core/session_store.dart`).** Replace the in-memory store with a persistent one backed by secure storage (`flutter_secure_storage`), preserving the `ChangeNotifier` API so screens are unaffected:

```dart
class PersistentSessionStore extends ChangeNotifier {
  Future<void> hydrate();                 // load on launch; clear+route to login if expired/invalid
  Future<void> setSession({...});         // persist credentials (10.1)
  Future<void> clear();                   // remove all credentials (10.5)
  bool get isAuthenticated;
  bool get isExpired;                     // token exp check used during hydrate (10.3)
}
```

Launch flow: `hydrate()` reads stored credentials; if the token is valid the app restores the authenticated session (10.2); if expired/invalid it clears the store and routes to login (10.3). Sign-out calls `clear()` (10.5).

**Parity.** Login, dashboard, research, careguard, and council screens are brought to functional parity with their web counterparts within mobile-supported actions, reusing the existing `ApiClient` methods.

### 8. Delivery deliverables (Requirements 1, 6, 12)

- **Audit_Record** (`.kiro/specs/product-polish-analytics/audit-record.md`): per-Surface defect list with `critical|high|medium|low` ranks. Drives task ordering (critical/high before medium/low on the same Surface).
- **Competitive_Research_Report** (`.kiro/specs/product-polish-analytics/competitive-research.md`): general UX patterns per Surface with attribution links and no verbatim copyrighted content; implemented improvements reference the originating pattern in the task plan.
- **Doc/config drift**: rewrite `CLAUDE.md` to describe an implemented monorepo; de-duplicate `DEEP_BETA_REPORT_MIN_WORDS` (and any other duplicate) in `.env.example`; fix `data/docs/index.md` path references; document the new `Product_Analytics`/`Clinical_Analytics`/`Analytics_SDK` config keys in `.env.example`.

## Data Models

### New configuration keys (`.env.example` — Requirement 12.4)

```
# Analytics SDK (web + mobile). Empty → transmission disabled (graceful no-op).
ANALYTICS_SDK_PROVIDER=            # posthog | ga | plausible | ""
ANALYTICS_SDK_KEY=
ANALYTICS_SDK_HOST=
NEXT_PUBLIC_ANALYTICS_SDK_PROVIDER=
NEXT_PUBLIC_ANALYTICS_SDK_KEY=
NEXT_PUBLIC_ANALYTICS_SDK_HOST=
# Internal analytics dashboards
PRODUCT_ANALYTICS_ENABLED=true
CLINICAL_ANALYTICS_ENABLED=true
ANALYTICS_DEFAULT_RANGE_DAYS=30
```

No new database tables are required: `Product_Analytics` reuses existing identity/usage tables and `Clinical_Analytics` reuses the in-memory flow/metrics stores. If durable history beyond the in-memory flow window is later needed, it can be added as a follow-up; this design intentionally avoids a duplicate collection path per Requirement 8.2.

### PII-free projection contract

The projection step accepts any internal record and emits a sanitized record containing only: identifiers that are opaque (no email/name), counts, distributions, severities, verdicts, timestamps, and numeric latencies. Denylisted fields: `email`, `full_name`, `user_input`/free-text query, drug-name lists, raw `source_errors`.

## Error Handling

- **Upstream/timeout errors → user-readable copy.** `sanitizeUpstreamError` converts any raw error (HTTP detail, connector id, URL, stack trace) into a calm Vietnamese retry message. Applied uniformly in chat, research, and careguard surfaces.
- **Connector partial failure.** CareGuard hides connector errors when another source still yields a valid signal; only when no signal remains is the error kept in metadata (never surfaced to `End_User`).
- **Analytics failures are non-fatal.** The `AnalyticsClient` never throws into product flows; when unconfigured or consent-less it is a safe no-op (Requirement 9.5).
- **Analytics endpoints.** Invalid date ranges return 422; missing admin role returns 403; empty ranges return a populated-shaped response with `has_data=false` to drive the empty state.
- **Mobile launch.** Corrupt/expired stored sessions never crash launch; `hydrate()` clears and routes to login.

## Testing Strategy

**Dual approach.** Property-based tests verify universal invariants (routing, privacy, sanitization, severity aggregation, RBAC, session lifecycle, safety guardrails); example/contract tests cover endpoint shapes, localization copy, parity screens, and the document deliverables.

- **Property tests** run a minimum of 100 generated iterations each and are tagged `Feature: product-polish-analytics, Property {n}: {text}`.
  - Web/TypeScript: `fast-check` for the dispatch, sanitizer, DDI projection, analytics PII/consent, async-state, and contrast properties.
  - Python: `hypothesis` for the ML runtime-client reuse, DDI aggregation, timeout-floor, Clinical_Analytics counts/windowing/PII, RBAC-gate, emergency fast-path, and CRITICAL-block properties.
  - Dart: model-level tests for the session lifecycle round-trip and invalid-token branch.
- **Example/contract tests** cover analytics endpoint shapes (7.1, 8.1), DDI risk-group localization (3.4), mode labels (4.4), parity screens (10.4), and the scribe-summary regression (8.5).
- **Smoke/doc checks** cover `make lint` + suites (1.4, 1.5), the `.env.example` duplicate-key and new-key checks (12.2, 12.4), `data/docs/index.md` path resolution (12.3), and CLAUDE.md content (12.1).
- **Regression-per-fix.** Every bug fix adds a test that fails on pre-fix behavior and passes after (Requirement 1.3), continuing the established `context.md` discipline.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Mode dispatch routes fast to tier1 and deep modes to tier2

For any research execution mode, the web dispatch routes `fast` to the tier1 chat endpoint and routes `deep`/`deep_beta` to the research tier2 job pipeline; no `fast` query ever reaches the tier2 job pipeline.

**Validates: Requirements 2.1, 2.2**

### Property 2: DeepSeek-only runtime reuses the default client without a shortened timeout

For any supplied runtime that matches the configured DeepSeek-only environment while `LLM_DEEPSEEK_ONLY` is enabled, the pipeline reuses the default DeepSeek client and the resolved request timeout is never silently capped below the default client timeout; for a non-matching runtime an explicit runtime client is created.

**Validates: Requirements 2.3**

### Property 3: API ML timeout is never below the ML synthesis timeout

For any request class, the resolved API ML request timeout is greater than or equal to the resolved CLARA_ML synthesis timeout for the same request (including the sync-research 600s floor).

**Validates: Requirements 2.4**

### Property 4: User-facing error messages are sanitized

For any raw upstream error or timeout payload, the user-facing message excludes stack-trace markers, raw exception class names, HTTP status detail tokens, internal URLs, and connector identifiers.

**Validates: Requirements 2.5, 4.2**

### Property 5: DDI end-user projection excludes telemetry

For any CareGuard DDI payload, the end-user projection contains only risk level, alerts, recommendations, and reference sources, and excludes runtime mode, fallback flags, and `source_errors`.

**Validates: Requirements 3.1**

### Property 6: openFDA-only evidence never creates a standalone alert

For any CareGuard signal set, a drug pair whose only evidence is openFDA co-occurrence (with no local or RxNav alert) produces no standalone alert; openFDA evidence attaches only as enrichment to a pre-existing alert.

**Validates: Requirements 3.2**

### Property 7: A medium drug_drug alert floors the overall risk at medium

For any alert set, if at least one `drug_drug` alert is ranked `medium`, the aggregated overall risk level is at least `medium`; a genuine `low` alert set is not bumped, and `high`/`critical` aggregation is unchanged.

**Validates: Requirements 3.3**

### Property 8: DDI checks require at least two medicines

For any medicine list with fewer than two entries, the DDI analysis is not invoked and a prompt to add at least two medicines is returned; for two or more entries the analysis proceeds.

**Validates: Requirements 3.5**

### Property 9: Connector errors are hidden while a valid signal remains

For any source-error set, if at least one valid alert or signal still exists, connector errors (such as `openfda http_400`) are hidden from the end-user view; when no alternative signal remains, the error is retained only in metadata and never in the end-user view.

**Validates: Requirements 3.6**

### Property 10: Internal telemetry labels are excluded from end-user views

For any backend payload, the end-user-rendered string contains none of the internal telemetry labels (`research mode`, `retrieval`, `RAG mode`, `Fallback mode`, `Policy: Warn/Allow`).

**Validates: Requirements 4.1**

### Property 11: Telemetry panel visibility equals admin role

For any role and view payload, detailed telemetry panels are visible if and only if the requesting role is `admin`.

**Validates: Requirements 4.3**

### Property 12: Date-range windowing and percentile monotonicity

For any selected date range, every returned analytics data point falls within that range (out-of-range data excluded), and computed latency percentiles are monotonic (p50 ≤ p90 ≤ p99).

**Validates: Requirements 7.3, 8.3**

### Property 13: Outward outputs contain no PII

For any underlying data, the system metrics, flow-event records, Product_Analytics aggregation, Clinical_Analytics aggregation, and every Analytics_SDK event payload contain no PII — no email, name, free-text query content, or drug lists.

**Validates: Requirements 7.4, 9.4, 11.5**

### Property 14: RBAC is enforced on protected endpoints

For any request bearing a role insufficient for a protected endpoint (including every Product_Analytics and Clinical_Analytics endpoint and every endpoint that required a role before this feature), the response is 401/403; an `admin` request is authorized.

**Validates: Requirements 7.2, 8.1, 11.1**

### Property 15: Blocked CRITICAL claims are counted

For any stream of verification/flow events, the Clinical_Analytics blocked-claims metric equals the number of events in which a `CRITICAL` claim failed verification and was blocked.

**Validates: Requirements 8.4**

### Property 16: Analytics transmission is suppressed without consent

For any sequence of analytics events emitted while analytics consent is not granted, the Analytics_SDK transport receives zero events.

**Validates: Requirements 9.3**

### Property 17: Analytics is a safe no-op without credentials

For any interaction while no Analytics_SDK credentials are configured, the application operates normally, no transmission is attempted, and no error propagates into the product flow.

**Validates: Requirements 9.5**

### Property 18: Users are identified by an opaque pseudonymous id

For any user, the Analytics_SDK distinct identifier is an opaque token that is neither the email nor the name and does not contain them, and is deterministic for the same user across events.

**Validates: Requirements 9.6**

### Property 19: Session persists and restores across restart, and clears on sign-out

For any valid login result, the credentials written to the persistent Session_Store are returned unchanged when the store is re-initialized from storage (the restored session is authenticated with matching credentials); after sign-out the persistent store is empty and reports unauthenticated.

**Validates: Requirements 10.1, 10.2, 10.5**

### Property 20: Expired or invalid stored tokens clear the store and route to login

For any expired or invalid persisted token, launch initialization clears the Session_Store and resolves to the login screen.

**Validates: Requirements 10.3**

### Property 21: Async sections render exactly one state

For any async data condition, a primary surface renders exactly one of the loading, empty, error, or populated states, and the states are mutually exclusive.

**Validates: Requirements 5.2**

### Property 22: Used color token pairs meet AA contrast

For any foreground/background design-token pair used together on a primary surface, the computed contrast ratio is at least 4.5:1 for normal text (or at least 3:1 for large text and interactive UI components).

**Validates: Requirements 5.3**

### Property 23: Consent gate precedes medical content

For any medical-data Surface accessed while consent is not granted, medical content is not rendered and the consent gate is shown first.

**Validates: Requirements 11.2**

### Property 24: Emergency symptoms trigger escalation without diagnostic reasoning

For any query containing an emergency symptom keyword, CLARA_ML returns the emergency escalation response and does not execute the diagnostic reasoning / RAG synthesis path.

**Validates: Requirements 11.3**

### Property 25: Failed CRITICAL claims are blocked

For any `CRITICAL` drug dosage or DDI claim whose verification fails, the response is blocked and never returned to the user.

**Validates: Requirements 11.4**

### Property 26: CSRF is enforced for cookie-authenticated mutations

For any mutating request authenticated via cookie, a missing or invalid CSRF token causes rejection; a mutating request authenticated via bearer token bypasses CSRF as before.

**Validates: Requirements 11.6**
