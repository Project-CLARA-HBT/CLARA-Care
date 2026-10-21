# Risk Register: PH03_A04 CSRF Bearer/Cookie Differential & Audit

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH03-A04-01** | Cross-Site Request Forgery (CSRF) | An attacker tricks an authenticated user's browser into executing state-mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) carrying ambient session cookies. | Critical | Medium | `enforce_csrf_for_cookie_session` middleware mandates matching double-submit `clara_csrf_token` cookie and `X-CSRF-Token` header for all cookie-authenticated mutations. | Controlled |
| **RR-PH03-A04-02** | Bearer Header Smuggling / Transport Confusion | An attacker supplies a junk/malformed `Authorization: Bearer <junk>` header to bypass CSRF, expecting the backend to ignore the header and fall back to the victim's session cookie. | Critical | Low | `has_valid_explicit_bearer_token` rigorously parses, decodes, and validates the bearer token signature and revocation status. Malformed or invalid headers return `False`, enforcing CSRF on the accompanying cookie session. Furthermore, `_extract_access_token` in `rbac.py` prevents transport fallback to cookies when an explicit Bearer scheme is present. | Controlled |
| **RR-PH03-A04-03** | Revoked Bearer Token CSRF Bypass | An attacker uses a revoked or denylisted Bearer token from a terminated session to bypass CSRF checks. | High | Low | `has_valid_explicit_bearer_token` consults `_reject_if_revoked` against `session_security.is_revoked(jti)`. If the token is revoked, exemption returns `False`. If the request also lacks a valid CSRF token, it is rejected with 403. | Controlled |
| **RR-PH03-A04-04** | RFC 7235 Scheme Case Sensitivity Vulnerability | A client sends mixed-case schemes (`bearer`, `BEARER`) which might evade strict string matching in one filter while matching in another. | Medium | Low | Scheme parsing uses `scheme.lower() == "bearer"`, ensuring complete parity across `_has_bearer_scheme`, `extract_bearer_token`, and the CSRF middleware. | Controlled |
| **RR-PH03-A04-05** | Timing Side-Channel on CSRF Token Comparison | Comparison of CSRF token strings using standard equality operators (`==`) leaks token byte lengths and prefixes via timing differences. | Medium | Low | `main.py` explicitly utilizes `secrets.compare_digest(csrf_cookie, csrf_header)` for constant-time evaluation. | Controlled |
| **RR-PH03-A04-06** | Telemetry / PII Leakage in Auth Failures | Auth and CSRF error responses leak user identifiers, session IDs, or internal stack traces. | High | Low | Rejections return fixed, static payloads (e.g. `{"detail": "CSRF validation failed"}` and `{"detail": "Token đã bị thu hồi"}`) with zero PII or internal state reflection. | Controlled |

---

## Architectural Invariants & Safety Guarantees

1. **Strict Double-Submit Protection:** Mutating actions (`POST`, `PUT`, `PATCH`, `DELETE`) with cookie sessions are gated by `secrets.compare_digest`.
2. **Conditional Bearer Exemption:** Bearer authentication is exempt from CSRF only when the credential is valid, unexpired, well-formed, and unrevoked.
3. **No Transport Fallback:** Requests attempting Bearer authentication are bound to Bearer resolution; invalid credentials fail authentication rather than silently switching to cookie authorization.
4. **No-PII Telemetry:** Constant-time comparison and static error descriptions preserve privacy and security invariants.
