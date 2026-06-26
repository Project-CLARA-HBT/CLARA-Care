# Design Document

## Overview

This design upgrades the CLARA-Care Admin & Observability surface to
production-grade quality. It is **additive and feature-flagged**: with every new
flag off the system behaves exactly as today, and nothing here changes clinical
reasoning, the router, the RAG retrieval path, or any safety guardrail.

The work completes four tracks over the as-built scaffolding:

1. **Admin operations** — finish the knowledge-source/RAG-registry control plane
   so admin mutations are RBAC-gated, durably backed, and surface real status
   instead of permanent fail-soft.
2. **Observability** — add per-route latency percentiles, ecosystem health, and
   distributed traces, backed by an optional durable store that honors a
   selectable date range beyond the 1,000-event in-memory window.
3. **Operability** — turn the already-computed `/ecosystem` `federation_alerts`
   into delivered, acknowledgeable, deduplicated Alerts, and add an append-only,
   no-PII admin-action audit trail.
4. **Analytics integrity** — keep Product_Analytics and Clinical_Analytics
   PII-free and correct over a selectable range, derived from existing
   observability.

The guiding principle is **extend, do not duplicate**. New work reuses the
existing `require_roles(...)` RBAC, the `APIMetricsStore`/`FlowEventStore`
observability primitives, the `AnalyticsAggregator` PII-free projection, the
role-gated `research_telemetry` sanitizer, the compliance redaction projection,
the `ml_proxy` fail-soft pattern, and the existing `OTEL_EXPORT_*` config keys.

### Key as-built facts this design builds on

- **RBAC**: `require_roles(*roles)` in `core/rbac.py` grants `admin` implicit access to any guarded route and returns HTTP 403 otherwise; `AuthContextMiddleware` decodes the token once and yields HTTP 401 when absent/invalid.
- **Admin RAG proxy**: `endpoints/admin_rag.py` already exposes `/admin/rag/{ingestion/run, ingestion/status/{job_id}, sources, sources/{id}, eval/run, eval/results/{run_id}, stats}`, all `require_roles("admin")`, proxying to `services/ml` with a fail-soft payload (`ml_available=false`, `fallback=true`, `fallback_reason`). The ml-side handlers "may not exist yet", so fail-soft is currently permanent.
- **Knowledge sources**: the web page (`app/admin/knowledge-sources/page.tsx`) creates sources, uploads documents, toggles document status, runs Source-Hub federation sync, and governs the RAG registry — all through `lib/research.ts` + the shared axios client + `sanitizeUpstreamError` + `AsyncSection`.
- **Metrics**: `APIMetricsStore` (`core/metrics.py`) is an in-process snapshot of `requests_total`, `by_route`, `by_status`, `avg_latency_ms` — average only, no percentiles, no time-series.
- **Flow events**: `FlowEventStore` (`core/flow_event_store.py`) is a bounded in-memory deque (`maxlen=1000`) of records carrying `source`, `user_id`, `role`, `intent`, `model_used`, `timestamp`, and an `event` dict with `stage`/`status`/`confidence`/latency.
- **Ecosystem health**: `/system/ecosystem` already computes `partner_health`, `data_trust_scores`, and `federation_alerts` — but the alerts are ephemeral, always `acknowledged: false`, never delivered, never deduplicated.
- **Analytics**: `endpoints/analytics.py` has `AnalyticsAggregator` with `_within_range`, `_project_pii_free` (PII denylist), `_percentile` (monotonic linear interpolation), and `_classify_tier`; `/system/analytics/{product,clinical}` are `require_roles("admin")` and flag-gated (`product_analytics_enabled`, `clinical_analytics_enabled`, `analytics_default_range_days`).
- **Telemetry sanitizer**: `core/research_telemetry.py` provides `sanitize_telemetry(payload, role)` (admin-only detailed rail) and `strip_pii(...)` (recursive PHR/identity denylist + email/long-digit scrubbing).
- **OTEL config**: `services/ml/config.py` already declares `otel_export_enabled`, `otel_export_endpoint`, `otel_export_timeout_seconds` — but **no OpenTelemetry instrumentation exists** (no spans, no exporter).
- **Audit precedent**: `phr/audit.py` (append-only `phr_audit`), `ScribeAudit`, `VnDrugMappingAudit`, and `compliance_events` establish the append-only, no-PII audit pattern; there is **no admin-action audit** for knowledge-source/registry/ingestion mutations.
- **Web analytics**: `lib/analytics/events.ts` emits coarse, named, no-PII admin events (`admin_*_viewed`) through the consent/PII-guarded facade.

### Feature Flags (all default OFF / preserving current behavior)

```
ADMIN_RAG_INGESTION_CONTROLS_ENABLED=false      # live ingestion control surfacing (vs permanent fail-soft)
ADMIN_OBSERVABILITY_PERCENTILES_ENABLED=false   # per-route p50/p90/p99 in metrics surface
ADMIN_OBSERVABILITY_PERSISTENT_STORE_ENABLED=false  # durable flow-event store (vs in-memory deque)
ADMIN_OBSERVABILITY_ALERTING_ENABLED=false      # alert evaluation + delivery + ack state
ADMIN_OBSERVABILITY_ALERT_WEBHOOK_URL=          # alert sink; empty → no outbound (no-op)
ADMIN_AUDIT_LOG_ENABLED=false                   # append-only admin-action audit trail
# CLARA_ML (existing keys, reused — wire instrumentation behind them):
OTEL_EXPORT_ENABLED=false                        # emit + export trace spans
OTEL_EXPORT_ENDPOINT=                            # OTLP endpoint; empty → no-op
OTEL_EXPORT_TIMEOUT_SECONDS=1.5
```

When a flag is off the corresponding enforcement/emission is skipped and the
endpoint either behaves exactly as today or returns an explicit "feature
disabled" (HTTP 404) shape (Requirements 12.2, 12.4).

## Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            CLARA_Web (Next.js admin)                         │
│  Admin_Surfaces: overview │ knowledge-sources │ answer-flow │ observability  │
│                  │ analytics │ analytics/clinical │ rag-* │ source-hub │ dsar │
│  shared: AsyncSection · sanitizeUpstreamError · TelemetryPanel(admin-only)   │
│          · analytics/events.ts (coarse, no-PII named events)                 │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                     │ /api/v1/*  (cookie+bearer, CSRF, RBAC)
┌────────────────────────────────────▼──────────────────────────────────────────┐
│                              CLARA_API (FastAPI)                                 │
│  rbac.require_roles · AuthContextMiddleware · APIMetricsMiddleware               │
│                                                                                 │
│  admin_rag.py        ── ingestion/run·status · sources · eval · stats (admin)    │
│  system.py           ── metrics · dependencies · ecosystem · sources · flow-     │
│                         events/stream · analytics/{product,clinical}             │
│  analytics.py        ── AnalyticsAggregator (PII-free projection, windowing)     │
│                                                                                 │
│  ┌──────────────────────── NEW (additive, flag-gated) ───────────────────────┐  │
│  │ MetricsPercentiles   p50/p90/p99 over per-route latency samples            │  │
│  │ AlertEngine          evaluate → dedupe → deliver(sink) → ack state         │  │
│  │ AdminAuditLog        append-only, no-PII admin-action records              │  │
│  │ FlowEventSink        durable persistence of Flow_Events (opt-in)           │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│  reuses: research_telemetry.strip_pii · compliance redaction · DB models         │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                 internal X-ML-Internal-Key │            │ OTLP (flag-gated)
┌────────────────────────────────────▼────────┐   ┌──────▼──────────────────────────┐
│              CLARA_ML (FastAPI)               │   │  Trace collector (OTLP endpoint) │
│  admin/rag/* handlers (ingestion/registry/    │   │  spans: no PII attributes        │
│  eval/stats) · OTel spans (per-request +      │   └──────────────────────────────────┘
│  stage children) when OTEL_EXPORT_ENABLED     │
└────────────────────────────────────────────────┘
```

### Design principles

- **Single source of truth for telemetry.** Clinical_Analytics, percentiles, and
  alerts all derive from the existing Observability_Store (`FlowEventStore`,
  `APIMetricsStore`). No new ingestion path is added (Requirements 10.3, 8.1).
- **Privacy by projection.** Every outward-facing surface (analytics, alerts,
  audit, spans, detailed telemetry) passes through a PII-stripping projection —
  `AnalyticsAggregator._project_pii_free`, `research_telemetry.strip_pii`, or the
  compliance redaction — so PII never leaves (Requirement 11).
- **Additive & reversible.** New tables/columns only; every migration has a
  downgrade. Flags default off; flags-off behavior equals baseline
  (Requirement 12).
- **Fail-soft, but honest.** When CLARA_ML is unavailable the admin surface stays
  up, but the payload is explicitly flagged degraded so the UI shows "unavailable,
  retry" instead of stale success (Requirement 3.3/3.4).
- **Guardrails are invariants.** RBAC, no-PII telemetry, the admin-only detailed
  telemetry rail, and CSRF are regression-locked, not re-implemented
  (Requirements 1, 11).

## Components and Interfaces

### 1. RBAC-gated admin operations (Requirement 1)

A single audit of the admin/observability router confirms every mutation route
carries a role dependency. The convention mirrors `admin_rag.ADMIN_ROLE_DEP`:

```python
ADMIN_ROLE_DEP = Depends(require_roles("admin"))            # mutations + analytics
OPERATIONAL_ROLE_DEP = Depends(require_roles("doctor"))     # admin implicit; doctor read
```

- Admin mutations (knowledge-source create/upload/status, RAG source update,
  ingestion/eval trigger, alert ack, audit read) → `ADMIN_ROLE_DEP` (403 for
  non-admin, 401 for no token).
- Operational reads (`/system/metrics`, `/dependencies`, `/ecosystem`,
  `/sources`) → `OPERATIONAL_ROLE_DEP` (admits `doctor`+`admin`; rejects
  `normal`/`researcher`). A route-table test asserts no new admin/observability
  route lacks a role dependency (Requirement 1.5). CSRF middleware is unchanged
  (Requirement 1.6).

### 2. Knowledge ingestion controls and durable status (Requirements 2, 3)

The existing `admin_rag.py` proxy already degrades to a fail-soft payload. This
design makes the degradation **explicit and recoverable** and gates the live
control path behind `ADMIN_RAG_INGESTION_CONTROLS_ENABLED`:

```python
def proxy_ingestion(path, body, *, fail_soft):
    if not settings.admin_rag_ingestion_controls_enabled:
        return feature_disabled_shape()                  # 404 (Req 12.4)
    result = _proxy_ml(path, body, fail_soft=fail_soft)  # existing fail-soft proxy
    result["degraded"] = bool(result.get("fallback") or not result.get("ml_available", True))
    return result
```

- A successful ML response leaves `degraded=false`/`fallback` unset
  (Requirement 3.4); any connect/timeout/HTTP/invalid-JSON failure yields the
  fail-soft payload with `ml_available=false, fallback=true, fallback_reason`
  (Requirement 3.3). The web layer renders an "unavailable, retry" state on the
  degraded marker (it already does for `fallback === true`).
- The single-run record cap reuses the existing ML-side
  `rag_admin_ingest_max_records` bound (Requirement 3.5).
- Knowledge-source CRUD/document-status endpoints are unchanged in contract and
  remain `ADMIN_ROLE_DEP`; the page already renders the four async states and
  routes errors through `sanitizeUpstreamError` (Requirements 2.2–2.5).

### 3. RAG source registry governance (Requirement 4)

The `SourceUpdateRequest` model already constrains `trust_tier` to `ge=1, le=4`
(422 outside the band — Requirement 4.2) and `weight` to `ge=0.0`
(Requirement 4.3), and forwards only explicitly-set fields via
`model_dump(exclude_none=True)` (Requirement 4.4). This design adds
`license_code` and `attribution` to the declared `SourceInfo` contract (they
already flow through `extra="allow"`) so the web list renders attribution
obligations explicitly (Requirements 4.1, 4.5).

### 4. Metrics percentiles and ecosystem health (Requirement 5)

**Per-route latency samples.** `APIMetricsStore` records only running totals.
This design adds an optional bounded per-route latency sample ring (flag
`ADMIN_OBSERVABILITY_PERCENTILES_ENABLED`) and a percentile projection that
reuses the proven `AnalyticsAggregator._percentile` (linear interpolation,
monotonic in `pct`):

```python
class MetricsPercentiles:
    def record(self, route: str, latency_ms: float) -> None: ...   # bounded ring per route
    def percentiles(self, route: str) -> dict[str, float]:         # {p50, p90, p99}
        s = self._samples.get(route, [])
        return {"p50_ms": pct(s, 50), "p90_ms": pct(s, 90), "p99_ms": pct(s, 99)}
```

Because percentiles are computed by the monotonic `_percentile`, `p50 ≤ p90 ≤
p99` for any fixed sample set (Requirement 5.3). When the flag is off the metrics
surface returns the existing average-only shape (Requirement 12.2).

**Ecosystem health** keeps the existing `/system/ecosystem` computation
(`partner_health`, ML reachability, flow-event freshness with the 30-minute
staleness rule). The flow-event status classification (`ok`/`degraded`/`down`
from age + count) is extracted into a pure function so it can be property-tested
(Requirement 5.5).

### 5. Distributed tracing / OpenTelemetry export (Requirement 6)

A new `clara_ml/observability/tracing.py` wires the **already-declared** OTEL
config into an optional tracer. It is initialized only when
`otel_export_enabled` and `otel_export_endpoint` are both set:

```python
def init_tracing(settings) -> Tracer | None:
    if not settings.otel_export_enabled or not settings.otel_export_endpoint.strip():
        return None                                  # no-op (Req 6.2, 6.3)
    exporter = OTLPSpanExporter(endpoint=settings.otel_export_endpoint,
                                timeout=settings.otel_export_timeout_seconds)
    return build_tracer(exporter)

@contextmanager
def request_span(tracer, name, attrs):               # top-level + stage children
    if tracer is None:
        yield None; return
    with tracer.start_as_current_span(name) as span:
        for k, v in strip_pii(attrs).items():        # PII-free attributes (Req 6.4)
            span.set_attribute(k, v)
        yield span
```

- Span attributes pass through the existing `research_telemetry.strip_pii` so no
  names/emails/queries/transcripts/drug lists land on a span (Requirement 6.4).
- Exporter init/flush failures are caught; the request is served regardless and
  the failure never reaches the response (Requirement 6.5). Stage child spans
  reuse the canonical `FLOW_STAGE_ALIAS_MAP` stage ids.

### 6. Durable observability store (Requirement 7)

Behind `ADMIN_OBSERVABILITY_PERSISTENT_STORE_ENABLED`, a `FlowEventSink` mirrors
each appended Flow_Event into a durable table so analytics can query beyond the
in-memory deque and across restarts. The aggregator reads from the sink when
enabled, else from the in-memory `FlowEventStore` (Requirements 7.1, 7.2). The
date-range contract is unchanged and reuses `AnalyticsAggregator._within_range`
+ `_resolve_analytics_range` (inclusive window; 422 on inverted range; trailing
default window; `has_data=false` for empty — Requirements 7.3–7.6).

```python
class FlowEventSink:                                  # opt-in durable mirror
    def persist(self, record: dict) -> None: ...      # append projected (PII-free) record
    def query(self, *, start: date, end: date) -> list[dict]: ...
```

The persisted record is the `_project_pii_free` projection of the Flow_Event, so
durability never introduces a PII surface (Requirement 11.1).

### 7. Alert engine (Requirement 8)

`clara_api/observability/alerts.py` promotes the ephemeral
`/ecosystem` `federation_alerts` into a stateful engine, gated by
`ADMIN_OBSERVABILITY_ALERTING_ENABLED`:

```python
@dataclass(frozen=True)
class Alert:
    id: str                      # stable, derived from rule + source (dedupe key)
    severity: str                # "info" | "warning" | "critical"
    source: str
    message: str                 # bounded, no-PII

class AlertEngine:
    def evaluate(self, metrics, deps, flow_health) -> list[Alert]: ...  # threshold rules
    def reconcile(self, alerts: list[Alert]) -> list[AlertState]:       # firing/cleared transitions
    def deliver(self, fired: list[Alert]) -> None:                      # webhook sink, no-PII
    def acknowledge(self, alert_id: str) -> AlertState: ...             # persisted ack
```

- Rules mirror the existing thresholds (ML unreachable/degraded, API 5xx ≥
  warn/critical, flow events stale/missing) and produce a bounded severity and a
  stable id (Requirement 8.1).
- Delivery posts a no-PII payload to `ADMIN_OBSERVABILITY_ALERT_WEBHOOK_URL` only
  on a not-firing → firing transition; no sink configured → in-app only
  (Requirements 8.2, 8.3). Delivery is best-effort: failures are swallowed and
  never reach a user-facing response (Requirement 8.6).
- Acknowledge state is persisted by stable id; an acknowledged alert is not
  re-presented as new until it clears and re-fires (Requirement 8.4). Within an
  evaluation window each stable id fires at most one delivery (Requirement 8.5).

### 8. Admin-action audit trail (Requirement 9)

`clara_api/observability/admin_audit.py` follows the established `phr/audit.py`
append-only discipline, gated by `ADMIN_AUDIT_LOG_ENABLED`:

```python
def record_admin_action(db, *, actor_ref: str, action: str, target: str,
                        outcome: str, meta: dict | None = None) -> AdminAuditRecord:
    row = AdminAuditRecord(
        actor_ref=actor_ref,                       # opaque (hashed user id)
        action=action, target=target, outcome=outcome,
        meta_json=_project_pii_free(meta or {}),   # counts/flags only (Req 9.3, 11.3)
        created_at=now_utc(),
    )
    db.add(row); db.flush()
    return row                                     # insert-only; never update/delete
```

- Every admin mutation calls `record_admin_action(...)` with the action, target,
  and outcome (success/failure) — including failed mutations (Requirements 9.1,
  9.5).
- The module exposes only inserts and a most-recent-first read
  (`list_admin_actions`, `ADMIN_ROLE_DEP`); no update/delete path exists
  (Requirements 9.2, 9.4).
- `actor_ref` is an opaque hash of the user id and `meta_json` passes through the
  PII-free projection (Requirements 9.3, 11.3).

### 9. Web admin & observability surfaces (Requirements 2.5, 5.6, 11.4, 11.5)

The existing pages are completed, not rebuilt: every async section uses
`AsyncSection`, every error string flows through `sanitizeUpstreamError`,
detailed telemetry is wrapped in `TelemetryPanel`/`sanitize_telemetry`
(admin-only, PHR-stripped — Requirement 11.4), and each surface emits its coarse
`admin_*_viewed` event via `analytics/events.ts` (no PII — Requirement 11.5). A
new alert-acknowledge control and an admin-audit list view consume the new
endpoints.

## Data Models

### New configuration keys (`.env.example` — Requirement 12.3)

```
# Admin RAG ingestion controls (live vs permanent fail-soft)
ADMIN_RAG_INGESTION_CONTROLS_ENABLED=false
# Observability
ADMIN_OBSERVABILITY_PERCENTILES_ENABLED=false
ADMIN_OBSERVABILITY_PERSISTENT_STORE_ENABLED=false
ADMIN_OBSERVABILITY_ALERTING_ENABLED=false
ADMIN_OBSERVABILITY_ALERT_WEBHOOK_URL=
# Admin audit
ADMIN_AUDIT_LOG_ENABLED=false
# CLARA_ML tracing (existing keys, now wired)
OTEL_EXPORT_ENABLED=false
OTEL_EXPORT_ENDPOINT=
OTEL_EXPORT_TIMEOUT_SECONDS=1.5
```

### `admin_audit_log` (append-only, no PII)

| column | type | note |
|---|---|---|
| id | int pk | |
| actor_ref | str(64) | opaque (hashed user id), no PII |
| action | str(48) | e.g. `kb_source.create`, `rag_source.update`, `ingestion.run`, `alert.ack` |
| target | str(128) | source id / job id / alert id (no PII) |
| outcome | str(16) | `success` / `failure` |
| meta_json | JSON | counts/flags only — **never** PII |
| created_at | datetime | |

### `flow_event_archive` (opt-in durable mirror, PII-free)

| column | type | note |
|---|---|---|
| id | int pk | |
| sequence | int | mirrors `FlowEventStore` sequence |
| source | str(48) | |
| role | str(16) | |
| intent | str(48) null | |
| model_used | str(64) null | |
| event_json | JSON | `_project_pii_free`-projected event (verdict/status/confidence/latency) |
| occurred_at | datetime | |

### `alert_state` (firing/ack state by stable id)

| column | type | note |
|---|---|---|
| alert_id | str(96) pk | stable dedupe key (rule + source) |
| severity | str(16) | info/warning/critical |
| state | str(16) | `firing` / `cleared` |
| acknowledged | bool | |
| first_fired_at | datetime | |
| last_evaluated_at | datetime | |
| last_delivered_at | datetime null | |

All new tables are additive; each migration ships with a downgrade. With all
new flags off, no new write path executes and request/response shapes equal the
baseline (Requirement 12.2).

### PII-free projection contract

Every outward record (analytics aggregation, alert payload, audit meta, archived
flow event, span attribute) is produced by a projection that emits only opaque
identifiers, counts, distributions, severities, verdicts, timestamps, and
numeric latencies. Denylisted: `email`, `full_name`/names, free-text
query/answer/transcript, drug-name lists, raw `source_errors`. Reuses
`AnalyticsAggregator._project_pii_free` and `research_telemetry.strip_pii`.

## Error Handling

- **ML unavailable.** Admin RAG controls degrade to a fail-soft payload flagged
  `ml_available=false, fallback=true, fallback_reason`; the web shows an
  "unavailable, retry" state, never stale success (Requirements 3.3, 3.4).
- **Flag-disabled endpoints.** Return an explicit HTTP 404 "feature disabled"
  shape, never a partial success (Requirement 12.4).
- **Invalid analytics range.** `from > to` → HTTP 422; unparseable dates → 422 via
  the query schema; empty range → populated shape with `has_data=false`
  (Requirements 7.4, 7.6).
- **Trace export failure.** Caught inside the tracing wrapper; the request is
  served and the failure never reaches the response (Requirement 6.5).
- **Alert delivery failure.** Best-effort; swallowed and logged (no PII), never
  propagated to a user-facing response (Requirement 8.6).
- **User-facing errors.** All web error strings pass through
  `sanitizeUpstreamError` so codes, stack traces, and internal URLs never reach a
  view (Requirements 2.4, 5.6).
- **Audit on failure.** A failing admin mutation still appends a `failure`-outcome
  audit record (Requirement 9.5).

## Testing Strategy

**Dual approach.** Property-based tests verify universal invariants (RBAC,
percentile monotonicity, windowing, PII-free projection, audit append-only,
alert dedupe/ack state machine, flags-off equivalence); example/contract tests
cover endpoint shapes, the route-table role-dependency audit, span emission, and
the scribe-summary regression.

- **Property tests** run ≥100 generated iterations and are tagged
  `Feature: clara-admin-observability, Property {n}: {text}`.
  - Python: `hypothesis` for RBAC gating, percentile monotonicity, range
    windowing, PII-free projection, audit append-only/ordering, alert
    dedupe/ack, blocked-claims counting, flow-health classification, and
    flags-off equivalence.
  - Web/TypeScript: `fast-check` for `sanitizeUpstreamError`, the admin
    `TelemetryPanel` visibility (admin-only), `AsyncSection` exclusivity, and
    coarse-event PII-stripping.
- **Example/contract tests** cover endpoint shapes (Requirements 2.1, 3.1–3.2,
  4.1, 5.1–5.2, 10.1, 10.4), the route-table role-dependency audit (1.5), span
  emission with a recording exporter (6.1, 6.3, 6.5), durable-store
  persist/restore (7.1), alert delivery to a capturing sink (8.2), and the
  scribe-summary regression (10.5).
- **Flags-off regression gate** asserts that with all new flags off the metrics
  shape, admin RAG responses, analytics shapes, and ecosystem alerts equal the
  pre-feature baseline (Requirement 12.2).
- **No-PII CI guard** feeds adversarial PII into analytics records, alert
  contexts, audit meta, and span attributes and asserts the persisted/emitted
  projection drops it (Requirement 11).

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Admin mutations require the admin role

For any admin mutation endpoint and any caller role, the request is authorized if and only if the role is `admin`; every non-admin role receives HTTP 403 and an absent/invalid token receives HTTP 401.

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Operational telemetry admits doctor and admin only

For any operational telemetry endpoint (`/system/metrics`, `/dependencies`, `/ecosystem`, `/sources`) and any role, access is granted iff the role is `doctor` or `admin`; `normal` and `researcher` receive HTTP 403.

**Validates: Requirements 1.4**

### Property 3: Every new admin/observability route has a role dependency

For every route registered under the admin/observability routers, the route declares a `require_roles(...)` dependency; no such route is reachable without a role check.

**Validates: Requirements 1.5**

### Property 4: CSRF is enforced for cookie-authenticated admin mutations

For any cookie-authenticated admin mutation, a missing or invalid CSRF token causes rejection; a valid token permits the request.

**Validates: Requirements 1.6**

### Property 5: ML availability determines the degraded marker

For any admin RAG control invocation, a successful CLARA_ML response yields a payload with no degraded/fallback marker, and any ML connect/timeout/HTTP/invalid-JSON failure yields a payload explicitly flagged `ml_available=false, fallback=true` with a `fallback_reason`.

**Validates: Requirements 3.3, 3.4**

### Property 6: A single ingestion run is bounded by the record cap

For any requested ingestion limit, a single admin-triggered run processes no more than the configured maximum record cap.

**Validates: Requirements 3.5**

### Property 7: Trust tier accepts only the closed band {1,2,3,4}

For any integer trust-tier update, the value is accepted iff it lies in `{1,2,3,4}`; any out-of-band value is rejected with HTTP 422.

**Validates: Requirements 4.2**

### Property 8: Weight accepts only non-negative values

For any weight update, the value is accepted iff it is greater than or equal to zero.

**Validates: Requirements 4.3**

### Property 9: Partial source updates touch only provided fields

For any subset of update fields, only the explicitly provided fields are forwarded to CLARA_ML; unspecified fields are left unchanged.

**Validates: Requirements 4.4**

### Property 10: Latency percentiles are monotonic

For any fixed latency sample set, the computed percentiles satisfy p50 ≤ p90 ≤ p99.

**Validates: Requirements 5.2, 5.3**

### Property 11: Flow-event health classification follows the staleness rule

For any latest-event age and event count, the flow-event stream health is `down` when no events exist or the latest is stale with no items, `degraded` when stale-with-items or the error ratio is above threshold, and `ok` otherwise.

**Validates: Requirements 5.5**

### Property 12: Trace export is a no-op when disabled or unconfigured

For any request, when OpenTelemetry export is disabled or no export endpoint is configured, no exporter is initialized and no span is exported; behavior equals the pre-feature baseline.

**Validates: Requirements 6.2, 6.3**

### Property 13: Span attributes contain no PII

For any payload, every emitted span attribute set excludes names, emails, free-text queries/answers, transcripts, and drug lists after the PII-stripping projection.

**Validates: Requirements 6.4**

### Property 14: Trace export failure never breaks the request

For any exporter error or unavailability, the request is served to completion and the export failure is not propagated into the response.

**Validates: Requirements 6.5**

### Property 15: Durable store toggles without behavioral change

For any sequence of Flow_Events, when the durable store is disabled the system reads the in-memory store and behaves as baseline; when enabled, persisted events remain queryable across a simulated restart.

**Validates: Requirements 7.1, 7.2**

### Property 16: Analytics windowing includes only in-range data

For any requested `from`/`to` range, every returned data point has a timestamp within the inclusive range and no out-of-range point is included; an inverted range yields HTTP 422 and an empty range yields a populated shape with `has_data=false`.

**Validates: Requirements 7.3, 7.4, 7.6**

### Property 17: Threshold rules produce stable, bounded alerts

For any metric/dependency/flow-health input that crosses a configured threshold, an Alert is produced with a stable id and a severity in `{info, warning, critical}`.

**Validates: Requirements 8.1**

### Property 18: Alerts are deduplicated and fire delivery once per transition

For any sequence of evaluations of a persistent condition, each stable alert id triggers at most one firing delivery within an evaluation window; a missing sink results in no outbound attempt.

**Validates: Requirements 8.3, 8.5**

### Property 19: Acknowledged alerts are not re-presented until clear-and-refire

For any acknowledge/clear/refire sequence, an acknowledged alert is not re-presented as new until it clears and fires again.

**Validates: Requirements 8.4**

### Property 20: Alert delivery failure never breaks the request

For any Alert_Sink delivery failure, the request is served to completion and the delivery failure is not propagated into a user-facing response.

**Validates: Requirements 8.6**

### Property 21: Every admin mutation appends exactly one audit record

For any admin mutation (success or failure), exactly one append-only Admin_Audit_Record is written capturing an opaque actor reference, the action, the target, a timestamp, and the outcome.

**Validates: Requirements 9.1, 9.5**

### Property 22: The admin audit trail is append-only and ordered

For any sequence of audit writes, no record is updated or deleted by application code (the record count never decreases) and the read endpoint returns records most-recent-first.

**Validates: Requirements 9.2, 9.4**

### Property 23: Blocked CRITICAL claims are counted

For any Flow_Event set over a range, the Clinical_Analytics blocked-claims count equals the number of in-range events whose status is `blocked`.

**Validates: Requirements 10.2**

### Property 24: Outward outputs contain no PII

For any internal record fed into an analytics aggregation, an alert payload, an admin-audit meta field, or an archived flow event, the projected output contains no PII (names, emails, free-text queries/answers, drug lists, raw source_errors).

**Validates: Requirements 11.1, 11.2, 11.3, 11.5**

### Property 25: Detailed telemetry is admin-only and PII-stripped

For any role and telemetry payload, the detailed telemetry rail is present if and only if the role is `admin`, and when present its PHR/medicine-cabinet/identity fields are stripped.

**Validates: Requirements 11.4**

### Property 26: Flags-off equivalence

For any request, with every new Feature_Flag off, request/response shapes and side effects equal the pre-feature baseline, and a flag-disabled gated endpoint returns the explicit HTTP 404 "feature disabled" shape.

**Validates: Requirements 12.2, 12.4**
