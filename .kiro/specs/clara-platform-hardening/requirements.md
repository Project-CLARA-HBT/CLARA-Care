# Requirements Document

## Introduction

This feature hardens the CLARA-Care platform to **production-grade quality**
across four pillars — **authentication/authorization**, **reliability/resilience**,
**performance**, and **security** — spanning the API service
(`services/api/src/clara_api`), the ML service (`services/ml/src/clara_ml`), the
web app (`apps/web`), the deploy stack (`deploy/docker/*`), and CI/CD
(`.github/workflows/*`).

It is **additive, feature-flagged, and back-compatible**. It does not change
clinical reasoning, the router, the RAG pipeline, or any existing safety
guardrail (RBAC via `require_roles`, CSRF double-submit, no-PII telemetry,
emergency fast-path, FIDES verification, the timeout-floor invariant). Every new
behavior that changes runtime semantics is gated behind a feature flag whose
**default preserves current behavior**; with all hardening flags off the system
is byte-for-byte equivalent to today.

The work closes concrete, observed gaps in the current platform, including:

- **Plaintext default secrets** baked into `deploy/docker/docker-compose.app.yml`
  (`JWT_SECRET_KEY:-change_me_super_secret`,
  `AUTH_BOOTSTRAP_ADMIN_PASSWORD:-Clara#Admin2026!`,
  `ML_INTERNAL_API_KEY:-clara_internal_key_default_2026`,
  `POSTGRES_PASSWORD:-clara_dev_password`, `MINIO_ROOT_PASSWORD:-minioadmin`,
  `NEO4J_AUTH:-neo4j/clara_dev_password`), and a **deploy SSH password that was
  recently exposed in plaintext in an operator transcript**.
- **Static health endpoints** (`/health`, `/api/v1/health`, ML `/health`) that
  always return `{"status": "ok"}` regardless of dependency state, and the
  absence of container-level healthchecks for `api`/`ml`/`web`.
- **Implicit production database fallback** to ephemeral SQLite:
  `docker-compose.deploy.yml` and `cd.yml` both set
  `DATABASE_FALLBACK_ENABLED=true` for staging *and* production, which defeats
  the in-code production fallback guard.
- **Session weaknesses**: 30-day refresh tokens with no server-side revocation
  or denylist, and refresh-reuse detection (`AUTH_REFRESH_REJECT_CONFLICT`)
  defaulting off.
- **No circuit breaker** for repeated downstream LLM/embedding failures (only
  per-base retries with backoff).
- **Unstructured logging** with `logger.exception(...)` that can capture PII via
  tracebacks, and no log redaction filter.
- **~105 Dependabot dependency vulnerabilities (1 critical, 40 high)** on the
  default branch; the CI security gates only block on `CRITICAL` and treat
  high-severity and PR-time findings as advisory.

Nothing in this feature changes CLARA-Care's positioning as decision-support
software; it makes the platform's runtime posture safe, observable, and
operationally defensible.

## Glossary

- **Hardening_System**: The cross-service layer added by this feature
  (configuration, middleware, probes, jobs, CI gates) that enforces the
  production-grade controls described here.
- **Secret Store / Managed Secret Store**: An external system of record for
  secrets (e.g., cloud secret manager, Vault, or GitHub Actions encrypted
  secrets injected at deploy time) from which credentials are sourced at
  runtime, never committed in plaintext.
- **Plaintext Default Secret**: A real-looking credential value embedded as a
  shell default (`${VAR:-value}`) in a compose file or workflow, usable if the
  environment variable is unset.
- **Credential Rotation**: Replacing a secret value (and invalidating the prior
  value) following a defined procedure and on a defined cadence or upon exposure.
- **Liveness Probe**: An endpoint reporting whether the process is running and
  should not be restarted.
- **Readiness Probe**: An endpoint reporting whether the process can currently
  serve traffic, derived from the health of its critical dependencies (database,
  cache, downstream ML).
- **Graceful Degradation**: Continuing to serve a reduced but safe response when
  a non-critical dependency is unavailable, rather than failing the request.
- **Circuit Breaker**: A control that, after a threshold of consecutive
  downstream failures, short-circuits further calls for a cool-down window and
  returns a fast degraded response.
- **DB Fallback**: The `services/api/.../db/session.py` behavior that switches
  from the primary database to a configured fallback URL when the primary is
  unreachable.
- **No-PII Logging**: The invariant that emitted logs, metrics, traces, and
  alerts contain no personal or health data (names, emails, query text, drug
  lists, free-text PHR).
- **Refresh Token Rotation**: Issuing a new refresh token on each refresh and
  invalidating the prior one, so a replayed (stolen) refresh token is detected.
- **Token Denylist**: A server-side record of revoked token identifiers (`jti`)
  consulted on each authenticated request until natural expiry.
- **Dependency Remediation**: Upgrading, replacing, or explicitly accepting
  (with documented justification) a vulnerable dependency.
- **Supply-Chain Gate**: A CI check (pip-audit, npm audit, Trivy) that fails the
  build when vulnerabilities exceed a defined severity threshold.
- **Backup/Restore Drill**: A rehearsed, verified procedure that produces a
  restorable backup and confirms a restore succeeds.
- **Migration Safety Gate**: A pre-deploy control ensuring a database migration
  has a tested downgrade and is preceded by a backup.
- **Feature flag**: A configuration switch enabling a new hardening behavior
  while defaulting to the value that preserves current behavior.

## Requirements

### Requirement 1: Secret Management and Credential Rotation

**User Story:** As a platform operator, I want every secret sourced from a managed
store with no plaintext defaults and a rotation procedure, so that a leaked
credential cannot compromise the platform and exposed secrets can be retired.

#### Acceptance Criteria

1. THE Hardening_System SHALL require that production secrets (JWT signing key, ML internal API key, database password, bootstrap admin password, object-store and graph-store credentials, LLM/embedding provider keys) are sourced from a managed secret store and never from a plaintext default in a compose file or workflow.
2. WHERE a required production secret is absent at startup, THE Hardening_System SHALL fail fast with a descriptive, secret-value-free error rather than starting with an insecure default.
3. THE Hardening_System SHALL define and document a credential-rotation procedure covering the JWT signing key, the ML internal API key, database and infrastructure passwords, and provider API keys, including the steps to invalidate the prior value.
4. WHEN a secret is identified as exposed, THE Hardening_System SHALL treat rotation of that secret as mandatory and SHALL record the rotation as completed.
5. THE Hardening_System SHALL require rotation of the deploy SSH credential that was exposed in plaintext in the operator transcript, and SHALL replace SSH password authentication for deploys with key-based authentication whose private key is held in the managed secret store.
6. THE Hardening_System SHALL ensure no secret value is written to a committed file, build log, CI log, or container image layer.
7. WHERE the JWT signing key is rotated, THE Hardening_System SHALL support a key-overlap window so that tokens signed with the prior key remain valid until natural expiry without a forced mass logout.

### Requirement 2: Authentication and Session Hardening

**User Story:** As a security owner, I want sessions that can be revoked, refresh
tokens that rotate, and replay detection, so that a stolen token has a bounded,
detectable blast radius.

#### Acceptance Criteria

1. THE Hardening_System SHALL preserve the existing access/refresh JWT issuance, issuer/type validation, and cookie-vs-bearer extraction behavior.
2. WHERE refresh-token rotation is enabled, WHEN a refresh token is exchanged, THE Hardening_System SHALL issue a new refresh token and invalidate the presented one.
3. WHEN a previously-invalidated (rotated or revoked) refresh token is presented, THE Hardening_System SHALL reject the request and SHALL record a no-PII reuse-detection event.
4. WHERE token revocation is enabled, WHEN a user logs out, THE Hardening_System SHALL add the token identifier (`jti`) to a denylist consulted on subsequent authenticated requests until the token's natural expiry.
5. THE Hardening_System SHALL keep brute-force login protection in place AND SHALL provide a configurable fail-closed mode so that, when the distributed limiter backend is unavailable, login throttling does not silently disappear.
6. THE Hardening_System SHALL preserve CSRF double-submit enforcement for cookie-authenticated mutating requests and the existing bearer-token exemption.
7. WHERE all session-hardening flags are off, THE Hardening_System SHALL behave equivalently to the current authentication flow.

### Requirement 3: Authorization — Deny-by-Default and Route Coverage

**User Story:** As a security reviewer, I want every non-public route to require an
explicit role or authenticated identity, so that no endpoint is unintentionally
exposed.

#### Acceptance Criteria

1. THE Hardening_System SHALL preserve `require_roles` semantics, including admin as an authorized role for role-gated routes.
2. THE Hardening_System SHALL maintain an inventory that classifies every API route as public, authenticated, or role-restricted.
3. WHEN a route is added without an explicit access classification, THE Hardening_System SHALL surface this as a failing check in the route-coverage test.
4. THE Hardening_System SHALL ensure admin/operator-only surfaces (metrics, compliance records, knowledge-source administration) reject unauthenticated and under-privileged callers.
5. THE Hardening_System SHALL preserve the ML service internal-key protection on its protected path prefixes.

### Requirement 4: Input Validation and Request Limits

**User Story:** As an operator, I want oversized or malformed inputs rejected
early, so that abusive or accidental payloads cannot exhaust resources.

#### Acceptance Criteria

1. THE Hardening_System SHALL enforce a configurable maximum request body size for API endpoints and reject larger requests with a clear 413-class response.
2. THE Hardening_System SHALL preserve the existing ML audio upload size and content-type limits.
3. THE Hardening_System SHALL validate all request bodies against typed schemas and SHALL return a PII-free 422 response for validation failures.
4. WHERE a request includes client-controlled identifiers used for ownership checks, THE Hardening_System SHALL enforce that the authenticated subject owns the referenced resource.
5. THE Hardening_System SHALL bound the size and count of list/batch inputs to documented maxima.

### Requirement 5: Rate Limiting and Abuse Protection

**User Story:** As an operator, I want effective rate limiting in production with
sensible per-actor and per-route caps, so that abuse and runaway clients are
contained without harming legitimate users.

#### Acceptance Criteria

1. THE Hardening_System SHALL preserve the existing global IP+path rate limiter and its 429 response shape with a `Retry-After` header.
2. WHERE distributed rate limiting is enabled, THE Hardening_System SHALL enforce limits across all API replicas using the shared backend.
3. THE Hardening_System SHALL provide a configurable fail-closed option so that, when the distributed limiter backend is unavailable, the limiter falls back to the in-process limiter rather than disabling enforcement.
4. THE Hardening_System SHALL preserve the existing research-job caps (max workers, max pending, max active per user).
5. THE Hardening_System SHALL document the recommended production rate-limit and distributed-limiter configuration and SHALL flag insecure-by-omission defaults in the deploy stack.
6. THE Hardening_System SHALL keep the proxy-trust resolution behavior so that client IPs are only derived from forwarded headers when the immediate peer is a trusted proxy.

### Requirement 6: Graceful Degradation, Health and Readiness Probes

**User Story:** As an operator, I want honest health and readiness signals and safe
degradation when dependencies fail, so that orchestration routes traffic
correctly and partial outages do not become total ones.

#### Acceptance Criteria

1. THE Hardening_System SHALL expose a liveness probe that reflects process health and a readiness probe that reflects the health of critical dependencies (database, and where configured, cache and downstream ML).
2. WHEN a critical dependency is unavailable, THE Hardening_System SHALL report not-ready from the readiness probe while keeping the liveness probe positive if the process itself is healthy.
3. THE Hardening_System SHALL preserve the static `/health` and `/api/v1/health` and ML `/health` endpoints as liveness signals for backward compatibility.
4. THE Hardening_System SHALL add container-level healthchecks for the `api`, `ml`, and `web` services in the deploy stack.
5. WHERE a non-critical downstream call repeatedly fails, THE Hardening_System SHALL open a circuit breaker for a cool-down window and return a labeled degraded response, reusing the existing local/deterministic fallback where available.
6. THE Hardening_System SHALL NOT enable implicit production database fallback to ephemeral SQLite by default, and SHALL require an explicit, documented opt-in for any production fallback.
7. THE Hardening_System SHALL preserve the startup timeout-floor invariant so the API ML request timeout never sits below the downstream synthesis timeout.

### Requirement 7: Structured Logging Without PII

**User Story:** As an operator and a data-protection owner, I want structured,
correlatable logs that never contain personal or health data, so that I can
debug and audit without creating a privacy liability.

#### Acceptance Criteria

1. WHERE structured logging is enabled, THE Hardening_System SHALL emit logs in a structured (JSON) format with a stable set of fields including timestamp, level, service, and a request correlation id.
2. THE Hardening_System SHALL apply a redaction projection so that emitted logs, metrics, traces, and alerts contain no PII (names, emails, query text, drug lists, free-text PHR).
3. WHEN an unhandled exception is logged, THE Hardening_System SHALL record the error type and a correlation id without emitting request bodies or user-identifying free text.
4. THE Hardening_System SHALL preserve the existing secure-error-message behavior so that 5xx responses to clients never leak internal detail in production.
5. WHERE structured logging is off, THE Hardening_System SHALL behave equivalently to the current logging configuration.

### Requirement 8: Dependency Vulnerability Remediation and Supply-Chain Hardening

**User Story:** As a security owner, I want the known dependency vulnerabilities
remediated and the CI gates strengthened, so that the default branch stops
shipping critical and high-severity vulnerabilities.

#### Acceptance Criteria

1. THE Hardening_System SHALL remediate the reported critical dependency vulnerability and the high-severity dependency vulnerabilities across `services/api`, `services/ml`, and `apps/web` by upgrading, replacing, or explicitly and justifiably accepting each.
2. THE Hardening_System SHALL fail the CI supply-chain gate on critical findings AND SHALL fail on high-severity findings for changes targeting the default branch.
3. THE Hardening_System SHALL audit application dependencies including, where feasible, development dependencies, rather than runtime-only scope.
4. THE Hardening_System SHALL keep the container image scan and SHALL record an inventory of accepted/ignored findings with justification and review date.
5. THE Hardening_System SHALL preserve the existing Dependabot configuration and SHALL document the triage and merge cadence for dependency update PRs.
6. WHERE a vulnerability has no available fix, THE Hardening_System SHALL document the compensating control and the conditions under which the acceptance is revisited.

### Requirement 9: Backup, Restore and Migration Safety

**User Story:** As an operator, I want verified backups and safe migrations, so
that a failed deploy or data incident is recoverable without data loss.

#### Acceptance Criteria

1. THE Hardening_System SHALL define an automated backup procedure for the primary datastore with a documented schedule and retention.
2. THE Hardening_System SHALL define and rehearse a restore procedure that verifies a backup is actually restorable.
3. WHEN a database migration is deployed, THE Hardening_System SHALL require that the migration has a tested downgrade and is preceded by a backup.
4. THE Hardening_System SHALL preserve the existing migration-management guard that requires the schema in production to be created by migrations rather than the create-all fallback.
5. WHERE a migration or deploy fails its post-deploy smoke checks, THE Hardening_System SHALL support a documented rollback to the prior image and, if needed, the prior backup.

### Requirement 10: Performance and Resource Limits

**User Story:** As an operator, I want sane concurrency, connection-pool, and
timeout settings, so that the platform performs predictably under load and one
slow dependency does not stall the whole service.

#### Acceptance Criteria

1. THE Hardening_System SHALL document and apply production-appropriate worker concurrency for the API and ML services rather than a single worker.
2. THE Hardening_System SHALL configure database connection-pool sizing appropriate to the worker concurrency and SHALL preserve the existing `pool_pre_ping` liveness check.
3. THE Hardening_System SHALL bound every outbound dependency call (database, cache, LLM, embedding, OCR, search) with an explicit timeout.
4. THE Hardening_System SHALL preserve the existing per-base retry-with-backoff behavior for LLM and external calls and SHALL ensure retries are bounded.
5. THE Hardening_System SHALL expose latency and error-rate metrics sufficient to detect performance regressions, without introducing PII into the metrics surface.

### Requirement 11: Regression-Safe, Default-Off Flagged Rollout and Guardrail Preservation

**User Story:** As a platform owner, I want every hardening change to default to
current behavior and preserve all safety guardrails, so that adoption carries no
clinical or operational regression risk.

#### Acceptance Criteria

1. THE Hardening_System SHALL gate every new behavior that changes runtime semantics behind a feature flag whose default preserves current behavior.
2. WHERE all hardening flags are off, THE Hardening_System SHALL behave equivalently to the pre-feature system in request/response shapes and side effects.
3. THE Hardening_System SHALL preserve every existing safety guardrail: RBAC, CSRF, emergency fast-path, FIDES CRITICAL-claim blocking, no-PII telemetry, and the timeout-floor invariant.
4. THE Hardening_System SHALL document a staged production enablement order with per-flag rollback.
5. THE Hardening_System SHALL NOT modify clinical reasoning, the router, or the RAG ranking behavior.
6. THE Hardening_System SHALL add a regression test asserting flags-off equivalence wherever a shared path is touched.
