# CLARA Security Remediation Report (2026-04-03)

## Scope

This report maps the latest threat-model findings to implementation status in the current codebase.

## Closed Findings

1. ML service unauthenticated internal surface  
Status: Closed  
Changes:
- API now sends `X-ML-Internal-Key` to ML upstream.
- ML now enforces internal key on `/v1/*`, `/metrics`, `/metrics/json`, `/health/details`, and `/ws/stream`.

2. Missing CSRF protection for cookie-authenticated mutating requests  
Status: Closed (with one controlled exception)  
Changes:
- API middleware enforces CSRF token (cookie + header comparison) for mutating methods.
- Web client now sends CSRF header for mutating requests.

3. Root metrics exposure risk  
Status: Closed  
Changes:
- `/metrics` now requires `METRICS_ACCESS_TOKEN` in production (or returns 404 when not configured).

4. Research upload DoS risk (size/type)  
Status: Closed  
Changes:
- Explicit safety checks and upload caps for research file ingestion.

5. Crawl allowlist bypass when allowlist empty  
Status: Closed  
Changes:
- Empty crawl allowlist is now deny-by-default in ML retrieval gateway.

6. Web token theft risk from localStorage  
Status: Closed  
Changes:
- Web moved auth token handling to memory/cookie-based session flow.

7. Refresh-token ambiguity / token source confusion  
Status: Closed  
Changes:
- Refresh endpoint rejects cookie/payload mismatch (`401` token conflict).

8. Horizontal scaling gap for brute-force/rate-limit (in-memory only)  
Status: Closed (feature available + tested)  
Changes:
- Added optional Redis-backed distributed login lockout.
- Added optional Redis-backed distributed global rate-limiter.
- Fail-open fallback to in-memory behavior when Redis is unavailable.

9. Production startup weak-policy gaps  
Status: Closed  
Changes:
- Enforced startup checks for:
  - `AUTH_AUTO_PROVISION_USERS=false` in production
  - non-default bootstrap admin password when bootstrap is enabled
  - `REDIS_URL` presence when distributed security limiters are enabled

10. Frontend dependency CVEs (`next`, `mermaid`)  
Status: Closed (prod dependencies)  
Changes:
- Upgraded `next` to `15.5.14`
- Pinned `mermaid` to `10.9.5`
- `npm audit --omit=dev` reports `0` vulnerabilities.

## Remaining Risks / Follow-ups

1. CSRF strictness for `/api/v1/auth/refresh`  
Current state:
- Refresh is intentionally exempted in CSRF middleware to preserve compatibility for legacy clients.  
Recommendation:
- Move refresh to strict CSRF path for browser clients and add explicit mobile/non-browser token-refresh channel.

2. Instance-level fallback behavior when Redis is down  
Current state:
- Security controls fail-open to keep service availability.  
Recommendation:
- For strict environments, add `SECURITY_FAIL_CLOSED=true` mode to block auth/rate-sensitive actions when Redis is unavailable.

3. Deprecation cleanup (non-security)  
Current state:
- FastAPI `@on_event` and a few deprecated HTTP status symbols still appear in warnings.  
Recommendation:
- Migrate to lifespan API and updated status constants to reduce maintenance drift.

## Verification Snapshot

- API regression suite (security/auth/core flows): pass
- ML focused suite: pass
- Web lint/build: pass
- `npm audit --omit=dev`: 0 vulnerabilities
- `pip-audit` (API + ML): no known vulnerabilities
