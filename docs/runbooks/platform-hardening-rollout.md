# Runbook: CLARA platform hardening (`HARDENING_*`) staged enablement

Spec: `clara-platform-hardening` · Task 1.4 (staged-rollout runbook).

This runbook covers the staged, per-environment enablement of the production
hardening layer added across the API (`services/api/src/clara_api`), the ML
service (`services/ml/src/clara_ml`), the web app (`apps/web`), and the deploy
stack. The layer is **additive, feature-flagged, and default-off**; with every
`HARDENING_*` flag off the system is byte-for-byte equivalent to the pre-feature
baseline in request/response shapes and side effects (Requirement 11.1, 11.2;
design Property 1 — flags-off equivalence). Nothing here changes clinical
reasoning, the router, the RAG ranking pipeline, or any existing safety
guardrail (RBAC, CSRF, emergency fast-path, FIDES CRITICAL block, no-PII
telemetry, the timeout-floor invariant; Requirement 11.3, 11.5).

The model is always: **enable in staging → verify the per-flag property check(s)
+ the flags-off regression gate + guardrail preservation → flip in production →
roll back if needed.** Each flag is independently reversible by a single config
change with no schema or data implications, and without redeploying clinical
code (Requirement 11.4).

## Summary — runtime feature flags (all default OFF)

API flags are read in `services/api/src/clara_api/core/config.py`; the
circuit-breaker flag/keys are mirrored in `services/ml/src/clara_ml/config.py`.
Flags are read from config/env at service start, so flipping one means updating
the environment's config and restarting/redeploying the affected service — there
is no in-request toggle. When a flag is off, the corresponding enforcement is
skipped and behavior matches today exactly.

| Capability | Flag | Service | Default |
| --- | --- | --- | --- |
| Refresh-token rotation + reuse detection | `HARDENING_REFRESH_ROTATION_ENABLED` | API | `false` |
| Access/refresh `jti` denylist (logout revocation) | `HARDENING_TOKEN_DENYLIST_ENABLED` | API | `false` |
| Login throttle fail-closed (limiter backend down) | `HARDENING_LOGIN_FAIL_CLOSED` | API | `false` |
| Rate-limit fail-closed fallback (limiter backend down) | `HARDENING_RATE_LIMIT_FAIL_CLOSED` | API | `false` |
| Request body-size limit | `HARDENING_REQUEST_BODY_LIMIT_ENABLED` (+ `HARDENING_REQUEST_BODY_MAX_BYTES`) | API | `false` |
| Dependency-aware readiness probe (`/health/ready`) | `HARDENING_READINESS_PROBE_ENABLED` | API | `false` |
| Circuit breaker on LLM/embedding downstream | `HARDENING_CIRCUIT_BREAKER_ENABLED` (+ failure-threshold, cool-down keys) | ML | `false` |
| Structured JSON logging + redaction + correlation id | `HARDENING_STRUCTURED_LOGGING_ENABLED` | API (mirrored in ML) | `false` |
| Content-Security-Policy response header | `HARDENING_CSP_ENABLED` | API | `false` |

> **Operational / CI hardening is out of band.** Secret sourcing
> (`docs/runbooks/credential-rotation.md`), prod-fallback opt-in
> (`DATABASE_FALLBACK_ENABLED`), the supply-chain gate thresholds in
> `.github/workflows/ci.yml`, backup/restore (`docs/runbooks/backup-restore.md`), and
> worker/pool sizing are governed by deploy/CI configuration rather than runtime
> flags. They are applied through the deploy stack and are independently
> reversible, but they are **not** part of the per-flag flip procedure below.
> Sequence them with the deploy that ships them, not with this runbook.

## Recommended production limiter configuration (Requirement 5.5)

The rate-limit and login-throttle controls already exist; what changes for
production is **where the counters live**. By default the global IP+path limiter
(`RateLimiterMiddleware`) and the login throttle (`LoginGuard`) count
**in-process**, per replica. In a multi-replica deployment that is
insecure-by-omission: each replica enforces the cap independently, so the
effective per-actor allowance is multiplied by the replica count, and a client
load-balanced across N replicas gets ~N× the intended budget.

Recommended production values (also annotated in `.env.example`):

| Key | Dev default | Recommended production | Why |
| --- | --- | --- | --- |
| `RATE_LIMIT_DISTRIBUTED_ENABLED` | `false` | `true` | Enforce the global limiter cap across **all** API replicas via the shared Redis backend instead of per-replica. |
| `AUTH_LOGIN_DISTRIBUTED_ENABLED` | `false` | `true` | Enforce login throttling cluster-wide so brute-force attempts can't fan out across replicas. |
| `REDIS_URL` | `redis://localhost:6379/0` | reachable managed Redis | Shared backend the two flags above and the security store depend on; must be reachable from every replica. |
| `HARDENING_RATE_LIMIT_FAIL_CLOSED` | `false` | `true` | When the distributed backend is unavailable, fall back to the in-process limiter instead of passing traffic through unthrottled (Requirement 5.3; staged per the per-flag procedure above). |
| `HARDENING_LOGIN_FAIL_CLOSED` | `false` | `true` | Same fail-closed posture for login throttling (Requirement 2.5). |
| `GLOBAL_RATE_LIMIT_PER_MIN` | `120` | tune to expected per-client traffic | Per-actor cap per `RATE_LIMIT_WINDOW_SECONDS`; the default is a starting point, not a tuned production value. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | `60` | Window the cap applies over; keep unless you have a specific reason to change it. |

Proxy-trust (Requirement 5.6) — only relevant when the API sits behind a reverse
proxy or load balancer:

| Key | Default | Recommended production (behind a trusted proxy/LB) | Why |
| --- | --- | --- | --- |
| `RATE_LIMIT_TRUST_PROXY_HEADERS` | `false` | `true` | Honor `X-Forwarded-For` so the limiter keys on the real client IP rather than the proxy's. |
| `RATE_LIMIT_TRUSTED_PROXIES` | _(empty)_ | the proxy/LB host(s) or CIDR(s) | Forwarded headers are honored **only** when the immediate peer is in this set; without it, clients can spoof their IP and evade per-actor limits. Leave both keys at their defaults if there is no trusted proxy in front of the API. |

Insecure-by-omission flags to check in the deploy stack before going live: any
multi-replica production environment that leaves `RATE_LIMIT_DISTRIBUTED_ENABLED`
or `AUTH_LOGIN_DISTRIBUTED_ENABLED` at `false`, that has no reachable
`REDIS_URL`, or that enables proxy-header trust without pinning
`RATE_LIMIT_TRUSTED_PROXIES`, is under-enforcing its limits and should be
corrected before launch.

The distributed-limiter and proxy-trust keys are **deploy/operational**
configuration (set with the deploy that ships them), not runtime `HARDENING_*`
flips. The two `HARDENING_*_FAIL_CLOSED` flags, however, are runtime flags and
follow the staged per-flag procedure below.

## Per-property suite

These are the targeted, fast suites that gate each enablement. **Do not run the
full or slow test suite** — run only the file(s) for the flag being enabled,
plus the flags-off regression gate. Property tests use `hypothesis` (Python),
run ≥100 generated iterations, and are tagged
`Feature: clara-platform-hardening, Property {n}`.

| Flag | Property / check | Test |
| --- | --- | --- |
| `HARDENING_REFRESH_ROTATION_ENABLED` | P4 rotation invalidates old token; P5 reuse event no-PII | `services/api/tests` (P4, P5) |
| `HARDENING_TOKEN_DENYLIST_ENABLED` | P6 denylisted token rejected until expiry | `services/api/tests` (P6) |
| `HARDENING_LOGIN_FAIL_CLOSED` | P7 login throttle survives backend outage | `services/api/tests` (P7) |
| `HARDENING_RATE_LIMIT_FAIL_CLOSED` | P12 in-process limiter still enforces cap; P13 proxy-trust soundness | `services/api/tests` (P12, P13) |
| `HARDENING_REQUEST_BODY_LIMIT_ENABLED` | P10 body-size enforcement (413-class); P11 ownership enforcement | `services/api/tests` (P10, P11) |
| `HARDENING_READINESS_PROBE_ENABLED` | P14 readiness reflects deps; P15 liveness preserved | `services/api/tests` (P14, P15) |
| `HARDENING_CIRCUIT_BREAKER_ENABLED` | P16 breaker opens and degrades, half-open recovery | `services/ml/tests` (P16) |
| `HARDENING_STRUCTURED_LOGGING_ENABLED` | P19 no-PII logging; P20 secure error messages | `services/api/tests` (P19, P20) |
| `HARDENING_CSP_ENABLED` | CSP header present alongside existing security headers | `services/api/tests` (security-headers) |

### Flags-off regression gate

Before and after any enablement, confirm the flags-off baseline still holds.
With every `HARDENING_*` flag at its default `false`, the middleware chain, auth
flow, health endpoints, and response envelopes are equivalent to the pre-feature
baseline (Requirement 11.2; design Property 1). The standing assertion lives in
the Epic 12 safety-regression module (flags-off baseline-equivalence test) and
the guardrail-preservation property test (Property 26 — emergency fast-path,
FIDES CRITICAL block, no-PII telemetry). Any failure here is a hard stop — do
not promote.

## Prerequisites (one-time, before any environment)

- Spec Epics 1–12 backend work complete for the flag being enabled, and its
  shared module built and consumed: `SessionSecurity`
  (`services/api/src/clara_api/core/session_security.py`) for rotation/denylist,
  the rate-limit fail-closed branch in `core/rate_limit.py`, the
  `RequestBodyLimitMiddleware`, the `/health/ready` router in
  `api/v1/endpoints/health.py`, the `CircuitBreaker`
  (`services/ml/src/clara_ml/llm/circuit_breaker.py`), the structured-logging
  filter (`core/logging_config.py`), and the CSP branch in the API
  `add_security_headers` middleware.
- All `HARDENING_*` flags confirmed declared and **default-off** in
  `services/api/src/clara_api/core/config.py` and (circuit breaker) in
  `services/ml/src/clara_ml/config.py`, and documented with no secret values in
  `.env.example`.
- For the denylist, rotation, and the fail-closed modes: `REDIS_URL` is
  configured and the shared `RedisSecurityStore` backend is reachable in the
  target environment (these flags depend on the distributed backend to do their
  job; verify connectivity first).
- For the readiness probe: the DB, Redis (if configured), and ML `/health`
  endpoints are reachable from the API so a healthy environment reports `ready`.
- Static checks clean: `ruff check services/api/src/clara_api` and
  `ruff check services/ml/src/clara_ml`, with no IDE diagnostics on the touched
  modules.
- The flags-off regression gate and the guardrail-preservation suite are green
  on the build being deployed.

## Staged enablement order

Enable in the order below — lowest user-facing/clinical risk first, security
controls and the readiness probe before the controls that change request
acceptance. Each step is gated on its property check(s) plus the flags-off
regression gate. **Complete each step fully in staging, then production, before
starting the next.** Do not batch multiple flags into a single flip.

1. `HARDENING_CSP_ENABLED` — additive response header only; lowest risk. Verify
   no web console CSP violations before production.
2. `HARDENING_STRUCTURED_LOGGING_ENABLED` — log format + redaction + correlation
   id; observability only, no request-path semantics (P19, P20).
3. `HARDENING_READINESS_PROBE_ENABLED` — adds `/health/ready`; liveness `/health`
   is unchanged (P14, P15). Wire orchestration readiness to it only after it
   reports correctly in staging.
4. `HARDENING_CIRCUIT_BREAKER_ENABLED` (ML) — opens on repeated downstream
   failures and returns the existing labeled local fallback (P16).
5. `HARDENING_RATE_LIMIT_FAIL_CLOSED` — in-process fallback when the distributed
   backend is down (P12, P13).
6. `HARDENING_LOGIN_FAIL_CLOSED` — login throttle survives a limiter-backend
   outage (P7).
7. `HARDENING_TOKEN_DENYLIST_ENABLED` — logout revocation consulted per request
   (P6). Enable before rotation so revoked `jti`s are already honored.
8. `HARDENING_REFRESH_ROTATION_ENABLED` — rotate + invalidate refresh tokens on
   exchange, with no-PII reuse detection (P4, P5).
9. `HARDENING_REQUEST_BODY_LIMIT_ENABLED` (+ `HARDENING_REQUEST_BODY_MAX_BYTES`)
   — enforce a max body size with a 413-class response (P10, P11). Enable last
   and set the maximum deliberately so legitimate large payloads (e.g. uploads)
   are not rejected; preserve the ML `_MAX_AUDIO_BYTES` limit.

## Per-flag procedure

Repeat the following for **each** flag, in the order above.

### Stage 1 — Enable in staging

1. In the **staging** environment, set the flag to `true` on the owning service
   (API for all flags except the circuit breaker, which is ML). For the
   body-size limit, also set `HARDENING_REQUEST_BODY_MAX_BYTES` to the intended
   maximum; for the circuit breaker, confirm the failure-threshold and cool-down
   keys are at the intended values.
2. Restart/redeploy the affected service so the new config is read at start.
3. Confirm activation:
   - **CSP**: responses carry the `Content-Security-Policy` header alongside the
     existing security headers.
   - **Structured logging**: logs are JSON with timestamp, level, service, and a
     correlation id, and the id appears in the response header.
   - **Readiness**: `GET /health/ready` returns `200 ready` in a healthy
     environment; `/health` and `/api/v1/health` still return their 200 liveness
     shape.
   - **Circuit breaker**: forced/observed downstream failures open the breaker
     and return the labeled local fallback without calling out.
   - **Rate-limit / login fail-closed**: with the distributed backend made
     unavailable, enforcement falls back to the in-process limiter/guard instead
     of passing through.
   - **Denylist**: a logged-out token's `jti` is rejected on subsequent requests.
   - **Refresh rotation**: a refresh exchange issues a new refresh token and a
     replay of the prior one is rejected with a no-PII reuse event recorded.
   - **Body limit**: a body above the configured maximum is rejected with a
     413-class PII-free response; a body at or below it is accepted.

### Stage 2 — Verify in staging

1. Run the per-property suite entry for this flag (table above) plus the
   flags-off regression gate. Run **only** those targeted files — not the full
   or slow suite.
2. Confirm zero PII in any log, metric, trace, or alert on the newly active path
   (P19): reuse-detection events, breaker events, denylist entries, and audit
   records carry types, counts, and opaque references only — never names,
   emails, query/answer text, drug lists, or PHR.
3. Confirm guardrails are intact and unchanged: RBAC (`require_roles`), CSRF
   double-submit on cookie-authenticated mutating requests with the bearer
   exemption preserved (P8), the emergency fast-path, FIDES CRITICAL-claim
   blocking, no-PII telemetry, and the timeout-floor invariant (Requirement
   11.3; design Property 26). Confirm secure 5xx error messages leak no internal
   detail in production (P20).
4. **Promotion gate:** proceed only when the property check(s) for this flag and
   the flags-off regression gate pass with zero failures and no guardrail
   regression. Any failure is a hard stop.

### Stage 3 — Flip on in production

1. After staging passes the promotion gate, set the same flag to `true` in the
   **production** environment.
2. Restart/redeploy the affected production service.
3. Confirm activation in production using the same activation checks as Stage 1,
   and confirm no-PII telemetry on the new path.
4. Monitor early production traffic for the newly enabled capability:
   - **CSP / structured logging**: no rise in errors; no unexpected CSP
     violations; logs parse as JSON and correlation ids thread end-to-end.
   - **Readiness**: orchestration routes traffic only to `ready` replicas;
     liveness restarts only truly-dead processes; no flapping.
   - **Circuit breaker**: breaker opens under real downstream failure and
     half-open probes recover; no breaker entering the request path as an error.
   - **Rate-limit / login fail-closed**: enforcement holds during a simulated or
     real backend blip; no silent disabling of throttling.
   - **Denylist / rotation**: logout revocation and refresh replays behave as in
     staging; watch for unexpected 401s indicating over-aggressive revocation.
   - **Body limit**: watch the 413-class rejection rate for false positives
     against legitimate large requests; adjust `HARDENING_REQUEST_BODY_MAX_BYTES`
     if needed.

### Rollback

Rollback is a single config change per flag with no data/schema implications
(the layer is additive and the legacy path is always preserved):

1. In the affected environment, set the flag back to `false` (for the body-size
   limit, the `HARDENING_REQUEST_BODY_MAX_BYTES` value is inert once the enable
   flag is off and may be left as-is).
2. Restart/redeploy the affected service.
3. With the flag off, the corresponding enforcement is skipped and behavior
   reverts to the exact pre-feature baseline (Requirement 11.2; design
   Property 1, verified by the Epic 12 flags-off regression gate).

Flags are independent: rolling one back does not affect the others. No
migration, data backfill, or cleanup is required — the Redis state used by the
denylist/rotation/fail-closed modes is ephemeral and TTL-bound, so it expires on
its own once the flag is off. Flipping the flag off is the normal, sufficient
mitigation and requires no clinical-code redeploy.

## Notes

- Enable the **denylist before rotation** (steps 7 then 8): rotation relies on
  the same revocation machinery, so having the denylist already honored avoids a
  window where a rotated-out `jti` is not yet consulted.
- The body-size limit (step 9) is the only flag that changes which requests are
  *accepted*. Set `HARDENING_REQUEST_BODY_MAX_BYTES` from observed legitimate
  payload sizes (including uploads) and verify in staging before the production
  flip; the ML audio upload size/content-type limits (`_MAX_AUDIO_BYTES`) are
  preserved independently.
- The fail-closed modes (`HARDENING_LOGIN_FAIL_CLOSED`,
  `HARDENING_RATE_LIMIT_FAIL_CLOSED`) only change behavior when the distributed
  backend is unavailable; in a healthy environment they are inert, so verify
  them by simulating a backend outage in staging rather than expecting a visible
  change under normal traffic.
- The circuit breaker never raises into the request path — it returns the
  existing labeled local/deterministic fallback. A flip that surfaces breaker
  errors to clients indicates a wiring bug; roll back and investigate.
- Operational/CI hardening (secret rotation, prod-fallback opt-in, supply-chain
  gate thresholds, backups, worker/pool sizing) ships with its deploy/CI change,
  not this per-flag flip. See `docs/runbooks/credential-rotation.md`,
  `docs/runbooks/backup-restore.md`, and `docs/security/accepted-findings.md`.
