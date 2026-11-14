# PH13 A01 — Risk Register

**Phase:** PH13 (Connected Health & Wearables)
**Agent:** A01 — API + Contract
**Branch:** `phase/ph13-a01`

| ID | Severity | Risk | Mitigation Implemented | Residual |
|----|----------|------|------------------------|----------|
| R-01 | High | In-process `SyncAdapterRateLimiter` is per-worker memory; horizontally scaled API instances each hold independent windows, so effective limit multiplies. | Documented as process-local; limiter exposes `reset()` for tests. Redis-backed shared limiter is out of A01 lane (see notes). | Accepted for single-worker deployments; **flag for multi-worker production** — coordinate with platform/Redis owner before scaling. |
| R-02 | High | Unbounded `_sync_limiter._history` map can grow with connector cardinality (memory pressure). | Per-connector `deque` prunes expired entries on each access; keys are connector-scoped and bounded by tenant connector count. | Low–medium under extreme connector churn; recommend periodic key eviction if connector counts grow large. |
| R-03 | Medium | Payload bound check (`>500`) runs after Pydantic has already parsed the body, so very large bodies are still allocated before rejection. | Pydantic field `max_length=500` on `records`/`tombstones` rejects at validation time; handler check is defense-in-depth. True body-size limiting relies on the existing gateway/middleware. | Depends on upstream request-size middleware remaining enabled. |
| R-04 | Medium | Sync adapter DTOs intentionally duplicate canonical `connected_health.schemas` models, creating drift risk between two representations. | `_dto_to_canonical_batch` performs explicit field mapping with safe defaults; contract suite covers round-trip behavior. | Ongoing maintenance cost; contract tests act as the drift alarm. |
| R-05 | Medium | Default provenance fallback fabricates `raw_hash = "sha256:" + "0"*64` when client omits provenance. | Hash is deterministic placeholder only; provenance field is client-supplied metadata, not a trust boundary. No clinical decision is derived from it. | Low; consider making provenance mandatory in a future contract revision. |
| R-06 | Medium | `GET /{connector_id}/sync/status` reads `ConnectorSyncCursor` via `updated_at desc` without table-level index guarantee. | Cursor table has `updated_at` from `onupdate`; result set bounded by connector. Query is ownership-gated by `owned_connector`. | Low; index tuning belongs to A02 (DB lane). |
| R-07 | Medium | Error envelopes echo `profile_id` / provider / status details. | Values echoed are identifiers from the caller's own authenticated connector scope, never PII or free-text clinical data. Cross-tenant probes receive generic `CONNECTOR_NOT_FOUND`. | Low; consistent with no-PII telemetry invariant. |
| R-08 | Low | `HTTP_413_REQUEST_ENTITY_TOO_LARGE` / `HTTP_422_UNPROCESSABLE_ENTITY` starlette constants emit deprecation warnings. | Behavior unchanged; constants still resolve. | Cosmetic; migrate in a follow-up lane. |
| R-09 | Low | Rate limiting is applied to the legacy `/{connector_id}/imports` route and the new adapter routes using the same bucket key, so heavy legacy imports can throttle adapter clients. | Intentional: shared per-connector budget models total sync pressure. | Documented behavior, not a regression. |
| R-10 | Low | Consent check is performed in the handler and again inside `import_batch` (double read). | Redundant reads are cheap and preserve the handler's ability to return the structured `CONSENT_REVOKED` envelope. | None. |

## Out-of-Lane Dependencies

- Redis/shared rate-limit store: platform infra (not A01 lane).
- Cursor index tuning / migration: A02 (DB lane).
- Upstream request-size middleware verification: A08/CI lane.

## Invariants Preserved

- RBAC: every new route uses `USER_ROLE_DEP = require_roles("normal","researcher","doctor","admin")`.
- Consent gate: sync ingestion re-checks `active_consent` before any write.
- Tenant isolation: `owned_connector` gates all connector-scoped reads/writes.
- No-PII telemetry: audit metadata carries only cursor and record counts.
