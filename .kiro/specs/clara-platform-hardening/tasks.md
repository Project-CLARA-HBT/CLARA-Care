# Implementation Plan: CLARA Platform Hardening

## Overview

This plan converts the design into additive, default-off, parallelizable tasks
across `services/api` (FastAPI/Python), `services/ml` (FastAPI/Python),
`apps/web` (Next.js/TypeScript), `deploy/docker/*`, and `.github/workflows/*`. It
**hardens** the existing platform rather than rebuilding it: every new runtime
behavior is feature-flagged off, and flags-off behavior equals the pre-feature
baseline.

The plan is organized into twelve epics that map to the design's component tracks
plus the safety/flags-off regression suite and the quality gates. Shared modules
(`SessionSecurity`, `CircuitBreaker`, the redaction logging filter, the readiness
router, the body-size middleware) are built once in their own files so unrelated
work can proceed in the same wave; per-surface integration tasks are split out so
independent tracks parallelize.

- Epic 1 — Configuration, feature flags & rollout scaffolding (additive, default-off)
- Epic 2 — Secret management & credential rotation (Requirement 1)
- Epic 3 — Authentication & session hardening (Requirement 2)
- Epic 4 — Authorization coverage (Requirement 3)
- Epic 5 — Input validation & request limits (Requirement 4)
- Epic 6 — Rate limiting & abuse protection (Requirement 5)
- Epic 7 — Health, readiness & graceful degradation (Requirement 6)
- Epic 8 — Structured logging without PII (Requirement 7)
- Epic 9 — Dependency remediation & supply-chain gate (Requirement 8)
- Epic 10 — Backup/restore & migration safety (Requirement 9)
- Epic 11 — Performance & resource limits (Requirement 10)
- Epic 12 — Safety & flags-off regression suite (Requirement 11)
- Epic 13 — Backend checkpoint
- Epic 14 — Final quality-gate checkpoint

Testing follows the design: `hypothesis` (Python) for the property tests.
Property-test sub-tasks are marked optional with `*`, labeled **[PBT]**, each is
its own sub-task, and each cites its design Property number and the requirement
clause it validates.

Testing prerequisites (set up as part of the first task that needs them, not as standalone tasks):
- Python: `hypothesis` is already used in `services/api/tests` and `services/ml/tests`; reuse it.
- A flags-off baseline fixture asserts byte-equivalence with pre-feature behavior.

## Tasks

- [ ] 1. Configuration, feature flags, and rollout scaffolding
  - [ ] 1.1 Add `HARDENING_*` feature flags to API config
    - In `services/api/src/clara_api/core/config.py`, add `hardening_refresh_rotation_enabled`, `hardening_token_denylist_enabled`, `hardening_login_fail_closed`, `hardening_rate_limit_fail_closed`, `hardening_request_body_limit_enabled`, `hardening_request_body_max_bytes`, `hardening_readiness_probe_enabled`, `hardening_circuit_breaker_enabled`, `hardening_structured_logging_enabled`, and `hardening_csp_enabled`, all defaulting to off/preserving values.
    - _Requirements: 11.1, 11.2_
  - [ ] 1.2 Mirror circuit-breaker flag/keys in ML config
    - In `services/ml/src/clara_ml/config.py`, add the circuit-breaker enable flag, failure-threshold, and cool-down keys, defaulting to off.
    - _Requirements: 6.5, 11.1_
  - [ ] 1.3 Document all new flags/keys in `.env.example`
    - Add every flag from 1.1/1.2 plus the recommended production rate-limit, worker, and pool keys; ensure no duplicate definitions and no secret values.
    - _Requirements: 5.5, 10.1, 11.4_
  - [ ] 1.4 Author the staged-rollout runbook
    - Create `docs/ops/hardening-rollout.md` with the per-flag enablement order and per-flag rollback.
    - _Requirements: 11.4_
  - [ ]* 1.5 **[PBT]** Write flags-off equivalence property test (hypothesis)
    - **Property 1: Flags-off equivalence**
    - **Validates: Requirements 11.1, 11.2**

- [ ] 2. Secret management and credential rotation
  - [ ] 2.1 Remove plaintext default secrets from the app compose
    - In `deploy/docker/docker-compose.app.yml`, replace `JWT_SECRET_KEY`, `AUTH_BOOTSTRAP_ADMIN_PASSWORD`, `ML_INTERNAL_API_KEY`, `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, and `NEO4J_AUTH` plaintext `:-` defaults with the externally-injected `:?required` pattern already used in `docker-compose.deploy.yml`.
    - _Requirements: 1.1, 1.2, 1.6_
  - [ ] 2.2 Author the credential-rotation runbook
    - Create `docs/ops/secret-rotation.md` enumerating each secret, its managed-store location, rotation steps, and the JWT key-overlap procedure.
    - _Requirements: 1.3, 1.7_
  - [ ] 2.3 Rotate the exposed deploy SSH credential and move to key-based auth
    - Record in the rotation runbook that the exposed SSH password is rotated, SSH password auth is replaced with key-based auth, and the private key resides only in the managed secret store / CI encrypted secrets.
    - _Requirements: 1.4, 1.5_
  - [ ] 2.4 Extend startup secret guards and document the JWT key-overlap window
    - Confirm/extend the `main.py` production guards (reject `change-me` JWT key, insecure bootstrap password, missing ML internal key) and document the dual-key validation window for JWT rotation.
    - _Requirements: 1.2, 1.7_
  - [ ]* 2.5 **[PBT]** Write deploy-stack plaintext-secret scan test (hypothesis/pytest)
    - **Property 2: No plaintext production secret**
    - **Validates: Requirements 1.1, 1.6**
  - [ ]* 2.6 **[PBT]** Write fail-fast-on-missing-secret property test (hypothesis)
    - **Property 3: Fail-fast on missing secret**
    - **Validates: Requirements 1.2**

- [ ] 3. Authentication and session hardening
  - [ ] 3.1 Implement `SessionSecurity` (rotation + denylist + reuse event)
    - Create `services/api/src/clara_api/core/session_security.py` with `rotate_refresh`, `is_revoked`, `revoke(jti, ttl)`, and `record_reuse`, backed by `RedisSecurityStore` and gated by `hardening_refresh_rotation_enabled` / `hardening_token_denylist_enabled`. No-PII payloads only.
    - _Requirements: 2.2, 2.3, 2.4_
  - [ ] 3.2 Wire rotation + denylist into the auth endpoints
    - In `services/api/src/clara_api/api/v1/endpoints/auth.py`, rotate the refresh token on `/auth/refresh` and revoke access+refresh `jti` on `/auth/logout` when the flags are on; preserve the current flow when off.
    - _Requirements: 2.1, 2.2, 2.4, 2.7_
  - [ ] 3.3 Consult the denylist in token resolution
    - In `core/rbac.py`, have `get_current_token` reject denylisted `jti` when `hardening_token_denylist_enabled`.
    - _Requirements: 2.4_
  - [ ] 3.4 Add login fail-closed mode
    - In `core/login_guard.py`, when `hardening_login_fail_closed` and the distributed backend is unavailable, fall back to the in-process guard instead of returning unthrottled.
    - _Requirements: 2.5_
  - [ ]* 3.5 **[PBT]** Write refresh-rotation-invalidation property test (hypothesis)
    - **Property 4: Refresh rotation invalidates the old token**
    - **Validates: Requirements 2.2, 2.3**
  - [ ]* 3.6 **[PBT]** Write reuse-detection no-PII property test (hypothesis)
    - **Property 5: Reuse detection is recorded without PII**
    - **Validates: Requirements 2.3**
  - [ ]* 3.7 **[PBT]** Write denylist-rejection property test (hypothesis)
    - **Property 6: Denylisted token is rejected**
    - **Validates: Requirements 2.4**
  - [ ]* 3.8 **[PBT]** Write login fail-closed property test (hypothesis)
    - **Property 7: Login fail-closed**
    - **Validates: Requirements 2.5**
  - [ ]* 3.9 **[PBT]** Write CSRF-preservation property test (hypothesis)
    - **Property 8: CSRF preserved**
    - **Validates: Requirements 2.6, 11.3**

- [ ] 4. Authorization coverage
  - [ ] 4.1 Build the route-classification inventory
    - Add a fixture listing every API route as `public`, `authenticated`, or `role:<name>`, derived from the FastAPI route table.
    - _Requirements: 3.2_
  - [ ] 4.2 Confirm admin/operator surfaces reject under-privileged callers
    - Audit metrics, compliance-records, and knowledge-source admin routes for explicit role dependencies; fix any drift. Confirm the ML internal-key guard on protected prefixes.
    - _Requirements: 3.1, 3.4, 3.5_
  - [ ]* 4.3 **[PBT]** Write route-coverage property test (hypothesis/pytest)
    - **Property 9: Route coverage**
    - **Validates: Requirements 3.2, 3.3**

- [ ] 5. Input validation and request limits
  - [ ] 5.1 Add the request-body-size middleware
    - Add `RequestBodyLimitMiddleware` (gated by `hardening_request_body_limit_enabled`) returning a 413-class PII-free response above `hardening_request_body_max_bytes`; preserve ML `_MAX_AUDIO_BYTES`.
    - _Requirements: 4.1, 4.2_
  - [ ] 5.2 Document and enforce list/batch caps
    - Reaffirm research-job caps and add explicit documented maxima to any unbounded list/batch input; keep PII-free 422 validation responses.
    - _Requirements: 4.3, 4.5_
  - [ ] 5.3 Reaffirm ownership checks on client-supplied identifiers
    - Audit endpoints that accept client-supplied resource ids and confirm owner/role scoping.
    - _Requirements: 4.4_
  - [ ]* 5.4 **[PBT]** Write body-size-enforcement property test (hypothesis)
    - **Property 10: Body-size enforcement**
    - **Validates: Requirements 4.1**
  - [ ]* 5.5 **[PBT]** Write ownership-enforcement property test (hypothesis)
    - **Property 11: Ownership enforcement**
    - **Validates: Requirements 4.4**

- [ ] 6. Rate limiting and abuse protection
  - [ ] 6.1 Add rate-limit fail-closed fallback
    - In `core/rate_limit.py`, when `hardening_rate_limit_fail_closed` and the distributed backend returns `None`, enforce via the in-process limiter instead of passing through.
    - _Requirements: 5.2, 5.3_
  - [ ] 6.2 Document recommended production limiter config
    - In `.env.example` / deploy docs, recommend distributed rate limiting + login limiting with `REDIS_URL` for multi-replica production and flag the current `false` defaults.
    - _Requirements: 5.5_
  - [ ]* 6.3 **[PBT]** Write rate-limit fail-closed property test (hypothesis)
    - **Property 12: Rate-limit fail-closed**
    - **Validates: Requirements 5.3**
  - [ ]* 6.4 **[PBT]** Write proxy-trust-soundness property test (hypothesis)
    - **Property 13: Proxy-trust soundness**
    - **Validates: Requirements 5.6**

- [ ] 7. Health, readiness and graceful degradation
  - [ ] 7.1 Add the dependency-aware readiness probe
    - In `services/api/src/clara_api/api/v1/endpoints/health.py`, add `GET /health/ready` (gated by `hardening_readiness_probe_enabled`) probing DB, Redis (if configured), and ML, returning 200 `ready` or 503 with a no-PII reason code; keep `/health` as liveness.
    - _Requirements: 6.1, 6.2, 6.3_
  - [ ] 7.2 Add container healthchecks to the deploy stack
    - In `deploy/docker/docker-compose.app.yml` and `docker-compose.deploy.yml`, add healthchecks for `api` (`/health`), `ml` (`/health`), and `web` (`/`).
    - _Requirements: 6.4_
  - [ ] 7.3 Implement the `CircuitBreaker` around the LLM/embedding client
    - Create `services/ml/src/clara_ml/llm/circuit_breaker.py` wrapping the DeepSeek/embedding retry loop: open after the failure threshold, short-circuit to the existing labeled local fallback for the cool-down, then half-open probe. Gated off by default.
    - _Requirements: 6.5_
  - [ ] 7.4 Stop forcing production DB fallback in deploy/CD
    - In `docker-compose.deploy.yml` and `.github/workflows/cd.yml`, stop emitting `DATABASE_FALLBACK_ENABLED=true` for production; document the explicit opt-in. Preserve the in-code prod fallback guard.
    - _Requirements: 6.6_
  - [ ]* 7.5 **[PBT]** Write readiness-reflects-dependencies property test (hypothesis)
    - **Property 14: Readiness reflects dependencies**
    - **Validates: Requirements 6.1, 6.2**
  - [ ]* 7.6 Write liveness-preservation example test
    - Assert `/health`, `/api/v1/health`, and ML `/health` keep their current 200 shape.
    - **Property 15: Liveness preserved**
    - _Requirements: 6.3_
  - [ ]* 7.7 **[PBT]** Write circuit-breaker open-and-degrade property test (hypothesis)
    - **Property 16: Circuit breaker opens and degrades**
    - **Validates: Requirements 6.5**
  - [ ]* 7.8 **[PBT]** Write no-implicit-prod-fallback property test (hypothesis)
    - **Property 17: No implicit prod DB fallback**
    - **Validates: Requirements 6.6**
  - [ ]* 7.9 **[PBT]** Write timeout-floor-invariant property test (hypothesis)
    - **Property 18: Timeout-floor invariant preserved**
    - **Validates: Requirements 6.7, 10.3**

- [ ] 8. Structured logging without PII
  - [ ] 8.1 Add structured logging + redaction filter + correlation id
    - Create `services/api/src/clara_api/core/logging_config.py` with `configure_logging(settings)` installing a JSON formatter and a `RedactionFilter` (reusing the compliance redaction projection) when `hardening_structured_logging_enabled`; add a correlation-id middleware surfacing the id in logs and a response header. Mirror the filter in ML.
    - _Requirements: 7.1, 7.2, 7.3_
  - [ ] 8.2 Harden the generic exception handler logging
    - Ensure `generic_exception_handler` logs error type + correlation id without request bodies; preserve the production secure-error-message client response.
    - _Requirements: 7.3, 7.4_
  - [ ] 8.3 Add the Content-Security-Policy header
    - In the API `add_security_headers` middleware, add a CSP header gated by `hardening_csp_enabled` (default off), alongside the existing headers.
    - _Requirements: 7.4_
  - [ ]* 8.4 **[PBT]** Write no-PII-logging property test (hypothesis)
    - **Property 19: No-PII logging**
    - **Validates: Requirements 7.2, 7.3**
  - [ ]* 8.5 **[PBT]** Write secure-error-message property test (hypothesis)
    - **Property 20: Secure error messages preserved**
    - **Validates: Requirements 7.4**

- [ ] 9. Dependency remediation and supply-chain gate
  - [ ] 9.1 Remediate critical and high-severity dependency vulnerabilities
    - Across `services/api`, `services/ml`, and `apps/web`, upgrade/replace/justifiably-accept the reported critical and high-severity findings; record outcomes.
    - _Requirements: 8.1, 8.3_
  - [ ] 9.2 Strengthen the CI supply-chain gate
    - In `.github/workflows/ci.yml`, make `security-audit` block on CRITICAL and (for default-branch changes) HIGH findings; broaden `npm audit` toward dev where feasible; keep the Trivy container scan.
    - _Requirements: 8.2, 8.3, 8.4_
  - [ ] 9.3 Record accepted/ignored findings
    - Create `docs/security/accepted-findings.md` listing each unfixable finding, its compensating control, and a review date; document the Dependabot triage/merge cadence.
    - _Requirements: 8.4, 8.5, 8.6_
  - [ ]* 9.4 **[PBT]** Write supply-chain-gate severity test (hypothesis/pytest)
    - **Property 21: Supply-chain gate severity**
    - **Validates: Requirements 8.2**
  - [ ]* 9.5 Write accepted-findings completeness test
    - Assert every entry in `accepted-findings.md` has a justification and review date.
    - **Property 22: Accepted-findings completeness**
    - _Requirements: 8.4, 8.6_

- [ ] 10. Backup/restore and migration safety
  - [ ] 10.1 Author the backup/restore runbook and schedule
    - Create `docs/ops/backup-restore.md` with the Postgres backup schedule, retention, restore procedure, and a rehearsed restore-drill checklist.
    - _Requirements: 9.1, 9.2_
  - [ ] 10.2 Add a pre-migrate backup step and downgrade check to CD
    - In `.github/workflows/cd.yml`, add a pre-migrate backup step and a check that the migration to be deployed defines a downgrade; document rollback to the prior image/backup.
    - _Requirements: 9.3, 9.5_
  - [ ] 10.3 Confirm the production migration-management guard
    - Verify `phr/migration_guard.py` still requires migration-managed schema in production (no behavior change).
    - _Requirements: 9.4_
  - [ ]* 10.4 **[PBT]** Write migration-downgrade-presence test (hypothesis/pytest)
    - **Property 23: Migration downgrade presence**
    - **Validates: Requirements 9.3**
  - [ ]* 10.5 Write migration-managed-schema example test
    - Assert the production schema guard rejects a create-all-produced schema.
    - **Property 24: Migration-managed schema preserved**
    - _Requirements: 9.4_

- [ ] 11. Performance and resource limits
  - [ ] 11.1 Set production worker concurrency and DB pool sizing
    - In the deploy stack and `.env.example`, set API/ML `UVICORN_WORKERS` to production values and define DB pool sizing relative to worker count; preserve `pool_pre_ping`.
    - _Requirements: 10.1, 10.2_
  - [ ] 11.2 Audit outbound-call timeouts and bounded retries
    - Confirm every outbound dependency call (DB, Redis, LLM, embedding, OCR, search) carries an explicit timeout and that retries stay within the `DEEPSEEK_RETRIES_PER_BASE` ceiling.
    - _Requirements: 10.3, 10.4_
  - [ ] 11.3 Confirm latency/error metrics exclude PII
    - Verify the metrics surface exposes latency/error-rate signals with no PII.
    - _Requirements: 10.5_
  - [ ]* 11.4 **[PBT]** Write bounded-retries property test (hypothesis)
    - **Property 25: Bounded retries**
    - **Validates: Requirements 10.4**

- [ ] 12. Safety and flags-off regression suite
  - [ ] 12.1 Set up the safety-regression module and shared fixtures
    - Create a dedicated regression module with fixtures for roles, cookie-vs-bearer auth, the `HARDENING_*` flag matrix, and adversarial-PII payloads, locking RBAC, no-PII, and flags-off invariants across tracks.
    - _Requirements: 11.2, 11.6_
  - [ ]* 12.2 Write the flags-off baseline-equivalence regression test
    - With every `HARDENING_*` flag off, assert the middleware chain, auth flow, health endpoints, and response shapes equal the pre-feature baseline.
    - _Requirements: 11.1, 11.2, 11.6_
  - [ ]* 12.3 **[PBT]** Write guardrail-preservation property test (hypothesis)
    - **Property 26: Guardrail preservation** (emergency fast-path, FIDES CRITICAL block, no-PII telemetry)
    - **Validates: Requirements 11.3**

- [ ] 13. Backend checkpoint — CLARA_API & CLARA_ML quality gates
  - Ensure `make lint` and the API and ML service test suites pass after the backend epics (1–11 backend tasks, 12). Ask the user if questions arise.
  - _Requirements: 11.6_

- [ ] 14. Final checkpoint — full quality gates
  - Ensure `make lint`, the API/ML suites, the web lint+build, the strengthened supply-chain gate, the container scan, and the docker-compose smoke all pass; confirm every new runtime capability is default-off, the no-PII/RBAC/CSRF/timeout-floor invariants hold, the secret-rotation and backup runbooks exist, and each property has its test. Ask the user if questions arise.
  - _Requirements: 8.2, 11.2, 11.3, 11.6_

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP, but the Epic 12 safety/flags-off suite is strongly recommended and should not be skipped — it locks the RBAC, no-PII, CSRF, and backward-compatibility invariants the rest of the work must preserve.
- Each task references specific requirement clauses for traceability; property-test (**[PBT]**) tasks additionally cite their design Property number (1–26).
- Property tests use `hypothesis` (Python), run ≥100 generated iterations, and are tagged `Feature: clara-platform-hardening, Property {n}`.
- All new runtime capabilities are additive and default-off; with every `HARDENING_*` flag off, request/response shapes and side effects equal the pre-feature baseline (Requirement 11.2). Operational/CI hardening (secret sourcing, prod-fallback opt-in, supply-chain thresholds, backups, worker/pool sizing) is applied via deploy/CI configuration and is independently reversible.
- The hardening layer extends existing primitives (`RedisSecurityStore`, `RateLimiterMiddleware`, `LoginGuard`, the `add_security_headers` middleware, the compliance redaction projection, `db/session.py`, `core/timeouts.py`, the CI `security-audit`/`container-scan` jobs) — no duplicate control path is introduced.
- All 26 design properties are covered: P1→1.5, P2→2.5, P3→2.6, P4→3.5, P5→3.6, P6→3.7, P7→3.8, P8→3.9, P9→4.3, P10→5.4, P11→5.5, P12→6.3, P13→6.4, P14→7.5, P15→7.6, P16→7.7, P17→7.8, P18→7.9, P19→8.4, P20→8.5, P21→9.4, P22→9.5, P23→10.4, P24→10.5, P25→11.4, P26→12.3.

## Task Dependency Graph

Same-file tasks are serialized into different waves to avoid write conflicts:
`core/config.py` (1.1 isolated), `auth.py` (3.2 after 3.1), `rbac.py` (3.3
isolated), `rate_limit.py` (6.1 isolated), `health.py` (7.1 isolated),
`docker-compose.deploy.yml` (7.2→7.4), `cd.yml` (7.4→10.2), and `ci.yml` (9.2
isolated). Shared modules (`session_security.py` 3.1, `circuit_breaker.py` 7.3,
`logging_config.py` 8.1) are built before the integration tasks (3.2/3.3, 8.2)
that consume them. Property tests live in their own files and parallelize freely
once their target module exists. Documentation tasks (1.4, 2.2, 2.3, 9.3, 10.1)
are independent and need no code.

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.4", "2.1", "2.2", "2.3", "3.1", "4.1", "5.1", "6.1", "7.1", "7.3", "8.1", "9.1", "9.3", "10.1", "11.1", "12.1"] },
    { "id": 1, "tasks": ["1.3", "1.5", "2.4", "2.5", "2.6", "3.2", "3.3", "3.4", "4.2", "5.2", "5.3", "6.2", "7.2", "8.2", "8.3", "9.2", "10.3", "11.2", "11.3"] },
    { "id": 2, "tasks": ["3.5", "3.6", "3.7", "3.8", "3.9", "4.3", "5.4", "5.5", "6.3", "6.4", "7.4", "7.5", "7.6", "7.7", "7.8", "7.9", "8.4", "8.5", "9.4", "9.5", "10.4", "10.5", "11.4", "12.2", "12.3"] },
    { "id": 3, "tasks": ["13"] },
    { "id": 4, "tasks": ["14"] }
  ]
}
```
